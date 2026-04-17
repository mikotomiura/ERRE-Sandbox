# Git Workflow — PR 作成前チェックリスト

## コミット前チェック

```bash
# 1. テスト通過確認
uv run pytest

# 2. lint + format チェック
uv run ruff check .
uv run ruff format --check .

# 3. ステージング内容の確認 (意図しない変更が混入していないか)
git diff --staged

# 4. 変更の要約確認
git status
```

## コミットメッセージテンプレート

```
[type]([scope]): [短い説明 — 英語、命令形]

- 変更内容 1
- 変更内容 2

Refs: .steering/[YYYYMMDD]-[task-name]/
```

### type の選び方

```
新機能を追加した          → feat
バグを直した              → fix
動作は変わらないが綺麗にした → refactor
テストだけ追加した        → test
ドキュメントだけ変更した  → docs
CI・設定・依存を変更した  → chore
GitHub Actions を変更した → ci
```

### scope の選び方

```
schemas.py を変更した              → schemas
memory/ を変更した                 → memory
cognition/ を変更した              → cognition
inference/ を変更した              → inference
world/ を変更した                  → world
ui/ を変更した                     → ui
godot_project/ を変更した          → godot
personas/ を変更した               → personas
erre/ を変更した                   → erre
複数レイヤー横断 (スコープ迷う時) → 最も影響大のモジュールを選ぶ
```

## PR 作成コマンド

```bash
# gh CLI で PR 作成
gh pr create \
  --title "feat(memory): implement Ebbinghaus memory decay" \
  --body "$(cat <<'EOF'
## Summary

- Park et al. (2023) の記憶スコアリング式を実装
- importance × exp(-λ×days) × (1 + recall_count×0.2)
- 単体テストを test_memory/test_retrieval.py に追加

## Test plan

- [ ] `uv run pytest tests/test_memory/` が通る
- [ ] `uv run ruff check src/ tests/` が通る
- [ ] memory decay の傾向が期待通りか手動確認

Refs: .steering/20260420-memory-decay/
EOF
)"
```

## ブランチを最新の main にリベース

```bash
git fetch origin
git rebase origin/main

# コンフリクトが出た場合
git status                    # コンフリクトファイルを確認
# ... 手動解消 ...
git add [resolved-file]
git rebase --continue
```

## リリースタグの打ち方

```bash
# タグ作成
git tag -a v0.5.0 -m "chore: v0.5.0 — 3体 MVP + ブログ公開"

# タグのリモート push (Zenodo が自動で DOI を発行)
git push origin v0.5.0

# 全タグの確認
git tag -l
```

## よくある失敗パターン

| 失敗 | 正しい対処 |
|---|---|
| `git add .` で意図しないファイルを含めた | `git add -p` で部分ステージング |
| コミット後に ruff エラーに気づいた | 新しいコミットで修正 (`--amend` はしない) |
| main に直接 push しようとした | 作業ブランチを切り直して PR 経由でマージ |
| Refs: を書き忘れた | 次のコミットで追記するか、作業記録の README に補足 |
