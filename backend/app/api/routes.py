"""The /chat API (P14).

``POST /chat`` runs the orchestration loop once and returns the answer plus its provenance
chain and the tools that were called. ``POST /chat/stream`` runs the same loop but streams
Server-Sent Events (each tool call as it fires, then the final answer) so a UI can show the
reasoning path live.

The principal comes from the request body here. In production it would come from an
authenticated session / SSO claim — RBAC is enforced at the tool boundary regardless of what
the body claims, so a forged principal can only ever *narrow* what a caller sees, never widen
it beyond what the tools allow. That is by design (PLAN.md §6): the prompt is not a security
boundary; the tool layer is.
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.llm import AnthropicClient, LLMClient, Message
from app.api.orchestrator import Orchestrator
from app.config import get_settings
from app.db import get_session
from app.tools.base import Principal
from app.tools.catalog import build_registry

router = APIRouter(tags=["chat"])


# The registry is process-wide and stateless; build it once.
@lru_cache
def get_registry():
    return build_registry()


def get_llm_client() -> LLMClient:
    """The live LLM client. Overridable in tests via FastAPI dependency_overrides so the
    route can be exercised with a ScriptedClient and no network."""
    settings = get_settings()
    key = settings.anthropic_api_key or None
    try:
        return AnthropicClient(model=settings.orchestration_model, api_key=key)
    except Exception as exc:  # SDK missing, or no ambient credential
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM client unavailable — set ANTHROPIC_API_KEY (or configure an ambient "
                f"credential) and install the anthropic SDK. ({exc})"
            ),
        ) from exc


class ChatRequest(BaseModel):
    principal: Principal
    message: str
    history: list[Message] | None = None


class ToolCallOut(BaseModel):
    tool: str
    params: dict
    ok: bool
    row_ids: list[int] = []
    crime_nos: list[str] = []
    error: str | None = None


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallOut]
    crime_nos: list[str]
    row_ids: list[int]
    rounds: int
    history: list[Message]


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
    orch = Orchestrator(get_registry(), llm)
    result = orch.chat(req.principal, req.message, session, req.history)
    return ChatResponse(
        answer=result.answer,
        tool_calls=[ToolCallOut(**vars(c)) for c in result.tool_calls],
        crime_nos=result.crime_nos,
        row_ids=result.row_ids,
        rounds=result.rounds,
        history=result.messages,
    )


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest,
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(get_llm_client),
) -> StreamingResponse:
    orch = Orchestrator(get_registry(), llm)

    def sse():
        for event in orch.iter_chat(req.principal, req.message, session, req.history):
            if event["type"] == "tool_call":
                rec = event["record"]
                payload = {
                    "type": "tool_call",
                    "tool": rec.tool,
                    "ok": rec.ok,
                    "crime_nos": rec.crime_nos,
                    "row_ids": rec.row_ids,
                    "error": rec.error,
                }
            elif event["type"] == "thinking":
                payload = {"type": "thinking", "text": event["text"]}
            elif event["type"] == "result":
                r = event["result"]
                payload = {
                    "type": "result",
                    "answer": r.answer,
                    "crime_nos": r.crime_nos,
                    "row_ids": r.row_ids,
                    "rounds": r.rounds,
                }
            else:
                continue
            yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
