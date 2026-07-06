#!/usr/bin/env bash
# ECL v0 sealed live run (Issue 003) — first-contact capture on G-GEAR.
# Requires live Ollama (qwen3:8b). One-shot sealed run; artifacts/ is committed.
# Replay/CI reproduction is Ollama-free via repro.sh (D-4).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_v0_live_capture.py --capture \
  --run-id ecl-v0-live-capture --seed 0 \
  --n-cognition-ticks 32 --physics-ticks-per-cognition 20 \
  --qwen3-model-digest 500a1f067a9f7826 \
  --ollama-version 0.31.1 \
  --vram-gb 16 \
  --uv-lock-sha256 9cc70f9dc5d61f6c
