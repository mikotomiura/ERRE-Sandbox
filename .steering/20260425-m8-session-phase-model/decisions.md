# Decisions — M8 Epoch Phase Model

本 task の /reimagine 軸 1-4 の採用判断を記録。詳細プロセスは `design.md` 参照。

## D1. enum の形式 — StrEnum を採用

- **選択肢**: (a) StrEnum (Zone / ERREModeName と同パターン) /
  (b) field-local `Literal` TypeAlias
- **採用**: (a) StrEnum (`EpochPhase`)
- **根拠**: 3 phase は run 全体で参照され単独で扱うため、StrEnum が自然で
  `test_str_enum_round_trip_as_json` fixture に乗せられる。field-local Literal は
  discriminator フィールド専用パターンで、本件は discriminator ではない。
- **影響範囲**: `schemas.py` §2 に追加、`__all__` に `"EpochPhase"` を追加

## D2. run-level state の置き場 — RunLifecycleState BaseModel + WorldRuntime

- **選択肢**: (a) 新規 Pydantic `RunState` BaseModel + WorldRuntime / (b) WorldRuntime
  attribute として直接 `epoch_phase` (BaseModel なし) / (c) 新規 `RunLifecycleState`
  BaseModel (epoch_phase + epoch_started_at のみ) + WorldRuntime
- **採用**: (c) hybrid
- **根拠**: BaseModel を 1 つ挟むと log 出力 / WS envelope 載せ替え / 将来の
  `epoch_metadata` 等拡張が容易。(a) の `RunState` は名前が広すぎで M8 spike の
  scope 外の意味が付く。(b) は ad-hoc で拡張時に手戻り。
- **影響範囲**: `schemas.py` に新規 §4.5 section、WorldRuntime に 1 属性
- **不採用理由の理由** (L6 で「AgentState vs BootConfig」と書いた件): 発見事項
  の通り、BootConfig は frozen dataclass で mutable 不可、AgentState は per-agent
  scope なので run-level 要件と噛み合わない。WorldRuntime は既存の mutable
  singleton で自然なホスト。

## D3. 遷移 API の形 — WorldRuntime メソッド、Protocol なし

- **選択肢**: (a) `EpochTransitioner` Protocol を `schemas.py` §7.5 に追加 /
  (b) WorldRuntime に直接メソッド追加、Protocol なし
- **採用**: (b) WorldRuntime メソッド
- **根拠**: 3 phase FSM は許可遷移 2 本のみで Protocol 層を挟むほどの複雑さが
  ない。DialogScheduler / ERREModeTransitionPolicy のように複数実装が想定
  されない (M8 spike は単一 WorldRuntime 前提)。M9 以降で必要になったら
  Protocol 化 (defer, YAGNI)。
- **影響範囲**: WorldRuntime に `transition_to_q_and_a()` +
  `transition_to_evaluation()` を追加、許可パス以外は `ValueError`

## D4. Q&A epoch の "researcher" 扱い — magic string

- **選択肢**: (a) `DialogTurnMsg.speaker_id` に magic string `"researcher"`
  を格納 / (b) `personas/researcher.yaml` 新規作成、AgentState として扱う
- **採用**: (a) magic string
- **根拠**: `DialogTurnMsg.speaker_id` は既に `str` で unconstrained、magic string
  受理に schema 変更不要。`personas/researcher.yaml` の作成 + persona loader
  への影響は M8 spike の scope を膨張させる。将来 Q&A epoch を
  "researcher = synthetic agent" で実装するなら (b) が活きるが、M8 precondition は
  magic string 規約で十分。
- **影響範囲**: decisions 記述のみ、コード変更なし
  (本 decisions.md がその規約の記録)
- **将来拡張**: Q&A 実装時に (b) に移行する可能性あり、そのとき PersonaId
  Literal 導入 (別 task) と合わせる

## D5. SCHEMA_VERSION bump — 0.4.0-m6 → 0.5.0-m8

- **採用**: `0.5.0-m8` (minor bump、additive)
- **根拠**: 新 enum / 新 BaseModel / 新 WorldRuntime 属性 / 新メソッドは全て
  additive で既存 wire 契約を破壊しない。consumer (Godot / MacBook orchestrator)
  は新フィールドを無視するだけ。
- **影響範囲**: `schemas.py:43` の `SCHEMA_VERSION` 定数、docstring、
  `personas/*.yaml` (3 files) の schema_version 欄、`fixtures/**` + `tests/schema_golden/**`
  を `scripts/regen_schema_artifacts.py` で再生成

## 横断メモ

本 spike が L6 ADR D3 の初回 precondition 実装。後続 spike:
- `m8-baseline-quality-metric` / `m8-episodic-log-pipeline` は本 spike に依存しない
- Q&A epoch の LLM routing 実装は M9 以降 (次の /start-task で別 spike を立てる)
- ControlEnvelope に `epoch_phase` を載せる観察要件が立ったら、別 spike で
  追加 (本 spike の scope 外、Out of Scope 通り)
