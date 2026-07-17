#Requires -Version 5.1
# aha!/DMN-ECN Phase 3 — think=True sealed capture (G-GEAR Windows native).
#
# reproducibility-discipline: 1-command sealed run. real qwen3:8b construction spend
# (measurement spend でない). think=True は非決定ゆえ byte-parity verify は成立しない
# (record→観察のみ, design-final §決定性). WSL2→Windows Ollama 不通ゆえ Windows native 実行
# (reference_wsl2_ollama_unreachable). PYTHONUTF8=1 必須 (Windows console cp932).
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"                                    # Codex L3 / cp932 guard
if (-not $env:OLLAMA_HOST) { $env:OLLAMA_HOST = "http://127.0.0.1:11434" }  # Codex L3
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # experiments/<date>/ -> repo root
Set-Location $repo

# --- env pins (Codex L3): record what actually produced the run ---
$ollamaVersion = try { (Invoke-RestMethod -Uri "$($env:OLLAMA_HOST)/api/version").version } catch { "unknown" }
$digest = "unknown"
try {
    $tags = Invoke-RestMethod -Uri "$($env:OLLAMA_HOST)/api/tags"
    $qwen = $tags.models | Where-Object { $_.name -eq "qwen3:8b" } | Select-Object -First 1
    if ($qwen) { $digest = $qwen.digest }
} catch {}
$vramGb = "0"
try {
    $totalMiB = (nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits) -split "`n" | Select-Object -First 1
    $vramGb = [string]([math]::Round([double]$totalMiB / 1024.0, 2))
} catch {}
$uvLock = (Get-FileHash -Algorithm SHA256 (Join-Path $repo "uv.lock")).Hash.ToLower()

Write-Host "[run] ollama=$ollamaVersion digest=$digest vram_gb=$vramGb uv_lock=$($uvLock.Substring(0,16))"

python scripts/aha_phase3_think_capture.py --capture `
    --qwen3-model-digest $digest `
    --ollama-version $ollamaVersion `
    --vram-gb $vramGb `
    --uv-lock-sha256 $uvLock
exit $LASTEXITCODE
