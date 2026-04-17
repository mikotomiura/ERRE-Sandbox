---
description: >
  バグ修正のワークフロー。implementation-workflow Skill の共通骨格を、
  バグ修正固有の制約（再現確認、TDD 順序、最小変更）で上書きしながら実行する。
  /start-task で作業ディレクトリを作成した後に実行する。
allowed-tools: Read, Edit, Glob, Grep, Bash(git *), Task
---

# /fix-bug

## 前提条件

- [ ] `/start-task` で作業ディレクトリ作成済み
- [ ] `破壊と構築（/reimagine）適用: Yes` の場合、バグ原因特定後に `/reimagine` を実行

## 実行フロー

### Step 1: implementation-workflow Skill の読み込み

`.claude/skills/implementation-workflow/SKILL.md` を Read。

### Step 2: バグ固有の前処理

Skill の共通骨格に入る前に、以下を実施。

#### 2a. バグの再現と理解

ユーザーから以下を聞く（一度に複数質問しない）:
- 再現手順
- 期待される動作
- 実際の動作
- エラーメッセージ（あれば）
- 発生環境

これらを `.steering/[現在のタスク]/requirement.md` に Edit で追記。

#### 2b. ログの確認（必要に応じて）

ログがある場合、`log-analyzer` サブエージェントを起動:

> Task: log-analyzer で関連するログを分析。

#### 2c. 原因特定と記録

関連コードを Read で読み原因を特定。`.steering/[現在のタスク]/design.md` に記録:

```markdown
## バグの原因
[詳細な分析]

## 根本原因
[原因の本質]

## 修正方針
[どう直すか]
```

### Step 3: Skill 共通骨格の実行（以下のオーバーライド付き）

Skill の Step A〜I を実行するが、`/fix-bug` では以下を上書き:

| 上書き対象 | 内容 |
|---|---|
| Step E 開始前 | **回帰テストを先に追加**（TDD 順序）。このテストは現時点で失敗するはず |
| Step E 本体 | **最小限の変更で修正**。広範囲のリファクタは別タスクに分離 |
| Step F | Step E で追加した回帰テストを含む全テストを実行 |

### Step 4: blockers.md の作成（任意）

このバグのデバッグで困った点があれば `.steering/[現在のタスク]/blockers.md` に記録。
次回似た問題に遭遇した時の参考になる。

### Step 5: 完了処理

`/finish-task` を実行する。

## 制約

- 原因が特定できないまま修正しない
- 回帰テストを追加せずに修正に入らない（TDD 順序の徹底）
- Skill の Step B で影響範囲を確認せずにマージしない
- 「とりあえず動いた」で終わらせない
- バグ修正の範疇を超えるリファクタリングを混ぜない
