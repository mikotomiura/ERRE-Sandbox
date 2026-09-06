# M13 live-loop I7 — Ollama-free replay-verify (1 command reproduction).
# Verifies the COMMITTED bytes of a bundle: Plane G (unmodified
# run_two_phase_capture) + Plane L (closure-root re-drive) + both side
# annotations. Opens no connection, spends nothing.
#
#   .\repro.ps1              # the committed Ollama-free rehearsal bundle
#   .\repro.ps1 -Real        # the sealed real bundle (after the ratified run)
[CmdletBinding()]
param([switch]$Real)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$env:PYTHONUTF8 = "1"
$dir = if ($Real) {
  "experiments/20260904-m13-live-loop-live/artifacts"
} else {
  "experiments/20260904-m13-live-loop-live/rehearsal"
}
python scripts/m13_live_loop_capture.py --verify --artifact-dir $dir
