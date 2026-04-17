---
description: >
  Hook 群を .claude/hooks/ と settings.json に構築する。
  3層構成: (1) Preflight 層（UserPromptSubmit で毎ターン .steering/ 状態・git 状態・
  reimagine 適用状態を動的チェックしてダッシュボード表示、BLOCK しない）、
  (2) Guard 層（PreToolUse で機械的に検出可能な違反をブロック、パス時は [guard] PASS を出力）、
  (3) Report 層（PostToolUse で fmt 実行＋変更報告、Stop で clippy/tsc 等のセッション終了チェック）。
  加えて SessionStart で動的情報表示。計 5 種の Hook を構築する。
  全層の出力を [preflight] / [guard] / [fmt] プレフィックスで統一する。
  /setup-commands の完了後に実行する。
allowed-tools: Read, Write, Edit, Glob, Bash(mkdir *), Bash(chmod *), Bash(ls *)
---

# /setup-hooks — Hook 群構築コマンド

> Phase 6 of 7. Let's think step by step.
> Hook はエージェントループの外で決定論的に動作するスクリプト。
> 「人間が毎回チェックすべきこと」を Hook に任せる。

## 設計原則: 3 層構成 (Preflight / Guard / Report)

Hook で矯正できるものと、できないものがある。加えて「hook が動いているか」をユーザー・Claude 双方から可視化できるかが継続運用の鍵になる。この両軸で設計する。

### 第 1 層: Preflight 層（UserPromptSubmit）

**毎ターン動的にプロジェクト状態を可視化** する。`preflight.sh` が .steering/ 状態・git 状態・reimagine 適用状態をスキャンし、2-3 行のダッシュボードを表示する。

- **BLOCK しない（常に exit 0）**。警告のみ。
- 毎ターン発火するため、計画立案・調査・質問応答など **編集を伴わないターンでも** プロジェクト状態が見える。
- 固定文言の echo ではなく動的チェックにすることで、hook が動いているかの **透明性（trust signal）** を確保する。

### 第 2 層: Guard 層（PreToolUse）

**決定論的に検出可能な違反** を機械的にブロックする。bash スクリプトで判定できるもの:

- `.steering/` に必須ファイルが無い状態で実装ファイルを編集 → ブロック
- 禁止された crate / import の混入 → ブロック

パス時は **`[guard] PASS: ...` を明示出力** する。無言通過は禁止（hook が動作していることの可視化）。

### 第 3 層: Report 層（PostToolUse / Stop）

**自動整形とセッション終了時の自己検証** を担当する。

- PostToolUse → `post-fmt.sh` が Edit/Write 後に fmt を実行し、**変更があった時のみ** `[fmt] ...` を報告
- Stop → `stop-check.sh` がセッション終了時に clippy / tsc などの重い静的解析を実行

### 出力規約

全 hook の出力は以下のプレフィックスで統一する:

- `[preflight]` — Preflight 層
- `[guard]` — Guard 層（PASS / BLOCKED の両方）
- `[fmt]` — PostToolUse の整形結果

これによりログのソースが即座に判別できる。

### 旧 2 層構成からの移行根拠

PreToolUse は `Edit|Write|MultiEdit` matcher にしか発火しない。つまり **編集を伴わないターンでは hook が全く働かない**。また UserPromptSubmit を固定文言 echo にすると、毎ターン同じ文字列が表示されるだけでプロジェクトの現状が見えない。Preflight 層を動的チェックに置き換えることでこの両方を解消する。

## 環境チェックブロック

### Check 1: 進捗ファイル

```bash
cat .steering/_setup-progress.md
```

Phase 5 完了を確認。

### Check 2: 既存設定の確認

```bash
ls -la .claude/
cat .claude/settings.json 2>/dev/null
```

既存の settings.json があれば内容を Read で確認。あれば追記モード、なければ新規作成モード。

### Check 3: コンテキスト予算

`/context` で 30% 以下を確認。

## 実行フロー

