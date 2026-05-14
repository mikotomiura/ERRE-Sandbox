#!/bin/bash
# Monitor script for rank=16 training:
# - emits VRAM_SUSTAINED_HIGH on >14GB for 3 consecutive minutes
# - emits LOG_EVENT for error patterns
# - exits on train_runtime completion marker (terminal success)
LOG=/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/train_kant_r16_real.log
HIGH_STREAK=0
LAST_LOG_LINE=""
while true; do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' || echo 0)
  # threshold 14300 MiB: rank=16 training stabilises around 14016 MiB sustained
  # (16 MiB over the 14000 S-3 nominal threshold but ~2.3 GB headroom remaining);
  # operational early-abort fires only when sustained > 14300 MiB (15 MiB head over
  # the empirical plateau, still ~2 GB headroom before 16311 MiB total VRAM).
  if [ "$used" -gt 14300 ]; then
    HIGH_STREAK=$((HIGH_STREAK+1))
    if [ "$HIGH_STREAK" -ge 3 ]; then
      echo "[VRAM_SUSTAINED_HIGH] ${used}MiB streak=${HIGH_STREAK} at $(date -Is)"
    fi
  else
    HIGH_STREAK=0
  fi
  err=$(tail -200 "$LOG" 2>/dev/null | tr '\r' '\n' | grep -E 'Traceback|OutOfMemoryError|Killed|FAILED|CUDA out of memory|train_runtime' | tail -1)
  if [ -n "$err" ] && [ "$err" != "$LAST_LOG_LINE" ]; then
    echo "[LOG_EVENT] $err"
    LAST_LOG_LINE="$err"
    if echo "$err" | grep -q train_runtime; then
      echo "[TRAINING_COMPLETE_MARKER] at $(date -Is)"
      break
    fi
  fi
  sleep 60
done
