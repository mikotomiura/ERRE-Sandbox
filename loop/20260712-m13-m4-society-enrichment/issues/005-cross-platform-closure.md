# Issue 005 (I5): cross-platform closure — WSL byte parity + pre-push CI parity 4段
verify_level: recheck   # 再現性契約（cross-platform byte 一致）+ push gate

## Goal
新 golden の cross-platform 再現性を実測 closure する: WSL で `--verify` byte 一致（Ollama-free）+
pre-push CI parity 4段（ruff format --check / ruff check / mypy src / pytest -q）全 pass。
**push / PR は 4段 pass 前に禁止**（feedback_pre_push_ci_parity）。

## Background
FROZEN design-final §F / §R2 / §R7。6桁量子化 `handoff.canonical_dumps` + WSL 実測で cross-platform
libm float drift を吸収（feedback_golden_crossplatform_float_drift、PR #55 で ECL が実証済）。
`--verify` は Ollama-free ゆえ WSL 可（R7）。WSL GPU/torch は不要（verify は replay のみ）。

## Scope
### In
1. **WSL byte parity**: WSL `/root/erre-sandbox`（or 同期先）で
   `python scripts/m4_society_live_capture.py --verify --artifact-dir tests/fixtures/m4_society_live_golden` exit 0
   （Windows bake の golden を Linux/glibc で replay → 6桁量子化で byte 一致実測）。
2. **pre-push CI parity 4段**: `pwsh scripts/dev/pre-push-check.ps1`（or `bash scripts/dev/pre-push-check.sh`）
   = ruff format --check / ruff check / mypy src / pytest -q 全 pass（CI 等価条件、Godot test は GODOT_BIN
   有りで実走 or 環境で skip）。
### Out
- 実装変更（I1-I3 で確定）。real capture（I4）。TASK-POST cross-review（別工程）。

## Allowed Files
- （検証のみ、実装変更なし）必要なら `.steering/.../blockers.md` に cross-platform drift 実測を記録

## Acceptance Criteria
- AC5-G1: WSL `--verify` exit 0（Windows bake golden の Linux replay byte 一致）。
- AC5-G2: `pwsh scripts/dev/pre-push-check.ps1` = `ALL CHECKS PASSED`（4段）。
- AC5-G3: `git diff` が read-only set（society.py/handoff.py/EclReplayPlayer.gd/MainScene.tscn/既存 m2 golden/
  凍結 evidence）に触れていない（無改変証明）。

## Test Plan
WSL で verify 実走（Ollama-free）。pre-push-check スクリプトを CI 同条件で local 実行。全段緑で push 可。
1 段でも fail なら push 禁止 → 修正 → 再実行。

## Stop Conditions
- WSL byte 不一致（float drift が量子化を超える）→ blockers.md（drift 実測 + 量子化桁再検討、要れば ADR）。
- pre-push 4段の 1 段でも fail → push せず修正。
- read-only set に diff → Stop（無改変違反）。
- budget 到達 → Stop。

## Dependencies
- **I1, I2, I3, I4**（全実装 + landed golden が前件）。

## Status
todo

## Execution Result
（完了時に記入。PR 本文になる）
