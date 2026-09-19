#!/bin/bash
# One-shot pipeline run against an arbitrary target + hotspot set.
# The CLI covers the common knobs; advanced pipeline settings remain available
# as environment variables for reproducibility and power-user runs.
#
# Example:
#   bash scripts/biosensor/run_custom.sh \
#     --name Ace_D229 --target inputs/2Z1P.pdb \
#     --hotspots A229,A231,A236,A238 --designs 50
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: bash scripts/biosensor/run_custom.sh [OPTIONS]

Required:
  --name NAME                 unique output name, e.g. Ace_D229
  --target PDB                target PDB relative to the RFantibody checkout
  --hotspots LIST             comma-separated hotspots, e.g. A229,A231,A236,A238

Common options:
  --designs N                 RFdiffusion backbones [100]
  --sequences N               ProteinMPNN sequences per backbone [4]
  --chunk-size N              GPU resume granularity [50]
  --output-root DIR           output root [designs/new_hotspots]
  --resume                    resume this named output (default)
  --clean                     refuse unless ALLOW_DESTRUCTIVE_CLEAN=true is set
  -h, --help                  show this help

Advanced pipeline settings (PAE_CUTOFF, RMSD_CUTOFF, RF2_RECYCLES, ...)
remain available as environment variables.
EOF
}

require_value() {
    [ "$#" -ge 2 ] || { echo "ERROR: $1 requires a value" >&2; exit 2; }
}

NAME="${NAME-}"
TARGET="${TARGET-}"
HOTSPOTS="${HOTSPOTS-}"
: "${DESIGNS_DIR:=designs/new_hotspots}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --name)
            require_value "$@"
            NAME="$2"
            shift 2
            ;;
        --target)
            require_value "$@"
            TARGET="$2"
            shift 2
            ;;
        --hotspots)
            require_value "$@"
            HOTSPOTS="$2"
            shift 2
            ;;
        --designs|--num-designs)
            require_value "$@"
            NUM_DESIGNS="$2"
            shift 2
            ;;
        --sequences|--seqs-per-struct)
            require_value "$@"
            SEQS_PER_STRUCT="$2"
            shift 2
            ;;
        --chunk-size)
            require_value "$@"
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --output-root|--designs-dir)
            require_value "$@"
            DESIGNS_DIR="$2"
            shift 2
            ;;
        --resume)
            CLEAN=false
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unexpected argument '$1'" >&2
            usage >&2
            exit 2
            ;;
    esac
done

: "${NAME:?set --name NAME (or NAME=...)}"
: "${TARGET:?set --target PDB (or TARGET=...)}"
: "${HOTSPOTS:?set --hotspots LIST (or HOTSPOTS=...)}"

source "$PIPELINE_DIR/_pipeline.sh"
