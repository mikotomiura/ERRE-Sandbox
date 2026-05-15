#!/bin/bash
# WSL-side SGLang launcher for retrain v2 verdict. Runs inside WSL.
# Writes PID to /mnt/c/.../sglang.pid and logs to /mnt/c/.../sglang.log.
set -e

TASK_DIR=/mnt/c/ERRE-Sand_Box/.steering/20260515-m9-c-adopt-retrain-v2-verdict

cd /root/erre-sandbox
nohup /root/erre-sandbox/.venv/bin/python -m sglang.launch_server \
    --model-path Qwen/Qwen3-8B \
    --quantization fp8 \
    --enable-lora \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loras-per-batch 1 \
    --max-lora-rank 8 \
    --max-loaded-loras 1 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --disable-cuda-graph \
    --max-running-requests 1 \
    --port 30000 \
    > "${TASK_DIR}/sglang.log" 2>&1 &
PID=$!
echo "${PID}" > "${TASK_DIR}/sglang.pid"
echo "SGLang launched: PID ${PID}"
