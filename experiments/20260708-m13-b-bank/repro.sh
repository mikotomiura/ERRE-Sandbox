#!/usr/bin/env bash
# ECL B — bank golden Ollama-free replay-verify (Issue 005 I5-G2/I5-G3/I5-G5).
# One-command reproduction of the committed bank-golden artifact bundle. No
# live Ollama needed — construction, not measurement (§I4/§I5, D-10 mock-only).
# ADR: .steering/20260707-m13-b-impl-design/design-final.md (FROZEN).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_bank_capture.py --verify \
  --artifact-dir experiments/20260708-m13-b-bank/artifacts
