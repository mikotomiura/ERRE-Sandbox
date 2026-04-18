# 設計 — T05 schemas-freeze (再生成案 v2)

## 実装アプローチ

**「Contract = ワイヤー境界」**と定義し直し、schemas.py を
"2 台の OS が信じ合うための境界条件" として設計する。
v2 の核心は以下 4 点:

1. **Discriminated Union を 2 箇所で徹底する** — `Observation` と `ControlEnvelope` は
   Pydantic v2 の `Field(discriminator=...)` を使い、イベント種別ごとに
   専用フィールドを持たせる。`payload: dict[str, object]` や
   `description: str` の free-form は排除する。
2. **静的ペルソナと動的状態を完全分離する** — 性格特性 (Big Five, wabi, ma_sense)
   や認知習慣は `PersonaSpec` に閉じ込める。`AgentState` は tick ごとに変化する
   物理・認知・ERRE モード・関係性のみを持つ。両者を跨ぐのは `persona_id: str`
   だけ。これにより YAML ファイルを書き換えても AgentState のスナップショット
   互換性が保たれる。
3. **スキーマバージョンを protocol level で持つ** — `SCHEMA_VERSION: Final[str]`
   を定義し、`HandshakeMsg` に必ず入れる。G-GEAR / MacBook / Godot の 3 者が
   バージョン差分を最初の 1 メッセージで検知できる。
4. **実装詳細を schema に漏らさない** — `MemoryEntry.embedding` のような
   「store が持つべきもの」はこのファイルから除外。schemas.py は
   「何が契約か」だけ、「どう保存するか」は T10 に任せる。

## 構造全体図

```
schemas.py (単一ファイル、セクションコメントで 8 区切り)
├─ §1  Protocol constants        (SCHEMA_VERSION, tick 関連定数)
├─ §2  Enums                      (Zone, ERREModeName, MemoryKind, HabitFlag,
│                                   ShuhariStage, PlutchikDimension)
├─ §3  Persona (static)           (CognitiveHabit, PersonalityTraits,
│                                   SamplingBase, PersonaSpec)
├─ §4  AgentState (dynamic)       (Position, Physical, Cognitive,
│                                   ERREMode, RelationshipBond, AgentState)
├─ §5  Observation (event union)  (PerceptionEvent, SpeechEvent,
│                                   ZoneTransitionEvent, ERREModeShiftEvent,
│                                   InternalEvent, Observation = RootModel[Union…])
├─ §6  Memory                     (MemoryEntry — pure domain, embedding は持たない)
├─ §7  ControlEnvelope (msg union) (HandshakeMsg, AgentUpdateMsg, SpeechMsg,
│                                   MoveMsg, AnimationMsg, WorldTickMsg,
│                                   ErrorMsg, ControlEnvelope = RootModel[Union…])
└─ §8  Re-exports                 (`__all__`)
```

## 主要モデルの定義意図

### §3 PersonaSpec (静的)

```python
class PersonalityTraits(BaseModel):
    # Big Five (0.0-1.0)
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    # ERRE 独自 (glossary: 日本文化由来の特性)
    wabi: float                 # 不完全受容度
    ma_sense: float             # 沈黙耐性

class CognitiveHabit(BaseModel):
    description: str
    source: str                 # 史料キー (e.g. "kuehn2001")
    flag: HabitFlag             # fact / legend / speculative
    mechanism: str              # 認知神経科学的メカニズム
    trigger_zone: Zone | None   # 発火ゾーン (optional)

class SamplingBase(BaseModel):
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.0

class PersonaSpec(BaseModel):
    persona_id: str             # kebab-case, e.g. "kant"
    display_name: str
    era: str                    # "1724-1804"
    primary_corpus_refs: list[str]
    personality: PersonalityTraits
    cognitive_habits: list[CognitiveHabit]
    preferred_zones: list[Zone]
    default_sampling: SamplingBase = Field(default_factory=SamplingBase)
    schema_version: str = SCHEMA_VERSION
```

### §4 AgentState (動的のみ)

