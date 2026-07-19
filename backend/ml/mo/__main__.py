"""Run MO fingerprinting and print the acceptance view: cluster labels, quality vs the hidden
ground truth, and 5 sample BriefFacts per cluster so you can eyeball whether the clusters are
real.

    python -m ml.mo                 # cluster, persist, print report
    python -m ml.mo --no-persist    # dry run
    python -m ml.mo --min-cluster-size 200
"""

from __future__ import annotations

import argparse

from ml.mo.fingerprint import run


def main() -> None:
    ap = argparse.ArgumentParser(description="MO fingerprinting (P15).")
    ap.add_argument("--no-persist", action="store_true")
    ap.add_argument("--min-cluster-size", type=int, default=120)
    args = ap.parse_args()

    rep = run(persist=not args.no_persist, min_cluster_size=args.min_cluster_size)

    print(f"\nMO fingerprinting — {rep.n_cases:,} cases")
    print("=" * 72)
    print(f"clusters: {rep.n_clusters}   noise: {rep.noise:,}   "
          f"({100 * rep.noise / rep.n_cases:.1f}% unclustered)")
    print(f"vs hidden MO ground truth — V-measure {rep.v_measure:.3f}  "
          f"(homogeneity {rep.homogeneity:.3f} / completeness {rep.completeness:.3f})")
    print("=" * 72)
    for c in rep.clusters:
        mix = c["cstype"]
        print(f"\n[cluster {c['cluster_id']}] {c['label']}   (n={c['size']:,})")
        print(f"    terms: {', '.join(c['top_terms'][:6])}")
        print(f"    outcomes: chargesheet {mix['A']} · false {mix['B']} · "
              f"undetected {mix['C']} · open {mix['open']}")
        for s in c["sample_texts"]:
            print(f"      · {s}")
    print()


if __name__ == "__main__":
    main()
