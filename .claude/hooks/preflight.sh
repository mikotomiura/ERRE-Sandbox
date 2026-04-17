#!/bin/bash
# Preflight dashboard — 毎ターン実行、プロジェクト状態を可視化
# 常に exit 0 (BLOCK しない)

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Task check: 直近 7 日内の .steering/YYYYMMDD-*/ を更新日時順で検索
TASK_DIR=""
TASK_NAME=""
for i in 0 1 2 3 4 5 6 7; do
    DATE=$(date -v-${i}d +%Y%m%d 2>/dev/null || date -d "$i days ago" +%Y%m%d 2>/dev/null)
    [ -z "$DATE" ] && continue
    FOUND=$(ls -1td "${REPO_ROOT}/.steering/${DATE}-"* 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        TASK_DIR="$FOUND"
        TASK_NAME=$(basename "$FOUND")
        break
    fi
done

if [ -z "$TASK_DIR" ]; then
    echo "[preflight] task: NONE -- /start-task required before implementation"
    UNCOMMITTED=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
    echo "[preflight] git: ${UNCOMMITTED} uncommitted"
    exit 0
fi

# 必須 3 ファイルの存在カウント
FILE_COUNT=0
MISSING=""
for f in requirement.md design.md tasklist.md; do
    if [ -f "$TASK_DIR/$f" ]; then
        FILE_COUNT=$((FILE_COUNT + 1))
    else
        MISSING="$MISSING $f"
    fi
done

# design.md テンプレート残存検出
DESIGN_NOTE=""
if [ -f "$TASK_DIR/design.md" ]; then
    if grep -q "採用する方針と、その理由。" "$TASK_DIR/design.md" 2>/dev/null; then
        DESIGN_NOTE=" | design: TEMPLATE"
    fi
fi

MISSING_NOTE=""
if [ -n "$MISSING" ]; then
    MISSING_NOTE=" | WARN: missing$MISSING"
fi

echo "[preflight] task: $TASK_NAME ($FILE_COUNT/3)${DESIGN_NOTE}${MISSING_NOTE}"

# Git + reimagine 適用状態
UNCOMMITTED=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
REIMAGINE=""
if [ -f "$TASK_DIR/design-v1.md" ] || [ -f "$TASK_DIR/design-comparison.md" ]; then
    REIMAGINE=" | reimagine: applied"
elif grep -q "/reimagine 適用: Yes" "$TASK_DIR/requirement.md" 2>/dev/null; then
    REIMAGINE=" | reimagine: PENDING"
fi

echo "[preflight] git: ${UNCOMMITTED} uncommitted${REIMAGINE}"
exit 0
