#!/bin/bash
# Launch SGLang server for Phase B 第 4 セッション ICC / Burrows / Vendi consumers.
# DB8 runbook §2 launch v5 with --max-lora-rank 16.
set -e
LOG=/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/sglang_icc.log

cd /root/erre-sandbox
exec /root/erre-sandbox/.venv/bin/python -m sglang.launch_server \
  --model-path Qwen/Qwen3-8B \
  --quantization fp8 \
  --enable-lora \
  --lora-target-modules q_proj k_proj v_proj o_proj \
  --max-loras-per-batch 3 \
  --max-lora-rank 16 \
  --max-loaded-loras 3 \
  --mem-fraction-static 0.85 \
  --max-total-tokens 2048 \
  --disable-cuda-graph \
  --max-running-requests 1 \
  --port 30000 \
  > "${LOG}" 2>&1
