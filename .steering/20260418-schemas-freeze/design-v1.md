# 設計 — T05 schemas-freeze (初回案 v1)

## 実装アプローチ

CSDG (`csdg/schemas.py`) の 3 階層構造 (`HumanCondition` / `CharacterState` /
`DailyEvent`) を **素直に平行移植** し、ERRE-Sandbox 固有の概念
(ERRE モード・ゾーン・4 種記憶・ControlEnvelope) を足し込む。
単一ファイル `src/erre_sandbox/schemas.py` に全型を平置きで並べる。
ネストは `AgentState` のサブモデルのみに留め、トップレベルに 7 種を並列配置する。

方針の要点:

1. **Pydantic v2 `BaseModel` + `ConfigDict(extra="forbid", frozen=False)`** を
   すべてのモデルに適用。後方互換性破壊を防ぐ。
2. **値域は `Annotated[float, Field(ge=..., le=...)]`** で宣言的に表現し、
   `field_validator` は clamp 用途では使わない (Pydantic v2 の Constraint で十分)。
3. **Enum** は `StrEnum` (Python 3.11) を使用し、JSON 往復でも文字列のまま残す。
4. **日時は `datetime`** (`tzinfo=UTC` 推奨) を使い、float 秒時刻は使わない。
5. **ID は `str` (short id)** を採用。Godot GDScript が UUID を扱いづらいため。
6. `dump_for_prompt()` 等のメソッドは T05 では定義しない。T12 cognition-cycle で
   追加する (Contract 凍結フェーズはデータ定義のみ)。

## 変更対象

### 修正するファイル
- `src/erre_sandbox/schemas.py` — 現状はスケルトンのみ。7 種のトップレベル型を追加

### 新規作成するファイル
- なし (T05 はスキーマ定義のみ、ファイルを増やさない)

### 削除するファイル
- なし

## 影響範囲

- `src/erre_sandbox/__init__.py` からの再 export は T08 test-schemas で扱う
- 後続タスク (T06, T07, T10-T14) はすべてこの schemas.py から import する前提で設計される
- 現状 `tests/test_smoke.py` は import しないので影響なし

## 型の構成 (v1 案)

