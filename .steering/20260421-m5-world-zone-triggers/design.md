# 設計 — m5-world-zone-triggers (v2 reimagine 再生成案)

## 実装アプローチ

**FSM を `CognitionCycle.step()` 内に内包する** — mode 遷移は cognitive
な判断なので cognition 層に置くのが自然、という観点で再構成する。世界側
(`world/tick.py`) には一切触れない。`cognition/ → erre/` を layer 依存として
明示追加し、`world/ → erre/` の変更は不要にする。

### 処理フロー

```
Physics tick (30Hz):
  - Kinematics step, zone change 判定
  - ZoneTransitionEvent を rt.pending に append    ← 既存 (無変更)
Cognition tick (10s):
  - rt.pending を _step_one が snapshot + pop     ← 既存 (無変更)
  - CognitionCycle.step(agent_state, persona, observations, tick_seconds):
    - Step 1: episodic write (既存)
    - Step 2: advance_physical (既存)
    - Step 3: reflection trigger (既存)
    ...
    - Step N-1 (新設): ERRE mode FSM step
      - candidate = erre_policy.next_mode(
          current=agent_state.erre.name,
          zone=agent_state.position.zone,
          observations=observations,
          tick=agent_state.tick,
        )
      - If candidate not None:
        - new_erre = ERREMode(name=candidate, entered_at_tick=agent_state.tick)
        - agent_state = agent_state.model_copy(update={"erre": new_erre})
        - shift_event = ERREModeShiftEvent(previous, current, reason="scheduled")
        - envelopes.append(AgentUpdateMsg(...)) は既存フロー任せ
    - Step N: return CycleResult(agent_state, envelopes, new_memory_ids, ...)
  - _consume_result が rt.state = res.agent_state を適用          ← 既存 (無変更)
```

world/tick.py は **完全に無変更** になる。既に res.agent_state を `_consume_result`
が applying しているので、cycle 内で mode を変えれば自動的に伝播する。

### Hook location: CognitionCycle.step() 内、episodic write の直後

- episodic write → 物理/認知状態更新 → **FSM** → reflection → envelope build → return
- FSM は `observations` を input にして mode 候補を返すだけ。既存の
  cognition pipeline を壊さず追加できる
- FSM が mode を変更したら、その後に LLM call がある場合 (同じ step 内の
  content generation) は即座に新 mode の sampling_overrides を使える

### DI pattern: CognitionCycle constructor の拡張

既存の `reflector` 注入パターンを踏襲:

- `CognitionCycle.__init__(..., erre_policy: ERREModeTransitionPolicy | None = None)`
- default None = FSM 無効 (既存挙動維持)

bootstrap 側で `CognitionCycle(erre_policy=DefaultERREModePolicy())` とする
(これは `m5-orchestrator-integration` の責務)。

### Layer rule update: `cognition/ → erre/` を architecture-rules に追加

- `cognition/` は既に `inference/`, `memory/`, `schemas.py` に依存
- `erre/` を追加すると: `cognition/ → erre/ → schemas.py` で cycle なし

この変更は `world/ → erre/` より弱い (cognition は元々 observation を解釈する
domain logic を持つので、その延長として自然)。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/cognition/cycle.py`:
  - import 追加: `ERREMode`, `ERREModeShiftEvent`, `ERREModeTransitionPolicy`
    (schemas のみ)
  - `CognitionCycle.__init__` に `erre_policy` 引数追加
  - `step()` 内の適切な位置に `_maybe_apply_erre_fsm` 呼び出しを追加
  - `_maybe_apply_erre_fsm(agent_state, observations)` private helper を追加
- `.claude/skills/architecture-rules/SKILL.md`:
  - 依存テーブルに `cognition/ → erre/` を allowed で追加
  - 既存 `erre/` 行の「依存先」に `cognition/` が他から許されることを併記しない
    (erre/ は cognition/ に依存しない、一方通行)
- `docs/architecture.md`:
  - cognition layer の説明に「ERRE mode FSM を `erre/` から注入」を追加
- `tests/test_cognition/` に:
  - `test_cycle_applies_erre_fsm_on_zone_observation`
  - `test_cycle_emits_mode_shift_event_when_fsm_returns_new_mode`
  - `test_cycle_fsm_returns_none_leaves_state_unchanged`
  - `test_cycle_without_erre_policy_skips_fsm`

### 新規作成するファイル

- なし

### 削除するファイル

- なし

## 実装擬似コード (cognition/cycle.py に追加する helper)

```python
from erre_sandbox.schemas import (
    ...
    ERREMode,
    ERREModeShiftEvent,
    ERREModeTransitionPolicy,
)


