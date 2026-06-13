#!/bin/bash
# ============================================================================
# Run all three experiments back-to-back (Ace -> EbpC -> Esp), then summarise.
# Sequential on purpose: you have ONE A100, so the runs must not overlap.
# ============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

for target in ace ebpc esp; do
    echo ""
    echo "############################################################"
    echo "#  Starting $target pipeline"
    echo "############################################################"
    bash "$SCRIPT_DIR/run_${target}.sh"
done

echo ""
echo "############################################################"
echo "#  Cross-target summary"
echo "############################################################"
uv run python "$SCRIPT_DIR/summarize.py" --designs-dir designs

echo ""
echo "All three experiments complete. Best designs across targets: designs/SUMMARY.csv"
