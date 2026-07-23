# M13 aha-substrate-embodiment traversal — I4 real qwen3 + real embedding sealed
# channel exercise (human-gated, separate session). Requires a live Ollama with
# qwen3:8b + nomic-embed-text pulled. Writes/commits artifacts/.
# ADR: .steering/20260723-m13-aha-substrate-embodiment/design-final.md (FROZEN).
#
# I4-G1 GATE (binding): do NOT run this until user spend ratify is obtained.
# This file is code-path scaffolding only — writing it is not permission to
# execute it. See env.md "status" for the current (BLOCKED) state.
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
Set-Location (Join-Path $PSScriptRoot "..\..")

python scripts/aha_traversal_live_capture.py --capture --real `
  --golden-dir experiments/20260723-aha-traversal-real/artifacts `
  --model qwen3:8b `
  --embed-model nomic-embed-text `
  --seed 0
