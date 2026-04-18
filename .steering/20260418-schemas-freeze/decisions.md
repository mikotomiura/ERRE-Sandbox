# 重要な設計判断 — T05 schemas-freeze

## 判断 1: Discriminated Union を Observation / ControlEnvelope に採用

- **判断日時**: 2026-04-18
- **背景**: `ControlEnvelope` は G-GEAR ↔ MacBook ↔ Godot の 3 者を跨ぐワイヤー契約。
  初回案は `kind: Literal + payload: dict[str, object]` の汎用エンベロープだったが、
  「両機独立実装による致命的手戻り (requirement.md W2)」への対応として契約が弱すぎる。
- **選択肢**:
  - A: `payload: dict[str, object]` 汎用（初回案 v1）
  - B: `Annotated[Union[...], Field(discriminator="kind")]` による Pydantic discriminated union（v2）
  - C: `RootModel[Union[...]]` ラッパー
- **採用**: B
- **理由**:
  - JSON Schema が各 `kind` のフィールドを具体的に表現できるため、Godot (GDScript) の
    型付き受信コードを自動生成しやすい
  - mypy strict + `from __future__ import annotations` 下でも型解決が安定
  - `TypeAdapter(ControlEnvelope)` で JSON バリデーションが型安全に行える
  - 新しいメッセージ種は union に追加するだけで既存仕様を破壊しない
- **トレードオフ**: モデル数が +7 (Envelope) / +5 (Observation) 増え、schemas.py が
  300+ 行になる。汎用 `payload: dict` なら足し込みが楽だが、そのコスト削減は
  contract の固さと引き換えになる
- **影響範囲**: T07 (control-envelope-fixtures) が各 kind ごとに fixture を書く前提、
  T14 (gateway-fastapi-ws) が `TypeAdapter(ControlEnvelope)` で validate する前提、
  Godot 側 (MacBook) は JSON Schema → GDScript 型マップを後続で整備
- **見直しタイミング**: M5 以降でメッセージ種が 15 以上に膨張した場合、あるいは
  Godot 側で discriminated union の型生成が機能しないと判明した場合

## 判断 2: 静的 PersonaSpec と動的 AgentState を完全分離

- **判断日時**: 2026-04-18
- **背景**: CSDG `CharacterState` は性格・認知習慣・現在状態を一体化していたが、
  ERRE-Sandbox では毎 tick の AgentState スナップショットを永続化するため、
  静的データと動的データを混ぜると保存コストとリプレイ互換性が悪化する
- **選択肢**:
  - A: AgentState に Traits / Biography も含める（初回案 v1、CSDG 直訳）
  - B: 静的は PersonaSpec、動的は AgentState、橋渡しは `persona_id: str` のみ
- **採用**: B
- **理由**:
  - PersonaSpec (YAML) を書き換えても AgentState 履歴が壊れない
  - 毎 tick のスナップショット size が小さくなる
  - T06 persona-kant-yaml が PersonaSpec をそのまま YAML ↔ Pydantic にマッピング可能
  - `shuhari_stage` のように学習で変わる要素は Cognitive (AgentState 側) に
    明示配置することで、「静的にみえる概念」の動性を誤解しない
- **トレードオフ**: 推論時に agent_id → persona_id → PersonaSpec の join が発生。
  キャッシュで吸収できる範疇
- **影響範囲**: T06 (PersonaSpec YAML), T12 (cognition-cycle が persona join を行う),
  T14 (gateway が AgentState と persona を別エンドポイントで返す可能性)
- **見直しタイミング**: M9 で LoRA per persona 導入時、persona_id が
  LoRA adapter 名と 1-1 対応する必要が出たら命名規約を見直す

## 判断 3: MemoryEntry に embedding を持たせない

- **判断日時**: 2026-04-18
- **背景**: CSDG は `LongTermMemory` に embedding ベクトルを同居させていたが、
  ERRE-Sandbox の `architecture.md §8` 拡張ポイントで「memory バックエンドを
  Qdrant + bge-m3 に差し替える可能性」が明記されている
- **選択肢**:
  - A: `MemoryEntry.embedding: list[float] | None` を持つ（初回案 v1）
  - B: 除外し、T10 memory-store で `StoredMemory(MemoryEntry + embedding)` 相当の
    内部型を作る
- **採用**: B
- **理由**:
  - schemas.py = 契約は「ドメイン概念」に徹し、実装詳細の漏洩を防ぐ
  - sqlite-vec → Qdrant 差し替え時に contract 破壊にならない
  - 384d のベクトルを wire に載せるのは WebSocket 帯域の無駄
- **トレードオフ**: memory_store 内部に派生型を作る手間が増える
- **影響範囲**: T10 memory-store で内部型を別途定義する必要
- **見直しタイミング**: embedding を wire で送る必要が実際に出てきた場合
  (フロントエンドが embedding 可視化をするケース等)

## 判断 4: SCHEMA_VERSION を protocol レベルで導入

- **判断日時**: 2026-04-18
- **背景**: 2 台の独立稼働では仕様ドリフトが起きやすく、気付いた時にはデータ非互換
  という事態を避けたい
- **選択肢**:
  - A: バージョン持たず、コミット SHA で事後追跡
  - B: `SCHEMA_VERSION: Final[str]` を schemas.py に定義し、主要 BaseModel
    (`AgentState`, `PersonaSpec`, `_EnvelopeBase`) に `schema_version` フィールドを持たせる
