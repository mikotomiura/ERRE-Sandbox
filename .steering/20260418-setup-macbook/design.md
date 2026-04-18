# 設計

## 実装アプローチ

MASTER-PLAN §7 に従い、MacBook Air M4 (arm64) へ段階的にツールを導入する。

**順序**:
1. Homebrew インストール (sudo 対話あり、一度だけ)
2. `eval "$(/opt/homebrew/bin/brew shellenv)"` を `~/.zprofile` に追記
   (新シェルで `brew` が PATH に載る)
3. `brew install poppler gh jq` (CLI)
4. `brew install --cask godot` (GUI アプリ、~100MB)
5. `uv python install 3.11` (uv 管理下の Python)
6. (任意) VS Code / Cursor の拡張導入
7. `.steering/_setup-progress.md` に T02 完了を追記
8. `feature/setup-macbook` ブランチを commit → push → PR 作成

**中断・再開**: Homebrew 以外は冪等。途中失敗しても個別にリトライ可能。

## 変更対象

### 修正するファイル

- `.steering/_setup-progress.md` — 「Phase 8 (MVP 実装開始): T02 setup-macbook 完了」追記
- `~/.zprofile` — Homebrew の `shellenv` 追記 (リポジトリ外)

### 新規作成するファイル

- なし (T02 はツール導入のみ)

### 削除するファイル

- なし

## 影響範囲

- **ローカル環境のみ**。他者のリポジトリ状態には影響しない
- `.steering/_setup-progress.md` のみ Git 管理下の変更、それ以外は OS レイヤ
- `~/.zprofile` 変更により新しいシェルの PATH が変わる (brew が見えるようになる)

## 既存パターンとの整合性

- MASTER-PLAN §7.1-7.2 のコマンドをそのまま実行
- `.steering/_setup-progress.md` への追記は Phase 0-7 の記録スタイルに合わせる
- git ブランチ命名は `feature/setup-macbook` (Conventional Branch、`development-guidelines.md` §Git)

## テスト戦略

環境構築タスクなので単体/統合テストは該当しない。代わりに **検証コマンド** で合否判定する:

```bash
# 受け入れ条件の機械的検証
brew --version
godot --version 2>&1 || ls /Applications/Godot.app
pdftotext -v 2>&1 | head -1
gh --version | head -1
jq --version
uv python list --only-installed | grep -E '^\s*cpython-3\.11'
```

すべてが非エラー終了することを確認する。

## ロールバック計画

- Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"`
- 個別パッケージ: `brew uninstall <name>` / `brew uninstall --cask godot`
- uv の Python: `uv python uninstall 3.11`
- `~/.zprofile` の Homebrew 行は手動削除
- Git 変更: `git checkout -- .steering/_setup-progress.md` (commit 前なら)、
  commit 後は `git revert <hash>`
