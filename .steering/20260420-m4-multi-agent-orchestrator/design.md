# 設計 — m4-multi-agent-orchestrator (v2 再生成案)

> **status**: v2 / 再構築案 (design-v1.md を参照せずに生成)

## 実装アプローチ

M4 #6 の本質は「N agent が **自律的に歩き反省し対話する ensemble** を
composition root で組み立てる」こと。以下 3 本の独立した抽象にまとめる:

1. **BootConfig は `agents` 空の場合、`__post_init__` で default 1-Kant を
   詰める** — bootstrap 本体から分岐を追放し `for spec in cfg.agents:` 1 本道
2. **`InMemoryDialogScheduler` は integration 層に置き、envelope sink を内包**
   — scheduler が自身で envelope を `WorldRuntime` の queue に put するので
   caller は結果処理不要
3. **`WorldRuntime._on_cognition_tick` の末尾で `scheduler.tick(...)` を呼ぶ**
   — proximity gate を scheduler 内部で評価し admit / close を自走させる

この 3 本が揃えば、unit test も live 検証も同じコードパスを通り、
M4 #6 の live 検証を G-GEAR でやる際に追加結線が不要になる。

### 核心アイデア — scheduler 自身が envelope emitter

v1 は `schedule_initiate` が envelope を **返す** 設計で、caller が
どこかで queue に put する責務を持つ。これは 2 つの拡散リスクを生む:

- caller が忘れる (dialog silent drop)
- caller が複数箇所あると **put 重複 / 順序ずれ**

v2: `InMemoryDialogScheduler(envelope_sink: Callable[[ControlEnvelope], None])`
で sink を渡す。scheduler が admit したら **scheduler 自身が sink(envelope)
を呼ぶ**。戻り値は Protocol 準拠のため維持 (`DialogInitiateMsg | None`) するが、
sink 経由で既に流れている envelope を caller が再度 put するのは禁止
(docstring で明示)。

### DialogScheduler の所属層

**`src/erre_sandbox/integration/dialog.py`** に `InMemoryDialogScheduler` を
置く。根拠:

| 層 | 責務 | dialog はそこに属するか |
|---|---|---|
| schemas | 純粋データ型 | No (Protocol だけ) |
| memory | 永続化・検索 | No (dialog は transient) |
| inference | LLM 呼び出し | No (admission だけでは LLM 不要) |
| cognition | 1-agent 1-tick pipeline | No (cross-agent orchestration) |
| world | 物理・位置・tick | Scheduler を参照するが実装主じゃない |
| **integration** | **gateway + composition 結線** | **Yes — multi-agent orchestration の要** |

