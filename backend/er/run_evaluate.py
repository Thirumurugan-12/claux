"""CLI: print the entity-resolution scorecard.

    python -m er.run_evaluate

Acceptance (P8): one command prints the full report — pairwise + B-cubed P/R/F1, the
error breakdown, and the collective-resolution lift (propagation off vs on). The lift
is the number that goes on the slide, so it's printed last and loud.
"""

from __future__ import annotations

import sys
import time

from er.evaluate import Evaluation, evaluate, load_ground_truth
from er.records import connect, district_adjacency, load_party_records
from er.resolve import ResolveConfig, prepare


def _row(label: str, prf) -> str:
    return f"  {label:<26} P={prf.precision:.3f}  R={prf.recall:.3f}  F1={prf.f1:.3f}"


def _delta(off, on) -> str:
    d = on.f1 - off.f1
    return f"{d:+.3f}"


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    truth = load_ground_truth("accused")
    with connect() as conn:
        records = load_party_records(conn, ("accused",))
        adjacency = district_adjacency(conn)

    cfg = ResolveConfig()
    prep = prepare(records, cfg, adjacency)
    ev: Evaluation = evaluate(prep, truth, cfg)

    print("=" * 66)
    print("  ENTITY RESOLUTION SCORECARD  (accused, vs hidden ground truth)")
    print("=" * 66)
    print(f"  records evaluated        : {len(records):,}")
    print(f"  ground-truth coverage    : {ev.truth_coverage:.1%} of loaded records")
    print(f"  true distinct people     : {ev.n_true_people:,}  "
          f"(recurring >1 FIR: {ev.n_true_recurring:,})")
    print(f"  predicted clusters       : {len(ev.on.clusters):,}  "
          f"(multi-member: {ev.on.stats['multi_member_clusters']:,})")
    print()
    print("  PAIRWISE  (same-person pairs)")
    print(_row("propagation OFF", ev.pairwise_off))
    print(_row("propagation ON", ev.pairwise_on))
    print()
    print("  B-CUBED  (per-record cluster metric)")
    print(_row("propagation OFF", ev.bcubed_off))
    print(_row("propagation ON", ev.bcubed_on))
    print()
    print("  WHERE WE LOSE RECALL  (corruption present in missed true pairs)")
    errs = ev.errors_on
    total = errs["total_missed_pairs"] or 1
    for k in ("missing_patronymic", "patronymic_drift", "age_drift_gt2",
              "heavy_name_drift", "cross_district"):
        print(f"    {k:<20} {errs[k]:>7,}  ({errs[k] / total:.0%} of missed pairs)")
    print(f"    {'total missed pairs':<20} {errs['total_missed_pairs']:>7,}")
    print()
    print("=" * 66)
    print("  >>> COLLECTIVE RESOLUTION LIFT (the slide number) <<<")
    print(f"      pairwise F1 : {ev.pairwise_off.f1:.3f}  ->  {ev.pairwise_on.f1:.3f}"
          f"   ({_delta(ev.pairwise_off, ev.pairwise_on)})")
    print(f"      pairwise recall : {ev.pairwise_off.recall:.3f}  ->  {ev.pairwise_on.recall:.3f}"
          f"   ({ev.pairwise_on.recall - ev.pairwise_off.recall:+.3f})")
    print(f"      B-cubed F1  : {ev.bcubed_off.f1:.3f}  ->  {ev.bcubed_on.f1:.3f}"
          f"   ({_delta(ev.bcubed_off, ev.bcubed_on)})")
    print(f"      extra auto-merges from the network : "
          f"+{ev.on.stats['auto_merges_final'] - ev.on.stats['auto_merges_base']:,}")
    print("=" * 66)
    print(f"  (evaluated in {time.perf_counter() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
