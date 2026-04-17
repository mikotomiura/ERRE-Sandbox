---
description: >
  直近の git 変更を多角的にレビューする。code-reviewer と security-checker を
  起動し、結果を統合して報告する。コミット前、PR 作成前に実行する。
allowed-tools: Read, Bash(git *), Task
---

# /review-changes

## 現在の状況

$SHELL_PREPROCESS: git status --short 2>/dev/null || echo "(git 管理外)"

## 変更統計

$SHELL_PREPROCESS: git diff --stat HEAD 2>/dev/null || echo "(変更なし)"

## 実行フロー

### Step 1: 変更の有無確認

上記の動的データから変更を確認。変更がない場合は中断:

> 「変更がありません。レビュー対象がないため終了します。」

### Step 2: code-reviewer の起動

`code-reviewer` サブエージェントを起動:

> Task: code-reviewer で直近の git diff をレビュー。HIGH/MEDIUM の指摘を優先的に。

### Step 3: security-checker の起動

外部入力を扱う変更や、認証/認可に関わる変更がある場合、`security-checker` を起動:

> Task: security-checker で変更内容のセキュリティリスクを調査。

### Step 4: 結果の統合

両エージェントからのレポートを統合し、以下の形式で表示:

```markdown
## 変更レビュー結果

### 変更概要
- 変更ファイル数: N
- 追加行数: +N
- 削除行数: -N

### CRITICAL/HIGH（必須対応）
[統合した指摘]

### MEDIUM（推奨対応）
[統合した指摘]

### LOW（任意対応）
[統合した指摘]

### 良かった点
[code-reviewer が評価した点]
```

### Step 5: ユーザーへの提案

- CRITICAL/HIGH があれば: 「これらを修正してから commit してください」
- なければ: 「commit して問題ありません」

## 制約

- 全レポートを生で流さない（統合・要約する）
- 重要な指摘を見落とさない
- 「問題なし」で終わらせる場合も理由を述べる
