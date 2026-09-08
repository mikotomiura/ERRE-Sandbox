# Issue 002 (I2): society.py 逐次 sorted scheduler + WorldRuntime record-mode sequential cognition seam + record/replay
verify_level: recheck   # 公開 driver API + 単一 agent 純関数不変 (N=1 canonical equivalent) + 逐次化契約 直結

## Goal
`integration/embodied/society.py`（新規）= N agent を 1 `WorldRuntime` に登録し、**record/construction mode で
due agent を全順序 `(world_tick, order_slot, agent_tick, seq)` に沿って sorted 逐次駆動**する決定的 driver を
実装する。`WorldRuntime` に **record-mode sequential cognition step の public-ish メソッド**を追加し、society は
それを呼ぶ（private 直駆動は暫定 precedent、契約は public seam へ移す）。Plane2 は `RecordReplayChatClient` を
**agent_id keyed** に、`EclDecisionRecord` を per-agent 保持。`run_ecl_loop` **無改変**で N=1 byte 不変。
**construction であって measurement でない**。

## Background
FROZEN ADR §M3（Placement-1 society.py）/§M4.1（record-mode 逐次 sorted scheduler、asyncio.gather を record
mode で捨てる）/§M6（two-plane N体拡張、per-agent full LLMPlan replay）/ DA-M2IMPL-1/3 / Codex MEDIUM-6
（private method 直駆動 brittle → public seam）。§M2 実コード確証: `run_ecl_loop` は単一 agent で phase-wheel を
バイパスし `world._step_one(rt)`/`world._consume_result`（loop.py L624-625）を直駆動、`order_slot =
sorted([agent_id]).index(agent_id)`=0（L557）。EclTraceRow（L333-337）+ EclDecisionRecord（L288）+
RecordReplayChatClient（L156）+ ecl_trace_checksum（L369）は N体前方互換 slot 完備。設計 FROZEN。

## Scope
### In
- `world/tick.py`: `WorldRuntime` に **`step_cognition_once(agent_id)`**（例、`_on_cognition_tick` の phase-wheel を
  経ずに 1 agent を決定的に step する public-ish seam、`_step_one`/`_consume_result` を内部で呼ぶ）を追加。
  live 挙動不変（既存 phase-wheel/gather は無改変）、N=1 byte 不変。
- 新規 `integration/embodied/society.py`:
  - `run_society_loop(*, agents, world, seed, record/replay, ...)` — N agent を register、physics tick を進め、
    cognition window で due agent を **`sorted(order_slot)` 順に 1 体ずつ** `step_cognition_once` 逐次駆動
    （record mode で asyncio.gather を使わない）。`order_slot = sorted(agent_id).index()`。
  - Plane2: `RecordReplayChatClient` を **agent_id keyed** wrapper 拡張（per-agent record/replay、
    `EclDecisionRecord` per-agent 保持）。record→replay で `inner_invocations==0` + per-agent byte 一致。
  - 全順序 tie-break `(world_tick, order_slot, agent_tick, seq)`。no wall-clock（ManualClock/tick 由来）、
    deterministic ids（`f"...-{agent_id}-{agent_tick:04d}"` 型）。
  - `run_ecl_loop` は **再利用せず無改変**（society は別 driver）。loop.py の Plane2/checksum primitive を import 再利用。
- 新規 `tests/test_integration/test_m2_society.py`（本 issue 分）。
### Out
- versioned event/decision log 全体 checksum + self_other slot（I3）。per-pair named RNG substream + discovery
  guard permutation/checklist（I4）。handoff N体 schema（I5）。spend ast-guard（I6）。tick §B4 sorted 化（I1、済）。
- Layer2 内部 HOW。live wall-clock loop（byte 不変性を課さない）。**measurement 一切**。

## Allowed Files
- `src/erre_sandbox/integration/embodied/society.py`（新規）
- `src/erre_sandbox/world/tick.py`（`step_cognition_once` public seam 追加のみ、既存 phase-wheel 無改変）
- `tests/test_integration/test_m2_society.py`（新規、本 issue 分）
- **無改変厳守**: `loop.py`（run_ecl_loop）/ `handoff.py` / committed golden / `evidence/**` / `bank*.py`

