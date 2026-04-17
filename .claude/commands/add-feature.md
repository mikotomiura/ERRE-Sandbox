---
description: >
  新機能追加のワークフロー。implementation-workflow Skill の共通骨格
  （調査→設計→実装→テスト→レビュー）をそのまま実行する。
  /start-task で作業ディレクトリを作成した後に実行する。
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git *), Task
---

# /add-feature

## 目的

新機能を追加する際の標準ワークフローを実行する。共通骨格は
`implementation-workflow` Skill に集約されているので、このコマンドは
**Skill 参照と新機能追加固有の留意点のみ**を記述する。

## 前提条件

- [ ] `/start-task` で `.steering/[YYYYMMDD]-[task-name]/` が作成済み
- [ ] requirement.md に要件が記入済み
- [ ] `破壊と構築（/reimagine）適用: Yes` の場合、Step 2 の後に `/reimagine` を実行

## 実行フロー

### Step 1: implementation-workflow Skill の読み込み

`.claude/skills/implementation-workflow/SKILL.md` を Read で読む。
以降の Step A〜I はこの Skill に従って実行する。

### Step 2: 共通骨格の実行（Step A〜I）

Skill の Step A〜I をそのまま実行する。`/add-feature` は **オーバーライドなし**。

ただし以下の点に特に注意:

- **Step B**: 類似機能の既存実装を必ず探す。ゼロから考えず既存パターンに乗る。
- **Step C**: 設計承認を得る前に Step D へ進まない。
- **Step H**: 外部入力（ユーザー入力、API、ファイルアップロード）を扱う場合、
  security-checker を必ず起動。
- **Step I**: 新機能は `docs/functional-design.md` への追記が必須。
  新用語があれば `docs/glossary.md` も更新。

### Step 3: 完了処理

ユーザーに通知:

> 「実装が完了しました。`/finish-task` を実行して作業を完了してください。」

## 制約

- Skill の Step C の設計承認を得ずに Step E に進まない
- Skill の Step F のテストが失敗したまま Step G に進まない
- Skill の Step G の HIGH 指摘を放置しない
- 外部入力を扱う場合に Step H を省略しない
