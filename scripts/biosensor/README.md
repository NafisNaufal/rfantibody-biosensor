# Nanobody biosensor campaign (Ace · EbpC · Esp)

De novo nanobodies against three *Enterococcus faecalis* surface proteins, for an
*E. coli* biosensor. One experiment per target (hotspots chosen by supervisor).

## Pipeline (per target)

```
RFdiffusion ─► geometry filter ─► ProteinMPNN ─► RF2 ─► select + rank
 (backbones)   (drop junk, free)   (sequences)   (predict)  (filter + cluster + winners)
   step 1           step 2            step 3       step 4       step 5
```

Two GPU-free money-savers bracket the expensive RF2 step: the **geometry filter**
(step 2) drops broken/undocked backbones *before* RF2, and **selection** (step 5)
filters, scores, ranks, and de-duplicates RF2's output into a short list of winners.

## Files

```
run_ace.sh / run_ebpc.sh / run_esp.sh   thin per-target wrappers (set NAME/TARGET/HOTSPOTS)
_pipeline.sh                            the shared 5-step pipeline (sourced by the wrappers)
run_all.sh                              all three, sequential, + cross-target summary
filter_backbones.py                     step 2: Cα-break + docking filter
select_designs.py                       step 5: pAE/RMSD/PRODIGY(/Rosetta) filter + rank + cluster
score_rosetta.py                        optional Rosetta interface ddG (runs in your PyRosetta env)
summarize.py                            combine all targets into designs/SUMMARY.csv
```

## The 3 experiments

| # | Target | Input file | Hotspots (spot #1) | Output dir |
|---|--------|------------|--------------------|------------|
| 1 | Ace  | `inputs/2Z1P.pdb`      | `A180,A182,A193,A195`        | `designs/Ace/`  |
| 2 | EbpC | `inputs/EBPC_9LLW.pdb` | `A61,A62,A63,A64,A65,A67`    | `designs/EbpC/` |
| 3 | Esp  | `inputs/AF_Esp.pdb`    | `A69,A71,A74`                | `designs/Esp/`  |

Shared: framework `inputs/Scaffold.pdb`, loops `H1:10,H2:6,H3:16`,
`--deterministic`. Each wrapper sets **`NUM_DESIGNS=1000`** and
**`SEQS_PER_STRUCT=4`**. For a quick pilot, set `NUM_DESIGNS=20` in a wrapper.
**Backup hotspots** (#2/#3) are in each wrapper — swap the `HOTSPOTS=` line if
spot #1 docks poorly. Any tunable (cutoffs, `CLEAN`, …) can be overridden the same way.

## How to run

```bash
# one target
bash scripts/biosensor/run_ace.sh

# all three + summary
bash scripts/biosensor/run_all.sh
```

> - **First run needs internet** (login node) so PRODIGY installs once; after that it's cached.
> - **Re-runs wipe and restart** (`CLEAN=true`). Set `CLEAN=false` in a wrapper to skip completed steps.
> - Everything is logged to `designs/<Target>/run.log` with per-step timing.

## The geometry filter (step 2)

`filter_backbones.py` scores each RFdiffusion backbone on two cheap checks,
**on the nanobody heavy chain (H) only** so the targets' natural gaps (EbpC is
missing res 49–59; 2Z1P has several) are never counted against a design:

| Metric | Meaning | Default reject |
|--------|---------|----------------|
| `max_break` | largest gap between neighbouring Cα (good ≈ 3.8 Å) | `> 4.5 Å` → broken |
| `cdr_contact` | closest any CDR loop gets to the target | `> 10 Å` → undocked |

## Selection + ranking (step 5)

`select_designs.py` reads the RF2 quiver (pAE + RMSDs are already in its scores),
applies the hard filters, scores binding energy, ranks, then **clusters**:

| Filter | Metric | Default |
|--------|--------|---------|
| confidence | `interaction_pae` | `< 10` |
| dock held | `target_aligned_antibody_rmsd` | `< 2 Å` |
| loops landed | `target_aligned_cdr_rmsd` | `< 2 Å` |
| affinity | PRODIGY `prodigy_dg` (kcal/mol) | `< -10` |
| Rosetta ddG | `rosetta_ddg` | rank only (set `--ddg-cutoff` to filter) |

**Ranking** = weighted composite (lower = better), min-max normalised per target:
PRODIGY ΔG 0.30, Rosetta ddG 0.20, pAE 0.20, **H3 RMSD 0.15**, dock RMSD 0.10,
CDR RMSD 0.05 (weights at top of `select_designs.py`; any missing metric is
dropped and the rest renormalised).

**Diversity clustering**: survivors are greedily clustered by CDR (H1+H2+H3)
sequence identity (`--cluster-identity 0.90`), so the **winners are the top-N
*distinct* designs** — you won't extract ten near-identical sequences.

PRODIGY runs isolated (`uv run --no-project --with prodigy-prot prodigy …`). No
internet / no PRODIGY? add `--skip-prodigy` to keep pAE+RMSD and rank without ΔG.

## Optional: Rosetta interface ddG (PyRosetta)

Off by default. To enable, install **PyRosetta** (free for academic/non-commercial
use — register at <https://www.pyrosetta.org>) in its **own** environment so it
can't disturb the GPU stack:

```bash
# easiest: a dedicated venv + the official installer
uv venv ~/envs/pyrosetta --python 3.10
source ~/envs/pyrosetta/bin/activate
pip install pyrosetta-installer
python -c "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"
deactivate
```

Then point the pipeline at it (once, before running) — either uncomment the line
in each wrapper, or export it:

```bash
export ROSETTA_CMD="$HOME/envs/pyrosetta/bin/python scripts/biosensor/score_rosetta.py"
```

`score_rosetta.py` minimises the H–T interface and computes the nanobody ddG using
the repo's shipped `scripts/scoring/util_minterface.xml`. It only runs on the few
designs that already cleared pAE+RMSD, so the cost is small. If `ROSETTA_CMD` is
unset, the step is simply skipped and PRODIGY carries the energy term.

## Outputs

Each target, in `designs/<Target>/`:

```
1_backbones.qv     RFdiffusion output (all 1000)
2_filtered.qv      survived the geometry filter (step 2)
3_mpnn.qv          sequences assigned
4_rf2.qv           RF2 structures + confidence scores
5_selection.csv    every design ranked: metrics, cluster, pass/fail   ← read this
winners/           top-N *distinct* designs as PDBs, rank-ordered      ← order these
filter_report.csv  step-2 geometry metrics
run.log            full log of the run
```

After `run_all.sh`, **`designs/SUMMARY.csv`** ranks the distinct winners across all
three targets together (by PRODIGY ΔG, then Rosetta ddG, then pAE).

## Notes

- Inputs are used **as-is** — waters are harmless (RFdiffusion reads only `ATOM`
  records) and chains stay `A` (hotspot letters match). RFdiffusion/MPNN/RF2 are
  left exactly as specified (the complex is preserved for downstream MD).
- The filters are stringent by design. If nothing passes, open `5_selection.csv`: it's usually pAE
  or RMSD, which points back to the hotspots, not the sequence.
