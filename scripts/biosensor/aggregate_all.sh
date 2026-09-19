#!/bin/bash
# On-demand check-in: fold in every finished batch across all configured
# targets/hotspot sets, then print the cross-campaign leaderboard. Safe to run
# anytime, as often as you like -- each call only processes what's new
# since the last one (see aggregate_batches.py).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.."
: "${DESIGNS_DIR:=designs}"

# The legacy campaign uses designs/. New Ace campaigns default to
# designs/new_hotspots/; select that root explicitly when checking it:
#   DESIGNS_DIR=designs/new_hotspots bash scripts/biosensor/aggregate_all.sh

declare -A HOTSPOTS_BY_TARGET=(
    [Ace]="spot1 spot2 spot3 D229 S295"
    [EbpC]="spot1 spot2 spot3"
    [Esp]="spot1 spot2 spot3"
)

for TARGET in "${!HOTSPOTS_BY_TARGET[@]}"; do
    for SPOT in ${HOTSPOTS_BY_TARGET[$TARGET]}; do
        EXTRA=()
        if [ "$TARGET" = "EbpC" ]; then
            EXTRA=(--rmsd-cutoff 999)   # see run_ebpc_loop.sh: EBPC_9LLW residue-gap bug
        fi
        uv run python scripts/biosensor/aggregate_batches.py \
            --target "$TARGET" --spot "$SPOT" --designs-dir "$DESIGNS_DIR" "${EXTRA[@]}"
    done
done

echo ""
echo "############################################################"
echo "#  Cross-campaign summary (all targets x all hotspot spots)"
echo "############################################################"
uv run python scripts/biosensor/summarize.py --designs-dir "$DESIGNS_DIR"
