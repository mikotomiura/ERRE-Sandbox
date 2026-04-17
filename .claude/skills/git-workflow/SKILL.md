---
name: git-workflow
description: >
  Git 運用ルールとコミットメッセージ規約。git commit / git push /
  ブランチ作成 / PR 作成 / タグ付けを行う時に必須参照。
  Conventional Commits 形式を書く時、feature/ fix/ refactor/ docs/ chore/
  ci/ のブランチを切る時、コミットメッセージに scope を付ける時、
  .steering/ を Refs: で参照する時に自動召喚される。
  main ブランチへの直接 push 禁止・作業ブランチ経由のみという制約を強制する。
  ファイル: .github/workflows/ci.yml, CITATION.cff, pyproject.toml (バージョン管理)。
allowed-tools: Bash(git *), Read
---

# Git Workflow

## このスキルの目的

個人プロジェクトでも一貫した Git 運用を維持し、変更履歴が将来の自分 (と OSS 貢献者)
にとって読みやすい状態を保つ。Conventional Commits で changelog の自動生成を可能にし、
Zenodo DOI 連携のリリースタグを正しく打てる状態を維持する。

## ブランチ戦略

| ブランチ | 用途 |
|---|---|
| `main` | 常にデプロイ可能な状態。直接 push 禁止 |
| `feature/[task-name]` | 新機能 |
| `fix/[task-name]` | バグ修正 |
| `refactor/[task-name]` | リファクタリング |
| `docs/[task-name]` | ドキュメント更新のみ |
| `chore/[task-name]` | CI・設定・依存更新 |

ブランチ名は **kebab-case**。スペース・アンダースコアは使わない。

```bash
# ✅ 良い例
git checkout -b feature/memory-stream-reflection
git checkout -b fix/embedding-prefix-mismatch

# ❌ 悪い例
git checkout -b feature_memory_stream  # アンダースコア
git checkout -b hotfix                 # task-name なし
```

## コミットメッセージ形式 (Conventional Commits)

```
[type]([scope]): [短い説明 — 英語、命令形]

- 変更内容 1 (日本語可)
- 変更内容 2

Refs: .steering/[YYYYMMDD]-[task-name]/
```

### type 一覧

| type | 使う場面 |
|---|---|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `refactor` | 機能変更なしのコード改善 |
| `docs` | ドキュメントのみの変更 |
| `test` | テストの追加・修正 |
| `chore` | CI、設定、依存更新 |
| `ci` | GitHub Actions ワークフロー変更 |

### scope 一覧

`schemas`, `memory`, `cognition`, `inference`, `world`, `ui`, `godot`, `personas`, `erre`

### 例

```
feat(cognition): add DMN-inspired idle reflection window

- peripatos/chashitsu 入室時に importance 閾値未満でも自由連想型内省を発火
- Beaty et al. (2016) の DMN-ECN 動的カップリングの計算論的類推として実装
- sampling_overrides: temperature +0.3, top_p +0.05

Refs: .steering/20260420-reflection-window/
```

```
fix(memory): correct embedding prefix for Ruri-v3-30m

- QUERY_PREFIX を "検索クエリ: " に修正 (以前は空文字列)
- test_embedding_prefix.py を追加して CI でプレフィックス検証

Refs: .steering/20260422-fix-embedding-prefix/
```

```
test(schemas): add validation tests for AgentState fields

- Physical.fatigue が 0〜100 の範囲外でバリデーションエラーを返すことを検証
- ERREMode.mode に無効値を渡した時の動作を確認

Refs: .steering/20260418-test-schemas/
```

## コミットの粒度

- **1 コミット = 1 つの論理的変更**
- 複数のモジュールにまたがる変更でも、目的が1つなら1コミットで OK
- `git add -p` で部分ステージングして意図しない変更を混入させない

```bash
# ✅ 良い例 — 論理的変更単位でコミット
git add src/erre_sandbox/memory/retrieval.py tests/test_memory/test_retrieval.py
git commit -m "feat(memory): implement Ebbinghaus memory decay function

Refs: .steering/20260420-memory-decay/"

# ❌ 悪い例 — 無関係な変更を一緒にコミット
git add .   # デバッグ用 print, 未完成の機能, フォーマット変更が混入
```

## main ブランチへのマージ

1. 作業ブランチで実装・テスト完了
2. `git rebase main` で最新化 (コンフリクト解消)
3. `uv run pytest` が通ることを確認
4. `uv run ruff check .` と `uv run ruff format --check .` が通ることを確認
5. PR 作成 (`gh pr create`) またはローカルで `git merge --no-ff`

## リリースタグ

```
v0.1.0  → スケルトン (M1)
v0.5.0  → 3体 MVP + ブログ (M4〜M5)
v0.9.0  → RC 候補、docs 完全化 (M11)
v1.0.0  → 論文併発 (M12)
```

```bash
# Semantic Versioning に従ってタグ付け
git tag -a v0.1.0 -m "chore: v0.1.0 skeleton release"
git push origin v0.1.0  # Zenodo が自動で DOI を発行
```

## チェックリスト

- [ ] 作業ブランチが `[type]/[task-name]` 形式か
- [ ] `main` に直接 push していないか
- [ ] コミットメッセージが Conventional Commits 形式か
- [ ] `scope` が `schemas/memory/cognition/inference/world/ui/godot/personas/erre` のいずれかか
- [ ] `Refs: .steering/[YYYYMMDD]-[task-name]/` が付いているか
- [ ] `pytest` と `ruff` が通ってからコミットしているか

## 補足資料

- `checklist.md` — PR 作成前の確認リストと `gh pr create` コマンドテンプレート

## 関連する他の Skill

- `implementation-workflow` — Step H (コミット段階) でこの Skill を参照
