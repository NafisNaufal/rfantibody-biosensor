#!/usr/bin/env python
"""
Cheap, GPU-free geometry filter for RFdiffusion nanobody/antibody backbones.

Runs BETWEEN RFdiffusion and ProteinMPNN/RF2, so broken or undocked backbones
are thrown out before the expensive RF2 step (ProteinMPNN and RF2 never repair
the backbone, so there is no point predicting a doomed one).

Two metrics, both measured on the nanobody HEAVY chain only (chain 'H') so the
target's natural gaps -- e.g. EbpC/9LLW is missing residues 49-59, 2Z1P has
several -- are NEVER mistaken for a design defect:

  1. Ca-Ca chain break:
       max distance between CONSECUTIVE Ca atoms in chain H.
       Real backbones sit at ~3.8 A; above --break-cutoff means the chain is
       physically broken -> reject.

  2. CDR-to-target contact (docking proxy):
       min distance from any H1/H2/H3 Ca to any target (chain 'T') Ca.
       Above --contact-cutoff the loops never reach the target (undocked, the
       most common RFantibody failure) -> reject.  Set --contact-cutoff <= 0
       to disable this check and keep only the break filter.

Writes a quiver (.qv) of passing designs and a CSV report of every design's
metrics.  Designed to be run with `uv run python ...` from the repo root.
"""
import argparse
import os
import sys

import numpy as np

from rfantibody.util.pose import Pose
from rfantibody.util.quiver import Quiver

CA = 1  # Ca index in the [L, 4, 3] backbone tensor (order: N, CA, C, O)


def compute_metrics(pose, break_cutoff):
    """Return (max_ca_break, n_breaks, cdr_target_mindist) for one design."""
    ca = pose.atoms[:, CA, :]          # [L, 3]
    chain = pose.chain                 # [L]

    # --- (1) chain breaks within the heavy chain only ---
    hidx = np.where(chain == "H")[0]
    if len(hidx) >= 2:
        consecutive = (hidx[1:] - hidx[:-1]) == 1      # ignore any index jumps
        d = np.linalg.norm(ca[hidx[1:]] - ca[hidx[:-1]], axis=1)[consecutive]
        d = d[~np.isnan(d)]
        max_break = float(d.max()) if len(d) else float("nan")
        n_breaks = int((d > break_cutoff).sum())
    else:
        max_break, n_breaks = float("nan"), 0

    # --- (2) CDR (H1/H2/H3) to target (T) minimum Ca distance ---
    cdr0 = [i - 1 for loop in ("H1", "H2", "H3")
            for i in pose.cdr_dict.get(loop, [])]      # cdr_dict is 1-indexed
    tidx = np.where(chain == "T")[0]
    if cdr0 and len(tidx):
        dd = np.linalg.norm(ca[cdr0][:, None, :] - ca[tidx][None, :, :], axis=-1)
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
            pose = Pose.from_pdblines(lines)
            mb, nb, cc = compute_metrics(pose, args.break_cutoff)
        except Exception as e:        # never let one bad design kill the run
            print(f"  ! {tag}: {type(e).__name__}: {e} -> rejected")
            mb, nb, cc = float("nan"), -1, float("nan")

        broken = (mb != mb) or (mb > args.break_cutoff)        # NaN or too long
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
    if args.report:
        print(f"  -> metrics CSV    : {args.report}")
    if n_pass == 0:
        print("  WARNING: nothing passed -- loosen --break-cutoff/--contact-cutoff "
              "or re-check the hotspots and inputs.")


if __name__ == "__main__":
    main()
