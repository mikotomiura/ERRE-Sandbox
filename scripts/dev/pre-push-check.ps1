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
#
# ---------------------------------------------------------------------------
# CI selection の正典 (SSOT) は `.github/workflows/ci.yml` の `test` job である。
# 本 script はその **文字列を複製** し、一致は
# `tests/test_architecture/test_pre_push_ci_parity.py` が parse して機械検査する。
# (.steering/20260911-ci-selection-ssot/decisions.md DA-CIS-1)
#
# 以前の `--ignore=tests/test_godot` は **`tests/test_godot` ディレクトリが存在しない**
# ため no-op で、CI が deselect する godot / eval / spike / training / inference を
# local だけが走らせていた。docs 1 ファイルの変更で pre-push が exit 1 になる偽陽性の
# 原因 (blockers B-P03-6 / memory feedback_pre_push_script_ci_drift)。
# ---------------------------------------------------------------------------

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

# CI (`.github/workflows/ci.yml` の `test` job) と同一の marker 式。
# 変更するときは ci.yml を先に直すこと (ci.yml が SSOT)。
$CiMarkerExpression = "not godot and not eval and not spike and not training and not inference"

# CI の `test` job が `env:` で立てているものと同じ。Windows console の既定
# codepage (cp932 等) だと subprocess の stdout を読むテストが
# UnicodeDecodeError で落ちる (memory feedback_powershell_cp932_subprocess_test)。
$env:PYTHONUTF8 = "1"

# CI は `PYTHONUTF8` 以外の env を一切設定しない。`ERRE_ZONE_BIAS_P` のような
# 実験用 pin が残っていると parity が崩れる (2026-09-11 に実際にやらかし、
# 封印 bundle の verify が 5 件落ちた)。落とさずに警告だけ出す。
$erreEnv = @(Get-ChildItem Env: | Where-Object { $_.Name -like 'ERRE_*' })
if ($erreEnv.Count -gt 0) {
    Write-Host ""
    Write-Host "WARNING: CI が設定しない ERRE_* 環境変数がこのセッションに残っています:" -ForegroundColor Yellow
    foreach ($e in $erreEnv) {
        Write-Host ("  {0}={1}" -f $e.Name, $e.Value) -ForegroundColor Yellow
    }
    Write-Host "         CI parity を測るなら外してから再実行してください。" -ForegroundColor Yellow
}

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
    Step "pytest -q -m (CI selection)" { & $Python -m pytest -q -m $CiMarkerExpression }
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
