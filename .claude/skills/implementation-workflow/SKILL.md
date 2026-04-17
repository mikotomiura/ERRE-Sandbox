---
name: implementation-workflow
description: >
  コード実装タスクの共通骨格。新機能追加・バグ修正・リファクタリングの
  いずれかを行う時、まずこの Skill を参照してから作業を始める。
  /add-feature・/fix-bug・/refactor コマンドから必ず参照される。
  .steering/ への記録・ユーザー承認・サブエージェント呼び出しのタイミングを定義する。
  src/erre_sandbox/ 配下の .py ファイルを変更する全タスクに適用。
  調査→設計→実装→テスト→レビューの流れと各ステップでの確認ポイントを提供する。
allowed-tools: Read, Edit, Glob, Grep
---

# Implementation Workflow

## このスキルの目的

`/add-feature`, `/fix-bug`, `/refactor` に共通する骨格を一箇所に集約し、
各コマンドが特殊制約だけに集中できるようにする。
骨格を飛ばして実装に入ることはアンチパターン (→ `anti-patterns.md` 参照)。

## 共通ステップ

### Step A: プロジェクト理解（スキップ禁止）

以下を Read する:

```
CLAUDE.md
docs/architecture.md
docs/development-guidelines.md
docs/repository-structure.md
.steering/[現在のタスク]/requirement.md   ← 存在する場合
```

### Step B: 既存パターンの調査

`file-finder` サブエージェントを起動:
> 「[対象機能] に類似する既存実装を `src/erre_sandbox/` から検索してください」

`impact-analyzer` サブエージェントを起動:
> 「[変更対象ファイル] を変更した場合の影響範囲を分析してください」

`architecture-rules` Skill を参照し、変更がレイヤー依存方向に違反しないか確認。

### Step C: 設計記録（ユーザー承認必須）

`.steering/[YYYYMMDD]-[task-name]/design.md` に記入:

```markdown
## アプローチ / 修正方針
[具体的な実装方針]

## 変更対象ファイル
- src/erre_sandbox/[module]/[file].py
- tests/test_[module]/test_[file].py

## 既存パターンとの整合性
[同様のパターンがある場合、どれを参考にするか]

## テスト戦略
[単体テスト / 統合テスト / TDD 適用範囲]

## 関連する Skill
- [skill-name] — 理由
```

**ユーザーに設計の承認を求める。承認なしに Step D へ進まない。**

### Step D: tasklist の作成

`.steering/[YYYYMMDD]-[task-name]/tasklist.md` にチェックボックス形式で列挙。
各タスクは **30 分以内で完了できる粒度** に分割。

```markdown
## タスクリスト

- [ ] test_[feature].py を先に書く (TDD 対象の場合)
- [ ] src/erre_sandbox/[module]/[file].py を実装
- [ ] uv run pytest tests/test_[module]/ が通ることを確認
- [ ] uv run ruff check src/ tests/ が通ることを確認
- [ ] .steering/tasklist.md を更新
```

### Step E: 実装

tasklist の各項目を順番に実装。完了ごとにチェックを更新。

関連 Skill を適宜参照:
- `python-standards` — コーディング規約
- `test-standards` — テストの書き方
- `error-handling` — asyncio エラー処理
- `architecture-rules` — インポート方向の確認

**コンテキスト 50% 超で `/smart-compact` を実行してから継続。**

### Step F: テストと検証

`test-runner` サブエージェントを起動、または直接実行:

```bash
uv run pytest tests/
uv run ruff check .
uv run ruff format --check .
```

失敗があれば `test-analyzer` サブエージェントで原因分析し、
全テストが通るまで繰り返す。**失敗したまま Step G に進まない。**

### Step G: コードレビュー

`code-reviewer` サブエージェントを起動:
> 「[変更した差分] をレビューしてください。HIGH 指摘は必ず対応、MEDIUM はユーザー判断」

重大度の対応基準:
- **HIGH**: 必ず修正してから次に進む
- **MEDIUM**: ユーザーに確認してから判断
- **LOW**: 次の機会に対応 (blockers.md に記録)

### Step H: セキュリティチェック（該当時のみ）

外部入力・認証・認可・WebSocket メッセージ検証を扱う場合のみ `security-checker` を起動。
CRITICAL/HIGH は必ず対応。

### Step I: ドキュメント更新

必要に応じて更新:
- `docs/functional-design.md` — 新機能の目的・要件が変わった場合
- `docs/architecture.md` — アーキテクチャが変わった場合
- `docs/glossary.md` — ERRE 固有の新しい用語が追加された場合

### Step J: コミット

`git-workflow` Skill を参照してコミット。

```bash
git add [changed-files]
git commit -m "feat(cognition): add DMN-inspired idle reflection

Refs: .steering/[YYYYMMDD]-[task-name]/"
```

## コマンド別の追加制約

| コマンド | 追加する制約 |
|---|---|
| `/add-feature` | Step A〜J をそのまま実行 |
| `/fix-bug` | Step E の前に「回帰テストを先に追加」を挿入 (TDD 順序) |
| `/refactor` | Step B の前に「現状テスト全部グリーン」を確認。実装は小さな単位で Step F と交互に |

## チェックリスト

- [ ] Step A でドキュメント 4 種を Read したか
- [ ] Step C でユーザー承認を得たか
- [ ] Step D で tasklist が 30 分粒度に分割されているか
- [ ] Step F で全テスト通過を確認したか
- [ ] Step G で HIGH 指摘に全対応したか
- [ ] Step J で `Refs:` 付きコミットをしたか

## 補足資料

- `anti-patterns.md` — 骨格を飛ばして実装に入った場合の失敗パターン

## 関連する他の Skill

- `python-standards` — Step E で参照
- `test-standards` — Step D/F で参照
- `git-workflow` — Step J で参照
- `error-handling` — Step E で asyncio エラー処理を書く時
- `architecture-rules` — Step B でレイヤー確認
