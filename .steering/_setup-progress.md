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
- [ ] **Phase 4: /setup-agents** — サブエージェント群
  - 完了日時: -
  - 作成エージェント: -
- [ ] **Phase 5: /setup-commands** — ワークフローコマンド群
  - 完了日時: -
  - 作成コマンド: -
- [ ] **Phase 6: /setup-hooks** — Hook 群
  - 完了日時: -
  - 作成 Hook: -
- [ ] **Phase 7: /verify-setup** — 整合性検証
  - 完了日時: -
  - 検証結果: -

## 次に実行すべきコマンド

`/setup-agents`

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

### Skill → Agent 参照
（/setup-agents 完了時に記入）

### Agent → Command 参照
（/setup-commands 完了時に記入）

### Hook → Command 参照
（/setup-hooks 完了時に記入）
