# Issue 002 (I4-logic): Ollama-free replay-verify apparatus (O3a/O3b/O5)
verify_level: recheck   # reproduction 契約・AC 直結

## Goal
committed live artifact を **Ollama-free で deterministic replay-verify** する apparatus + test を構築する。
O3a (committed decisions のみ replay → checksum 一致 + inner_invocations==0) / O3b (raw Plane2 → artifact
re-render SHA 一致) / O5 (≥1 tick で llm_status==ok∧plan≠None∧resolved_from==memory_centroid) + repro.sh。
**Issue 003 の committed live artifact が未生成ゆえ、test logic は既存 synthetic golden をテンプレに先行実装**
(Issue 004 で live artifact へ差替え)。

## Background
FROZEN ADR O2/O3a/O3b/O5、Codex HIGH-2 (O3 を O3a/O3b 分割、live 再 capture byte 一致は非要求) / MEDIUM-2
(O5 parsed-action)。grill-goals.md I4 + D-5/D-6/D-8。`scripts/ecl_v0_golden.py --verify` 構造写経。設計 FROZEN。

## Scope
### In
- 新規 `tests/test_integration/test_ecl_live_golden.py` — O3a/O3b/O5 の verify logic。**synthetic golden
  (`tests/fixtures/ecl_v0_golden/`) をテンプレ入力に green** (Issue 004 で `experiments/.../artifacts/` へ差替え、
  fixture path を定数化して切替容易に)。
- verify helper (Issue 001 `live.py` の replay 経路 or `scripts/ecl_v0_live_capture.py --verify` 相当、
  handoff serializer 再利用) — committed decisions → replay → checksum + re-render SHA + O5 boolean。
- 新規 `experiments/20260706-ecl-v0-live-capture/repro.sh` (1 コマンド Ollama-free replay-verify、雛形)。
### Out
- committed live artifact 生成 (Issue 003)。live artifact への最終差替え+cross-platform 実測 (Issue 004)。
  measurement 再入 (O4/O5 は boolean/counting annotation のみ、floor/landscape/verdict 計算禁止)。

## Allowed Files
- `tests/test_integration/test_ecl_live_golden.py` (新規)
- `scripts/ecl_v0_live_capture.py` (Issue 001 の script に `--verify` サブコマンド追加は可、CLI のみ)
- `experiments/20260706-ecl-v0-live-capture/repro.sh` (新規)
- **無改変**: `loop.py`/`cycle.py`/`world`/`handoff.py`/`ecl_v0_golden.py`/`live.py` の公開 API (import のみ)

## Acceptance Criteria (AC↔test)
- I4-G1: `test_live_golden_replay_checksum_matches` — committed decisions のみ replay → manifest checksum 一致 +
  inner_invocations==0 (O3a、テンプレは synthetic golden で green)
- I4-G2: `test_live_golden_artifact_rerender_sha` — 同一 raw Plane2 → full artifact re-render SHA 一致 (O3b)
- I4-G3: `test_live_golden_parsed_action_path` — decisions に O5 (≥1 tick llm_status==ok∧plan≠None∧
  resolved_from==memory_centroid) 成立を boolean assert
- I4-G4: `test_live_golden_measurement_guard` — verify が floor/landscape/verdict を計算・出力しない
- I4-G5: `bash experiments/20260706-ecl-v0-live-capture/repro.sh` exit 0 (テンプレ artifact で)
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_live_golden.py` (synthetic golden テンプレ入力) + pre-push 4 段。
fixture path を module 定数化し Issue 004 で experiments/ へ 1 行差替え可能に。

## Stop Conditions
- 全 AC 緑 (Done、テンプレ入力)。
- replay-verify logic が既存 seam の改変を要する → Stop (superseding ADR)。
- O5 判定が measurement (分布/floor) を要し始める → Stop (holding 侵食)。

## Dependencies
- **Issue 001 (live.py replay 経路 import)**。autonomous だが 001 land 後に着手 (直列)。Issue 004 の前提。

## Status
QUEUED

## Execution Result
(完了時に記入)
