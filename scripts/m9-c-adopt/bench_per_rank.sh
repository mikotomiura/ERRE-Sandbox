#!/usr/bin/env bash
# Phase B Step 5e — per-rank single_lora benchmark on running SGLang server
# (CS-1 launch v6: --max-lora-rank 16, --max-loras-per-batch 3 --max-loaded-loras 3,
#  fp8 + --disable-cuda-graph + --max-running-requests 1).
#
# Captures `single_lora-r{4,8,16}` for the DA-1 throughput axis.
# `no_lora` baseline is the PR #163 K-β value (single_lora 34.64 tok/s,
# threshold 0.7x = 24.25 tok/s) — re-launching without --enable-lora is
# operationally heavy and outside this session's scope (handed off to
# Phase B 第 4 セッション if a fresh no_lora baseline is required).
#
# CS-7 4 trigger evaluation (downstream tool + Step 5f decision):
#   * p95 e2e > 2x baseline           → FIRE
#   * output tok/s < 24.25 tok/s      → FIRE (rank-specific)
#   * adapter-misrouting              → manual sanity (Step 4 multi_pin sanity)
#   * timeout (any)                   → FIRE
#
# Usage (WSL2):
#   bash scripts/m9-c-adopt/bench_per_rank.sh
set -euo pipefail

BENCH_OUT_DIR="${BENCH_OUT_DIR:-/mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-bench}"
SERVER_URL="${SERVER_URL:-http://localhost:30000}"
NUM_PROMPTS="${NUM_PROMPTS:-32}"
SEED="${SEED:-0}"
PYBIN="${PYBIN:-/root/erre-sandbox/.venv/bin/python}"

mkdir -p "${BENCH_OUT_DIR}"

# Health probe
elapsed=0
until curl -sf "${SERVER_URL}/health" > /dev/null 2>&1; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ "${elapsed}" -ge 60 ]; then
        echo "ERROR: SGLang at ${SERVER_URL} not healthy after 60s" >&2
        exit 1
    fi
done

HOST=$(echo "${SERVER_URL}" | sed -E 's#https?://([^:/]+).*#\1#')
PORT=$(echo "${SERVER_URL}" | sed -E 's#.*:([0-9]+).*#\1#')

for rank in 4 8 16; do
    name="kant_r${rank}_real"
    out="${BENCH_OUT_DIR}/single_lora-r${rank}.jsonl"
    if [ -f "${out}" ]; then
        echo "[skip] ${out} exists"
        continue
    fi
    echo "=== bench rank=${rank} adapter=${name} ==="
    "${PYBIN}" -m sglang.bench_serving \
        --backend sglang \
        --host "${HOST}" \
        --port "${PORT}" \
        --num-prompts "${NUM_PROMPTS}" \
        --random-input-len 256 \
        --random-output-len 256 \
        --seed "${SEED}" \
        --dataset-name random \
        --lora-name "${name}" \
        --output-file "${out}"
    echo "[done] rank=${rank} -> ${out}"
done

echo "=== summary (key metrics) ==="
for rank in 4 8 16; do
    out="${BENCH_OUT_DIR}/single_lora-r${rank}.jsonl"
    if [ -f "${out}" ]; then
        echo "--- rank=${rank} ---"
        # bench_serving emits a single JSON record; extract key fields
        "${PYBIN}" -c "
import json, sys, pathlib
data = pathlib.Path('${out}').read_text().strip().splitlines()
if not data: sys.exit(0)
r = json.loads(data[-1])
print(f'  output_throughput_tok_s = {r.get(\"output_throughput\", \"NA\"):.2f}')
print(f'  ttft_p50_ms             = {r.get(\"median_ttft_ms\", \"NA\"):.1f}')
print(f'  ttft_p99_ms             = {r.get(\"p99_ttft_ms\", \"NA\"):.1f}')
print(f'  e2e_p99_ms              = {r.get(\"p99_e2e_latency_ms\", \"NA\"):.1f}')
print(f'  itl_p99_ms              = {r.get(\"p99_itl_ms\", \"NA\"):.1f}')
print(f'  errors                  = {r.get(\"successful_requests\", \"NA\")}/{r.get(\"completed\", \"NA\")}')
"
    fi
done