class CognitionCycle:
    def __init__(
        self,
        *,
        retriever: Retriever,
        store: MemoryStore,
        embedding: EmbeddingClient,
        llm: OllamaChatClient,
        rng: Random | None = None,
        update_config: StateUpdateConfig | None = None,
        reflector: Reflector | None = None,
        erre_policy: ERREModeTransitionPolicy | None = None,   # ← 新規
    ) -> None:
        ...
        self._erre_policy = erre_policy

    def _maybe_apply_erre_fsm(
        self,
        agent_state: AgentState,
        observations: Sequence[Observation],
    ) -> tuple[AgentState, ERREModeShiftEvent | None]:
        """Apply the FSM if one is configured; otherwise no-op.

        Returns the (possibly updated) AgentState and an emitted
        ERREModeShiftEvent (or None if no transition happened).
        """
        if self._erre_policy is None:
            return agent_state, None
        candidate = self._erre_policy.next_mode(
            current=agent_state.erre.name,
            zone=agent_state.position.zone,
            observations=observations,
            tick=agent_state.tick,
        )
        if candidate is None:
            return agent_state, None
        previous = agent_state.erre.name
        new_erre = ERREMode(name=candidate, entered_at_tick=agent_state.tick)
        new_state = agent_state.model_copy(update={"erre": new_erre})
        shift_event = ERREModeShiftEvent(
            tick=agent_state.tick,
            agent_id=agent_state.agent_id,
            previous=previous,
            current=candidate,
            reason="scheduled",
        )
        return new_state, shift_event

    async def step(
        self,
        agent_state: AgentState,
        persona: PersonaSpec,
        observations: Sequence[Observation],
        *,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> CycleResult:
        # ... existing step 1-2 ...

        # Step (new): ERRE mode FSM
        agent_state, shift_event = self._maybe_apply_erre_fsm(
            agent_state, observations,
        )
        # shift_event は CycleResult の中で後続ステップに使える。現時点では
        # log または envelope への添付は不要 (AgentState.erre 更新が自動的に
        # 次 agent_update で Godot へ propagate)。
        # Shift event はメモリ・リフレクション対象に加える場合は observations
        # に追記する選択肢もある (decisions.md で判断)

        # ... existing step 3+ ...

        return CycleResult(agent_state=agent_state, ...)
```

## 影響範囲

- **wire 互換**: なし (contract 未変更)
- **world/tick.py**: **完全無変更** (これが v2 の最大の価値)
- **bootstrap.py**: 本 task では変更なし。`m5-orchestrator-integration` で
  `CognitionCycle(erre_policy=DefaultERREModePolicy())` と wire
- **既存 test**: `erre_policy=None` 時は既存挙動、cognition/cycle.py 既存 test
  全 PASS
- **architecture-rules**: `cognition/ → erre/` 許可追加 (`world/ → erre/`
  は発生しない)

## 既存パターンとの整合性

- `reflector` 注入パターン (cycle.py で既に採用) を 1:1 複製
- `model_copy(update={...})` は cycle.py 内で既に複数箇所で使用
- Protocol 型でタイプヒントし concrete は DI で差替は reflector と同構造
- `ERREModeShiftEvent` 発火は既存 Observation discriminated union の自然な拡張

## テスト戦略

### 単体 (`tests/test_cognition/test_cycle.py` に追加)

- `test_cycle_no_erre_policy_keeps_mode_static` — default None で既存挙動維持
- `test_cycle_erre_policy_updates_agent_state_erre` — Mock policy が
  CHASHITSU を返す → `res.agent_state.erre.name == CHASHITSU`
- `test_cycle_erre_policy_none_return_noop` — Mock policy が None 返却 →
  `res.agent_state.erre == agent_state.erre` (変化なし)
- `test_cycle_erre_policy_receives_observations` — spy で FSM に渡される
  observation が step の入力と一致
- `test_cycle_erre_policy_emits_shift_event_into_envelopes_or_observations`
  (decisions.md で決定した方法に応じて)

### 回帰

- 既存 `tests/test_cognition/*` 全 PASS (erre_policy default None で既存挙動維持)
- 既存 `tests/test_world/*` 全 PASS (world/tick.py 無変更)
- 既存 `tests/test_bootstrap*` 全 PASS

### 統合

なし (本 task では integration test は追加しない)

## ロールバック計画

- 単一 PR `feature/m5-world-zone-triggers`
- 問題時は `git revert` で CognitionCycle 拡張 + architecture-rules 更新を
  同時に戻す
- `erre_policy=None` default なので attach しない限り挙動 unchanged (bootstrap
  では attach しないため、本 task merge 時点では dead code。安全)

## 設計判断の履歴

- 初回案 (`design-v1.md`) は `world/tick.py` で FSM を呼ぶ方針、再生成案 (v2) は
  `CognitionCycle.step()` に内包する方針
- **採用: v2 (cognition 層内包)**
- 根拠 (`design-comparison.md` 参照):
  1. ERRE mode は認知状態なので cognition 層が自然な owner
  2. `world/tick.py` 完全無変更で regression リスク最小
  3. mode 変更が同 tick 内で有効 (sampling override との整合)
  4. `reflector` 注入パターンとの対称性
  5. `m5-orchestrator-integration` の wiring が単純 (CognitionCycle 引数 1 行追加)
- 細部判断:
  - `ERREModeShiftEvent` は本 task では emit しない (AgentUpdateMsg で
    `agent_state.erre` 変化が伝播する)。memory 学習が必要になれば後続で追加
  - mode 遷移ログは debug level に留める (10 秒毎の info ログを避ける)
  - `erre/ → cognition/` の逆依存は発生しないことを再確認 (erre は schemas のみ)
