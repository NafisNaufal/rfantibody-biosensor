#!/bin/bash
# Continuous Ace campaign: run unlimited batches for selected hotspot sets.
# Stop with Ctrl-C. New campaigns default to designs/new_hotspots/ so the legacy
# designs/ tree is never selected accidentally.
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
HOTSPOT_EXPECTED=(
    "TYR,VAL,ARG,PHE"
    "THR,TYR,GLN,ASN"
    "ILE,GLU,ARG"
    "ASP,VAL,THR,TYR"
    "SER,ASP,TYR,THR,GLU,LYS"
)
NEW_HOTSPOT_NAMES=("D229" "S295")

: "${BATCH_SIZE:=50}"
: "${SEQS_PER_STRUCT:=4}"
: "${SLEEP_SECONDS:=0}"
: "${DESIGNS_DIR:=designs/new_hotspots}"
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage: bash scripts/biosensor/run_ace_loop.sh [OPTIONS]

Run the continuous Ace campaign. The default output root is
designs/new_hotspots, separate from the legacy designs/ tree.

Options:
  --spot NAME                 run one set, e.g. D229
  --spots "NAME ..."          run several sets in order
  --batch-size N              designs per batch [50]
  --sequences N               sequences per backbone [4]
  --output-root DIR           output root [designs/new_hotspots]
  --sleep-seconds N           pause between batches [0]
  --dry-run                   validate and print the campaign without GPU work
  -h, --help                  show this help

Known sets: spot1 spot2 spot3 D229 S295
Default sets: D229 S295
EOF
}

require_value() {
    [ "$#" -ge 2 ] || { echo "ERROR: $1 requires a value" >&2; exit 2; }
}

SPOTS_ARG=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --spot|--spots)
            require_value "$@"
            SPOTS_ARG="$2"
            shift 2
            ;;
        --batch-size)
            require_value "$@"
            BATCH_SIZE="$2"
            shift 2
            ;;
        --sequences|--seqs-per-struct)
            require_value "$@"
            SEQS_PER_STRUCT="$2"
            shift 2
            ;;
        --output-root|--designs-dir)
            require_value "$@"
            DESIGNS_DIR="$2"
            shift 2
            ;;
        --sleep-seconds)
            require_value "$@"
            SLEEP_SECONDS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [ -n "$SPOTS_ARG" ]; then
                echo "ERROR: unexpected argument '$1'" >&2
                usage >&2
                exit 2
            fi
            SPOTS_ARG="$1"
            shift
            ;;
    esac
done

# Which hotspot sets to cycle, space-separated. An explicit command-line value
# wins over the environment; otherwise preserve the SPOTS compatibility knob.
if [ -n "$SPOTS_ARG" ]; then
    SPOTS="$SPOTS_ARG"
else
    : "${SPOTS:=${NEW_HOTSPOT_NAMES[*]}}"
fi

case "$BATCH_SIZE" in ''|*[!0-9]*|0) echo "ERROR: --batch-size must be a positive integer" >&2; exit 2 ;; esac
case "$SEQS_PER_STRUCT" in ''|*[!0-9]*|0) echo "ERROR: --sequences must be a positive integer" >&2; exit 2 ;; esac
case "$SPOTS" in *[![:space:]]*) ;; *) echo "ERROR: no hotspot set selected" >&2; exit 2 ;; esac

PROJECT_ROOT="$(cd "$PIPELINE_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Fail fast on a typo: an unmatched name would leave the `while true` below
# spinning forever with no work to do.
for _s in $SPOTS; do
    case " ${HOTSPOT_NAMES[*]} " in
        *" $_s "*) ;;
        *) echo "ERROR: unknown spot '$_s' (known: ${HOTSPOT_NAMES[*]})" >&2; exit 1 ;;
    esac
done

# Guard the residue numbering before any GPU time is spent. The expected
# identities also catch a valid-but-wrong numbering frame (the Surf2Spot +43
# offset is the known failure mode for these sites).
for _s in $SPOTS; do
    for _i in "${!HOTSPOT_NAMES[@]}"; do
        [ "${HOTSPOT_NAMES[$_i]}" = "$_s" ] || continue
        uv run python scripts/biosensor/validate_hotspots.py \
            --pdb "$TARGET_PDB" --hotspots "${HOTSPOT_VALUES[$_i]}" \
            --expected "${HOTSPOT_EXPECTED[$_i]}" --label "$_s" || exit 1
    done
done

echo "Cycling hotspot set(s): $SPOTS"

if [ "$DRY_RUN" = "true" ]; then
    echo "Dry run complete: no design output was created and no GPU command was started."
    echo "  output root: $DESIGNS_DIR"
    exit 0
fi

# A batch is only "finished" once it either completed selection or the
# geometry filter reported zero survivors (both are terminal outcomes with
# nothing left to compute). Anything else -- no run.log yet, or a run.log
# that stops short of those markers -- means it was cut off mid-step (e.g.
# server died) and should be resumed by name, not abandoned for a fresh one.
is_batch_finished() {
    local log="$DESIGNS_DIR/$1/run.log"
    [ -f "$log" ] && grep -qE "^DONE \($1\)|^WARNING: 0 backbones passed for $1" "$log"
}

find_resumable_batch() {
    local target="$1" spot="$2" d name
    for d in "$DESIGNS_DIR"/${target}_${spot}_batch_*/; do
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
            HOTSPOTS_EXPECTED="${HOTSPOT_EXPECTED[$i]}"
            DESIGNS_DIR="$DESIGNS_DIR"
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
            # next round. Backoff prevents a persistent GPU/environment failure
            # from hot-looping and consuming scheduler time.
            FAILS=$((FAILS + 1))
            if [ "$FAILS" -ge 6 ]; then BACKOFF=900; else BACKOFF=$((30 << (FAILS - 1))); fi
            echo "WARNING: batch $BATCH_NAME failed with exit code $rc (consecutive failures: $FAILS)."
            if [ "$FAILS" -ge 3 ]; then
                echo "  >> $FAILS batches have failed in a row; inspect the error above."
            fi
            echo "  backing off ${BACKOFF}s before the next attempt."
            sleep "$BACKOFF"
        fi

        # trajectory files are multi-GB and never needed past this point
        # Trajectories are disposable intermediates, and pruning only occurs
        # inside the selected output root. The legacy designs/ tree is never
        # touched by the default new-hotspot command.
        find "$DESIGNS_DIR/$BATCH_NAME" -name '*_traj.qv' -delete 2>/dev/null || true

        # fold this batch into the running, globally-reclustered leaderboard
        uv run python scripts/biosensor/aggregate_batches.py \
            --target "$TARGET_NAME" --spot "$SPOT_NAME" --designs-dir "$DESIGNS_DIR" || \
            echo "WARNING: aggregation failed for $BATCH_NAME; will retry next batch."

        if [ "$SLEEP_SECONDS" -gt 0 ]; then
            sleep "$SLEEP_SECONDS"
        fi
    done

    ROUND=$((ROUND + 1))
done
