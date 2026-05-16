#!/bin/bash
# WSL CUDA training launcher for retrain v2 kant_r8_v2.
# Runs under WSL2 Ubuntu-22.04 with /root/erre-sandbox/.venv (torch 2.9.1+cu128).
# Source from /mnt/c/ERRE-Sand_Box/src (latest main with WeightedTrainer).
set -e

REPO=/mnt/c/ERRE-Sand_Box
STEERING="${REPO}/.steering/20260515-m9-c-adopt-retrain-v2-verdict"
OUTPUT_DIR="${REPO}/data/lora/m9-c-adopt-v2/kant_r8_v2"

cd "${REPO}"
PYTHONPATH="${REPO}/src" nohup /root/erre-sandbox/.venv/bin/python \
    -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob "${REPO}/data/eval/golden/kant_*.duckdb" \
    --output-dir "${OUTPUT_DIR}/" \
    --rank 8 --max-steps 4000 --weighted -v \
    > "${STEERING}/training-wsl.log" 2>&1 &
TRAIN_PID=$!
echo "${TRAIN_PID}" > "${STEERING}/training-wsl.pid"
echo "WSL PID: ${TRAIN_PID}"
sleep 2
ps -p "${TRAIN_PID}" -o pid,etime,stat,cmd 2>&1 | head -3 || echo "process not visible from this shell"
