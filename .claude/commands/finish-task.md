---
description: >
  タスクの完了処理を行う。.steering の最終化、最終レビュー、テスト実行、
  コミット提案までを一連の流れで実行する。
  /add-feature, /fix-bug, /refactor の完了後に必ず実行する。
allowed-tools: Read, Write, Edit, Bash(git *), Task
---

# /finish-task

## 実行フロー

### Step 1: tasklist の最終確認

`.steering/[現在のタスク]/tasklist.md` を Read で確認。

未完了のタスクがあれば、ユーザーに確認:

> 「以下のタスクが未完了です:
> - タスク 1
> - タスク 2
>
> これらを完了させますか? それとも次のタスクに繰り越しますか?」

### Step 2: design.md の最終化

実装中に判明した設計の変更や追加情報を反映する。
当初の設計から変わった点があれば明記する。

### Step 3: blockers.md / decisions.md の作成（任意）

ユーザーに尋ねる:

> 「このタスクで特筆すべきブロッカーや重要な設計判断はありましたか?
> あれば blockers.md / decisions.md に記録します。」

あれば該当ファイルを Write で作成。

### Step 4: 最終レビュー

`/review-changes` を呼び出す:

> /review-changes を実行してください。

CRITICAL/HIGH の指摘があれば対応する。

### Step 5: テスト実行

`test-runner` サブエージェントを起動:

> Task: test-runner で全テストを実行。

すべて通ることを確認。失敗があれば完了しない。

### Step 6: コミットメッセージの提案

ユーザーに提案:

```
[type](scope): [短い説明]

- 変更内容 1
- 変更内容 2
- 変更内容 3

Refs: .steering/[YYYYMMDD]-[task-name]/
```

type の選択肢:
- `feat`: 新機能
- `fix`: バグ修正
- `refactor`: リファクタリング
- `docs`: ドキュメント
- `test`: テスト
- `chore`: その他

### Step 7: コミット実行

ユーザーが承認したら git commit を実行。

### Step 8: 完了通知

```
タスク完了です!

作業記録: .steering/[YYYYMMDD]-[task-name]/
  - requirement.md
  - design.md
  - tasklist.md
  - (blockers.md, decisions.md があれば)

次のタスクを始める前に `/clear` でセッションをリセットすることを強く推奨します。
```

## 制約

- テストが失敗している状態で完了しない
- CRITICAL/HIGH の指摘を残したまま完了しない
- .steering の記録を省略しない
- ユーザー承認なしで commit しない
