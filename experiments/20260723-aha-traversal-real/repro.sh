#!/usr/bin/env bash
# M13 aha-substrate-embodiment traversal — I4 Ollama-free replay-verify (WSL
# cross-platform byte-parity leg, both Plane 1 channels). No live Ollama needed.
# ADR: .steering/20260723-m13-aha-substrate-embodiment/design-final.md (FROZEN).
#
# Only meaningful AFTER a real sealed run (run.ps1) has committed artifacts/ —
# see env.md "status" (currently BLOCKED, no artifacts/ committed yet).
set -euo pipefail
export PYTHONUTF8=1
cd "$(dirname "$0")/../.."

python scripts/aha_traversal_live_capture.py --verify --real \
  --golden-dir experiments/20260723-aha-traversal-real/artifacts
