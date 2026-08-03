#!/usr/bin/env python
"""
Remove dead continuous-campaign batch directories.

When the pipeline fails fast and repeatedly (GPU OOM at step 1 is the usual
cause), the loop runners keep minting fresh timestamped batch directories --
thousands of empty shells that hold no recoverable work.

A batch is classified DEAD only when ALL of these are true:
  * run.log has no terminal marker ("DONE (<name>)" or the zero-survivor
    early exit) -- i.e. it never legitimately finished;
  * every stage output (1_backbones / 2_filtered / 3_mpnn / 4_rf2 .qv) is
    missing or zero-length;
  * no per-chunk .done marker exists (so no banked GPU work to resume);
  * it has not been touched recently (guards against deleting a batch that
    is running right now).

Anything failing those tests is KEPT. Dry-run by default -- nothing is
deleted unless --delete is passed.

Only ever matches "<Target>_<spot>_batch_*" directories. The accumulated
"<Target>_<spot>_master/" pools are never candidates.
"""
import argparse
import glob
import os
import shutil
import sys
import time


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def has_terminal_marker(batch_dir, name):
    log = os.path.join(batch_dir, "run.log")
    if not os.path.isfile(log):
        return False
    done = f"DONE ({name})"
    zero = f"WARNING: 0 backbones passed for {name}"
    try:
        with open(log, errors="ignore") as f:
            for line in f:
                if line.startswith(done) or line.startswith(zero):
                    return True
    except OSError:
        return True  # unreadable -> treat as keep, never delete on uncertainty
    return False


def has_banked_work(batch_dir):
    """Any non-empty stage output, or any completed chunk, means keep."""
    for stage in ("1_backbones.qv", "2_filtered.qv", "3_mpnn.qv", "4_rf2.qv"):
        p = os.path.join(batch_dir, stage)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return True
    chunks = os.path.join(batch_dir, "chunks")
    if os.path.isdir(chunks):
        for entry in os.listdir(chunks):
            if entry.endswith(".done"):
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--designs-dir", default="designs")
    ap.add_argument("--target", default="*", help="e.g. Ace [all]")
    ap.add_argument("--spot", default="*", help="e.g. spot1 [all]")
    ap.add_argument("--min-age-minutes", type=int, default=30,
                    help="never touch a batch modified within this window, so a "
                         "currently-running batch is safe [30]")
    ap.add_argument("--delete", action="store_true",
                    help="actually delete (default is a dry run that changes nothing)")
    ap.add_argument("--list-out", default=None,
                    help="write the dead-batch names to this file for review")
    args = ap.parse_args()

    pattern = os.path.join(args.designs_dir, f"{args.target}_{args.spot}_batch_*")
    batches = sorted(d for d in glob.glob(pattern) if os.path.isdir(d))
    if not batches:
        print(f"No batch directories matched {pattern}")
        return

    cutoff = time.time() - args.min_age_minutes * 60
    dead, kept_terminal, kept_data, kept_recent = [], 0, 0, 0

    for d in batches:
        name = os.path.basename(d)
        if os.path.getmtime(d) > cutoff:
            kept_recent += 1
            continue
        if has_terminal_marker(d, name):
            kept_terminal += 1
            continue
        if has_banked_work(d):
            kept_data += 1
            continue
        dead.append(d)

    freed = sum(dir_size(d) for d in dead)
    print(f"Scanned {len(batches)} batch directories under {args.designs_dir}/\n")
    print(f"  KEEP  finished normally      : {kept_terminal}")
    print(f"  KEEP  hold recoverable work  : {kept_data}")
    print(f"  KEEP  modified <{args.min_age_minutes}min ago     : {kept_recent}"
          f"   (possibly running now)")
    print(f"  DEAD  no work, no completion : {len(dead)}"
          f"   ({freed / 1e9:.2f} GB)")

    if args.list_out and dead:
        with open(args.list_out, "w") as f:
            for d in dead:
                f.write(os.path.basename(d) + "\n")
        print(f"\n  dead-batch names written to {args.list_out}")

    if not dead:
        print("\nNothing to clean up.")
        return

    if not args.delete:
        print("\nDRY RUN -- nothing deleted. Examples of what would go:")
        for d in dead[:5]:
            print(f"    {d}")
        if len(dead) > 5:
            print(f"    ... and {len(dead) - 5} more")
        print("\nRe-run with --delete to remove them.")
        return

    removed = 0
    for d in dead:
        try:
            shutil.rmtree(d)
            removed += 1
        except OSError as e:
            print(f"  ! could not remove {d}: {e}", file=sys.stderr)
    print(f"\nDeleted {removed} dead batch directories, freed ~{freed / 1e9:.2f} GB.")


if __name__ == "__main__":
    main()
