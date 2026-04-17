---
description: >
  ワークフロー型のスラッシュコマンド群を .claude/commands/ 配下に構築する。
  start-task, add-feature, fix-bug, refactor, reimagine, review-changes,
  smart-compact, finish-task の 8 つのコマンドを 1 ファイルずつ承認を得ながら作成する。
  各コマンドは Phase 3-4 で作成された Skill と Agent を組み合わせて呼び出す。
  特に /add-feature, /fix-bug, /refactor は implementation-workflow Skill を
  参照する薄い構造とし、共通骨格の重複を排除する。
  /setup-agents の完了後に実行する。
allowed-tools: Read, Write, Glob, Bash(mkdir *), Bash(ls *)
---

# /setup-commands — スラッシュコマンド群構築コマンド

> Phase 5 of 7. Let's think step by step.

## 環境チェックブロック

### Check 1: 進捗ファイル

```bash
cat .steering/_setup-progress.md
```

Phase 4 完了を確認。

### Check 2: Skill と Agent の存在

```bash
ls .claude/skills/
ls .claude/agents/
```

両方が存在することを確認。Commands はこれらを呼び出す。

### Check 3: コンテキスト予算

`/context` で 30% 以下を確認。

## 設計原則

### 1. 単一責任の原則

1 つのコマンドは 1 つの目的に集中。`/develop-application` のような巨大コマンドは作らない。

### 2. 適切な粒度

「1 回の作業セッションで完了する一連の手順」が目安。

### 3. 明確な実行フロー

各ステップで何をするか、どのツールを使うかを具体的に記述。抽象的な指示は避ける。

### 4. Skill と Agent の積極的活用

メインエージェントが直接全部やるのではなく、専門の Skill と Agent に委譲する。

### 5. 共通骨格は Skill に切り出す（DRY の要）

`/add-feature`, `/fix-bug`, `/refactor` に共通する「調査→設計→実装→テスト→レビュー」の
骨格は **コマンドに繰り返し書かない**。Phase 3 で作成した `implementation-workflow` Skill に
一元化し、各コマンドはそれを参照した上で **自分固有の制約・順序変更だけを書く**。
これによりコマンドファイルは薄く保たれ、ワークフロー変更時の修正箇所も1つで済む。

## 実行フロー

### Step 1: 既存 Skill と Agent の把握

`.claude/skills/` と `.claude/agents/` 配下のファイルを Glob で確認。各 Skill と Agent の name を頭に入れる。

### Step 2: ディレクトリ作成

```bash
ls .claude/commands/
```

`/bootstrap` で既に作成されているはず。なければ作成:

```bash
mkdir -p .claude/commands
```

### Step 3: 8 つのコマンドを 1 つずつ作成

> **重要**: 必ず 1 つずつ作成し、各コマンド完成後に **(a) ユーザー承認** + **(b) Grill me ステップ** を実施。

順序: `/start-task` → `/add-feature` → `/fix-bug` → `/refactor` → `/reimagine` → `/review-changes` → `/smart-compact` → `/finish-task`

#### 3.1 `/start-task`

```markdown
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

\`\`\`bash
date +%Y%m%d
\`\`\`

### Step 3: ディレクトリ作成

\`\`\`bash
mkdir -p .steering/[YYYYMMDD]-[task-name]
\`\`\`

### Step 4: テンプレートのコピー

\`\`\`bash
cp .steering/_template/requirement.md .steering/[YYYYMMDD]-[task-name]/
cp .steering/_template/design.md .steering/[YYYYMMDD]-[task-name]/
cp .steering/_template/tasklist.md .steering/[YYYYMMDD]-[task-name]/
\`\`\`

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

\`\`\`
タスク `.steering/[YYYYMMDD]-[task-name]/` を作成しました。

作成ファイル:
- requirement.md (記入済み)
- design.md (空)
- tasklist.md (空)

次のステップ: 上記で選択したコマンド (`/add-feature` / `/fix-bug` / `/refactor`) を実行してください。
\`\`\`

## 制約

- ヒアリングを省略しない
- requirement.md の記入を省略しない
- 一度に複数の質問をしない
```