### Step 1: ユーザーへのヒアリング

このプロジェクトで使う Hook を決めるため、以下を質問:

1. lint ツール: 何を使っていますか?（ruff, eslint, prettier など）
2. format ツール: 何を使っていますか?
3. テストランナー: 何を使っていますか?
4. このプロジェクトで「セッション開始時に必ず確認したい情報」は何ですか?
5. 「実装完了時に必ず実行したいチェック」は何ですか?
6. commit メッセージの規約はありますか?（例: `type(scope): ...` 形式）
7. 実装ファイルの配置パス: 実装コードはどのディレクトリに入りますか?（例: `src/`, `app/`, `lib/`）
8. **禁止事項**: プロジェクト固有の禁止パターンはありますか?（例: 特定 crate の使用禁止、特定関数の混入禁止 — `println!`, `console.log` 等）

回答を踏まえて以下の Hook を構築する。

### Step 2: ディレクトリ作成

```bash
mkdir -p .claude/hooks
```

### Step 3: SessionStart Hook の作成

CLAUDE.md にプロジェクトの動的情報を入れる代わりに、Hook で表示する。これにより CLAUDE.md をスリムに保てる。

`.claude/hooks/session-start.sh`:

```bash
#!/bin/bash
# Session start hook - プロジェクトの動的情報を表示

echo "════════════════════════════════════════"
echo "📍 Branch: $(git branch --show-current 2>/dev/null || echo 'N/A')"
echo "🔖 Last commit: $(git log -1 --oneline 2>/dev/null || echo 'N/A')"
echo "📝 Modified files: $(git status --short 2>/dev/null | wc -l | tr -d ' ')"

# 未対応 TODO の数
todo_count=$(grep -r "TODO\|FIXME\|HACK" src/ 2>/dev/null | wc -l | tr -d ' ')
echo "📋 Open TODOs: $todo_count"

# 進行中のタスク
current_tasks=$(ls -1 .steering/ 2>/dev/null | grep -E '^[0-9]{8}-' | tail -3)
if [ -n "$current_tasks" ]; then
    echo ""
    echo "🚧 Recent tasks in .steering/:"
    echo "$current_tasks" | sed 's/^/  - /'
fi

# プロジェクトタイプの検出
if [ -f "pyproject.toml" ]; then
    echo "🐍 Python project (pyproject.toml)"
fi
if [ -f "package.json" ]; then
    echo "📦 Node project (package.json)"
fi
if [ -f "Cargo.toml" ]; then
    echo "🦀 Rust project (Cargo.toml)"
fi

echo "════════════════════════════════════════"
```

権限を付与:

```bash
chmod +x .claude/hooks/session-start.sh
```

ユーザーに表示して承認を得る。プロジェクト固有の情報を追加したい場合は反映。

### Step 4: UserPromptSubmit Hook の設計（Preflight 層）

**毎ターン .steering/ 状態・git 状態・reimagine 適用状態を動的にスキャン** し、2-3 行のダッシュボードで可視化する。BLOCK しない（常に exit 0）。固定文言 echo は使わない。

#### 4a. preflight.sh スクリプトの作成

`.claude/hooks/preflight.sh`:

```bash
#!/bin/bash
# Preflight dashboard — 毎ターン実行、プロジェクト状態を可視化
# 常に exit 0 (BLOCK しない)

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Task check: 直近 7 日内の .steering/YYYYMMDD-*/ を更新日時順で検索
TASK_DIR=""
TASK_NAME=""
for i in 0 1 2 3 4 5 6 7; do
    # macOS BSD date と GNU date の両対応
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

# design.md テンプレート残存検出（プロジェクトに応じて判定文字列を調整）
DESIGN_NOTE=""
if [ -f "$TASK_DIR/design.md" ]; then
    # ⚠️ ヒアリング Q: このプロジェクトの design.md テンプレートに特有の文字列を指定
    # 例: "採用する方針と、その理由。" / "## 設計方針" など、テンプレート未記入を示す一意な文字列
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
```

