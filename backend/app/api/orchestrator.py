"""The orchestration loop (P14) — the merge point where the tool catalogue becomes a
conversation.

This is a **manual** Claude tool-calling loop (not the SDK tool runner) because every tool
call has to pass through :meth:`ToolRegistry.call`, which is where RBAC, provenance, and the
audit log live (P9). The loop:

  1. sends the running conversation + the registry's tool schemas to the LLM,
  2. if the model asked to use tools, executes each one *through the registry with the
     caller's principal* — so an out-of-scope request is denied at the boundary, not by the
     prompt — feeds the results back, and repeats,
  3. otherwise returns the model's final answer together with the **provenance chain**: every
     CrimeNo and row id that any tool touched on the way to the answer.

The system prompt encodes CLAUDE.md's two hardest rules — *the LLM never authors a fact* and
*when no tool can answer, say so; never guess*. But the prompt is the soft layer: a denied or
empty tool result is a fact the model must relay, and the provenance chain is what proves the
answer was assembled from tool output rather than invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.api.llm import LLMClient, Message
from app.tools.base import Principal, ToolDenied, ToolRegistry

MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """\
You are the analyst assistant for the Karnataka State Police Crime Intelligence Platform.
You answer questions about the FIR database for an authenticated police user.

HARD RULES — these are not style preferences, they are the integrity guarantees of the system:

1. You never author a fact. Every number, name, date, place, section, and status in your
   answer MUST come from a tool result in this conversation. You do not estimate, infer,
   extrapolate, or fill gaps from general knowledge. If you did not get it from a tool, you
   do not say it.

2. You never write SQL and you never invent a tool. You may only call the tools provided.
   Choose the tool whose description matches the question and supply its parameters.

3. When no available tool can answer the question, say so plainly and stop. Do not guess and
   do not apologise your way into a fabricated answer. A truthful "I can't answer that with
   the tools I have" is correct; a plausible invented answer is a serious failure.

4. A tool may refuse a call because the user is outside their jurisdiction (access denied),
   or return no rows. That refusal or emptiness is itself the answer — relay it honestly
   ("that case is outside your authorised scope", "no cases match"). Never work around a
   denial or present withheld data.

5. Identity across FIRs comes only from get_person / the person_cluster the tools return.
   Never treat an accused_master_id as a stable person identifier.

