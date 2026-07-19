"""The LLM client boundary for the orchestration loop (P14).

The orchestrator (``app/api/orchestrator.py``) drives a manual tool-calling loop. It never
imports a provider SDK directly — it talks to an :class:`LLMClient`. That gives us three
interchangeable paths:

  * **Catalyst UniAI / gateway path (demo default)** — :class:`OpenAICompatClient`, which
    speaks the OpenAI chat-completions wire format over plain HTTPS. Zoho Catalyst is the
    hackathon's platform partner; its UniAI service fronts LLM providers behind a single
    Catalyst-configured key (BYOK), so pointing ``UNIAI_BASE_URL`` + ``UNIAI_API_KEY`` at it
    powers the demo without any provider SDK. The same client covers Catalyst QuickML LLM
    serving or any other OpenAI-compatible endpoint.
  * **Direct Anthropic path** — :class:`AnthropicClient`, calling ``claude-opus-4-8`` with
    adaptive thinking and streaming, when a raw Anthropic key is available.
  * **Test/demo path** — :class:`ScriptedClient`, a deterministic fake that replays a
    pre-authored sequence of assistant turns. The loop mechanics, provenance chaining, and
    the refusal path are then fully exercised with no network and no API key.

All speak the same tiny vocabulary — a request carries the running message list plus the tool
schemas, and a reply is a normalised :class:`LLMResponse` of content blocks. The message list
is kept in Anthropic block format internally; :class:`OpenAICompatClient` translates it to
the OpenAI shape on the wire, so the orchestrator knows nothing about which client it holds.
"""

from __future__ import annotations

import json
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
# Catalyst UniAI / OpenAI-compatible gateway client
# -----------------------------------------------------------------------------


class OpenAICompatClient:
    """Calls any OpenAI-chat-completions-compatible endpoint — built for **Zoho Catalyst
    UniAI** (the hackathon platform's unified AI gateway, BYOK) and equally usable against
    Catalyst QuickML LLM serving or any other compatible gateway.

    The orchestrator keeps the conversation in Anthropic block format (``tool_use`` blocks in
    assistant turns, ``tool_result`` blocks in user turns). This client translates that to the
    OpenAI wire shape per request (``tool_calls`` on assistant messages, ``role: "tool"``
    result messages) and maps the response back to :class:`LLMResponse`, so the orchestrator
    is provider-agnostic.

    Uses plain ``httpx`` rather than a provider SDK so auth quirks are configurable:
    ``auth_scheme`` is ``"bearer"`` (``Authorization: Bearer <key>``) or ``"zoho-oauthtoken"``
    (``Authorization: Zoho-oauthtoken <key>``, the Zoho OAuth convention).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        chat_path: str = "/v1/chat/completions",
        auth_scheme: str = "bearer",
        max_tokens: int = 4096,
        timeout: float = 120.0,
        transport: Any = None,  # httpx transport override, for tests
    ) -> None:
        import httpx

        if not base_url:
            raise RuntimeError("UNIAI_BASE_URL is not set")
        if not api_key:
            raise RuntimeError("UNIAI_API_KEY is not set")
        if not model:
            raise RuntimeError("UNIAI_MODEL is not set")
        self.model = model
        self.max_tokens = max_tokens
        self._url = base_url.rstrip("/") + chat_path
        scheme = {"bearer": "Bearer", "zoho-oauthtoken": "Zoho-oauthtoken"}.get(auth_scheme)
        if scheme is None:
            raise RuntimeError(f"unknown auth_scheme '{auth_scheme}'")
        self._http = httpx.Client(
            headers={"Authorization": f"{scheme} {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    # --- wire-format translation: Anthropic blocks -> OpenAI messages ---

    @staticmethod
    def _to_openai_messages(system: str, messages: list[Message]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for msg in messages:
            role, content = msg["role"], msg["content"]
            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue
            if role == "assistant":
                text = "".join(b["text"] for b in content if b.get("type") == "text")
                tool_calls = [
                    {
                        "id": b["id"],
                        "type": "function",
                        "function": {
                            "name": b["name"],
                            "arguments": json.dumps(b["input"]),
                        },
                    }
                    for b in content
                    if b.get("type") == "tool_use"
                ]
                entry: dict = {"role": "assistant", "content": text or None}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                out.append(entry)
            else:  # user turn carrying tool_result blocks -> one role:"tool" message each
                plain_parts: list[str] = []
                for b in content:
                    if b.get("type") == "tool_result":
                        out.append(
                            {
                                "role": "tool",
                                "tool_call_id": b["tool_use_id"],
                                "content": b["content"],
                            }
                        )
                    elif b.get("type") == "text":
                        plain_parts.append(b["text"])
                if plain_parts:
                    out.append({"role": "user", "content": "".join(plain_parts)})
        return out

    @staticmethod
    def _to_openai_tools(tools: list[dict]) -> list[dict]:
        """Registry schemas are Anthropic-shaped {name, description, input_schema}."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def complete(
        self, system: str, messages: list[Message], tools: list[dict]
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": self._to_openai_messages(system, messages),
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = self._to_openai_tools(tools)
        resp = self._http.post(self._url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM gateway returned {resp.status_code}: {resp.text[:500]}"
            )
        body = resp.json()
        choice = body["choices"][0]
        msg = choice["message"]

        content: list[ContentBlock] = []
        if msg.get("content"):
            content.append(TextBlock(text=msg["content"]))
        for tc in msg.get("tool_calls") or []:
            args_raw = tc["function"].get("arguments") or "{}"
            content.append(
                ToolUseBlock(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    input=json.loads(args_raw) if isinstance(args_raw, str) else args_raw,
                )
            )
        finish = choice.get("finish_reason")
        stop_reason = "tool_use" if (finish == "tool_calls" or msg.get("tool_calls")) else (
            finish or "end_turn"
        )
        return LLMResponse(content=content, stop_reason=stop_reason)


def client_from_settings(settings: Any) -> LLMClient:
    """Build the configured live client. ``llm_provider`` selects the path:

    * ``"uniai"`` (default) — Catalyst UniAI / any OpenAI-compatible gateway, from
      ``UNIAI_BASE_URL`` / ``UNIAI_API_KEY`` / ``UNIAI_MODEL`` (+ optional
      ``UNIAI_CHAT_PATH``, ``UNIAI_AUTH_SCHEME``).
    * ``"anthropic"`` — direct Anthropic SDK with ``ANTHROPIC_API_KEY``.

    Raises RuntimeError with an actionable message when the chosen path is unconfigured.
    """
    provider = getattr(settings, "llm_provider", "uniai")
    if provider == "anthropic":
        return AnthropicClient(
            model=settings.orchestration_model,
            api_key=settings.anthropic_api_key or None,
        )
    if provider == "uniai":
        return OpenAICompatClient(
            base_url=settings.uniai_base_url,
            api_key=settings.uniai_api_key,
            model=settings.uniai_model,
            chat_path=settings.uniai_chat_path,
            auth_scheme=settings.uniai_auth_scheme,
        )
    raise RuntimeError(f"unknown LLM_PROVIDER '{provider}' (use 'uniai' or 'anthropic')")


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
