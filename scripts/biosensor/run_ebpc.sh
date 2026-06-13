#!/bin/bash
# Experiment 2/3 : EbpC (pilus shaft N-terminal domain, PDB 9LLW)
PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAME="EbpC"
TARGET="inputs/EBPC_9LLW.pdb"
HOTSPOTS="A61,A62,A63,A64,A65,A67"   # spot #1 (AB loop, D1)   (backups: #2 A86,A88,A89,A92,A94   #3 A72,A73,A74)

: "${NUM_DESIGNS:=1000}"   # full run; override for a quick test: NUM_DESIGNS=20 bash run_ebpc.sh
: "${SEQS_PER_STRUCT:=4}"  # 4 seqs per backbone → 4000 RF2 runs per target

# To add Rosetta ddG, point this at your PyRosetta env's python (see README):
# ROSETTA_CMD="$HOME/envs/pyrosetta/bin/python scripts/biosensor/score_rosetta.py"

# Other knobs (NUM_DESIGNS, cutoffs, weights, CLEAN, ...) default in _pipeline.sh;
# override by setting the variable here before the source line.
source "$PIPELINE_DIR/_pipeline.sh"
