# RFantibody biosensor (Ace · EbpC · Esp)

De novo nanobody design against three *Enterococcus faecalis* surface proteins
(Ace, EbpC, Esp) for an *E. coli* whole-cell biosensor.

## Setup

Needs [`uv`](https://docs.astral.sh/uv/) and an NVIDIA GPU.

```bash
git clone https://github.com/NafisNaufal/rfantibody-biosensor.git
cd rfantibody-biosensor
bash setup.sh
```

`setup.sh` does everything: clones RFantibody, installs the Python env, downloads
model weights, and copies the biosensor scripts and input PDBs into place.

## Run

```bash
bash run.sh           # all 3 targets (Ace → EbpC → Esp) + cross-target summary
bash run.sh ace       # one target only
```

Results land in `rfantibody/designs/`.

## Pipeline

```
RFdiffusion ─► geometry filter ─► ProteinMPNN ─► RF2 ─► select + rank
 (backbones)   (drop junk, free)   (sequences)   (predict)  (filter + cluster + winners)
```

1000 backbones per target, 4 sequences each → up to 4000 RF2 predictions per
target. Full details in [`scripts/biosensor/README.md`](scripts/biosensor/README.md).

## Targets

| Target | Input | Hotspots |
|--------|-------|----------|
| Ace    | `inputs/2Z1P.pdb`      | `A180,A182,A193,A195`     |
| EbpC   | `inputs/EBPC_9LLW.pdb` | `A61,A62,A63,A64,A65,A67` |
| Esp    | `inputs/AF_Esp.pdb`    | `A69,A71,A74`             |
