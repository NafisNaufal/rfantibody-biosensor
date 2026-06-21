#!/usr/bin/env python
"""
Post-RF2 selection + ranking for the nanobody campaign (pipeline Step 5).

Reads an RF2 output quiver (whose QV_SCORE lines already carry interaction_pae
and the RMSD metrics), applies hard filters, scores binding energy (PRODIGY),
ranks survivors with a weighted composite, then diversity-clusters them so the
winners you order are genuinely distinct.

Hard filters (a design must pass ALL):
    interaction_pae               < --pae-cutoff   (default 10)
    target_aligned_antibody_rmsd  < --rmsd-cutoff  (default 2.0)   # dock held
    target_aligned_cdr_rmsd       < --rmsd-cutoff  (default 2.0)   # loops landed
    prodigy_dg (kcal/mol)         < --dg-cutoff    (default -10)   # PRODIGY affinity

Ranking (survivors only): min-max normalise each metric (0 = best) and combine
with weights favouring binding energy, then interface confidence, then H3 loop
fidelity, then dock/CDR RMSD. Lowest composite = best. Survivors are then greedily
clustered by CDR (H1+H2+H3) sequence identity; winners = top-N cluster reps.

External scorers run in isolated envs so they can't perturb the GPU stack:
  PRODIGY:  uv run --no-project --with prodigy-prot prodigy <pdb> --selection H T
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile

# metric -> weight (all "lower is better", incl. dG since more-negative = better)
WEIGHTS = {
    "prodigy_dg":                   0.40,   # PRODIGY predicted affinity
    "interaction_pae":              0.25,   # interface confidence
    "framework_aligned_H3_rmsd":    0.20,   # H3 loop fidelity (hardest CDR)
    "target_aligned_antibody_rmsd": 0.10,   # dock reproduced
    "target_aligned_cdr_rmsd":      0.05,   # CDRs reproduced
}
THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLU": "E",
    "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


def read_quiver_scores(qv_path):
    """tag -> {metric: float} from the QV_SCORE lines (key=val|key=val)."""
    scores = {}
    with open(qv_path) as f:
        for line in f:
            if not line.startswith("QV_SCORE"):
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            tag, sstr = parts[1], parts[2].strip()
            d = {}
            for kv in sstr.split("|"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    try:
                        d[k.strip()] = float(v)
                    except ValueError:
                        pass
            scores[tag] = d
    return scores


def base_name(tag):
    if tag.endswith("_best"):
        return tag[:-5]
    return re.sub(r"_cycle_\d+$", "", tag)


def choose_best_entries(scores):
    """One entry per design: prefer the *_best tag, else lowest interaction_pae."""
    groups = {}
    for tag, m in scores.items():
        groups.setdefault(base_name(tag), []).append((tag, m))
    chosen = {}
    for base, entries in groups.items():
        best = next((e for e in entries if e[0].endswith("_best")), None)
        if best is None:
            best = min(entries, key=lambda e: e[1].get("interaction_pae", 1e9))
        chosen[base] = best
    return chosen


def _run_energy(pdb_lines, cmd, pattern, selection=None, temp=None):
    """Write a temp PDB, run an external scorer, return (value, note)."""
    with tempfile.TemporaryDirectory() as td:
        pdb = os.path.join(td, "complex.pdb")
        with open(pdb, "w") as f:
            f.writelines(pdb_lines)
        full = cmd + [pdb]
        if selection:
            full += ["--selection", selection[0], selection[1]]
        if temp is not None:
            full += ["--temperature", str(temp)]
        try:
            r = subprocess.run(full, capture_output=True, text=True, timeout=900, cwd=td)
        except Exception as e:
            return float("nan"), f"{type(e).__name__}: {e}"
        text = r.stdout + r.stderr
    m = re.search(pattern, text)
    if m:
        return float(m.group(1)), "ok"
    last = text.strip().splitlines()[-1][:160] if text.strip() else "no output"
    return float("nan"), last


def run_prodigy(pdb_lines, cmd, chains, temp):
    dg, note = _run_energy(pdb_lines, cmd,
                           r"Predicted binding affinity \(kcal\.mol-1\):\s*(-?\d+\.?\d*)",
                           selection=chains, temp=temp)
    kd = float("nan")
    return dg, kd, note



def cdr_sequence(pdb_lines):
    """Concatenated H1+H2+H3 one-letter sequence (the only designed residues)."""
    ca = [l[17:20].strip() for l in pdb_lines
          if l.startswith("ATOM") and l[12:16].strip() == "CA"]
    labels = {"H1": [], "H2": [], "H3": []}
    for l in pdb_lines:
        if "PDBinfo-LABEL" in l:
            p = l.split()
            try:
                resi, loop = int(p[-2]), p[-1]
            except (ValueError, IndexError):
                continue
            if loop in labels:
                labels[loop].append(resi)
    seq = ""
    for loop in ("H1", "H2", "H3"):
        for resi in sorted(labels[loop]):
            if 1 <= resi <= len(ca):
                seq += THREE2ONE.get(ca[resi - 1], "X")
    return seq


def identity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x == y for x, y in zip(a, b)) / len(a)


def cluster_survivors(survivors, threshold):
    """Greedy, best-first: each design joins a cluster whose rep is >=threshold
    identical (CDRs), else founds a new cluster. Adds 'cluster' and 'cluster_rep'."""
    reps = []  # (cdrseq, cluster_id)
    for r in survivors:
        cid = None
        for repseq, rid in reps:
            if identity(r["cdr_seq"], repseq) >= threshold:
                cid = rid
                break
        if cid is None:
            cid = len(reps) + 1
            reps.append((r["cdr_seq"], cid))
            r["cluster"], r["cluster_rep"] = cid, True
        else:
            r["cluster"], r["cluster_rep"] = cid, False


def minmax(vals):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.0] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="RF2 output quiver (.qv)")
    ap.add_argument("--outdir", required=True, help="output dir (CSV + winners/)")
    ap.add_argument("--pae-cutoff", type=float, default=10.0)
    ap.add_argument("--rmsd-cutoff", type=float, default=2.0)
    ap.add_argument("--dg-cutoff", type=float, default=-10.0)
    ap.add_argument("--top", type=int, default=10, help="number of cluster-rep winners to extract")
    ap.add_argument("--cluster-identity", type=float, default=0.90,
                    help="CDR identity for designs to share a cluster [0.90]")
    ap.add_argument("--prodigy-temp", type=float, default=25.0)
    ap.add_argument("--chains", default="H T", help="PRODIGY partner chains [\"H T\"]")
    ap.add_argument("--prodigy-cmd", default="uv run --no-project --with prodigy-prot prodigy",
                    help="how to invoke prodigy (isolated env)")
    ap.add_argument("--skip-prodigy", action="store_true",
                    help="skip PRODIGY: keep pAE+RMSD filters, drop dG from filter & ranking")
    args = ap.parse_args()

    from rfantibody.util.quiver import Quiver  # lazy: keeps parsing logic importable without GPU env

    os.makedirs(args.outdir, exist_ok=True)
    qin = Quiver(args.input, "r")
    scores = read_quiver_scores(args.input)
    if not scores:
        sys.exit(f"ERROR: no QV_SCORE lines in {args.input} (did RF2 write scores?)")
    designs = choose_best_entries(scores)
    chains = tuple(args.chains.split())
    prodigy_cmd = shlex.split(args.prodigy_cmd)

    rows = []
    n_pae = n_rmsd = n_final = 0
    for base, (tag, m) in sorted(designs.items()):
        pae = m.get("interaction_pae", float("nan"))
        rdock = m.get("target_aligned_antibody_rmsd", float("nan"))
        rcdr = m.get("target_aligned_cdr_rmsd", float("nan"))
        h3 = m.get("framework_aligned_H3_rmsd", float("nan"))
        pass_pae = pae < args.pae_cutoff
        pass_rmsd = (rdock < args.rmsd_cutoff) and (rcdr < args.rmsd_cutoff)
        n_pae += int(pass_pae)
        n_rmsd += int(pass_pae and pass_rmsd)

        dg = kd = float("nan")
        note = "skipped"
        cdrseq = ""
        # Only spend external scorers on designs that already cleared pAE + RMSD.
        if pass_pae and pass_rmsd:
            lines = qin.get_pdblines(tag)
            cdrseq = cdr_sequence(lines)
            if not args.skip_prodigy:
                dg, kd, note = run_prodigy(lines, prodigy_cmd, chains, args.prodigy_temp)

        pass_dg = True if args.skip_prodigy else (dg < args.dg_cutoff)
        pass_all = pass_pae and pass_rmsd and pass_dg
        n_final += int(pass_all)

        rows.append(dict(tag=tag, base=base, interaction_pae=pae,
                         target_aligned_antibody_rmsd=rdock,
                         target_aligned_cdr_rmsd=rcdr,
                         framework_aligned_H3_rmsd=h3,
                         prodigy_dg=dg, prodigy_kd=kd,
                         prodigy_note=note, cdr_seq=cdrseq,
                         pass_pae=pass_pae, pass_rmsd=pass_rmsd,
                         pass_dg=pass_dg, pass_all=pass_all,
                         cluster="", cluster_rep=False))

    # ---- composite ranking over survivors (drop metrics with no finite values) ----
    survivors = [r for r in rows if r["pass_all"]]
    finite = lambda v: v == v  # noqa: E731  (False for NaN)
    weights = {k: w for k, w in WEIGHTS.items()
               if any(finite(r.get(k, float("nan"))) for r in survivors)}
    if survivors and weights:
        norms = {}
        for key in weights:
            vals = [r[key] for r in survivors]
            worst = max((v for v in vals if finite(v)), default=0.0)
            norms[key] = minmax([v if finite(v) else worst for v in vals])
        wsum = sum(weights.values())
        for i, r in enumerate(survivors):
            r["composite"] = sum(weights[k] * norms[k][i] for k in weights) / wsum
        survivors.sort(key=lambda r: r["composite"])
        cluster_survivors(survivors, args.cluster_identity)
        for rank, r in enumerate(survivors, 1):
            r["rank"] = rank

    # ---- write ranked CSV (all designs) ----
    csv_path = os.path.join(args.outdir, "5_selection.csv")
    cols = ["rank", "tag", "cluster", "cluster_rep", "pass_all", "composite",
            "prodigy_dg", "prodigy_kd", "interaction_pae",
            "target_aligned_antibody_rmsd", "target_aligned_cdr_rmsd",
            "framework_aligned_H3_rmsd", "cdr_seq",
            "pass_pae", "pass_rmsd", "pass_dg", "prodigy_note"]
    info = {r["tag"]: r for r in survivors}
    ordered = survivors + [r for r in rows if not r["pass_all"]]
    with open(csv_path, "w") as f:
        f.write(",".join(cols) + "\n")
        for r in ordered:
            row = {**r, "rank": info.get(r["tag"], {}).get("rank", ""),
                   "composite": info.get(r["tag"], {}).get("composite", ""),
                   "cluster": info.get(r["tag"], {}).get("cluster", ""),
                   "cluster_rep": int(info.get(r["tag"], {}).get("cluster_rep", False))}
            out = []
            for c in cols:
                v = row.get(c, "")
                if isinstance(v, bool):
                    v = int(v)
                out.append(f"{v:.3f}" if isinstance(v, float) else str(v))
            f.write(",".join(out) + "\n")

    # ---- extract top-N cluster-representative winners ----
    win_dir = os.path.join(args.outdir, "winners")
    winners = [r for r in survivors if r["cluster_rep"]][:args.top]
    if winners:
        os.makedirs(win_dir, exist_ok=True)
        for r in winners:
            out = os.path.join(win_dir, f"rank{r['rank']:02d}_{r['base']}.pdb")
            with open(out, "w") as f:
                f.writelines(qin.get_pdblines(r["tag"]))

    # ---- summary ----
    total = len(rows)
    n_clusters = len({r["cluster"] for r in survivors}) if survivors else 0
    print(f"\nSelection over {total} designs:")
    print(f"  passed pAE  (<{args.pae_cutoff})       : {n_pae}")
    print(f"  + passed RMSD (<{args.rmsd_cutoff})      : {n_rmsd}")
    print(f"  + passed energy [PRODIGY]    : {n_final}" if not args.skip_prodigy
          else f"  PRODIGY skipped                : {n_final} survivors")
    print(f"  -> {n_clusters} distinct clusters; ranked CSV: {csv_path}")
    if winners:
        print(f"  -> winners: {win_dir}/ (top {len(winners)} distinct designs)")
        b = winners[0]
        print(f"  BEST: {b['base']}  pAE={b['interaction_pae']:.1f}"
              f"  dock={b['target_aligned_antibody_rmsd']:.2f}"
              f"  H3={b['framework_aligned_H3_rmsd']:.2f}"
              f"  dG={b['prodigy_dg']:.1f}")
    else:
        print("  No designs passed all filters — loosen cutoffs or inspect 5_selection.csv.")


if __name__ == "__main__":
    main()
