#!/bin/bash
# Stop hook (Report 層) - セッション終了時の静的解析
# 失敗しても exit 0（ブロックしない。報告のみ）

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# src/ が存在しない場合はスキップ（スケルトン段階）
if [ ! -d "${REPO_ROOT}/src" ]; then
    exit 0
fi

# ruff lint チェック
if command -v ruff >/dev/null 2>&1; then
    if ! ruff check "${REPO_ROOT}/src" >/dev/null 2>&1; then
        echo "[stop] WARN: ruff check reported issues. Run 'ruff check src/' to inspect."
    fi
fi

# mypy 型チェック（インストールされている場合のみ）
if command -v mypy >/dev/null 2>&1; then
    if ! mypy "${REPO_ROOT}/src" --ignore-missing-imports --no-error-summary >/dev/null 2>&1; then
        echo "[stop] WARN: mypy reported type errors. Run 'mypy src/ --ignore-missing-imports' to inspect."
    fi
fi

exit 0
