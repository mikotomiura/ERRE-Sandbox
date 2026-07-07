#!/usr/bin/env bash
# ECL v1 Ollama-free replay-verify (V2/V3a/V3b) + V4a/V4b channel-active annotation.
# One-command reproduction of a committed artifact bundle. No live Ollama needed.
# ADR: .steering/20260707-ecl-v1-adr/design-final.md (FROZEN §F, Codex MEDIUM-2).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_v1_live_capture.py --verify \
  --artifact-dir experiments/20260707-ecl-v1-locomotion/artifacts
