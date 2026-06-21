#!/bin/bash
# Experiment 1/3 : Ace (collagen-adhesin domain, PDB 2Z1P)
PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAME="Ace"
TARGET="inputs/2Z1P.pdb"
HOTSPOTS="A180,A182,A193,A195"   # spot #1   (backups: #2 A206,A300,A301,A304   #3 A146,A147,A158)

: "${NUM_DESIGNS:=1000}"   # full run; override for a quick test: NUM_DESIGNS=20 bash run_ace.sh
: "${SEQS_PER_STRUCT:=4}"  # 4 seqs per backbone → 4000 RF2 runs per target

# Other knobs (NUM_DESIGNS, cutoffs, weights, CLEAN, ...) default in _pipeline.sh;
# override by setting the variable here before the source line.
source "$PIPELINE_DIR/_pipeline.sh"