ユーザー承認 + Grill me。

#### 3.2 `/add-feature`

```markdown
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
```

ユーザー承認 + Grill me。

#### 3.3 `/fix-bug`

```markdown
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

\`\`\`markdown
## バグの原因
[詳細な分析]

## 根本原因
[原因の本質]

## 修正方針
[どう直すか]
\`\`\`

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
```

ユーザー承認 + Grill me。

#### 3.4 `/refactor`

```markdown
---
description: >
  リファクタリングのワークフロー。implementation-workflow Skill の共通骨格を、
  リファクタリング固有の制約（テスト全グリーン前提、小さな段階的変更、
  振る舞い維持）で上書きしながら実行する。
allowed-tools: Read, Edit, Glob, Grep, Bash(git *), Task
---

# /refactor

## 前提条件

- [ ] `/start-task` で作業ディレクトリ作成済み
- [ ] **現状のテストが全てグリーン**（このコマンドはそれを前提に動く）

## 実行フロー

### Step 1: implementation-workflow Skill の読み込み

`.claude/skills/implementation-workflow/SKILL.md` を Read。

### Step 2: リファクタリング固有の前提確認

Skill の Step B に入る前に以下を実施:

#### 2a. 対象の理解
対象ファイルを Read で読み、現状を把握する。

#### 2b. 既存テスト全グリーンの確認（最重要）

`test-runner` で対象に関連するテストを実行:
> Task: test-runner で関連テストを実行。

**赤いテストがある状態でリファクタリングを始めない。** 必ずすべてグリーンの状態から開始。
赤があれば中断し、先にバグ修正（`/fix-bug`）を行うようユーザーに通知。

### Step 3: Skill 共通骨格の実行（以下のオーバーライド付き）

Skill の Step A〜I を実行するが、`/refactor` では以下を上書き:

| 上書き対象 | 内容 |
|---|---|
| Step C（設計） | 「振る舞いを変えないことの保証方法」と「段階的な変更ステップ（小さな単位に分割）」を必ず含める |
| Step D（tasklist） | 各項目は **1 コミット分の最小単位**。大きな変更を 1 項目にまとめない |
| Step E（実装） | 各項目ごとに: 変更→Step F→失敗なら即ロールバック→成功なら git commit→次へ |
| Step F（テスト） | 各変更ステップ直後に必ず実行。通常の「最後に一括」ではなく **交互実行** |
| Step G（レビュー） | 可読性・保守性・設計改善の観点を特に重視 |

### Step 4: 完了処理

`/finish-task` を実行する。

## 制約

- **振る舞いを変える変更は含めない**（リファクタリングの定義違反）
- 既存テストを変更しない（新規追加は OK）
- 大きな変更を一度に行わない（Step E の交互実行を徹底）
- テストが赤い状態でリファクタリングを始めない
- バグ修正や新機能追加を混ぜない（別タスクに分離）
```

ユーザー承認 + Grill me。

#### 3.5 `/reimagine`（破壊と構築）