既に `integration/gateway.py` / `integration/protocol.py` が multi-agent 
routing (M4 #4) を持っているので、dialog scheduler も integration 層の
住人として自然。world は DialogScheduler Protocol に type-hint するのみ。

### Proximity gate = scheduler.tick の責務

`InMemoryDialogScheduler.tick(world_tick: int, agents: Sequence[AgentView])`
を **Protocol 外の拡張 API** として提供。

- `AgentView` = `NamedTuple(agent_id, zone, tick)` (scheduler が必要な値だけ
  抽出した minimum projection。AgentRuntime 全体を渡すと layer 侵入になる)
- tick で以下を順に評価:
  1. open dialog の timeout 判定 → close
  2. 同 zone に 2+ agent + 各 pair に対し cooldown 超過 + まだ open なし
     → `schedule_initiate` を内部で呼び、admit なら sink に流す
  3. turn-taking は本タスクでは実装しない (発火のみ。turn は後続で追加)

auto-fire のレートは `AUTO_FIRE_PROB_PER_TICK = 0.25` 程度の確率閾値で
発火を間引く (deterministic なら RNG を inject)。テストでは RNG を
固定して再現性確保。

### bootstrap の一本道化

```python
@dataclass(frozen=True)
class BootConfig:
    ...
    agents: tuple[AgentSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.agents:
            # frozen dataclass での field 書き換えは object.__setattr__ 経由
            default = (AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),)
            object.__setattr__(self, "agents", default)
```

`bootstrap()` は `cfg.agents` が **必ず非空** であることを前提にでき、
`for spec in cfg.agents:` 1 本道になる。
persona は `_load_persona_yaml(dir, persona_id)` で persona_id ごとに load
(キャッシュは MVP では不要、3 体で 3 回読む)。

### AgentSpec → AgentState 変換

```python
def _build_initial_state(spec: AgentSpec, persona: PersonaSpec) -> AgentState:
    agent_id = f"a_{spec.persona_id}_001"
    return AgentState(
        agent_id=agent_id,
        persona_id=spec.persona_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=spec.initial_zone),
        erre=ERREMode(
            name=_default_erre_for_zone(spec.initial_zone),
            entered_at_tick=0,
        ),
    )
```

`_default_erre_for_zone`: peripatos → PERIPATETIC / chashitsu → CHASHITSU /
それ以外 → DEEP_WORK (persona-erre skill §ERRE mode デフォルト)。

### CLI 拡張

```python
parser.add_argument(
    "--personas",
    help="Comma-separated persona_ids, e.g. 'kant,nietzsche,rikyu'. "
         "Each persona's first preferred_zone is used as initial_zone.",
)
```

`--personas` 指定時:
1. 各 persona を load (バリデーション先行、未存在なら loud fail)
2. `AgentSpec(persona_id=pid, initial_zone=persona.preferred_zones[0])` を生成
3. `BootConfig(..., agents=tuple(specs))`

未指定時は従来通り BootConfig のデフォルト (Kant 1 体) が使われる。

### WorldRuntime 拡張

```python
class WorldRuntime:
    def __init__(
        self,
        *,
        cycle: CognitionCycle,
        dialog_scheduler: DialogScheduler | None = None,
        ...
    ): ...

    async def _on_cognition_tick(self, now: float) -> None:
        # ... 既存: 各 agent の cycle.step ...
        if self._dialog_scheduler is not None:
            views = [
                AgentView(r.agent_id, r.state.position.zone, r.state.tick)
                for r in self._agents.values()
            ]
            self._dialog_scheduler.tick(self._world_tick, views)
            # scheduler が内部で envelope_sink 経由で self._envelopes に put
```

`envelope_sink` は bootstrap 側で `runtime._envelopes.put_nowait` の
thin wrapper を渡す。これで既存 envelope queue に自然統合される。

### 既存パターンとの整合性

- **Contract-First**: DialogScheduler Protocol (#1 foundation) を壊さない
- **Collaborator injection**: `WorldRuntime(dialog_scheduler=...)` は
  既存 `CognitionCycle(reflector=...)` と同パターン
- **envelope queue 単一化**: 既存の `runtime._envelopes: asyncio.Queue` に
  全 envelope を集約する原則 (T14) を継承
- **Pure projection for tests**: `AgentView` NamedTuple は tick.py の
  `_cycle_result_to_envelopes` 等と同じ「必要値だけ抽出」パターン
- **Proximity gate は pure**: RNG を inject することで決定的テスト可能

## 変更対象ファイル

### 新規
- `src/erre_sandbox/integration/dialog.py` — `InMemoryDialogScheduler` +
  `AgentView` + `_OpenDialog` dataclass
- `tests/test_integration/test_dialog.py` — 15+ unit tests
- `tests/test_bootstrap_multi_agent.py` — 3-agent smoke test
  (既存 `tests/test_bootstrap.py` の有無を確認して位置決定)

### 修正
- `src/erre_sandbox/bootstrap.py` — `_load_persona_yaml` / `_build_initial_state` /
  loop register / scheduler 構築
- `src/erre_sandbox/__main__.py` — `--personas` オプション
- `src/erre_sandbox/schemas.py` — `BootConfig`... (待て、BootConfig は
  bootstrap.py に居る、schemas ではない。変更不要)
- `src/erre_sandbox/world/tick.py` — `dialog_scheduler` optional param +
  `_on_cognition_tick` 末尾 hook
- `src/erre_sandbox/world/__init__.py` — 変更なし (scheduler は integration
  からの export)
- `src/erre_sandbox/integration/__init__.py` — scheduler export
- `docs/architecture.md` — §Orchestrator / §Composition Root 追記
- `docs/functional-design.md` — §4 M4 acceptance 追記

### 削除
なし

## 影響範囲

- `BootConfig.__post_init__` の追加: frozen dataclass での初期化が
  object.__setattr__ 経由になる。これは dataclass frozen の慣用句だが
  mypy / ruff が警告する可能性 → 必要なら `# type: ignore` で抑制
- `WorldRuntime.__init__` に kwarg 追加: 既存呼び出し (bootstrap.py のみ)
  は kwarg のみ使用済みで破壊的変更なし
- 既存 `tests/test_world/` 全 PASS 維持 (新 param は optional)
- M2 back-compat: agents が空 → default 1-Kant が詰まるので、
  CLI `--personas` 未指定の既存挙動と等価

## テスト戦略

### `test_dialog.py` unit
- `test_scheduler_admits_first_initiate_and_allocates_id`
- `test_scheduler_rejects_second_initiate_for_same_pair`
- `test_scheduler_rejects_reverse_pair_during_open_dialog` (A→B open なら B→A も拒否)
- `test_scheduler_rejects_during_cooldown`
- `test_scheduler_admits_after_cooldown_elapsed`
- `test_scheduler_records_turn_for_open_dialog`
- `test_scheduler_raises_on_turn_for_unknown_dialog`
- `test_scheduler_close_moves_dialog_out_of_open`
- `test_scheduler_envelope_sink_receives_initiate_and_close`
- `test_scheduler_tick_auto_fires_when_two_agents_same_zone`
- `test_scheduler_tick_skips_when_lone_agent`
- `test_scheduler_tick_closes_on_timeout`
- `test_scheduler_tick_deterministic_with_fixed_rng`
- `test_scheduler_get_dialog_id_roundtrip`
- `test_scheduler_protocol_conformance` (isinstance DialogScheduler Protocol)

### `test_bootstrap_multi_agent.py`
- `test_bootconfig_post_init_fills_default_when_empty`
- `test_bootconfig_preserves_explicit_agents`
- `test_bootstrap_registers_n_agents_with_correct_zones`
  (Ollama health_check skip で mock、cycle 1 回 tick 検証は不要)
- `test_cli_parses_personas_flag`
  (既存 `tests/test_main.py` を拡張)

### 既存テスト影響ゼロ
M2 back-compat は BootConfig のデフォルト経路で保証、
WorldRuntime の新 param は optional。

## ロールバック計画

PR revert で `bootstrap.py` / `__main__.py` / `tick.py` / 新規 2 ファイルが
元に戻る。schema 無変更、DB migration なし。BootConfig の `__post_init__` は
revert で消えるため、空 agents で起動していた path も元通り (既存 Kant 1 体)。

## 受け入れ条件との対応

| 受け入れ条件 | v2 での満たし方 |
|---|---|
| 3 AgentSpec で起動 | `test_bootstrap_registers_n_agents_with_correct_zones` |
| CLI `--personas` expand | `test_cli_parses_personas_flag` |
| schedule_initiate 初回 admit | `test_scheduler_admits_first_initiate_and_allocates_id` |
| 重複ペア reject | `test_scheduler_rejects_second_initiate_for_same_pair` + reverse |
| cooldown respect | `test_scheduler_rejects_during_cooldown` + elapsed |
| record_turn → close → 再 initiate | `test_scheduler_close_moves_dialog_out_of_open` + admit after |
| timeout close | `test_scheduler_tick_closes_on_timeout` |
| 3-agent smoke | bootstrap smoke test |
| 462 PASS 継続 | 既存シグネチャ無破壊、新 param optional |
| ruff クリーン | 開発中に逐次修正 |
| live 検証 handoff | decisions.md + `.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md` |

## live 検証の handoff 方針

live 検証 (G-GEAR 必須) は本 PR では **実施しない**。代わりに:
- `.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md` を残し
  G-GEAR で実行すべきコマンド・期待 evidence (5 項目) を箇条書き化
- `scripts/` は追加しない (bootstrap 既存コマンドだけで完結する設計)
- merge 後、ユーザーが G-GEAR で `uv run erre-sandbox --personas ...` を
  走らせ、evidence ファイルを `.steering/20260420-m4-acceptance-live/` に
  集める (別タスク)

## 設計判断の履歴

- 初回案 (`design-v1.md`: bootstrap 分岐 + `world/dialog.py` 配置 +
  return-based envelope + auto-fire なし) を生成
- `/reimagine` で意図的リセットし、v2 (`__post_init__` 1 本道 +
  `integration/dialog.py` 配置 + sink-based envelope +
  `_on_cognition_tick` auto-fire) を再生成
- `design-comparison.md` で 12 観点比較
- **採用: v2 (ハイブリッド要素なし)**
- 根拠:
  1. live 検証で追加結線が発生しない (merge 直後に G-GEAR 起動で動く)
  2. envelope 経路の単一化 (M4 #4 で確立した原則の継承)
  3. bootstrap の可読性維持 (if/else で汚さない)
  4. AgentView projection は M5/M9 でも再利用可能な先行投資
  5. Contract-First 尊重 (Protocol は無変更、extension メソッドで拡張)
