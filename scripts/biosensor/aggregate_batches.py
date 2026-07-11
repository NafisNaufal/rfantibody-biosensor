#!/usr/bin/env python
"""
Fold newly-finished continuous-campaign batches into one running, ranked pool.

The loop runners (run_<target>_loop.sh) generate unlimited timestamped batches
under designs/<Target>_<spot>_batch_*/. This script:

  1. Finds batches for a given (target, hotspot-spot) not yet folded in
     (tracked in a ledger file, so re-running only processes what's new).
  2. Appends their 4_rf2.qv entries into one persistent master quiver.
  3. Re-runs select_designs.py over the WHOLE accumulated master pool, so
     diversity-clustering (and thus "winners") reflects every batch ever
     generated for this target+spot, not just one batch's own 50 designs.
  4. Uses a persistent PRODIGY tag->dG cache so step 3 only scores designs
     that are new since the last time this ran -- stays fast indefinitely.

Safe to call repeatedly: on-demand for a manual check-in, or automatically
after every batch from inside the loop runner. A no-op (fast) if nothing
new has finished since the last call.
"""
import argparse
import glob
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def iter_blocks(path):
    """Yield raw text blocks (list of lines), one per design, from a .qv file."""
    current = []
    with open(path) as f:
        for line in f:
            if line.startswith("QV_TAG ") and current:
                yield current
                current = [line]
            else:
                current.append(line)
    if current:
        yield current


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="e.g. Ace, EbpC, Esp")
    ap.add_argument("--spot", required=True, help="hotspot-set name, e.g. spot1")
    ap.add_argument("--designs-dir", default="designs")
    ap.add_argument("--pae-cutoff", type=float, default=10.0)
    ap.add_argument("--rmsd-cutoff", type=float, default=2.0)
    ap.add_argument("--dg-cutoff", type=float, default=-10.0)
    ap.add_argument("--lddt-cutoff", type=float, default=0.9)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--cluster-identity", type=float, default=0.90)
    args = ap.parse_args()

    def has_results(d):
        rf2 = os.path.join(d, "4_rf2.qv")
        return os.path.isfile(rf2) and os.path.getsize(rf2) > 0

    prefix = f"{args.target}_{args.spot}_batch_"
    batch_dirs = sorted(
        d for d in glob.glob(os.path.join(args.designs_dir, f"{prefix}*"))
        if os.path.isdir(d) and has_results(d)
    )
    if not batch_dirs:
        print(f"No completed batches yet for {args.target}/{args.spot} "
              f"(looking for {args.designs_dir}/{prefix}*/4_rf2.qv)")
        return

    master_dir = os.path.join(args.designs_dir, f"{args.target}_{args.spot}_master")
    os.makedirs(master_dir, exist_ok=True)
    master_qv = os.path.join(master_dir, "all_rf2.qv")
    ledger_path = os.path.join(master_dir, ".folded_batches.txt")
    cache_path = os.path.join(master_dir, "prodigy_cache.csv")

    folded = set()
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            folded = {line.strip() for line in f if line.strip()}

    new_dirs = [d for d in batch_dirs if os.path.basename(d) not in folded]
    if not new_dirs:
        print(f"{args.target}/{args.spot}: {len(batch_dirs)} batch(es) total, "
              f"none new since last aggregation -- re-ranking existing pool only.")
    else:
        print(f"{args.target}/{args.spot}: folding in {len(new_dirs)} new "
              f"batch(es) ({len(batch_dirs)} total so far)...")
        seen_tags = set()
        if os.path.exists(master_qv):
            for block in iter_blocks(master_qv):
                seen_tags.add(block[0].split()[1])
        with open(master_qv, "a") as out:
            for d in new_dirs:
                n = 0
                for block in iter_blocks(os.path.join(d, "4_rf2.qv")):
                    tag = block[0].split()[1]
                    if tag in seen_tags:
                        continue
                    seen_tags.add(tag)
                    out.writelines(block)
                    n += 1
                print(f"  + {os.path.basename(d)}: {n} designs")
        with open(ledger_path, "a") as f:
            for d in new_dirs:
                f.write(os.path.basename(d) + "\n")

    cmd = [
        "uv", "run", "python", os.path.join(SCRIPT_DIR, "select_designs.py"),
        "--input", master_qv, "--outdir", master_dir,
        "--pae-cutoff", str(args.pae_cutoff), "--rmsd-cutoff", str(args.rmsd_cutoff),
        "--lddt-cutoff", str(args.lddt_cutoff), "--dg-cutoff", str(args.dg_cutoff),
        "--top", str(args.top), "--cluster-identity", str(args.cluster_identity),
        "--prodigy-cache", cache_path,
    ]
    r = subprocess.run(cmd)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
