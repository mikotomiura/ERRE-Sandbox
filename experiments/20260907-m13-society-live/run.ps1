# M13 society live-closure Issue 007 sealed real run (human-gated, SEPARATE
# session) — real qwen3:8b action-LLM per agent (N=3: a_kant / a_nietzsche /
# a_rikyu) + real nomic-embed-text embedding, two-phase knob ACTIVE, the
# pre-registered 36-message bounded perturbation plan injected via
# InboundSink (no live Godot client).
#
# Issue: loop/20260906-m13-society-live-closure/issues/007.md
#
# HARD STOP (binding for Issue 007 itself): this script's real path is
# documented here for a FUTURE ratified session. Issue 007 never invokes it —
# no Ollama connection is opened, no GPU is touched, by this issue's own
# automation. Running it requires the user to have explicitly ratified the
# spend first (design-final.md grill G4 equivalent); even then the harness
# itself refuses without --confirm-spend, without pinned provenance, or
# against an existing sealed bundle (script-enforced, not merely documented —
# see tests/test_integration/test_m13_society_live_capture.py AC2-AC4).
#
# Windows PowerShell 5.1 compatible (no `??` / ternary — memory
# feedback_pre_push_ci_parity notes pwsh is not always present).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$env:PYTHONUTF8 = "1"

# Fail fast on unset provenance rather than sealing an unauditable artifact
# (I7 precedent H-2/L-1: a silent 'unknown' fallback would spend a real run
# and produce a bundle nobody could audit afterwards).
$required = @("QWEN3_DIGEST", "OLLAMA_VERSION", "VRAM_GB")
$missing = @()
foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrWhiteSpace($value)) { $missing += $name }
}
if ($missing.Count -gt 0) {
    Write-Host "ERROR: unset provenance environment variable(s): $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Set them before the sealed run, e.g.:" -ForegroundColor Yellow
    Write-Host '  $env:QWEN3_DIGEST  = (ollama show qwen3:8b --json | ConvertFrom-Json).digest'
    Write-Host '  $env:OLLAMA_VERSION = (ollama --version)'
    Write-Host '  $env:VRAM_GB = "16"'
    exit 2
}

# No --n-cognition-ticks / --physics-ticks-per-cognition / --seed / --agent-ids
# flags exist on this harness (AC7): the roster, horizon, seed and
# perturbation budget are frozen module constants and are deliberately NOT
# reachable from the CLI, so this script cannot silently drift off the
# pre-registration. --uv-lock-sha256 is also intentionally NOT passed: the
# harness derives it from this checkout's uv.lock.
python scripts/m13_society_live_capture.py --capture --real --confirm-spend `
  --out-dir experiments/20260907-m13-society-live/artifacts `
  --qwen3-model-digest $env:QWEN3_DIGEST `
  --ollama-version $env:OLLAMA_VERSION `
  --vram-gb $env:VRAM_GB
