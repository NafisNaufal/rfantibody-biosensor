# RFantibody biosensor add-on (Ace · EbpC · Esp)

De novo nanobody design campaign against three *Enterococcus faecalis* surface
proteins (Ace, EbpC, Esp), for an *E. coli* whole-cell biosensor. This is a
**drop-in add-on** for [RFantibody](https://github.com/RosettaCommons/RFantibody)
— it adds a `scripts/biosensor/` pipeline + the prepared target structures, and
does **not** modify any RFantibody code.

## Setup

Needs [`uv`](https://docs.astral.sh/uv/) and an NVIDIA GPU. Two cases:

### A) From scratch (no RFantibody yet)

```bash
# 1. RFantibody itself
git clone https://github.com/RosettaCommons/RFantibody.git
cd RFantibody
uv sync                              # build the env (Python 3.10, torch, dgl, ...)
bash include/download_weights.sh     # model weights (several GB)

# 2. this add-on, dropped on top
git clone https://github.com/NafisNaufal/rfantibody-biosensor.git /tmp/biosensor
bash /tmp/biosensor/install.sh "$PWD"
```

### B) Into an existing RFantibody clone

```bash
git clone https://github.com/NafisNaufal/rfantibody-biosensor.git
bash rfantibody-biosensor/install.sh /path/to/RFantibody
```

`install.sh` copies `scripts/biosensor/` and the four input PDBs into the
RFantibody clone (it doesn't touch any RFantibody code).

## Run

```bash
cd /path/to/RFantibody
uv run rfdiffusion --help                  # sanity check the env
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
