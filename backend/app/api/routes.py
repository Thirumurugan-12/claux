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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.llm import LLMClient, Message, client_from_settings
from app.api.orchestrator import Orchestrator
from app.config import get_settings
from app.db import get_session
from app.tools.base import Principal, Role, ToolDenied
from app.tools.catalog import build_registry

router = APIRouter(tags=["chat"])


# The registry is process-wide and stateless; build it once.
@lru_cache
def get_registry():
    return build_registry()


def get_llm_client() -> LLMClient:
    """The live LLM client, selected by LLM_PROVIDER — Catalyst UniAI (default, BYOK from
    the Catalyst console) or direct Anthropic. Overridable in tests via FastAPI
    dependency_overrides so the route can be exercised with a ScriptedClient and no network."""
    try:
        return client_from_settings(get_settings())
    except Exception as exc:  # unconfigured provider, missing SDK, etc.
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM client unavailable — for Catalyst UniAI set UNIAI_BASE_URL, "
                "UNIAI_API_KEY and UNIAI_MODEL (or set LLM_PROVIDER=anthropic with "
                f"ANTHROPIC_API_KEY). ({exc})"
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
    data: Any = None


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
                    "params": rec.params,
                    "ok": rec.ok,
                    "crime_nos": rec.crime_nos,
                    "row_ids": rec.row_ids,
                    "error": rec.error,
                    "data": rec.data,  # lets the UI paint network/map panes from the result
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


# -----------------------------------------------------------------------------
# Shell support (P19): demo principals for the role switcher, and a case lookup for
# clickable CrimeNos in the evidence pane.
# -----------------------------------------------------------------------------


@router.get("/demo/principals")
def demo_principals(session: Session = Depends(get_session)) -> dict:
    """One ready-to-use principal per role, populated with real IDs from the loaded data so
    the RBAC role-switcher in the UI actually resolves scope. State roles carry no unit."""
    top_station = session.execute(
        text(
            "SELECT c.police_station_id, u.district_id, u.unit_name "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "GROUP BY 1, 2, 3 ORDER BY count(*) DESC LIMIT 1"
        )
    ).mappings().first()
    top_parent = session.execute(
        text(
            "SELECT u.parent_unit AS unit_id, pu.unit_name "
            "FROM ksp.unit u JOIN ksp.case_master c ON c.police_station_id = u.unit_id "
            "JOIN ksp.unit pu ON pu.unit_id = u.parent_unit "
            "WHERE u.parent_unit IS NOT NULL GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 1"
        )
    ).mappings().first()
    top_district = session.execute(
        text(
            "SELECT u.district_id, d.district_name "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "JOIN ksp.district d ON d.district_id = u.district_id "
            "GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 1"
        )
    ).mappings().first()

    roles = [
        {
            "role": Role.SHO.value,
            "label": "SHO",
            "scope": f"Station {top_station['unit_name']}" if top_station else "one station",
            "principal": {
                "name": "Demo SHO",
                "role": Role.SHO.value,
                "unit_id": top_station["police_station_id"] if top_station else None,
                "district_id": top_station["district_id"] if top_station else None,
            },
        },
        {
            "role": Role.DYSP.value,
            "label": "DySP",
            "scope": f"Subdivision {top_parent['unit_name']}" if top_parent else "a subdivision",
            "principal": {
                "name": "Demo DySP",
                "role": Role.DYSP.value,
                "unit_id": top_parent["unit_id"] if top_parent else None,
            },
        },
        {
            "role": Role.SP.value,
            "label": "SP",
            "scope": f"District {top_district['district_name']}" if top_district else "a district",
            "principal": {
                "name": "Demo SP",
                "role": Role.SP.value,
                "district_id": top_district["district_id"] if top_district else None,
            },
        },
        {
            "role": Role.SCRB_ANALYST.value,
            "label": "SCRB Analyst",
            "scope": "State-wide, aggregate only",
            "principal": {"name": "Demo Analyst", "role": Role.SCRB_ANALYST.value},
        },
        {
            "role": Role.POLICYMAKER.value,
            "label": "Policymaker",
            "scope": "State-wide, aggregate only",
            "principal": {"name": "Demo Policymaker", "role": Role.POLICYMAKER.value},
        },
    ]
    return {"roles": roles}


class CaseLookupRequest(BaseModel):
    principal: Principal
    crime_no: str | None = None
    case_master_id: int | None = None


@router.post("/case")
def get_case(req: CaseLookupRequest, session: Session = Depends(get_session)) -> dict:
    """Fetch one FIR through the get_case tool (RBAC + provenance enforced), for the clickable
    CrimeNos in the evidence pane. A denial is a real answer, returned as 403."""
    from app.tools.retrieval import GetCaseTool

    params = {}
    if req.case_master_id is not None:
        params["case_master_id"] = req.case_master_id
    elif req.crime_no:
        params["crime_no"] = req.crime_no
    else:
        raise HTTPException(status_code=422, detail="provide crime_no or case_master_id")
    try:
        result = GetCaseTool().run(req.principal, params, session)
    except ToolDenied as denied:
        raise HTTPException(status_code=403, detail=str(denied)) from denied
    return {"data": result.data, "provenance": result.provenance.model_dump()}
