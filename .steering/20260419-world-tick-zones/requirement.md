# T13 world-tick-zones

## 背景

T12 で `cognition/cycle.py` の `CognitionCycle.step(agent_state, persona, observations)` が
1 tick 分の CoALA/ERRE パイプラインを走らせる単位として完成した。しかし現在は以下が欠落している:

- **駆動役 (ドライバ) 不在**: `step()` を **時間軸 (tick) 上で周期的に呼び出す** ループがない。
  docs/architecture.md §1 が要求する「asyncio tick loop @ 30Hz world / 0.1Hz agent cognition」が未実装。
- **ゾーン定義の欠落**: `schemas.Zone` は 5 値の enum しかなく、座標・隣接・入退境界などの
  **空間セマンティクス**を持つ物理側の表現がない。`ZoneTransitionEvent` を自然発生させる仕組みがない。
- **上位層へのブロッキング**: T14 (gateway-fastapi-ws) は WS に送る envelopes の生成源として
  world tick を前提とする。T13 がないと T14 が着手できず、M2 の E2E 動作が組めない。

docs/functional-design.md §2 機能1d (Express) と §5 非機能要件 "ティックレート" に直接対応する
**Simulation Layer の中核タスク**。CLAUDE.md および docs/architecture.md §3 が想定する責務を
`src/erre_sandbox/world/` 配下に最小で満たす。

## ゴール

`world/` モジュールが、単一プロセス内で:

1. **5 ゾーンの空間表現**を `zones.py` に持ち、`Position.zone` と座標 `(x, y, z)` の
   相互変換 (座標 → 所在ゾーン判定、ゾーン → 代表ポイント) を提供する。
2. **ワールドティックループ** (`tick.py`) が asyncio 上で、
   - 物理: 30 Hz でエージェント位置を微小更新 (現時点は等速直線移動のみ)
   - 認知: 10 秒ごと (0.1 Hz) に各エージェントの `CognitionCycle.step()` を呼び出し、
     その `CycleResult.envelopes` を外部購読者 (T14 で FastAPI WS) に受け渡せる形に
     キューイングする
3. **ゾーン遷移の検知**: エージェントが位置更新の結果として所属ゾーンが変わった瞬間に
   `ZoneTransitionEvent` を生成し、次の認知 tick で `observations` として
   `CognitionCycle.step()` に流す。
4. **`WorldTickMsg` ハートビート発行**: 物理 tick ごと (または 1 Hz 程度に間引き) に
   `active_agents` 付きの heartbeat を envelope キューに投入。

## スコープ

### 含むもの
- `src/erre_sandbox/world/__init__.py` — 公開 API re-export
- `src/erre_sandbox/world/zones.py` — 5 ゾーンのレイアウト定数、点-in-zone 判定、
  代表点 (spawn / waypoint) テーブル、隣接グラフ (peripatos ↔ agora ↔ garden ↔ chashitsu ↔ study)
- `src/erre_sandbox/world/tick.py` — `WorldClock` / `WorldLoop` / `EnvelopeQueue` 相当の
  asyncio コンポーネント。`run()` / `stop()` / `register_agent(agent_state, persona)` /
  `drain_envelopes()` の薄い API
- `src/erre_sandbox/world/physics.py` (最小) — 位置の等速直線移動のみ。衝突・NavMesh は持たない
- 単体テスト `tests/test_world/test_zones.py`, `tests/test_world/test_tick.py`, `tests/test_world/test_physics.py`
- 決定論テスト用に `WorldClock` を注入可能にする (`MonotonicClock` / `FakeClock`)
- `MoveMsg` が `world` に届いた時にエージェントの `destination` を更新する経路
  (`CycleResult.envelopes` から `MoveMsg` を取り出して内部状態に反映)

### 含まないもの
- FastAPI / WebSocket サーバー本体 → **T14** (`gateway-fastapi-ws`)
- Godot 側のシーン・アバター → T15-T17
- 反省 (reflection) の本体実装 → M4 以降 (T13 は `reflection_triggered=True` を
  キューに記録するのみで、実際の LLM 反省呼び出しは行わない)
