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

# Which hotspot sets to cycle, space-separated. Default: all of them. Override
# to pour all compute into one epitope, e.g.
#   SPOTS=spot1 bash scripts/biosensor/run_esp_loop.sh
: "${SPOTS:=${HOTSPOT_NAMES[*]}}"

# Fail fast on a typo: an unmatched name would leave the `while true` below
# spinning forever with no work to do.
for _s in $SPOTS; do
    case " ${HOTSPOT_NAMES[*]} " in
        *" $_s "*) ;;
        *) echo "ERROR: unknown spot '$_s' (known: ${HOTSPOT_NAMES[*]})" >&2; exit 1 ;;
    esac
done
echo "Cycling hotspot set(s): $SPOTS"

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
FAILS=0     # consecutive failures, drives the backoff below
while true; do
    ROUND_ID="$(printf '%06d' "$ROUND")"

    for i in "${!HOTSPOT_NAMES[@]}"; do
        SPOT_NAME="${HOTSPOT_NAMES[$i]}"
        SPOT_HOTSPOTS="${HOTSPOT_VALUES[$i]}"

        # skip hotspot sets not selected via $SPOTS
        case " $SPOTS " in *" $SPOT_NAME "*) ;; *) continue ;; esac

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
            FAILS=0
        else
            rc=$?
            if [ "$rc" -eq 130 ] || [ "$rc" -eq 143 ]; then
                echo "Stopped."
                exit "$rc"
            fi
            # A failed batch keeps no terminal marker, so it is picked up again
            # next round. Without a backoff that becomes a hot spin loop when
            # the cause is persistent (wrong working directory, missing env,
            # GPU OOM) -- which is exactly how ~13 days were burned unnoticed.
            FAILS=$((FAILS + 1))
            if [ "$FAILS" -ge 6 ]; then BACKOFF=900; else BACKOFF=$((30 << (FAILS - 1))); fi
            echo "WARNING: batch $BATCH_NAME failed with exit code $rc (consecutive failures: $FAILS)."
            if [ "$FAILS" -ge 3 ]; then
                echo "  >> $FAILS batches have failed in a row. This is very likely systematic"
                echo "  >> (wrong working directory, missing uv env, or GPU OOM) rather than"
                echo "  >> bad luck. Read the error above instead of leaving this running."
            fi
            echo "  backing off ${BACKOFF}s before the next attempt."
            sleep "$BACKOFF"
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
