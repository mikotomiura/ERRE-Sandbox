#!/usr/bin/env bash
# aha Phase 4b Ollama-free replay-verify (WSL cross-platform byte-parity leg).
# One-command reproduction of a committed artifact bundle. No live Ollama needed.
# ADR: .steering/20260717-aha-phase4b-construction-validation-live/design-final.md (FROZEN §5).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/aha_phase4b_two_phase_live_capture.py --verify \
  --artifact-dir experiments/20260717-aha-phase4b-construction-validation-live/artifacts
