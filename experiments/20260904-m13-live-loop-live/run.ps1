# M13 live-loop I7 sealed live run (human-gated, separate session) — real qwen3:8b
# action-LLM + real nomic-embed-text embedding, two-phase knob ACTIVE, bounded
# scripted perturbations injected via InboundSink (no live Godot client).
#
# ADR: .steering/20260724-m13-live-loop-closure/design-final.md (FROZEN §5 Issue 007)
# Session: .steering/20260904-m13-live-loop-i7-real-run/
#
# REAL SPEND — run only after the user has explicitly ratified the spend.
# --confirm-spend is mandatory; without it the harness exits 2 without opening
# any connection. The harness also refuses a run whose provenance pins are
# missing, whose parameters differ from the pre-registration, or that would
# overwrite an existing sealed bundle.
#
# Requires a live Ollama with `qwen3:8b` and `nomic-embed-text` pulled.
#
# Windows PowerShell 5.1 compatible (no `??` / ternary — memory
# feedback_pre_push_ci_parity notes pwsh is not always present).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

$env:PYTHONUTF8 = "1"

# Fail fast on unset provenance rather than sealing an unauditable artifact
# (Codex H-2/L-1: the previous `?? 'unknown'` fallback would have spent a real
# run and produced a bundle nobody could audit afterwards).
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

# --uv-lock-sha256 is intentionally NOT passed: the harness derives it from
# this checkout's uv.lock, so it cannot silently end up as "unknown".
python scripts/m13_live_loop_capture.py --capture --real --confirm-spend `
  --out-dir experiments/20260904-m13-live-loop-live/artifacts `
  --n-cognition-ticks 32 `
  --physics-ticks-per-cognition 20 `
  --qwen3-model-digest $env:QWEN3_DIGEST `
  --ollama-version $env:OLLAMA_VERSION `
  --vram-gb $env:VRAM_GB