## Acceptance Criteria（AC↔test）
- I2-G1: `test_m2_society_n1_canonical_equivalent` — society driver を **N=1** で回した出力が canonical
  projection/adapter 経由で `run_ecl_loop` と **意味等価**（schema version 違いの raw byte 一致は要求しない、
  §M7 M2 path、Codex HIGH-2）。単一 agent 埋込 per-agent 純関数不変を担保。
- I2-G2: `test_m2_society_sequential_scheduler_order` — N=3 で due agent が `sorted(order_slot)` 順に逐次 step
  され、record mode で asyncio.gather を経由しない（trace の order_slot 昇順、gather 非使用を assert）。
- I2-G3: `test_m2_society_plane2_per_agent_replay` — per-agent `RecordReplayChatClient` の record→replay で
  `inner_invocations==0` + per-agent LLMPlan byte 一致（N=3）。
- I2-G4: `test_m2_step_cognition_once_seam` — `WorldRuntime.step_cognition_once(agent_id)` が phase-wheel を
  経ず 1 agent を決定的 step（public seam、private 直駆動と等価挙動）。
- I2-G5: 既存 ECL v0/v1 legacy byte 不変回帰（`test_ecl_flag_off_byte_invariant` 等）+ I1 の tick test 群 緑維持
  （run_ecl_loop 無改変、N=1 legacy byte 不変）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m2_society.py` + 既存 ECL/flag-off 回帰 + pre-push 4 段。N=1 canonical
equivalence は mock chat client（決定的 raw response）で run_ecl_loop と society N=1 の canonical projection を
比較。N=3 scheduler/replay も mock LLM。**gating は replay/mock only、live 非依存**（§M8 LOW-9）。

## Stop Conditions
- 全 AC 緑（Done）。
- society N=1 が run_ecl_loop と canonical-equivalent にならない → Stop（単一 agent 純関数不変 / §M7 M2 path 逸脱）。
- record mode で asyncio.gather を使わないと逐次化できない設計になった → Stop（§M4.1 逸脱）。
- `run_ecl_loop` / loop.py core / 凍結 apparatus の改変を要する → Stop（binding 逸脱→superseding ADR）。
- budget 到達 → Stop。

## Dependencies
- I1（tick.py §B4 sorted 化 land 後。deterministic tick が driver checksum の前件）。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit 4ed8b26）

## Execution Result
subagent（Sonnet）実装 → test-runner(Haiku) 独立再検証（recheck、6/6 exit 0）→ loop-watchdog verdict=DONE。
- 新規 `society.py`: `run_society_loop`（逐次 sorted scheduler、record mode で gather 非使用）/
  `_AgentKeyedChatClient`（per-agent RecordReplayChatClient ルーター、shared CognitionCycle を "activate
  before step" で keyed 化、sequential ゆえ active agent 一意）/ per-agent `EclDecisionRecord` / 全順序
  `(world_tick, order_slot, agent_tick, seq)`。run_ecl_loop 無改変・未 import、primitive のみ再利用。
- `tick.py`: `WorldRuntime.step_cognition_once(agent_id)` public seam（既存 phase-wheel/gather 無改変）。
- 新規 `tests/test_integration/test_m2_society.py`（5 AC test）。
- **独立検証**: pytest（新規 5 / integration ECL 回帰 181 / test_world 158 passed）+ mypy(239 clean) +
  ruff check + format、**6/6 exit 0**。
- **強 witness**: N=1 canonical-equivalent は run_ecl_loop と **byte-identical**（I2 は新 schema 未導入ゆえ
  ADR の「canonical projection 等価」より強い。schema 割れは I3/I5 以降、2 経路二分は I5 で発生）。
- **設計判断（cross-review 付託候補）**: WorldRuntime は 1 CognitionCycle を全 agent 共有する既存設計ゆえ、
  per-agent Plane2 keyed 化を society 側の router で実現（CognitionCycle 無改変）。bias_sink も active_agent_id
  読取りクロージャで per-agent fan-out。RNG substream 分離は I4 scope で未実装（単一 Random 共有＝run_ecl_loop
  precedent の N 体拡張のみ）。
