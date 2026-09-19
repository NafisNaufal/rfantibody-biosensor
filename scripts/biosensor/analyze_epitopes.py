#!/usr/bin/env python
"""
Compare epitopes and build an order-ready panel from their 5_selection.csv files.

Consolidates the analyses used for the Ace epitope comparison (spot1 vs D229 vs
S295) so they are reproducible rather than ad-hoc.

Subcommands
-----------
compare   per-epitope funnel + diversity, then survivors from ALL epitopes
          pooled and re-scored under one joint normalisation. Necessary because
          `composite` in each CSV is normalised within its own survivor set and
          is therefore NOT comparable across files.

panel     pick one design per distinct RFdiffusion backbone (best-ranked first)
          and verify diversity. Preferred over top-N-by-rank, which can return
          several sibling MPNN sequences on one backbone -- the same binding
          mode ordered twice. Also preferred over the built-in CDR clustering,
          which compares CDRs only (32 aa) at 90%, so designs 96% identical
          over the full 127 aa can land in different clusters.

outliers  scan for non-physical PRODIGY dG. The dg-cutoff is a `<` test, so an
          artifact at -55 kcal/mol PASSES and, being the minimum, normalises to
          0.0 (best) while compressing every other design's dG term.

numbering map a tool's sequential residue index (counting only resolved
          residues) onto PDB author numbering. Surf2Spot reports sequential
          indices; 2Z1P chain A starts at 31 with four gaps, so its numbers run
          43 below the PDB's. Passing them literally targets the wrong site.

Identity note: the framework is invariant (only H1/H2/H3 are designed), so
full-sequence identity has a floor of framework_len/total_len -- ~74.8% for a
127 aa VHH with 32 designed positions. CDR-only identity is the honest metric.

Pure stdlib.
"""
import argparse
import csv
import itertools
import re
import statistics as st
import sys

WEIGHTS = {
    "prodigy_dg":                   0.40,
    "interaction_pae":              0.25,
    "framework_aligned_H3_rmsd":    0.20,
    "target_aligned_cdr_rmsd":      0.10,
    "target_aligned_antibody_rmsd": 0.05,
}
BACKBONE_RE = re.compile(r"^(?P<namespace>.*__)?samples_design_(?P<index>\d+)_")


