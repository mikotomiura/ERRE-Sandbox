# T02 setup-macbook

## 背景

Claude Code 環境 (Phase 0-7) は完了し、`.steering/20260418-implementation-plan/`
で MVP/本番構築の全タスクが定義された。MacBook Air M4 は本プロジェクトの
**マスター機** (Claude Code CLI + Godot + PDF 閲覧 + Python スキーマ/UI) として
全タスクの起動起点となるが、実装に必要なツールチェインは未整備。

実環境のプロービング結果 (2026-04-18):

- ✅ Xcode Command Line Tools (`/Library/Developer/CommandLineTools`)
- ✅ uv (`/Users/johnd/.local/bin/uv`) — MASTER-PLAN 既定どおり導入済み
- ✅ python3 (python.org 経由 3.11) — ただし `uv python install 3.11` で
     uv 管理下の Python も必要
- ✅ git (`/usr/bin/git`)
- ✅ node (`/usr/local/bin/node`)
- ❌ Homebrew (`/opt/homebrew/bin/brew` が無い)
- ❌ gh, jq, poppler, Godot (brew 経由のため同時に未導入)

## ゴール

MacBook Air M4 で以下が可能な状態を作る:

1. Homebrew 経由で Godot 4.4 / poppler / gh / jq / git が利用できる
2. uv 管理の Python 3.11 が利用できる (`uv python list` で 3.11 がヒット)
3. 推奨 VS Code 拡張 (ruff / python / godot-tools) が導入されている (任意)
4. 次タスク T03 (pdftotext 化) と T04 (pyproject scaffold) が即着手可能

## スコープ

### 含むもの

- Homebrew (arm64 / /opt/homebrew) のインストール
- `brew install --cask godot`
- `brew install poppler gh jq` (git は既存のままで可)
- `uv python install 3.11` (python.org 版とは別)
- VS Code / Cursor のいずれかと、ruff / python / godot-tools 拡張 (任意)
- `.steering/_setup-progress.md` の MVP 実装フェーズ進捗更新

### 含まないもの

- `pyproject.toml` の作成・依存解決 → T04
- `godot_project/` の初期化 → T15
- `docs/_pdf_derived/erre-sandbox-v0.2.txt` の生成 → T03
- G-GEAR 側の環境構築 → T01
- Python 依存ライブラリ (pydantic, fastapi 等) のインストール → T04

## 受け入れ条件

- [ ] `which brew` がヒットし `brew --version` が 4.x 以上
- [ ] `which godot` がヒット (または `/Applications/Godot.app` が存在)
- [ ] `which pdftotext` がヒット (poppler)
- [ ] `which gh` がヒット、`gh --version` が 2.x 以上
- [ ] `which jq` がヒット
- [ ] `uv python list --only-installed` に 3.11.x が含まれる
- [ ] (任意) `code --list-extensions` に ruff / python / godot-tools が含まれる
- [ ] `.steering/_setup-progress.md` に T02 完了を追記
- [ ] `.steering/20260418-setup-macbook/` の tasklist.md が全チェック済み
- [ ] 作業ブランチ `feature/setup-macbook` を push、PR 作成までは T02 内、
      main マージは plan ブランチの内容と合わせて行う

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §7 (MacBook 側アクション)
- `.steering/20260418-implementation-plan/decisions.md` (判断 2, 判断 3, 判断 6)
- `docs/architecture.md` §2-4 (2 拠点構成)
- `docs/development-guidelines.md` §Git ワークフロー

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **No**
- 理由: 環境構築はアーキテクチャ判断を伴わず、実装案が自明 (brew + uv のみ)
- タスク種類: その他 (環境構築 / セットアップ)
