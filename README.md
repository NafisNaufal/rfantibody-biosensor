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

# New Ace Surf2Spot campaign; writes only under the isolated new-hotspot root
bash run.sh ace-loop --spot D229 --batch-size 50 --output-root designs/new_hotspots

# validate the default D229/S295 selection without starting GPU work
bash run.sh ace-loop --dry-run

# One-shot run for any target/hotspot set
bash run.sh custom --name Ace_D229 --target inputs/2Z1P.pdb \
  --hotspots A229,A231,A236,A238 --designs 50
```

Results from the legacy runners remain in `rfantibody/designs/`. New hotspot
commands above use `rfantibody/designs/new_hotspots/`, so the existing ACE
campaign is not reused, cleaned, or overwritten.

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
| Ace    | `inputs/2Z1P.pdb`      | existing: `A180,A182,A193,A195` |
| Ace    | `inputs/2Z1P.pdb`      | Surf2Spot D229: `A229,A231,A236,A238` |
| Ace    | `inputs/2Z1P.pdb`      | Surf2Spot S295: `A295,A297,A300,A308,A310,A311` |
| EbpC   | `inputs/EBPC_9LLW.pdb` | `A61,A62,A63,A64,A65,A67` |
| Esp    | `inputs/AF_Esp.pdb`    | `A69,A71,A74`             |
