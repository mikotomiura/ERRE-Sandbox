# M13 live-loop I7 sealed live run (human-gated, separate session) — real qwen3:8b
# action-LLM + real nomic-embed-text embedding, two-phase knob ACTIVE, bounded
# scripted perturbations injected via InboundSink (no live Godot client).
#
# ADR: .steering/20260724-m13-live-loop-closure/design-final.md (FROZEN §5 Issue 007)
# Session: .steering/20260904-m13-live-loop-i7-real-run/
#
# REAL SPEND — run only after the user has explicitly ratified the spend.
# --confirm-spend is mandatory; without it the harness exits 2 without opening
# any connection.
#
# Requires a live Ollama with `qwen3:8b` and `nomic-embed-text` pulled.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$env:PYTHONUTF8 = "1"

python scripts/m13_live_loop_capture.py --capture --real --confirm-spend `
  --out-dir experiments/20260904-m13-live-loop-live/artifacts `
  --n-cognition-ticks 32 `
  --physics-ticks-per-cognition 20 `
  --qwen3-model-digest "$($env:QWEN3_DIGEST ?? 'unknown')" `
  --ollama-version "$($env:OLLAMA_VERSION ?? 'unknown')" `
  --vram-gb "$($env:VRAM_GB ?? '0')" `
  --uv-lock-sha256 "$($env:UV_LOCK_SHA256 ?? 'unknown')"
