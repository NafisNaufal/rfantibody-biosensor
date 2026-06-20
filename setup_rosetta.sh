#!/bin/bash
# Optional: install PyRosetta for Rosetta ddG scoring.
# Run once after setup.sh. Requires free RosettaCommons academic credentials.
# PyRosetta is installed into rfantibody/.venv-rosetta (separate from the GPU env).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/rfantibody/.venv-rosetta"

if [ -d "$VENV" ]; then
    echo "rfantibody/.venv-rosetta already exists — skipping. To reinstall: rm -rf rfantibody/.venv-rosetta"
    exit 0
fi

echo "==> Creating PyRosetta venv..."
python3 -m venv "$VENV"

echo "==> Installing pyrosetta-installer..."
"$VENV/bin/pip" install --quiet pyrosetta-installer

echo "==> Downloading and installing PyRosetta (will prompt for RosettaCommons credentials)..."
"$VENV/bin/python" -c "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"

echo "==> Verifying..."
"$VENV/bin/python" -c "import pyrosetta; print('PyRosetta OK')"

echo ""
echo "Done. The pipeline will auto-detect PyRosetta on next run (no ROSETTA_CMD needed)."
