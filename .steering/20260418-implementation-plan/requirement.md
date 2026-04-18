# 実装プラン (MVP + 本番構築版 / 2 拠点対応) の外部記憶化

## 背景

Claude Code 環境構築 (Phase 0-7) が 2026-04-18 に完了したが、実装資産
(`src/erre_sandbox/`, `godot_project/`, `personas/`, `tests/`, `pyproject.toml`)
はすべて未着手。

そこでユーザーから以下の要求が提示された:

1. MVP 版 (M2) と本番構築版 (M4→M10-11) の 2 段構成で実装プランを立てる
2. PDF 仕様書 (`ERRE-Sandbox_v0.2.pdf`) の参照方針を確定する
3. G-GEAR (RTX 5060 Ti 16GB) と MacBook Air M4 のそれぞれで取るべきアクションと
   インストール項目を列挙する
4. 「破壊と構築」(`/reimagine`) を計画段階で適用する

本タスクは **その計画を永続化** し、以降のセッション・両機での実装作業で
ブレなく参照できる外部記憶として保持することを目的とする。

## ゴール

- `.steering/20260418-implementation-plan/` に計画一式を記録する
- MASTER-PLAN.md に全文を保持、他のファイルでは要点のみを扱う
- MEMORY.md に参照リンクを追記し、次回セッション以降の検索性を確保

## スコープ

### 含むもの
- MVP (M2) の全 20 タスク (T01-T20) の記録
- 本番構築版 (M4 / M5 / M7 / M9 / M10-11) の段階計画
- G-GEAR / MacBook Air M4 のインストール手順・環境変数・ネットワーク設定
- PDF 資料の扱い方 (pdftotext 化、Read ツール利用)
- 両機間の連携ワークフロー、ブランチ戦略、コンフリクト防止
- リスク一覧 (R1-R13) とその対処
- 「破壊と構築」で採用した判断 (Contract-First、マスター機 = MacBook)

### 含まないもの
- 個別タスク (T01-T20) の詳細 requirement/design/tasklist
  → 実装着手時に `.steering/[YYYYMMDD]-[task-name]/` を別途作成
- コードの実装そのもの (計画段階のため)

## 受け入れ条件

- [x] `.steering/20260418-implementation-plan/requirement.md` 作成
- [x] `.steering/20260418-implementation-plan/design.md` 作成
- [x] `.steering/20260418-implementation-plan/tasklist.md` 作成
- [x] `.steering/20260418-implementation-plan/decisions.md` 作成
- [x] `.steering/20260418-implementation-plan/MASTER-PLAN.md` (全文) 作成
- [x] MEMORY.md に参照リンクを追記

## 関連ドキュメント

- `docs/functional-design.md` — MVP と本番マイルストーンの定義
- `docs/architecture.md` — 2 拠点構成・技術スタック・VRAM 予算
- `docs/repository-structure.md` — 依存方向・ファイル配置
- `docs/development-guidelines.md` — Git ワークフロー・テスト方針
- `docs/glossary.md` — ERRE 用語の統一定義
- `.steering/_setup-progress.md` — Phase 0-7 構築進捗
- `/Users/johnd/.claude/plans/mvp-pdf-macbook-air-wiggly-crescent.md` — 承認済み plan file (セッション外保管)
