#!/bin/bash
# Continuous Esp campaign: run unlimited 50-design batches for each hotspot set.
# Stop with Ctrl-C. Outputs are kept in unique designs/Esp_spot*_batch_* directories.
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'echo ""; echo "Stopped."; exit 130' INT TERM

TARGET_NAME="Esp"
TARGET_PDB="inputs/AF_Esp.pdb"
HOTSPOT_NAMES=("spot1" "spot2" "spot3")
HOTSPOT_VALUES=(
    "A69,A71,A74"
    "A40,A42,A63"
    "A156,A157,A160"
)

: "${BATCH_SIZE:=50}"
: "${SEQS_PER_STRUCT:=4}"
: "${SLEEP_SECONDS:=0}"

# A batch is only "finished" once it either completed selection or the
# geometry filter reported zero survivors (both are terminal outcomes with
# nothing left to compute). Anything else -- no run.log yet, or a run.log
# that stops short of those markers -- means it was cut off mid-step (e.g.
# server died) and should be resumed by name, not abandoned for a fresh one.
is_batch_finished() {
    local log="designs/$1/run.log"
    [ -f "$log" ] && grep -qE "^DONE \($1\)|^WARNING: 0 backbones passed for $1" "$log"
}

find_resumable_batch() {
    local target="$1" spot="$2" d name
    for d in designs/${target}_${spot}_batch_*/; do
        [ -d "$d" ] || continue
        name="$(basename "${d%/}")"
        if ! is_batch_finished "$name"; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

ROUND=1
while true; do
    ROUND_ID="$(printf '%06d' "$ROUND")"

    for i in "${!HOTSPOT_NAMES[@]}"; do
        SPOT_NAME="${HOTSPOT_NAMES[$i]}"
        SPOT_HOTSPOTS="${HOTSPOT_VALUES[$i]}"

        RESUMING=0
        if RESUME_NAME="$(find_resumable_batch "$TARGET_NAME" "$SPOT_NAME")"; then
            BATCH_NAME="$RESUME_NAME"
            RESUMING=1
        else
            STAMP="$(date '+%Y%m%d_%H%M%S')"
            BATCH_NAME="${TARGET_NAME}_${SPOT_NAME}_batch_${ROUND_ID}_${STAMP}"
        fi

        echo ""
        echo "============================================================"
        if [ "$RESUMING" = "1" ]; then
            echo "Resuming $BATCH_NAME (interrupted last time, e.g. by a server restart)"
        else
            echo "Starting $BATCH_NAME ($BATCH_SIZE designs; hotspots=$SPOT_HOTSPOTS)"
        fi
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

        # fold this batch into the running, globally-reclustered leaderboard
        uv run python scripts/biosensor/aggregate_batches.py \
            --target "$TARGET_NAME" --spot "$SPOT_NAME" || \
            echo "WARNING: aggregation failed for $BATCH_NAME; will retry next batch."

        if [ "$SLEEP_SECONDS" -gt 0 ]; then
            sleep "$SLEEP_SECONDS"
        fi
    done

    ROUND=$((ROUND + 1))
done