```markdown
---
description: >
  プラン段階での「破壊と構築」を実行する。現在の design.md を一旦退避し、
  初回案を意図的に破棄してゼロから再生成した案と並べて比較、
  採用案（または両者のハイブリッド）を決定してから実装に入る。
  アーキテクチャ判断、公開 API 設計、難しいバグ、複数案が考えられる設計で起動する。
  実装着手後には使わない（副作用の巻き戻しが困難なため）。
allowed-tools: Read, Write, Edit
---

# /reimagine

## 目的

初回のプランに対する確証バイアスを排除する。同じ要件に対してゼロから
もう一度考え直し、2 案を比較してから実装に進むことで、設計の品質を
底上げする。best-of-N 的な再生成の人間版。

## 前提条件

- [ ] `.steering/[現在のタスク]/requirement.md` が記入済み
- [ ] `.steering/[現在のタスク]/design.md` に初回プランが記入済み
- [ ] **まだ実装に着手していない**（着手済みなら使用禁止）

## 実行フロー

### Step 1: 初回案の退避

現在の `design.md` の内容を `design-v1.md` としてリネーム保存:

\`\`\`bash
cp .steering/[現在のタスク]/design.md .steering/[現在のタスク]/design-v1.md
\`\`\`

ユーザーに通知:

> 「初回案を design-v1.md に退避しました。これからゼロから再生成します。」

### Step 2: コンテキストの意図的リセット

メインエージェントは以下を自分に宣言する:

> 「これから同じ要件に対して、先ほどの design-v1.md を **見なかったことにして**
> ゼロから最良案を設計する。初回案の影響を受けないよう、以下を意識する:
> - 初回案の用語・構造を踏襲しない
> - 初回案で採用した技術選定を自動で引き継がない
> - 要件 (requirement.md) だけに立脚する」

### Step 3: v2 案の生成

`requirement.md` のみを Read で読み直し、**初回案を参照せず**に設計する。

新しい `design.md` に記入:
- 実装アプローチ
- 変更対象ファイル
- 既存パターンとの整合性
- テスト戦略

### Step 4: 2 案の比較

`design-v1.md`（初回）と `design.md`（v2）を Read し、以下の形式で比較表を作成して
`.steering/[現在のタスク]/design-comparison.md` に保存:

\`\`\`markdown
## 設計案比較

### v1（初回案）の要旨
[3-5 行で]

### v2（再生成案）の要旨
[3-5 行で]

### 主要な差異
| 観点 | v1 | v2 |
|---|---|---|
| アプローチ | ... | ... |
| 技術選定 | ... | ... |
| 変更規模 | ... | ... |
| テスト戦略 | ... | ... |
| リスク | ... | ... |

### 評価（各案の長所・短所）
...

### 推奨案
[v1 / v2 / ハイブリッド] — 理由:
\`\`\`

### Step 5: ユーザーへの提示と判断

ユーザーに以下を尋ねる:

> 「2 案を比較しました。どれを採用しますか?
> 1. v1（初回案）を採用
> 2. v2（再生成案）を採用
> 3. 両案のハイブリッド（具体的に指定してください）
> 4. どちらも不十分 → もう一度 `/reimagine` を実行」

### Step 6: 採用案を design.md に確定

- v1 採用 → `cp design-v1.md design.md`
- v2 採用 → 現状の design.md をそのまま
- ハイブリッド → Edit で design.md を編集
- 4 を選択 → Step 1 から繰り返し（ただし最大 3 回まで。それ以上は要件定義に問題がある可能性）

最後に採用判断の根拠を design.md 末尾に追記:

\`\`\`markdown
## 設計判断の履歴
- 初回案（design-v1.md）と再生成案（v2）を比較
- 採用: [v1 / v2 / ハイブリッド]
- 根拠: [ユーザーの判断理由]
\`\`\`

### Step 7: 完了通知

> 「破壊と構築が完了しました。採用案が design.md に確定されています。
> 元のワークフロー（`/add-feature` など）の Step C 以降を続行してください。」

## 制約

- 実装に着手した後は使用しない（副作用が巻き戻せない）
- Step 2 の「意図的リセット」を省略しない（省略すると初回案に引きずられる）
- 2 案を「どちらも良い」で終わらせない。必ず採用判断をする
- 最大繰り返し回数は 3 回。それ以上は要件側を見直す

## 使用しない場面

- 自明な実装（CRUD の単純追加、文言変更など）
- 小さなリファクタ
- ドキュメント更新
- 既に実装着手済みのタスク
```

ユーザー承認 + Grill me。

#### 3.6 `/review-changes`

```markdown
---
description: >
  直近の git 変更を多角的にレビューする。code-reviewer と security-checker を
  起動し、結果を統合して報告する。コミット前、PR 作成前に実行する。
  Shell Preprocessing で git の現状を動的に取得する。
allowed-tools: Read, Bash(git *), Task
---

# /review-changes

## 現在の状況
!`git status --short`

## 変更統計
!`git diff --stat HEAD`

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

\`\`\`markdown
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
\`\`\`

### Step 5: ユーザーへの提案

- CRITICAL/HIGH があれば: 「これらを修正してから commit してください」
- なければ: 「commit して問題ありません」

## 制約

- 全レポートを生で流さない（統合・要約する）
- 重要な指摘を見落とさない
- 「問題なし」で終わらせる場合も理由を述べる
```