```python
# --- Enums ---
class Zone(StrEnum): STUDY / PERIPATOS / CHASHITSU / AGORA / GARDEN

class ERREModeName(StrEnum):
    PERIPATETIC / CHASHITSU / ZAZEN / SHU_KATA /
    HA_DEVIATE / RI_CREATE / DEEP_WORK / SHALLOW

class MemoryKind(StrEnum): EPISODIC / SEMANTIC / PROCEDURAL / RELATIONAL
class HabitFlag(StrEnum): FACT / LEGEND / SPECULATIVE
class ShuhariStage(StrEnum): SHU / HA / RI

# --- AgentState とサブモデル (CSDG HumanCondition を骨格に採用) ---
class Physical(BaseModel):
    sleep_quality: float = 0.7       # [0,1]
    physical_energy: float = 0.7     # [0,1]
    mood_baseline: float = 0.0       # [-1,1]
    cognitive_load: float = 0.2      # [0,1]
    emotional_conflict: float = 0.0  # [0,1]
    fatigue: float = 0.0             # [0,1]
    stress: float = 0.0              # [0,1]
    hunger: float = 0.0              # [0,1]
    location: Zone = Zone.STUDY

class Traits(BaseModel):
    # Big Five
    openness / conscientiousness / extraversion / agreeableness / neuroticism: float = 0.5
    # ERRE 独自 (glossary)
    wabi: float = 0.5
    ma_sense: float = 0.5
    shuhari_stage: ShuhariStage = ShuhariStage.SHU

class Emotion(BaseModel):
    valence: float = 0.0    # [-1,1]
    arousal: float = 0.0    # [-1,1]
    dominant: Literal["joy","trust","fear","surprise","sadness",
                      "disgust","anger","anticipation"] | None = None

class Biography(BaseModel):
    persona_id: str
    display_name: str
    era: str  # "1724-1804"

class Goal(BaseModel):
    text: str
    priority: float = 0.5
    deadline: datetime | None = None

class Relationship(BaseModel):
    other_agent_id: str
    affinity: float = 0.0         # [-1,1]
    familiarity: float = 0.0      # [0,1]
    ichigo_ichie_count: int = 0

class ERREMode(BaseModel):
    mode: ERREModeName
    dmn_bias: float = 0.0
    sampling_overrides: dict[str, float] = Field(default_factory=dict)

class AgentState(BaseModel):
    agent_id: str
    tick: int
    biography: Biography
    traits: Traits
    physical: Physical
    emotion: Emotion
    erre: ERREMode
    relationships: list[Relationship] = []
    goals: list[Goal] = []

# --- Memory ---
class MemoryEntry(BaseModel):
    id: str
    agent_id: str
    kind: MemoryKind
    text: str
    importance: float            # [0,1]
    created_at: datetime
    last_recall_at: datetime | None = None
    recall_count: int = 0
    embedding: list[float] | None = None  # 384d, store 時のみ付与

# --- Observation (CSDG DailyEvent 応用) ---
class Observation(BaseModel):
    tick: int
    agent_id: str
    event_type: Literal["speech","sight","sound","internal","environment"]
    domain: str
    description: str
    emotional_impact: float = 0.0   # [-1,1]
    source_agent_id: str | None = None

# --- Persona ---
class CognitiveHabit(BaseModel):
    description: str
    source: str
    flag: HabitFlag
    mechanism: str

class PersonaSpec(BaseModel):
    name: str
    era: str
    primary_corpus_refs: list[str]
    cognitive_habits: list[CognitiveHabit]
    personality_traits: dict[str, float]
    preferred_zones: list[Zone]

# --- ControlEnvelope (Gateway → Godot) ---
class ControlEnvelope(BaseModel):
    kind: Literal["agent_state","speech","world_tick","heartbeat"]
    tick: int
    agent_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
```

## 既存パターンとの整合性

- CSDG `HumanCondition` の 5 フィールド + デフォルト値を `Physical` に踏襲
- architecture-rules: `schemas.py` から他 `erre_sandbox.*` を import しない
- python-standards: `from __future__ import annotations`, 型ヒント完備, snake_case
- persona-erre: `CognitiveHabit` の 4 フィールド (description/source/flag/mechanism) を遵守

## テスト戦略

- T05 では **smoke テストのみ** を `tests/test_schemas.py` に追加:
  - 各モデルがデフォルト値でインスタンス化可能
  - `extra="forbid"` で未知フィールドが reject される
  - enum の値が文字列として dump される
- フル仕様テストは T08 test-schemas で実装

## ロールバック計画

- schemas.py は他モジュールから import されていない (T05 開始時点) ため、
  問題が起きたら `git revert` でロールバック可能
- `feature/schemas-freeze` ブランチで作業し、main へは PR 経由のみ

## v1 の懸念点 (自覚)

| 懸念 | 内容 |
|---|---|
| ControlEnvelope が弱型 | `payload: dict[str, object]` だと strict mypy で型安全性が落ちる。Discriminated Union を検討すべき |
| AgentState がフラット | サブモデルを 6 つ並列で持つが、「認知状態」と「身体状態」の区別が弱い。Cognitive / Physical のグルーピングが甘い |
| Emotion が CSDG と接続しない | CSDG の `mood_baseline` (Physical) と `valence` (Emotion) の意味境界が曖昧 |
| Observation が ERRE 固有要素なし | ゾーン入退室・ERRE モード切替のイベントを `event_type` に含めるべきか未決 |
| 記憶 embedding を schema に持つか | store 層の実装詳細が schema に染み出している |

これらの懸念を踏まえ、`/reimagine` で再設計し比較する。
