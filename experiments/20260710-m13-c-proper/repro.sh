#!/usr/bin/env bash
# M13 C-proper Ollama-free replay-verify + frozen scorer → verdict.json.
# One-command reproduction of a committed artifact bundle. No live Ollama needed:
# replays the committed bank records (inner_invocations==0, byte-identical
# re-render) and applies the FROZEN C-proper scorer (§CB4.4 verdict, one-shot,
# forking-paths seal). Run on both Windows (bake) and WSL (byte-一致 check).
# ADR: .steering/20260710-m13-c-proper/design-final.md §S8 (seal / determinism)
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_bank_cproper_capture.py --verify \
  --artifact-dir experiments/20260710-m13-c-proper/artifacts
