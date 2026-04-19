# 設計 v2 — 単一コルーチン・heapq スケジューラ + Voronoi ゾーン + gather 並列認知

> **ステータス**: 再生成案 (v2)。v1 は `design-v1.md` に退避済み。
> `design-comparison.md` で 2 案比較後、採用案をここに確定する。

## 1. 実装アプローチ

**設計の核**: 「30Hz / 10s / 1Hz の 3 種類の周期タスクを並行させる」問題を
**複数の asyncio タスクで並列化する**のではなく、**単一コルーチン内で
絶対時刻スケジュールのヒープキューとして解く**。

### 1.1 なぜ単一コルーチン + heapq なのか

- **時間ドリフト排除**: `asyncio.sleep(0.0333)` を 30Hz でループすると
  1 秒あたり数 ms ずつ遅延が累積する。各イベントに「絶対 due_at」を持たせて
  `sleep_until(due_at)` 方式にすれば、遅延が発生しても次の due_at は
  固定され、時間がドリフトしない。
- **決定論的テスト**: ManualClock は「次の due_at まで時間を飛ばし、
  due なイベントをすべて実行する」で 1 tick を完全再現できる。
  asyncio.TaskGroup のようにイベントループのスケジューリングに依存しない。
- **ローカル状態での競合なし**: 3 タスクが `agents` dict や envelope キューを
  同時触することがないため、ロック不要。Python の GIL すらも不要な単純性。
- **責務の合成**: 新しい周期タスク (M4 の反省ループ、M7 の永続化スナップショット等) を
  追加するときは `schedule(period, callback)` 1 行で済む。

### 1.2 認知 tick の LLM 遅延を並列化で吸収

単一コルーチンだと「認知 tick の LLM 呼び出し中は物理 tick も heartbeat も止まる」
という問題が生じる。これを **`asyncio.gather` で N エージェントの `step()` を
同時並走させる + その await 中は event loop が他のイベント (次の物理 tick) を
処理できる** という asyncio のセマンティクスで解く。

具体的には、cognition ハンドラは:
```python
async def _on_cognition_tick(self) -> None:
    # N エージェントの step() を並列発射、終わるまでここで await
    results = await asyncio.gather(
        *(self._step_one(a) for a in self._agents.values()),
        return_exceptions=True,
    )
    for rt, res in zip(self._agents.values(), results, strict=True):
        self._consume_result(rt, res)
```
この await の間、イベントループは `_on_physics_tick` の次の due_at も
待っているので、LLM が 2 秒かかっても物理 tick は 60 回発火する (スケジューラが
イベントを貯めて一気に処理)。

### 1.3 ゾーンは「最近傍セントロイド (Voronoi lite)」

5 ゾーンごとに (x, y, z) の代表点 1 個だけを持ち、
`locate_zone(x, y, z) = argmin(Zone, ‖(x,z) − center(Zone).xz‖)`
として **Voronoi 分割**で一意にゾーンを決める。矩形 AABB ではない理由:

- 矩形は境界ケース (枠の外) / 重なりの扱いに if 文が増える
- Voronoi は 5 個の 2D 距離計算だけで決定的・連続的
- ゾーンレイアウトの調整は「代表点をずらす」だけで済む (矩形の x_min/x_max 4 点を
  調整するより直感的)
- エージェントが「世界の外」に行くことがあっても最近傍ゾーンに自動マッピング
  されるので、壁・境界なしでも空間意味論が壊れない (MVP の負債を先送りせずに済む)

これは `locate_zone` が決して `None` を返さない (全座標が 5 ゾーンの分割を成す)
という帰結を持つ。v1 の `ZoneNotFoundError` は不要になる。

### 1.4 Envelope 境界: **unbounded `asyncio.Queue` + `recv()`/`drain()` 2 面**

- T14 の WS 送信側は `await runtime.recv_envelope()` で 1 件ずつ pop
  (`asyncio.Queue.get()` の wrapper)
- テスト側は `runtime.drain_envelopes() -> list[ControlEnvelope]` で
  現時点の全件を非ブロッキング取得
- **maxsize=0 (unbounded)** でバックプレッシャは持たせない。MVP では
  5-8 エージェント × 10 秒間隔の cognition envelopes しか生まれず、
  30Hz の `AgentUpdateMsg` を送っても毎秒 300 件 / 100-500 byte 程度。
  仮に T14 が遅延しても 10 分間ぶんで 18 万件 ≈ 100 MB メモリ、MVP スコープ内。
  v1 の bounded + back-pressure は過剰エンジニアリングと判断。

