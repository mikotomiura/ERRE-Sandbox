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

set -uo pipefail

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
[[ "$NO_PYTEST" == "0" ]] && step "pytest -q (non-godot)" "$PYTHON" -m pytest -q --ignore=tests/test_godot

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