権限を付与:

```bash
chmod +x .claude/hooks/preflight.sh
```

#### 4b. カスタマイズポイント（ヒアリングで調整）

- **design.md テンプレート判定の grep パターン**: プロジェクトの design.md テンプレートに応じて一意の文字列を指定。`/setup-claude-md` で配置した `.steering/_template/design.md` の中身を確認して決める。
- **reimagine チェックの有無**: /reimagine コマンドを使わないプロジェクトでは該当ブロックを削除。
- **実装ファイルパス**: preflight.sh はディレクトリパスの判定を行わない（全ターン発火のため）が、TASK_DIR の検索対象は `.steering/YYYYMMDD-*/` 形式に限定。この命名規約は /start-task の出力と一致することを確認する。

#### 4c. なぜ固定文言 echo ではダメなのか

- 旧設計の `[REMINDER] CLAUDE.md を精読...` は毎ターン同じ文字列が流れるだけで、情報密度がゼロ。
- 「hook が動いているか」が不可視。動いていなくても同じ結果に見える。
- プロジェクトの「現在の状態」(アクティブタスク、未コミット変更、reimagine 適用状態) が一切見えない。
- CLAUDE.md 精読の想起は、SessionStart hook と CLAUDE.md 本体の「セッション開始時の行動規範」に委ねる方が適切（毎ターン注入する固定費に見合わない）。

ユーザーに preflight.sh の内容を表示して承認を得る。テンプレート判定文字列はヒアリングで確定させる。

### Step 5: PreToolUse Hook の設計（Guard 層）

**決定論的に検出可能な違反をブロックする**。bash スクリプトで実装。パス時は必ず `[guard] PASS: ...` を出力する（無言通過は禁止）。

#### 5a. steering チェックスクリプトの作成

`.claude/hooks/pre-edit-steering.sh`:

```bash
#!/bin/bash
# PreToolUse hook (Guard 層) - .steering/ の必須ファイルが無い状態で実装ファイルの編集をブロック
# パス時は [guard] PASS を明示出力する

# 引数: 編集対象のファイルパス（PreToolUse の入力から渡される）
TARGET_FILE="$1"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# 相対パス化（ログ可読性のため）
REL="${TARGET_FILE#$REPO_ROOT/}"

# 実装ファイルのパスパターン（Step 1 のヒアリング結果で調整）
IMPL_PATTERN="^(src|app|lib)/"

# 対象外ならチェック不要（docs/ やテストファイルなど）
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
```

権限を付与:

```bash
chmod +x .claude/hooks/pre-edit-steering.sh
```

#### 5b. プロジェクト固有の禁止パターンチェック（任意）

Step 1 のヒアリングで禁止事項が挙がった場合、追加のチェックスクリプトを作成する。

例（Rust プロジェクトで `println!` 混入と winapi crate をブロック）:

`.claude/hooks/pre-edit-banned.sh`:

```bash
#!/bin/bash
# PreToolUse hook (Guard 層) - 禁止パターンの検出
# パス時は [guard] PASS を明示出力する

TARGET_FILE="$1"
CONTENT="$2"  # 書き込み予定の内容（Edit/Write の場合）
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
REL="${TARGET_FILE#$REPO_ROOT/}"

# println! / eprintln! の混入チェック（*.rs ファイル対象）
if echo "$REL" | grep -qE '\.rs$'; then
    if echo "$CONTENT" | grep -qE '(println!|eprintln!)'; then
        echo "[guard] BLOCKED: println!/eprintln! の使用は禁止です。log crate を使ってください。"
        exit 1
    fi
fi

# winapi crate の追加チェック（Cargo.toml 対象）
if echo "$REL" | grep -qE 'Cargo\.toml$'; then
    if echo "$CONTENT" | grep -qE 'winapi'; then
        echo "[guard] BLOCKED: winapi crate の使用は禁止です。windows crate を使ってください。"
        exit 1
    fi
fi

# パス時: PASS を明示出力
echo "[guard] PASS: banned patterns ($REL)"
exit 0
```