### 1.5 クロック抽象: **抽象基底クラス (ABC)** 1 つのみ

v1 の `Protocol` (構造的部分型) はテスト・本番で duck-typing されるだけなので
`abc.ABC` + `Clock.monotonic()` / `Clock.sleep_until(due_at)` の 2 メソッドに
集約。Protocol を使わないのは:
- isinstance チェックを許容したい (ログで「このランタイムは ManualClock」と確認)
- Pydantic / mypy-strict で Protocol より ABC のほうがノイズが少ない
- `sleep_until(abs)` は `sleep(delta)` より絶対時刻設計に自然

## 2. モジュール構成

```
src/erre_sandbox/world/
├── __init__.py     # 公開 API re-export  (~30 行)
├── zones.py        # ZONE_CENTERS / ADJACENCY / locate_zone / default_spawn /
│                   # adjacent_zones  (pure, ~90 行)
├── physics.py      # Kinematics / step_kinematics / apply_move_command
│                   # (pure, ~110 行)
└── tick.py         # Clock ABC / RealClock / ManualClock /
                    # WorldRuntime / AgentRuntime / ScheduledEvent
                    # (asyncio, ~340 行)
```

### 2.1 `world/zones.py` (pure, ~90 行)

```python
from types import MappingProxyType
from typing import Final

ZONE_CENTERS: Final[Mapping[Zone, tuple[float, float, float]]] = MappingProxyType({
    Zone.STUDY:     (-20.0, 0.0, -20.0),
    Zone.PERIPATOS: (  0.0, 0.0,   0.0),
    Zone.CHASHITSU: ( 20.0, 0.0, -20.0),
    Zone.AGORA:     (  0.0, 0.0,  20.0),
    Zone.GARDEN:    ( 20.0, 0.0,  20.0),
})
"""Five zone centroids in world XZ-plane coordinates (y kept for future)."""

ADJACENCY: Final[Mapping[Zone, frozenset[Zone]]] = MappingProxyType({
    Zone.STUDY:     frozenset({Zone.PERIPATOS}),
    Zone.PERIPATOS: frozenset({Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN}),
    Zone.CHASHITSU: frozenset({Zone.PERIPATOS, Zone.GARDEN}),
    Zone.AGORA:     frozenset({Zone.PERIPATOS, Zone.GARDEN}),
    Zone.GARDEN:    frozenset({Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA}),
})


def locate_zone(x: float, y: float, z: float) -> Zone:
    """Return the Zone whose center is nearest in the XZ plane (Voronoi-lite)."""
    return min(
        ZONE_CENTERS.items(),
        key=lambda kv: (kv[1][0] - x) ** 2 + (kv[1][2] - z) ** 2,
    )[0]


def default_spawn(zone: Zone) -> Position:
    cx, cy, cz = ZONE_CENTERS[zone]
    return Position(x=cx, y=cy, z=cz, zone=zone)


def adjacent_zones(zone: Zone) -> frozenset[Zone]:
    return ADJACENCY[zone]
```

`locate_zone` は総 O(5) の浮動小数点乗算 10 回程度 = <1µs。30Hz × 8 agents でも余裕。

### 2.2 `world/physics.py` (pure, ~110 行)

```python
@dataclass(slots=True)
class Kinematics:
    """World-internal mutable kinematic state (NOT exposed via schemas.Position).

    schemas.Position は外部契約 (Godot に送る) として不変的に扱い、
    速度や目的地のような world の内部状態は本クラスで管理する。
    """
    position: Position
    destination: Position | None = None
    speed_mps: float = 1.3


def step_kinematics(
    kin: Kinematics,
    dt_seconds: float,
) -> tuple[Position, Zone | None]:
    """Advance by dt; return (new_position, zone_if_changed).

    destination=None なら位置据え置き・ゾーン変化なし。
    dest.xz 方向に dt * speed 進むが、残距離未満なら dest にスナップして dest を解除。
    新位置で locate_zone を走らせ、前位置の zone と違えば第 2 要素に入れる。
    """


def apply_move_command(kin: Kinematics, move: MoveMsg) -> None:
    kin.destination = move.target
    kin.speed_mps = move.speed
```

### 2.3 `world/tick.py` (asyncio, ~340 行)

