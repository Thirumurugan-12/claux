"""Pairwise scoring — a 0–1 same-person probability with a full signal breakdown.

Every weight lives in :class:`ScoringWeights` so the whole model can be tuned in one
place, and :func:`score_pair` returns the per-signal contribution for *every* pair so
you can answer "why did (or didn't) these two match" — the input to the review queue
(P7) and the explainability requirement (PS1 §9).

Signals (PLAN.md §2 stage 4):
  * Jaro-Winkler on the normalized given name — always applies.
  * Patronymic agreement when both are present — strong.
  * Alias overlap — strong.
  * Age consistency — birth year within ±2y, linearly decaying.
  * Gender — a HARD GATE, not a weight: a confident mismatch forces the score to 0.
  * Geography — same station > same district > adjacent district.

Weights are calibrated so the common strong case (name + patronymic + age + geography
all agreeing) clears the 0.85 auto-merge line; name + patronymic with a *missing* age
or distant geography lands in the 0.60–0.85 review band; and a bare name + age + district
agreement with no patronymic or alias stays below 0.60 — on a small name pool that is a
coincidence waiting to happen, and it should not merge without more evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jellyfish

from er.records import PartyRecord


@dataclass
class ScoringWeights:
    # Calibrated so the CORE identity signals — same (corrupted) given name + same
    # father + consistent age — clear the 0.85 auto-merge line on their OWN, with no
    # geography. That is the flagship case: the same person across different police
    # stations. Geography and alias are bonuses, not requirements. Bare name+age with
    # no patronymic still stays below the 0.60 review floor (coincidence-prone).
    name_jw: float = 0.40
    patronymic: float = 0.35
    alias: float = 0.15
    age: float = 0.20
    geo_same_station: float = 0.08
    geo_same_district: float = 0.05
    geo_adjacent: float = 0.03
    # a name below this similarity contributes nothing (kills coincidental blocks)
    jw_floor: float = 0.80
    # measured on P2 data: corrupted-but-same patronymics score >=0.886, genuinely
    # different fathers <=0.75, so 0.85 / 0.80 cleanly separates match from mismatch.
    patronymic_floor: float = 0.85
    alias_floor: float = 0.90
    age_tolerance: int = 2
    age_decay: float = 0.2  # per-year falloff within tolerance: diff 0/1/2 -> 1.0/0.8/0.6
    # When both patronymics are present but clearly different (below this similarity),
    # that is evidence *against* a match — two people with different fathers. This is
    # what stops a common given name (all the "Anand"s) transitively over-merging.
    # Corrupted-but-same patronymics (Maranna/Marappa) sit well above this threshold.
    patronymic_mismatch_floor: float = 0.80
    patronymic_mismatch_penalty: float = 0.35


DEFAULT_WEIGHTS = ScoringWeights()

# Auto-merge / review thresholds (PLAN.md §2 stage 6, CLAUDE.md conventions).
AUTO_MERGE = 0.85
REVIEW_FLOOR = 0.60


@dataclass
class ScoredPair:
    idx_a: int
    idx_b: int
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def band(self) -> str:
        if self.score >= AUTO_MERGE:
            return "auto-merge"
        if self.score >= REVIEW_FLOOR:
            return "review"
        return "reject"


def _jw(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return jellyfish.jaro_winkler_similarity(a, b)


def _gender_mismatch(a: PartyRecord, b: PartyRecord) -> bool:
    return a.gender_id is not None and b.gender_id is not None and a.gender_id != b.gender_id


def score_pair(
    a: PartyRecord,
    b: PartyRecord,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    adjacency: dict[int, set[int]] | None = None,
) -> ScoredPair:
    """Score one candidate pair, recording every signal's contribution."""
    signals: dict[str, float] = {}
    notes: dict[str, str] = {}

    # --- hard gate: confident gender mismatch cannot be the same person ---
    if _gender_mismatch(a, b):
        return ScoredPair(a.idx, b.idx, 0.0, {"gender_gate": 0.0}, {"gender_gate": "blocked"})

    # --- name (always applies) ---
    name_sim = _jw(a.normalized_given, b.normalized_given)
    if name_sim >= weights.jw_floor:
        signals["name_jw"] = round(weights.name_jw * name_sim, 4)
    notes["name_jw"] = f"jw={name_sim:.3f}"

    # --- patronymic (both present): a match is strong, a clear mismatch is a penalty ---
    if a.normalized_patronymic and b.normalized_patronymic:
        patro_sim = _jw(a.normalized_patronymic, b.normalized_patronymic)
        if patro_sim >= weights.patronymic_floor:
            signals["patronymic"] = round(weights.patronymic * patro_sim, 4)
        elif patro_sim < weights.patronymic_mismatch_floor:
            signals["patronymic_mismatch"] = -round(weights.patronymic_mismatch_penalty, 4)
        notes["patronymic"] = f"jw={patro_sim:.3f}"

    # --- alias overlap (alias of one matches the other's given or alias) ---
    alias_sim = _best_alias_overlap(a, b)
    if alias_sim >= weights.alias_floor:
        signals["alias"] = round(weights.alias * alias_sim, 4)
        notes["alias"] = f"overlap={alias_sim:.3f}"

    # --- age consistency (±tolerance years, linear decay) ---
    if a.est_birth_year is not None and b.est_birth_year is not None:
        diff = abs(a.est_birth_year - b.est_birth_year)
        if diff <= weights.age_tolerance:
            signals["age"] = round(weights.age * max(0.0, 1 - weights.age_decay * diff), 4)
        notes["age"] = f"Δbirthyear={diff}"

    # --- geography ---
    geo, geo_note = _geo_signal(a, b, weights, adjacency or {})
    if geo:
        signals["geo"] = round(geo, 4)
    notes["geo"] = geo_note

    total = max(0.0, min(1.0, sum(signals.values())))
    return ScoredPair(a.idx, b.idx, round(total, 4), signals, notes)


