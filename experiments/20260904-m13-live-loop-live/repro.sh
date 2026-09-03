#!/usr/bin/env bash
# M13 live-loop I7 — Ollama-free replay-verify (1 command reproduction).
# Verifies the COMMITTED bytes: Plane G + Plane L + both side annotations.
# Opens no connection, spends nothing. Used for the WSL side of the L3
# cross-platform byte check.
#
#   ./repro.sh              # the committed Ollama-free rehearsal bundle
#   ./repro.sh --real       # the sealed real bundle (after the ratified run)
set -euo pipefail
cd "$(dirname "$0")/../.."

export PYTHONUTF8=1
dir="experiments/20260904-m13-live-loop-live/rehearsal"
if [ "${1:-}" = "--real" ]; then
  dir="experiments/20260904-m13-live-loop-live/artifacts"
fi
python scripts/m13_live_loop_capture.py --verify --artifact-dir "$dir"
