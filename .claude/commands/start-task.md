---
description: >
  新規タスクの作業を開始する。.steering/[YYYYMMDD]-[task-name]/ を作成し、
  requirement.md, design.md, tasklist.md のテンプレートを配置して
  初期ヒアリングを行う。実装作業を始める前に必ず最初に実行する。
allowed-tools: Write, Bash(mkdir *), Bash(date *), Bash(cp *), Read
---

# /start-task

## 目的

新規タスクの開始時に作業記録ディレクトリを作成し、必須ファイルを配置して初期要件を記録する。

## 実行フロー

### Step 1: タスク名の取得

ユーザーにタスク名を尋ねる:

> 「これから始めるタスクの名前を教えてください。kebab-case で 5-30 文字程度を推奨します。例: `add-user-authentication`, `fix-login-bug`」

### Step 2: 日付の取得

```bash
date +%Y%m%d
```

### Step 3: ディレクトリ作成

```bash
mkdir -p .steering/[YYYYMMDD]-[task-name]
```

### Step 4: テンプレートのコピー

```bash
cp .steering/_template/requirement.md .steering/[YYYYMMDD]-[task-name]/
cp .steering/_template/design.md .steering/[YYYYMMDD]-[task-name]/
cp .steering/_template/tasklist.md .steering/[YYYYMMDD]-[task-name]/
```

### Step 5: requirement.md の初期記入

ユーザーに以下を順番に質問（一度に複数質問しない）:

1. このタスクの背景は何ですか?
2. ゴール（完了条件）は何ですか?
3. スコープに含まれるものは?
4. スコープに含まれないものは?
5. 受け入れ条件をリストで挙げてください

回答を requirement.md に Edit ツールで記入する。

### Step 6: タスクの種類の判定

ユーザーに尋ねる:

> 「このタスクは以下のどれに該当しますか?
> 1. 新機能追加 → 次に `/add-feature` を実行
> 2. バグ修正 → 次に `/fix-bug` を実行
> 3. リファクタリング → 次に `/refactor` を実行
> 4. その他」

### Step 6.5: 破壊と構築の適用判断

ユーザーに尋ねる:

> 「このタスクは以下のいずれかに該当しますか?
> - アーキテクチャや設計判断を伴う
> - 公開 API / 外部インターフェースを定義する
> - 再現や原因特定が難しいバグ
> - 複数の実装案が考えられ、どれが最良か自明でない
>
> 該当する場合、プラン作成後に `/reimagine` を起動して初回案を破棄・再生成し、
> 2案を比較してから実装に入ることを強く推奨します。
> 自明な実装・小さなリファクタ・ドキュメント更新などでは不要です。」

回答を `.steering/[現在のタスク]/requirement.md` の末尾にメモ:

```markdown
## 運用メモ
- 破壊と構築（/reimagine）適用: Yes / No
- 理由: [ユーザーの回答]
```

### Step 7: 完了通知

```
タスク `.steering/[YYYYMMDD]-[task-name]/` を作成しました。

作成ファイル:
- requirement.md (記入済み)
- design.md (空)
- tasklist.md (空)

次のステップ: 上記で選択したコマンド (`/add-feature` / `/fix-bug` / `/refactor`) を実行してください。
```

## 制約

- ヒアリングを省略しない
- requirement.md の記入を省略しない
- 一度に複数の質問をしない
