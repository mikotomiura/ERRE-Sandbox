#!/bin/bash
# PreToolUse hook (Guard 層) - ERRE-Sandbox 固有の禁止パターン検出
# 禁止: import openai/anthropic (クラウドLLM禁止), import bpy (GPL禁止), print( デバッグ出力
# パス時は [guard] PASS を明示出力する

TOOL_INPUT=$(cat)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

TARGET_FILE=$(echo "$TOOL_INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null)
if [ -z "$TARGET_FILE" ]; then
    exit 0
fi

# 相対パス化
REL="${TARGET_FILE#$REPO_ROOT/}"

# src/erre_sandbox/ 配下の .py ファイルのみ対象
if ! echo "$REL" | grep -qE "^src/erre_sandbox/.*\.py$"; then
    exit 0
fi

# Edit の new_string、Write の content、MultiEdit の edits[].new_string を取得
CONTENT=$(echo "$TOOL_INPUT" | jq -r '
  .tool_input.new_string //
  .tool_input.content //
  (.tool_input.edits // [] | map(.new_string // "") | join("\n"))
' 2>/dev/null)

if [ -z "$CONTENT" ]; then
    exit 0
fi

# 1. クラウド LLM API の import 禁止
if printf '%s\n' "$CONTENT" | grep -qE "^\s*(import openai|from openai|import anthropic|from anthropic)"; then
    echo "[guard] BLOCKED: クラウド LLM API の import は禁止です。(コストゼロ制約)"
    echo "[guard]          ローカル推論 (SGLang / Ollama) を使用してください。"
    exit 1
fi

# 2. GPL ライブラリ (bpy) の import 禁止
if printf '%s\n' "$CONTENT" | grep -qE "^\s*(import bpy|from bpy)"; then
    echo "[guard] BLOCKED: import bpy は src/erre_sandbox/ への混入が禁止です。(GPL viral 制約)"
    echo "[guard]          Blender 連携は別パッケージ (GPL-3.0 スコープ) に分離してください。"
    exit 1
fi

# 3. print() デバッグ出力の禁止
if printf '%s\n' "$CONTENT" | grep -qE "^\s*print\("; then
    echo "[guard] BLOCKED: print() の使用は禁止です。logging モジュールを使用してください。"
    echo "[guard]          例: import logging; logger = logging.getLogger(__name__); logger.debug(...)"
    exit 1
fi

# パス時: PASS を明示出力
echo "[guard] PASS: banned patterns ($REL)"
exit 0
