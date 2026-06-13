#!/bin/bash
# Experiment 3/3 : Esp (surface protein, AlphaFold model AF_Esp)
PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAME="Esp"
TARGET="inputs/AF_Esp.pdb"
HOTSPOTS="A69,A71,A74"   # spot #1   (backups: #2 A40,A42,A63   #3 A156,A157,A160)

: "${NUM_DESIGNS:=1000}"   # full run; override for a quick test: NUM_DESIGNS=20 bash run_esp.sh
: "${SEQS_PER_STRUCT:=4}"  # 4 seqs per backbone → 4000 RF2 runs per target

# To add Rosetta ddG, point this at your PyRosetta env's python (see README):
# ROSETTA_CMD="$HOME/envs/pyrosetta/bin/python scripts/biosensor/score_rosetta.py"

# Other knobs (NUM_DESIGNS, cutoffs, weights, CLEAN, ...) default in _pipeline.sh;
# override by setting the variable here before the source line.
source "$PIPELINE_DIR/_pipeline.sh"
