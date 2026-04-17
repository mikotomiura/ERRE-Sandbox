---
description: >
  CLAUDE.md と作業記録ディレクトリ .steering/ の構造を構築する。
  CLAUDE.md は 150 行以下のポインタ型ドキュメントとして、docs/ への参照と
  運用ルールだけを記載する。.steering/_template/ にタスク用の 5 ファイル
  テンプレートを配置する。/setup-docs の完了後に実行する。
allowed-tools: Read, Write, Glob, Bash(mkdir *), Bash(wc *), Bash(cat *)
---

# /setup-claude-md — CLAUDE.md と作業記録構造の構築

> Phase 2 of 7. Let's think step by step.

## 環境チェックブロック

### Check 1: 進捗ファイル

```bash
cat .steering/_setup-progress.md
```

Phase 1 が完了マークされていることを確認。されていない場合は中断。

### Check 2: docs/ の存在

```bash
ls docs/
```

5 つのドキュメントすべてが存在することを確認。

### Check 3: コンテキスト予算

`/context` で 30% 以下を確認。

### Check 4: モデル

`/model` で Opus を確認。Sonnet でも実行可能だが Opus 推奨。

## 実行フロー

### Step 1: 既存 docs の精査

`docs/` 配下の 5 つのファイルすべてを Read で読む:

```
docs/functional-design.md
docs/architecture.md
docs/repository-structure.md
docs/development-guidelines.md
docs/glossary.md
```

これらの内容を頭に入れた状態で CLAUDE.md を構築する。CLAUDE.md は **これらへのポインタ** として機能するため、内容を理解していないと適切なポインタが書けない。

### Step 2: CLAUDE.md のドラフト作成

**最重要ルール**: 150 行以下に収める。これを超えそうになったら情報を docs/ に退避する。

以下のテンプレートをベースにプロジェクト固有の内容で埋める:

```markdown
# [プロジェクト名]

## このファイルについて

このファイルは Claude Code がセッション開始時に自動で読み込む指示書です。
詳細な情報は `docs/` 配下の各ドキュメントを参照してください。

このファイルの目的は **Claude が探索を始める起点を示すこと** であり、
プロジェクトの全情報を含むことではありません。

## プロジェクト概要

- **名称**: [プロジェクト名]
- **目的**: [1 行で]
- **主要技術**: [言語、フレームワーク]
- **チーム規模**: [個人 / 小規模 / 中規模]

## セッション開始時の行動規範

タスク/セッション開始時、メインエージェントは以下を **必ずこの順** で実行してください。
全部自分でやろうとしないこと。

1. **コマンド選定**: `.claude/commands/` を glob で確認し、今回の作業に該当する
   スラッシュコマンド（`/start-task`, `/add-feature`, `/fix-bug`, `/refactor` 等）が
   あれば **必ずそれを起動する**。該当コマンドを使わずに作業を始めない。
2. **Skill 参照**: 実装・レビュー・テスト等、該当する Skill があれば
   `.claude/skills/[name]/SKILL.md` を Read で参照してから手を動かす。
3. **サブエージェントへの委譲**: 以下はメインエージェントではなくサブエージェントで実行する。
   - 複数ファイル横断の探索・読み込み → `file-finder`
   - 影響範囲調査 → `impact-analyzer`
   - コードレビュー → `code-reviewer`
   - テスト実行 → `test-runner`
   - セキュリティ確認 → `security-checker`
4. **破壊と構築の判断**: 設計判断・アーキテクチャ選択・難しいバグなど高難度タスクでは
   `/reimagine` をプラン段階で起動し、初回案を一旦破棄してゼロから再生成した案と比較する。

このルールに従うことで、メインエージェントのコンテキストを節約し、各領域の専門性を活かせます。

## 参照すべきドキュメント

作業内容に応じて、必要なドキュメントを Read で読んでください:

| ファイル | いつ読むか |
|---|---|
| `docs/functional-design.md` | 機能の意図や要件を確認したい時 |
| `docs/architecture.md` | アーキテクチャや技術選定を確認したい時 |
| `docs/repository-structure.md` | ファイル配置や命名規則を確認したい時 |
| `docs/development-guidelines.md` | コーディング規約やレビュー基準を確認したい時 |
| `docs/glossary.md` | 用語の意味を確認したい時 |

## 作業記録の運用ルール（重要）

**すべての実装作業は `.steering/` 配下に記録を残してください。**

### ディレクトリ命名規則

\`\`\`
.steering/[YYYYMMDD]-[task-name]/
\`\`\`

例:
- `.steering/20260407-add-user-authentication/`
- `.steering/20260408-fix-login-bug/`

### 各タスクで作成するファイル

| ファイル | 必須/任意 | 内容 |
|---|---|---|
| `requirement.md` | 必須 | 今回の作業の背景、ゴール、受け入れ条件 |
| `design.md` | 必須 | 実装アプローチ、変更対象、テスト戦略 |
| `tasklist.md` | 必須 | チェックボックス形式の具体的タスクリスト |
| `blockers.md` | 任意 | 発生したブロッカーと対処方法 |
| `decisions.md` | 任意 | 重要な設計判断と根拠 |

### 作成タイミング

1. **作業開始時**: `/start-task` コマンドで自動作成（Phase 5 で構築）
2. **実装中**: `tasklist.md` のチェックボックスを更新、必要に応じて追記
3. **作業完了時**: `/finish-task` コマンドで最終化（Phase 5 で構築）

### テンプレート

`.steering/_template/` 配下に各ファイルのテンプレートが配置されています。
新規タスク時はそこからコピーして使ってください。

## モデル選択ルール

| タスク種別 | モデル | 理由 |
|---|---|---|
| Plan Mode、設計判断 | Opus | 推論深度が必要 |
| 実装、テスト、リファクタ | Sonnet | バランス最良 |
| リネーム、フォーマット | Haiku | 速度優先 |
| 大規模変更（10ファイル以上） | Sonnet[1m] | 1M コンテキスト |

## コンテキスト管理ルール

### 黄金律

1. **50% ルール**: 使用率が 50% を超えたら次の区切りで `/smart-compact`
2. **タスク切り替え時は `/clear`**: 文脈が変わるなら `/compact` ではなく `/clear`
3. **`/context` を見る習慣**: セッション開始、実装前、compact 前

### Plan → Execute の徹底

複雑なタスクでは省略しない:
1. `Shift+Tab` 2 回で Plan Mode
2. `/model opus` に切り替え
3. 計画を立てさせる（コードはまだ書かせない）
4. レビューして承認
5. `/model sonnet` で実装

## 禁止事項

- 既存のテストを無断で削除しない
- ドキュメント化されていない設計判断を勝手に変更しない
- `.steering/` への記録を省略しない
- 50% を超えてもセッションを続ける
- 曖昧な指示に対して推測で実装する（質問する）

## 利用可能な独自コマンド

このプロジェクトには以下のスラッシュコマンドが定義されています:

- `/start-task` — 新規タスクの開始
- `/add-feature` — 新機能追加ワークフロー
- `/fix-bug` — バグ修正ワークフロー
- `/refactor` — リファクタリングワークフロー
- `/reimagine` — プラン段階での「破壊と構築」（初回案を破棄し再生成して比較）
- `/review-changes` — 変更レビュー
- `/smart-compact` — 情報保持型 compact
- `/finish-task` — タスク完了処理

詳細は `.claude/commands/` を参照。

## 利用可能なサブエージェント

- 情報収集: `file-finder`, `dependency-checker`, `impact-analyzer`
- レビュー: `code-reviewer`, `test-analyzer`, `security-checker`
- 実行: `test-runner`, `build-executor`, `log-analyzer`

詳細は `.claude/agents/` を参照。
```

