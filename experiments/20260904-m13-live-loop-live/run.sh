#!/usr/bin/env bash
# M13 live-loop I7 sealed live run (human-gated) — WSL2 / Linux side.
# REAL SPEND — run only after the user has explicitly ratified the spend.
# See run.ps1 for the full note; --confirm-spend is mandatory.
set -euo pipefail
cd "$(dirname "$0")/../.."

export PYTHONUTF8=1

python scripts/m13_live_loop_capture.py --capture --real --confirm-spend \
  --out-dir experiments/20260904-m13-live-loop-live/artifacts \
  --n-cognition-ticks 32 \
  --physics-ticks-per-cognition 20 \
  --qwen3-model-digest "${QWEN3_DIGEST:-unknown}" \
  --ollama-version "${OLLAMA_VERSION:-unknown}" \
  --vram-gb "${VRAM_GB:-0}" \
  --uv-lock-sha256 "${UV_LOCK_SHA256:-unknown}"
