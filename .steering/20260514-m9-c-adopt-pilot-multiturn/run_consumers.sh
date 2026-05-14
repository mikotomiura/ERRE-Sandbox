#!/bin/bash
# Multi-turn pilot consumer 実行 (Vendi semantic / Big5 ICC / Burrows Δ)
# Plus matched baseline downsampling (HIGH-2) + no-LoRA control consumers.
# Run AFTER run_pilot_multiturn.sh completes.
set -e

PYBIN=".venv/Scripts/python.exe"
PILOT_DIR=data/eval/m9-c-adopt-tier-b-pilot-multiturn
STEERING=.steering/20260514-m9-c-adopt-pilot-multiturn
HISTORICAL_GOLDEN=data/eval/golden
SGLANG=http://127.0.0.1:30000

mkdir -p "${STEERING}/logs"
OVERALL_START=$(date +%s)

# === Matched baseline (HIGH-2): historical baseline downsampled to 300 focal/shard ===
echo "[matched] vendi semantic"
"${PYBIN}" scripts/m9-c-adopt/compute_baseline_vendi.py \
  --persona kant --condition stimulus \
  --shards-glob "${HISTORICAL_GOLDEN}/kant_stimulus_run*.duckdb" \
  --kernel semantic --window-size 100 \
  --max-focal-per-shard 300 \
  --output "${STEERING}/tier-b-baseline-matched-kant-vendi-semantic.json" \
  > "${STEERING}/logs/baseline_matched_vendi.log" 2>&1

echo "[matched] burrows delta"
"${PYBIN}" scripts/m9-c-adopt/compute_burrows_delta.py \
  --persona kant \
  --shards-glob "${HISTORICAL_GOLDEN}/kant_stimulus_run*.duckdb" \
  --window-size 100 \
  --max-focal-per-shard 300 \
  --output "${STEERING}/tier-b-baseline-matched-kant-burrows.json" \
  > "${STEERING}/logs/baseline_matched_burrows.log" 2>&1

# === Multi-turn pilot LoRA-on (3 rank) ===
for r in 4 8 16; do
  shards="${PILOT_DIR}/kant_r${r}_run*_stim.duckdb"

  echo "[mt LoRA r=${r}] vendi semantic"
  "${PYBIN}" scripts/m9-c-adopt/compute_baseline_vendi.py \
    --persona kant --condition stimulus \
    --shards-glob "${shards}" \
    --kernel semantic --window-size 100 \
    --output "${STEERING}/tier-b-pilot-multiturn-kant-r${r}-vendi-semantic.json" \
    > "${STEERING}/logs/mt_lora_r${r}_vendi.log" 2>&1

  echo "[mt LoRA r=${r}] burrows delta"
  "${PYBIN}" scripts/m9-c-adopt/compute_burrows_delta.py \
    --persona kant \
    --shards-glob "${shards}" \
    --window-size 100 \
    --output "${STEERING}/tier-b-pilot-multiturn-kant-r${r}-burrows.json" \
    > "${STEERING}/logs/mt_lora_r${r}_burrows.log" 2>&1

  echo "[mt LoRA r=${r}] Big5 ICC (SGLang LoRA-on, T=0.7)"
  "${PYBIN}" scripts/m9-c-adopt/compute_big5_icc.py \
    --persona kant \
    --shards-glob "${shards}" \
    --responder sglang --sglang-host "${SGLANG}" \
    --sglang-adapter "kant_r${r}_real" --temperature 0.7 \
    --window-size 100 \
    --output "${STEERING}/tier-b-icc-multiturn-kant-r${r}.json" \
    > "${STEERING}/logs/mt_lora_r${r}_icc.log" 2>&1
done

# === No-LoRA SGLang control ===
nolora_shards="${PILOT_DIR}/kant_nolora_run*_stim.duckdb"
echo "[nolora] vendi semantic"
"${PYBIN}" scripts/m9-c-adopt/compute_baseline_vendi.py \
  --persona kant --condition stimulus \
  --shards-glob "${nolora_shards}" \
  --kernel semantic --window-size 100 \
  --output "${STEERING}/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json" \
  > "${STEERING}/logs/mt_nolora_vendi.log" 2>&1

echo "[nolora] burrows delta"
"${PYBIN}" scripts/m9-c-adopt/compute_burrows_delta.py \
  --persona kant \
  --shards-glob "${nolora_shards}" \
  --window-size 100 \
  --output "${STEERING}/tier-b-pilot-multiturn-kant-nolora-burrows.json" \
  > "${STEERING}/logs/mt_nolora_burrows.log" 2>&1

echo "[nolora] Big5 ICC (SGLang base, T=0.7)"
"${PYBIN}" scripts/m9-c-adopt/compute_big5_icc.py \
  --persona kant \
  --shards-glob "${nolora_shards}" \
  --responder sglang --sglang-host "${SGLANG}" \
  --sglang-adapter "Qwen/Qwen3-8B" --temperature 0.7 \
  --window-size 100 \
  --output "${STEERING}/tier-b-icc-multiturn-kant-nolora.json" \
  > "${STEERING}/logs/mt_nolora_icc.log" 2>&1

# === Final matrix renderer ===
echo "[matrix] da1_matrix_multiturn render"
"${PYBIN}" scripts/m9-c-adopt/da1_matrix_multiturn.py \
  --steering-historical .steering/20260513-m9-c-adopt \
  --steering-investigation "${STEERING}" \
  --output "${STEERING}/da1-matrix-multiturn-kant.json" \
  > "${STEERING}/da1-matrix-multiturn-kant.md" 2> "${STEERING}/logs/matrix.log"

OVERALL_END=$(date +%s)
echo "[overall] consumers + matrix total elapsed=$((OVERALL_END - OVERALL_START))s"
echo "Final verdict in ${STEERING}/da1-matrix-multiturn-kant.{json,md}"
