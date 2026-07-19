"""CLI: block + score the loaded party records and dump the top pairs.

    python -m er.score_pairs --top 50

Acceptance (P6): scoring the ~50k-case dataset completes well under two minutes, and
the top pairs print with a full per-signal breakdown so a link can be debugged.
This reads only ksp; it does not resolve or persist anything (that is P7).
"""

from __future__ import annotations

import argparse
import sys
import time

from er.blocking import candidate_pairs
from er.records import connect, district_adjacency, load_party_records
from er.scoring import AUTO_MERGE, REVIEW_FLOOR, score_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="er.score_pairs", description=__doc__)
    parser.add_argument("--top", type=int, default=50, help="how many top pairs to print")
    # Default to accused — the offender-resolution target and the ~50k-record set the
    # P6 acceptance refers to. Add victim/complainant with --roles for the fuller run
    # (P7a resolves them into the same namespace); it is slower on the small name pool.
    parser.add_argument(
        "--roles",
        default="accused",
        help="comma-separated roles to load (e.g. accused,victim,complainant)",
    )
    args = parser.parse_args(argv)
    roles = tuple(r.strip() for r in args.roles.split(","))

    with connect() as conn:
        t0 = time.perf_counter()
        records = load_party_records(conn, roles)
        t_load = time.perf_counter() - t0
        adjacency = district_adjacency(conn)

    t1 = time.perf_counter()
    pairs = candidate_pairs(records)
    t_block = time.perf_counter() - t1

    t2 = time.perf_counter()
    scored = score_all(records, pairs, adjacency=adjacency)
    t_score = time.perf_counter() - t2

    scored.sort(key=lambda s: s.score, reverse=True)
    auto = sum(1 for s in scored if s.score >= AUTO_MERGE)
    review = sum(1 for s in scored if REVIEW_FLOOR <= s.score < AUTO_MERGE)

    print(f"records loaded   : {len(records):,}  ({t_load:.1f}s)")
    print(f"candidate pairs  : {len(pairs):,}  (blocking {t_block:.1f}s)")
    print(f"scored (>0)      : {len(scored):,}  (scoring {t_score:.1f}s)")
    print(f"  auto-merge >= {AUTO_MERGE}: {auto:,}")
    print(f"  review {REVIEW_FLOOR}-{AUTO_MERGE} : {review:,}")
    print(f"total pipeline   : {t_load + t_block + t_score:.1f}s")
    print()
    print(f"Top {args.top} scored pairs:")
    for sp in scored[: args.top]:
        a, b = records[sp.idx_a], records[sp.idx_b]
        print(
            f"  [{sp.score:.3f} {sp.band:>10}] "
            f"{a.role[:4]}#{a.source_row_id} '{a.raw_name}'  <->  "
            f"{b.role[:4]}#{b.source_row_id} '{b.raw_name}'"
        )
        breakdown = "  ".join(f"{k}={v}" for k, v in sp.signals.items())
        print(f"        signals: {breakdown}")
        print(f"        notes  : {sp.notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
