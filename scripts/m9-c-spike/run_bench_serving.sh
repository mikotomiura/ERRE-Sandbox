#!/usr/bin/env bash
# SGLang bench_serving N=3 throughput — CS-7 protocol.
#
# Runs three baselines against a running SGLang server (CS-1 launch v5):
#   1. no_lora       — base model only, `--enable-lora` flag absent from launch
#   2. single_lora   — Kant real adapter, single-LoRA workload
#   3. multi_lora_3  — Kant + 2 mock pinned adapters, N=3 multi-LoRA workload
#
# Output goes to ``data/eval/spike/m9-c-spike-bench/`` as JSONL records.
#
# CS-7 4 trigger evaluation (downstream tool, not this script):
#   * p95 e2e > 2x single-LoRA baseline
#   * output tok/s < 70% baseline
#   * adapter-misrouting (Kant prompt → other adapter response)
#   * request timeout (any single occurrence)
#
# Usage (WSL2):
#   bash scripts/m9-c-spike/run_bench_serving.sh
#
# Pre-conditions:
#   * SGLang 0.5.10.post1 running on localhost:30000 with --enable-lora
#   * Kant adapter at /root/erre-sandbox/checkpoints/kant_r8_real/
#   * mock adapters at /root/erre-sandbox/checkpoints/mock_{nietzsche,rikyu}_r8/ if
#     N=3 multi-LoRA condition runs
set -euo pipefail

BENCH_OUT_DIR="${BENCH_OUT_DIR:-/mnt/c/ERRE-Sand_Box/data/eval/spike/m9-c-spike-bench}"
SERVER_URL="${SERVER_URL:-http://localhost:30000}"
ADAPTER_KANT="${ADAPTER_KANT:-/root/erre-sandbox/checkpoints/kant_r8_real}"
NUM_PROMPTS="${NUM_PROMPTS:-32}"
SEED="${SEED:-0}"

mkdir -p "${BENCH_OUT_DIR}"

# Helper: probe server health
wait_for_health() {
    local url="$1"
    local timeout="${2:-60}"
    local elapsed=0
    until curl -sf "${url}/health" > /dev/null 2>&1; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [ "$elapsed" -ge "$timeout" ]; then
            echo "ERROR: SGLang server at ${url} not healthy after ${timeout}s" >&2
            return 1
        fi
    done
}

wait_for_health "${SERVER_URL}"

# Condition 1 — single_lora (Kant only)
curl -sf -X POST "${SERVER_URL}/unload_lora_adapter" \
    -H "Content-Type: application/json" \
    -d '{"lora_name": "kant_r8_real"}' || true
curl -sf -X POST "${SERVER_URL}/load_lora_adapter" \
    -H "Content-Type: application/json" \
    -d "{\"lora_name\": \"kant_r8_real\", \"lora_path\": \"${ADAPTER_KANT}\"}"

python -m sglang.bench_serving \
    --backend sglang \
    --host "$(echo "${SERVER_URL}" | sed -E 's#https?://([^:/]+).*#\1#')" \
    --port "$(echo "${SERVER_URL}" | sed -E 's#.*:([0-9]+).*#\1#')" \
    --num-prompts "${NUM_PROMPTS}" \
    --random-input-len 256 \
    --random-output-len 256 \
    --seed "${SEED}" \
    --dataset-name random \
    --lora-name kant_r8_real \
    --output-file "${BENCH_OUT_DIR}/single_lora.jsonl"

# Condition 2 — no_lora (base only, requires the server to be re-launched
# without --enable-lora; this script emits a marker the operator must
# rotate manually because the launch flags cannot be changed at runtime).
echo "INFO: no_lora condition requires re-launching SGLang without --enable-lora."
echo "INFO: Operator: stop the current server, relaunch without --enable-lora,"
echo "INFO:           then re-run this script with COND=no_lora to capture it."

# Condition 3 — multi_lora_3 (Kant + 2 mocks). Mocks must be built via
# tools/spike/build_mock_lora.py first; the script does not auto-create
# them because that requires the [training] extras and CS-9 metadata
# already lives in tools/spike/build_mock_lora.py.
echo "INFO: multi_lora_3 condition requires 3 adapters pinned on the server."
echo "INFO:           kant_r8_real + mock_nietzsche_r8 + mock_rikyu_r8."

echo "DONE: single_lora condition captured to ${BENCH_OUT_DIR}/single_lora.jsonl"
