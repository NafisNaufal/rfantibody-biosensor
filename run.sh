#!/bin/bash
# Run the biosensor pipeline from the rfantibody-biosensor root.
# Usage:
#   bash run.sh           # all 3 targets (Ace, EbpC, Esp) + summary
#   bash run.sh ace       # one target only
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RFA="$HERE/rfantibody"

[ -d "$RFA" ] || { echo "ERROR: rfantibody/ not found. Run: bash setup.sh"; exit 1; }
cd "$RFA"

TARGET="${1:-all}"
if [ "$TARGET" = "all" ]; then
    bash scripts/biosensor/run_all.sh
else
    bash "scripts/biosensor/run_${TARGET}.sh"
fi
