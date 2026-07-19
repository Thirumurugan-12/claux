"""P10 tests for the retrieval tools, including RBAC denial cases.

Exercised against the loaded data + person_cluster. Fixtures pull a real case and a real
multi-FIR person so scope logic is tested against the actual hierarchy.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.tools.base import Principal, Role, ToolDenied
from app.tools.catalog import build_registry
from app.tools.retrieval import (
    GetCaseTimelineTool,
    GetCaseTool,
    GetChargesheetStatusTool,
    GetPersonTool,
    SearchCasesTool,
    SearchPersonsTool,
)


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


@pytest.fixture()
def a_person(session):
    """A resolved multi-FIR person and one district they appear in."""
    pcid = session.execute(
        text(
            "SELECT person_cluster_id FROM derived.person_cluster "
            "ORDER BY member_count DESC LIMIT 1"
        )
    ).scalar_one()
    dist = session.execute(
        text(
            "SELECT u.district_id FROM derived.person_cluster_member pcm "
            "JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id "
            "JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE pcm.person_cluster_id = :id LIMIT 1"
        ),
        {"id": pcid},
    ).scalar_one()
    return {"person_cluster_id": pcid, "district_id": dist}


def _sp(district):
    return Principal(name="SP", role=Role.SP, district_id=district)


# --- get_case ----------------------------------------------------------------


def test_get_case_links_accused_to_person_cluster(session, a_case):
    result = GetCaseTool().run(
        _sp(a_case["district_id"]), {"case_master_id": a_case["case_master_id"]}, session
    )
    assert result.data["crime_no"] == a_case["crime_no"]
    assert "sections" in result.data and "accused" in result.data
    # if there is an accused, it carries a person_cluster_id key (resolved via ER, not
    # accused_master_id-as-person)
    for a in result.data["accused"]:
        assert "person_cluster_id" in a


def test_get_case_by_crime_no(session, a_case):
    result = GetCaseTool().run(
        _sp(a_case["district_id"]), {"crime_no": a_case["crime_no"]}, session
    )
    assert result.data["case_master_id"] == a_case["case_master_id"]


def test_get_case_requires_an_identifier(session):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GetCaseTool().run(_sp(1), {}, session)


def test_get_case_out_of_scope_denied(session, a_case):
    sho_elsewhere = Principal(name="sho", role=Role.SHO, unit_id=a_case["police_station_id"] + 1)
    with pytest.raises(ToolDenied):
        GetCaseTool().run(sho_elsewhere, {"case_master_id": a_case["case_master_id"]}, session)


# --- get_person --------------------------------------------------------------


def test_get_person_returns_resolved_profile(session, a_person):
    result = GetPersonTool().run(
        _sp(a_person["district_id"]), {"person_cluster_id": a_person["person_cluster_id"]}, session
    )
    assert result.data["person_cluster_id"] == a_person["person_cluster_id"]
    assert result.data["appearances"], "expected at least one in-scope FIR"
    # every appearance is inside the SP's district
    assert all(a["district_id"] == a_person["district_id"] for a in result.data["appearances"])


def test_get_person_denied_when_no_firs_in_scope(session, a_person):
    # a district the person does NOT appear in
    other = session.execute(
        text(
            "SELECT district_id FROM ksp.district WHERE district_id NOT IN ("
            "  SELECT u.district_id FROM derived.person_cluster_member pcm "
            "  JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id "
            "  JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "  WHERE pcm.person_cluster_id = :id) LIMIT 1"
        ),
        {"id": a_person["person_cluster_id"]},
    ).scalar_one()
    with pytest.raises(ToolDenied):
        GetPersonTool().run(
            _sp(other), {"person_cluster_id": a_person["person_cluster_id"]}, session
        )


def test_get_person_denied_for_policymaker(session, a_person):
    with pytest.raises(ToolDenied):
        GetPersonTool().run(
            Principal(name="pm", role=Role.POLICYMAKER),
            {"person_cluster_id": a_person["person_cluster_id"]},
            session,
        )


# --- search_persons / search_cases -------------------------------------------


def test_search_persons_scoped(session, a_person):
    result = SearchPersonsTool().run(_sp(a_person["district_id"]), {"limit": 5}, session)
    assert result.data["count"] <= 5
    assert "persons" in result.data


def test_search_cases_filters_and_scopes(session, a_case):
    result = SearchCasesTool().run(
        _sp(a_case["district_id"]), {"district_id": a_case["district_id"], "limit": 10}, session
    )
    assert result.data["cases"]
    assert all(c["district_id"] == a_case["district_id"] for c in result.data["cases"])
    assert len(result.data["cases"]) <= 10


# --- timeline / chargesheet --------------------------------------------------


def test_timeline_is_ordered_with_gaps(session, a_case):
    result = GetCaseTimelineTool().run(
        _sp(a_case["district_id"]), {"case_master_id": a_case["case_master_id"]}, session
    )
    tl = result.data["timeline"]
    assert tl[0]["event"] == "incident"
    # gaps are non-negative (the chain is monotonic)
    for ev in tl[1:]:
        if ev["gap_days_from_prev"] is not None:
            assert ev["gap_days_from_prev"] >= 0


def test_chargesheet_status_meaning(session, a_case):
    result = GetChargesheetStatusTool().run(
        _sp(a_case["district_id"]), {"case_master_id": a_case["case_master_id"]}, session
    )
    assert "has_chargesheet" in result.data
    assert result.data["cs_type_meaning"] in {
        "Chargesheet filed",
        "False case",
        "Undetected",
        "Pending / open",
        "Unknown",
    }


# --- catalog -----------------------------------------------------------------


def test_all_retrieval_tools_registered():
    names = {s["name"] for s in build_registry().anthropic_schemas()}
    assert {
        "get_case",
        "search_cases",
        "get_person",
        "search_persons",
        "get_case_timeline",
        "get_chargesheet_status",
    } <= names
