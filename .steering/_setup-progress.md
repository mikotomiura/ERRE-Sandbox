# Claude Code 環境構築進捗

> このファイルは構築の進捗を記録する。各 setup-* コマンドが完了するたびに更新される。
> セッションを跨いだ継続のための引き継ぎ情報として機能する。

## プロジェクト概要

- **名称**: ERRE-Sandbox
- **目的**: 歴史的偉人（アリストテレス・カント・ニーチェ・利休・道元など）の認知習慣を、ローカルLLMで駆動される自律エージェント群として3D空間に再実装し、「意図的非効率性」と「身体的回帰」を設計プリミティブとして知的創発を観察する、完全OSS・予算ゼロの研究プラットフォーム
- **技術スタック**: Python / FastAPI / Godot (3D) / Ollama + llama.cpp / sqlite-vec / SGLang
- **チーム規模**: 個人 (1人)
- **重視する品質特性**: 再現可能性, パフォーマンス, 保守性・拡張性, セキュリティ
- **構築開始日**: 2026-04-17
- **仕様書**: ERRE-Sandbox_v0.2.pdf (21ページ, 研究企画書兼技術設計書)

## 構築進捗

- [x] **Phase 0: Bootstrap** (このコマンド)
  - 完了日時: 2026-04-17
  - 備考: 環境チェック完了、git init 実施、ディレクトリ構造作成済み
- [x] **Phase 1: /setup-docs** — 永続ドキュメント
  - 完了日時: 2026-04-17
  - 作成ファイル:
    - docs/functional-design.md
    - docs/architecture.md
    - docs/repository-structure.md
    - docs/development-guidelines.md
    - docs/glossary.md
  - 主要な決定事項:
    - 優先ユースケース: ゲーム開発者向け自律NPC AIミドルウェア
    - ドキュメント言語: 日本語メイン、OSS公開に必要な箇所は英語追加
    - アーキテクチャ: 特定パターンに縛らず、必要に応じて破壊と再構築
    - 全5ドキュメントの横断整合性レビュー完了
- [x] **Phase 2: /setup-claude-md** — CLAUDE.md と .steering
  - 完了日時: 2026-04-17
  - 作成ファイル:
    - CLAUDE.md (87 行)
    - .steering/README.md
    - .steering/_template/ × 5 ファイル (requirement, design, tasklist, blockers, decisions)
  - .gitignore 更新: なし (.steering/ は git 追跡対象)
  - Grill me: 実施済み — 全チェック項目 OK
- [x] **Phase 3: /setup-skills** — Skill 群
  - 完了日時: 2026-04-17
  - 作成 Skill:
    - python-standards (SKILL.md, patterns.md) — Python 3.11 / asyncio / Pydantic v2 / ruff 規約
    - test-standards (SKILL.md, examples.md) — pytest-asyncio / conftest / 埋め込みプレフィックステスト
    - git-workflow (SKILL.md, checklist.md) — Conventional Commits / Refs: / リリースタグ
    - error-handling (SKILL.md, examples.md) — SGLang→Ollama フォールバック / 再接続 / gather
    - architecture-rules (SKILL.md, decision-tree.md) — レイヤー依存 / GPL禁止 / API禁止
    - implementation-workflow (SKILL.md, anti-patterns.md) — 調査→設計→実装→テスト→レビュー骨格
    - project-status (SKILL.md) — 動的 Shell Preprocessing Skill
  - 動的 Skill 数: 1 (project-status)
- [x] **Phase 4: /setup-agents** — サブエージェント群
  - 完了日時: 2026-04-18
  - 作成エージェント:
    - file-finder (sonnet) — ファイル検索・分類専門
    - dependency-checker (sonnet) — 依存関係調査専門
    - impact-analyzer (sonnet) — 変更影響範囲分析専門
    - code-reviewer (opus) — コード品質・可読性レビュー専門
    - test-analyzer (sonnet) — テスト失敗原因分析専門
    - security-checker (opus) — セキュリティリスク監査専門
    - test-runner (haiku) — テスト実行・結果要約専門
    - build-executor (haiku) — ビルド実行・結果要約専門
    - log-analyzer (sonnet) — ログ分析・異常パターン検出専門
- [x] **Phase 5: /setup-commands** — ワークフローコマンド群
  - 完了日時: 2026-04-18
  - 作成コマンド:
    - /start-task
    - /add-feature
    - /fix-bug
    - /refactor
    - /reimagine
    - /review-changes
    - /smart-compact
    - /finish-task
