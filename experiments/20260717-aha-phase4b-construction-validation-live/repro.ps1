# aha Phase 4b Ollama-free replay-verify (V2/V3a/V3b) + firing annotation side file.
# One-command reproduction of a committed artifact bundle. No live Ollama needed.
# ADR: .steering/20260717-aha-phase4b-construction-validation-live/design-final.md (FROZEN §5).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

python scripts/aha_phase4b_two_phase_live_capture.py --verify `
  --artifact-dir experiments/20260717-aha-phase4b-construction-validation-live/artifacts
