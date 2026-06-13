#!/bin/bash
# One-shot setup: clones RFantibody, installs env + weights, drops in biosensor files.
# Run once from the rfantibody-biosensor directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RFA="$HERE/rfantibody"

if [ -d "$RFA" ]; then
    echo "rfantibody/ already exists — skipping clone. To start fresh: rm -rf rfantibody/"
else
    echo "==> Cloning RFantibody..."
    git clone https://github.com/RosettaCommons/RFantibody.git "$RFA"
fi

echo "==> Installing Python env..."
cd "$RFA"
uv sync

echo "==> Downloading model weights..."
bash include/download_weights.sh

echo "==> Installing biosensor scripts + inputs..."
mkdir -p scripts/biosensor inputs
cp -r "$HERE/scripts/biosensor/." scripts/biosensor/
cp "$HERE/inputs/"*.pdb inputs/
chmod +x scripts/biosensor/*.sh 2>/dev/null || true

echo "==> Pre-warming PRODIGY (needs internet, cached after this)..."
uv run --no-project --with prodigy-prot prodigy --help >/dev/null && echo "   PRODIGY ok."

echo ""
echo "Setup complete. Run the pipeline:"
echo "  bash run.sh              # all 3 targets"
echo "  bash run.sh ace          # one target only"
