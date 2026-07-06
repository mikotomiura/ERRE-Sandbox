# Issue 001 (I1): live-capture apparatus — ThinkOffChatClient + harness + protocol/env pin
verify_level: recheck   # 公開 API (ThinkOffChatClient) + AC 直結 (think=False 注入) + pre-registration

## Goal
ECL v0 organ を real qwen3:8b で record-mode 封印実走するための **apparatus を live 非依存に構築**する
(実走は Issue 003)。核 = `ThinkOffChatClient` (driver-local wrapper、`inner.chat(...,think=False)` 強制、
cycle 無改変 = Codex HIGH-1) + `run_live_capture` (record mode で `RecordReplayChatClient(inner=ThinkOffChatClient
(inner_chat))` を `run_ecl_loop` に注入、mock inner で test 可) + 事前登録 protocol 定数 (N=32/persona=kant/
embedding=mock/O5 閾値、D-1..5) + manifest env-pin fields (D-3) + measurement 非再入 guard。

## Background
FROZEN ADR (`.steering/20260706-m13-forward-primary/design-final.md`) binding a-e、Codex HIGH-1
(think=False 経路が cycle 無 pass ゆえ閉じない → wrapper 必須)。grill-goals.md I1/I2 + D-1..5/D-7。
**設計 FROZEN、再オープンしない** (fork なら Stop→superseding ADR)。

## Scope
### In
- 新規 `src/erre_sandbox/integration/embodied/live.py`:
  - `ThinkOffChatClient` — inner chat client を包み `chat(..., think=False)` を強制転送 (他引数 messages/
    sampling/model/options は無改変)。
  - `run_live_capture(*, inner_chat, store, embedding, ...)` — inner を DI (mock 可)、ThinkOffChatClient +
    `RecordReplayChatClient(inner=...)` record mode + `run_ecl_loop` を駆動し `EclRunResult` 返却。
  - protocol 定数: `LIVE_N_COGNITION_TICKS=32` / `LIVE_PERSONA_ID="kant"` / embedding=mock / `LIVE_O5_MIN_TICKS=1`。
  - live manifest env-pin helper (qwen3 digest / Ollama version / VRAM / uv.lock hash / `think:false` /
    resolved sampling を run_config へ、`handoff.build_manifest` 無改変呼出)。
- 新規 `scripts/ecl_v0_live_capture.py` — thin CLI (`--capture`) が real `OllamaChatClient` を構築し
  `run_live_capture` 呼出 + `handoff.write_golden` 相当で artifact 書出 (実走は Issue 003 で使用)。
- 新規 `tests/test_integration/test_ecl_live_capture.py`。
### Out
- live Ollama 実走・committed artifact (Issue 003)。replay-verify test 本体 (Issue 002)。measurement 再入。

## Allowed Files
- `src/erre_sandbox/integration/embodied/live.py` (新規)
- `scripts/ecl_v0_live_capture.py` (新規)
- `tests/test_integration/test_ecl_live_capture.py` (新規)
- **無改変厳守**: `loop.py`/`cycle.py`/`world/tick.py`/`handoff.py`/`ecl_v0_golden.py`

## Acceptance Criteria (AC↔test)
- I1-G1: `test_think_off_chat_client_forces_think_false` — mock inner に think=False が渡る (request-capture)
- I1-G2: `test_think_off_chat_client_passthrough` — messages/sampling/model/options 無改変転送
- I1-G3: `test_live_capture_harness_records_with_mock_inner` — mock inner で record → captured decisions 完全+
  trace+checksum 生成 (live 非依存)
- I1-G4: `test_live_capture_replay_roundtrip_mock` — captured decisions のみ replay → checksum byte 一致+
  inner_invocations==0
- I2-G1: `test_live_capture_protocol_constants` — N==32/persona=="kant"/embedding=mock/O5_min==1 固定
- I2-G2: `test_live_manifest_pins_env` — manifest に qwen3 digest/Ollama version/VRAM/uv.lock/think:false/
  resolved sampling
- I2-G4: `test_live_capture_measurement_guard` — evidence/spdm/runningness 非 import + floor/landscape/verdict
  非出力
- I1-G5: 既存 `test_ecl_flag_off_byte_invariant` + ECL test 群 緑維持
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_live_capture.py` + 既存 ECL/flag-off 回帰 + pre-push 4 段。
ThinkOffChatClient は mock inner (request 記録) で think=False を pin、harness は mock で record/replay 完結。

## Stop Conditions
- 全 AC 緑 (Done)。
- apparatus が loop.py/cycle.py/world/handoff の改変を要する → Stop (binding「既存 seam 無改変」逸脱→superseding ADR)。
- budget 到達 (Stop)。

## Dependencies
- なし (autonomous /loop-issue の起点)。Issue 002/003 の前提。

## Status
QUEUED

## Execution Result
(完了時に記入)