def fnum(x):
    try:
        v = float(x)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def identity(a, b):
    """Positional, ungapped percent identity. Unequal lengths -> 0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x == y for x, y in zip(a, b)) / len(a) * 100


def backbone_id(tag):
    """Return the RFdiffusion backbone identity encoded in a design tag.

    A one-shot batch uses tags such as ``samples_design_48_dldesign_0``.
    Continuous batches are namespaced by ``aggregate_batches.py`` and look
    like ``000025_20260909_083442__samples_design_48_dldesign_0``.  The local
    RFdiffusion index restarts at zero in every batch, so the namespace is part
    of the backbone identity and must be retained.
    """
    m = BACKBONE_RE.match(tag)
    if not m:
        return tag
    namespace = m.group("namespace") or ""
    return f"{namespace}samples_design_{m.group('index')}"


def load(spec):
    """'label=path/to/5_selection.csv' -> (label, survivor rows sorted by rank)."""
    label, _, path = spec.partition("=")
    if not path:
        sys.exit(f"expected LABEL=PATH, got {spec!r}")
    rows = [r for r in csv.DictReader(open(path)) if r.get("pass_all") == "1"]
    rows.sort(key=lambda r: float(r["rank"]) if r.get("rank") else 1e9)
    for r in rows:
        r["_ep"] = label
        r["_bb"] = backbone_id(r["tag"])
    return label, rows


def joint_score(rows):
    """Min-max normalise across the GIVEN rows, then weighted sum. Lower = better."""
    norms = {}
    for k in WEIGHTS:
        vals = [fnum(r.get(k)) for r in rows]
        ok = [v for v in vals if v is not None]
        if not ok:
            continue
        lo, hi = min(ok), max(ok)
        span = (hi - lo) or 1.0
        norms[k] = [((v if v is not None else hi) - lo) / span for v in vals]
    wsum = sum(WEIGHTS[k] for k in norms) or 1.0
    return [sum(WEIGHTS[k] * norms[k][i] for k in norms) / wsum
            for i in range(len(rows))]


def one_per_backbone(rows):
    seen, out = set(), []
    for r in rows:                      # already best-first
        if r["_bb"] not in seen:
            seen.add(r["_bb"])
            out.append(r)
    return out


def diversity(rows, key="cdr_seq"):
    seqs = [r[key] for r in rows if r.get(key)]
    if len(seqs) < 2:
        return None
    p = [identity(a, b) for a, b in itertools.combinations(seqs, 2)]
    return max(p), sum(p) / len(p), sum(1 for v in p if v >= 90), len(set(seqs))


def cmd_compare(args):
    sets = dict(load(s) for s in args.csv)

    print("=== per-epitope survivors and diversity (CDR identity) ===")
    print(f"{'epitope':10} {'surv':>5} {'backbones':>10} {'uniqCDR':>8} {'maxID%':>7} {'meanID%':>8} {'>=90%':>6}")
    for t, rows in sets.items():
        d = diversity(rows)
        if d:
            mx, mn, dup, uniq = d
            print(f"{t:10} {len(rows):>5} {len(set(r['_bb'] for r in rows)):>10} "
                  f"{uniq:>8} {mx:>7.1f} {mn:>8.1f} {dup:>6}")
        else:
            print(f"{t:10} {len(rows):>5} {len(set(r['_bb'] for r in rows)):>10} "
                  f"{'-':>8} {'-':>7} {'-':>8} {'-':>6}")

    for label, subset in (("ALL survivors", {t: r for t, r in sets.items()}),
                          ("ONE PER BACKBONE", {t: one_per_backbone(r) for t, r in sets.items()})):
        pool = [r for t in subset for r in subset[t]]
        if not pool:
            continue
        for r, s in zip(pool, joint_score(pool)):
            r["_j"] = s
        pool.sort(key=lambda r: r["_j"])
        print(f"\n=== {label}: jointly normalised composite (lower = better) ===")
        print(f"{'epitope':10} {'n':>4} {'best':>7} {'median':>8} {'worst':>7}")
        for t in subset:
            g = [r["_j"] for r in subset[t]]
            if g:
                print(f"{t:10} {len(g):>4} {min(g):>7.3f} {st.median(g):>8.3f} {max(g):>7.3f}")
        top = pool[:args.top]
        from collections import Counter
        print(f"  top {len(top)} composition: {dict(Counter(r['_ep'] for r in top))}")
        for i, r in enumerate(top, 1):
            print(f"  {i:>2} {r['_ep']:8} bb{r['_bb']:<6} joint={r['_j']:.3f} "
                  f"dG={fnum(r['prodigy_dg']):>6.1f} pAE={fnum(r['interaction_pae']):>5.2f}")


def cmd_panel(args):
    _, rows = load(args.csv)
    if not rows:
        sys.exit("no survivors in that CSV")
    panel = one_per_backbone(rows)[:args.n]
    print(f"survivors {len(rows)} on {len(set(r['_bb'] for r in rows))} backbones "
          f"-> panel of {len(panel)}")
    print(f"{'slot':>4} {'rank':>5} {'backbone':>9} {'dG':>7} {'pAE':>6} {'lDDT':>6} "
          f"{'dock':>6} {'cdr':>6} {'H3':>6}  tag")
    for i, r in enumerate(panel, 1):
        print(f"{i:>4} {int(float(r['rank'])):>5} {r['_bb']:>9} "
              f"{fnum(r['prodigy_dg']):>7.1f} {fnum(r['interaction_pae']):>6.2f} "
              f"{fnum(r['pred_lddt']):>6.3f} {fnum(r['target_aligned_antibody_rmsd']):>6.2f} "
              f"{fnum(r['target_aligned_cdr_rmsd']):>6.2f} "
              f"{fnum(r['framework_aligned_H3_rmsd']):>6.2f}  {r['tag']}")

    # membership by tag, not dict equality
    chosen = {r["tag"] for r in panel}
    taken = {r["_bb"] for r in panel}
    skipped = [r for r in rows if r["tag"] not in chosen]
    if skipped:
        print("\n  skipped:")
        for r in skipped:
            why = (f"backbone {r['_bb']} already taken at a better rank" if r["_bb"] in taken
                   else f"backbone {r['_bb']} new, but panel already full at {args.n}")
            print(f"    rank {int(float(r['rank'])):>3}  {why}")

    d = diversity(panel)
    if d:
        mx, mn, dup, _ = d
        print(f"\n  panel CDR identity: max {mx:.1f}%  mean {mn:.1f}%  pairs >=90%: {dup}")

    if args.tags_out:
        with open(args.tags_out, "w") as f:
            for r in panel:
                f.write(r["tag"] + "\n")
        print(f"  tags -> {args.tags_out}  (feed to export_survivors.py)")


def cmd_outliers(args):
    for spec in args.csv:
        t, _ = spec.partition("=")[0], None
        rows = list(csv.DictReader(open(spec.partition("=")[2])))
        dg = [(fnum(r["prodigy_dg"]), r) for r in rows if fnum(r.get("prodigy_dg")) is not None]
        if not dg:
            print(f"=== {t} === no dG computed")
            continue
        vals = sorted(v for v, _ in dg)
        sus = [(v, r) for v, r in dg if v < args.floor or v > 0]
        print(f"=== {t} ===")
        print(f"  dG computed: {len(dg)}   range {vals[0]:.1f} .. {vals[-1]:.1f}   "
              f"median {st.median(vals):.1f}")
        print(f"  outside [{args.floor}, 0]: {len(sus)}")
        for v, r in sorted(sus)[:10]:
            print(f"      dG={v:>7.1f}  pAE={r['interaction_pae']:>6} "
                  f"dock={r['target_aligned_antibody_rmsd']:>6}  pass_all={r['pass_all']}  {r['tag']}")


def cmd_numbering(args):
    T2O = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLU": "E",
           "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
           "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
           "TYR": "Y", "VAL": "V"}
    seen, order = {}, []
    for l in open(args.pdb):
        if l.startswith("ATOM") and l[21] == args.chain:
            r = int(l[22:26])
            if r not in seen:
                seen[r] = l[17:20].strip()
                order.append(r)
    gaps = [(a, b) for a, b in zip(order, order[1:]) if b - a > 1]
    print(f"chain {args.chain}: {order[0]}-{order[-1]}, {len(order)} resolved, gaps {gaps}")
    print(f"\n{'seq#':>6} {'->PDB':>7} {'aa':>5}   (pass the PDB column to --hotspots)")
    pdbs = []
    for n in args.index:
        if not 1 <= n <= len(order):
            print(f"{n:>6} {'OUT OF RANGE':>7}")
            continue
        p = order[n - 1]
        aa = seen[p]
        pdbs.append(f"{args.chain}{p}")
        print(f"{n:>6} {args.chain + str(p):>7} {aa + ' (' + T2O.get(aa, '?') + ')':>5}")
    if pdbs:
        print(f"\nhotspot string: {','.join(pdbs)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="pool epitopes under one normalisation")
    c.add_argument("csv", nargs="+", metavar="LABEL=5_selection.csv")
    c.add_argument("--top", type=int, default=10)
    c.set_defaults(fn=cmd_compare)

    p = sub.add_parser("panel", help="one design per backbone")
    p.add_argument("csv", metavar="LABEL=5_selection.csv")
    p.add_argument("-n", type=int, default=10)
    p.add_argument("--tags-out", default=None)
    p.set_defaults(fn=cmd_panel)

    o = sub.add_parser("outliers", help="scan for non-physical dG")
    o.add_argument("csv", nargs="+", metavar="LABEL=5_selection.csv")
    o.add_argument("--floor", type=float, default=-25.0,
                   help="dG below this is treated as non-physical [-25]")
    o.set_defaults(fn=cmd_outliers)

    n = sub.add_parser("numbering", help="sequential index -> PDB author numbering")
    n.add_argument("--pdb", required=True)
    n.add_argument("--chain", default="A")
    n.add_argument("index", nargs="+", type=int)
    n.set_defaults(fn=cmd_numbering)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
