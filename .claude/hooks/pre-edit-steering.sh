#!/bin/bash
# PreToolUse hook (Guard 層) - .steering/ の必須ファイルが無い状態で実装ファイルの編集をブロック
# パス時は [guard] PASS を明示出力する
# stdin から Claude Code の tool_input JSON を受け取る

TOOL_INPUT=$(cat)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# file_path を JSON から取得（Edit/Write/MultiEdit のスキーマに対応）
TARGET_FILE=$(echo "$TOOL_INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null)

if [ -z "$TARGET_FILE" ]; then
    exit 0
fi

# 相対パス化（ログ可読性のため）
REL="${TARGET_FILE#$REPO_ROOT/}"

# 実装ファイルのパスパターン: src/erre_sandbox/ のみ対象
IMPL_PATTERN="^src/erre_sandbox/"

if ! echo "$REL" | grep -qE "$IMPL_PATTERN"; then
    exit 0
fi

# 直近 7 日以内の .steering/YYYYMMDD-* タスクディレクトリを探索
TASK_DIR=""
for i in 0 1 2 3 4 5 6 7; do
    DATE=$(date -v-${i}d +%Y%m%d 2>/dev/null || date -d "$i days ago" +%Y%m%d 2>/dev/null)
    [ -z "$DATE" ] && continue
    FOUND=$(ls -1td "${REPO_ROOT}/.steering/${DATE}-"* 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        TASK_DIR="$FOUND"
        break
    fi
done

if [ -z "$TASK_DIR" ]; then
    echo "[guard] BLOCKED: 実装ファイルを編集する前に /start-task でタスクを開始してください。"
    echo "[guard]          .steering/ にアクティブなタスクディレクトリが見つかりません。"
    exit 1
fi

# 必須 3 ファイルの存在チェック
MISSING=""
[ ! -f "$TASK_DIR/requirement.md" ] && MISSING="$MISSING requirement.md"
[ ! -f "$TASK_DIR/design.md" ] && MISSING="$MISSING design.md"
[ ! -f "$TASK_DIR/tasklist.md" ] && MISSING="$MISSING tasklist.md"

if [ -n "$MISSING" ]; then
    TASK_NAME=$(basename "$TASK_DIR")
    echo "[guard] BLOCKED: $TASK_NAME に以下の必須ファイルがありません:$MISSING"
    echo "[guard]          /start-task を完了してから実装に入ってください。"
    exit 1
fi

# パス時: PASS を明示出力
TASK_NAME=$(basename "$TASK_DIR")
echo "[guard] PASS: steering ($TASK_NAME, 3/3 files) -> $REL"
exit 0
