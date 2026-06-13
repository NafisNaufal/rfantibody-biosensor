#!/bin/bash
# ============================================================================
# SLURM submission -- ONE job per target (Ace, EbpC, Esp) via a job array.
# Submit from the repo root:   sbatch scripts/biosensor/submit.slurm
#
# Why an array: a 1000-design run per target takes many hours -- usually more
# than one all-in-one job should hold. Each array task is its own job with its
# own wall-time budget; %1 runs them one-at-a-time (you have a single A100).
#
# >>> SET --time below from your 100-design pilot: open designs/<T>/run.log,
#     find "DONE (...) in Ns total", multiply by ~10, add margin, and cap at
#     your cluster's max wall time. Also set partition/account/gres for your site.
# ============================================================================
#SBATCH --job-name=nb_biosensor
#SBATCH --partition=gpu              # <-- your GPU partition
#SBATCH --gres=gpu:a100:1            # <-- 1x A100
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=48:00:00              # <-- PER TARGET. SET FROM YOUR PILOT TIMING!
#SBATCH --array=0-2%1                # 3 targets, one at a time
#SBATCH --output=slurm-nb-%A_%a.out
#SBATCH --error=slurm-nb-%A_%a.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

TARGETS=(ace ebpc esp)
T="${TARGETS[$SLURM_ARRAY_TASK_ID]}"
echo "=== array task $SLURM_ARRAY_TASK_ID -> $T  @ $(date) ==="

# module load cuda/12.2              # uncomment if your cluster needs it
nvidia-smi || { echo "No GPU visible"; exit 1; }

# Warm the isolated PRODIGY env (needs internet once, then cached). If compute
# nodes are offline, run this on a LOGIN node first:
#   uv run --no-project --with prodigy-prot prodigy --help
if uv run --no-project --with prodigy-prot prodigy --help >/dev/null 2>&1; then
    echo "PRODIGY ready."
else
    echo "WARNING: PRODIGY unavailable on this node (offline?). Step 5 keeps pAE+RMSD but skips ΔG."
fi

bash "scripts/biosensor/run_${T}.sh"

echo "Task $T finished. After ALL THREE complete, build the cross-target table:"
echo "  uv run python scripts/biosensor/summarize.py"
