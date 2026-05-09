#!/usr/bin/env bash
# K-α Step 2 — SGLang launch with --enable-lora (CS-1).
#
# Run from WSL2:
#   bash /mnt/c/ERRE-Sand_Box/scratch_kalpha/step2_launch.sh 2>&1 | tee /tmp/sglang_launch.log
#
# Uses Windows-side HF cache (~/.cache/huggingface on /mnt/c) so the 15 GB
# Qwen3-8B snapshot does not have to be re-downloaded into the WSL2 native FS.

set -euo pipefail

export HF_HOME=/mnt/c/Users/johnd/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export TRANSFORMERS_VERBOSITY=info

# Required by deep_gemm (transitive dep of sglang>=0.5) — JIT compiles
# kernels for the GPU compute capability via nvcc. Without CUDA_HOME pointing
# at a CUDA toolkit (>=12.9 for sm_120 / Blackwell consumer), import-time
# AssertionError fires inside deep_gemm/__init__.py:_find_cuda_home.
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

cd /root/erre-sandbox

echo "[step2] HF_HOME=${HF_HOME}"
echo "[step2] launching SGLang at $(date -Iseconds)"

# CS-1 launch args (verbatim from k-alpha-handoff-prompt.md / decisions.md)
exec uv run --extra inference python -m sglang.launch_server \
  --model qwen/Qwen3-8B \
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