### Step 3: 行数チェック

```bash
wc -l CLAUDE.md
```

**150 行を超えていたら** 以下の情報を docs/ に退避することを検討:

- モデル選択ルール → `docs/development-guidelines.md` に追記
- コンテキスト管理ルール → 新規 `docs/claude-code-operations.md` を作成
- 利用可能なコマンド/サブエージェントの一覧 → 削除（`.claude/` を見れば分かる）

100-150 行を目標にする。

### Step 4: ユーザー承認 + Grill me

**ユーザー承認**: 「この CLAUDE.md で問題ないですか?行数は [N] 行です」

**Grill me ステップ**:

> CLAUDE.md を批判的にレビューします:
> - 重複情報はないか? (docs/ にあるものを書いていないか)
> - ポインタとして機能しているか? (内容を抱え込んでいないか)
> - 150 行以下に収まっているか?
> - 毎ターン消費されることを意識した記述になっているか?
> - 「禁止事項」が具体的か? (抽象的な「丁寧に」とか書いていないか)

問題があれば修正。

### Step 5: .steering/ ディレクトリの構築

#### 5.1 .steering/README.md の作成

```markdown
# .steering/

このディレクトリは Claude Code との作業記録を保管します。

## 構造

\`\`\`
.steering/
├── README.md              # このファイル
├── _setup-progress.md     # 環境構築の進捗記録
├── _template/             # 新規タスク用テンプレート
│   ├── requirement.md
│   ├── design.md
│   ├── tasklist.md
│   ├── blockers.md
│   └── decisions.md
└── [YYYYMMDD]-[task-name]/   # 各タスクの作業記録
    ├── requirement.md
    ├── design.md
    ├── tasklist.md
    ├── blockers.md (任意)
    └── decisions.md (任意)
\`\`\`

## 新規タスクの開始

`/start-task` コマンドを使うと、自動的にディレクトリとテンプレートが配置されます。

## ファイルの役割

- **requirement.md** — 何をするか（背景、ゴール、受け入れ条件）
- **design.md** — どうやるか（アプローチ、変更対象、テスト戦略）
- **tasklist.md** — 具体的なタスクのチェックリスト
- **blockers.md** — 詰まったポイントとその解決方法（任意）
- **decisions.md** — 重要な設計判断とその根拠（任意）
```

