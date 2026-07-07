# Issue 005 (I5): annotation side-file（opaque）+ construction 検証 run（mock）+ bank golden replay + cross-platform
verify_level: recheck   # committed golden + reproduction 契約 + cross-platform byte 一致 直結

## Goal
bank の **raw-row annotation side-file**（opaque）を serialize し、**mock construction 検証 run**（Ollama 非依存、
D-10 mock-only 裁定）で K×M×2 の bank を回して **committed golden** を焼き、replay で byte 一致を検証する。
zone-pick は categorical（Zone enum）ゆえ float 非感応で byte 一致自明、provenance pass の幾何 float のみ
6 桁量子化継承。**stats 非計算・verdict なし・raw row のみ**。

## Background
FROZEN ADR §I4（raw row のみ・annotation opaque）/§I5（bank golden = 小規模 committed replay fixture、
cross-platform）。grill-goals.md D-8/D-10（mock-only）。committed golden の float drift 対策は
`feedback_golden_crossplatform_float_drift`（6 桁量子化 + WSL byte 実測）。**live shakedown は OUT**（D-10）。
**設計 FROZEN**。

## Scope
### In
- 新規 `scripts/ecl_bank_capture.py`（thin CLI）:
  - mock inner chat（決定的 raw response、Ollama 非依存）で I1 provenance pass → K 個の凍結 context → I2
    `run_bank_mloop`（M draw × 2 condition）→ `BankLlmCallRecord` bank。
  - annotation side-file writer: JSONL raw row `{frozen_ctx_id, condition, mc_index, pre_bias_destination_zone,
    resolved_from}`（checksum 外、opaque、`BANK_ANNOTATION_SCHEMA_VERSION`）。**H/count/diversity を計算しない**。
  - bank golden bake: `handoff.canonical_dumps` 相当（6 桁量子化）で committed artifact 書出 + bank manifest
    overlay（`BANK_SCHEMA_VERSION`）+ env pins。
  - call cap（I3 の `2·M·K` ceiling）を尊重、fail-fast。
- 新規 `experiments/20260708-m13-b-bank/artifacts/`（committed mock golden: bank records + annotation side-file +
  manifest）+ `run.sh`/`repro.sh`/`env.md`。
- 新規 `tests/test_integration/test_ecl_bank_golden.py`（Ollama-free replay-verify、CI）。
### Out
- competing cue fixture / provenance pass 本体（I1）。bank driver 本体（I2）。spend guard helper（I3、call cap は
  再利用）。continuity/T3 test（I6）。live Ollama（D-10）。measurement 再入。

## Allowed Files
- `scripts/ecl_bank_capture.py`（新規）
- `experiments/20260708-m13-b-bank/artifacts/**`（新規 committed golden）+ `run.sh`/`repro.sh`/`env.md`（新規）
- `tests/test_integration/test_ecl_bank_golden.py`（新規）
- **無改変厳守**: `handoff.py`（`canonical_dumps`/`capture_env_pins` 再利用のみ）/ organ / bank.py / bank_fixtures.py

## Acceptance Criteria（AC↔test）
- I5-G1: `test_bank_annotation_side_file_schema` — annotation JSONL row が `{frozen_ctx_id, condition, mc_index,
  pre_bias_destination_zone, resolved_from}` 閉集合ちょうど + `BANK_ANNOTATION_SCHEMA_VERSION`（余計 field 非在）
- I5-G2: `test_bank_golden_replay_checksum` — committed bank records のみ replay → bank byte 一致 +
  `inner_invocations==0`（Ollama-free、reproduction 契約）
- I5-G3: `test_bank_golden_categorical_byte_stable` — zone-pick categorical（Zone enum）ゆえ byte 一致自明を
  assert、provenance pass の幾何 float は 6 桁量子化（`_q`/round(x,6)）で cross-platform 吸収
- I5-G4: `test_bank_construction_run_mock` — mock construction 検証 run が K×M×2 を例外なく完走（schema-test、
  Ollama 非依存）+ call cap 尊重
- I5-G5: `bash experiments/20260708-m13-b-bank/repro.sh` exit 0（1 コマンド Ollama-free 再現）
- I5-G6: **WSL Linux (glibc) で committed golden が Windows (UCRT) と byte 一致**（cross-platform 手動実測、
  `env.md` 記録、`feedback_golden_crossplatform_float_drift` 同手順）
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_golden.py` + pre-push 4 段 + WSL byte 一致手動実測。mock inner で
record→golden→replay を完結。annotation opaque は I3 guard + 本 test の「count/diversity を assert しない」で二重
保証。

## Stop Conditions
- 全 AC 緑（Done）+ WSL byte 一致実測。
- golden が float drift で cross-platform byte 不一致 → Stop（量子化漏れ特定、6 桁量子化 or categorical 化）。
- annotation writer が raw row を超えて集計を書く必要が出た → Stop（§I4 opaque 逸脱）。
- budget 到達 → Stop。

## Dependencies
- I1（provenance pass）、I2（`run_bank_mloop` / `BankLlmCallRecord` / annotation 型 / bank overlay）。I3 の call
  cap を再利用（緑後が望ましい）。

## Status
TODO

## Execution Result
（完了時に記入。PR 本文になる）
