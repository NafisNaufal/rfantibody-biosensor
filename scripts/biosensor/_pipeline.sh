# ============================================================================
# Shared 5-step nanobody pipeline. SOURCED by run_<target>.sh after they set:
#   NAME, TARGET, HOTSPOTS   (required)
#   ROSETTA_CMD              (optional: PyRosetta python + score_rosetta.py)
#   any tunable below        (optional: set before `source` to override)
# Steps: RFdiffusion -> geometry filter -> ProteinMPNN -> RF2 -> select + rank
# Adds: idempotent re-runs, per-step timing, a run.log, and the Rosetta hook.
# ============================================================================
set -euo pipefail

# ---- tunables (override by setting the var before sourcing) ----------------
: "${FRAMEWORK:=inputs/Scaffold.pdb}"
: "${LOOPS:=H1:10,H2:6,H3:16}"     # = scaffold's native CDR lengths
: "${NUM_DESIGNS:=100}"
: "${BREAK_CUTOFF:=4.5}"           # step 2: reject Cα-Cα break > this (Å)
: "${CONTACT_CUTOFF:=10.0}"        # step 2: reject undocked (CDR-target > this Å); <=0 off
: "${SEQS_PER_STRUCT:=4}"          # step 3
: "${MPNN_TEMP:=0.1}"              # step 3: low temp = stable, expressible seqs
: "${RF2_RECYCLES:=10}"            # step 4
: "${RF2_HOTSPOT_SHOW:=0.0}"       # step 4: 0 = blind = stricter filter
: "${PAE_CUTOFF:=10}"              # step 5
: "${RMSD_CUTOFF:=2.0}"            # step 5: dock AND CDR RMSD both < this
: "${DG_CUTOFF:=-10.0}"            # step 5: PRODIGY ΔG must be < this (kcal/mol)
: "${TOP_N:=10}"                   # step 5: number of distinct winners to extract
: "${ROSETTA_CMD:=}"              # step 5: empty = skip Rosetta ddG
: "${CLEAN:=true}"                 # idempotent re-runs: wipe this target's outputs first

# ---- setup -----------------------------------------------------------------
PROJECT_ROOT="$(cd "$PIPELINE_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

OUTDIR="designs/$NAME"
if [ "$CLEAN" = "true" ]; then rm -rf "$OUTDIR"; fi   # fresh, error-free re-run
mkdir -p "$OUTDIR"
LOG="$OUTDIR/run.log"
exec > >(tee -a "$LOG") 2>&1                 # mirror all output to the log

BB="$OUTDIR/1_backbones.qv"; FILT="$OUTDIR/2_filtered.qv"
MPNN="$OUTDIR/3_mpnn.qv";    RF2="$OUTDIR/4_rf2.qv"

_t()    { STEP_T0=$SECONDS; echo ""; echo "$1"; }
_done() { echo "  ($1 done in $((SECONDS - STEP_T0))s)"; }

echo "================ $NAME  @ $(date '+%Y-%m-%d %H:%M:%S') ================"
echo "target=$TARGET  hotspots=$HOTSPOTS  loops=$LOOPS  n=$NUM_DESIGNS"
[ -n "$ROSETTA_CMD" ] && echo "rosetta ddG: ON" || echo "rosetta ddG: off (set ROSETTA_CMD to enable)"

# ---- step 1: RFdiffusion ---------------------------------------------------
_t "[1/5] RFdiffusion ($NUM_DESIGNS backbones)"
uv run rfdiffusion \
    --target "$TARGET" --framework "$FRAMEWORK" --output-quiver "$BB" \
    --num-designs "$NUM_DESIGNS" --design-loops "$LOOPS" --hotspots "$HOTSPOTS" \
    --deterministic
_done "[1/5]"

# ---- step 2: geometry filter (GPU-free) ------------------------------------
_t "[2/5] Geometry filter (drop broken / undocked)"
uv run python scripts/biosensor/filter_backbones.py \
    --input "$BB" --output "$FILT" --report "$OUTDIR/filter_report.csv" \
    --break-cutoff "$BREAK_CUTOFF" --contact-cutoff "$CONTACT_CUTOFF" --overwrite
_done "[2/5]"

# stop cleanly if nothing survived -- avoids crashing MPNN/RF2 on an empty quiver
N_FILT=$(grep -c '^QV_TAG' "$FILT" 2>/dev/null || true); N_FILT=${N_FILT:-0}
echo "  ($N_FILT backbones passed the geometry filter)"
if [ "$N_FILT" -eq 0 ]; then
    echo "WARNING: 0 backbones passed for $NAME (poor hotspot/dock?). Skipping steps 3-5."
    exit 0
fi

# ---- step 3: ProteinMPNN ---------------------------------------------------
_t "[3/5] ProteinMPNN ($SEQS_PER_STRUCT seqs/backbone)"
uv run proteinmpnn \
    --input-quiver "$FILT" --output-quiver "$MPNN" \
    --seqs-per-struct "$SEQS_PER_STRUCT" --temperature "$MPNN_TEMP"
_done "[3/5]"

# ---- step 4: RF2 -----------------------------------------------------------
_t "[4/5] RF2 ($RF2_RECYCLES recycles)"
uv run rf2 \
    --input-quiver "$MPNN" --output-quiver "$RF2" \
    --num-recycles "$RF2_RECYCLES" --hotspot-show-prop "$RF2_HOTSPOT_SHOW"
_done "[4/5]"

# ---- step 5: select + rank (GPU-free) --------------------------------------
_t "[5/5] Select + rank (pAE<$PAE_CUTOFF, RMSD<$RMSD_CUTOFF, dG<$DG_CUTOFF${ROSETTA_CMD:+, +Rosetta})"
uv run python scripts/biosensor/select_designs.py \
    --input "$RF2" --outdir "$OUTDIR" \
    --pae-cutoff "$PAE_CUTOFF" --rmsd-cutoff "$RMSD_CUTOFF" --dg-cutoff "$DG_CUTOFF" \
    --top "$TOP_N" --rosetta-cmd "$ROSETTA_CMD"
_done "[5/5]"

echo ""
echo "DONE ($NAME) in $((SECONDS))s total."
echo "  ranked table : $OUTDIR/5_selection.csv"
echo "  winners      : $OUTDIR/winners/   (distinct, rank-ordered)"
echo "  log          : $LOG"
