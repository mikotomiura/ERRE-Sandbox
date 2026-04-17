#!/bin/bash
# PostToolUse hook (Report 層) - ruff format 実行 + 変更報告
# 変更が生じた時だけ [fmt] を出力する（ノイズ削減）

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

command -v ruff >/dev/null 2>&1 || exit 0

# src/ 配下に .py ファイルが存在するか確認
if [ ! -d "${REPO_ROOT}/src" ]; then
    exit 0
fi

# --check で変更が必要かを先判定（変更不要なら無言で抜ける）
if ruff format --check "${REPO_ROOT}/src" >/dev/null 2>&1; then
    exit 0
fi

# ここに来た = 整形が必要
ruff format "${REPO_ROOT}/src" >/dev/null 2>&1 || true
echo "[fmt] ruff format applied"
exit 0
