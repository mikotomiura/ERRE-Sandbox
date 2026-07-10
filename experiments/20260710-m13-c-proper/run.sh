#!/usr/bin/env bash
# M13 C-proper powered sealed run (human-gated, separate session) — real qwen3:8b,
# reads the FROZEN B bank apparatus, provenance=mock / M-loop=live (M=300 × K=8,
# think=False). Writes/commits artifacts/. THE R-BUDGET=1 SPEND — run only after
# the scorer is frozen (committed) and the user has ratified the spend.
# ADR: .steering/20260708-m13-c-design-bank/design-final.md §CB4 (pre-register)
#      .steering/20260710-m13-c-proper/design-final.md §S (scorer, FROZEN pre-run)
set -euo pipefail
cd "$(dirname "$0")/../.."

# M/K/seed are pinned to the pre-registered powered constants (M_MIN=300, K_MIN=8,
# seed=20260708) inside the CLI — there is no flag to make a sub-powered sealed run.
python scripts/ecl_bank_cproper_capture.py --capture \
  --out-dir experiments/20260710-m13-c-proper/artifacts \
  --qwen3-model-digest "${QWEN3_DIGEST:-unknown}" \
  --ollama-version "${OLLAMA_VERSION:-unknown}" \
  --vram-gb "${VRAM_GB:-0}" \
  --uv-lock-sha256 "${UV_LOCK_SHA256:-unknown}"
