#!/bin/bash
# Continuous EbpC campaign: run unlimited 50-design batches.
# Stop with Ctrl-C. Outputs are kept in unique designs/EbpC_batch_* directories.
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'echo ""; echo "Stopped."; exit 130' INT TERM

TARGET_NAME="EbpC"
TARGET_PDB="inputs/EBPC_9LLW.pdb"
TARGET_HOTSPOTS="A61,A62,A63,A64,A65,A67"

: "${BATCH_SIZE:=50}"
: "${SEQS_PER_STRUCT:=4}"
: "${SLEEP_SECONDS:=0}"

BATCH=1
while true; do
    STAMP="$(date '+%Y%m%d_%H%M%S')"
    BATCH_ID="$(printf '%06d' "$BATCH")"
    BATCH_NAME="${TARGET_NAME}_batch_${BATCH_ID}_${STAMP}"

    echo ""
    echo "============================================================"
    echo "Starting $BATCH_NAME ($BATCH_SIZE designs)"
    echo "============================================================"

    if (
        SECONDS=0
        PIPELINE_DIR="$PIPELINE_DIR"
        NAME="$BATCH_NAME"
        TARGET="$TARGET_PDB"
        HOTSPOTS="$TARGET_HOTSPOTS"
        NUM_DESIGNS="$BATCH_SIZE"
        CHUNK_SIZE="$BATCH_SIZE"
        SEQS_PER_STRUCT="$SEQS_PER_STRUCT"
        CLEAN=false
        source "$PIPELINE_DIR/_pipeline.sh"
    ); then
        echo "Batch $BATCH_NAME finished."
    else
        rc=$?
        if [ "$rc" -eq 130 ] || [ "$rc" -eq 143 ]; then
            echo "Stopped."
            exit "$rc"
        fi
        echo "WARNING: batch $BATCH_NAME failed with exit code $rc; continuing."
    fi

    BATCH=$((BATCH + 1))
    if [ "$SLEEP_SECONDS" -gt 0 ]; then
        sleep "$SLEEP_SECONDS"
    fi
done
