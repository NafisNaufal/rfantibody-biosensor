#!/usr/bin/env python
"""Merge multiple quiver (.qv) files into one, preserving all QV_TAG/QV_SCORE/PDB lines."""
import argparse
import os
import sys


def iter_blocks(path):
    """Yield raw text blocks (list of lines), one per design."""
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="quiver files to merge (in order)")
    ap.add_argument("--output", required=True, help="merged output .qv file")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if os.path.exists(args.output) and not args.overwrite:
        sys.exit(f"ERROR: {args.output} already exists (pass --overwrite to replace)")

    seen = set()
    total = 0
    with open(args.output, "w") as out:
        for path in args.inputs:
            if not os.path.exists(path):
                print(f"  WARNING: {path} not found, skipping", file=sys.stderr)
                continue
            for block in iter_blocks(path):
                tag = block[0].split()[1] if block else None
                if tag in seen:
                    print(f"  WARNING: duplicate tag {tag} skipped", file=sys.stderr)
                    continue
                seen.add(tag)
                out.writelines(block)
                total += 1

    print(f"Merged {total} designs from {len(args.inputs)} files -> {args.output}")


if __name__ == "__main__":
    main()
