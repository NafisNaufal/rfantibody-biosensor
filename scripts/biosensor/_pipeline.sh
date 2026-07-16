# ============================================================================
# Shared 5-step nanobody pipeline. SOURCED by run_<target>.sh after they set:
#   NAME, TARGET, HOTSPOTS   (required)
#   any tunable below        (optional: set before `source` to override)
# Steps: RFdiffusion -> geometry filter -> ProteinMPNN -> RF2 -> select + rank
# Adds: per-chunk resume (CLEAN=false default), per-step timing, run.log.
# ============================================================================
set -euo pipefail

# ---- tunables (override by setting the var before sourcing) ----------------
: "${FRAMEWORK:=inputs/Scaffold.pdb}"
: "${LOOPS:=H1:10,H2:6,H3:16}"     # = scaffold's native CDR lengths
: "${NUM_DESIGNS:=100}"
: "${CHUNK_SIZE:=50}"               # designs per GPU call (resume granularity)
: "${BREAK_CUTOFF:=4.0}"           # step 2: reject Cα-Cα break > this (Å)
: "${CONTACT_CUTOFF:=10.0}"        # step 2: reject undocked (CDR-target > this Å); <=0 off
: "${SEQS_PER_STRUCT:=4}"          # step 3
: "${MPNN_TEMP:=0.1}"              # step 3: low temp = stable, expressible seqs
: "${RF2_RECYCLES:=10}"            # step 4
: "${RF2_HOTSPOT_SHOW:=0.0}"       # step 4: 0 = blind = stricter filter
: "${PAE_CUTOFF:=10}"              # step 5
: "${RMSD_CUTOFF:=2.0}"            # step 5: dock AND CDR RMSD both < this
: "${DG_CUTOFF:=-10.0}"            # step 5: PRODIGY ΔG must be < this (kcal/mol)
: "${LDDT_CUTOFF:=0.9}"           # step 5: RF2 pred_lddt must be >= this (0-1)
: "${TOP_N:=10}"                   # step 5: number of distinct winners to extract
: "${CLEAN:=false}"                # false = resume from last completed chunk; true = wipe and restart

# ---- setup -----------------------------------------------------------------
PROJECT_ROOT="$(cd "$PIPELINE_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

OUTDIR="designs/$NAME"
CHUNKS="$OUTDIR/chunks"
if [ "$CLEAN" = "true" ]; then rm -rf "$OUTDIR"; fi
mkdir -p "$OUTDIR" "$CHUNKS"
LOG="$OUTDIR/run.log"
exec > >(tee -a "$LOG") 2>&1

BB="$OUTDIR/1_backbones.qv"; FILT="$OUTDIR/2_filtered.qv"
MPNN="$OUTDIR/3_mpnn.qv";    RF2="$OUTDIR/4_rf2.qv"

_t()    { STEP_T0=$SECONDS; echo ""; echo "$1"; }
_done() { echo "  (step $1 done in $((SECONDS - STEP_T0))s)"; touch "$OUTDIR/.step${1}.done"; }
_skip() { echo ""; echo "[SKIP] step $1 already complete — delete $OUTDIR/.step${1}.done to re-run"; }

# split a quiver file into per-chunk files; outputs chunk paths to stdout
_split_quiver() {
    local INPUT="$1" PREFIX="$2" CSIZE="$3"
    uv run python - "$INPUT" "$PREFIX" "$CSIZE" <<'PYEOF'
import sys, os
input_path, prefix, chunk_size = sys.argv[1], sys.argv[2], int(sys.argv[3])
blocks, current = [], []
with open(input_path) as f:
    for line in f:
        if line.startswith("QV_TAG ") and current:
            blocks.append(current); current = [line]
        else:
            current.append(line)
if current:
    blocks.append(current)
n = (len(blocks) + chunk_size - 1) // chunk_size
for i in range(n):
    out = f"{prefix}{i:04d}.qv"
    with open(out, "w") as f:
        for b in blocks[i*chunk_size:(i+1)*chunk_size]:
            f.writelines(b)
    print(out)
PYEOF
}

echo "================ $NAME  @ $(date '+%Y-%m-%d %H:%M:%S') ================"
echo "target=$TARGET  hotspots=$HOTSPOTS  loops=$LOOPS  n=$NUM_DESIGNS  chunk=$CHUNK_SIZE"

# ---- step 1: RFdiffusion (chunked) -----------------------------------------
# NOTE: gated by per-chunk count, NOT a single .step1.done flag -- if NUM_DESIGNS
# grows between runs, a stale whole-step flag would silently skip generating the
# extra backbones forever. Always recompute how many chunks are *currently*
# required and only skip the ones already done.
N_CHUNKS=$(( (NUM_DESIGNS + CHUNK_SIZE - 1) / CHUNK_SIZE ))
LAST_SIZE=$(( NUM_DESIGNS - (N_CHUNKS - 1) * CHUNK_SIZE ))
N_CHUNK_DONE=$(ls "$CHUNKS"/.1_bb_*.done 2>/dev/null | wc -l | tr -d ' ')
if [ -f "$OUTDIR/.step1.done" ] && [ "$N_CHUNK_DONE" -ge "$N_CHUNKS" ]; then
    _skip 1