#### 5.2 _template/ にテンプレートを配置

各ファイルを以下の内容で作成:

**`.steering/_template/requirement.md`**:

```markdown
# [タスク名]

## 背景

なぜこのタスクが必要か。何が問題で、何を解決したいのか。

## ゴール

何を達成すれば「完了」とするのか。

## スコープ

### 含むもの
- ...

### 含まないもの
- ...

## 受け入れ条件

- [ ] 条件 1
- [ ] 条件 2
- [ ] 条件 3

## 関連ドキュメント

- docs/architecture.md の [該当セクション]
- ...
```

**`.steering/_template/design.md`**:

```markdown
# 設計

## 実装アプローチ

採用する方針と、その理由。

## 変更対象

### 修正するファイル
- `path/to/file1.py` — 何を変えるか
- `path/to/file2.py` — 何を変えるか

### 新規作成するファイル
- `path/to/new_file.py` — 役割

### 削除するファイル
- ...

## 影響範囲

この変更が影響する箇所と、その対処。

## 既存パターンとの整合性

既存のコードベースのどのパターンに従うか。

## テスト戦略

- 単体テスト: 何をテストするか
- 統合テスト: 何をテストするか
- E2E テスト: 必要か

## ロールバック計画

変更が問題を起こした場合の戻し方。
```

**`.steering/_template/tasklist.md`**:

```markdown
# タスクリスト

## 準備
- [ ] 関連する docs を読む
- [ ] 影響範囲を file-finder で調査

## 実装
- [ ] タスク 1
- [ ] タスク 2
- [ ] タスク 3

## テスト
- [ ] 単体テストを追加
- [ ] 統合テストを追加（必要なら）
- [ ] テストが通ることを確認

## レビュー
- [ ] code-reviewer によるレビュー
- [ ] HIGH 指摘への対応

## ドキュメント
- [ ] docs の更新（必要なら）
- [ ] glossary への用語追加（必要なら）

## 完了処理
- [ ] design.md の最終化
- [ ] decisions.md の作成（重要な判断があった場合）
- [ ] git commit
```

**`.steering/_template/blockers.md`**:

```markdown
# ブロッカー記録

## ブロッカー 1: [タイトル]

- **発生日時**:
- **症状**:
- **試したこと**:
  1. ...
  2. ...
- **原因**:
- **解決方法**:
- **教訓**: 次回同じ状況に遭遇したらどうすべきか
```

**`.steering/_template/decisions.md`**:

```markdown
# 重要な設計判断

## 判断 1: [タイトル]

- **判断日時**:
- **背景**: なぜこの判断が必要だったか
- **選択肢**:
  - A: [説明]
  - B: [説明]
  - C: [説明]
- **採用**: B
- **理由**:
- **トレードオフ**: 何を諦めたか
- **影響範囲**: この判断がどこに影響するか
- **見直しタイミング**: どんな状況になったら再検討すべきか
```

### Step 6: .gitignore の確認

ユーザーに `.steering/` を git で追跡するか尋ねる:

- **追跡する場合**: 何もしない（共有可能なナレッジとして残る）
- **ローカルのみ**: `.gitignore` に追加

推奨は **追跡する**。チームで共有できるし、過去の作業履歴が貴重なナレッジになる。

### Step 7: 進捗ファイルの更新

`.steering/_setup-progress.md` の Phase 2 を完了マーク:

```markdown
- [x] **Phase 2: /setup-claude-md** — CLAUDE.md と .steering
  - 完了日時: [YYYY-MM-DD HH:MM]
  - 作成ファイル:
    - CLAUDE.md ([N] 行)
    - .steering/README.md
    - .steering/_template/ × 5 ファイル
  - .gitignore 更新: あり / なし
```

### Step 8: 完了通知

```
Phase 2 完了です。

作成したファイル:
- CLAUDE.md ([N] 行 / 上限 150 行)
- .steering/README.md
- .steering/_template/requirement.md
- .steering/_template/design.md
- .steering/_template/tasklist.md
- .steering/_template/blockers.md
- .steering/_template/decisions.md

次のステップ:
1. `/clear` でセッションをリセット
2. `/model sonnet` に切り替え（Phase 3 は Sonnet で十分）
3. `/setup-skills` を実行
```

## 完了条件

- [ ] CLAUDE.md が 150 行以下で作成されている
- [ ] CLAUDE.md がポインタ型になっている（docs の内容を抱え込んでいない）
- [ ] Grill me ステップを実施済み
- [ ] .steering/README.md が作成されている
- [ ] .steering/_template/ に 5 つのテンプレートが配置されている
- [ ] .gitignore の方針がユーザーと合意されている
- [ ] Phase 2 が完了マークされている

## アンチパターン

- ❌ CLAUDE.md にプロジェクトの全情報を詰め込む
- ❌ docs の内容を CLAUDE.md にコピーする
- ❌ 150 行を超える CLAUDE.md を許容する
- ❌ テンプレートを省略する
- ❌ Grill me を省略する
