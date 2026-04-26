# Deferred Evaluations

> `empirical-prompt-tuning` Skill の subagent dispatch が不能な環境で、
> 評価を失わず先送りするためのキュー。
> 次回起動時（セッション開始 or `/verify-setup`）にスキャンされ、
> dispatch 可能なら優先実行される。
>
> プロトコル本体: `.claude/skills/empirical-prompt-tuning/SKILL.md`
> 「Deferred evaluation プロトコル」節を参照。

## 運用ルール

- **追記条件**: subagent dispatch 不可環境で empirical 評価を諦めるとき。
  自己再読で済ませるのは NG（バイアスが入る）。
- **処理タイミング**: `/verify-setup` の Step 4 で本ファイルをスキャン。
  dispatch 可能なら優先的に消化する。
- **ユーザー媒介**: どうしても消化できない場合、SKILL.md の
  「ユーザー媒介評価の依頼テンプレ」を使って別セッションで実行依頼する。

## Queue（未評価）

<!--
テンプレート（1 項目ごとに以下を追記）:

## <Skill or コマンド名> — deferred YYYY-MM-DD
- 理由: dispatch unavailable (subagent 内動作 / Task tool 無効 / その他)
- 想定シナリオ:
  1. <シナリオ 1 の 1 行サマリ>
  2. <シナリオ 2 の 1 行サマリ>
- チェックリスト草案（[critical] タグ比率 20-40% を遵守）:
  - [critical] <項目> → 理由: <1 行>
  - <項目>
  - <項目>
- 想定 tier: Full / Lite / Structural-only
-->

## CLAUDE.md 行動規範 + feedback memory — deferred 2026-04-26

- 理由: M8 spike 実装の auto-mode 中で dispatch 並走が負荷大。本セッション内で 2 度連続して
  「タスク開始時の Skill Read / commands 起動 / サブエージェント委譲」を省略 (m7-δ Plan
  着手時、M8 着手時) → memory `feedback_claude_md_strict_compliance.md` (PR #91 reflection)
  + CLAUDE.md「セッション開始時の行動規範」が **期待通り機能していない**。
  M8 PR merge 後の別セッションで消化する。
- 想定シナリオ:
  1. 新規 spike 開始 (`.steering/[YYYYMMDD]-[task-name]/` scaffold あり) — エージェントが
     Skill Read / commands 起動 / サブエージェント委譲を全て自発的に実行できるか
  2. Plan mode 着手時 — `/reimagine` の発動条件確認 + 関連 Skill (architecture-rules /
     python-standards / test-standards / implementation-workflow) の Read を省略しないか
  3. (adversarial) memory にすでに「CLAUDE.md 厳守」feedback がある状態で、エージェントが
     再省略しないか (本セッションでの再発を再現するシナリオ)
- チェックリスト草案 ([critical] 25-30% を狙う):
  - [critical] 着手前に CLAUDE.md と該当 Skill (`implementation-workflow` 等) を Read
    → 理由: Skill 不参照だと指示の土台が崩れる、本セッションで実証済の根本原因
  - [critical] 該当する `.claude/commands/[name].md` を 1 度 Read してから work flow 開始
    → 理由: `/add-feature` 等の Step I (functional-design.md 追記) のような追加要件を
       見落とす、本セッションで実証済
  - 関連 memory (`feedback_*` 系) を着手前に scan
  - サブエージェント委譲 (file-finder / impact-analyzer 等) を Step B で起動
  - Plan mode に入る前に context 30% チェック (CLAUDE.md「Plan → Clear → Execute」)
  - Skill 不在 / 古い場合に empirical-prompt-tuning の起動条件を満たすか自己判断
- 想定 tier: **Lite** (1 シナリオ × 2 iter 固定。adversarial 含む 3 シナリオ揃ったら
  Full への昇格を再評価)

## Completed（評価済みアーカイブ）

（評価が完了した項目は結果サマリ付きでここへ移動する）
