# Issue 001 (α): record-mode Plane2/clock hardening — P2(B-2) + W(B-5)
verify_level: parse   # mock 注入で完結 (ADR §5 = 通常)。ただし flag-off byte-invariance を hard AC 化

## Goal
ECL record mode の Plane2 を tick-indexed + `outcome ∈ {ok, unparseable, raised}` union 化し、
LLM 失敗 (`OllamaUnavailableError` raise / unparseable) を crash させず replay 再現可能にする。
併せて record mode の cycle `_fallback` を `_pin_envelope_clock` 経由にし、`AgentUpdateMsg.agent_state.wall_clock`
と `ReasoningTrace.created_at` を `retrieval_now` に pin する (W = 全 artifact SHA を bake 間で決定化)。
flag-off (`ecl_mode is None`) 経路は完全 byte 不変。committed golden は **再生成しない** (γ が単一 re-bake)。

## Background
FROZEN ADR §3.2 (P2) + §3.3 (W)、Codex HIGH-1 (wall-clock 混入) + HIGH-2 (outcome union) + LOW/H-13
(success→raised→replay 回帰)。決定的 sequencing = 既存 AC2 `test_ecl_handoff.py:174-186` は decisions.jsonl の
byte 安定を意図的に非 assert (wall_clock/created_at 未 pin を既知文書化) ゆえ、**W fix は既存 test を壊さず
main merge 可**。grill-goals.md D-α1..D-α3 参照。**設計 FROZEN、再オープンしない。**

## Scope
### In
- `loop.py` `RecordedLlmCall`: `outcome: Literal["ok","unparseable","raised"]="ok"` 追加 + `response` を
  optional 化 (raised は response-less)。`raw_response` を None 安全化。
- `loop.py` `RecordReplayChatClient.chat`: record 側で `OllamaUnavailableError` を捕捉し raised record を
  `_used` に append してから **再送** (cognition fallback 発火)、成功は `outcome="ok"`。replay 側は
  `outcome=="raised"` で同例外再送・それ以外は recorded content 返却。`_used` を tick 整合に保つ。
- `loop.py` driver `run_ecl_loop`: `llm.used[agent_tick]` 位置参照廃止 (tick 軸で record 対応付け)。
- `loop.py` `_build_decision`: `raised` を parse 前に処理 (`plan=None` / `llm_status="raised"`)、
  unparseable は現行 `parse_llm_plan()==None` 踏襲。
- `cycle.py` `_fallback`: record mode 時 `envelopes = self._pin_envelope_clock(envelopes)` 経由 (flag-off 不変)。
- `cycle.py` `_pin_envelope_clock`: record mode で nested `AgentUpdateMsg.agent_state.wall_clock` と
  `ReasoningTraceMsg.trace.created_at` も `retrieval_now` に pin (sent_at pin と同 clock、D-α2)。flag-off 不変。
- `handoff.py` `_recorded_call_to_dict`/`_recorded_call_from_dict`: `outcome` の JSONL roundtrip +
  response=None (raised) の null 安全化。既存 golden (outcome 欠) は `data.get("outcome","ok")` で後方互換。
### Out
- `ecl_trace_checksum` の canonical 化 (γ)。
- committed golden の再生成 (γ が単一 re-bake、α は decisions.jsonl 波及を残置)。
- measurement 再入 (holding 不可侵)。
- `MANIFEST_SCHEMA_VERSION` bump / manifest checksum-rule fields (γ)。

## Allowed Files
- `src/erre_sandbox/integration/embodied/loop.py`
- `src/erre_sandbox/cognition/cycle.py` (`_fallback` / `_pin_envelope_clock` のみ)
- `src/erre_sandbox/integration/embodied/handoff.py` (`_recorded_call_to_dict`/`_from_dict` のみ)
- `tests/test_integration/test_ecl_loop.py`
- `tests/test_integration/test_ecl_handoff.py` (α-G6 2x-bake determinism)
- `tests/test_cognition/test_ecl_cycle.py` (α-G4 fallback clock pin が cycle-level の場合)

## Acceptance Criteria (AC↔test マッピング)
- α-G1: `test_ecl_loop_raised_call_does_not_crash` 緑 — tick k で `OllamaUnavailableError` 注入 → run 完走
  (IndexError なし) + `used` tick 整合 (len==n_ticks) + 当該 decision `llm_status=="raised"`/`plan is None`
- α-G2: `test_ecl_loop_raised_replay_checksum_matches` 緑 — raised tick 含む record → decisions のみで replay →
  `inner_invocations==0` + 同例外再送 + fallback 再現 + `checksum` byte 一致
- α-G3: `test_ecl_loop_unparseable_replay_checksum_matches` 緑 — unparseable content → fallback → replay で
  content 返却→同 fallback → checksum 一致
- α-G4: `test_ecl_loop_fallback_envelope_clock_pinned` 緑 — record mode fallback tick の AgentUpdateMsg
  `sent_at == retrieval_now`、flag-off は default factory (未 pin) 不変
- α-G5: `test_ecl_loop_success_then_raised_replay_matches` 緑 — ok→raised→ok 列 → replay checksum 一致
  (直前 Kinematics.destination 依存の位置前進が決定的、Codex LOW/H-13)
- α-G6 (W): `test_ecl_v0_golden_rebake_is_deterministic` 緑 — `run_golden`→`render_golden` 2 回で全 4 artifact
  文字列 byte 一致 (wall_clock/created_at pin の letter、in-memory、D-α3)
- α-G7: `test_ecl_flag_off_byte_invariant` (既存) 緑維持 — flag-off 経路完全不変
- α-G8 CI parity: `bash scripts/dev/pre-push-check.sh` 4 段全 pass (`ALL CHECKS PASSED`)

## Test Plan
`pytest -q tests/test_integration/test_ecl_loop.py tests/test_integration/test_ecl_handoff.py tests/test_cognition/`
+ 既存全 test 回帰 (flag-off byte 不変 = live cognition 経路無改変) + pre-push CI parity 4 段。

## Stop Conditions
- 全 AC 緑 (Done)
- raised 処理が sanctioned 範囲 (`_fallback` pin / record-mode clock pin / `RecordReplayChatClient` /
  `_build_decision` / driver 位置参照廃止 / handoff roundtrip) を超えて frozen cycle.py 他所改変を要する → Stop
- 2x-bake が W fix 後も非決定 → Stop (未 pin source 特定)
- budget 到達 (Stop)

## Dependencies
- なし (β と並行開発可)。**γ の前提** (γ は α・β merge 後)。

## Status
QUEUED

## Execution Result
(完了時に記入)
