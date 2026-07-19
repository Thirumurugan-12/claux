"""CLI: generate synthetic KSP data, load it, and write the hidden ground truth.

    python -m ingest.synth --cases 50000

Acceptance (P2): the command loads the database and the ground-truth file lets you
compute how many distinct real people exist behind the corrupted name variants.
The ground truth is written to a file the entity-resolution pipeline must NEVER read
(it is gitignored) — that separation is what makes the F1 measurement in P8 honest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .generator import Generator

DEFAULT_GROUND_TRUTH = Path(__file__).resolve().parent / "ground_truth.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest.synth", description=__doc__)
    parser.add_argument("--cases", type=int, default=2000, help="number of FIRs to generate")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=DEFAULT_GROUND_TRUTH,
        help="where to write the hidden ground-truth registry",
    )
    parser.add_argument(
        "--no-load",
        action="store_true",
        help="generate and write ground truth but skip the database load",
    )
    args = parser.parse_args(argv)

    t0 = time.perf_counter()
    print(f"Generating {args.cases:,} cases (seed={args.seed})...", flush=True)
    gen = Generator(args.cases, seed=args.seed)
    ds = gen.build()
    gt = ds.ground_truth
    print(f"  generated in {time.perf_counter() - t0:.1f}s", flush=True)

    args.ground_truth.parent.mkdir(parents=True, exist_ok=True)
    args.ground_truth.write_text(json.dumps(gt, default=str))
    print(f"  ground truth -> {args.ground_truth}", flush=True)

    if not args.no_load:
        from .db import load  # imported lazily so --no-load needs no database

        t1 = time.perf_counter()
        counts = load(ds)
        print(f"  loaded in {time.perf_counter() - t1:.1f}s", flush=True)
        for table, n in counts.items():
            print(f"    {table:<38} {n:>9,}")

    print()
    print("Ground-truth summary (the answer key ER never sees):")
    print(f"  distinct real people      : {gt['n_distinct_people']:,}")
    print(f"  of which recur (>1 FIR)   : {gt['n_recurring_people']:,}")
    print(f"  total party appearances   : {gt['n_total_appearances']:,}")
    print(f"  co-offending gangs present: {gt['n_gangs']:,}")
    dedup = gt["n_total_appearances"] / gt["n_distinct_people"] if gt["n_distinct_people"] else 0
    print(f"  appearances per person    : {dedup:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
