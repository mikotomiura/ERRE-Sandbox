# 設計 v1 — 2 タスク並行 WorldLoop + 矩形ゾーン + drain API

> **ステータス**: 初回案 (v1)。`/reimagine` で破棄・再生成して v2 と比較する予定。
> 本ファイルは `/reimagine` 実行時に `design-v1.md` へ退避される。

## 1. 実装アプローチ

**方針**: T11 / T12 の DI 構造 (`ClassVar DEFAULT_*` + `__init__` 引数注入) を踏襲し、
`world/` に 4 モジュールを追加する。

1. **ゾーンは矩形 (AABB) 集合で表現** — 5 ゾーンごとに XZ 平面の
   矩形領域 + 高さ Y レンジを定数テーブルで持ち、`locate_zone(x, y, z) -> Zone`
   を O(5) 線形走査で実装。隣接は静的な dict で保持。
2. **WorldLoop は `asyncio.TaskGroup` で物理 / 認知の 2 タスクを並行駆動** — 物理タスクは
   `asyncio.sleep(1/30)` で 33ms ごとに全エージェントの位置を等速直線補間、
   認知タスクは `asyncio.sleep(10.0)` ごとに各エージェントの
   `CognitionCycle.step()` を逐次呼び出し。
3. **時刻は `Clock` プロトコルで抽象化** — `MonotonicClock` (本番) と
   `FakeClock` (テスト) を用意し、`asyncio.sleep` を `clock.sleep()` に置換可能に。
4. **Envelope は `asyncio.Queue` で生成→消費を疎結合** — `WorldLoop.produce_envelopes()`
   が内部キューに投入、`drain_envelopes()` / `async iter_envelopes()` で
   T14 側が消費。上限超でドロップせずバックプレッシャ (`put` で待つ)。
5. **エラー隔離**: 1 エージェントの `step()` 失敗 (`CognitionError` 等) は
   `logger.exception` で記録し当該エージェントのみスキップ、次 tick を止めない。
   `OllamaUnavailableError` は `CycleResult.llm_fell_back=True` で cycle 側が
   すでに吸収済みなので再 catch しない (error-handling §crash-loud の派生適用)。

## 2. モジュール構成

```
src/erre_sandbox/world/
├── __init__.py     # 12 シンボル re-export
├── zones.py        # ZoneLayout / ZONE_LAYOUTS / locate_zone / default_spawn /
│                   # adjacent_zones / ZoneNotFoundError  (pure, ~140 行)
├── physics.py      # AgentKinematics / step_position / apply_move_command
│                   # (pure, ~100 行)
└── tick.py         # Clock protocol / MonotonicClock / FakeClock /
                    # AgentRuntime / WorldLoop  (asyncio, ~320 行)
```

### 2.1 `world/zones.py` (pure, ~140 行)

```python
@dataclass(frozen=True, slots=True)
class ZoneLayout:
    zone: Zone
    min_xz: tuple[float, float]   # (min_x, min_z)
    max_xz: tuple[float, float]   # (max_x, max_z)
    center: tuple[float, float, float]  # spawn / waypoint 代表点
    y_range: tuple[float, float] = (0.0, 3.0)

ZONE_LAYOUTS: Final[Mapping[Zone, ZoneLayout]] = MappingProxyType({
    Zone.STUDY:     ZoneLayout(Zone.STUDY,     (-30.0, -30.0), (-10.0, -10.0), (-20.0, 0.0, -20.0)),
    Zone.PERIPATOS: ZoneLayout(Zone.PERIPATOS, (-10.0, -10.0), ( 10.0,  10.0), (  0.0, 0.0,   0.0)),
    Zone.CHASHITSU: ZoneLayout(Zone.CHASHITSU, ( 10.0, -10.0), ( 20.0,   0.0), ( 15.0, 0.0,  -5.0)),
    Zone.AGORA:     ZoneLayout(Zone.AGORA,     (-10.0,  10.0), ( 10.0,  30.0), (  0.0, 0.0,  20.0)),
    Zone.GARDEN:    ZoneLayout(Zone.GARDEN,    ( 10.0,  10.0), ( 30.0,  30.0), ( 20.0, 0.0,  20.0)),
})

ADJACENCY: Final[Mapping[Zone, frozenset[Zone]]] = MappingProxyType({
    Zone.STUDY:     frozenset({Zone.PERIPATOS}),
    Zone.PERIPATOS: frozenset({Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN}),
    Zone.CHASHITSU: frozenset({Zone.PERIPATOS, Zone.GARDEN}),
    Zone.AGORA:     frozenset({Zone.PERIPATOS, Zone.GARDEN}),
    Zone.GARDEN:    frozenset({Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA}),
})

class ZoneNotFoundError(ValueError): ...

def locate_zone(x: float, y: float, z: float) -> Zone: ...  # 線形走査
def default_spawn(zone: Zone) -> Position: ...
def adjacent_zones(zone: Zone) -> frozenset[Zone]: ...
```

