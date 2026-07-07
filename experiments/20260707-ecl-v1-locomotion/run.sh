#!/usr/bin/env bash
# ECL v1 sealed live run (I3, human-gated, separate session) — real qwen3:8b,
# locomotion→sampling channel ACTIVE (seeded LocomotionState(lam=0.0)).
# Requires a live Ollama with qwen3:8b pulled. Writes/commits artifacts/ (I3).
# ADR: .steering/20260707-ecl-v1-adr/design-final.md (FROZEN §B/§E/§F).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_v1_live_capture.py --capture \
  --out-dir experiments/20260707-ecl-v1-locomotion/artifacts \
  --n-cognition-ticks 32 \
  --qwen3-model-digest "${QWEN3_DIGEST:-unknown}" \
  --ollama-version "${OLLAMA_VERSION:-unknown}" \
  --vram-gb "${VRAM_GB:-0}" \
  --uv-lock-sha256 "${UV_LOCK_SHA256:-unknown}"