⚠️ **このスクリプトはプロジェクト固有**。ヒアリング結果に応じてパターンを書き換えること。
禁止事項がない場合はこのスクリプト自体を作成しない（代わりに無言通過してしまう `[guard] PASS` を出すためだけの空スクリプトも作らない — ノイズになる）。

ユーザーに承認を得る。

### Step 6: Stop Hook の設計（Report 層）

セッション終了時に重めの静的解析（clippy / tsc 等）を実行する。`"type": "prompt"` の自然言語プロンプトではなく、`"type": "command"` の外部スクリプトに統一する（settings.json の形式を全 hook で揃えるため）。

`.claude/hooks/stop-check.sh` テンプレート:

```bash
#!/bin/bash
# Stop hook (Report 層) - セッション終了時の静的解析
# 失敗しても exit 0（ブロックしない。報告のみ）

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# --- Rust (clippy) ---
# ⚠️ Step 1 のヒアリングに応じて調整。Rust プロジェクトでない場合はブロックごと削除。
MANIFEST="${REPO_ROOT}/src-tauri/Cargo.toml"
if [ -f "$MANIFEST" ]; then
    if ! cargo clippy --manifest-path "$MANIFEST" --quiet -- -D warnings >/dev/null 2>&1; then
        echo "[stop] WARN: cargo clippy reported issues. Run 'cargo clippy' to inspect."
    fi
fi

# --- TypeScript (tsc) ---
# ⚠️ TypeScript プロジェクトでない場合はブロックごと削除。
if [ -f "${REPO_ROOT}/tsconfig.json" ] && command -v npx >/dev/null 2>&1; then
    if ! (cd "$REPO_ROOT" && npx --no-install tsc --noEmit >/dev/null 2>&1); then
        echo "[stop] WARN: tsc reported type errors. Run 'npx tsc --noEmit' to inspect."
    fi
fi

exit 0
```

権限を付与:

```bash
chmod +x .claude/hooks/stop-check.sh
```

⚠️ **重要**: 出力を必ず `>/dev/null 2>&1` で抑制し、問題があった時だけ短い 1 行を出す。clippy / tsc のフル出力を流すと 1 ターンで数万トークンを消費する。詳細を見たい時はユーザーが手動で実行する前提。

⚠️ **プロジェクト固有**: clippy / tsc ブロックはヒアリング結果に応じて差し替える。Python なら ruff / mypy、Go なら `go vet` 等。

### Step 7: PostToolUse Hook の設計（Report 層）

Edit/Write 後の自動整形を行う。インラインコマンドではなく **外部スクリプト** に切り出す。理由は (1) 保守性、(2) 変更があった時だけ報告する条件分岐が書きやすい、(3) settings.json の形式を全 hook で揃えられる。

#### 7a. post-fmt.sh の作成

`.claude/hooks/post-fmt.sh` テンプレート（Rust の例）:

```bash
#!/bin/bash
# PostToolUse hook (Report 層) - format 実行 + 変更報告
# 変更が生じた時だけ [fmt] を出力する（ノイズ削減）

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
MANIFEST="${REPO_ROOT}/src-tauri/Cargo.toml"  # ⚠️ プロジェクトに合わせて調整

if [ ! -f "$MANIFEST" ]; then
    exit 0
fi

# 先に --check で変更が必要かを判定（変更不要なら無言で抜ける）
if cargo fmt --manifest-path "$MANIFEST" -- --check >/dev/null 2>&1; then
    exit 0
fi

# ここに来た = 整形が必要
cargo fmt --manifest-path "$MANIFEST" --quiet 2>/dev/null || true
echo "[fmt] cargo fmt applied"
exit 0
```

権限を付与:

```bash
chmod +x .claude/hooks/post-fmt.sh
```

#### 7b. 他言語の例

Python (ruff) の場合:

```bash
#!/bin/bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
command -v ruff >/dev/null 2>&1 || exit 0
# check → needs-formatting なら fix を当てて報告
if ruff format --check "$REPO_ROOT" >/dev/null 2>&1; then
    exit 0
fi
ruff format "$REPO_ROOT" >/dev/null 2>&1 || true
echo "[fmt] ruff format applied"
exit 0
```

TypeScript (prettier) の場合:

```bash
#!/bin/bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
command -v npx >/dev/null 2>&1 || exit 0
if (cd "$REPO_ROOT" && npx --no-install prettier --check . >/dev/null 2>&1); then
    exit 0
fi
(cd "$REPO_ROOT" && npx --no-install prettier --write . >/dev/null 2>&1) || true
echo "[fmt] prettier applied"
exit 0
```

⚠️ **重要**: 出力は必ず `>/dev/null 2>&1` で抑制する。これを忘れると 1 ターンで数万トークンを消費する。報告は `[fmt] ... applied` の 1 行のみ。

ユーザーに確認:

> 「PostToolUse Hook で自動整形を有効にしますか? 有効にすると Edit/Write のたびに post-fmt.sh が実行されます。変更があった時のみ `[fmt] ... applied` と 1 行だけ報告され、不要なら無言で通過します。」

### Step 8: SessionStart Hook の登録

settings.json で SessionStart Hook を登録（`bash` プレフィックスを付けて他 hook と形式を揃える）:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/session-start.sh"
          }
        ]
      }
    ]
  }
}
```

### Step 9: settings.json の統合

すべての Hook 設定を 1 つの settings.json に統合する。**全 hook を `"type": "command"` に統一** する（旧 `"type": "prompt"` は使わない）。

`.claude/settings.json` を作成または更新:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/session-start.sh" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/preflight.sh" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/pre-edit-steering.sh \"$TOOL_INPUT_FILE\"" },
          { "type": "command", "command": "bash .claude/hooks/pre-edit-banned.sh \"$TOOL_INPUT_FILE\" \"$TOOL_INPUT_CONTENT\"" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/stop-check.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/post-fmt.sh" }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/post-fmt.sh" }
        ]
      }
    ]
  }
}
```

⚠️ **PreToolUse の `$TOOL_INPUT_FILE` / `$TOOL_INPUT_CONTENT` は Claude Code の環境変数**。実際のフック仕様に応じて調整が必要。ユーザーに Claude Code のフックドキュメントを確認して正確な変数名を使うよう促すこと。

⚠️ **pre-edit-banned.sh を作らない場合**（ヒアリングで禁止事項が無かった場合）、`PreToolUse` の該当行を削除する。

既存の settings.json がある場合は、Edit ツールでマージする。上書きしない。

### Step 10: 動作テスト

ユーザーに以下を依頼:

> 「Hook が正しく設定されたかテストします。」

テスト項目:

1. **SessionStart**: `/clear` 後にプロジェクト情報が表示されるか
2. **UserPromptSubmit (Preflight 層)**: 任意のプロンプト送信後に `[preflight] task: ...` と `[preflight] git: ...` が 2 行で出るか。タスクが無い状態では `[preflight] task: NONE ...` になるか
3. **PreToolUse (Guard 層)**:
   - `.steering/` が無い状態で `src/` 内のファイルを Edit しようとすると `[guard] BLOCKED: ...` が出るか
   - 必須 3 ファイルが揃った状態で Edit すると `[guard] PASS: steering (...) -> ...` が出るか（**PASS が出ない = 無言通過 = 異常**）
   - `docs/` や `tests/` の Edit はブロックされないか（偽陽性チェック）
4. **Stop (Report 層)**: ターン完了時に `[stop] WARN: ...` が出るか（問題が無ければ無言）
5. **PostToolUse (Report 層)**: 整形が必要な Edit 後に `[fmt] ... applied` が 1 行出るか。整形不要な Edit では無言通過するか

各テストの結果を確認し、問題があれば修正。

### Step 11: Grill me ステップ

Hook 設定を批判的にレビュー:

> Hook 設定を批判的にレビューします:
> - **Preflight 層**: preflight.sh は動的に状態を出しているか? 固定文言 echo になっていないか?
> - **Preflight 層**: `exit 0` を厳守し、BLOCK していないか?
> - **Preflight 層**: design.md テンプレート判定の grep パターンはプロジェクトの実テンプレートと一致しているか?
> - **Guard 層**: PreToolUse のブロック条件は偽陽性を出さないか? (docs/ 編集やテストファイル編集をブロックしていないか)
> - **Guard 層**: パス時に `[guard] PASS: ...` を出力しているか? (無言通過は NG)
> - **Report 層**: post-fmt.sh は `--check` で先判定し、変更時のみ `[fmt] ... applied` を出すか?
> - **Report 層**: stop-check.sh の clippy / tsc 出力は `>/dev/null 2>&1` で抑制されているか?
> - SessionStart Hook の出力は簡潔か? (毎セッション表示されるため、長すぎると邪魔)
> - settings.json の構文は正しいか? 全 hook が `"type": "command"` に統一されているか? (`"type": "prompt"` が混在していないか)
> - 全 hook の出力が `[preflight]` / `[guard]` / `[fmt]` / `[stop]` プレフィックスで統一されているか?
> - Hook がセッションを遅くする原因にならないか?
> - 3 層構成の設計原則に沿っているか? (Preflight = 動的可視化 / Guard = 決定論的ブロック+PASS / Report = 整形+終了時検証)

問題があれば修正。

### Step 12: 進捗ファイルの更新

`.steering/_setup-progress.md` の Phase 6 を完了マーク:

```markdown
- [x] **Phase 6: /setup-hooks** — Hook 群（3 層構成: Preflight / Guard / Report）
  - 完了日時: [YYYY-MM-DD HH:MM]
  - 作成 Hook:
    - SessionStart: .claude/hooks/session-start.sh（動的情報表示）
    - UserPromptSubmit: Preflight 層 / preflight.sh（毎ターン .steering/ 状態・git 状態・reimagine 状態を動的表示、BLOCK せず）
    - PreToolUse: Guard 層 / pre-edit-steering.sh + pre-edit-banned.sh（違反ブロック + パス時 `[guard] PASS` 出力）
    - PostToolUse: Report 層 / post-fmt.sh（Edit/Write 後に fmt、変更時のみ `[fmt] ... applied`）
    - Stop: Report 層 / stop-check.sh（clippy / tsc 等のセッション終了時チェック、問題時のみ WARN）
  - 出力プレフィックス統一: [preflight] / [guard] / [fmt] / [stop]
  - settings.json: [新規作成 / 既存に追記]（全 hook を `"type": "command"` に統一）
  - 外部スクリプト:
    - .claude/hooks/session-start.sh
    - .claude/hooks/preflight.sh
    - .claude/hooks/pre-edit-steering.sh
    - .claude/hooks/pre-edit-banned.sh（該当する場合のみ）
    - .claude/hooks/post-fmt.sh
    - .claude/hooks/stop-check.sh

### Hook → Command 参照
- SessionStart Hook → 全コマンドのセッション開始時に動作
- UserPromptSubmit Hook (Preflight 層) → 全ターンで動作。編集を伴わないターン（調査・質問・計画）でもプロジェクト状態を可視化
- PreToolUse Hook (Guard 層) → /add-feature, /fix-bug, /refactor の実装ステップで動作。パス時は `[guard] PASS` で可視化
- PostToolUse Hook (Report 層) → /add-feature, /fix-bug, /refactor 等の実装系で動作、変更時のみ報告
- Stop Hook (Report 層) → 全コマンドのターン終了時に動作、問題時のみ WARN
```

### Step 13: 完了通知

