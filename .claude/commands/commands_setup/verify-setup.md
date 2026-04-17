---
description: >
  Claude Code 環境構築の整合性を検証する。docs, CLAUDE.md, .steering, skills,
  agents, commands, hooks のすべてが正しく構築され、相互参照が破綻していないかを
  確認し、検証レポートを生成する。/setup-hooks の完了後、または既存環境の
  健全性を確認したい時に実行する。
allowed-tools: Read, Glob, Grep, Bash(ls *), Bash(cat *), Bash(wc *), Bash(find *)
---

# /verify-setup — 環境構築の整合性検証

> Phase 7 of 7. Let's think step by step.
> このコマンドは構築物の最終チェックと健全性の確認を行う。
> 月次メンテナンスでも繰り返し使える。

## 環境チェックブロック

### Check 1: 進捗ファイル

```bash
cat .steering/_setup-progress.md
```

Phase 0-6 がすべて完了マークされていることを確認。
未完了のフェーズがあれば、そのフェーズに戻るよう通知。

## 実行フロー

### Step 1: ファイル存在チェック

以下のすべてが存在することを確認:

```bash
# 永続ドキュメント
ls docs/functional-design.md
ls docs/architecture.md
ls docs/repository-structure.md
ls docs/development-guidelines.md
ls docs/glossary.md

# CLAUDE.md
ls CLAUDE.md

# .steering
ls .steering/README.md
ls .steering/_setup-progress.md
ls .steering/_template/requirement.md
ls .steering/_template/design.md
ls .steering/_template/tasklist.md
ls .steering/_template/blockers.md
ls .steering/_template/decisions.md

# .claude
ls .claude/skills/
ls .claude/agents/
ls .claude/commands/
ls .claude/hooks/
ls .claude/settings.json
```

不足しているファイルがあればリストアップ。

### Step 2: CLAUDE.md の品質チェック

```bash
wc -l CLAUDE.md
```

以下を確認:

- [ ] 行数が 150 以下か
- [ ] docs/ 配下のドキュメントへのポインタが含まれているか
- [ ] `.steering/` の運用ルールが含まれているか
- [ ] モデル選択ルールが含まれているか
- [ ] コンテキスト管理ルールが含まれているか

CLAUDE.md を Read で読んで品質チェック。

### Step 3: docs の整合性チェック

各 docs を Read で読み、以下を確認:

#### functional-design.md と architecture.md
- 機能と技術スタックの対応が取れているか
- 機能設計に登場するコンポーネントが technical 設計に存在するか

#### architecture.md と repository-structure.md
- アーキテクチャのレイヤーが実際のディレクトリ構造に反映されているか
- 想定するコンポーネントが repository-structure に記載されているか

#### development-guidelines.md と repository-structure.md
- テスト方針とテストディレクトリ構造が整合しているか
- 命名規則が両方で同じか

#### glossary.md と他の docs
- 重要な用語が glossary に登録されているか
- 同じ概念が異なる名前で呼ばれていないか

矛盾を発見したらリストアップ。

### Step 4: Skill の品質チェック

```bash
find .claude/skills -name "SKILL.md"
```

各 SKILL.md を Read で読み、以下を確認:

- [ ] frontmatter に name, description, allowed-tools がある
- [ ] description に具体的な技術名が含まれている
- [ ] description に動作トリガー語が含まれている
- [ ] description に「以下の状況で必須参照:」がある
- [ ] 補足ファイル（examples.md, patterns.md など）が存在する
- [ ] 動的 Skill が最低 1 つあるか（`!` 構文を使うもの）

問題のある Skill をリストアップ。

### Step 5: Agent の品質チェック

```bash
find .claude/agents -name "*.md"
```

各エージェント定義を Read で読み、以下を確認:

- [ ] 9 つすべて存在するか:
  - file-finder
  - dependency-checker
  - impact-analyzer
  - code-reviewer
  - test-analyzer
  - security-checker
  - test-runner
  - build-executor
  - log-analyzer
- [ ] 各エージェントに name, description, tools, model がある
- [ ] レポート形式が定義されているか
- [ ] レポートの行数制限が設けられているか
- [ ] 参照すべき Skill が明示されているか
- [ ] モデル選択が用途に合っているか
  - 実行系 (test-runner, build-executor): Haiku
  - 情報収集系: Sonnet
  - レビュー系 (code-reviewer, security-checker): Opus

問題のあるエージェントをリストアップ。

### Step 6: Command の品質チェック

```bash
find .claude/commands -name "*.md"
```

各コマンド定義を Read で読み、以下を確認:

- [ ] 8 つすべて存在するか:
  - /start-task
  - /add-feature
  - /fix-bug
  - /refactor
  - /reimagine
  - /review-changes
  - /smart-compact
  - /finish-task
