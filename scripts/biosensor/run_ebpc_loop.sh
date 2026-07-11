#!/bin/bash
# Continuous EbpC campaign: run unlimited 50-design batches for each hotspot set.
# Stop with Ctrl-C. Outputs are kept in unique designs/EbpC_spot*_batch_* directories.
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'echo ""; echo "Stopped."; exit 130' INT TERM

TARGET_NAME="EbpC"
TARGET_PDB="inputs/EBPC_9LLW.pdb"
HOTSPOT_NAMES=("spot1" "spot2" "spot3")
HOTSPOT_VALUES=(
    "A61,A62,A63,A64,A65,A67"
    "A86,A88,A89,A92,A94"
    "A72,A73,A74"
)

: "${BATCH_SIZE:=50}"
: "${SEQS_PER_STRUCT:=4}"
: "${SLEEP_SECONDS:=0}"

ROUND=1
while true; do
    ROUND_ID="$(printf '%06d' "$ROUND")"

    for i in "${!HOTSPOT_NAMES[@]}"; do
        SPOT_NAME="${HOTSPOT_NAMES[$i]}"
        SPOT_HOTSPOTS="${HOTSPOT_VALUES[$i]}"
        STAMP="$(date '+%Y%m%d_%H%M%S')"
        BATCH_NAME="${TARGET_NAME}_${SPOT_NAME}_batch_${ROUND_ID}_${STAMP}"

        echo ""
        echo "============================================================"
        echo "Starting $BATCH_NAME ($BATCH_SIZE designs; hotspots=$SPOT_HOTSPOTS)"
        echo "============================================================"

        if (
            SECONDS=0
            PIPELINE_DIR="$PIPELINE_DIR"
            NAME="$BATCH_NAME"
            TARGET="$TARGET_PDB"
            HOTSPOTS="$SPOT_HOTSPOTS"
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

        # trajectory files are multi-GB and never needed past this point
        find "designs/$BATCH_NAME" -name '*_traj.qv' -delete 2>/dev/null || true

        # fold this batch into the running, globally-reclustered leaderboard.
        # NOTE: --rmsd-cutoff bypassed (EBPC_9LLW has a residue-numbering gap,
        # 49-59, that corrupts RF2's target-aligned RMSD; see 5649be7 history --
        # dG/pAE/lDDT/H3 remain trustworthy and still gate + rank everything).
        uv run python scripts/biosensor/aggregate_batches.py \
            --target "$TARGET_NAME" --spot "$SPOT_NAME" --rmsd-cutoff 999 || \
            echo "WARNING: aggregation failed for $BATCH_NAME; will retry next batch."

        if [ "$SLEEP_SECONDS" -gt 0 ]; then
            sleep "$SLEEP_SECONDS"
        fi
    done

    ROUND=$((ROUND + 1))
done