Be concise and factual. Cite the CrimeNo(s) your answer rests on. When you state a figure,
make clear which tool result it came from.
"""


@dataclass
class ToolCallRecord:
    """One executed tool call, for the transcript and the provenance chain. ``data`` is the
    tool's result payload — carried so the UI (P19) can render a returned network graph or
    hotspot set in its visual panes without re-running the tool."""

    tool: str
    params: dict[str, Any]
    ok: bool
    row_ids: list[int] = field(default_factory=list)
    crime_nos: list[str] = field(default_factory=list)
    error: str | None = None
    data: Any = None


@dataclass
class ChatResult:
    answer: str
    tool_calls: list[ToolCallRecord]
    rounds: int
    messages: list[Message]  # the full running list, for multi-turn continuation

    @property
    def crime_nos(self) -> list[str]:
        seen: dict[str, None] = {}
        for c in self.tool_calls:
            for cn in c.crime_nos:
                seen.setdefault(cn, None)
        return list(seen)

    @property
    def row_ids(self) -> list[int]:
        seen: dict[int, None] = {}
        for c in self.tool_calls:
            for rid in c.row_ids:
                seen.setdefault(rid, None)
        return list(seen)


def _tool_result_block(tool_use_id: str, payload: str, is_error: bool = False) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": payload}
    if is_error:
        block["is_error"] = True
    return block


class Orchestrator:
    """Runs the tool-calling loop for one principal against one tool registry."""

    def __init__(
        self,
        registry: ToolRegistry,
        llm: LLMClient,
        system_prompt: str = SYSTEM_PROMPT,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.system_prompt = system_prompt
        self.max_rounds = max_rounds
        self._schemas = registry.anthropic_schemas()

    def chat(
        self,
        principal: Principal,
        user_message: str,
        session: Session,
        history: list[Message] | None = None,
    ) -> ChatResult:
        """Answer one user message. ``history`` carries prior turns for multi-turn context;
        the returned ``ChatResult.messages`` is the updated list to pass back next turn."""
        result: ChatResult | None = None
        for event in self.iter_chat(principal, user_message, session, history):
            if event["type"] == "result":
                result = event["result"]
        assert result is not None  # iter_chat always ends with a result event
        return result

    def iter_chat(
        self,
        principal: Principal,
        user_message: str,
        session: Session,
        history: list[Message] | None = None,
    ):
        """The loop as an event generator. Yields ``{"type": "tool_call", ...}`` as each tool
        runs and a terminal ``{"type": "result", "result": ChatResult}``. :meth:`chat` is a
        thin drain of this; the streaming route forwards the events to the client."""
        messages: list[Message] = list(history or [])
        messages.append({"role": "user", "content": user_message})

        calls: list[ToolCallRecord] = []
        rounds = 0
        while True:
            resp = self.llm.complete(self.system_prompt, messages, self._schemas)
            messages.append(resp.to_assistant_message())
            if resp.text:
                yield {"type": "thinking", "text": resp.text}

            if resp.stop_reason != "tool_use" or not resp.tool_uses:
                result = ChatResult(
                    answer=resp.text, tool_calls=calls, rounds=rounds, messages=messages
                )
                yield {"type": "result", "result": result}
                return

            rounds += 1
            if rounds > self.max_rounds:
                # Safety valve: stop looping and let the model summarise what it has.
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You have reached the tool-call limit. Answer using only the tool "
                            "results already gathered, or say you could not complete the request."
                        ),
                    }
                )
                final = self.llm.complete(self.system_prompt, messages, self._schemas)
                messages.append(final.to_assistant_message())
                result = ChatResult(
                    answer=final.text, tool_calls=calls, rounds=rounds, messages=messages
                )
                yield {"type": "result", "result": result}
                return

            result_blocks = []
            for tu in resp.tool_uses:
                record, block = self._execute(principal, tu.id, tu.name, tu.input, session)
                calls.append(record)
                result_blocks.append(block)
                yield {"type": "tool_call", "record": record}
            # All tool results for a turn go back in a SINGLE user message, ids matching.
            messages.append({"role": "user", "content": result_blocks})

    def _execute(
        self, principal: Principal, tool_use_id: str, name: str, args: dict, session: Session
    ) -> tuple[ToolCallRecord, dict]:
        import json

        try:
            result = self.registry.call(name, principal, args, session)
        except ToolDenied as denied:
            # A denial is a fact the model must relay, not an error to hide. Surface it as an
            # error tool_result so the model narrates the refusal instead of inventing data.
            rec = ToolCallRecord(tool=name, params=args, ok=False, error=str(denied))
            return rec, _tool_result_block(
                tool_use_id, f"ACCESS DENIED: {denied}", is_error=True
            )
        except KeyError as unknown:
            rec = ToolCallRecord(tool=name, params=args, ok=False, error=str(unknown))
            return rec, _tool_result_block(tool_use_id, f"NO SUCH TOOL: {unknown}", is_error=True)
        except Exception as exc:  # a broken tool must not crash the conversation
            rec = ToolCallRecord(tool=name, params=args, ok=False, error=str(exc))
            return rec, _tool_result_block(tool_use_id, f"TOOL ERROR: {exc}", is_error=True)

        prov = result.provenance
        rec = ToolCallRecord(
            tool=name,
            params=args,
            ok=True,
            row_ids=list(prov.row_ids),
            crime_nos=list(prov.crime_nos),
            data=result.data,
        )
        payload = json.dumps(
            {"data": result.data, "provenance": prov.model_dump()}, default=str
        )
        return rec, _tool_result_block(tool_use_id, payload)