```
Phase 6 完了です。

設定した Hook: 5 種（3 層構成）

【Preflight 層】
1. UserPromptSubmit → preflight.sh
   → 毎ターン .steering/ 状態・git 状態・reimagine 適用状態を動的チェック
   → 出力: [preflight] task: ... / [preflight] git: ...

【Guard 層】
2. PreToolUse → pre-edit-steering.sh + pre-edit-banned.sh
   → 実装ファイル編集時に [guard] PASS or BLOCKED を明示
   → 出力: [guard] PASS: ... / [guard] BLOCKED: ...

【Report 層】
3. PostToolUse → post-fmt.sh
   → Edit/Write 後に format 実行、変更時のみ報告
   → 出力: [fmt] ... applied（整形不要時は無言）
4. Stop → stop-check.sh
   → セッション終了時に clippy/tsc チェック
   → 出力: [stop] WARN: ...（問題時のみ）

【情報表示】
5. SessionStart → session-start.sh
   → セッション開始時にプロジェクト情報を表示

次のステップ:
1. `/clear` でセッションをリセット
2. SessionStart Hook + Preflight Hook が動作することを確認
3. `/verify-setup` を実行して全構築物の整合性チェック
```

## 完了条件

- [ ] `.claude/hooks/session-start.sh` が作成され、実行権限がある
- [ ] `.claude/hooks/preflight.sh` が作成され、実行権限がある
- [ ] `.claude/hooks/pre-edit-steering.sh` が作成され、実行権限がある
- [ ] `.claude/hooks/post-fmt.sh` が作成され、実行権限がある
- [ ] `.claude/hooks/stop-check.sh` が作成され、実行権限がある
- [ ] `.claude/settings.json` に 5 種類の Hook が設定され、全 hook が `"type": "command"` に統一されている
- [ ] `preflight.sh` が毎ターン動的にプロジェクト状態を表示する（固定文言 echo ではない）
- [ ] `preflight.sh` が常に `exit 0` で終了し、BLOCK しない
- [ ] PreToolUse がパス時に `[guard] PASS: ...` を出力する（無言通過しない）
- [ ] PreToolUse が実装ファイルのみを対象とし、docs/ やテストファイルをブロックしない
- [ ] PostToolUse (`post-fmt.sh`) が `--check` で先判定し、変更時のみ `[fmt] ... applied` を 1 行出す
- [ ] Stop (`stop-check.sh`) の出力が `>/dev/null 2>&1` で抑制され、問題時のみ WARN を出す
- [ ] 全 hook の出力が `[preflight]` / `[guard]` / `[fmt]` / `[stop]` プレフィックスで統一されている
- [ ] Grill me ステップ実施済み
- [ ] 進捗ファイルが更新されている

## アンチパターン

- ❌ UserPromptSubmit に固定文言の echo を使う（動的チェックの `preflight.sh` を使うこと。固定文言は情報密度ゼロで、hook が動いているかの可視化にもならない）
- ❌ `preflight.sh` で BLOCK する（Preflight 層は警告のみ。常に `exit 0`。BLOCK は Guard 層の責務）
- ❌ PreToolUse のパス時に無言で通過する（`[guard] PASS: ...` を出力すること。無言 = hook が動いたかどうかユーザーから見えない）
- ❌ PostToolUse で format 変更の有無を報告しない（`--check` で先判定して、変更時のみ 1 行報告するのが正解）
- ❌ Stop Hook の clippy / tsc 出力を抑制しない（数万トークン消費する。詳細はユーザーが手動で見る前提）
- ❌ `"type": "prompt"` と `"type": "command"` を混在させる（全 command 型に統一）
- ❌ 出力プレフィックスを付けない、または `⛔`/`⚠️` 等の絵文字だけで識別しようとする（`[guard]` `[fmt]` 等の機械可読なプレフィックスが必要）
- ❌ PreToolUse で意味解釈が必要な判定をしようとする（「サブエージェントを使うべきだったか」等は hook では判定不能）
- ❌ SessionStart Hook で大量の出力をする
- ❌ 既存の settings.json を上書きする
- ❌ Hook の動作テストを省略する（特に Guard 層の PASS が出ることは必ず確認する）
