# RFantibody biosensor add-on (Ace · EbpC · Esp)

De novo nanobody design campaign against three *Enterococcus faecalis* surface
proteins (Ace, EbpC, Esp), for an *E. coli* whole-cell biosensor. This is a
**drop-in add-on** for [RFantibody](https://github.com/RosettaCommons/RFantibody)
— it adds a `scripts/biosensor/` pipeline + the prepared target structures, and
does **not** modify any RFantibody code.

## Prerequisites

A working RFantibody clone on your machine/HPC with the env ready and weights
downloaded (i.e. `uv run rfdiffusion --help` works).

## Install (drop into your RFantibody clone)

```bash
git clone https://github.com/NafisNaufal/rfantibody-biosensor.git
bash rfantibody-biosensor/install.sh /path/to/RFantibody
```

That copies `scripts/biosensor/` and the four input PDBs into your existing
RFantibody clone — reusing its environment and weights (nothing to re-download).

Then run the campaign:

```bash
cd /path/to/RFantibody
bash scripts/biosensor/run_all.sh          # or: sbatch scripts/biosensor/submit.slurm
```

## What's inside

```
scripts/biosensor/   the 5-step pipeline + filtering/selection/scoring tools
inputs/              2Z1P.pdb (Ace) · EBPC_9LLW.pdb (EbpC) · AF_Esp.pdb (Esp) · Scaffold.pdb
```

Full usage, parameters, the filtering/ranking logic, and the optional PyRosetta
ddG setup are documented in **[`scripts/biosensor/README.md`](scripts/biosensor/README.md)**.

## Pipeline at a glance

```
RFdiffusion ─► geometry filter ─► ProteinMPNN ─► RF2 ─► select + rank
 (backbones)   (drop junk, free)   (sequences)   (predict)  (filter + cluster + winners)
```

Design steps (RFdiffusion/ProteinMPNN/RF2) follow the supervisor's spec exactly;
the surrounding filtering, ranking, diversity-clustering, and robustness are the
add-ons.
