"""The LLM client boundary for the orchestration loop (P14).

The orchestrator (``app/api/orchestrator.py``) drives a manual Claude tool-calling loop.
It never imports the Anthropic SDK directly — it talks to an :class:`LLMClient`. That gives
us two things:

  * **A production path** — :class:`AnthropicClient`, which calls ``claude-opus-4-8`` with the
    tool-use schemas the registry emits, adaptive thinking, and streaming.
  * **A test/demo path** — :class:`ScriptedClient`, a deterministic fake that replays a
    pre-authored sequence of assistant turns. The loop mechanics, provenance chaining, and the
    refusal path are then fully exercised with no network and no API key. This is what the
    eval suite and the unit tests run against.

Both speak the same tiny vocabulary — a request carries the running message list plus the tool
schemas, and a reply is a normalised :class:`LLMResponse` of content blocks. The orchestrator
knows nothing about which client it holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# The message shape mirrors the Anthropic Messages API: a list of {role, content} dicts where
# content is a list of typed blocks. We keep it as plain dicts so a message list built by the
# orchestrator can be handed straight to the SDK (AnthropicClient) or to a fake (ScriptedClient).
Message = dict[str, Any]


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


ContentBlock = TextBlock | ToolUseBlock


@dataclass
class LLMResponse:
    """One assistant turn, normalised. ``stop_reason == "tool_use"`` means the loop must
    execute the requested tools and continue; otherwise the turn is the final answer."""

    content: list[ContentBlock]
    stop_reason: str

    @property
    def text(self) -> str:
        return "".join(b.text for b in self.content if isinstance(b, TextBlock))

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    def to_assistant_message(self) -> Message:
        """Re-serialise this turn as an assistant message to append to the running list."""
        blocks: list[dict[str, Any]] = []
        for b in self.content:
            if isinstance(b, TextBlock):
                blocks.append({"type": "text", "text": b.text})
            else:
                blocks.append(
                    {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                )
        return {"role": "assistant", "content": blocks}


class LLMClient(Protocol):
    def complete(
        self, system: str, messages: list[Message], tools: list[dict]
    ) -> LLMResponse: ...


# -----------------------------------------------------------------------------
# Production client — the real Claude call
# -----------------------------------------------------------------------------


class AnthropicClient:
    """Calls Claude via the official Anthropic SDK.

    Uses ``claude-opus-4-8`` for orchestration (CLAUDE.md stack), adaptive thinking, and
    streaming (so long tool-heavy turns don't hit request timeouts). The SDK is imported
    lazily so the module — and therefore the whole test suite — loads even where the
    package or an API key is absent.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        max_tokens: int = 4096,
        api_key: str | None = None,
    ) -> None:
        from anthropic import Anthropic  # lazy: only needed on the live path

        self.model = model
        self.max_tokens = max_tokens
        # A bare Anthropic() also picks up ANTHROPIC_API_KEY / an ambient credential source.
        self._client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def complete(
        self, system: str, messages: list[Message], tools: list[dict]
    ) -> LLMResponse:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
        ) as stream:
            final = stream.get_final_message()
        content: list[ContentBlock] = []
        for block in final.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(
                    ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
                )
            # thinking blocks are not replayed into the transcript we surface
        return LLMResponse(content=content, stop_reason=final.stop_reason or "end_turn")


# -----------------------------------------------------------------------------
# Test / demo client — a deterministic replay
# -----------------------------------------------------------------------------


@dataclass
class ScriptedTurn:
    """One pre-authored assistant turn. ``text`` becomes a text block; each entry in
    ``tool_calls`` becomes a tool_use block. If any tool call is present the turn stops with
    ``tool_use``; otherwise it is a final answer."""

    text: str = ""
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)

    def to_response(self, turn_index: int) -> LLMResponse:
        content: list[ContentBlock] = []
        if self.text:
            content.append(TextBlock(text=self.text))
        for j, (name, args) in enumerate(self.tool_calls):
            content.append(ToolUseBlock(id=f"toolu_{turn_index}_{j}", name=name, input=args))
        stop = "tool_use" if self.tool_calls else "end_turn"
        return LLMResponse(content=content, stop_reason=stop)


class ScriptedClient:
    """Replays a fixed list of :class:`ScriptedTurn` in order, one per ``complete`` call.

    It ignores the running message list — the script is authored to model a specific
    conversation — but records every request it received in ``seen`` so tests can assert that
    tool results were fed back correctly. Running past the end raises, which surfaces a loop
    that never terminated."""

    def __init__(self, turns: list[ScriptedTurn]) -> None:
        self._turns = turns
        self._i = 0
        self.seen: list[list[Message]] = []

    def complete(
        self, system: str, messages: list[Message], tools: list[dict]
    ) -> LLMResponse:
        self.seen.append([dict(m) for m in messages])
        if self._i >= len(self._turns):
            raise RuntimeError("ScriptedClient exhausted — the loop did not stop")
        turn = self._turns[self._i]
        resp = turn.to_response(self._i)
        self._i += 1
        return resp
