# タスクリスト

## 準備
- [x] MASTER-PLAN §7 を読み直す
- [x] 実環境プロービング (brew / uv / godot / poppler / gh / jq)
- [x] `.steering/20260418-setup-macbook/` 作成と requirement/design 記入
- [x] `feature/setup-macbook` ブランチ作成

## 実装

### A. Homebrew 導入
- [x] A1. Homebrew インストール (Homebrew 5.1.6 — user 実行で完了)
- [x] A2. `~/.zprofile` に `eval "$(/opt/homebrew/bin/brew shellenv)"` を追記
- [x] A3. `which brew` と `brew --version` 確認 (`/opt/homebrew/bin/brew`, 5.1.6)

### B. CLI ツール
- [x] B1. `brew install gh jq poppler` (依存含め一発で完了)
- [x] B2. `gh 2.90.0` / `jq-1.8.1` / `pdftotext version 26.04.0` 確認

### C. Godot
- [x] C1. `brew install --cask godot` (**4.6.2.stable** — MASTER-PLAN 4.4 指定から更新、decisions 判断 1)
- [x] C2. `/Applications/Godot.app` 存在、`/opt/homebrew/bin/godot` シンボリックリンク確認

### D. uv 管理の Python
- [x] D1. `uv python install 3.11` → cpython-3.11.15-macos-aarch64-none
- [x] D2. `uv python list --only-installed` で確認 (3.11.15 + 既存 3.11.9 共存)

### E. VS Code 拡張
- [x] E1. VS Code.app 導入済み、`code` CLI を `~/.local/bin/code` に symlink (decisions 判断 2)
- [x] E2. `charliermarsh.ruff v2026.40.0` / `geequlim.godot-tools v2.6.1` を追加インストール
- [x] E3. `ms-python.python` は既存

## 検証
- [x] V1. 機械検証 bash を実行、全コマンドが期待出力
- [x] V2. 受け入れ条件 9 件すべて満たす

## レビュー
- [x] R1. design.md は最終化済み (バージョン番号は tasklist に記録)
- [x] R2. decisions.md 作成 (Godot 4.6 / code symlink / python 併存の 3 判断)
- [x] R3. code-reviewer は不要 (コード変更なし、設定/環境のみ)

## ドキュメント
- [x] DOC1. `.steering/_setup-progress.md` に「Phase 8: T02 完了」を追記
- [x] DOC2. docs/ の更新は不要 (T02 のみ)

## 完了処理
- [ ] DONE1. git add + commit (Conventional Commits、scope: chore)
- [ ] DONE2. git push origin feature/setup-macbook
- [ ] DONE3. gh pr create で base=main, head=feature/setup-macbook
      (plan の差分も一緒にマージされる、二重作業回避)
- [ ] DONE4. `/review-changes` で self-review
- [ ] DONE5. `/finish-task` で締め
