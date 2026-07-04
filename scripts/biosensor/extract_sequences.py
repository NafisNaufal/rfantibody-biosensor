#!/usr/bin/env python
"""
Extract the full nanobody (chain H) protein sequence from each winner PDB
into a plain-text file, ready for codon optimization.

Reads designs/<Target>/winners/*.pdb (written by select_designs.py) and writes
designs/<Target>/<target>_top10_sequences.txt with one FASTA-style record per
winner, ordered by rank.

Pure stdlib -- no rfantibody/GPU dependency, safe to run anywhere.
"""
import argparse
import glob
import os
import re

THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLU": "E",
    "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


def chain_h_sequence(pdb_path, chain="H"):
    seq = []
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == chain:
                seq.append(THREE2ONE.get(line[17:20].strip(), "X"))
    return "".join(seq)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--winners-dir", required=True, help="designs/<Target>/winners/")
    ap.add_argument("--out", required=True, help="output .txt path")
    ap.add_argument("--chain", default="H", help="PDB chain id for the designed nanobody [H]")
    args = ap.parse_args()

    pdbs = sorted(glob.glob(os.path.join(args.winners_dir, "rank*.pdb")))
    if not pdbs:
        print(f"No winner PDBs found in {args.winners_dir}")
        return

    with open(args.out, "w") as out:
        for p in pdbs:
            name = os.path.splitext(os.path.basename(p))[0]
            m = re.match(r"(rank\d+)_(.+)", name)
            rank, tag = (m.group(1), m.group(2)) if m else (name, name)
            seq = chain_h_sequence(p, args.chain)
            out.write(f">{rank}_{tag}\n{seq}\n")

    print(f"Wrote {len(pdbs)} sequences -> {args.out}")


if __name__ == "__main__":
    main()
