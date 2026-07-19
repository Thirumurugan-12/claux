"""P7 tests for collective resolution.

The two things worth pinning down without a database:
  * the cannot-link constraints (patronymic key, birth-year span) that stop the
    transitive over-merge, and
  * the collective boost itself — a pair that is *below* auto-merge on name evidence
    alone crosses the line once its co-offenders resolve to the same person.
"""

from __future__ import annotations

from er.names import normalize_token, parse
from er.records import PartyRecord
from er.resolve import ResolveConfig, UnionFind, resolve
from er.scoring import AUTO_MERGE


def rec(
    idx,
    name,
    *,
    gender=1,
    age=40,
    reg_year=2024,
    district=1,
    station=10,
    case=None,
    events=frozenset(),
    role="accused",
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
        arrest_events=events,
    )


# --- cannot-link constraints ------------------------------------------------


def test_unionfind_patronymic_cannot_link():
    uf = UnionFind(3, labels=["MR", "MR", "ML"])
    assert uf.union(0, 1) is True  # same patronymic key merges
    assert uf.union(0, 2) is False  # different key refused
    assert uf.find(0) != uf.find(2)


def test_unionfind_birth_span_cannot_link():
    uf = UnionFind(3, births=[1980, 1982, 1990], max_birth_span=5)
    assert uf.union(0, 1) is True  # 2 years apart, ok
    assert uf.union(0, 2) is False  # 10 years apart, refused


def test_unionfind_birth_span_accumulates():
    # a chain 1980-1983-1986 must be refused once the span exceeds the bound
    uf = UnionFind(3, births=[1980, 1983, 1986], max_birth_span=5)
    assert uf.union(0, 1) is True
    assert uf.union(1, 2) is False  # 1980..1986 span is 6 > 5


# --- collective resolution --------------------------------------------------


def _collective_scenario():
    # Two 'Ramesh @ Rami' records with NO patronymic and in different districts: on
    # name+alias+age alone they score ~0.75 (review, below auto-merge). Each is
    # co-arrested with a 'Suresh'; the two Sureshes auto-merge on their own, so the
    # Rameshes share a resolved co-offender and should be boosted over the line.
    r0 = rec(0, "Ramesh @ Rami", age=40, district=1, station=10, case=1, events=frozenset({100}))
    r1 = rec(1, "Ramesh @ Rami", age=40, district=9, station=90, case=2, events=frozenset({200}))
    s0 = rec(
        2, "Suresh S/o Nanjappa", age=50, district=1, station=10, case=1, events=frozenset({100})
    )
    s1 = rec(
        3, "Suresh S/o Nanjappa", age=50, district=1, station=10, case=2, events=frozenset({200})
    )
    return [r0, r1, s0, s1]


def test_collective_boost_promotes_a_pair():
    records = _collective_scenario()
    result = resolve(records, ResolveConfig(max_rounds=3))
    # r0 and r1 end up in the same cluster only because of the network boost
    clusters = {frozenset(m) for m in result.clusters.values()}
    r_cluster = next(c for c in clusters if 0 in c)
    assert 1 in r_cluster, "collective boost failed to merge the two Rameshes"
    assert result.stats["collective_lift"] >= 1
    # the evidence records the shared resolved co-offender
    ev = result.member_evidence[0]
    assert ev.get("collective_boost", 0) > 0
    assert ev["shared_resolved_cooffenders"], "boost applied with no evidence recorded"


def test_without_cooffenders_pair_stays_in_review():
    # same records but strip the arrest events -> no network signal -> no merge
    records = _collective_scenario()
    stripped = [PartyRecord(**{**r.__dict__, "arrest_events": frozenset()}) for r in records]
    result = resolve(stripped, ResolveConfig(max_rounds=3))
    r_cluster = next(frozenset(m) for m in result.clusters.values() if 0 in m)
    assert 1 not in r_cluster, "Rameshes merged without any network evidence"
    # they should instead be sitting in the review band
    assert any(
        {result.records[wp.a].source_row_id, result.records[wp.b].source_row_id} == {0, 1}
        for wp in result.review_pairs
    )


def test_singletons_get_singleton_evidence():
    records = [
        rec(0, "Ramesh S/o Krishnappa", age=40, case=1),
        rec(1, "Girish S/o Kempegowda", age=33, case=2),
    ]
    result = resolve(records)
    assert result.member_evidence[0] == {"singleton": True}
    assert result.member_confidence[0] == 1.0


def test_auto_merge_evidence_has_signals():
    records = [
        rec(0, "Ramesh S/o Krishnappa", age=40, station=10, district=1, case=1),
        rec(1, "Ramesha S/o Krishnappa", age=41, station=10, district=1, case=2),
    ]
    result = resolve(records)
    merged = next(m for m in result.clusters.values() if len(m) > 1)
    assert set(merged) == {0, 1}
    ev = result.member_evidence[0]
    assert ev["score"] >= AUTO_MERGE and "signals" in ev and "linked_to" in ev
