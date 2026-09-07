# M13 society live-closure Issue 007 — Ollama-free replay-verify (1 command
# reproduction). Verifies the COMMITTED bytes of a bundle: Plane G
# (unmodified run_society_loop replay) + request conformance + fixed
# constructor fingerprint + the 3 side annotations. Opens no connection,
# spends nothing, regardless of -Real.
#
#   .\repro.ps1              # the committed Ollama-free rehearsal bundle
#   .\repro.ps1 -Real        # the sealed real bundle (absent until a future
#                             # ratified session produces one; this script
#                             # never causes that run itself)
[CmdletBinding()]
param([switch]$Real)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$env:PYTHONUTF8 = "1"
if ($Real) {
    python scripts/m13_society_live_capture.py --verify --real
} else {
    python scripts/m13_society_live_capture.py --verify
}
