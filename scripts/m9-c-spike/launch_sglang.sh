#!/usr/bin/env bash
# m9-c-spike Phase K-β SGLang launch (CS-1 launch v5).
#
# Usage from WSL2:
#   bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-spike/launch_sglang.sh 2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs/sglang.log
set -euo pipefail

cd /root/erre-sandbox
source .venv/bin/activate

export HF_HOME=/root/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

echo "[launch_sglang] HF_HOME=${HF_HOME}"
echo "[launch_sglang] python=$(which python)"
echo "[launch_sglang] starting at $(date -Iseconds)"

exec python -m sglang.launch_server \
    --model Qwen/Qwen3-8B \
    --enable-lora \
    --max-loras-per-batch 3 \
    --max-lora-rank 8 \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loaded-loras 3 \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --port 30000 \
    --host 127.0.0.1
