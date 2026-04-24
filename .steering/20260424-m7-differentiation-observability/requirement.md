# M7 — 三者の個別性と脳内可視化 (First PR 優先 3)

## 背景

2026-04-21 / 04-22 のライブ M6 Research Observatory 実行中、観察者が
`~/Downloads/ERRE-SandBox_issue.docx` に 12+ 件の改善 issue を記録した。
3 本の Explore エージェント + 1 本の Plan エージェントで現状コードと
`.steering/20260418-implementation-plan/MASTER-PLAN.md` を突き合わせた結果、
issue は 6 層 (Layer 1-6) にクラスタリングされた。

本タスクは **M7 本体** として 4-track + 1 vertical 構成を採用するが、
First PR は「体感デルタ/工数比が最大」の **優先 3 のみ** に絞る。
L6 (LoRA / agent scaling / user-dialogue IF) ロードマップは
`.steering/20260424-steering-scaling-lora/` に別途起票（コード無し文書）。

プラン全文: `/Users/johnd/.claude/plans/snuggly-jingling-pike.md`

## ゴール

First PR 1 本で以下 4 つを同時に解決し、M6 ライブ観察者が
「3 agent が別生物として振る舞い、field-event 境界が見え、反省が日本語」を
体感できる状態にする:

- V. LATEST REFLECTION が日本語
- A1. Reasoning panel 内の行動指針に persona 固有の personality 語彙が現れる
- B1. AffordanceEvent が発火し `evidence/<run>.summary.json` に出現
- B2. BoundaryLayer に affordance 半径 / proximity 閾値の円が描画される

## スコープ

### 含むもの (First PR)

- **V** `src/erre_sandbox/cognition/reflection.py:129-135` system prompt 末尾に
  日本語指示追加（`integration/dialog_turn.py:100-118` の `_DIALOG_LANG_HINT` 流用）
- **A1** `src/erre_sandbox/cognition/prompting.py:65-76` `_format_persona_block`
  を拡張し、Big Five (O/C/E/A/N) 1 行 + Wabi/Ma_sense 1 行を prompt に inject
- **B1** `src/erre_sandbox/world/tick.py` に `_fire_affordance_events()` 新規実装
  （`_fire_proximity_events:520-559` をテンプレに）。MVP は chashitsu 1 zone の
  1-2 prop 座標のみ。
- **B2** `godot_project/scripts/BoundaryLayer.gd` に affordance 半径円 (2m) +
  proximity 閾値円 (5m) を追加描画

### 含まないもの (Follow-up)

- Track A 残り: A2 (preferred_zones soft-weight), A3 (shuhari progression)
- Track B 残り: B3 (ReasoningTrace 拡張)
- Track C 全体: world 120m 拡張、top-down camera、zone 建物 primitive、MIND_PEEK
  深化（**C3 は着手前 `/reimagine` 必須**）
- Track D 全体: 相互反省、affinity 更新配線、prompt flow-back、成長メトリクス UI
- L6 steering 文書本体（別タスク `.steering/20260424-steering-scaling-lora/`）

## 受け入れ条件

### Unit / integration
- [ ] `uv run pytest tests/` 全パス
- [ ] `uv run ruff check src/ tests/` パス
- [ ] `uv run ruff format --check src/ tests/` パス
- [ ] `tests/test_cognition/test_reflection.py` に日本語応答パターン assert
- [ ] `tests/test_cognition/test_prompting.py` に personality フィールド存在 assert
- [ ] `tests/test_world/test_tick.py` に affordance event 発火テスト

### Empirical prompt tuning (Lite tier)
- [ ] V (reflection prompt) に 1 シナリオ × 2 iter 適用
- [ ] A1 (persona prompt) に 1 シナリオ × 2 iter 適用
- [ ] 結果を `.claude/skills/empirical-prompt-tuning/examples.md` に初の実評価ログとして追記

### Live on G-GEAR (acceptance)
- [ ] `evidence/_stream_probe_m6.py` で 60-90s run
- [ ] `evidence/<run>.summary.json` に `affordance_event` kind が出現
- [ ] Godot で BoundaryLayer に affordance / proximity 円描画
- [ ] Reasoning panel で 3 agent が **異なる** salient / decision を出す
  (Kant = study/peripatos, Nietzsche = peripatos/garden, Rikyu = chashitsu の傾向)
- [ ] LATEST REFLECTION が日本語表示

## 関連ドキュメント

- プラン全文: `/Users/johnd/.claude/plans/snuggly-jingling-pike.md`
- MASTER-PLAN: `.steering/20260418-implementation-plan/MASTER-PLAN.md`
- M6 carryover (親): `.steering/20260422-m6-observatory-carryover/` (V 吸収後 close)
- Source issue: `~/Downloads/ERRE-SandBox_issue.docx` (2026-04-21, 2026-04-22)
