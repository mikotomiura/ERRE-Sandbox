#!/bin/bash
# Phase B training kicker — writes to /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/
# Args: $1 = rank (4|8|16|32), $2 = adapter output dir name (e.g. kant_r4_real)
set -e

RANK="${1:-4}"
ADAPTER_NAME="${2:-kant_r${RANK}_real}"
LOG_DIR="/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs"
OUT_DIR="/root/erre-sandbox/checkpoints/${ADAPTER_NAME}"
PID_FILE="${LOG_DIR}/${ADAPTER_NAME}.pid"
LOG_FILE="${LOG_DIR}/train_${ADAPTER_NAME}.log"

mkdir -p "${OUT_DIR}"
mkdir -p "${LOG_DIR}"

cd /mnt/c/ERRE-Sand_Box

nohup /root/erre-sandbox/.venv/bin/python -m erre_sandbox.training.train_kant_lora \
  --persona kant \
  --rank "${RANK}" \
  --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb' \
  --output-dir "${OUT_DIR}" \
  -v \
  > "${LOG_FILE}" 2>&1 < /dev/null &

TRAIN_PID=$!
disown
echo "${TRAIN_PID}" > "${PID_FILE}"
echo "PID=${TRAIN_PID}"
echo "LOG=${LOG_FILE}"
echo "OUT=${OUT_DIR}"
echo "PID_FILE=${PID_FILE}"
