#!/usr/bin/env python
"""
Export every design that passed all filters from a run or an accumulated pool.

Produces a single self-describing folder:
    rank01_<design>.pdb ...   full H+T complexes, straight from the quiver
    metrics.csv               rank, dG, pAE, lDDT, all three RMSDs, CDR seq
    sequences.txt             FASTA of the nanobody (chain H), for codon opt

Unlike designs/<run>/winners/, this is NOT capped at --top, so designs that
passed every filter but fell outside the top-N are included -- they are
otherwise visible only as rows in 5_selection.csv.

Works on a one-shot run directory (4_rf2.qv) or a continuous-campaign pool
(all_rf2.qv). Pure stdlib: no GPU env, no rfantibody import.

    python scripts/biosensor/export_survivors.py --dir designs/Ace_spot1_master
"""
import argparse
import csv
import os
import re
import sys

THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLU": "E",
    "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


def base_name(tag):
    if tag.endswith("_best"):
        return tag[:-5]
    return re.sub(r"_cycle_\d+$", "", tag)


def chain_sequence(lines, chain="H"):
    return "".join(
        THREE2ONE.get(l[17:20].strip(), "X") for l in lines
        if l.startswith("ATOM") and l[12:16].strip() == "CA" and l[21] == chain
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True,
                    help="run or pool dir holding 5_selection.csv + the quiver")
    ap.add_argument("--out", default=None, help="output dir [<dir>/survivors]")
    ap.add_argument("--quiver", default=None,
                    help="quiver path [auto: all_rf2.qv, else 4_rf2.qv]")
    ap.add_argument("--top", type=int, default=0,
                    help="keep only the best N by rank [0 = every survivor]")
    ap.add_argument("--reps-only", action="store_true",
                    help="cluster representatives only (drops near-duplicate CDRs)")
    ap.add_argument("--chain", default="H", help="nanobody chain for sequences [H]")
    args = ap.parse_args()

    csv_path = os.path.join(args.dir, "5_selection.csv")
    if not os.path.isfile(csv_path):
        sys.exit(f"ERROR: {csv_path} not found -- has selection been run?")

    quiver = args.quiver
    if quiver is None:
        for cand in ("all_rf2.qv", "4_rf2.qv"):
            p = os.path.join(args.dir, cand)
            if os.path.isfile(p):
                quiver = p
                break
    if not quiver or not os.path.isfile(quiver):
        sys.exit(f"ERROR: no quiver found in {args.dir} (looked for all_rf2.qv, 4_rf2.qv)")

    rows = [r for r in csv.DictReader(open(csv_path)) if r.get("pass_all") == "1"]
    if args.reps_only:
        rows = [r for r in rows if r.get("cluster_rep") == "1"]
    rows.sort(key=lambda r: float(r["rank"]) if r.get("rank") else 1e9)
    if args.top:
        rows = rows[:args.top]
    if not rows:
        print(f"No designs passed all filters in {csv_path}.")
        return

    want = {r["tag"]: r for r in rows}
    out_dir = args.out or os.path.join(args.dir, "survivors")
    os.makedirs(out_dir, exist_ok=True)

    # stream the quiver once, writing out only the blocks we want
    seqs, found = [], set()
    cur, buf = None, []

    def flush():
        if cur in want and buf:
            r = want[cur]
            rank = int(float(r["rank"])) if r.get("rank") else 0
            stem = f"rank{rank:02d}_{base_name(cur)}"
            with open(os.path.join(out_dir, stem + ".pdb"), "w") as f:
                f.writelines(buf)
            seqs.append((rank, stem, chain_sequence(buf, args.chain)))
            found.add(cur)

    with open(quiver) as f:
        for line in f:
            if line.startswith("QV_TAG "):
                flush()
                cur, buf = line.split()[1], []
            elif line.startswith("QV_SCORE "):
                continue
            elif cur is not None:
                buf.append(line)
    flush()

    cols = ["rank", "tag", "cluster", "cluster_rep", "composite", "prodigy_dg",
            "interaction_pae", "pred_lddt", "target_aligned_antibody_rmsd",
            "target_aligned_cdr_rmsd", "framework_aligned_H3_rmsd", "cdr_seq"]
    with open(os.path.join(out_dir, "metrics.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])

    seqs.sort()
    with open(os.path.join(out_dir, "sequences.txt"), "w") as f:
        for _rank, stem, seq in seqs:
            f.write(f">{stem}\n{seq}\n")

    print(f"survivors in {os.path.basename(csv_path)} : {len(rows)}")
    print(f"PDBs written                    : {len(found)}")
    missing = sorted(set(want) - found)
    if missing:
        print(f"  WARNING: {len(missing)} selected design(s) absent from "
              f"{os.path.basename(quiver)} -- CSV and pool are out of sync. "
              f"Re-run aggregation/selection. First few: {missing[:3]}")
    print(f"  -> {out_dir}/  (metrics.csv, sequences.txt, {len(found)} PDBs)")


if __name__ == "__main__":
    main()