- 複数エージェントの並列認知 tick 内部での真の並列化 (M7 PIANO 並列までは逐次 `gather` で可)
- NavMesh / 経路探索 / 衝突応答 / 重力 (MVP 範囲外、MASTER-PLAN R8 に準拠)
- ゾーン別のビジュアル差異 (Godot 側)
- ERRE モード FSM の自動遷移トリガー (M5 `erre-mode-fsm` で扱う。T13 では
  `ZoneTransitionEvent` を Observation に落とすところまで)
- SGLang への切替 (M7)
- 永続化 (SQLite への tick スナップショット) — 最小では memory store の書き込みのみに留め、
  AgentState 毎 tick スナップショットは M4 以降

## 受け入れ条件

- [ ] `src/erre_sandbox/world/zones.py` が 5 ゾーンの矩形/円形領域定義と
      `locate_zone(x, y, z) -> Zone`、`default_spawn(zone) -> Position` を提供する
- [ ] `src/erre_sandbox/world/tick.py` の `WorldLoop.run()` が asyncio 上で
      30 Hz の物理 tick と 10 秒ごとの認知 tick を並行駆動できる
      (`FakeClock` で決定論的に advance 可能)
- [ ] 登録済みエージェントが `MoveMsg` を発行 → 物理 tick で `Position` が補間更新され、
      ゾーン境界をまたいだ瞬間に `ZoneTransitionEvent` が次の認知 tick で
      `CognitionCycle.step()` に渡る
- [ ] `WorldLoop` が produce した `ControlEnvelope` を `drain_envelopes()` で
      順序保証付きで取り出せる (T14 がこれを WS に流す前提の API)
- [ ] `LLMUnavailable` 等で `CycleResult.llm_fell_back=True` が返っても
      ループは継続し、次 tick を止めない (error-handling Skill: crash-loud 除外枠)
- [ ] `uv run pytest tests/test_world/` がグリーン、既存テストに回帰がない
      (T12 完了時点の baseline +α)
- [ ] `ruff check` / `ruff format --check` / `mypy --strict src/erre_sandbox/world/` が通る
- [ ] `from erre_sandbox.world import *` が `ui/`, `inference/` 以外を import していないこと
      (architecture-rules: world → cognition → {memory, inference})

## 関連ドキュメント

- `docs/architecture.md` §1 全体図 / §3 Simulation Layer / §5 データフロー 1
- `docs/functional-design.md` §2 機能 1d Express / §2 機能 2 認知サイクル / §5 非機能要件
- `docs/repository-structure.md` §2 `src/erre_sandbox/world/` の責務 / §4 依存方向
- `docs/glossary.md` Zone / tick / 反省 / 一期一会
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` T13 行 + §11 Critical Files
- `.steering/20260419-cognition-cycle-minimal/design.md` — T13 が呼び出す `CognitionCycle.step()` の契約
- `src/erre_sandbox/schemas.py` — `Zone`, `Position`, `ZoneTransitionEvent`,
  `ControlEnvelope` (AgentUpdateMsg / MoveMsg / AnimationMsg / WorldTickMsg)
- `.claude/skills/python-standards/SKILL.md` (primary)
- `.claude/skills/error-handling/SKILL.md` (tick ループの例外隔離)
- `.claude/skills/architecture-rules/SKILL.md` (依存方向)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes (推奨)**
- 理由: (1) WorldLoop の tick スケジューリング手法は複数案が考えられる
  (単一 `asyncio.sleep` ループ / `asyncio.TaskGroup` + 2 タスク / `apscheduler` 類 /
  自前 `FakeClock` 駆動のみ) ため、初回案に引きずられやすい。
  (2) Envelope の「生成→消費」境界 (コールバック / Queue / AsyncIterator) は
  T14 の WS 実装と結合するインターフェースで、後戻りコストが高い。
  (3) ゾーン表現も矩形 vs ポリゴン vs 名前付き領域など選択肢が複数。
  これら設計判断を `/reimagine` で一度破棄し再生成し、2 案比較してから実装に入る。
