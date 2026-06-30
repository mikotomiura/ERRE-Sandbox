#!/usr/bin/env bash
# M13-ES4 Phase 0 — SGLang fp8 qwen3:8b base-model launch (no LoRA).
#
# Base-model variant of scripts/m9-c-spike/launch_sglang.sh: ES-4 generates with
# the frozen base decoding only (no adapters), so the LoRA flags are dropped. fp8
# + mem-fraction 0.85 + max-running-requests 1 are required on the 16 GB RTX 5060
# Ti (BF16 OOMs; see memory reference_qwen3_sglang_fp8_required).
#
# Usage from WSL2 (run as root; repo runs from /mnt/c via PYTHONPATH, GPU venv):
#   wsl -u root bash /mnt/c/ERRE-Sand_Box/scripts/es4/launch_sglang_es4.sh \
#     2>&1 | tee /mnt/c/ERRE-Sand_Box/experiments/20260630-es4-phase0/sglang.log
set -euo pipefail

cd /root/erre-sandbox
source .venv/bin/activate

export HF_HOME=/root/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

echo "[launch_sglang_es4] HF_HOME=${HF_HOME}"
echo "[launch_sglang_es4] python=$(which python)"
echo "[launch_sglang_es4] starting at $(date -Iseconds)"

# --attention-backend triton: the default flashinfer attention backend crashes
# (SIGQUIT in forward_batch_generation) on this Blackwell SM120 GPU (RTX 5060 Ti)
# under SGLang 0.5.10.post1; triton generates correctly (decisions.md DA-PH0-7).
exec python -m sglang.launch_server \
    --model Qwen/Qwen3-8B \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --attention-backend triton \
    --port 30000 \
    --host 127.0.0.1
