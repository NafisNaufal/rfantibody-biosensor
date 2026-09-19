#!/bin/bash
# Continuous Ace campaign: run unlimited 50-design batches for each hotspot set.
# Stop with Ctrl-C. Outputs are kept in unique designs/Ace_spot*_batch_* directories.
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'echo ""; echo "Stopped."; exit 130' INT TERM

TARGET_NAME="Ace"
TARGET_PDB="inputs/2Z1P.pdb"
HOTSPOT_NAMES=("spot1" "spot2" "spot3" "D229" "S295")
HOTSPOT_VALUES=(
    "A180,A182,A193,A195"
    "A206,A300,A301,A304"
    "A146,A147,A158"
    # Surf2Spot-derived sites, in 2Z1P AUTHOR numbering. Surf2Spot reports
    # sequential indices over resolved residues only; 2Z1P chain A starts at 31
    # with four gaps, so its indices run 43 low (186/188/193/195 -> 229/231/236/238).
    "A229,A231,A236,A238"              # D229 V231 T236 Y238
    "A295,A297,A300,A308,A310,A311"    # S295 D297 Y300 T308 E310 K311
)

: "${BATCH_SIZE:=50}"
: "${SEQS_PER_STRUCT:=4}"
: "${SLEEP_SECONDS:=0}"

# Which hotspot sets to cycle, space-separated. Default: all of them. Override
# to pour all compute into one epitope, e.g.
#   SPOTS=spot1 bash scripts/biosensor/run_ace_loop.sh
: "${SPOTS:=${HOTSPOT_NAMES[*]}}"

# Fail fast on a typo: an unmatched name would leave the `while true` below
# spinning forever with no work to do.
for _s in $SPOTS; do
    case " ${HOTSPOT_NAMES[*]} " in
        *" $_s "*) ;;
        *) echo "ERROR: unknown spot '$_s' (known: ${HOTSPOT_NAMES[*]})" >&2; exit 1 ;;
    esac
done

# Guard the residue numbering before any GPU time is spent. A hotspot that does
# not exist in the target is not an error RFdiffusion reports -- it just builds
# against whatever is left, so an indefinite run can burn weeks designing
# binders for the wrong surface. This is the exact failure mode the Surf2Spot
# +43 offset sets up, so check every selected set against the PDB up front.
#
# NB: existence is a weak test on its own -- the off-by-43 indices (186, 188)
# are perfectly real residues, just the wrong ones. So print each hotspot's
# identity and eyeball it against what you meant: D229 V231 T236 Y238 should
# read ASP VAL THR TYR, and anything else means the numbering slipped.
validate_hotspots() {
    local pdb="$1" name="$2" spec="$3" h ch num aa rc=0 ids=""
    for h in $(echo "$spec" | tr ',' ' '); do
        ch="${h:0:1}"; num="${h:1}"
        aa=$(awk -v c="$ch" -v n="$num" '
                substr($0,1,4)=="ATOM" && substr($0,22,1)==c && substr($0,23,4)+0==n {
                    print substr($0,18,3); exit }' "$pdb")
        if [ -z "$aa" ]; then
            echo "ERROR: $name hotspot $h is not a resolved residue in $pdb" >&2
            rc=1
        else
            ids="$ids $h=$aa"
        fi
    done
    [ "$rc" -eq 0 ] && echo "  $name:$ids"
    return $rc
}

[ -f "$TARGET_PDB" ] || { echo "ERROR: $TARGET_PDB not found (run from the rfantibody/ dir)" >&2; exit 1; }
for _s in $SPOTS; do
    for _i in "${!HOTSPOT_NAMES[@]}"; do
        [ "${HOTSPOT_NAMES[$_i]}" = "$_s" ] || continue
        validate_hotspots "$TARGET_PDB" "$_s" "${HOTSPOT_VALUES[$_i]}" || exit 1
    done
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
