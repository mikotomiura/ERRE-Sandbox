#!/usr/bin/env bash
# ECL B — bank golden mock construction run (Issue 005, mock-only, D-10).
# Ollama-free throughout: no live Ollama, no real embedding — every chat() call
# is served by a deterministic in-process mock. Writes/commits artifacts/.
# ADR: .steering/20260707-m13-b-impl-design/design-final.md (FROZEN §I4/§I5).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_bank_capture.py --capture \
  --out-dir experiments/20260708-m13-b-bank/artifacts
