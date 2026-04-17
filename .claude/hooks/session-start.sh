#!/bin/bash
# Session start hook - プロジェクトの動的情報を表示

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

echo "════════════════════════════════════════"
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'N/A')"
echo "Last commit: $(git log -1 --oneline 2>/dev/null || echo 'N/A')"
echo "Modified: $(git status --short 2>/dev/null | wc -l | tr -d ' ') files"

# 未対応 TODO の数
todo_count=$(grep -r "TODO\|FIXME\|HACK" "${REPO_ROOT}/src" 2>/dev/null | wc -l | tr -d ' ')
echo "Open TODOs: $todo_count"

# 進行中のタスク（直近3件）
current_tasks=$(ls -1t "${REPO_ROOT}/.steering/" 2>/dev/null | grep -E '^[0-9]{8}-' | head -3)
if [ -n "$current_tasks" ]; then
    echo ""
    echo "Recent tasks:"
    echo "$current_tasks" | sed 's/^/  - /'
fi

echo "════════════════════════════════════════"
