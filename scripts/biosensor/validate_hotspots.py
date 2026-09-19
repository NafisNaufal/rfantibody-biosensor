#!/usr/bin/env python3
"""Validate RFantibody hotspot strings against PDB author numbering.

The RFdiffusion command accepts hotspot strings that look syntactically valid
even when a residue is absent from the target or the numbering came from a
different residue frame.  This small, dependency-free preflight makes that
failure explicit before a GPU campaign starts.
"""

import argparse
import re
import sys


HOTSPOT_RE = re.compile(r"^(?P<chain>[A-Za-z0-9])(?P<number>[0-9]+)(?P<icode>[A-Za-z]?)$")


def read_residues(path):
    """Return ``(chain, author_resseq, insertion_code) -> residue name``."""
    residues = {}
    try:
        with open(path) as handle:
            for line in handle:
                if not line.startswith("ATOM") or len(line) < 27:
                    continue
                chain = line[21].strip()
                if not chain:
                    chain = "_"
                try:
                    resseq = int(line[22:26])
                except ValueError:
                    continue
                icode = line[26].strip()
                residues.setdefault((chain, resseq, icode), line[17:20].strip())
    except OSError as exc:
        raise SystemExit(f"ERROR: cannot read PDB {path}: {exc}")
    return residues


def parse_hotspots(spec):
    items = [item.strip() for item in spec.split(",")]
    if not spec or any(not item for item in items):
        raise ValueError("hotspots must be a comma-separated list such as A229,A231")

    parsed = []
    seen = set()
    for item in items:
        match = HOTSPOT_RE.fullmatch(item)
        if not match:
            raise ValueError(f"invalid hotspot '{item}' (expected CHAIN+RESSEQ, e.g. A229)")
        key = (match.group("chain"), int(match.group("number")), match.group("icode"))
        if key in seen:
            raise ValueError(f"duplicate hotspot '{item}'")
        seen.add(key)
        parsed.append((item, key))
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb", required=True, help="target PDB")
    parser.add_argument("--hotspots", required=True, help="comma-separated hotspot string")
    parser.add_argument("--expected", default=None,
                        help="optional comma-separated 3-letter residue names")
    parser.add_argument("--label", default="hotspots", help="label for the success line")
    args = parser.parse_args(argv)

    try:
        hotspots = parse_hotspots(args.hotspots)
        expected = None
        if args.expected is not None:
            expected = [item.strip().upper() for item in args.expected.split(",")]
            if len(expected) != len(hotspots):
                raise ValueError("--expected must contain one residue name per hotspot")
            if any(not re.fullmatch(r"[A-Z]{3}", item) for item in expected):
                raise ValueError("--expected values must be 3-letter residue names")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    residues = read_residues(args.pdb)
    found = []
    errors = []
    for index, (spelling, key) in enumerate(hotspots):
        name = residues.get(key)
        if name is None:
            errors.append(f"{spelling} is not a resolved ATOM residue in {args.pdb}")
            continue
        if expected is not None and name.upper() != expected[index]:
            errors.append(f"{spelling} is {name}, expected {expected[index]} in {args.pdb}")
            continue
        found.append(f"{spelling}={name}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"{args.label}: " + " ".join(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
