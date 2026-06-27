#!/usr/bin/env python
"""
Cross-target summary: pull the distinct winners from every target's
designs/<Target>/5_selection.csv into one ranked table.

Each target's `composite` is normalised *within* that target, so it is not
comparable across targets. We therefore rank the combined winners by the
absolute, cross-comparable metrics: PRODIGY ΔG (most negative first), then
interface pAE.

Writes designs/SUMMARY.csv and prints the overall top designs. Pure stdlib.
"""
import argparse
import csv
import glob
import os


def fnum(x, worst=float("inf")):
    """Parse a CSV cell to float; NaN/blank -> `worst` (so they sort last)."""
    try:
        v = float(x)
        return worst if v != v else v
    except (TypeError, ValueError):
        return worst


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--designs-dir", default="designs",
                    help="dir holding <Target>/5_selection.csv [designs]")
    ap.add_argument("--out", default=None, help="output CSV [<designs-dir>/SUMMARY.csv]")
    ap.add_argument("--top", type=int, default=15, help="rows to print [15]")
    args = ap.parse_args()

    out = args.out or os.path.join(args.designs_dir, "SUMMARY.csv")
    csvs = sorted(glob.glob(os.path.join(args.designs_dir, "*", "5_selection.csv")))
    if not csvs:
        print(f"No <Target>/5_selection.csv under {args.designs_dir}/ — run the pipeline first.")
        return

    winners = []
    for path in csvs:
        target = os.path.basename(os.path.dirname(path))
        with open(path) as f:
            for row in csv.DictReader(f):
                if row.get("pass_all") == "1" and row.get("cluster_rep") == "1":
                    row["target"] = target
                    winners.append(row)

    if not winners:
        print("No designs passed all filters in any target. Check each 5_selection.csv.")
        return

    winners.sort(key=lambda r: (fnum(r.get("prodigy_dg")),
                                fnum(r.get("interaction_pae"))))

    cols = ["overall_rank", "target", "tag", "prodigy_dg",
            "interaction_pae", "target_aligned_antibody_rmsd",
            "framework_aligned_H3_rmsd", "cdr_seq"]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, r in enumerate(winners, 1):
            w.writerow([i] + [r.get(c, "") for c in cols[1:]])

    print(f"\nCross-target winners: {len(winners)} distinct designs from {len(csvs)} targets")
    print(f"  -> {out}\n")
    hdr = f"  {'#':>2}  {'target':<6} {'ΔG':>6} {'pAE':>5} {'dock':>5} {'H3':>5}  design"
    print(hdr)
    for i, r in enumerate(winners[:args.top], 1):
        print(f"  {i:>2}  {r['target']:<6} {r.get('prodigy_dg',''):>6} "
              f"{r.get('interaction_pae',''):>5} {r.get('target_aligned_antibody_rmsd',''):>5} "
              f"{r.get('framework_aligned_H3_rmsd',''):>5}  {r.get('tag','')}")


if __name__ == "__main__":
    main()