```python
# ---------- Clock ----------

class Clock(ABC):
    @abstractmethod
    def monotonic(self) -> float: ...

    @abstractmethod
    async def sleep_until(self, due_at: float) -> None: ...


class RealClock(Clock):
    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep_until(self, due_at: float) -> None:
        delta = due_at - time.monotonic()
        if delta > 0:
            await asyncio.sleep(delta)


class ManualClock(Clock):
    """Deterministic clock for tests. `advance(dt)` jumps time and wakes sleepers."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start
        self._waiters: list[tuple[float, asyncio.Future[None]]] = []

    def monotonic(self) -> float:
        return self._now

    async def sleep_until(self, due_at: float) -> None:
        if due_at <= self._now:
            await asyncio.sleep(0)
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        heapq.heappush(self._waiters, (due_at, fut))
        await fut

    def advance(self, dt: float) -> None:
        """Move the clock forward by dt and resolve any waiters whose due_at <= now."""
        self._now += dt
        while self._waiters and self._waiters[0][0] <= self._now:
            _, fut = heapq.heappop(self._waiters)
            if not fut.done():
                fut.set_result(None)


# ---------- Scheduled events ----------

@dataclass(order=True)
class ScheduledEvent:
    due_at: float
    seq: int                           # FIFO tie-breaker
    period: float = field(compare=False)
    handler: Callable[[], Awaitable[None]] = field(compare=False)
    name: str = field(compare=False, default="")


# ---------- Agent runtime ----------

@dataclass(slots=True)
class AgentRuntime:
    agent_id: str
    state: AgentState
    persona: PersonaSpec
    kinematics: Kinematics
    pending: list[Observation] = field(default_factory=list)


# ---------- WorldRuntime ----------

class WorldRuntime:
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
    ) -> None:
        self._cycle = cycle
        self._clock: Clock = clock or RealClock()
        self._physics_dt = 1.0 / (physics_hz or self.DEFAULT_PHYSICS_HZ)
        self._cognition_period = cognition_period_s or self.DEFAULT_COGNITION_PERIOD_S
        self._heartbeat_period = heartbeat_period_s or self.DEFAULT_HEARTBEAT_PERIOD_S
        self._agents: dict[str, AgentRuntime] = {}
        self._events: list[ScheduledEvent] = []
        self._envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
        self._running = False
        self._seq = 0

    # ----- Registration -----

    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None:
        self._agents[state.agent_id] = AgentRuntime(
            agent_id=state.agent_id,
            state=state,
            persona=persona,
            kinematics=Kinematics(position=state.position),
        )

    def inject_observation(self, agent_id: str, obs: Observation) -> None:
        self._agents[agent_id].pending.append(obs)

    # ----- Envelope consumers -----

    async def recv_envelope(self) -> ControlEnvelope:
        return await self._envelopes.get()

    def drain_envelopes(self) -> list[ControlEnvelope]:
        out: list[ControlEnvelope] = []
        while not self._envelopes.empty():
            out.append(self._envelopes.get_nowait())
        return out

    # ----- Lifecycle -----

    async def run(self) -> None:
        self._schedule(self._physics_dt, self._on_physics_tick, "physics")
        self._schedule(self._cognition_period, self._on_cognition_tick, "cognition")
        self._schedule(self._heartbeat_period, self._on_heartbeat_tick, "heartbeat")
        self._running = True
        try:
            while self._running and self._events:
                ev = heapq.heappop(self._events)
                await self._clock.sleep_until(ev.due_at)
                try:
                    await ev.handler()
                except Exception:      # isolate handler failures, keep loop alive
                    logger.exception("world tick handler %s failed", ev.name)
                # re-schedule for next period (anti-drift: absolute due_at += period)
                ev.due_at += ev.period
                self._seq += 1
                heapq.heappush(
                    self._events,
                    replace(ev, seq=self._seq),
                )
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    # ----- Handlers -----

    async def _on_physics_tick(self) -> None:
        for rt in self._agents.values():
            new_pos, zone_changed = step_kinematics(rt.kinematics, self._physics_dt)
            if new_pos != rt.kinematics.position:
                rt.kinematics.position = new_pos
                rt.state = rt.state.model_copy(update={"position": new_pos})
            if zone_changed is not None:
                rt.pending.append(
                    ZoneTransitionEvent(
                        tick=rt.state.tick,
                        from_zone=rt.state.position.zone,
                        to_zone=zone_changed,
                        # ... other required fields
                    ),
                )

    async def _on_cognition_tick(self) -> None:
        if not self._agents:
            return
        results = await asyncio.gather(
            *(self._step_one(rt) for rt in self._agents.values()),
            return_exceptions=True,
        )
        # consume after gather so pending mutations are atomic
        for rt, res in zip(self._agents.values(), results, strict=True):
            self._consume_result(rt, res)

    async def _step_one(self, rt: AgentRuntime) -> CycleResult | BaseException:
        obs = rt.pending
        rt.pending = []
        try:
            return await self._cycle.step(
                rt.state, rt.persona, obs,
                tick_seconds=self._cognition_period,
            )
        except Exception as exc:      # pragma: log only, do not crash loop
            return exc

    def _consume_result(
        self, rt: AgentRuntime, res: CycleResult | BaseException,
    ) -> None:
        if isinstance(res, BaseException):
            logger.exception("agent %s step failed", rt.agent_id, exc_info=res)
            return
        rt.state = res.agent_state
        for env in res.envelopes:
            if isinstance(env, MoveMsg):
                apply_move_command(rt.kinematics, env)
            self._envelopes.put_nowait(env)

    async def _on_heartbeat_tick(self) -> None:
        self._envelopes.put_nowait(
            WorldTickMsg(tick=0, active_agents=len(self._agents)),
        )

    # ----- Scheduling helper -----

    def _schedule(
        self, period: float, handler: Callable[[], Awaitable[None]], name: str,
    ) -> None:
        self._seq += 1
        heapq.heappush(
            self._events,
            ScheduledEvent(
                due_at=self._clock.monotonic() + period,
                seq=self._seq,
                period=period,
                handler=handler,
                name=name,
            ),
        )
```

