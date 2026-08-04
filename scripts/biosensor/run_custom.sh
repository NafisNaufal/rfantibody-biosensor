#!/bin/bash
# One-shot pipeline run against an arbitrary target + hotspot set.
#
# For exploring a new epitope without editing run_<target>.sh, or for
# side-by-side epitope comparisons at a fixed design count.
#
# Required: NAME, TARGET, HOTSPOTS
# Optional: anything _pipeline.sh accepts (NUM_DESIGNS, SEQS_PER_STRUCT,
#           CHUNK_SIZE, PAE_CUTOFF, ...), plus CUDA_VISIBLE_DEVICES to pin
#           the run to one GPU.
#
# Example -- two epitopes in parallel, one per GPU:
#   CUDA_VISIBLE_DEVICES=0 NAME=Ace_surf2spot_D229 TARGET=inputs/2Z1P.pdb \
#     HOTSPOTS=A229,A231,A236,A238 NUM_DESIGNS=1000 SEQS_PER_STRUCT=4 \
#     bash scripts/biosensor/run_custom.sh
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${NAME:?set NAME, e.g. NAME=Ace_surf2spot_D229}"
: "${TARGET:?set TARGET, e.g. TARGET=inputs/2Z1P.pdb}"
: "${HOTSPOTS:?set HOTSPOTS, e.g. HOTSPOTS=A229,A231,A236,A238}"

source "$PIPELINE_DIR/_pipeline.sh"
