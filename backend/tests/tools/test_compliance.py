"""P11 tests for the compliance tools — the chargesheet deadline board and the
registration-delay report. Pure helpers are unit-tested; the SQL is checked against
the loaded data for the invariants that make the tools correct.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.tools.base import Principal, Role
from app.tools.catalog import build_registry
from app.tools.compliance import (
    ChargesheetDeadlineWatchTool,
    RegistrationDelayReportTool,
    _bucket,
    _outlier_threshold,
)


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


ANALYST = Principal(name="scrb", role=Role.SCRB_ANALYST)  # state-wide, no scope filter


# --- pure helpers ------------------------------------------------------------


def test_bucket_boundaries():
    assert _bucket(-1) == "BREACHED"
    assert _bucket(0) == "critical (0-7d)"
    assert _bucket(7) == "critical (0-7d)"
    assert _bucket(8) == "warning (8-15d)"
    assert _bucket(15) == "warning (8-15d)"
    assert _bucket(30) == "watch (16-30d)"
    assert _bucket(31) == "ok (>30d)"


def test_outlier_threshold_math():
    assert _outlier_threshold([1.0, 1.0], 2.0) is None  # too few units
    # values 0,0,0,10 -> mean 2.5, std ~4.33, +1 std ~6.83
    t = _outlier_threshold([0, 0, 0, 10], 1.0)
    assert 6.0 < t < 7.5


# --- chargesheet_deadline_watch ---------------------------------------------


def test_deadline_board_invariants(session):
    p = {"warn_within_days": 15, "max_overdue_days": 45}
    result = ChargesheetDeadlineWatchTool().run(ANALYST, p, session)
    cases = result.data["cases"]
    assert cases, "expected flagged cases in the loaded data"
    for c in cases:
        # within the actionable window
        assert -45 <= c["days_remaining"] <= 15
        # deadline follows gravity: 90 for heinous, 60 otherwise
        assert c["deadline_days"] == (90 if c["heinous"] else 60)
        # bucket matches the days remaining
        assert c["bucket"] == _bucket(c["days_remaining"])
    # sorted by urgency (ascending days_remaining)
    assert [c["days_remaining"] for c in cases] == sorted(c["days_remaining"] for c in cases)
    # provenance carries the crime numbers
    assert len(result.provenance.row_ids) == len(cases)


def test_deadline_board_cases_really_lack_a_chargesheet(session):
    result = ChargesheetDeadlineWatchTool().run(ANALYST, {"warn_within_days": 10}, session)
    ids = [c["case_master_id"] for c in result.data["cases"][:50]]
    if not ids:
        pytest.skip("no flagged cases")
    n_with_cs = session.execute(
        text("SELECT count(*) FROM ksp.chargesheet_details WHERE case_master_id = ANY(:ids)"),
        {"ids": ids},
    ).scalar_one()
    assert n_with_cs == 0, "the board flagged a case that already has a chargesheet"
    n_with_arrest = session.execute(
        text(
            "SELECT count(DISTINCT case_master_id) FROM ksp.arrest_surrender "
            "WHERE case_master_id = ANY(:ids)"
        ),
        {"ids": ids},
    ).scalar_one()
    assert n_with_arrest == len(ids), "the board flagged a case without an arrest"


def test_deadline_board_max_overdue_bounds_result(session):
    tight = ChargesheetDeadlineWatchTool().run(
        ANALYST, {"warn_within_days": 15, "max_overdue_days": 10}, session
    )
    wide = ChargesheetDeadlineWatchTool().run(
        ANALYST, {"warn_within_days": 15, "max_overdue_days": 120}, session
    )
    assert wide.data["total_flagged"] >= tight.data["total_flagged"]
    assert all(c["days_remaining"] >= -10 for c in tight.data["cases"])


def test_deadline_board_scoped_to_district(session):
    # find a district that actually has flagged cases
    full = ChargesheetDeadlineWatchTool().run(ANALYST, {"warn_within_days": 30}, session)
    a_district = full.data["cases"][0]["district_id"]
    scoped = ChargesheetDeadlineWatchTool().run(
        ANALYST, {"warn_within_days": 30, "district_id": a_district}, session
    )
    assert scoped.data["cases"]
    assert all(c["district_id"] == a_district for c in scoped.data["cases"])


# --- registration_delay_report ----------------------------------------------


def test_registration_delay_outlier_flag_is_consistent(session):
    result = RegistrationDelayReportTool().run(
        ANALYST, {"min_cases": 20, "outlier_z": 2.0}, session
    )
    units = result.data["units"]
    assert units
    threshold = result.data["outlier_threshold_days"]
    for u in units:
        assert u["is_outlier"] == (u["avg_lag_days"] > threshold)
    # sorted worst-first
    assert [u["avg_lag_days"] for u in units] == sorted(
        (u["avg_lag_days"] for u in units), reverse=True
    )
    assert result.data["caveat"]  # the ecological-inference caveat must reach the user


def test_registration_delay_kanon_for_analyst(session):
    # aggregate + count_field=cases -> analyst never sees a unit with < 5 cases
    result = RegistrationDelayReportTool().run(ANALYST, {"min_cases": 1}, session)
    assert all(u["cases"] >= 5 for u in result.data["units"])


# --- catalog -----------------------------------------------------------------


def test_compliance_tools_registered_in_catalog():
    names = {s["name"] for s in build_registry().anthropic_schemas()}
    assert {"chargesheet_deadline_watch", "registration_delay_report"} <= names