```python
class Position(BaseModel):
    x: float
    y: float
    z: float
    zone: Zone

class Physical(BaseModel):
    """CSDG HumanCondition 5 軸 + ERRE 物理軸 3 つ。全 [0,1] または [-1,1]。"""
    sleep_quality: float = 0.7         # [0,1]
    physical_energy: float = 0.7       # [0,1]
    mood_baseline: float = 0.0         # [-1,1] — 基調気分 (日/長期)
    cognitive_load: float = 0.2        # [0,1]
    emotional_conflict: float = 0.0    # [0,1]
    fatigue: float = 0.0               # [0,1]
    hunger: float = 0.0                # [0,1]
    breath_rate: float = 0.25          # [0,1] — 歩行/座禅で変動

class Cognitive(BaseModel):
    """CSDG CharacterState 由来の心理状態 + ERRE 認知軸。
    mood_baseline (Physical) と valence (ここ) の違い:
        mood_baseline = 日単位の基調、Physical で半減衰
        valence       = 現在の tick での即時感情、Cognitive で都度更新
    """
    # Russell circumplex (即時感情)
    valence: float = 0.0               # [-1,1]
    arousal: float = 0.0               # [-1,1]
    # Plutchik 8 primary (optional, dominant 感情)
    dominant_emotion: PlutchikDimension | None = None
    # CSDG CharacterState 参考
    motivation: float = 0.5            # [0,1]
    stress: float = 0.0                # [0,1]
    curiosity: float = 0.5             # [0,1]
    # ERRE 独自
    shuhari_stage: ShuhariStage = ShuhariStage.SHU
    dmn_activation: float = 0.3        # [0,1] — 現在の DMN 活性
    active_goals: list[str] = []       # 短文 goal の列 (詳細は M4 で構造化)

class ERREMode(BaseModel):
    name: ERREModeName
    dmn_bias: float = 0.0              # [-1,1]
    sampling_overrides: SamplingBase   # 差分、絶対値ではない
    entered_at_tick: int
    zone_trigger: Zone | None = None

class RelationshipBond(BaseModel):
    other_agent_id: str
    affinity: float = 0.0              # [-1,1]
    familiarity: float = 0.0           # [0,1]
    ichigo_ichie_count: int = 0
    last_interaction_tick: int | None = None

class AgentState(BaseModel):
    """tick ごとの動的スナップショット。
    静的情報 (性格・認知習慣) は persona_id で PersonaSpec を参照して取得する。
    """
    schema_version: str = SCHEMA_VERSION
    agent_id: str
    persona_id: str
    tick: int
    wall_clock: datetime               # UTC
    position: Position
    physical: Physical
    cognitive: Cognitive
    erre: ERREMode
    relationships: list[RelationshipBond] = []
```

### §5 Observation — discriminated by `event_type`

```python
class _ObservationBase(BaseModel):
    tick: int
    agent_id: str                      # 観察主体
    wall_clock: datetime

class PerceptionEvent(_ObservationBase):
    event_type: Literal["perception"] = "perception"
    modality: Literal["sight","sound","smell","touch","proprioception"]
    source_agent_id: str | None
    source_zone: Zone
    content: str
    intensity: float                   # [0,1]

class SpeechEvent(_ObservationBase):
    event_type: Literal["speech"] = "speech"
    speaker_id: str
    utterance: str
    emotional_impact: float = 0.0      # [-1,1]

class ZoneTransitionEvent(_ObservationBase):
    event_type: Literal["zone_transition"] = "zone_transition"
    from_zone: Zone
    to_zone: Zone

class ERREModeShiftEvent(_ObservationBase):
    event_type: Literal["erre_mode_shift"] = "erre_mode_shift"
    previous: ERREModeName
    current: ERREModeName
    reason: Literal["scheduled","zone","fatigue","external","reflection"]

class InternalEvent(_ObservationBase):
    event_type: Literal["internal"] = "internal"
    content: str                       # 反省・内省のプロンプト
    importance_hint: float = 0.5

Observation = Annotated[
    PerceptionEvent | SpeechEvent | ZoneTransitionEvent
    | ERREModeShiftEvent | InternalEvent,
    Field(discriminator="event_type"),
]
```

この設計の効果:
- `event_type` 文字列で Godot 側も Python 側も分岐可能
- 新しいイベント種を足す時は union に 1 要素追加するだけ
- 既存フィールドは破壊されない (extra="forbid" でも互換維持)

### §6 MemoryEntry (pure domain)

