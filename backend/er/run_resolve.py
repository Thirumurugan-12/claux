"""CLI: run collective entity resolution and persist person_cluster.

    python -m er.run_resolve                 # resolve accused, persist, show a sample
    python -m er.run_resolve --no-persist     # dry run, just the stats + lift

Acceptance (P7): person_cluster is populated, and for any cluster you can ask "why are
these the same person" and get the evidence back. The run prints the collective-boost
lift (auto-merges with propagation off vs on) and, for a sample multi-member cluster,
the members with the signals and shared co-offenders that linked them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from er.records import connect, district_adjacency, load_party_records
from er.resolve import resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="er.run_resolve", description=__doc__)
    parser.add_argument("--roles", default="accused", help="comma-separated roles to resolve")
    parser.add_argument("--no-persist", action="store_true", help="don't write to the database")
    parser.add_argument("--sample", type=int, default=3, help="multi-member clusters to explain")
    args = parser.parse_args(argv)
    roles = tuple(r.strip() for r in args.roles.split(","))

    with connect() as conn:
        t0 = time.perf_counter()
        records = load_party_records(conn, roles)
        adjacency = district_adjacency(conn)
        t_load = time.perf_counter() - t0

        t1 = time.perf_counter()
        result = resolve(records, adjacency=adjacency)
        t_resolve = time.perf_counter() - t1

        s = result.stats
        print(f"loaded {s['records']:,} records ({t_load:.1f}s); resolved in {t_resolve:.1f}s")
        print(f"  candidate pairs        : {s['candidate_pairs']:,}")
        print(
            f"  clusters               : {s['clusters']:,}  "
            f"(multi-member: {s['multi_member_clusters']:,})"
        )
        print(f"  auto-merges (name only): {s['auto_merges_base']:,}")
        print(f"  auto-merges (collective): {s['auto_merges_final']:,}")
        print(f"  >>> collective lift    : +{s['collective_lift']:,} merges from the network")
        print(f"  review queue (0.60-0.85): {s['review_pairs']:,}")

        if not args.no_persist:
            from er.resolve import persist

            tp = time.perf_counter()
            persist(conn, result)
            print(f"  persisted to derived.* in {time.perf_counter() - tp:.1f}s")

    _explain_samples(result, args.sample)
    return 0


def _explain_samples(result, n: int) -> None:
    multi = [(root, m) for root, m in result.clusters.items() if len(m) > 1]

    # show clusters whose links actually used a collective boost first, they're the point
    def used_boost(members):
        return any(result.member_evidence[i].get("collective_boost", 0) > 0 for i in members)

    multi.sort(key=lambda rm: (used_boost(rm[1]), len(rm[1])), reverse=True)
    print(f"\n=== 'why are these the same person' — {min(n, len(multi))} sample clusters ===")
    for _root, members in multi[:n]:
        recs = [result.records[i] for i in members]
        print(f"\ncluster of {len(members)} — likely '{recs[0].parsed.given}':")
        for i in members:
            r = result.records[i]
            ev = result.member_evidence[i]
            print(
                f"  accused#{r.source_row_id} (FIR {r.case_master_id}) '{r.raw_name}' "
                f"conf={result.member_confidence[i]}"
            )
            if "signals" in ev:
                boost = ev.get("collective_boost", 0)
                extra = f"  +boost {boost} via {ev['shared_resolved_cooffenders']}" if boost else ""
                print(f"        {json.dumps(ev['signals'])}{extra}")


if __name__ == "__main__":
    sys.exit(main())
