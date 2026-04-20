# m5-world-zone-triggers — ERRE mode FSM を world tick にフック

## 背景

M5 critical path: `m5-contracts-freeze` (PR #56) → `m5-erre-mode-fsm` (PR #57) →
**本タスク** → `m5-orchestrator-integration` → `m5-acceptance-live`。

前タスク `m5-erre-mode-fsm` (merged 2026-04-21) で `DefaultERREModePolicy` の
concrete 実装が入った。しかし現状は **呼び出し側が存在しない** ため FSM は
dead code。`world/tick.py::_on_physics_tick` は `ZoneTransitionEvent` を
`rt.pending` に追加するだけで、`_on_cognition_tick` がそれを
`CognitionCycle.step` に流すだけ。`AgentState.erre` は mode が bootstrap 以後
更新されない。

本タスクは FSM を tick ループに wire up し、agent の ERRE mode が observation に
応じて **実際に遷移する** 状態まで仕上げる。これで `m5-erre-sampling-override-live`
が FSM 更新後の mode を参照できるようになり、`m5-orchestrator-integration` の
feature flag wiring に進める。

加えて、前タスク decisions.md §4 で先送りした **`world/` → `erre/` layer 依存**
の可否判断を本タスクで決着させる (architecture-rules の update を含む可能性あり)。

## ゴール

`WorldRuntime` が `ERREModeTransitionPolicy` の実装インスタンスを受け取り、
各 cognition tick で observation を FSM にかけ、返ってきた次 mode で
`AgentState.erre` を更新する。更新時は `ERREModeShiftEvent` を emit して
`rt.pending` に追記し、次 tick 以降の FSM 判定で trace できるようにする。

後続 task はこの wiring を前提に:
- `m5-erre-sampling-override-live`: `agent_state.erre.sampling_overrides` が
  FSM 更新後の値を反映
- `m5-orchestrator-integration`: feature flag `--disable-erre-fsm` で FSM を
  off に切替可能な構成

## スコープ

### 含むもの

- **Layer 依存の許可**: `.claude/skills/architecture-rules/SKILL.md` の依存
  テーブルに `world/ → erre/` を追加 (決定と根拠を decisions.md に記録)
- **`WorldRuntime` の FSM 受入口**:
  - constructor に `erre_policy: ERREModeTransitionPolicy | None = None` 引数追加
    (None = 無効、既存 bootstrap の挙動を維持)
  - 新メソッド `attach_erre_policy(policy)` (後付け注入用、DialogScheduler と同じ
    pattern)
- **Tick hook の実装**:
  - `_on_cognition_tick` で `_consume_result` の後に FSM を呼ぶ
  - observation は `_step_one` が pop する前の snapshot を使う (順序維持)
  - FSM が非 None を返したら `rt.state.erre` を `ERREMode` で更新
    (`entered_at_tick` / `sampling_overrides` は persona_erre Skill §ルール 2 の
    delta 表から取得するが、本タスクでは **delta 反映は `m5-erre-sampling-override-live`
    に委譲** し、ここでは `ERREMode(name=new_mode, entered_at_tick=tick)` の最小更新)
  - `ERREModeShiftEvent(previous, current, reason="scheduled")` を `rt.pending` に
    追記 (次 tick 以降の FSM 判定に反映できるようにする)
- **Tests**:
  - `tests/test_world/test_tick.py` に:
    - FSM 未注入時は従来挙動を維持 (既存 test 全 PASS)
    - FSM 注入時: zone entry → mode 更新 + ERREModeShiftEvent emit
    - FSM 注入時: fatigue InternalEvent → CHASHITSU 更新
    - FSM 注入時: current と同じ mode (FSM が None 返却) → 何もしない
- **docs update**: 必要に応じて architecture.md / repository-structure.md を
  軽微に追記

### 含まないもの

- **`bootstrap.py` で `DefaultERREModePolicy` をインスタンス化し wire する実装** →
  `m5-orchestrator-integration` の責務 (feature flag と一緒に追加)
- **`compose_sampling()` の live 反映** → `m5-erre-sampling-override-live`
- **InternalEvent (fatigue / shuhari) を synthesize するコード** → 別 task。
  本 task は InternalEvent が渡ってきた場合の挙動だけ保証
- **Godot 側 mode tint** → `m5-godot-zone-visuals`
- **ERRE mode に対応した `sampling_overrides` の delta 値の注入** → 上記 sampling
  override task
- **new persona YAML / zone**

## 受け入れ条件

- [ ] `architecture-rules` Skill に `world/ → erre/` が明示的に許可エントリとして
      追加される (変更理由も SKILL.md に注記)
- [ ] `WorldRuntime.__init__` に `erre_policy: ERREModeTransitionPolicy | None = None`
      追加 (default で既存挙動を維持)
- [ ] `WorldRuntime.attach_erre_policy(policy)` メソッドが存在し、後付け注入可能
- [ ] FSM 未注入時は既存 test (tests/test_world/*) が 0 failures
- [ ] FSM 注入時に zone entry → `AgentState.erre.name` 更新 + `ERREModeShiftEvent`
      が次 tick の observation に載る
- [ ] FSM 注入時に fatigue InternalEvent → CHASHITSU 更新
- [ ] FSM が None を返したら `AgentState.erre` も `rt.pending` も変更なし
- [ ] `uv run pytest -q` 全 PASS (既存 544 + 新規 test)
- [ ] `uv run ruff check src tests` / `ruff format --check` PASS
- [ ] `uv run mypy src/erre_sandbox` 0 errors
- [ ] `docs/architecture.md` に layer 依存変更が反映される (該当箇所)

## 関連ドキュメント

- `.steering/20260420-m5-planning/design.md` §3 新軸 M 軸 / §依存グラフ
- `.steering/20260420-m5-erre-mode-fsm/decisions.md` §4 (本 task で layer 判断)
- `.steering/20260420-m5-erre-mode-fsm/design.md` (FSM の signature + semantics)
- `src/erre_sandbox/world/tick.py` (`_on_cognition_tick` / `_step_one` が変更点)
- `src/erre_sandbox/erre/__init__.py` (FSM と canonical map の export)
- `.claude/skills/architecture-rules/SKILL.md` (本 task で update 予定)
- `.claude/skills/persona-erre/SKILL.md` §ルール 2 (delta 表は本 task では使わず、
  後続 sampling-override task が使う)

## 運用メモ

- **タスク種別**: 新機能追加 (FSM wiring の hook 追加 + constructor 拡張 +
  architecture-rules 更新)
- **破壊と構築 (/reimagine) 適用**: **Yes**
  - 理由: 複数の設計案が考えられる。特に (a) FSM の呼出箇所 (world/tick.py vs
    cognition/cycle.py)、(b) DI の形 (constructor vs attach メソッド vs
    route-through-cognition)、(c) observation 取得タイミング (step 前 snapshot vs
    CycleResult 経由)、(d) ERREModeShiftEvent の emit 先 (rt.pending vs envelope
    queue)、(e) architecture-rules の update 方針 (world→erre OK か、
    cognition→erre 経由で回避するか)。これらは downstream 3 sub-task に影響するので
    慎重に決めたい。memory `feedback_reimagine_scope.md` 「迷ったら適用」にも合致。
