# aha Phase 4b sealed live run (human-gated, separate session) — real qwen3:8b,
# λ↔two-phase knob ACTIVE (TwoPhaseKnob injected, deep_work=EVALUATION seed).
# Requires a live Ollama with qwen3:8b pulled. Writes/commits artifacts/.
# ADR: .steering/20260717-aha-phase4b-construction-validation-live/design-final.md (FROZEN §5).
# real spend — only run after user spend ratify.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

python scripts/aha_phase4b_two_phase_live_capture.py --capture `
  --out-dir experiments/20260717-aha-phase4b-construction-validation-live/artifacts `
  --n-cognition-ticks 32 `
  --qwen3-model-digest "$($env:QWEN3_DIGEST ?? 'unknown')" `
  --ollama-version "$($env:OLLAMA_VERSION ?? 'unknown')" `
  --vram-gb "$($env:VRAM_GB ?? '0')" `
  --uv-lock-sha256 "$($env:UV_LOCK_SHA256 ?? 'unknown')"
