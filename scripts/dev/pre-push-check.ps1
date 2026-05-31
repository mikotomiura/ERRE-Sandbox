# Pre-push CI parity check (PowerShell, G-GEAR Windows native venv)
#
# 使い方:
#   .\scripts\dev\pre-push-check.ps1
#
# CI (.github/workflows/ci.yml) と同じ 4 段階を local で実行する。
# 1 段でも fail なら exit 非ゼロ。push / `gh pr create` の前に必ず実行する。
#
# Memory: feedback_pre_push_ci_parity.md (PR #181 reflection で起票)
# 例外的に skip したい場合は明示的な `-SkipPytest` 等の flag を用意するか、
# 該当 commit に「why CI fix is acceptable」を justification として記録する。

[CmdletBinding()]
param(
    [switch]$NoFormat,
    [switch]$NoLint,
    [switch]$NoMypy,
    [switch]$NoPytest
)

$ErrorActionPreference = 'Continue'
$Script:Failed = 0
$Script:Started = Get-Date

function Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==[ $Label ]==" -ForegroundColor Cyan
    $stepStart = Get-Date
    & $Body
    $exit = $LASTEXITCODE
    $dur = ((Get-Date) - $stepStart).TotalSeconds
    if ($exit -eq 0) {
        Write-Host ("  [PASS] {0} ({1:N1}s)" -f $Label, $dur) -ForegroundColor Green
    } else {
        Write-Host ("  [FAIL] {0} (exit={1}, {2:N1}s)" -f $Label, $exit, $dur) -ForegroundColor Red
        $Script:Failed += 1
    }
}

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: $Python not found. Run 'uv sync --extra eval' first." -ForegroundColor Red
    exit 2
}

if (-not $NoFormat) {
    Step "ruff format --check src tests" { & $Python -m ruff format --check src tests }
}

if (-not $NoLint) {
    Step "ruff check src tests" { & $Python -m ruff check src tests }
}

if (-not $NoMypy) {
    Step "mypy src" { & $Python -m mypy src }
}

if (-not $NoPytest) {
    Step "pytest -q (non-godot)" { & $Python -m pytest -q --ignore=tests/test_godot }
}

$totalDur = ((Get-Date) - $Script:Started).TotalSeconds
Write-Host ""
if ($Script:Failed -eq 0) {
    Write-Host ("==[ ALL CHECKS PASSED ({0:N1}s total) ]==" -f $totalDur) -ForegroundColor Green
    Write-Host "Safe to push / gh pr create." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("==[ {0} CHECK(S) FAILED ({1:N1}s total) ]==" -f $Script:Failed, $totalDur) -ForegroundColor Red
    Write-Host "DO NOT push. Fix the failures above and re-run." -ForegroundColor Red
    exit 1
}
