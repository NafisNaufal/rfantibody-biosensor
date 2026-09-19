#!/usr/bin/env python
"""
Add a composite + rank over EVERY design in a 5_selection.csv, not just the
ones that cleared the hard filters.

select_designs.py scores survivors only, because PRODIGY is gated behind
pAE+RMSD+lDDT -- so prodigy_dg is NaN for the large majority and its 0.40
weight cannot be applied to them. This re-scores all rows using the four
RF2-derived metrics, with their weights renormalised to sum to 1.0, and writes
rank_all / composite_all alongside the originals.

IMPORTANT: composite_all ranks confidence and geometry, NOT binding. A design
high in rank_all has good RF2 metrics and no affinity evidence whatsoever.
It is also normalised over a different population than `composite`, so the two
columns are not on a comparable scale.

    python scripts/biosensor/rank_all.py --in 5_selection.csv --out all_ranked.csv
"""
import argparse
import csv
import sys

# production weights, must match select_designs.py WEIGHTS
FULL = {
    "prodigy_dg":                   0.40,
    "interaction_pae":              0.25,
    "framework_aligned_H3_rmsd":    0.20,
    "target_aligned_cdr_rmsd":      0.10,
    "target_aligned_antibody_rmsd": 0.05,
}
# dG unavailable for non-survivors -> drop it and renormalise the rest
NO_DG = {k: v for k, v in FULL.items() if k != "prodigy_dg"}
_S = sum(NO_DG.values())
NO_DG = {k: v / _S for k, v in NO_DG.items()}


def fnum(x):
    try:
        v = float(x)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, help="5_selection.csv")
    ap.add_argument("--out", dest="dst", required=True)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.src)))
    if not rows:
        sys.exit("empty input")

    # min-max normalise each metric across ALL rows (0 = best; lower is better)
    norms = {}
    for k in NO_DG:
        vals = [fnum(r.get(k)) for r in rows]
        ok = [v for v in vals if v is not None]
        if not ok:
            continue
        lo, hi = min(ok), max(ok)
        span = (hi - lo) or 1.0
        # missing value -> treated as worst, so it cannot rank well by absence
        norms[k] = [((v if v is not None else hi) - lo) / span for v in vals]

    wsum = sum(NO_DG[k] for k in norms)
    for i, r in enumerate(rows):
        r["composite_all"] = round(sum(NO_DG[k] * norms[k][i] for k in norms) / wsum, 4)

    rows.sort(key=lambda r: r["composite_all"])
    for i, r in enumerate(rows, 1):
        r["rank_all"] = i

    cols = ["rank_all", "composite_all"] + [c for c in rows[0]
                                            if c not in ("rank_all", "composite_all")]
    with open(args.dst, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    npass = sum(1 for r in rows if r.get("pass_all") == "1")
    print(f"{args.dst}: {len(rows)} designs ranked ({npass} passed all hard filters)")
    print("  rank_all weights (renormalised, dG dropped): "
          + ", ".join(f"{k}={v:.4f}" for k, v in NO_DG.items()))


if __name__ == "__main__":
    main()
