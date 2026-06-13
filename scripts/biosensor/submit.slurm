#!/bin/bash
# ============================================================================
# SLURM submission for the full 3-target nanobody campaign on one A100 80GB.
# Submit from the repo root:   sbatch scripts/biosensor/submit.slurm
# Adjust the #SBATCH lines (partition, account, time) to your cluster.
# ============================================================================
#SBATCH --job-name=nb_biosensor
#SBATCH --partition=gpu              # <-- change to your GPU partition
#SBATCH --gres=gpu:a100:1            # <-- 1x A100 (change name if needed)
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00              # generous for 3x100-design pilots
#SBATCH --output=designs/slurm_%j.out
#SBATCH --error=designs/slurm_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# If your cluster needs a module for the GPU driver/CUDA, load it here:
# module load cuda/12.2
# (uv + the project's .venv provide Python and all packages.)

nvidia-smi || { echo "No GPU visible"; exit 1; }

# --- pre-warm the isolated PRODIGY env (step 5 needs it) --------------------
# Compute nodes are often offline; if this fails, run it once on a LOGIN node
# (it just populates the uv cache), then resubmit.
echo "Pre-warming PRODIGY env ..."
if uv run --no-project --with prodigy-prot prodigy --help >/dev/null 2>&1; then
    echo "  PRODIGY ready."
else
    echo "  WARNING: could not prepare PRODIGY (no internet on this node?)."
    echo "  Run on a login node first:  uv run --no-project --with prodigy-prot prodigy --help"
    echo "  Step 5 will still filter on pAE+RMSD, but ΔG (and ranking) will be incomplete."
fi
# Rosetta ddG is optional and uses your own PyRosetta env (set ROSETTA_CMD in
# the run_*.sh). Make sure that env is reachable from compute nodes if used.

bash scripts/biosensor/run_all.sh