ユーザー承認 + Grill me。

#### 3.7 `/smart-compact`

```markdown
---
description: >
  重要情報を明示的に保持した compact を実行する。
  単なる /compact ではなく、設計判断、未解決事項、決定事項を必ず保持する。
  コンテキスト使用率が 50% を超えた時、長いセッションで品質劣化を感じた時に実行する。
---

# /smart-compact

## 実行フロー

### Step 1: 現在のコンテキスト確認

ユーザーに `/context` の実行を依頼。

50% 未満の場合:

> 「現在のコンテキスト使用率は [N]% です。compact は不要です。50% を超えてから実行することを推奨します。」

50% 以上の場合は次へ。

### Step 2: タスクの継続性確認

ユーザーに尋ねる:

> 「現在のタスクをこのまま続けますか? それとも別のタスクに切り替えますか?」

- **続ける** → Step 3 へ
- **切り替える** → 「`/clear` を使うことを推奨します。compact ではなく完全リセットの方が次のタスクに適しています。」と通知して終了

### Step 3: 重要情報の確認

ユーザーに尋ねる:

> 「現在のセッションで保持すべき特に重要な情報はありますか? 例えば、特定の設計判断、未解決のバグ、ユーザーから受けた制約など。」

回答を待つ。

### Step 4: compact の実行

以下のプロンプトで compact を実行:

\`\`\`
/compact 以下を必ず保持してください:
(1) このセッションで決定したアーキテクチャ判断とその根拠
(2) 未解決の TODO、ブロッカー、待機中の依存関係
(3) ユーザーが明示的に拒否した実装方針とその理由
(4) 採用したライブラリ・パッケージとバージョン
(5) 実行したテストとその結果
(6) [Step 3 でユーザーが指定した追加の重要情報]

詳細なコード断片、会話の枝葉、解決済みの議論は省略可。
\`\`\`

### Step 5: compact 後の確認

ユーザーに `/context` と `/memory` を実行してもらい、以下を確認:

- 使用率が下がったか
- CLAUDE.md がまだロードされているか
- 必要な情報が保持されているか

## 使用タイミング

- コンテキスト使用率が 50% を超えた時
- 大きな機能実装が完了した直後
- 長いデバッグセッション後
- 方針転換するとき（ただし完全な切り替えは `/clear` を推奨）

## アンチパターン

- ❌ コンテキストが 80% を超えてから実行する（手遅れ）
- ❌ タスクが完全に切り替わる時に使う（その時は `/clear`）
- ❌ Step 3 の重要情報の確認を省略する
```

ユーザー承認 + Grill me。

#### 3.8 `/finish-task`

```markdown
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

実装中にブロッカーが発生した場合は `blockers.md` を作成。
重要な設計判断があった場合は `decisions.md` を作成。

ユーザーに尋ねる:

> 「このタスクで特筆すべきブロッカーや重要な設計判断はありましたか?
> あれば blockers.md / decisions.md に記録します。」

### Step 4: 最終レビュー

`/review-changes` を呼び出す:

> /review-changes を実行してください。

CRITICAL/HIGH の指摘があれば対応する。

### Step 5: テスト実行

`test-runner` を起動:

> Task: test-runner で全テストを実行。

すべて通ることを確認。

### Step 6: コミットメッセージの提案

ユーザーに提案:

\`\`\`
[type]: [短い説明]

- 変更内容 1
- 変更内容 2
- 変更内容 3

Refs: .steering/[YYYYMMDD]-[task-name]/
\`\`\`

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

\`\`\`
タスク完了です!

作成・更新したファイル:
- .steering/[YYYYMMDD]-[task-name]/requirement.md
- .steering/[YYYYMMDD]-[task-name]/design.md
- .steering/[YYYYMMDD]-[task-name]/tasklist.md
- (blockers.md, decisions.md があれば)
- (実装したコードファイル)

次のタスクを始める前に `/clear` でセッションをリセットすることを強く推奨します。
\`\`\`

## 制約

- テストが失敗している状態で完了しない
- CRITICAL/HIGH の指摘を残したまま完了しない
- .steering の記録を省略しない
- ユーザー承認なしで commit しない
```