```python
class MemoryEntry(BaseModel):
    """T10 の sqlite-vec store に渡す前の「契約」。
    embedding ベクトル・検索スコア等の実装詳細はこのファイルに含めない。
    """
    id: str
    agent_id: str
    kind: MemoryKind                   # episodic/semantic/procedural/relational
    content: str
    importance: float                  # [0,1]
    created_at: datetime
    last_recalled_at: datetime | None = None
    recall_count: int = 0
    source_observation_id: str | None = None
    tags: list[str] = []
```

### §7 ControlEnvelope — discriminated by `kind`

```python
class _EnvelopeBase(BaseModel):
    schema_version: str = SCHEMA_VERSION
    tick: int
    sent_at: datetime

class HandshakeMsg(_EnvelopeBase):
    kind: Literal["handshake"] = "handshake"
    peer: Literal["g-gear","macbook","godot"]
    capabilities: list[str]            # e.g. ["agent_update","speech","move"]

class AgentUpdateMsg(_EnvelopeBase):
    kind: Literal["agent_update"] = "agent_update"
    agent_state: AgentState

class SpeechMsg(_EnvelopeBase):
    kind: Literal["speech"] = "speech"
    agent_id: str
    utterance: str
    zone: Zone
    emotion: PlutchikDimension | None = None

class MoveMsg(_EnvelopeBase):
    kind: Literal["move"] = "move"
    agent_id: str
    target: Position
    speed: float                       # m/s

class AnimationMsg(_EnvelopeBase):
    kind: Literal["animation"] = "animation"
    agent_id: str
    animation_name: str                # "walk","idle","sit_seiza","bow"
    loop: bool = False

class WorldTickMsg(_EnvelopeBase):
    kind: Literal["world_tick"] = "world_tick"
    wall_clock: datetime
    active_agents: int

class ErrorMsg(_EnvelopeBase):
    kind: Literal["error"] = "error"
    code: str
    detail: str

ControlEnvelope = Annotated[
    HandshakeMsg | AgentUpdateMsg | SpeechMsg | MoveMsg
    | AnimationMsg | WorldTickMsg | ErrorMsg,
    Field(discriminator="kind"),
]
```

**ハンドシェイク**: 接続開始時に `HandshakeMsg` を交換し、
`schema_version` が不一致なら警告ログ + 互換モード判定に入る。
(実装は T14 gateway-fastapi-ws)

## 変更対象

### 修正するファイル
- `src/erre_sandbox/schemas.py` — 現状 13 行のスケルトン。フルに書き下ろす (推定 300-400 行)

### 新規作成するファイル
- なし (T05 はデータ契約のみ、ファイルは増やさない — repository-structure.md §5 の判断フローに従う)

### 削除するファイル
- なし

## 影響範囲

- `src/erre_sandbox/__init__.py` の `__all__` に主要型を載せる (再 export)
- `pyproject.toml` の `warn_return_any = false` の昇格を T05 完了後に決断可能になる
- 後続 T06 (persona-kant-yaml) は `PersonaSpec` をそのまま YAML マッピングで使える
- 後続 T07 (control-envelope-fixtures) は `ControlEnvelope` の各 union メンバの JSON Schema を書き出して Godot 側の参考にする

## 既存パターンとの整合性

- **architecture-rules**: schemas.py は `erre_sandbox.*` を import しない。`TYPE_CHECKING` も使わない (自己完結)
- **python-standards**: `from __future__ import annotations`, 全型ヒント, ruff ALL 対応, f-string 使用
- **persona-erre**: `CognitiveHabit` の 4 フィールド (description/source/flag/mechanism) + `trigger_zone` を追加
- **CSDG**: `Physical` の 5 フィールド名とデフォルト値は `HumanCondition` と一致。`Cognitive` は `CharacterState` の構造を参考 (motivation/stress/memory_buffer は stress + motivation + active_goals に再マップ)
- **glossary**: `Zone` / `ERREModeName` / `MemoryKind` / `wabi` / `ma_sense` / `ichigo_ichie_count` を厳密に踏襲

## テスト戦略

T05 の段階では `tests/test_schemas.py` に smoke テストのみ追加:

1. **構造検証**: 各モデルがデフォルト値または最小引数でインスタンス化可能
2. **extra="forbid"**: 未知フィールドを与えると `ValidationError`
3. **Enum 往復**: `StrEnum` 値が `.model_dump_json()` で文字列として出力される
4. **Discriminated Union**: `{"event_type": "speech", ...}` JSON が `SpeechEvent` に
   decode され、`{"event_type": "unknown"}` が `ValidationError` になる