def score_value(
    a: PartyRecord,
    b: PartyRecord,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    adjacency: dict[int, set[int]] | None = None,
) -> float:
    """Fast path: the 0–1 score only, no per-signal dict or notes.

    This runs on every candidate pair (millions), so it allocates nothing per call —
    the full :func:`score_pair` breakdown is computed only for the pairs that survive.
    """
    if _gender_mismatch(a, b):
        return 0.0

    # Rounds each contribution to 4 dp exactly as score_detail/score_pair do, so the
    # score a pair is clustered by never disagrees with the signal sum shown as its
    # evidence — the two must not diverge at the 0.85 auto-merge boundary.
    total = 0.0
    name_sim = _jw(a.normalized_given, b.normalized_given)
    if name_sim >= weights.jw_floor:
        total += round(weights.name_jw * name_sim, 4)

    if a.normalized_patronymic and b.normalized_patronymic:
        patro_sim = _jw(a.normalized_patronymic, b.normalized_patronymic)
        if patro_sim >= weights.patronymic_floor:
            total += round(weights.patronymic * patro_sim, 4)
        elif patro_sim < weights.patronymic_mismatch_floor:
            total -= round(weights.patronymic_mismatch_penalty, 4)

    if a.alias_norm or b.alias_norm:
        alias_sim = _best_alias_overlap(a, b)
        if alias_sim >= weights.alias_floor:
            total += round(weights.alias * alias_sim, 4)

    if a.est_birth_year is not None and b.est_birth_year is not None:
        diff = abs(a.est_birth_year - b.est_birth_year)
        if diff <= weights.age_tolerance:
            total += round(weights.age * max(0.0, 1 - weights.age_decay * diff), 4)

    if a.station_id is not None and a.station_id == b.station_id:
        total += round(weights.geo_same_station, 4)
    elif a.district_id is not None and a.district_id == b.district_id:
        total += round(weights.geo_same_district, 4)
    elif (
        adjacency
        and a.district_id is not None
        and b.district_id in adjacency.get(a.district_id, ())
    ):
        total += round(weights.geo_adjacent, 4)

    return max(0.0, min(1.0, total))


def score_detail(
    a: PartyRecord,
    b: PartyRecord,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    adjacency: dict[int, set[int]] | None = None,
) -> tuple[float, dict[str, float]]:
    """Score plus the per-signal contribution dict, but without the human-readable
    ``notes`` f-strings :func:`score_pair` builds. Used to attach evidence to the
    pairs ER keeps (cluster edges, review queue) without paying the notes cost on the
    millions of pairs that get thrown away."""
    if _gender_mismatch(a, b):
        return 0.0, {"gender_gate": 0.0}
    signals: dict[str, float] = {}

    name_sim = _jw(a.normalized_given, b.normalized_given)
    if name_sim >= weights.jw_floor:
        signals["name_jw"] = round(weights.name_jw * name_sim, 4)
    if a.normalized_patronymic and b.normalized_patronymic:
        patro_sim = _jw(a.normalized_patronymic, b.normalized_patronymic)
        if patro_sim >= weights.patronymic_floor:
            signals["patronymic"] = round(weights.patronymic * patro_sim, 4)
        elif patro_sim < weights.patronymic_mismatch_floor:
            signals["patronymic_mismatch"] = -round(weights.patronymic_mismatch_penalty, 4)
    if a.alias_norm or b.alias_norm:
        alias_sim = _best_alias_overlap(a, b)
        if alias_sim >= weights.alias_floor:
            signals["alias"] = round(weights.alias * alias_sim, 4)
    if a.est_birth_year is not None and b.est_birth_year is not None:
        diff = abs(a.est_birth_year - b.est_birth_year)
        if diff <= weights.age_tolerance:
            signals["age"] = round(weights.age * max(0.0, 1 - weights.age_decay * diff), 4)
    geo, _ = _geo_signal(a, b, weights, adjacency or {})
    if geo:
        signals["geo"] = round(geo, 4)
    return max(0.0, min(1.0, sum(signals.values()))), signals


def _best_alias_overlap(a: PartyRecord, b: PartyRecord) -> float:
    candidates = []
    if a.alias_norm:
        candidates.append(_jw(a.alias_norm, b.normalized_given))
        if b.alias_norm:
            candidates.append(_jw(a.alias_norm, b.alias_norm))
    if b.alias_norm:
        candidates.append(_jw(b.alias_norm, a.normalized_given))
    return max(candidates) if candidates else 0.0


def _geo_signal(a, b, weights, adjacency) -> tuple[float, str]:
    if a.station_id is not None and a.station_id == b.station_id:
        return weights.geo_same_station, "same station"
    if a.district_id is not None and a.district_id == b.district_id:
        return weights.geo_same_district, "same district"
    if a.district_id is not None and b.district_id in adjacency.get(a.district_id, set()):
        return weights.geo_adjacent, "adjacent district"
    return 0.0, "distant"


def score_all(
    records: list[PartyRecord],
    pairs: set[tuple[int, int]],
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    adjacency: dict[int, set[int]] | None = None,
    keep_floor: float = REVIEW_FLOOR,
) -> list[ScoredPair]:
    """Score every candidate pair on the fast path, then return the full breakdown
    only for pairs at or above ``keep_floor`` (the review band and up) — the ones ER
    actually acts on. Coincidental low-score pairs are counted, not materialized."""
    out: list[ScoredPair] = []
    for ia, ib in pairs:
        if score_value(records[ia], records[ib], weights, adjacency) >= keep_floor:
            out.append(score_pair(records[ia], records[ib], weights, adjacency))
    return out
