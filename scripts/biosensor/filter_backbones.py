#!/usr/bin/env python
"""
Cheap, GPU-free geometry filter for RFdiffusion nanobody/antibody backbones.

Runs BETWEEN RFdiffusion and ProteinMPNN/RF2, so broken or undocked backbones
are thrown out before the expensive RF2 step (ProteinMPNN and RF2 never repair
the backbone, so there is no point predicting a doomed one).

Parses the PDB directly (no heavy deps) and measures two metrics, both on the
nanobody HEAVY chain only (chain 'H') so the target's natural gaps -- EbpC/9LLW
is missing res 49-59, 2Z1P has several -- are NEVER counted as a defect:

  1. Ca-Ca chain break: max distance between CONSECUTIVE Ca atoms in chain H.
       Real backbones sit at ~3.8 A; above --break-cutoff -> physically broken.
  2. CDR-to-target contact: min distance from any H1/H2/H3 Ca to any target
       (chain 'T') Ca. Above --contact-cutoff -> undocked. Set <=0 to disable.

Writes a quiver (.qv) of passing designs and a CSV of every design's metrics.
"""
import argparse
import os
import sys

import numpy as np


def parse_design(pdb_lines):
    """Return (chains[L], ca_xyz[L,3], cdr_idx0) from one design's PDB lines.

    cdr_idx0 = 0-based absolute indices of H1/H2/H3 residues (from REMARKs).
    Pure text parsing -- independent of any rfantibody internals.
    """
    chains, xyz = [], []
    for l in pdb_lines:
        if l.startswith("ATOM") and l[12:16].strip() == "CA":
            chains.append(l[21])
            xyz.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
    chains = np.array(chains)
    xyz = np.array(xyz, dtype=float) if xyz else np.zeros((0, 3))

    cdr = []
    for l in pdb_lines:
        if "PDBinfo-LABEL" in l:
            p = l.split()
            try:
                resi, loop = int(p[-2]), p[-1]
            except (ValueError, IndexError):
                continue
            if loop in ("H1", "H2", "H3"):
                cdr.append(resi - 1)               # REMARKs are 1-indexed absolute
    cdr = [i for i in cdr if 0 <= i < len(xyz)]
    return chains, xyz, cdr


def compute_metrics(chains, xyz, cdr, break_cutoff):
    """(max_ca_break, n_breaks, cdr_target_mindist) for one design."""
    if len(xyz) == 0:
        return float("nan"), -1, float("nan")

    # (1) chain breaks within the heavy chain only, between consecutive residues
    hidx = np.where(chains == "H")[0]
    if len(hidx) >= 2:
        consecutive = (hidx[1:] - hidx[:-1]) == 1
        d = np.linalg.norm(xyz[hidx[1:]] - xyz[hidx[:-1]], axis=1)[consecutive]
        d = d[~np.isnan(d)]
        max_break = float(d.max()) if len(d) else float("nan")
        n_breaks = int((d > break_cutoff).sum())
    else:
        max_break, n_breaks = float("nan"), 0

    # (2) CDR (H1/H2/H3) to target (T) minimum Ca distance
    tidx = np.where(chains == "T")[0]
    if cdr and len(tidx):
        dd = np.linalg.norm(xyz[cdr][:, None, :] - xyz[tidx][None, :, :], axis=-1)
        cdr_contact = float(np.nanmin(dd))
    else:
        cdr_contact = float("nan")

    return max_break, n_breaks, cdr_contact


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="RFdiffusion output quiver (.qv)")
    ap.add_argument("--output", required=True, help="quiver (.qv) for PASSING designs")
    ap.add_argument("--report", default=None, help="optional CSV of per-design metrics")
    ap.add_argument("--rejected", default=None, help="optional quiver of FAILING designs")
    ap.add_argument("--break-cutoff", type=float, default=4.5,
                    help="max consecutive Ca-Ca distance allowed in chain H, A [4.5]")
    ap.add_argument("--contact-cutoff", type=float, default=10.0,
                    help="max CDR-to-target min Ca distance, A; <=0 disables [10.0]")
    ap.add_argument("--overwrite", action="store_true",
                    help="overwrite output/rejected quivers if they already exist")
    args = ap.parse_args()

    from rfantibody.util.quiver import Quiver  # lazy: keeps parsing testable without the env

    for f in (args.output, args.rejected):
        if f and os.path.exists(f):
            if args.overwrite:
                os.remove(f)
            else:
                sys.exit(f"ERROR: {f} already exists (pass --overwrite to replace).")

    qin = Quiver(args.input, "r")
    qout = Quiver(args.output, "w")
    qrej = Quiver(args.rejected, "w") if args.rejected else None
    use_contact = args.contact_cutoff > 0

    tags = qin.get_tags()
    if not tags:
        sys.exit(f"ERROR: no designs found in {args.input}")

    rows = []
    n_pass = n_broken = n_undocked = 0
    for tag in tags:
        lines = qin.get_pdblines(tag)
        try:
            chains, xyz, cdr = parse_design(lines)
            mb, nb, cc = compute_metrics(chains, xyz, cdr, args.break_cutoff)
        except Exception as e:        # never let one bad design kill the run
            print(f"  ! {tag}: {type(e).__name__}: {e} -> rejected")
            mb, nb, cc = float("nan"), -1, float("nan")

        broken = (mb != mb) or (mb > args.break_cutoff)
        undocked = use_contact and ((cc != cc) or cc > args.contact_cutoff)
        passed = (not broken) and (not undocked)

        score = (f"max_break={mb:.2f} n_break={nb} "
                 f"cdr_contact={cc:.2f} pass={int(passed)}")
        if passed:
            qout.add_pdb(lines, tag, score_str=score)
            n_pass += 1
        else:
            n_broken += int(broken)
            n_undocked += int(undocked and not broken)
            if qrej:
                qrej.add_pdb(lines, tag, score_str=score)
        rows.append((tag, mb, nb, cc, int(broken), int(undocked), int(passed)))

    if args.report:
        with open(args.report, "w") as f:
            f.write("tag,max_break,n_break,cdr_contact,broken,undocked,pass\n")
            for t, mb, nb, cc, b, u, p in rows:
                f.write(f"{t},{mb:.3f},{nb},{cc:.3f},{b},{u},{p}\n")

    total = len(tags)
    print(f"\nFiltered {total} designs:")
    print(f"  passed              : {n_pass}")
    print(f"  rejected (broken)   : {n_broken}   (Ca-Ca > {args.break_cutoff} A in chain H)")
    if use_contact:
        print(f"  rejected (undocked) : {n_undocked}   (CDR-target > {args.contact_cutoff} A)")
    print(f"  -> passing quiver : {args.output}")
    if n_pass == 0:
        print("  WARNING: nothing passed -- loosen --break-cutoff/--contact-cutoff "
              "or re-check the hotspots and inputs.")


if __name__ == "__main__":
    main()