### 2.4 `world/__init__.py`

11 シンボル re-export:
`Clock / RealClock / ManualClock / WorldRuntime / AgentRuntime /
Kinematics / step_kinematics / apply_move_command /
ZONE_CENTERS / locate_zone / default_spawn`

## 3. 変更対象

### 新規作成 (9 ファイル)

| ファイル | 想定行数 |
|---|---|
| `src/erre_sandbox/world/__init__.py` | ~25 |
| `src/erre_sandbox/world/zones.py` | ~90 |
| `src/erre_sandbox/world/physics.py` | ~110 |
| `src/erre_sandbox/world/tick.py` | ~340 |
| `tests/test_world/__init__.py` | 0 |
| `tests/test_world/conftest.py` | ~90 |
| `tests/test_world/test_zones.py` | ~80 |
| `tests/test_world/test_physics.py` | ~100 |
| `tests/test_world/test_tick.py` | ~260 |

合計 新規 ~1095 行

### 修正 (1 ファイル)

`.steering/_setup-progress.md` — Phase 8 に T13 エントリ追加

## 4. 影響範囲

- `cognition/cycle.py` 変更不要 (`tick_seconds` 予約シグネチャをそのまま使う)
- `schemas.py` 変更不要 (Kinematics は world 内部型)
- 既存テスト回帰なし (test_world/ は独立 conftest)
- T14 への契約: `recv_envelope()` / `drain_envelopes()` / `inject_observation()` /
  `register_agent()` / `run()` / `stop()` の 6 API

## 5. 既存パターンとの整合性

| パターン | 参照 | v2 での適用 |
|---|---|---|
| `ClassVar DEFAULT_*` + kw-only `__init__` DI | `cognition/cycle.py:107` | `WorldRuntime` のすべてのパラメータ |
| `rng: Random \| None = None` 注入 | `cognition/cycle.py:126` | `clock: Clock \| None = None` |
| `*Error` 1 種 | `cognition.CognitionError` | **不要** (Voronoi で 例外を発生させない) |
| frozen/dataclass 戻り値 | `CycleResult` | `ScheduledEvent` に `@dataclass(order=True)` |
| `asyncio.gather(return_exceptions=True)` | (既存 inference 未使用) | 認知 tick の N 並列で採用 |
| tests ミラー構造 | `tests/test_cognition/` | `tests/test_world/` 新規 |

## 6. テスト戦略

### 6.1 `test_zones.py` (pure, ~80 行)

- 5 ゾーンの代表点 → 自身のゾーンが返る (5 ケース)
- 中間点 (2 ゾーン間の等距離) → Voronoi 決着 (同点時は辞書順 / seed 固定で検証)
- 遠方点 (1000, 0, 1000) → 最近傍ゾーン (GARDEN)
- `adjacent_zones` が対称
- `ZONE_CENTERS` / `ADJACENCY` が MappingProxyType
- `default_spawn(z).zone == z`

### 6.2 `test_physics.py` (pure, ~100 行)

- destination=None で step → 位置不変・zone_changed=None
- 残距離 > dt*speed: 直線上を dt*speed 進み dest は保持
- 残距離 <= dt*speed: dest にスナップし dest=None、zone_changed は dest の zone
- ゾーン境界跨ぎ: zone_changed に遷移先 Zone
- `apply_move_command` が dest / speed を上書き