else
    _t "[1/5] RFdiffusion ($NUM_DESIGNS backbones, chunk=$CHUNK_SIZE)"
    NEW_WORK=0
    for i in $(seq 0 $((N_CHUNKS - 1))); do
        IDX=$(printf '%04d' $i)
        CHUNK_QV="$CHUNKS/1_bb_${IDX}.qv"
        CHUNK_DONE="$CHUNKS/.1_bb_${IDX}.done"
        if [ -f "$CHUNK_DONE" ]; then
            echo "  [chunk $IDX] already done, skipping"
            continue
        fi
        NEW_WORK=1
        rm -f "$CHUNK_QV"
        # last chunk may be smaller
        THIS_N=$CHUNK_SIZE
        if [ $i -eq $((N_CHUNKS - 1)) ]; then THIS_N=$LAST_SIZE; fi
        echo "  [chunk $IDX] generating $THIS_N backbones..."
        uv run rfdiffusion \
            --target "$TARGET" --framework "$FRAMEWORK" --output-quiver "$CHUNK_QV" \
            --num-designs "$THIS_N" --design-loops "$LOOPS" --hotspots "$HOTSPOTS"
        touch "$CHUNK_DONE"
    done
    if [ "$NEW_WORK" = "1" ] || [ ! -f "$BB" ]; then
        rm -f "$BB"
        # NOTE: glob must match ONLY the real chunk files (1_bb_0000.qv, ...),
        # NOT rfdiffusion's own trajectory companions written into the same
        # dir (1_bb_0000_pX0_traj.qv, 1_bb_0000_Xt-1_traj.qv) -- those are
        # noisy, partially-denoised intermediate states, not real backbones,
        # and a looser glob would silently merge them in as if they were.
        uv run python scripts/biosensor/merge_quivers.py \
            "$CHUNKS"/1_bb_[0-9][0-9][0-9][0-9].qv --output "$BB" --overwrite
    fi
    _done 1
fi

# ---- step 2: geometry filter (GPU-free, fast — single pass) ----------------
# Always re-run: it's cheap (CPU-only) and $BB can grow between runs if
# NUM_DESIGNS increased, so a stale "done" flag here would silently leave
# $FILT built from only the old, smaller backbone set.
_t "[2/5] Geometry filter (drop broken / undocked)"
rm -f "$FILT"
uv run python scripts/biosensor/filter_backbones.py \
    --input "$BB" --output "$FILT" --report "$OUTDIR/filter_report.csv" \
    --break-cutoff "$BREAK_CUTOFF" --contact-cutoff "$CONTACT_CUTOFF" --overwrite
_done 2

# stop cleanly if nothing survived
N_FILT=$(grep -c '^QV_TAG' "$FILT" 2>/dev/null || true); N_FILT=${N_FILT:-0}
echo "  ($N_FILT backbones passed the geometry filter)"
if [ "$N_FILT" -eq 0 ]; then
    echo "WARNING: 0 backbones passed for $NAME (poor hotspot/dock?). Skipping steps 3-5."
    exit 0
fi

# ---- step 3: ProteinMPNN (chunked) -----------------------------------------
# Re-split whenever $FILT's count changed (NUM_DESIGNS growth => more survivors
# than last time) instead of trusting a one-shot ".3_split.done" flag. Since
# $FILT is append-only across re-runs (step 2 preserves input order), existing
# chunk files stay byte-identical after a re-split, so their GPU .done markers
# below remain valid -- only the new trailing chunks actually get (re)computed.
N_FILT_NOW=$(grep -c '^QV_TAG' "$FILT" 2>/dev/null || true); N_FILT_NOW=${N_FILT_NOW:-0}
N_FILT_SPLIT=$(cat "$CHUNKS/.3_split.count" 2>/dev/null || echo -1)
N_CHUNK3_DONE=$(ls "$CHUNKS"/.3_*.done 2>/dev/null | grep -v split | wc -l | tr -d ' ')
N_CHUNK3_NEEDED=$(( (N_FILT_NOW + CHUNK_SIZE - 1) / CHUNK_SIZE ))
if [ -f "$OUTDIR/.step3.done" ] && [ "$N_FILT_NOW" = "$N_FILT_SPLIT" ] && [ "$N_CHUNK3_DONE" -ge "$N_CHUNK3_NEEDED" ]; then
    _skip 3