5. **ControlEnvelope Union**: 同様に `{"kind": "handshake", ...}` が
   `HandshakeMsg` に正しくディスパッチされる
6. **SCHEMA_VERSION**: `AgentState().schema_version == SCHEMA_VERSION`

フル仕様テスト (境界値・round-trip・論理制約) は T08 test-schemas で実装。

## 実装順序 (tasklist に対応)

1. §1 定数 + §2 Enum 群を書く (最も依存が薄い)
2. §3 PersonaSpec 系 (CognitiveHabit → PersonalityTraits → SamplingBase → PersonaSpec)
3. §4 AgentState 系 (Position → Physical → Cognitive → ERREMode → RelationshipBond → AgentState)
4. §5 Observation union (基底 → 5 種類 → Annotated Union)
5. §6 MemoryEntry
6. §7 ControlEnvelope union
7. §8 `__all__` 定義
8. `ruff check`・`ruff format`・`mypy` をパスさせる
9. `tests/test_schemas.py` に smoke テスト 6 種
10. `decisions.md` に CSDG 参考箇所を明記
11. Conventional Commits でコミット

## ロールバック計画

- schemas.py は他モジュールから import されていないため、失敗時は `git revert` で単純に戻せる
- PR はレビュー必須 (main 直 push 禁止ルールに従う)

## v2 の設計判断の根拠

| 判断 | 理由 |
|---|---|
| Traits を PersonaSpec に移動 (AgentState から除外) | 性格特性は tick ごとに変わらない。静的データと動的データを混ぜると永続化戦略が複雑化 |
| Observation を discriminated union 化 | 自由記述 `description: str` では LLM 推論時にイベント型を判別できず、結局文字列マッチに戻る。型で分岐できる設計が CoALA の Observe ステップと整合 |
| ControlEnvelope を discriminated union 化 | `payload: dict` は JSON Schema を生成しても Godot 側が何を期待すべきか分からない。各 kind に専用フィールドがあれば GDScript 側も型付きで受けられる |
| MemoryEntry から embedding を除外 | embedding は sqlite-vec の実装詳細。schemas.py = 契約は「ドメイン概念」に徹する。T10 で `StoredMemory(MemoryEntry + embedding)` のような内部型を作る |
| SCHEMA_VERSION を protocol レベルで持つ | 2 台の独立開発では仕様ドリフトが起きる。早期検知の仕組みを最初から入れる |
| mood_baseline と valence の両立 | CSDG の長期基調 (Physical) と即時感情 (Cognitive) の時間スケール差を明示。名前と配置場所で意味境界を固定 |

## 懸念とその対処

| 懸念 | 対処 |
|---|---|
| Discriminated Union は Pydantic v2 の `Field(discriminator=)` が `RootModel` でのみ top-level で使えるケース有 | `Annotated[Union[...], Field(discriminator="kind")]` を `TypeAdapter` 経由でも `RootModel` でも受けられる構成にする |
| mypy strict で Union 判別が遅延評価と相性悪 | `from __future__ import annotations` 下で `TypeAdapter(ControlEnvelope)` を使う方針を decisions.md に明記 |
| `SamplingBase` (ベース) と `ERREMode.sampling_overrides` (差分) の型が同じでセマンティクスが違う | フィールド description に「絶対値 vs 加算差分」を明記、将来 T11/T12 で適用関数をテスト |
| Observation / ControlEnvelope の合計モデル数 (~12) が多い | 単一ファイルで保つためセクションコメントで目視ナビゲート、`__all__` で公開面をコントロール |

## 設計判断の履歴

- 初回案（design-v1.md）と再生成案（v2）を `design-comparison.md` で比較
- 採用: **v2（再生成案）**
- 根拠: requirement.md §背景の「両機独立実装による致命的手戻り (W2)」への正面対応には
  discriminated union による契約の固さが必須。v1 の `payload: dict[str, object]` は
  contract として未完成で、後続 T07 fixture も形式的契約にならない。
  MemoryEntry の embedding 除外は T10 での store バックエンド差し替え (architecture.md §8)
  に対する予防的措置として v2 を優先。ハイブリッドは v2 の長所を薄めるため不採用。