### 2.2 `world/physics.py` (pure, ~100 行)

```python
@dataclass(slots=True)
class AgentKinematics:
    """Mutable per-agent kinematic state (world-internal, NOT exported via schemas)."""
    position: Position                      # current
    destination: Position | None = None     # latest MoveMsg target
    speed_mps: float = 1.3

def step_position(
    kin: AgentKinematics,
    dt_seconds: float,
) -> tuple[Position, Zone | None]:
    """Advance kinematics by dt. Returns (new_position, zone_changed_to_or_None)."""

def apply_move_command(kin: AgentKinematics, move: MoveMsg) -> None:
    kin.destination = move.target
    kin.speed_mps = move.speed
```

`velocity` 等は `AgentKinematics` に閉じ込め、`schemas.Position` の契約は変えない
(impact-analyzer 指摘に準拠)。

### 2.3 `world/tick.py` (asyncio, ~320 行)

```python
class Clock(Protocol):
    async def sleep(self, seconds: float) -> None: ...
    def monotonic(self) -> float: ...

class MonotonicClock: ...      # asyncio.sleep + time.monotonic
class FakeClock:               # advance(dt) で手動時間進め + sleep は Event 待ち
    def advance(self, dt: float) -> None: ...

@dataclass(slots=True)
class AgentRuntime:
    agent_id: str
    agent_state: AgentState
    persona: PersonaSpec
    kinematics: AgentKinematics
    pending_observations: list[Observation] = field(default_factory=list)

class WorldLoop:
    DEFAULT_PHYSICS_HZ: ClassVar[float] = 30.0
    DEFAULT_COGNITION_PERIOD_S: ClassVar[float] = 10.0
    DEFAULT_HEARTBEAT_PERIOD_S: ClassVar[float] = 1.0

    def __init__(
        self,
        *,
        cycle: CognitionCycle,
        clock: Clock | None = None,
        physics_hz: float | None = None,
        cognition_period_s: float | None = None,
        heartbeat_period_s: float | None = None,
        queue_maxsize: int = 1024,
    ) -> None: ...

    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None: ...
    def apply_external_observation(self, agent_id: str, obs: Observation) -> None: ...

    async def run(self) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._physics_task(), name="world-physics")
            tg.create_task(self._cognition_task(), name="world-cognition")
            tg.create_task(self._heartbeat_task(), name="world-heartbeat")

    async def stop(self) -> None: ...

    def drain_envelopes(self) -> list[ControlEnvelope]: ...
    async def iter_envelopes(self) -> AsyncIterator[ControlEnvelope]: ...

    # 内部
    async def _physics_task(self) -> None:
        """30Hz: 位置補間 + ゾーン遷移で ZoneTransitionEvent を pending に追加。"""

    async def _cognition_task(self) -> None:
        """10s: 全 agent の CognitionCycle.step() を逐次実行。
        pending_observations を swap し step に渡す。
        CycleResult.envelopes を queue に投入、MoveMsg は apply_move_command で反映。"""

    async def _heartbeat_task(self) -> None:
        """1Hz: WorldTickMsg を queue に投入。"""
```

### 2.4 `world/__init__.py`

12 シンボル re-export:
`Clock / MonotonicClock / FakeClock / WorldLoop / AgentRuntime /
AgentKinematics / ZoneLayout / ZONE_LAYOUTS / ADJACENCY /
locate_zone / default_spawn / adjacent_zones`

## 3. 変更対象

### 新規作成 (9 ファイル)

| ファイル | 想定行数 |
|---|---|
| `src/erre_sandbox/world/__init__.py` | ~30 |
| `src/erre_sandbox/world/zones.py` | ~140 |
| `src/erre_sandbox/world/physics.py` | ~100 |
| `src/erre_sandbox/world/tick.py` | ~320 |
| `tests/test_world/__init__.py` | 0 |
| `tests/test_world/conftest.py` | ~100 |
| `tests/test_world/test_zones.py` | ~120 |
| `tests/test_world/test_physics.py` | ~90 |
| `tests/test_world/test_tick.py` | ~220 |

合計 新規 ~1120 行

### 修正 (1 ファイル)

| ファイル | 内容 |
|---|---|
| `.steering/_setup-progress.md` | Phase 8 に T13 エントリ追加 |

