#!/bin/bash
# Multi-turn pilot full capture — m9-c-adopt-pilot-multiturn investigation
# 6 LoRA-on shard (rank 4/8/16 × run 0/1) + 2 no-LoRA SGLang control shard.
# Total focal ≈ 2400 turn @ ~1.3 focal/s avg ≈ ~30-90 min wall (G-GEAR).
set -e

SGLANG=http://127.0.0.1:30000
PERSONA=kant
TURN_COUNT=300
CYCLE_COUNT=6
MULTI_TURN_MAX=6
PILOT_DIR=data/eval/m9-c-adopt-tier-b-pilot-multiturn
LOGDIR=.steering/20260514-m9-c-adopt-pilot-multiturn/logs
mkdir -p "${PILOT_DIR}" "${LOGDIR}"
PYBIN=".venv/Scripts/python.exe"

OVERALL_START=$(date +%s)

# === LoRA-on ===
for rank in 4 8 16; do
  for run_idx in 0 1; do
    out="${PILOT_DIR}/${PERSONA}_r${rank}_run${run_idx}_stim.duckdb"
    if [ -f "${out}" ]; then
      echo "[skip] ${out} already exists"
      continue
    fi
    log="${LOGDIR}/${PERSONA}_r${rank}_run${run_idx}.log"
    echo "[start LoRA] rank=${rank} run=${run_idx} -> ${out}"
    cell_start=$(date +%s)
    "${PYBIN}" scripts/m9-c-adopt/tier_b_pilot.py \
      --persona "${PERSONA}" --rank "${rank}" --run-idx "${run_idx}" \
      --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
      --multi-turn-max "${MULTI_TURN_MAX}" \
      --sglang-host "${SGLANG}" \
      --output "${out}" \
      --log-level info > "${log}" 2>&1
    cell_end=$(date +%s)
    elapsed=$((cell_end - cell_start))
    echo "[done  LoRA] rank=${rank} run=${run_idx} elapsed=${elapsed}s out=${out}"
  done
done

# === no-LoRA SGLang control (HIGH-1) ===
for run_idx in 0 1; do
  out="${PILOT_DIR}/${PERSONA}_nolora_run${run_idx}_stim.duckdb"
  if [ -f "${out}" ]; then
    echo "[skip] ${out} already exists"
    continue
  fi
  log="${LOGDIR}/${PERSONA}_nolora_run${run_idx}.log"
  echo "[start nolora] run=${run_idx} -> ${out}"
  cell_start=$(date +%s)
  "${PYBIN}" scripts/m9-c-adopt/tier_b_pilot.py \
    --persona "${PERSONA}" --rank 0 --run-idx "${run_idx}" --no-lora-control \
    --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
    --multi-turn-max "${MULTI_TURN_MAX}" \
    --sglang-host "${SGLANG}" \
    --output "${out}" \
    --log-level info > "${log}" 2>&1
  cell_end=$(date +%s)
  elapsed=$((cell_end - cell_start))
  echo "[done  nolora] run=${run_idx} elapsed=${elapsed}s out=${out}"
done

OVERALL_END=$(date +%s)
echo "[overall] total elapsed=$((OVERALL_END - OVERALL_START))s"
