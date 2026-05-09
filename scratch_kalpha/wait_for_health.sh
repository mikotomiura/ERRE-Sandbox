#!/usr/bin/env bash
# Block until SGLang /health returns 200 or timeout.
#
# Run from WSL2:
#   bash /mnt/c/ERRE-Sand_Box/scratch_kalpha/wait_for_health.sh 600
set -euo pipefail
TIMEOUT=${1:-600}
echo "[health] waiting up to ${TIMEOUT}s for SGLang /health on http://127.0.0.1:30000"
START=$(date +%s)
while true; do
  if curl -fsS -m 2 http://127.0.0.1:30000/health >/dev/null 2>&1; then
    ELAPSED=$(($(date +%s) - START))
    echo "[health] HEALTHY after ${ELAPSED}s"
    nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu \
      --format=csv,noheader 2>/dev/null || true
    exit 0
  fi
  ELAPSED=$(($(date +%s) - START))
  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "[health] TIMEOUT after ${ELAPSED}s"
    exit 124
  fi
  sleep 3
done