- [ ] 各コマンドが単一責任を満たしているか
- [ ] 実行フローが具体的か
- [ ] Skill と Agent を適切に呼び出しているか
- [ ] 制約 / アンチパターンが記載されているか

### Step 7: Hook の動作チェック

```bash
ls -la .claude/hooks/
cat .claude/settings.json
```

以下を確認（3 層構成: Preflight / Guard / Report）:

#### ファイル存在と権限
- [ ] `.claude/hooks/session-start.sh` が実行可能か (`-x` 権限)
- [ ] `.claude/hooks/preflight.sh` が存在し実行権限があるか
- [ ] `.claude/hooks/pre-edit-steering.sh` が存在し実行権限があるか
- [ ] `.claude/hooks/post-fmt.sh` が存在し実行権限があるか
- [ ] `.claude/hooks/stop-check.sh` が存在し実行権限があるか
- [ ] `.claude/hooks/pre-edit-banned.sh` が存在する場合、実行権限があるか

#### settings.json の構造
- [ ] JSON 構文が正しいか
- [ ] SessionStart, UserPromptSubmit, PreToolUse, Stop, PostToolUse の 5 種類の Hook があるか
- [ ] **全 hook が `"type": "command"` に統一されているか（`"type": "prompt"` が混在していないこと）**
- [ ] 各 command が `bash .claude/hooks/*.sh` の形式で記述されているか

#### Preflight 層（UserPromptSubmit）
- [ ] `preflight.sh` が動的チェックで実装されているか（固定文言 echo ではないこと）
- [ ] `preflight.sh` が常に `exit 0` で終了し、BLOCK しないか
- [ ] 出力が `[preflight] task: ...` / `[preflight] git: ...` の形式か

#### Guard 層（PreToolUse）
- [ ] `pre-edit-steering.sh` が実装ファイルのみを対象とし、docs/ やテストファイルをブロックしないか（偽陽性チェック）
- [ ] パス時に `[guard] PASS: steering (...)` を出力するか（**無言通過していないこと**）
- [ ] 違反時に `[guard] BLOCKED: ...` を出力するか
- [ ] `pre-edit-banned.sh` が存在する場合、パス時に `[guard] PASS: banned patterns (...)` を出すか

#### Report 層（PostToolUse / Stop）
- [ ] `post-fmt.sh` が `--check` で先判定し、変更時のみ `[fmt] ... applied` を出すか（ノイズ削減チェック）
- [ ] `post-fmt.sh` の実コマンド出力が `>/dev/null 2>&1` で抑制されているか
- [ ] `stop-check.sh` の clippy / tsc 等の出力が `>/dev/null 2>&1` で抑制されているか
- [ ] `stop-check.sh` は問題時のみ `[stop] WARN: ...` を 1 行出すか

#### 出力プレフィックス統一
- [ ] 全 hook の出力が `[preflight]` / `[guard]` / `[fmt]` / `[stop]` のいずれかのプレフィックスで始まっているか
- [ ] Hook のコマンドが存在するツール（cargo, ruff, npx 等）を参照しているか

### Step 8: 相互参照の検証

`.steering/_setup-progress.md` の「構築物の相互参照マップ」を Read で確認し、以下を検証:

#### Skill → Agent
- マップに記載された Skill が実際に存在するか
- 各 Agent が記載通りに Skill を参照しているか（Read で確認）

#### Skill → Command
- `implementation-workflow` Skill が存在し、`/add-feature`, `/fix-bug`, `/refactor`
  の 3 コマンドから実際に Read 参照されているか
- 3 コマンドが共通骨格を再度コピーしておらず、Skill 参照型の薄い構造になっているか

#### Agent → Command
- マップに記載された Agent が各 Command で実際に呼ばれているか

#### Hook → Command
- Hook が各 Command の動作と矛盾しないか

破綻があればリストアップ。

### Step 9: 検証レポートの生成

すべてのチェック結果を統合し、以下の形式でレポートを生成:

```markdown
# Claude Code 環境構築 検証レポート

検証日時: [YYYY-MM-DD HH:MM]

## 総合判定

[✅ HEALTHY / ⚠️ WARNINGS / ❌ ISSUES]

## 各フェーズの状態

### Phase 1: docs ✅
- すべてのファイル存在: ✅
- 整合性: ✅
- 行数: 適切

### Phase 2: CLAUDE.md ✅
- 行数: [N] (上限 150)
- ポインタ型: ✅
- 必須セクション: ✅

### Phase 3: Skills [✅/⚠️/❌]
- Skill 数: [N]
- 静的 Skill: [N]
- 動的 Skill: [N] (最低 1 必要)
- description 品質: [合格 N / 全 N]
- 補足ファイル: [合格 N / 全 N]
- 問題のある Skill:
  - [skill-name]: [問題の説明]

### Phase 4: Agents [✅/⚠️/❌]
- エージェント数: [N] / 9
- レポート形式定義: [合格 N / 全 N]
- Skill 参照: [合格 N / 全 N]
- モデル選択: [合格 N / 全 N]
- 問題のあるエージェント:
  - [agent-name]: [問題の説明]

### Phase 5: Commands [✅/⚠️/❌]
- コマンド数: [N] / 8
- 単一責任: [合格 N / 全 N]
- Skill/Agent 参照: [合格 N / 全 N]
- 問題のあるコマンド:
  - [command-name]: [問題の説明]

### Phase 6: Hooks [✅/⚠️/❌]
**3 層構成 (Preflight / Guard / Report) の整合性**:

- **Preflight 層**:
  - UserPromptSubmit Hook (`preflight.sh`): ✅/❌
  - 動的チェック実装 (固定文言 echo でない): ✅/❌
  - `exit 0` 厳守 (BLOCK しない): ✅/❌
- **Guard 層**:
  - PreToolUse Hook (`pre-edit-steering.sh`): ✅/❌
  - PreToolUse Hook (`pre-edit-banned.sh`, 任意): ✅/❌/N/A
  - `[guard] PASS` 出力 (無言通過でない): ✅/❌
  - 偽陽性なし (docs/ やテストをブロックしない): ✅/❌
- **Report 層**:
  - PostToolUse Hook (`post-fmt.sh`): ✅/❌
  - Stop Hook (`stop-check.sh`): ✅/❌
  - `--check` 先判定で変更時のみ報告: ✅/❌
  - clippy / tsc 出力の抑制 (`>/dev/null 2>&1`): ✅/❌
- **情報表示層**:
  - SessionStart Hook: ✅/❌
- **settings.json**:
  - 全 hook が `"type": "command"` に統一: ✅/❌
  - JSON 構文正常: ✅/❌
- **出力プレフィックス統一** (`[preflight]` / `[guard]` / `[fmt]` / `[stop]`): ✅/❌
- 問題:
  - ...

## 相互参照の整合性

- Skill → Agent: ✅/❌
- Agent → Command: ✅/❌
- Hook → Command: ✅/❌

## 修正が必要な項目

### CRITICAL
- [破壊的な問題があれば]

### HIGH
- [すぐに修正すべき問題]

### MEDIUM
- [計画的に修正すべき問題]

### LOW
- [改善の余地]

## 推奨される次のアクション

1. ...
2. ...
```

### Step 10: 進捗ファイルの更新

`.steering/_setup-progress.md` の Phase 7 を完了マーク:

```markdown
- [x] **Phase 7: /verify-setup** — 整合性検証
  - 完了日時: [YYYY-MM-DD HH:MM]
  - 検証結果: HEALTHY / WARNINGS / ISSUES
  - 修正が必要な項目: [N] 件
```

検証レポートを `.steering/_verify-report-[YYYYMMDD].md` として保存。

### Step 11: 完了通知

```
Phase 7 完了です。すべての構築フェーズが終わりました。

検証結果: [HEALTHY / WARNINGS / ISSUES]

[問題があれば修正リストを表示]

これで Claude Code 環境構築の全工程が完了しました。

日々の運用:
1. 新規タスク開始時: /start-task
2. 設計判断が重い時: /reimagine（プラン段階で初回案を破棄・再生成して比較）
3. 実装中: /add-feature, /fix-bug, /refactor
4. 完了時: /finish-task
5. 月次メンテナンス: /verify-setup を再実行

検証レポートは .steering/_verify-report-[YYYYMMDD].md に保存されました。
```

## 月次メンテナンスとしての使い方

このコマンドは構築直後だけでなく、月に 1 回程度の定期メンテナンスでも実行することを推奨。
時間の経過とともに以下が起こりうる:

- Skill の description が古くなる
- 削除した Agent への参照が残る
- docs の内容が実装と乖離する
- CLAUDE.md が肥大化する

`/verify-setup` を月次で実行することで、これらを早期発見できる。

## 完了条件

- [ ] すべてのフェーズの状態をチェック済み
- [ ] 検証レポートが生成されている
- [ ] 検証レポートが .steering/ に保存されている
- [ ] 進捗ファイルが更新されている
- [ ] ユーザーに修正項目が伝えられている

## アンチパターン

- ❌ ファイル存在チェックだけで終わる
- ❌ 相互参照の検証を省略する
- ❌ 検証レポートを保存しない
- ❌ 問題があっても「だいたい OK」で済ませる
