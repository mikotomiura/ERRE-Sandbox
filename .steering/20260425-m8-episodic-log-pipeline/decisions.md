# Decisions — M8 Episodic Log Pipeline

本 task の /reimagine 軸 1-5 の採用判断を記録。詳細プロセスは `design.md` 参照。

## D1. 永続化範囲 — dialog_turn のみ (v2)

- **選択肢**: (a) dialog_turn + reasoning_trace + reflection_event 全 3 種永続化 /
  (b) **dialog_turn のみ** / (c) dialog_turn + reasoning_trace
- **採用**: (b) dialog_turn のみ
- **根拠**:
  - L6 D1 の真の目的は M9 LoRA 訓練用の対話 turn 数 tracking
  - LoRA 訓練入力は対話 turn そのもの、reasoning_trace は認知内部の観察シグナル
    で訓練入力ではない
  - reflection_event は既に `semantic_memory` table に `upsert_semantic()` 経由で
    要約が保存済 (`store.py:559-616`)、追加永続化は DRY 違反
  - (a) は scope 1.5-2d (spike 1d 見積を倍近く超える)
- **影響範囲**: 新 table は `dialog_turns` のみ。reasoning_trace / reflection_event
  の永続化は将来「観察要件が立ったとき」に別 spike で起票

## D2. persona_id の格納方法 — sink 側で解決

- **選択肢**: (a) `DialogTurnMsg` schema に `persona_id` 追加 + SCHEMA_VERSION
  bump / (b) **schema 変更せず、sink 側で agent_id → persona_id を解決**
- **採用**: (b) sink 側で解決
- **根拠**:
  - persona_id は speaker_id/addressee_id から解決可能、wire 冗長
  - 直前の M8 session-phase-model (PR #87) で SCHEMA_VERSION を 0.5.0-m8 に
    bump 済、短期間に連続 bump は consumer (Godot) への負荷が大きい
  - sink 側解決なら AgentRegistry (bootstrap 既存) からの lookup で十分
- **影響範囲**: bootstrap で turn_sink closure を構築する際に
  `{agent_id: persona_id}` の map を閉包、scheduler は map 非依存

## D3. session_id の扱い — 導入しない (defer)

- **選択肢**: (a) `session_id` 概念を新規導入 (schemas / store / gateway /
  WorldRuntime 横断改修) / (b) **本 spike では導入せず、timestamp range で代用**
- **採用**: (b) 導入しない
- **根拠**:
  - 横断改修は 2-3d 規模、spike scope を超える
  - turn count tracking には session 境界は不要 (`SELECT speaker_persona_id,
    COUNT(*) FROM dialog_turns GROUP BY speaker_persona_id` で十分)
  - L6 D3 の 2-phase methodology (M8 session-phase-model で session_phase 導入済)
    が session 概念の自然な発展点、そこで統合する
- **影響範囲**: dialog_turns table に session_id カラム無し、tick と created_at
  で session 境界を推定できる設計に留める

## D4. export format — JSONL のみ

- **選択肢**: (a) JSONL + Parquet 両対応 (pyarrow 依存追加) / (b) **JSONL のみ**
- **採用**: (b) JSONL のみ
- **根拠**:
  - pyarrow は ~100MB wheel、本 spike のためだけに追加は YAGNI
  - LoRA 訓練 pipeline (HuggingFace datasets) は JSONL を直接 load 可
  - Parquet は M9 LoRA task で本当に必要になった時に追加、追加 cost は低い
- **影響範囲**: `--format` flag 自体は残すが `jsonl` のみ受理、他形式は明示的
  error を返す (M9 で追加時は値を増やす)

## D5. sink 注入点 — DialogScheduler ctor

- **選択肢**: (a) **`InMemoryDialogScheduler` ctor に `turn_sink` callable を
  注入** / (b) envelope broadcast を観察する別 sink layer / (c) gateway.py
  の envelope pub で trigger
- **採用**: (a) DialogScheduler ctor
- **根拠**:
  - DialogScheduler は既に dialog 状態の真実源、coupling は自然
  - (b) envelope layer (観察用) に永続化責任を混ぜると関心分離が崩れる
  - (c) gateway 層が WS 観察以外の責務を持ち始める
  - `record_turn()` は同期 Protocol、sync callback を渡すのが最も簡潔
- **影響範囲**: `InMemoryDialogScheduler.__init__` に optional `turn_sink:
  Callable[[DialogTurnMsg], None]` を追加、省略時は既存挙動を維持
  (後方互換)

## 横断メモ

- SCHEMA_VERSION **変更なし** (wire 形式は無変更)。MemoryStore の内部 table は
  wire 契約ではないので bump 対象外 (M4 contracts-freeze decisions D3 準拠)
- `record_turn()` は同期 Protocol のため、sync sink を採用 (async 化は Protocol
  破壊、M8 scope 外)
- agent_id → persona_id の map は bootstrap で `AgentSpec.persona_id` から
  構築、scheduler 経由で sink closure に閉包する
- reasoning_trace / reflection_event の永続化が本当に必要になったら、本 spike
  と同じ「turn_sink」パターンで ReasoningTraceMsg / ReflectionEventMsg に対する
  sink を cognition/cycle.py に追加する (既存設計との整合性)
