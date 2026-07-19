"""P13 tests for the trend + hotspot tools. Pure helpers are unit-tested; the SQL and the
geo-honesty / category-digit logic are checked against the loaded data for the invariants
that make each tool correct and truthful.
"""

from __future__ import annotations

import pytest

from app.db import SessionLocal
from app.tools.base import Principal, Role
from app.tools.catalog import build_registry
from app.tools.trends import (
    CompareToBaselineTool,
    CrimeTrendTool,
    HotspotScanTool,
    SeasonalityTool,
    SpatioTemporalClustersTool,
    ZeroFirFlowsTool,
    parse_crime_no,
)


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


ANALYST = Principal(name="scrb", role=Role.SCRB_ANALYST)  # state-wide, aggregate


# --- pure helper -------------------------------------------------------------


def test_parse_crime_no():
    p = parse_crime_no("800280351202600001")
    assert p == {"category": 8, "district": 28, "station": 351, "year": 2026, "serial": 1}
    assert parse_crime_no("123") is None
    assert parse_crime_no(None) is None
    assert parse_crime_no("80028035120260000X") is None  # non-digit


# --- crime_trend -------------------------------------------------------------


def test_crime_trend_buckets_and_totals(session):
    result = CrimeTrendTool().run(ANALYST, {"period": "month"}, session)
    series = result.data["series"]
    assert series
    # chronologically ordered
    assert [s["period"] for s in series] == sorted(s["period"] for s in series)
    assert result.data["total"] == sum(s["count"] for s in series)


def test_crime_trend_scoped_to_district(session):
    sp = Principal(name="sp", role=Role.SP, district_id=1)
    full = CrimeTrendTool().run(ANALYST, {"period": "year"}, session).data["total"]
    scoped = CrimeTrendTool().run(sp, {"period": "year"}, session).data["total"]
    assert 0 < scoped < full  # a single district is a strict subset of the state


# --- hotspot_scan (geo honesty) ---------------------------------------------


def test_hotspot_scan_reports_precise_vs_inferred(session):
    result = HotspotScanTool().run(ANALYST, {"eps_km": 2.0, "min_samples": 5}, session)
    cov = result.data["coverage"]
    # the precise/inferred split must add up and be reported openly
    assert cov["precise"] + cov["inferred_centroid_only"] == cov["total_cases"]
    assert 0 < cov["precise"] < cov["total_cases"]  # data is ~58% null
    # every hotspot is built from precise points only
    assert all(h["point_type"] == "precise" for h in result.data["hotspots"])
    assert "centroid" in result.data["caveat"].lower()


def test_hotspot_scan_min_samples_respected(session):
    result = HotspotScanTool().run(ANALYST, {"eps_km": 1.0, "min_samples": 10}, session)
    assert all(h["size"] >= 10 for h in result.data["hotspots"])


# --- spatiotemporal_clusters -------------------------------------------------


def test_spatiotemporal_daypart_labelling(session):
    result = SpatioTemporalClustersTool().run(ANALYST, {"top": 10}, session)
    cells = result.data["hot_cells"]
    assert cells
    assert [c["count"] for c in cells] == sorted((c["count"] for c in cells), reverse=True)
    valid = {"night (00-06)", "morning (06-12)", "afternoon (12-18)", "evening (18-24)"}
    assert all(c["daypart"] in valid for c in cells)


# --- compare_to_baseline -----------------------------------------------------


def test_compare_to_baseline_zscore_and_redzone_flag(session):
    result = CompareToBaselineTool().run(
        ANALYST, {"window_days": 30, "baseline_windows": 6, "z_threshold": 2.0}, session
    )
    districts = result.data["districts"]
    assert districts
    for d in districts:
        # the red-zone flag is consistent with the z-score and threshold
        if d["z_score"] is not None:
            assert d["is_red_zone"] == (d["z_score"] >= 2.0)
        assert "recent_count" in d and "baseline_mean" in d
    assert result.data["red_zone_count"] == sum(d["is_red_zone"] for d in districts)


# --- seasonality -------------------------------------------------------------


def test_seasonality_months_and_dow(session):
    result = SeasonalityTool().run(ANALYST, {}, session)
    assert result.data["by_month"]
    assert 1 <= result.data["peak_month"] <= 12
    assert 0 <= result.data["peak_day_of_week"] <= 6
    assert all(1 <= m["month"] <= 12 for m in result.data["by_month"])


# --- zero_fir_flows ----------------------------------------------------------


def test_zero_fir_flows_identifies_category_8(session):
    result = ZeroFirFlowsTool().run(ANALYST, {"top": 20}, session)
    assert result.data["total_zero_firs"] > 0
    # every provenance crime_no is genuinely a category-8 Zero FIR
    for cn in result.provenance.crime_nos:
        assert parse_crime_no(cn)["category"] == 8
    # by-district counts sum to no more than the total (k-anon may drop small cells)
    assert sum(d["zero_firs"] for d in result.data["by_registering_district"]) <= (
        result.data["total_zero_firs"]
    )
    # flows are only reported on genuine divergence; the note explains the empty case
    assert "CrimeNo" in result.data["note"]


# --- catalog -----------------------------------------------------------------


def test_trend_tools_registered():
    names = {s["name"] for s in build_registry().anthropic_schemas()}
    assert {
        "crime_trend",
        "hotspot_scan",
        "spatiotemporal_clusters",
        "compare_to_baseline",
        "seasonality",
        "zero_fir_flows",
    } <= names