- **採用**: B
- **理由**: `HandshakeMsg` で接続直後にバージョン確認、不一致なら警告ログ。
  事後追跡より安い
- **トレードオフ**: フィールド 1 つの wire オーバーヘッド (数十バイト/メッセージ)
- **影響範囲**: T14 gateway で handshake 時に SCHEMA_VERSION 比較を実装
- **見直しタイミング**: M5 以降の破壊的変更時に、"0.1.0-m2" → "0.2.0-m5" に昇格

## 判断 5: SamplingBase と SamplingDelta を別型にする

- **判断日時**: 2026-04-18
- **背景**: ペルソナの baseline (絶対値) と ERRE モード override (差分) は同じ
  3 フィールド (temperature / top_p / repeat_penalty) を持つが、値域・デフォルト・
  意味が全く違う
- **選択肢**:
  - A: 同一型 `SamplingBase` を両方で使い、コメントで区別
  - B: `SamplingBase` (baseline) と `SamplingDelta` (差分) に分離
- **採用**: B
- **理由**: 型で意味を表現することで、`persona.default_sampling + erre.sampling_overrides`
  の合成式が型的に明確になる。mypy が誤代入を検出する
- **トレードオフ**: モデル数が +1
- **影響範囲**: T11 / T12 で合成コード (クランプ含む) を書く際、型シグネチャで
  `combine(base: SamplingBase, delta: SamplingDelta) -> SamplingBase` の形に固定できる
- **見直しタイミング**: 将来 `min_p` / `mirostat` などのサンプリングパラメータを
  追加する際に両型を拡張する

## 判断 6: `warn_return_any = false` を pyproject で維持

- **判断日時**: 2026-04-18
- **背景**: T04 の pyproject では `warn_return_any = false` のままで、
  「T05 完了後に true に昇格」とコメントされていた
- **選択肢**:
  - A: T05 完了と同時に true に昇格
  - B: T10-T14 で `Any` が発生しやすい箇所 (sqlite-vec / FastAPI 等) の実装を
    確認してから昇格
- **採用**: B（本タスク内では変更しない）
- **理由**: 昇格は Contract 凍結より後の実装層 (T10+) で初めて意味を持つ。
  先に昇格すると `Any` 由来のエラーが大量発生し、デバッグ効率が落ちる
- **トレードオフ**: 一時的に strict の強度が 1 段弱い
- **影響範囲**: 本 PR では pyproject.toml を変更しない
- **見直しタイミング**: T10 memory-store 完了時に再検討

## 判断 7: code-reviewer の HIGH 指摘への対応

- **判断日時**: 2026-04-18
- **背景**: T05 実装後の code-reviewer が以下 2 件を HIGH で指摘:
  1. `SamplingDelta.temperature` の range (`ge=-2.0, le=2.0`) が `SamplingBase`
     との合成時に上限越えを許す (base=1.5 + delta=+0.8 = 2.3 > SamplingBase 上限 2.0)
  2. `__all__` がアルファベットソート済だがカテゴリコメントが実体と不整合
- **採用**:
  1. `SamplingDelta.temperature` の range を `ge=-1.0, le=1.0` に絞る +
     合成時クランプは T11/T12 の責務と docstring に明記
  2. `__all__` からカテゴリコメントを全削除しフラットソートを保つ
- **理由**: Contract の固さを維持する (#1) と、静的解析と保守性の両立 (#2)

## 判断 8: code-reviewer の MEDIUM 指摘のうち contract 影響を対応

- **判断日時**: 2026-04-18
- **採用内容**:
  - `Position` に `pitch` を追加 (#3 bow/gaze アニメーション対応)
  - `src/erre_sandbox/__init__.py` で主要 6 型を re-export (#4)
  - `Cognitive.active_goals` に `max_length=10` とソフト上限 + M4 破壊的変更予定を明記 (#6)
  - `PerceptionEvent.source_agent_id` の description に environmental 起因時が None と明示 (#8)
  - `tests/test_schemas.py` に `_Unit` / `_Signed` 範囲外 reject テストを追加 (#7)
- **見送り (後続タスク対応)**:
  - #5 `last_interaction_tick` の Annotated 書き換え (動作上問題なし、好み)
  - #9-#12 LOW 指摘 (ErrorMsg.severity, HandshakeMsg.capabilities Enum 化,
    `_make_agent_state` の conftest.py 昇格) は T08 test-schemas / T14 gateway 時に対応

## CSDG 参考箇所の明示（ライセンス上の礼節）

CSDG (MIT ライセンス, https://github.com/mikotomiura/cognitive-state-diary-generator) の
以下の設計パターンを参考にしてリライトした（コード断片の直接コピーはなし）:

- `csdg/schemas.py` `HumanCondition` の 5 フィールド + デフォルト値
  (sleep_quality=0.7, physical_energy=0.7, mood_baseline=0.0, cognitive_load=0.2,
  emotional_conflict=0.0) → `schemas.Physical`
- `csdg/schemas.py` `CharacterState` の心理状態構造 (motivation / stress) → `schemas.Cognitive`
- `csdg/schemas.py` `DailyEvent` の (event_type / domain / description /
  emotional_impact) の発想 → `schemas.PerceptionEvent` / `schemas.SpeechEvent`

法的帰属義務はないが、ERRE-Sandbox 本家リポジトリの `NOTICE` への記載は T08
test-schemas の完了処理で検討する (本 PR のスコープ外)。