- [x] **Phase 6: /setup-hooks** — Hook 群（3 層構成: Preflight / Guard / Report）
  - 完了日時: 2026-04-18
  - 作成 Hook:
    - SessionStart: .claude/hooks/session-start.sh（動的情報表示）
    - UserPromptSubmit: Preflight 層 / preflight.sh（毎ターン .steering/ 状態・git 状態・reimagine 状態を動的表示、BLOCK せず）
    - PreToolUse: Guard 層 / pre-edit-steering.sh + pre-edit-banned.sh（違反ブロック + パス時 `[guard] PASS` 出力）
    - PostToolUse: Report 層 / post-fmt.sh（Edit/Write 後に ruff format、変更時のみ `[fmt] ruff format applied`）
    - Stop: Report 層 / stop-check.sh（ruff check + mypy、問題時のみ WARN）
  - 出力プレフィックス統一: [preflight] / [guard] / [fmt] / [stop]
  - settings.json: 新規作成（全 hook を `"type": "command"` に統一）
  - 外部スクリプト:
    - .claude/hooks/session-start.sh
    - .claude/hooks/preflight.sh
    - .claude/hooks/pre-edit-steering.sh
    - .claude/hooks/pre-edit-banned.sh
    - .claude/hooks/post-fmt.sh
    - .claude/hooks/stop-check.sh
- [x] **Phase 7: /verify-setup** — 整合性検証
  - 完了日時: 2026-04-18
  - 検証結果: HEALTHY
  - 修正が必要な項目: 3 件 (すべて LOW、運用上問題なし)
  - レポート: .steering/_verify-report-20260418.md

## 次に実行すべきコマンド

`/start-task` で最初の実装タスクを開始

## 各コマンド実行前のチェックリスト

各 setup-* コマンドを実行する前に、以下を必ず確認してください:

1. `/context` で使用率が 30% 以下か
2. 適切なモデルに切り替えてあるか（設計系は Opus、実装系は Sonnet）
3. 前のコマンドが完了し、`/clear` でセッションがリセットされているか
4. このファイル (`.steering/_setup-progress.md`) を Read で読んで進捗を確認したか

## 構築物の相互参照マップ

このセクションは各 setup-* コマンドが完了するたびに更新される。

### Skill リスト
- python-standards
- test-standards
- git-workflow
- error-handling
- architecture-rules
- implementation-workflow
- project-status (動的)
- llm-inference (動的)
- persona-erre
- godot-gdscript
- blender-pipeline

### Skill → Agent 参照
- test-standards → code-reviewer, test-analyzer
- python-standards → code-reviewer
- error-handling → code-reviewer, security-checker, log-analyzer
- architecture-rules → impact-analyzer, code-reviewer, security-checker
- git-workflow → dependency-checker
- llm-inference → code-reviewer, log-analyzer, security-checker
- persona-erre → code-reviewer, impact-analyzer
- godot-gdscript → code-reviewer, impact-analyzer
- blender-pipeline → security-checker, code-reviewer

### Skill → Command 参照
- implementation-workflow → /add-feature, /fix-bug, /refactor（共通骨格）
- test-standards → /add-feature, /fix-bug, /refactor（Step F/tasklist 参照）
- llm-inference → /add-feature, /fix-bug（inference/ 関連タスク時）
- persona-erre → /add-feature（personas/ や schemas.py の ERREMode 関連タスク時）
- godot-gdscript → /add-feature（godot_project/ 関連タスク時）

### Agent → Command 参照
- file-finder → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- impact-analyzer → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- code-reviewer → implementation-workflow 経由で全実装系 + /review-changes, /finish-task
- security-checker → /add-feature (Step H), /review-changes
- test-runner → implementation-workflow 経由で全実装系 + /refactor 交互実行 + /finish-task
- test-analyzer → implementation-workflow 経由で /add-feature, /fix-bug
- log-analyzer → /fix-bug (Step 2b)

### Hook → Command 参照
- SessionStart Hook → 全コマンドのセッション開始時に動作
- UserPromptSubmit Hook (Preflight 層) → 全ターンで動作。編集を伴わないターン（調査・質問・計画）でもプロジェクト状態を可視化
- PreToolUse Hook (Guard 層) → /add-feature, /fix-bug, /refactor の実装ステップで動作。パス時は `[guard] PASS` で可視化
- PostToolUse Hook (Report 層) → /add-feature, /fix-bug, /refactor 等の実装系で動作、変更時のみ報告
- Stop Hook (Report 層) → 全コマンドのターン終了時に動作、問題時のみ WARN