ユーザー承認 + Grill me。

### Step 4: 全コマンドの整合性レビュー

```bash
ls -la .claude/commands/
```

すべてのコマンドが作成されたことを確認。

整合性チェック:

- [ ] 単一責任の原則を満たしているか
- [ ] 各コマンドが Skill と Agent を適切に呼び出しているか
- [ ] コマンド間の連携（/start-task → /add-feature → /finish-task）がスムーズか
- [ ] 重複するコマンドはないか
- [ ] アンチパターンが明示されているか

### Step 5: 進捗ファイルの更新

`.steering/_setup-progress.md` の Phase 5 を完了マーク + 相互参照マップ更新:

```markdown
- [x] **Phase 5: /setup-commands** — ワークフローコマンド群
  - 完了日時: [YYYY-MM-DD HH:MM]
  - 作成コマンド:
    - /start-task
    - /add-feature
    - /fix-bug
    - /refactor
    - /reimagine
    - /review-changes
    - /smart-compact
    - /finish-task

### Skill → Command 参照
- implementation-workflow → /add-feature, /fix-bug, /refactor（共通骨格）
- test-standards → /add-feature, /fix-bug, /refactor（Step F/tasklist 参照）

### Agent → Command 参照
- file-finder → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- impact-analyzer → implementation-workflow 経由で /add-feature, /fix-bug, /refactor
- code-reviewer → implementation-workflow 経由で全実装系 + /review-changes, /finish-task
- security-checker → /add-feature (Step H), /review-changes
- test-runner → implementation-workflow 経由で全実装系 + /refactor の交互実行 + /finish-task
- test-analyzer → implementation-workflow 経由で /add-feature, /fix-bug
- log-analyzer → /fix-bug (Step 2b)
```

### Step 6: 完了通知

```
Phase 5 完了です。

作成したコマンド: 8 個
- ライフサイクル: /start-task, /finish-task
- ワークフロー: /add-feature, /fix-bug, /refactor
- 品質担保: /reimagine（破壊と構築）, /review-changes
- ユーティリティ: /smart-compact

共通骨格は implementation-workflow Skill に集約済み。
各ワークフローコマンドは薄い参照型。

次のステップ:
1. `/clear` でリセット
2. `/model sonnet` を維持
3. `/setup-hooks` を実行
```

## 完了条件

- [ ] 8 つのコマンドすべてが作成されている
- [ ] 各コマンドに明確な実行フローが記述されている
- [ ] 各コマンドが適切に Skill と Agent を呼び出している
- [ ] `/add-feature`, `/fix-bug`, `/refactor` が implementation-workflow Skill を参照する薄い構造になっている
- [ ] `/reimagine` が実装着手前専用である旨が明記されている
- [ ] 各コマンドで Grill me ステップ実施済み
- [ ] 進捗ファイルの相互参照マップ（Skill → Command, Agent → Command）が更新されている

## アンチパターン

- ❌ 複数のコマンドを一気に作成する
- ❌ 抽象的なステップを記述する
- ❌ Skill や Agent を呼ばずに全部メインエージェントで処理する
- ❌ 単一責任を破る
- ❌ 実行フローの順序を曖昧にする
- ❌ Grill me を省略する
- ❌ `/add-feature`, `/fix-bug`, `/refactor` の各コマンド内に共通骨格を再度書く（implementation-workflow Skill に任せる）
- ❌ `/reimagine` を実装着手後に使う（副作用を巻き戻せない）
- ❌ `/reimagine` の Step 2（意図的リセット）を省略して初回案を見ながら再生成する
