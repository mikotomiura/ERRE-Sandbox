# Decisions — M8 Baseline Quality Metric

Plan mode で /reimagine を全 5 軸 (A-E) に適用し、ゼロから再生成した v2
を採用した。各軸の採用根拠を以下に固定する。

## D1 (Axis A). metric 本数 = 2 (fidelity + bias_fired)、affinity は defer

- **採用**: 2 metric 構成。affinity 推移は baseline JSON に `null` field として
  残し、実装は別 spike `m8-affinity-dynamics` (新規、L6 D1 residual) に移す
- **根拠**: Phase 1 で `RelationshipBond.affinity` に mutation logic ゼロ
  が判明 (`src/` 全域 grep で schemas.py:422 のみ)。mutation なしで測ると
  「全 run 常に 0.0」が baseline になるだけで意味がない。proxy
  (`last_interaction_tick` による co-present count) は L6 D1 が意図した
  「affinity 推移」ではない別指標で、baseline に混入すると M9 比較が歪む
- **却下案**:
  - v1 (3 metric 全部) → affinity mutation 設計が先行必要で spike が
    2-in-1 化、両方半端
  - v3 (proxy 使用) → 意味論乖離で M9 比較精度を下げる
- **残課題**: L6 ADR decisions.md に `m8-affinity-dynamics` を D1 residual
  として追記すること

## D2 (Axis B). bias.fired capture = process 内 structured sink

- **採用**: `cognition/cycle.py::_apply_zone_bias` に optional `bias_sink:
  Callable[[BiasFiredEvent], None] | None = None` 引数を追加、sink は
  bootstrap で `MemoryStore.add_bias_event_sync()` を呼ぶ closure
- **根拠**: PR #88 の `turn_sink` と同じパターンで一貫性。Godot 側に露出
  不要な observability データはサーバ内で sqlite に落とせば十分。
  SCHEMA_VERSION 無影響、default None で既存 callsite は無改変
- **却下案**:
  - v1 (ログパース) → logger 再設定や format 変更に脆い
  - v3 (ControlEnvelope に BiasFiredMsg 追加) → wire 変更で SCHEMA_VERSION
    bump、Godot consumer への不要負荷

## D3 (Axis C). trigram 閾値 = 2 次元 (persona 内自己反復 + persona 間 echo)

- **採用**: 単一閾値をやめ、`self_repetition_rate` と
  `cross_persona_echo_rate` の 2 値を別 field で baseline JSON に記録
- **根拠**: CSDG の 0.30 / 0.50 は single-author diary 前提の定数。dialog
  では「自己反復が低い (新鮮さ)」と「persona 間 echo が低い (差異)」は
  別の望ましい性質。単一閾値だと両者を分解できず、LoRA 比較時に「どちらが
  悪化したか」が判別不能
- **却下案**:
  - v1 (単一閾値流用) → 2 性質が重なって観測不能
  - v3 (N×N pair matrix) → baseline に冗長、集約しづらい
- **CSDG 数値**: 参考値として baseline.md に並記するが、閾値判定には
  使わない。純粋に M9 との diff 可能な生数値として残す

## D4 (Axis D). 集計タイミング = post-hoc CLI

- **採用**: `erre-sandbox baseline-metrics --run-db <path> --out <json>`
  subcommand。sqlite を offline で読んで JSON を吐く。live run 側は永続化
  (既存 dialog_turns + 新規 bias_events) のみ担当
- **根拠**: PR #88 の `export-log` と同じ post-hoc パターン。metric 式を
  revise しても過去 run DB があれば再集計可能。unit test も fixture DB
  一発で済む。`_stream_probe_m6.py` が standalone (src/ 外) である事実とも整合
- **却下案**:
  - v1 (in-process hook) → 集計ロジック変更のたびに live run 再実行で
    G-GEAR 往復増
  - v3 (両方実装) → DRY 違反

## D5 (Axis E). sink 注入点 = WorldRuntime bootstrap closure

- **採用**: (a) bootstrap.py が `_persist_bias_event` closure を組み立てて
  cognition cycle の呼び出しパスに渡す。agent_id → persona_id は
  `runtime.agent_persona_id()` で解決
- **根拠**: PR #88 の `_persist_dialog_turn` と同パターン。runtime は
  bootstrap で組み立てる唯一の singleton で、persona registry を持つのも
  ここ。gateway 層に持たせると envelope 観察以外の責務を混ぜて架構が汚れる
- **却下案**:
  - (b) gateway 層での推論 → bias は envelope として出ておらず実現不能
  - (c) 個別 agent 毎 → 3 agent に同じ sink を配るだけで (a) と等価

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D1
- 上流 spike: `.steering/20260425-m8-episodic-log-pipeline/` (iter_dialog_turns 提供)
- 後続 spike (新規起票): `m8-affinity-dynamics` (L6 D1 residual)
- Plan 原本: `/Users/johnd/.claude/plans/misty-marinating-scone.md`