else
    _t "[3/5] ProteinMPNN ($SEQS_PER_STRUCT seqs/backbone, chunk=$CHUNK_SIZE)"
    if [ "$N_FILT_NOW" != "$N_FILT_SPLIT" ]; then
        rm -f "$CHUNKS"/3_in_*.qv
        _split_quiver "$FILT" "$CHUNKS/3_in_" "$CHUNK_SIZE" > /dev/null
        echo "$N_FILT_NOW" > "$CHUNKS/.3_split.count"
    fi
    NEW_WORK=0
    for CHUNK_IN in "$CHUNKS"/3_in_*.qv; do
        IDX="${CHUNK_IN##*/3_in_}"; IDX="${IDX%.qv}"
        CHUNK_OUT="$CHUNKS/3_out_${IDX}.qv"
        CHUNK_DONE="$CHUNKS/.3_${IDX}.done"
        if [ -f "$CHUNK_DONE" ]; then
            echo "  [chunk $IDX] already done, skipping"
            continue
        fi
        NEW_WORK=1
        rm -f "$CHUNK_OUT"
        echo "  [chunk $IDX] running ProteinMPNN..."
        uv run proteinmpnn \
            --input-quiver "$CHUNK_IN" --output-quiver "$CHUNK_OUT" \
            --loops H1,H2,H3 \
            --seqs-per-struct "$SEQS_PER_STRUCT" --temperature "$MPNN_TEMP"
        [ -s "$CHUNK_OUT" ] || { echo "ERROR: ProteinMPNN chunk $IDX produced empty output"; exit 1; }
        touch "$CHUNK_DONE"
    done
    if [ "$NEW_WORK" = "1" ] || [ ! -f "$MPNN" ]; then
        rm -f "$MPNN"
        uv run python scripts/biosensor/merge_quivers.py \
            "$CHUNKS"/3_out_*.qv --output "$MPNN" --overwrite
    fi
    _done 3
fi

# ---- step 4: RF2 (chunked) -------------------------------------------------
# Same growth-aware gating as step 3 (see comment above).
N_MPNN_NOW=$(grep -c '^QV_TAG' "$MPNN" 2>/dev/null || true); N_MPNN_NOW=${N_MPNN_NOW:-0}
N_MPNN_SPLIT=$(cat "$CHUNKS/.4_split.count" 2>/dev/null || echo -1)
N_CHUNK4_DONE=$(ls "$CHUNKS"/.4_*.done 2>/dev/null | grep -v split | wc -l | tr -d ' ')
N_CHUNK4_NEEDED=$(( (N_MPNN_NOW + CHUNK_SIZE - 1) / CHUNK_SIZE ))
if [ -f "$OUTDIR/.step4.done" ] && [ "$N_MPNN_NOW" = "$N_MPNN_SPLIT" ] && [ "$N_CHUNK4_DONE" -ge "$N_CHUNK4_NEEDED" ]; then
    _skip 4
else
    _t "[4/5] RF2 ($RF2_RECYCLES recycles, chunk=$CHUNK_SIZE)"
    if [ "$N_MPNN_NOW" != "$N_MPNN_SPLIT" ]; then
        rm -f "$CHUNKS"/4_in_*.qv
        _split_quiver "$MPNN" "$CHUNKS/4_in_" "$CHUNK_SIZE" > /dev/null
        echo "$N_MPNN_NOW" > "$CHUNKS/.4_split.count"
    fi
    NEW_WORK=0
    for CHUNK_IN in "$CHUNKS"/4_in_*.qv; do
        IDX="${CHUNK_IN##*/4_in_}"; IDX="${IDX%.qv}"
        CHUNK_OUT="$CHUNKS/4_out_${IDX}.qv"
        CHUNK_DONE="$CHUNKS/.4_${IDX}.done"
        if [ -f "$CHUNK_DONE" ]; then
            echo "  [chunk $IDX] already done, skipping"
            continue
        fi
        NEW_WORK=1
        rm -f "$CHUNK_OUT"
        echo "  [chunk $IDX] running RF2..."
        uv run rf2 \
            --input-quiver "$CHUNK_IN" --output-quiver "$CHUNK_OUT" \
            --num-recycles "$RF2_RECYCLES" --hotspot-show-prop "$RF2_HOTSPOT_SHOW"
        [ -s "$CHUNK_OUT" ] || { echo "ERROR: RF2 chunk $IDX produced empty output"; exit 1; }
        touch "$CHUNK_DONE"
    done
    if [ "$NEW_WORK" = "1" ] || [ ! -f "$RF2" ]; then
        rm -f "$RF2"
        uv run python scripts/biosensor/merge_quivers.py \
            "$CHUNKS"/4_out_*.qv --output "$RF2" --overwrite
    fi
    _done 4
fi

# ---- step 5: select + rank (GPU-free) --------------------------------------
# Always re-run: $RF2 can grow between runs (NUM_DESIGNS increases), and a
# stale "done" flag here would silently leave 5_selection.csv/winners built
# from only the old, smaller RF2 output.
_t "[5/5] Select + rank (pAE<$PAE_CUTOFF, RMSD<$RMSD_CUTOFF, lDDT>=$LDDT_CUTOFF, dG<$DG_CUTOFF)"
uv run python scripts/biosensor/select_designs.py \
    --input "$RF2" --outdir "$OUTDIR" \
    --pae-cutoff "$PAE_CUTOFF" --rmsd-cutoff "$RMSD_CUTOFF" \
    --lddt-cutoff "$LDDT_CUTOFF" --dg-cutoff "$DG_CUTOFF" \
    --top "$TOP_N"
_done 5

echo ""
echo "DONE ($NAME) in $((SECONDS))s total."
echo "  ranked table : $OUTDIR/5_selection.csv"
echo "  winners      : $OUTDIR/winners/"
echo "  log          : $LOG"