### 6.3 `test_tick.py` (asyncio, ~260 行)

使うフィクスチャ: `ManualClock`, `MockCycle` (step 呼び出しを記録)

- `run()` 起動 → `ManualClock.advance(1/30)` → `_on_physics_tick` が 1 回発火
- `advance(10.0)` → cognition 1 回 + heartbeat 10 回 + physics 300 回
- エージェント 3 体登録 → cognition tick で `asyncio.gather` が 3 step を同時発火
- `MockCycle.step` の 1 つを例外にする → 他 2 エージェントの結果は通常消費、
  当該エージェントは envelope 送らず loop 継続
- MoveMsg が CycleResult.envelopes に入る → 次の物理 tick で位置補間
- ゾーン境界跨ぎで次の cognition tick の observations に ZoneTransitionEvent が渡る
- `CycleResult.llm_fell_back=True` のケースでも runtime は継続し envelopes は流れる
- `stop()` で `run()` が return
- `drain_envelopes()` の順序 (先に入った AgentUpdateMsg → 後の SpeechMsg)
- heartbeat: `advance(1.0)` × 5 で 5 件の WorldTickMsg

### 6.4 conftest.py (~90 行)

- `manual_clock()` — fresh `ManualClock` を返す
- `mock_cycle()` — `MagicMock(spec=CognitionCycle)` + 呼び出し記録用 deque
- `world_runtime(mock_cycle, manual_clock)` — 登録済みエージェントを持たない最小 runtime

### 6.5 回帰確認

- baseline: T12 完了時点全グリーン
- 期待追加: +30 件前後
- skip は据え置き

## 7. ロールバック計画

- 新規ファイルのみ、`git revert` 1 コミットで復元
- ゾーン境界チューニングは `ZONE_CENTERS` を編集するだけ
- 物理 / 認知 / heartbeat の周期はすべて `__init__` 引数で外から上書き可能

## 8. 関連する Skill

- `python-standards` — 型ヒント、kw-only、f-string、asyncio の基本
- `error-handling` — `asyncio.gather(return_exceptions=True)` と handler 例外隔離
- `architecture-rules` — world → cognition のみ (memory/inference を直接触らない)
- `test-standards` — pytest-asyncio、ManualClock による決定論テスト

## 9. v2 の内部ハイライト (v1 との差別化ポイント)

| 観点 | v1 | v2 |
|---|---|---|
| 並行性 | asyncio.TaskGroup + 3 タスク | 単一コルーチン + heapq スケジューラ |
| 認知の N 並列 | 逐次 (M7 まで gather せず) | `asyncio.gather(return_exceptions=True)` |
| 時間精度 | `sleep(dt)` 累積ドリフトあり | 絶対 `sleep_until(due_at)` ドリフト無 |
| ゾーン判定 | AABB 矩形 + `ZoneNotFoundError` | Voronoi 最近傍 (例外ゼロ) |
| Clock 抽象 | Protocol | ABC + RealClock / ManualClock |
| Envelope | bounded Queue + back-pressure | unbounded Queue + `recv()`/`drain()` |
| 新周期タスク追加 | TaskGroup にタスク追加 (分岐) | `schedule(period, handler)` 1 行 |
| 想定 LOC | ~1120 | ~1095 |

## 設計判断の履歴

- 初回案 (`design-v1.md`) と再生成案 (本ファイル = v2) を `design-comparison.md` で比較
- 採用: **v2**
- 根拠:
  1. 時間ドリフト排除が M10-11 評価フレームワーク (Ripley K / Lomb-Scargle) の
     精度に直結する
  2. 単一コルーチン設計により状態競合の余地を構造で排除できる (ロック不要)
  3. 認知 N 並列 (`asyncio.gather`) が M4 の 3 体対話時点から必要であり、
     v1 の「M7 まで逐次 → gather 化」は 2 回書くコストが発生する
  4. Voronoi 最近傍は MVP の物理前提 (壁なし / 立方体アバター) に適合し、
     `ZoneNotFoundError` と AABB 境界分岐を排除できる
  5. `schedule(period, handler)` 1 行で M4 反省ループ・M7 永続化スナップショットを
     追加できる拡張容易性
- v1 の長所の補完: ハンドラ関数を `_on_physics_tick` / `_on_cognition_tick` /
  `_on_heartbeat_tick` に分離することで「タスク分離の読みやすさ」は同等に実現。
  back-pressure は T14 実装時に `asyncio.Queue(maxsize=N)` への差し替え 1 行で対応可能
