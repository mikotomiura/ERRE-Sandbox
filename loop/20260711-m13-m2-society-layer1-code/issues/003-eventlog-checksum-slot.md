# Issue 003 (I3): versioned event/decision log 全体 checksum（geometry はその一部）+ self_other slot 予約
verify_level: recheck   # Codex HIGH-2 (event-log 全体 checksum) + MEDIUM-5 (self_other 最小 wire envelope) 直結

## Goal
society driver の acceptance checksum を **versioned event/decision log 全体**へ拡張する:
`{geometry rows（EclTraceRow）+ dialog events + affinity deltas + memory mutations + pair events
（proximity/separation）+ self_other_observation_input slot（Layer1 では null）+ per-agent LLMPlan replay
（EclDecisionRecord）}`。**geometry plane checksum はその一部**。`self_other_observation_input` slot を
**versioned additive・最小 wire envelope `null | {schema_version, payload}`** で予約（Layer1 は常に null）。
**checksum は再現性という construction 品質であって structural floor でない**（metric/verdict 非計算）。

## Background
FROZEN ADR §M4.4（versioned event/decision log 全体 checksum）/§M5.1（self_other slot 最小 wire envelope 予約、
Layer1 null）/ DA-M2IMPL-5/6 / Codex HIGH-2（geometry 偏重で social/cognitive 非決定を見逃す）/ MEDIUM-5
（self_other wire 契約 = `null | {"schema_version": str, "payload": object}` 凍結、payload 具体 field は defer=
引っ張り禁止）。checksum canonical 規律 = `ecl_trace_checksum`（loop.py L369、6 桁量子化 canonical JSON /
sort_keys / compact separators / allow_nan=False）踏襲（cross-platform byte 一致）。設計 FROZEN。

## Scope
### In
- `integration/embodied/society.py`:
  - **versioned event-log record 集合**: 各 event 種別（geometry/dialog/affinity/memory mutation/pair event/
    self_other slot/per-agent LLMPlan replay）を canonical JSON へ **6 桁量子化 projection**、全順序 key で sort 後
    SHA-256。`ecl_trace_checksum` の canonical 規律踏襲。geometry checksum はその一部として合成。
  - `self_other_observation_input: None | {"schema_version": str, "payload": object}` slot を event/decision log に
    **versioned additive** で予約。**Layer1 は常に None**。checksum 対象に含む（None ゆえ Layer1 checksum 不変）。
    payload 具体 field は **書かない**（Layer2 ADR、引っ張り禁止）。
  - event-log の schema version 定数（例 `M2_EVENTLOG_SCHEMA_VERSION`）を additive に定義。
- `tests/test_integration/test_m2_society.py`（本 issue 分を追記）。
### Out
- per-pair named RNG substream + permutation/checklist discovery guard（I4）。handoff manifest（I5）。
- spend ast-guard（I6）。Layer2 continuity gate 実装（別 mirror-sim ADR）。self_other payload 具体 schema。
- **measurement 一切**（checksum は floor でない、H/divergence/verdict 非計算）。

## Allowed Files
- `src/erre_sandbox/integration/embodied/society.py`（event-log 集合 + checksum + slot 予約）
- `tests/test_integration/test_m2_society.py`（本 issue 分）
- **無改変厳守**: `loop.py`（ecl_trace_checksum は import 再利用のみ）/ `handoff.py` / committed golden /
  `evidence/**` / `bank*.py`

## Acceptance Criteria（AC↔test）
- I3-G1: `test_m2_society_event_log_checksum_stable` — N=3 で同一 (seed, 記録済 Plane2) → **versioned
  event/decision log 全体**（幾何+dialog+affinity+memory mutation+pair event+self_other[None]+per-agent LLMPlan
  replay）の checksum byte 一致。geometry checksum はその一部。**再現性であって structural floor でない**。
- I3-G2: `test_m2_log_carries_self_other_slot_forward_compat` — event/decision log が
  `self_other_observation_input` slot（`None | {schema_version, payload}`）を versioned additive に持ち、
  Layer1 checksum が None slot で byte 不変（forward-compat = payload 追加時 schema break しない wire 形）。
- I3-G3: `test_m2_eventlog_covers_social_cognitive` — checksum 入力が geometry のみでなく dialog/affinity/memory
  mutation/pair event/per-agent LLMPlan を含む（social/cognitive event の非決定を検出可能なことを、意図的に
  1 event 種を non-canonical にすると checksum が変わることで示す）。
- I3-G4: `test_m2_eventlog_6digit_quantized` — emitted float が 6 桁量子化されてから hash/serialize
  （cross-platform byte 一致の前件、`feedback_golden_crossplatform_float_drift`）。
- I3-G5: I1/I2 の test 群 + 既存 legacy byte 不変回帰 緑維持。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m2_society.py` + 回帰 + pre-push 4 段。全て mock LLM（決定的 raw
response）。checksum stability は同一 seed 2 回 run で byte 一致。social/cognitive coverage は event 種別ごとに
mutation 注入して checksum 感応を確認。

## Stop Conditions
- 全 AC 緑（Done）。
- checksum に self_other slot を含めると Layer1（None）で byte が動く → Stop（None slot 不変性 違反）。
- self_other payload の具体 field を書かないと checksum が組めない → Stop（引っ張り禁止 抵触→Layer2 ADR 案件）。
- checksum が floor/verdict/metric として解釈される計算に化けた → Stop（construction≠measurement 逸脱）。
- 凍結 apparatus 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- I2（society driver が event-log を生成する。checksum は driver 出力に対して定義される）。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit d148ad6）

## Execution Result
subagent（Sonnet）実装 → test-runner(Haiku) 独立再検証（recheck、6/6 exit 0）→ verdict=DONE。
- `society.py`: `event_log_checksum()` 純関数（`M2_EVENTLOG_SCHEMA_VERSION="m2-eventlog-1"`、
  `geometry_checksum=ecl_trace_checksum(rows)` 埋込）+ `PairEventRecord`/`DialogEventRecord`/
  `AffinityDeltaRecord`/`MemoryMutationRecord`（versioned additive、全順序 sort → 6 桁量子化 canonical
  JSON → SHA-256）。pair events = `rt.pending` の ProximityEvent を sorted_pair 側のみ harvest、memory
  mutations = ORDER BY id ASC。self_other slot = `dict|None` + `_validate_self_other_slot()`。
- **独立検証**: pytest（test_m2_society 9 / integration ECL 回帰 181 / test_world 158 passed）+ mypy/ruff/
  format、6/6 exit 0。
- **既知の gap（cross-review 付託 / I4 で対処、DG-6）**: record-mode driver は dialog/affinity を発火しない
  （live phase-wheel `_on_cognition_tick` 経由のみ、record-mode は bypass）。schema は present だが
  `test_m2_society_event_log_checksum_stable` の実データは geometry+pair+memory_mutation+LLMPlan のみ。
  dialog/affinity は Layer1 社会動態であって Layer2 mirror-sim でない → society.py コメントの "Layer2 scope"
  は誤ラベル、I4 で record-mode driver へ dialog 逐次配線 + コメント訂正。ADR §M4.3 item5 は dialog 発火前提。
