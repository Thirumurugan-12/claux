"""P6 tests for pairwise scoring and blocking.

Built on in-memory PartyRecords (no database) so the scorer's behaviour is pinned
down directly: the gender gate, the auto-merge / review bands, each signal's effect,
and the blocking rules (same-FIR exclusion, the conjunctive keys).
"""

from __future__ import annotations

from er.blocking import candidate_pairs
from er.names import normalize_token, parse
from er.records import PartyRecord
from er.scoring import AUTO_MERGE, REVIEW_FLOOR, ScoringWeights, score_pair, score_value


def rec(
    idx, name, gender=1, age=40, reg_year=2024, district=1, station=10, case=None, role="accused"
):
    p = parse(name)
    est = reg_year - age if age is not None else None
    alias_norm = normalize_token(p.alias) if p.alias else None
    return PartyRecord(
        idx=idx,
        role=role,
        source_row_id=idx,
        case_master_id=case if case is not None else idx,
        raw_name=name,
        age_year=age,
        gender_id=gender,
        district_id=district,
        station_id=station,
        reg_year=reg_year,
        parsed=p,
        est_birth_year=est,
        alias_norm=alias_norm,
        arrest_events=frozenset(),
    )


def test_gender_mismatch_is_a_hard_gate():
    a = rec(0, "Ramesh S/o Krishnappa", gender=1)
    b = rec(1, "Ramesh S/o Krishnappa", gender=2)
    assert score_value(a, b) == 0.0
    assert score_pair(a, b).score == 0.0
    assert score_pair(a, b).notes.get("gender_gate") == "blocked"


def test_strong_match_auto_merges():
    # same name (spelling drift) + same patronymic + same age + same station
    a = rec(0, "Ramesh S/o Krishnappa", age=40, station=10, district=1)
    b = rec(1, "Ramesha S/o Krishnappa", age=41, station=10, district=1)
    sp = score_pair(a, b)
    assert sp.score >= AUTO_MERGE, sp.signals
    assert sp.band == "auto-merge"
    assert "name_jw" in sp.signals and "patronymic" in sp.signals and "age" in sp.signals


def test_name_and_age_only_stays_below_review():
    # no patronymic/alias: bare name + age + district agreement is coincidence-prone
    # on a small name pool and must not reach the review band on its own.
    a = rec(0, "Suresh", age=30, station=10, district=5)
    b = rec(1, "Suresha", age=31, station=11, district=5)
    sp = score_pair(a, b)
    assert sp.score < REVIEW_FLOOR, sp.signals


def test_name_plus_patronymic_without_age_is_review():
    # strong name + patronymic agreement but no age to corroborate -> ask a human
    a = rec(0, "Suresh S/o Nanjappa", age=None, station=10, district=5)
    b = rec(1, "Suresha S/o Nanjappa", age=None, station=11, district=5)
    sp = score_pair(a, b)
    assert REVIEW_FLOOR <= sp.score < AUTO_MERGE, sp.signals


def test_age_beyond_tolerance_drops_age_signal():
    a = rec(0, "Ramesh S/o Krishnappa", age=30)
    b = rec(1, "Ramesh S/o Krishnappa", age=40)  # 10y apart
    sp = score_pair(a, b)
    assert "age" not in sp.signals


def test_alias_overlap_contributes():
    a = rec(0, "Ramesh @ Rami S/o Krishnappa")
    b = rec(1, "Rami S/o Krishnappa")  # b's given name is a's alias
    sp = score_pair(a, b)
    assert "alias" in sp.signals


def test_different_names_score_low():
    a = rec(0, "Ramesh S/o Krishnappa")
    b = rec(1, "Suresh S/o Nanjappa")
    assert score_value(a, b) < REVIEW_FLOOR


def test_weights_are_configurable():
    a = rec(0, "Ramesh S/o Krishnappa", age=40, station=10)
    b = rec(1, "Ramesha S/o Krishnappa", age=41, station=10)
    low = ScoringWeights(
        name_jw=0.0,
        patronymic=0.0,
        alias=0.0,
        age=0.0,
        geo_same_station=0.0,
        geo_same_district=0.0,
        geo_adjacent=0.0,
    )
    assert score_value(a, b, low) == 0.0  # zeroed weights -> zero score


def test_signal_breakdown_is_recorded():
    a = rec(0, "Ramesh S/o Krishnappa", age=40, station=10, district=1)
    b = rec(1, "Ramesh S/o Krishnappa", age=40, station=10, district=1)
    sp = score_pair(a, b)
    # every contribution is present and they sum (capped) to the score
    assert abs(min(1.0, sum(sp.signals.values())) - sp.score) < 1e-9
    assert sp.notes["geo"] == "same station"


# --- blocking ---------------------------------------------------------------


def test_blocking_pairs_same_person_variants():
    records = [
        rec(0, "Ramesh S/o Krishnappa", age=40, district=1, station=10, case=100),
        rec(1, "Ramesha S/o Krishnappa", age=41, district=1, station=11, case=200),
    ]
    pairs = candidate_pairs(records)
    assert (0, 1) in pairs


def test_blocking_excludes_same_fir():
    # two accused in the SAME case are distinct people and must never be paired
    records = [
        rec(0, "Ramesh S/o Krishnappa", age=40, case=100),
        rec(1, "Ramesh S/o Krishnappa", age=40, case=100),
    ]
    assert candidate_pairs(records) == set()


def test_blocking_catches_cross_district_repeat_offender():
    # same name + same age, different districts -> caught by the name+age key
    records = [
        rec(0, "Manjunath S/o Kempegowda", age=35, district=1, station=10, case=1),
        rec(1, "Manjunatha S/o Kempegowda", age=36, district=9, station=90, case=2),
    ]
    assert (0, 1) in candidate_pairs(records)
