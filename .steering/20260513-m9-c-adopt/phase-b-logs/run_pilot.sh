#!/bin/bash
# Phase B Step 5c — full Tier B pilot kick: 3 rank × 2 run × 300 turn = 1800 turn.
# Runs serialized (single SGLang server, single rank per call) to keep
# adapter routing semantics simple and avoid concurrency / memory churn.
set -e

SGLANG=http://127.0.0.1:30000
PERSONA=kant
TURN_COUNT=300
CYCLE_COUNT=6
PILOT_DIR=/mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-tier-b-pilot
LOGDIR=/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/pilot
mkdir -p "${PILOT_DIR}" "${LOGDIR}"

OVERALL_START=$(date +%s)
for rank in 4 8 16; do
  for run_idx in 0 1; do
    out="${PILOT_DIR}/${PERSONA}_r${rank}_run${run_idx}_stim.duckdb"
    if [ -f "${out}" ]; then
      echo "[skip] ${out} already exists"
      continue
    fi
    log="${LOGDIR}/${PERSONA}_r${rank}_run${run_idx}.log"
    echo "[start] rank=${rank} run=${run_idx} -> ${out}"
    cell_start=$(date +%s)
    /root/erre-sandbox/.venv/bin/python /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/tier_b_pilot.py \
      --persona "${PERSONA}" --rank "${rank}" --run-idx "${run_idx}" \
      --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
      --sglang-host "${SGLANG}" \
      --output "${out}" \
      --log-level info > "${log}" 2>&1
    cell_end=$(date +%s)
    elapsed=$((cell_end - cell_start))
    echo "[done ] rank=${rank} run=${run_idx} elapsed=${elapsed}s out=${out}"
  done
done
OVERALL_END=$(date +%s)
echo "[overall] total elapsed=$((OVERALL_END - OVERALL_START))s"
