#!/bin/bash
# Run the biosensor pipeline from the rfantibody-biosensor root.
# Usage:
#   bash run.sh           # all 3 targets (Ace, EbpC, Esp) + summary
#   bash run.sh ace       # one target only
#   bash run.sh ace-loop --spot D229
#   bash run.sh custom --name Ace_D229 --target inputs/2Z1P.pdb \
#       --hotspots A229,A231,A236,A238 --designs 50
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RFA="$HERE/rfantibody"

[ -d "$RFA" ] || { echo "ERROR: rfantibody/ not found. Run: bash setup.sh"; exit 1; }
cd "$RFA"

TARGET="${1:-all}"
if [ "$#" -gt 0 ]; then
    shift
fi
if [ "$TARGET" = "all" ]; then
    [ "$#" -eq 0 ] || { echo "ERROR: 'all' does not accept extra arguments" >&2; exit 2; }
    bash scripts/biosensor/run_all.sh
else
    case "$TARGET" in
        ace-loop) SCRIPT="run_ace_loop.sh" ;;
        *) SCRIPT="run_${TARGET}.sh" ;;
    esac
    bash "scripts/biosensor/$SCRIPT" "$@"
fi