### 削除

なし。

## 4. 影響範囲

- `cognition/cycle.py` の `CognitionCycle.step()` は API 変更不要
  (`tick_seconds` 引数は既に予約済み、`_ = tick_seconds` で未使用)
- `schemas.py` は変更なし (velocity は `AgentKinematics` に閉じる)
- 既存 tests に回帰リスクは低い (test_world/ は独立 conftest で分離)
- 下流 T14: `drain_envelopes()` 同期版と `iter_envelopes()` 非同期版の両方を提供

## 5. 既存パターンとの整合性

| パターン | 参照元 | T13 での適用 |
|---|---|---|
| `ClassVar DEFAULT_*` + `__init__(*, ...)` で DI | `cognition/cycle.py:107-134` | `WorldLoop.DEFAULT_PHYSICS_HZ` 等 |
| `rng: Random \| None = None` 注入で決定論テスト | `cognition/cycle.py:126` | `clock: Clock \| None = None` で代替 |
| `*Error` 1 種で例外正規化 | `cognition.CognitionError` | `ZoneNotFoundError(ValueError)` のみ |
| httpx.MockTransport テスト差し替え | `test_cognition/conftest.py:43-105` | `FakeClock` で同等の決定論化 |
| tests ミラー構造 | `tests/test_cognition/` | `tests/test_world/` を新規作成 |

## 6. テスト戦略

### 6.1 `test_zones.py` (pure, ~120 行)

- `locate_zone` が 5 ゾーンの center / 境界点 / 外側 (ZoneNotFoundError) を返す
- `default_spawn` が各ゾーンの layout.center と一致
- `adjacent_zones` が対称 (a ∈ adjacent(b) ⇔ b ∈ adjacent(a))
- ZONE_LAYOUTS が MappingProxyType で不変

### 6.2 `test_physics.py` (pure, ~90 行)

- `step_position`: destination=None のとき位置不変
- 目的地到達前 / 到達時 / 到達後 (clamping) 各ケース
- ゾーン境界跨ぎで zone_changed_to が返る
- `apply_move_command` で destination / speed 更新

### 6.3 `test_tick.py` (asyncio, ~220 行)

- `FakeClock.advance(1/30)` で物理タスクが 1 回 step
- `FakeClock.advance(10.0)` で認知タスクが `cycle.step()` を呼び envelopes が queue に入る
- MoveMsg 注入 → 次の物理 tick で位置補間
- ゾーン境界跨ぎで ZoneTransitionEvent が pending に入り次 cognition tick で渡る
- `cycle.step()` 例外で当該エージェントのみスキップ、他エージェントと次 tick は継続
- `stop()` で TaskGroup クリーン終了
- heartbeat: 1Hz で WorldTickMsg が queue に入る
- `drain_envelopes()` が FIFO
- queue_maxsize 超えでバックプレッシャ

### 6.4 conftest.py (~100 行)

- `make_world_loop(cycle=MockCycle, clock=FakeClock, ...)` ファクトリ
- `MockCycle` — `step()` 呼び出しを記録するテストダブル
- `FakeClock` の共通プロビジョン

### 6.5 回帰確認

- baseline: T12 完了時点の全テスト緑
- 期待: +20-25 件追加 = 全テスト緑

## 7. ロールバック計画

- 新規ファイルのみ、`git revert` 1 コミットで復元可能
- ゾーンレイアウト定数は `ZONE_LAYOUTS` 差し替えのみで調整可

## 8. 関連する Skill

- `python-standards` — snake_case / 型ヒント / asyncio / f-string (primary)
- `error-handling` — tick ループの例外隔離
- `architecture-rules` — world → cognition/memory/inference/schemas のみ
- `test-standards` — pytest-asyncio、AgentState ファクトリ再利用

## 9. 破壊と構築 (/reimagine) 適用予定

requirement.md の運用メモ記載通り、本 v1 案はこの後 `/reimagine` で
`design-v1.md` に退避され、ゼロから v2 を再生成する。比較観点:

1. **タスク分割粒度**: 2 タスク (物理 / 認知) vs 3 タスク (+ heartbeat) vs 1 タスクで内部タイマ管理
2. **Envelope 境界**: `asyncio.Queue` vs コールバック登録 (`on_envelope`) vs `AsyncIterator`
3. **ゾーン表現**: AABB vs 多角形 vs `(zone, center)` 名前参照のみ (距離判定は Godot 側)
4. **Clock 抽象化**: `Clock` プロトコル注入 vs `asyncio.get_event_loop().time()` 直接使用
