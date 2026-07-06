# Issue 004 (I4-final): live-golden finalize + cross-platform confirm
verify_level: recheck   # reproduction 契約 (committed live artifact)

## Goal
Issue 002 の replay-verify test を **committed live artifact (Issue 003) へ差替え**、O3a/O3b/O5 が real capture で
緑 + repro.sh Ollama-free 再現 + cross-platform 実測確定。これで **Done=O1∧O2∧O3a∧O3b** が live artifact 上で
成立し first-contact = construction validated が閉じる。

## Background
Issue 002 は synthetic golden テンプレで logic 緑化済。Issue 003 が real artifact を commit。本 issue は
fixture path を experiments/ へ切替え、live artifact で全 verify 緑を確定。設計 FROZEN。

## Scope
### In
- `test_ecl_live_golden.py` の fixture path 定数を `experiments/20260706-ecl-v0-live-capture/artifacts/` へ差替え。
- live artifact で I4-G1..G5 全緑 (O3a/O3b/O5 real、repro.sh exit 0)。
- O5 annotation (成功 tick 数) / O4 非縮退 を test で boolean assert (counting のみ、分布非計算)。
### Out
- measurement 再入。live re-capture の cross-platform byte 一致要求 (Codex HIGH-2: 非要求)。artifact 再生成 (003)。

## Allowed Files
- `tests/test_integration/test_ecl_live_golden.py` (fixture path + live artifact assert)
- `experiments/20260706-ecl-v0-live-capture/repro.sh` (path 確定)
- **無改変**: committed artifact (003 成果物、read-only)、src の seam

## Acceptance Criteria (AC↔test)
- I4-G1: `test_live_golden_replay_checksum_matches` — **committed live** decisions replay → checksum 一致 +
  inner_invocations==0 (O3a)
- I4-G2: `test_live_golden_artifact_rerender_sha` — live raw Plane2 → artifact re-render SHA 一致 (O3b)
- I4-G3: `test_live_golden_parsed_action_path` — live decisions に O5 ≥1 成立 (first-contact 存在証明)
- I4-G4: `test_live_golden_measurement_guard` — floor/landscape/verdict 非計算・非出力
- I4-G5: `bash experiments/20260706-ecl-v0-live-capture/repro.sh` exit 0 (Ollama-free)
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_live_golden.py` (committed live artifact) + repro.sh + pre-push 4 段。

## Stop Conditions / Branch (軸5)
- 全 AC 緑 (Done、live artifact 上で first-contact construction validated)。
- replay-verify が committed live artifact に一致しない (003 の非決定) → Stop→superseding hardening。
- O5==0 → construction 妥当性 branch (003 の O5 annotation を承け)。

## Dependencies
- **Issue 003 (committed live artifact) 必須**。autonomous /loop-issue (小)、003 land 後。

## Status
QUEUED

## Execution Result
(完了時に記入 — PR 本文候補)
