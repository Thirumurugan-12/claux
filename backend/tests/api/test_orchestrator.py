"""P14 tests for the orchestration loop.

These drive the loop with a :class:`ScriptedClient` so the mechanics are tested deterministically
with no network: the multi-tool round-trip, the tool_result plumbing (ids matching, one user
message per round), the provenance chain, the RBAC-denial path (a denied tool becomes an error
result the model must relay, not hidden data), the refusal path (no tool → no invented
provenance), multi-turn context carry-forward, and the max-rounds safety valve.

The eval set's own pass rate is asserted separately in ``test_eval_set.py``.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from app.api.llm import ScriptedClient, ScriptedTurn
from app.api.orchestrator import MAX_TOOL_ROUNDS, Orchestrator
from app.db import SessionLocal
from app.tools.base import Principal, Role
from app.tools.catalog import build_registry


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def registry():
    return build_registry()


@pytest.fixture()
def a_case(session):
    row = (
        session.execute(
            text(
                "SELECT c.case_master_id, c.crime_no, c.police_station_id, u.district_id "
                "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "WHERE c.police_station_id IS NOT NULL LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    return dict(row)


def _sp(district):
    return Principal(name="sp", role=Role.SP, district_id=district)


def test_single_tool_round_trip_and_provenance(session, registry, a_case):
    llm = ScriptedClient(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text=f"Case {a_case['crime_no']} is a theft FIR."),
        ]
    )
    orch = Orchestrator(registry, llm)
    result = orch.chat(_sp(a_case["district_id"]), "show me the case", session)

    assert result.answer.startswith("Case")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool == "get_case"
    assert result.tool_calls[0].ok
    # the provenance chain surfaced the crime number the tool touched
    assert a_case["crime_no"] in result.crime_nos
    assert a_case["case_master_id"] in result.row_ids


def test_tool_result_is_fed_back_in_one_user_message(session, registry, a_case):
    """After a tool round the next request must contain exactly one user message whose content
    is the tool_result block, with a tool_use_id matching the assistant's tool_use id."""
    llm = ScriptedClient(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text="done"),
        ]
    )
    Orchestrator(registry, llm).chat(_sp(a_case["district_id"]), "q", session)

    # the SECOND request the client saw is the one carrying the tool result
    second = llm.seen[1]
    assistant = second[-2]
    tool_result_msg = second[-1]
    assert assistant["role"] == "assistant"
    use_id = assistant["content"][0]["id"]
    assert tool_result_msg["role"] == "user"
    block = tool_result_msg["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == use_id
    # the payload is real tool output, not model-authored text
    payload = json.loads(block["content"])
    assert "provenance" in payload and "data" in payload


def test_parallel_tool_calls_in_one_turn(session, registry, a_case):
    """Two tool_use blocks in a single assistant turn must both execute and both come back in
    one user message, ids matched."""
    cid = a_case["case_master_id"]
    llm = ScriptedClient(
        [
            ScriptedTurn(
                tool_calls=[
                    ("get_case", {"case_master_id": cid}),
                    ("get_case_timeline", {"case_master_id": cid}),
                ]
            ),
            ScriptedTurn(text="both fetched"),
        ]
    )
    result = Orchestrator(registry, llm).chat(_sp(a_case["district_id"]), "q", session)
    assert [c.tool for c in result.tool_calls] == ["get_case", "get_case_timeline"]
    assert all(c.ok for c in result.tool_calls)
    results_msg = llm.seen[1][-1]
    ids = {b["tool_use_id"] for b in results_msg["content"]}
    assert len(ids) == 2


def test_rbac_denial_becomes_error_result_not_hidden_data(session, registry, a_case):
    """An out-of-scope call is denied at the boundary and surfaced to the model as an error
    tool_result — never silent data. The loop keeps going so the model can relay the refusal."""
    sho_elsewhere = Principal(
        name="sho", role=Role.SHO, unit_id=a_case["police_station_id"] + 1
    )
    llm = ScriptedClient(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text="That case is outside your jurisdiction."),
        ]
    )
    result = Orchestrator(registry, llm).chat(sho_elsewhere, "show me the case", session)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].ok is False
    assert result.tool_calls[0].error
    # nothing leaked into the provenance chain
    assert result.crime_nos == []
    assert result.row_ids == []
    # the error result block is marked is_error so the model treats it as a refusal
    block = llm.seen[1][-1]["content"][0]
    assert block.get("is_error") is True
    assert "DENIED" in block["content"]


def test_refusal_path_calls_no_tool_and_has_empty_provenance(session, registry, a_case):
    """A question no tool can answer: the model refuses directly. No tool runs, so the
    provenance chain is empty — there is nothing to invent from."""
    llm = ScriptedClient(
        [ScriptedTurn(text="There is no financial data in this system; I can't answer that.")]
    )
    result = Orchestrator(registry, llm).chat(_sp(a_case["district_id"]), "bank accounts?", session)
    assert result.tool_calls == []
    assert result.crime_nos == []
    assert result.rounds == 0
    assert "can't" in result.answer.lower() or "no " in result.answer.lower()


def test_multi_turn_context_is_carried_forward(session, registry, a_case):
    cid = a_case["case_master_id"]
    sp = _sp(a_case["district_id"])
    orch = Orchestrator(
        registry,
        ScriptedClient(
            [
                ScriptedTurn(tool_calls=[("get_case", {"case_master_id": cid})]),
                ScriptedTurn(text="It's a theft case."),
                ScriptedTurn(tool_calls=[("get_case_timeline", {"case_master_id": cid})]),
                ScriptedTurn(text="Registered 3 days after the incident."),
            ]
        ),
    )
    first = orch.chat(sp, "what is this case?", session)
    second = orch.chat(sp, "how fast was it registered?", session, history=first.messages)
    # the second turn's message list contains the first turn's exchanges
    roles = [m["role"] for m in second.messages]
    assert roles.count("user") >= 3  # q1, tool_result, q2 (+ tool_result)
    assert second.answer.startswith("Registered")


def test_max_rounds_safety_valve(session, registry, a_case):
    """A model that keeps calling tools forever is stopped and forced to summarise."""
    cid = a_case["case_master_id"]
    # The valve fires the first time rounds exceeds the cap — i.e. on the (MAX+1)-th tool
    # turn. It then makes ONE more call, which must be the forced-summary turn.
    turns = [
        ScriptedTurn(tool_calls=[("get_case", {"case_master_id": cid})])
        for _ in range(MAX_TOOL_ROUNDS + 1)
    ]
    turns.append(ScriptedTurn(text="Summarising what I have."))
    result = Orchestrator(registry, ScriptedClient(turns)).chat(
        _sp(a_case["district_id"]), "loop please", session
    )
    assert result.rounds > MAX_TOOL_ROUNDS
    assert result.answer.startswith("Summarising")


def test_unknown_tool_is_an_error_not_a_crash(session, registry, a_case):
    llm = ScriptedClient(
        [
            ScriptedTurn(tool_calls=[("no_such_tool", {})]),
            ScriptedTurn(text="I couldn't find a tool for that."),
        ]
    )
    result = Orchestrator(registry, llm).chat(_sp(a_case["district_id"]), "q", session)
    assert result.tool_calls[0].ok is False
    block = llm.seen[1][-1]["content"][0]
    assert block.get("is_error") is True
