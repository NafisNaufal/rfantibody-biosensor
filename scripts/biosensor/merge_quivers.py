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


def retag(line, prefix):
    """'KEYWORD tag[ rest]' -> 'KEYWORD <prefix>tag[ rest]'."""
    parts = line.rstrip("\n").split(" ", 2)
    parts[1] = prefix + parts[1]
    return " ".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="quiver files to merge (in order)")
    ap.add_argument("--output", required=True, help="merged output .qv file")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--namespace", action="store_true",
                    help="prefix each design's tag with its source filename stem. "
                         "REQUIRED when merging generator chunks: RFdiffusion restarts "
                         "numbering at samples_design_0 in every chunk, so without this "
                         "the dedup below silently discards all but the first chunk.")
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
            prefix = (os.path.splitext(os.path.basename(path))[0] + "__"
                      if args.namespace else "")
            for block in iter_blocks(path):
                if prefix:
                    block = [retag(l, prefix)
                             if l.startswith(("QV_TAG ", "QV_SCORE ")) else l
                             for l in block]
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
