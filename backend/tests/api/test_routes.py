"""P14 — the /chat FastAPI route, exercised with a ScriptedClient via dependency_overrides so
no API key or network is needed. Proves request/response shape, the provenance in the body,
and that the route enforces RBAC through the same tool boundary (denials don't leak data).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.llm import ScriptedClient, ScriptedTurn
from app.api.routes import get_llm_client
from app.db import SessionLocal
from app.main import app


@pytest.fixture()
def a_case():
    s = SessionLocal()
    try:
        row = (
            s.execute(
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
    finally:
        s.close()


def _override_llm(turns):
    def _factory():
        return ScriptedClient(turns)

    return _factory


def test_chat_route_returns_answer_and_provenance(a_case):
    app.dependency_overrides[get_llm_client] = _override_llm(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text=f"Case {a_case['crime_no']} summary."),
        ]
    )
    try:
        client = TestClient(app)
        resp = client.post(
            "/chat",
            json={
                "principal": {"name": "sp", "role": "sp", "district_id": a_case["district_id"]},
                "message": "show me the case",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"].startswith("Case")
        assert a_case["crime_no"] in body["crime_nos"]
        assert body["tool_calls"][0]["tool"] == "get_case"
        assert body["tool_calls"][0]["ok"] is True
        assert body["history"]  # returned for multi-turn continuation
    finally:
        app.dependency_overrides.clear()


def test_chat_route_relays_rbac_denial_without_data(a_case):
    app.dependency_overrides[get_llm_client] = _override_llm(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text="That case is outside your jurisdiction."),
        ]
    )
    try:
        client = TestClient(app)
        resp = client.post(
            "/chat",
            json={
                "principal": {
                    "name": "sho",
                    "role": "sho",
                    "unit_id": a_case["police_station_id"] + 1,
                },
                "message": "show me the case",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tool_calls"][0]["ok"] is False
        assert body["crime_nos"] == []
    finally:
        app.dependency_overrides.clear()


def test_demo_principals_lists_all_roles_with_ids():
    client = TestClient(app)
    resp = client.get("/demo/principals")
    assert resp.status_code == 200
    roles = {r["role"] for r in resp.json()["roles"]}
    assert {"sho", "dysp", "sp", "scrb_analyst", "policymaker"} <= roles
    by_role = {r["role"]: r for r in resp.json()["roles"]}
    # operational roles are populated with real scope ids
    assert by_role["sho"]["principal"]["unit_id"] is not None
    assert by_role["sp"]["principal"]["district_id"] is not None
    # state roles carry no unit/district
    assert "unit_id" not in by_role["scrb_analyst"]["principal"]


def test_case_lookup_returns_case_for_in_scope_principal(a_case):
    client = TestClient(app)
    resp = client.post(
        "/case",
        json={
            "principal": {"name": "sp", "role": "sp", "district_id": a_case["district_id"]},
            "crime_no": a_case["crime_no"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["crime_no"] == a_case["crime_no"]


def test_case_lookup_denied_out_of_scope_is_403(a_case):
    client = TestClient(app)
    resp = client.post(
        "/case",
        json={
            "principal": {
                "name": "sho",
                "role": "sho",
                "unit_id": a_case["police_station_id"] + 1,
            },
            "case_master_id": a_case["case_master_id"],
        },
    )
    assert resp.status_code == 403


def test_chat_stream_route_emits_events(a_case):
    app.dependency_overrides[get_llm_client] = _override_llm(
        [
            ScriptedTurn(tool_calls=[("get_case", {"case_master_id": a_case["case_master_id"]})]),
            ScriptedTurn(text="Streamed answer."),
        ]
    )
    try:
        client = TestClient(app)
        with client.stream(
            "POST",
            "/chat/stream",
            json={
                "principal": {"name": "sp", "role": "sp", "district_id": a_case["district_id"]},
                "message": "show me the case",
            },
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
        assert "tool_call" in body
        assert "result" in body
    finally:
        app.dependency_overrides.clear()
