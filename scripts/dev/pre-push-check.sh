#!/usr/bin/env bash
# Pre-push CI parity check (bash, WSL2 / macOS / Linux)
#
# 使い方:
#   bash scripts/dev/pre-push-check.sh
#
# CI (.github/workflows/ci.yml) と同じ 4 段階を local で実行する。
# 1 段でも fail なら exit 非ゼロ。push / `gh pr create` の前に必ず実行する。
#
# Memory: feedback_pre_push_ci_parity.md (PR #181 reflection で起票)
#
# ---------------------------------------------------------------------------
# CI selection の正典 (SSOT) は `.github/workflows/ci.yml` の `test` job である。
# 本 script はその **文字列を複製** し、一致は
# `tests/test_architecture/test_pre_push_ci_parity.py` が parse して機械検査する。
# (.steering/20260911-ci-selection-ssot/decisions.md DA-CIS-1)
#
# 以前の `--ignore=tests/test_godot` は **`tests/test_godot` ディレクトリが存在しない**
# ため no-op で、CI が deselect する godot / eval / spike / training / inference を
# local だけが走らせていた (blockers B-P03-6 / memory feedback_pre_push_script_ci_drift)。
# ---------------------------------------------------------------------------

set -uo pipefail

# CI (`.github/workflows/ci.yml` の `test` job) と同一の marker 式。
# 変更するときは ci.yml を先に直すこと (ci.yml が SSOT)。
CI_MARKER_EXPRESSION="not godot and not eval and not spike and not training and not inference"

# CI の `test` job が `env:` で立てているものと同じ。Windows (Git Bash) から
# 回したときに subprocess の stdout 読み取りが legacy codepage で落ちるのを防ぐ。
# Linux / macOS では既に UTF-8 が実効既定なので no-op。
export PYTHONUTF8=1

# CI は `PYTHONUTF8` 以外の env を一切設定しない。`ERRE_ZONE_BIAS_P` のような
# 実験用 pin が残っていると parity が崩れる。落とさずに警告だけ出す。
erre_env=$(env | grep -E '^ERRE_' || true)
if [[ -n "$erre_env" ]]; then
    echo ""
    echo "WARNING: CI が設定しない ERRE_* 環境変数がこのセッションに残っています:"
    echo "$erre_env" | sed 's/^/  /'
    echo "         CI parity を測るなら外してから再実行してください。"
fi

NO_FORMAT=${NO_FORMAT:-0}
NO_LINT=${NO_LINT:-0}
NO_MYPY=${NO_MYPY:-0}
NO_PYTEST=${NO_PYTEST:-0}

FAILED=0
STARTED=$(date +%s)

PYTHON=".venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON=".venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python venv not found. Run 'uv sync --extra eval' first." >&2
    exit 2
fi

step() {
    local label="$1"; shift
    echo ""
    echo "==[ $label ]=="
    local step_start
    step_start=$(date +%s)
    if "$@"; then
        printf "  [PASS] %s (%ss)\n" "$label" "$(( $(date +%s) - step_start ))"
    else
        local code=$?
        printf "  [FAIL] %s (exit=%s, %ss)\n" "$label" "$code" "$(( $(date +%s) - step_start ))"
        FAILED=$((FAILED + 1))
    fi
}

[[ "$NO_FORMAT" == "0" ]] && step "ruff format --check" "$PYTHON" -m ruff format --check src tests
[[ "$NO_LINT" == "0" ]]   && step "ruff check"          "$PYTHON" -m ruff check src tests
[[ "$NO_MYPY" == "0" ]]   && step "mypy src"            "$PYTHON" -m mypy src
[[ "$NO_PYTEST" == "0" ]] && step "pytest -q -m (CI selection)" "$PYTHON" -m pytest -q -m "$CI_MARKER_EXPRESSION"

TOTAL_DUR=$(( $(date +%s) - STARTED ))
echo ""
if [[ "$FAILED" -eq 0 ]]; then
    echo "==[ ALL CHECKS PASSED (${TOTAL_DUR}s total) ]=="
    echo "Safe to push / gh pr create."
    exit 0
else
    echo "==[ ${FAILED} CHECK(S) FAILED (${TOTAL_DUR}s total) ]=="
    echo "DO NOT push. Fix the failures above and re-run."
    exit 1
fi
