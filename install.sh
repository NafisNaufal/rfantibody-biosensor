#!/bin/bash
# Drop the biosensor toolkit + inputs into an existing RFantibody clone.
# Usage: bash install.sh /path/to/RFantibody
set -euo pipefail

RFA="${1:?Usage: bash install.sh /path/to/RFantibody}"
[ -f "$RFA/pyproject.toml" ] || { echo "ERROR: $RFA does not look like an RFantibody clone (no pyproject.toml)"; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$RFA/scripts/biosensor" "$RFA/inputs"
cp -r "$HERE/scripts/biosensor/." "$RFA/scripts/biosensor/"
cp "$HERE/inputs/"*.pdb "$RFA/inputs/"
chmod +x "$RFA/scripts/biosensor/"*.sh "$RFA/scripts/biosensor/"*.slurm 2>/dev/null || true

echo "Installed biosensor toolkit + inputs into: $RFA"
echo "Next:"
echo "  cd $RFA"
echo "  uv run rfdiffusion --help          # sanity check env"
echo "  bash scripts/biosensor/run_all.sh  # or: sbatch scripts/biosensor/submit.slurm"
