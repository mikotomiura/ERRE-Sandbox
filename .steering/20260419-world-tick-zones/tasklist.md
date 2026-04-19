# タスクリスト — T13 world-tick-zones

各タスクは 30 分以内の粒度。`test-standards` / `python-standards` /
`architecture-rules` / `error-handling` Skill に準拠。

## 準備

- [x] docs (architecture / functional-design / repository-structure / development-guidelines) 読了
- [x] file-finder / impact-analyzer で既存パターンと影響範囲を確認
- [x] design-v1 生成 → `/reimagine` で v2 生成 → 比較 → v2 採用確定

## 実装フェーズ 1: 純粋ロジック (zones + physics)

### zones.py

- [x] `tests/test_world/__init__.py` と `tests/test_world/test_zones.py` 骨格を作成
      (fail する TDD 雛形)
- [x] `src/erre_sandbox/world/zones.py` に
      `ZONE_CENTERS` / `ADJACENCY` / `locate_zone` / `default_spawn` /
      `adjacent_zones` を実装
- [x] `test_zones.py` に 5 ケース (各ゾーン代表点 / 中間点 / 遠方点 /
      ADJACENCY 対称性 / MappingProxyType 不変) を書いてグリーン

### physics.py

- [x] `tests/test_world/test_physics.py` 骨格
- [x] `src/erre_sandbox/world/physics.py` に
      `Kinematics` / `step_kinematics` / `apply_move_command` を実装
- [x] `test_physics.py` に 5 ケース
      (destination=None / 進行中 / 到達時 snap / ゾーン跨ぎ / MoveMsg 適用)
      を書いてグリーン

## 実装フェーズ 2: asyncio スケジューラ

### tick.py — Clock 抽象

- [x] `src/erre_sandbox/world/tick.py` に
      `Clock` ABC / `RealClock` / `ManualClock` を実装
- [x] `tests/test_world/conftest.py` に `manual_clock` fixture を追加
- [x] `test_tick.py` の冒頭に ManualClock 単体テスト
      (advance で waiter が解放される / 同一 due_at の順序) を書いてグリーン

### tick.py — WorldRuntime コア

- [x] `ScheduledEvent` dataclass (`order=True`, seq tie-breaker) を追加
- [x] `AgentRuntime` dataclass を追加
- [x] `WorldRuntime.__init__` / `register_agent` / `inject_observation` /
      `recv_envelope` / `drain_envelopes` / `stop` / `_schedule` を実装
- [x] `WorldRuntime.run()` のメインループ (heapq pop → sleep_until → handler →
      anti-drift reschedule → 例外隔離) を実装

### tick.py — 3 ハンドラ

- [x] `_on_heartbeat_tick` (WorldTickMsg を envelope queue に投入) を実装
- [x] `_on_physics_tick` (全 agent に step_kinematics、ゾーン跨ぎで
      ZoneTransitionEvent を pending に追加、Position 変化で state.position 更新)
- [x] `_on_cognition_tick` + `_step_one` + `_consume_result`
      (asyncio.gather / return_exceptions / MoveMsg を apply_move_command)

### tick.py — 統合テスト

- [x] `tests/test_world/conftest.py` に `mock_cycle` / `world_runtime` fixture
- [x] `test_tick.py` に以下のテスト:
  - [x] `ManualClock.advance(1/30)` → 物理 tick 1 回発火
  - [x] `advance(10.0)` → cognition 1 回 + heartbeat 10 回 + physics 300 回
  - [x] 3 体登録 → cognition で gather が 3 step 同時発火
  - [x] 1 体の step() を例外 → 他 2 体通常消費、loop 継続
  - [x] MoveMsg → 次 physics tick で destination へ補間
  - [x] ゾーン跨ぎ → 次 cognition の observations に ZoneTransitionEvent
  - [x] `llm_fell_back=True` でも loop 継続
  - [x] `stop()` で run() が return
  - [x] `drain_envelopes()` が FIFO 順
  - [x] heartbeat: advance(1.0) × 5 で WorldTickMsg 5 件

## 実装フェーズ 3: 公開 API と配線

- [x] `src/erre_sandbox/world/__init__.py` に 11 シンボル re-export
- [x] `from erre_sandbox.world import *` が architecture-rules に違反しないことを
      grep で確認 (`from erre_sandbox.ui` / `from erre_sandbox.inference` を
      `world/` 内部が直接 import していないこと)

## 検証フェーズ

- [x] `uv run pytest tests/test_world/ -v` 全グリーン
- [x] `uv run pytest` 全テスト緑 (既存回帰なし)
- [x] `uv run ruff check src/erre_sandbox/world tests/test_world`
- [x] `uv run ruff format --check src/erre_sandbox/world tests/test_world`
- [x] `uv run mypy --strict src/erre_sandbox/world` (または pyproject.toml の
      mypy 設定に従う)

## レビュー

- [x] code-reviewer サブエージェントで差分レビュー (HIGH は必ず対応)
- [x] HIGH 指摘対応
- [x] MEDIUM 指摘はユーザー確認

## ドキュメント

- [x] docs/functional-design.md § "機能 1d Express" / "機能 2 認知サイクル" への
      追記判断 (world tick が存在する旨の 1-2 行)
- [x] docs/architecture.md §3 Simulation Layer の記述と実装の一致確認
- [x] docs/glossary.md に新用語追加不要 (既に Zone / tick / 反省が定義済み)

## 完了処理

- [x] `.steering/_setup-progress.md` の Phase 8 に T13 完了エントリ追加
- [x] design.md 最終化 (実装中に確定した細部があれば追記)
- [x] decisions.md 作成 (v2 採用の決定履歴 + Voronoi 採用 + unbounded Queue 採用)
- [x] `feature/world-tick-zones` ブランチで commit
      (Conventional Commits: `feat(world): T13 world-tick-zones — ...`)
- [x] PR 作成 (任意)
