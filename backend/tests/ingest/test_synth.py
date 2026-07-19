"""P2 invariants for the synthetic generator.

These run purely in memory (no database) — the generator is deliberately separable
from the loader so its correctness can be pinned down fast. The date-chain and
ground-truth-consistency checks are the ones that would silently corrupt every
downstream measurement if they regressed.
"""

from __future__ import annotations

import pytest

from ingest.synth.generator import REFERENCE_NOW, Generator

CASE_COL = {  # name -> index into a ksp.case_master row
    "case_master_id": 0,
    "crime_no": 1,
    "case_no": 2,
    "crime_registered_date": 3,
    "case_category_id": 6,
    "incident_from_date": 12,
    "incident_to_date": 13,
    "info_received_ps_date": 14,
    "latitude": 15,
    "longitude": 16,
}


@pytest.fixture(scope="module")
def ds():
    return Generator(1500, seed=123).build()


def _rows(ds, table):
    return ds.tables[table]


def test_crime_no_is_well_formed(ds):
    for row in _rows(ds, "ksp.case_master"):
        crime_no = row[CASE_COL["crime_no"]]
        assert len(crime_no) == 18 and crime_no.isdigit()
        # leading digit is the case category
        assert int(crime_no[0]) == row[CASE_COL["case_category_id"]]
        # embedded year matches the registration year (or the incident year cap)
        assert 2022 <= int(crime_no[9:13]) <= 2026


def test_case_no_is_year_plus_serial(ds):
    for row in _rows(ds, "ksp.case_master"):
        assert row[CASE_COL["case_no"]] == row[CASE_COL["crime_no"]][9:]


def test_categories_include_zero_fir_and_udr(ds):
    cats = {row[CASE_COL["case_category_id"]] for row in _rows(ds, "ksp.case_master")}
    assert 1 in cats and 3 in cats and 8 in cats  # FIR, UDR, Zero FIR all present


def test_date_chain_is_monotonic(ds):
    for row in _rows(ds, "ksp.case_master"):
        incident = row[CASE_COL["incident_from_date"]]
        info = row[CASE_COL["info_received_ps_date"]]
        registered = row[CASE_COL["crime_registered_date"]]
        assert incident <= info, "incident after info-received"
        assert info.date() <= registered, "info-received after registration"
        assert registered <= REFERENCE_NOW, "registered in the future"


def test_lat_long_is_heavily_null(ds):
    rows = _rows(ds, "ksp.case_master")
    nulls = sum(1 for r in rows if r[CASE_COL["latitude"]] is None)
    assert 0.4 < nulls / len(rows) < 0.75  # the plan's "heavily null" reality


def test_cstype_only_known_labels(ds):
    for row in _rows(ds, "ksp.chargesheet_details"):
        assert row[3] in ("A", "B", "C")


def test_co_arrest_edges_exist(ds):
    junction = _rows(ds, "ksp.inv_arrest_surrender_accused")
    from collections import Counter

    per_event = Counter(arrest_id for arrest_id, _ in junction)
    multi = [e for e, n in per_event.items() if n > 1]
    assert multi, "no co-arrest events — collective ER and network tools would have no signal"


def test_ground_truth_appearances_reference_real_rows(ds):
    gt = ds.ground_truth
    accused_ids = {r[0] for r in _rows(ds, "ksp.accused")}
    victim_ids = {r[0] for r in _rows(ds, "ksp.victim")}
    comp_ids = {r[0] for r in _rows(ds, "ksp.complainant_details")}
    valid = {"accused": accused_ids, "victim": victim_ids, "complainant": comp_ids}

    total = 0
    for person in gt["people"]:
        for app in person["appearances"]:
            assert app["source_row_id"] in valid[app["role"]]
            total += 1
    assert total == gt["n_total_appearances"]
    # every party row is accounted for by exactly one ground-truth appearance
    assert total == len(accused_ids) + len(victim_ids) + len(comp_ids)


def test_recurring_people_and_overlap_present(ds):
    gt = ds.ground_truth
    assert gt["n_recurring_people"] > 0, "no one recurs — ER would have nothing to resolve"
    # at least one person appears in two different roles (victim-offender overlap)
    dual = [p for p in gt["people"] if len({a["role"] for a in p["appearances"]}) > 1]
    assert dual, "no victim-offender overlap — P7a would have nothing to find"
