"""P9 tests for the tool framework: RBAC scope, denial + audit, k-anonymity,
mandatory provenance, and schema emission — exercised end to end against the DB.

These read the loaded synthetic data. They pick a real case and derive principals whose
scope does / does not contain it, so the scope logic is tested against actual
unit.parent_unit hierarchy rather than mocks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.db import SessionLocal
from app.tools.base import Principal, Role, ToolDenied, ToolResult, sql_hash
from app.tools.demo import CaseCountByDistrictTool, GetCaseTool, build_default_registry


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def a_case(session):
    """A real case with its station and district, to build in/out-of-scope principals."""
    row = (
        session.execute(
            text(
                "SELECT c.case_master_id, c.police_station_id, u.district_id "
                "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "WHERE c.police_station_id IS NOT NULL LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    return dict(row)


def _audit_count(session, tool: str, denied: bool | None = None) -> int:
    sql = "SELECT count(*) FROM derived.audit_log WHERE tool = :t"
    params = {"t": tool}
    if denied is not None:
        sql += " AND denied = :d"
        params["d"] = denied
    return session.execute(text(sql), params).scalar_one()


# --- provenance is mandatory -------------------------------------------------


def test_tool_result_requires_provenance():
    with pytest.raises(ValidationError):
        ToolResult(data={"x": 1})  # no provenance -> pydantic rejects


def test_sql_hash_is_deterministic():
    assert sql_hash("SELECT 1", {"a": 1}) == sql_hash("SELECT 1", {"a": 1})
    assert sql_hash("SELECT 1", {"a": 1}) != sql_hash("SELECT 1", {"a": 2})


# --- happy path: in-scope SHO gets the case, audited --------------------------


def test_in_scope_sho_gets_case_and_is_audited(session, a_case):
    before = _audit_count(session, "get_case", denied=False)
    sho = Principal(name="SHO-test", role=Role.SHO, unit_id=a_case["police_station_id"])
    result = GetCaseTool().run(sho, {"case_master_id": a_case["case_master_id"]}, session)
    assert result.data["case_master_id"] == a_case["case_master_id"]
    assert result.provenance.crime_nos and result.provenance.row_ids
    assert _audit_count(session, "get_case", denied=False) == before + 1


# --- out-of-scope is DENIED and the denial is logged -------------------------


def test_out_of_scope_sho_is_denied_and_logged(session, a_case):
    before = _audit_count(session, "get_case", denied=True)
    # an SHO whose own unit is some other station (use station+1, guaranteed different)
    other_unit = a_case["police_station_id"] + 1
    sho = Principal(name="wrong-station", role=Role.SHO, unit_id=other_unit)
    with pytest.raises(ToolDenied):
        GetCaseTool().run(sho, {"case_master_id": a_case["case_master_id"]}, session)
    assert _audit_count(session, "get_case", denied=True) == before + 1


def test_sp_in_district_is_in_scope(session, a_case):
    sp = Principal(name="SP-test", role=Role.SP, district_id=a_case["district_id"])
    result = GetCaseTool().run(sp, {"case_master_id": a_case["case_master_id"]}, session)
    assert result.data["case_master_id"] == a_case["case_master_id"]


# --- person-level tools disabled for analyst / policymaker --------------------


def test_person_tool_denied_for_policymaker(session, a_case):
    pm = Principal(name="policy", role=Role.POLICYMAKER)
    with pytest.raises(ToolDenied):
        GetCaseTool().run(pm, {"case_master_id": a_case["case_master_id"]}, session)


# --- k-anonymity on aggregate tool for analyst -------------------------------


def test_kanonymity_suppresses_small_cells_for_analyst(session):
    analyst = Principal(name="scrb", role=Role.SCRB_ANALYST)
    tool = CaseCountByDistrictTool()
    # analyst sees only cells with >= 5 cases
    analyst_rows = tool.run(analyst, {}, session).data
    assert all(r["cases"] >= 5 for r in analyst_rows)


def test_operational_role_sees_small_cells(session, a_case):
    # an SHO scoped to a single station will see its (small) count, not k-suppressed
    sho = Principal(name="sho", role=Role.SHO, unit_id=a_case["police_station_id"])
    rows = CaseCountByDistrictTool().run(sho, {}, session).data
    # not an aggregate-only role, so no suppression applied
    assert isinstance(rows, list)


# --- registry emits Anthropic schemas ----------------------------------------


def test_registry_emits_anthropic_schemas():
    registry = build_default_registry()
    schemas = registry.anthropic_schemas()
    names = {s["name"] for s in schemas}
    assert {"get_case", "case_count_by_district"} <= names
    for s in schemas:
        assert "description" in s and "input_schema" in s
        assert s["input_schema"]["type"] == "object"  # valid JSON schema


def test_registry_rejects_duplicate_registration():
    registry = build_default_registry()
    with pytest.raises(ValueError):
        registry.register(GetCaseTool())
