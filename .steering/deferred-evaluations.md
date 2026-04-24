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

（未評価項目はまだ無い）

## Completed（評価済みアーカイブ）

（評価が完了した項目は結果サマリ付きでここへ移動する）
