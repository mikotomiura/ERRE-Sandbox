# M13 aha-substrate-embodiment traversal — I4 Ollama-free replay-verify (both
# Plane 1 channels: LLM decisions.jsonl + embedding_record.jsonl) + firing /
# channel-exercise annotation side files. No live Ollama needed.
# ADR: .steering/20260723-m13-aha-substrate-embodiment/design-final.md (FROZEN).
#
# Only meaningful AFTER a real sealed run (run.ps1) has committed artifacts/ —
# until then this fails with a missing-file error, which is expected (no
# artifacts/ directory is committed here yet; see env.md "status").
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
Set-Location (Join-Path $PSScriptRoot "..\..")

python scripts/aha_traversal_live_capture.py --verify --real `
  --golden-dir experiments/20260723-aha-traversal-real/artifacts
