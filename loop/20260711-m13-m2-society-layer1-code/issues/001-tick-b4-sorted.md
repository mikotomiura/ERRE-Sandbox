# Issue 001 (I1): tick.py §B4 侵入経路 sorted 化（separation/proximity/values() + pair canonical）+ N=1 byte 不変
verify_level: recheck   # live hot path (tick.py) 改変 + Codex HIGH-3 (N=1 byte 不変 / sorted pair canonical) 直結

## Goal
`world/tick.py`（`WorldRuntime`）の §B4 Plane1 侵入経路を **漏れなく sorted 化**し、pair event を
`sorted_pair=(min_id,max_id)` canonical に固定する。**determinism 硬化であって live 挙動変更でない**。
**N=1 で byte 不変**（combinations 空・単一 agent 純関数不変）を acceptance で担保する。**construction であって
measurement でない**（checksum/floor/verdict 非計算、本 issue は tick 側の canonical 化のみ）。

## Background
FROZEN ADR §M4.3 / §M2（実コード確証）/ DA-M2IMPL-4 / Codex HIGH-3。§B4 が flag した経路（実読で確証）:
- `_apply_separation_force`（L1229）が `combinations(self._agents.values(), 2)`（**L1249、非 sorted**）→
  3+ agent の chain-push が登録順依存 = checksum に load-bearing。
- `_fire_proximity_events`（L1275）も `combinations(self._agents.values(), 2)`（**L1294、非 sorted**）。
- `_on_physics_tick`（L1151）の `for rt in self._agents.values():`（**L1153、非 sorted**）mutation loop
  （per-agent 独立で順序不感だが discovery guard として一様 sorted 化）。`_fire_temporal_events`（L1401 相当）/
  affordance の非 sorted values() も同様。
- `_emit_ecl_trace`（L1208）は **既に `sorted(self._agents)`**（L1225）= 変更不要（回帰で緑維持）。
**byte 不変 claim は N=1 限定**（Codex HIGH-3）: N≥2 は「sorted pair を新 canonical とする」（N=2 でも pair
orientation が event log/pair key/proximity 順序に出るため「N≤2 byte 不変」は過剰主張、撤回）。設計 FROZEN。

## Scope
### In
- `world/tick.py`:
  - separation（L1249）/ proximity（L1294）の `combinations(self._agents.values(), 2)` を
    `combinations([self._agents[a] for a in sorted(self._agents)], 2)`（sorted-pair 順）へ。
  - pair event（proximity/separation）の serialize を **常に `sorted_pair=(min_id, max_id)`**
    （agent_a/agent_b・pair key・event 順序に pair orientation を漏らさない）。
  - 非 sorted `values()` 反復（L1153 mutation loop / temporal / affordance）を **一様 sorted 化**
    （discovery guard として「checksum 経路に裸の非 sorted values() が無い」を機械保証可能に）。
- 新規 `tests/test_world/test_tick_b4_determinism.py`。
### Out
- society.py 逐次 scheduler（I2）。event/decision log 全体 checksum（I3）。per-pair named RNG substream（I4、
  本 issue は反復順序の canonical 化まで、RNG substream 命名は I4）。handoff schema（I5）。spend guard（I6）。
- live wall-clock `_on_cognition_tick` の async gather（L1432、tick.py では**無改変**、record mode 逐次化は I2）。
- **measurement 一切**（H/count/divergence/floor/verdict、Counter/set-over-zones/numpy）。

## Allowed Files
- `src/erre_sandbox/world/tick.py`（§B4 経路の sorted 化 + pair canonical のみ、live 挙動不変）
- `tests/test_world/test_tick_b4_determinism.py`（新規）
- **無改変厳守**: `integration/embodied/loop.py`（run_ecl_loop）/ `handoff.py` / committed golden / `evidence/**` /
  `bank*.py` / organ committed artifact

## Acceptance Criteria（AC↔test）
- I1-G1: `test_tick_n1_byte_invariant` — N=1 で本変更前後の ecl_trace_checksum（既存 `ecl_trace_checksum`）が
  完全一致（combinations 空・単一 agent 純関数不変、Codex HIGH-3 の N=1 限定 byte 不変）。
- I1-G2: `test_tick_separation_registration_order_invariant` — N=3 で agent 登録順を permutation しても
  separation 適用後の全 position が同一（sorted-pair 順で chain-push が登録順非依存）。
- I1-G3: `test_tick_proximity_pair_canonical` — proximity/separation event が `sorted_pair=(min_id,max_id)` で
  serialize（pair orientation 非漏洩、a<b 固定）。
- I1-G4: `test_tick_no_bare_values_iteration_on_checksum_path` — tick.py の checksum 影響経路に裸の非 sorted
  `values()` iteration が無い（AST/grep、canonicalization 用 `sorted(...)` は allow）。
- I1-G5: 既存 ECL v0/v1 flag-off byte 不変回帰（`test_ecl_flag_off_byte_invariant` 等）+ 既存 tick test 群 緑維持。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_world/test_tick_b4_determinism.py` + 既存 ECL/flag-off/tick 回帰 + pre-push 4 段。
N=1 byte 不変は変更前 checksum を fixture で pin（または変更前後を同一 seed で比較）。N=3 permutation は
mock agent 集合（LLM 非依存、幾何/物理のみ）。live LLM 不要。

## Stop Conditions
- 全 AC 緑（Done）。
- sorted 化が既存 N=1 golden の byte を変える → Stop（Codex HIGH-3「N=1 byte 不変」逸脱、実装ミス）。
- live 挙動（物理定数・force 計算式）を変える必要が出た → Stop（determinism 硬化の範囲逸脱、behavior-preserving 違反）。
- loop.py / handoff.py / 凍結 apparatus の改変を要する → Stop（binding 逸脱→superseding ADR）。
- budget 到達 → Stop。

## Dependencies
- なし（foundation）。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit 212c7da）

## Execution Result
subagent（Sonnet、fresh context）実装 → test-runner(Haiku) で独立再検証（verify_level=recheck、
exit code 基準で self-申告打ち消し）→ loop-watchdog verdict=DONE。
- `world/tick.py`: 新規 private helper `_sorted_runtimes()` を追加、`_on_physics_tick` /
  `_apply_separation_force`（combinations）/ `_fire_proximity_events`（combinations）/
  `_fire_affordance_events` / `_fire_temporal_events` の 5 箇所の `self._agents.values()` を置換。
  `_emit_ecl_trace`（既に `sorted(self._agents)`）は無改変。物理定数・force 式 一切不変。
- 新規 `tests/test_world/test_tick_b4_determinism.py`（I1-G1..G4、4 test）。
- **独立検証**: pytest（新規 4 passed / tests/test_world 158 passed / integration byte 不変 10 passed）+
  mypy（238 files clean）+ ruff check + ruff format --check、**6/6 exit 0 全緑**。
- Allowed Files（tick.py / test）以外無改変（run_ecl_loop/handoff/golden/evidence/bank 無改変を diff 確認）。
- **解釈判断（binding 逸脱でない）**: `ProximityEvent` は perspective-per-agent（agent_id/other_agent_id）で
  単一 sorted_pair フィールドが schemas に無いため、pair canonical を `combinations(_sorted_runtimes(),2)` の
  反復順序（rt_a<rt_b）で実装。event-log の pair serialize は I3 の全体 checksum で完遂（scope 境界）。
- ADR の line 番号は現行 tick.py で移動していたため grep で実在箇所を再特定（内容は ADR 記述と一致）。
