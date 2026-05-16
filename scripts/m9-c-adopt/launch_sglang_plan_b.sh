#!/usr/bin/env bash
# m9-c-adopt Plan B verdict — SGLang launch with kant_r8v3 LoRA adapter.
#
# K-α launch v5 + Plan B retrain best checkpoint (step 1500).
# See .steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md DR-4 for
# the Blackwell SM120 piecewise-cuda-graph workaround.
#
# Usage from WSL2 (background):
#   nohup bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/launch_sglang_plan_b.sh \
#       > /mnt/c/ERRE-Sand_Box/.steering/20260516-m9-c-adopt-plan-b-eval-gen/sglang.log 2>&1 &
#
# Stop with:
#   pkill -f 'sglang.launch_server.*kant_r8v3'

set -euo pipefail

cd /root/erre-sandbox
source .venv/bin/activate

export HF_HOME=/root/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONUTF8=1
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

echo "[launch_sglang_plan_b] HF_HOME=${HF_HOME}"
echo "[launch_sglang_plan_b] python=$(which python)"
echo "[launch_sglang_plan_b] starting at $(date -Iseconds)"

exec python -m sglang.launch_server \
    --model Qwen/Qwen3-8B \
    --enable-lora \
    --max-loras-per-batch 1 \
    --max-lora-rank 8 \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loaded-loras 1 \
    --lora-paths "kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500" \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --disable-piecewise-cuda-graph \
    --host 0.0.0.0 \
    --port 30000
