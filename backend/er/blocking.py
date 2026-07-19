"""Blocking — generate candidate pairs without comparing all N² records.

The synthetic name pool is small, so a phonetic key alone produces enormous blocks;
we instead use three *conjunctive* keys, each selective enough to keep blocks small,
and union the pairs they produce:

  1. name + gender + age  — same-sounding given name, same gender, birth year within
     ±2y. This is what catches a repeat offender **across districts** (the whole point).
  2. name + gender + district — same name in the same district, for pairs whose age
     drifted past ±2y or is missing.
  3. name + gender + patronymic — same given name and father's name, the strongest
     block, independent of geography.

Gender is folded into every key: it is a hard gate in scoring, so gender-mismatched
pairs can never merge and excluding them from blocking loses no recall while roughly
halving block sizes.

Two records in the **same FIR** are never paired: distinct rows in one case are, by
construction, distinct people. (Shared-arrest links are therefore all within-FIR and
add no same-person candidates here; that co-offending signal is P7's, not blocking's.)
"""

from __future__ import annotations

from collections import defaultdict

from er.records import PartyRecord

# If a single bucket exceeds this, sub-partition it by a name prefix before pairing,
# so one pathologically common key can't blow up the pair count.
MAX_BUCKET = 500


def _age_buckets(est_birth_year: int) -> tuple[int, ...]:
    # Emitting {by, by+1, by+2} guarantees two records with |Δbirthyear| ≤ 2 share a
    # bucket (their length-3 intervals overlap iff the difference is ≤ 2).
    return (est_birth_year, est_birth_year + 1, est_birth_year + 2)


def _keys(r: PartyRecord) -> list[tuple]:
    keys: list[tuple] = []
    if not r.phonetic_key or r.gender_id is None:
        return keys
    pk, g = r.phonetic_key, r.gender_id
    if r.est_birth_year is not None:
        for b in _age_buckets(r.est_birth_year):
            keys.append(("na", pk, g, b))
    if r.district_id is not None:
        keys.append(("nd", pk, g, r.district_id))
    if r.patronymic_key:
        keys.append(("np", pk, g, r.patronymic_key))
    return keys


def candidate_pairs(records: list[PartyRecord]) -> set[tuple[int, int]]:
    """Return the deduplicated set of candidate index pairs to score."""
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for r in records:
        for key in _keys(r):
            buckets[key].append(r.idx)

    pairs: set[tuple[int, int]] = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        if len(members) <= MAX_BUCKET:
            _emit(records, members, pairs)
        else:
            _emit_subblocked(records, members, pairs)
    return pairs


def _emit(records: list[PartyRecord], members: list[int], pairs: set[tuple[int, int]]) -> None:
    for a in range(len(members)):
        ia = members[a]
        ca = records[ia].case_master_id
        for b in range(a + 1, len(members)):
            ib = members[b]
            if records[ib].case_master_id == ca:  # same FIR -> distinct people, skip
                continue
            pairs.add((ia, ib) if ia < ib else (ib, ia))


def _emit_subblocked(
    records: list[PartyRecord], members: list[int], pairs: set[tuple[int, int]]
) -> None:
    # Split an oversized bucket by a 5-char normalized-name prefix and pair within.
    sub: dict[str, list[int]] = defaultdict(list)
    for i in members:
        sub[records[i].normalized_given[:5]].append(i)
    for group in sub.values():
        if len(group) >= 2:
            _emit(records, group, pairs)


def block_stats(records: list[PartyRecord]) -> dict[str, int]:
    pairs = candidate_pairs(records)
    return {"records": len(records), "candidate_pairs": len(pairs)}
