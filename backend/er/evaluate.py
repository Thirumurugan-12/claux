"""P8 — score the entity-resolution pipeline against P2's hidden ground truth.

This is the harness that turns "the clusters look right" into a number. It loads the
ground-truth registry (which the resolver never sees), runs resolution, and reports:

  * **pairwise** precision / recall / F1 — over same-person pairs,
  * **B-cubed** precision / recall / F1 — the standard per-record cluster metric that
    handles singletons correctly,
  * an **error breakdown** — for the true merges we missed, which corruption type
    (missing patronymic, patronymic drift, age drift, heavy name drift, cross-district)
    is implicated, so we know where the pipeline bleeds recall, and
  * the **collective-resolution lift** — the same metrics with propagation off vs on.
    That delta is the headline number for the slide.

Ground truth is keyed by ``source_row_id``; it must correspond to the loaded database
(same generator seed/volume). The harness checks the overlap and warns if it looks off.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from er.records import PartyRecord
from er.resolve import Prepared, ResolveConfig, ResolveResult, resolve_prepared

GROUND_TRUTH = Path(__file__).resolve().parent.parent / "ingest" / "synth" / "ground_truth.json"


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float

    @staticmethod
    def from_counts(tp: int, fp: int, fn: int) -> PRF:
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        return PRF(round(p, 4), round(r, 4), round(f, 4))


def load_ground_truth(role: str = "accused", path: Path = GROUND_TRUTH) -> dict[int, int]:
    """Return {source_row_id: true_person_id} for the given role."""
    gt = json.loads(path.read_text())
    mapping: dict[int, int] = {}
    for person in gt["people"]:
        for app in person["appearances"]:
            if app["role"] == role:
                mapping[app["source_row_id"]] = person["true_person_id"]
    return mapping


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


def _labels(records: list[PartyRecord], result: ResolveResult, truth: dict[int, int]):
    """Align predicted and true cluster labels over the records present in both."""
    pred_of: dict[int, int] = {}
    for cid, members in result.clusters.items():
        for idx in members:
            pred_of[records[idx].source_row_id] = cid
    ids = [sid for sid in pred_of if sid in truth]
    pred = {sid: pred_of[sid] for sid in ids}
    true = {sid: truth[sid] for sid in ids}
    return ids, pred, true


def _groups(ids, label_of) -> dict[int, list[int]]:
    g: dict[int, list[int]] = {}
    for sid in ids:
        g.setdefault(label_of[sid], []).append(sid)
    return g


def pairwise_prf(ids, pred, true) -> PRF:
    """Precision/recall/F1 over same-person pairs. Counting is done per-group so it
    never materialises the full N² pair space."""
    pred_groups = _groups(ids, pred)
    true_groups = _groups(ids, true)
    pred_pairs = {frozenset(p) for g in pred_groups.values() for p in combinations(g, 2)}
    true_pairs = {frozenset(p) for g in true_groups.values() for p in combinations(g, 2)}
    tp = len(pred_pairs & true_pairs)
    fp = len(pred_pairs - true_pairs)
    fn = len(true_pairs - pred_pairs)
    return PRF.from_counts(tp, fp, fn)


def bcubed_prf(ids, pred, true) -> PRF:
    """B-cubed precision/recall/F1, averaged over records (singleton-safe)."""
    pred_groups = _groups(ids, pred)
    true_groups = _groups(ids, true)
    pred_size = {sid: len(pred_groups[pred[sid]]) for sid in ids}
    true_size = {sid: len(true_groups[true[sid]]) for sid in ids}
    # for each record, how many of its predicted-cluster-mates share its true cluster
    prec_sum = rec_sum = 0.0
    true_lookup = {}
    for tid, members in true_groups.items():
        true_lookup[tid] = set(members)
    for sid in ids:
        mates = pred_groups[pred[sid]]
        correct = sum(1 for m in mates if true[m] == true[sid])
        prec_sum += correct / pred_size[sid]
        rec_sum += correct / true_size[sid]
    n = len(ids)
    p, r = prec_sum / n, rec_sum / n
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return PRF(round(p, 4), round(r, 4), round(f, 4))


# -----------------------------------------------------------------------------
# Error breakdown — why did we miss a true merge?
# -----------------------------------------------------------------------------


def error_breakdown(records: list[PartyRecord], result: ResolveResult, truth: dict[int, int],
                    limit: int = 20000) -> dict[str, int]:
    """For same-person pairs the pipeline split apart, tally the corruption(s) that
    plausibly caused the miss. A pair can implicate several factors."""
    by_id = {r.source_row_id: r for r in records}
    pred_of: dict[int, int] = {}
    for cid, members in result.clusters.items():
        for idx in members:
            pred_of[records[idx].source_row_id] = cid

    true_groups: dict[int, list[int]] = {}
    for sid, tid in truth.items():
        if sid in pred_of:
            true_groups.setdefault(tid, []).append(sid)

    tally = {
        "missing_patronymic": 0, "patronymic_drift": 0, "age_drift_gt2": 0,
        "heavy_name_drift": 0, "cross_district": 0, "total_missed_pairs": 0,
    }
    seen = 0
    for members in true_groups.values():
        for s1, s2 in combinations(members, 2):
            if pred_of[s1] == pred_of[s2]:
                continue  # correctly kept together
            tally["total_missed_pairs"] += 1
            seen += 1
            if seen > limit:
                continue
            a, b = by_id[s1], by_id[s2]
            _classify_miss(a, b, tally)
    return tally


def _classify_miss(a: PartyRecord, b: PartyRecord, tally: dict[str, int]) -> None:
    import jellyfish

    pa, pb = a.normalized_patronymic, b.normalized_patronymic
    if bool(pa) != bool(pb):
        tally["missing_patronymic"] += 1
    elif pa and pb and jellyfish.jaro_winkler_similarity(pa, pb) < 0.85:
        tally["patronymic_drift"] += 1
    if a.est_birth_year is not None and b.est_birth_year is not None:
        if abs(a.est_birth_year - b.est_birth_year) > 2:
            tally["age_drift_gt2"] += 1
    if jellyfish.jaro_winkler_similarity(a.normalized_given, b.normalized_given) < 0.85:
        tally["heavy_name_drift"] += 1
    if a.district_id != b.district_id:
        tally["cross_district"] += 1


# -----------------------------------------------------------------------------
# Full evaluation (propagation off vs on)
# -----------------------------------------------------------------------------


@dataclass
class Evaluation:
    off: ResolveResult
    on: ResolveResult
    pairwise_off: PRF
    pairwise_on: PRF
    bcubed_off: PRF
    bcubed_on: PRF
    errors_on: dict[str, int]
    truth_coverage: float
    n_true_people: int
    n_true_recurring: int


def evaluate(prep: Prepared, truth: dict[int, int], cfg: ResolveConfig) -> Evaluation:
    records = prep.records
    off_cfg = ResolveConfig(**{**cfg.__dict__, "boost_per_cooffender": 0.0})
    off = resolve_prepared(prep, off_cfg, attach_review_signals=False)
    on = resolve_prepared(prep, cfg, attach_review_signals=False)

    ids, pred_off, true_off = _labels(records, off, truth)
    ids_on, pred_on, true_on = _labels(records, on, truth)

    n_true = len(set(truth.values()))
    from collections import Counter
    counts = Counter(truth.values())
    n_recurring = sum(1 for c in counts.values() if c > 1)
    coverage = len(ids_on) / len(records) if records else 0.0

    return Evaluation(
        off=off, on=on,
        pairwise_off=pairwise_prf(ids, pred_off, true_off),
        pairwise_on=pairwise_prf(ids_on, pred_on, true_on),
        bcubed_off=bcubed_prf(ids, pred_off, true_off),
        bcubed_on=bcubed_prf(ids_on, pred_on, true_on),
        errors_on=error_breakdown(records, on, truth),
        truth_coverage=round(coverage, 4),
        n_true_people=n_true,
        n_true_recurring=n_recurring,
    )
