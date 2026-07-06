# Issue 003 (I3): sealed live run + committed artifact [MANUAL sealed gate — loop 外]
verify_level: recheck   # ただし autonomous /loop-issue 対象外 (live Ollama 一発)。verify = Issue 002/004 の replay-verify gate + WSL byte 一致

## Goal
Issue 001 の apparatus を **G-GEAR で real qwen3:8b に対し封印実走** (think=False, N=32) し、captured real
Plane2/trace/manifest を `experiments/20260706-ecl-v0-live-capture/artifacts/` へ committed (6桁量子化)。
first-contact = organ が real LLM で substrate を end-to-end 駆動した唯一の実走。**Done = O1∧O2∧O3a∧O3b**、
O4/O5 は channel-exercise annotation。

## Background
FROZEN ADR (construction validation、verdict なし)。**人手 sealed gate** (loop-watchdog は live Ollama を回せない)。
reference_g_gear_host (Ollama 起動)、reference_qwen3_ollama_gotchas (think=False)、
feedback_golden_crossplatform_float_drift (WSL byte 一致)、feedback_log_tail_completion_marker (完了判定)。

## Scope
### In
- G-GEAR で Ollama 起動 (qwen3:8b) → `python scripts/ecl_v0_live_capture.py --capture` (think=False, N=32,
  persona=kant, embedding=mock)。
- committed: `experiments/20260706-ecl-v0-live-capture/{run.sh, env.md, ollama.log, artifacts/{manifest.json,
  decisions.jsonl, ecl_trace.jsonl, envelope_stream.jsonl}}`。
- **WSL Linux (glibc) で committed artifact が Windows (UCRT) と byte 一致を手動実測** (O3a/O3b cross-platform)、
  env.md に記録。
### Out
- N体化 (B); measurement (C); Godot 可視化 (Milestone 4)。artifact への verify test (Issue 002/004)。

## Allowed Files (committed 成果物)
- `experiments/20260706-ecl-v0-live-capture/**` (run.sh/env.md/ollama.log/artifacts/*)
- **src/tests 無改変** (実走のみ、コードは Issue 001/002 で完結)

## Acceptance Criteria
- I3-G1 (O1): live 実走が例外なく完走 (N=32、α hardening の raised fallback で堅牢)
- I3-G2: artifact committed (6桁量子化、envelope_provenance embedded JSON float も量子化)
- I3-G3 (O2): committed decisions のみ replay → checksum byte 一致 + inner_invocations==0。**verify は CI fixture
  path 切替 (004) に依存しない standalone 手順** (Codex TASK-PRE MEDIUM-1): `python scripts/ecl_v0_live_capture.py
  --verify experiments/20260706-ecl-v0-live-capture/artifacts` または `bash experiments/.../repro.sh` で committed
  artifact を直接 verify
- I3-G4 (O3a/O3b): WSL Linux vs Windows で committed artifact byte 一致 (手動実測、env.md 記録)
- I3-G5 (annotation): O5 成功 tick 数 (≥1) + O4 非縮退 (distinct zone>1 or move target>1) を env.md へ honest 記録

## Test Plan
`bash experiments/20260706-ecl-v0-live-capture/repro.sh` (standalone、CI fixture path 非依存) exit 0 + WSL byte
一致目視。004 は CI fixture path の最終切替に限定 (MEDIUM-1)。

## Stop Conditions / Branch (軸5)
- **Stop**: replay 非決定/crash (I3-G3 fail) → superseding hardening ADR (Plan+Codex、cross-platform 量子化同型漏れ)。
- **Stop (軸6)**: WSL byte drift (I3-G4 fail) → 量子化漏れ特定 (envelope_provenance embedded float 疑い)。
- **branch**: O5==0 (全 unparseable) or O4 縮退 → construction 妥当性 branch (think=False 経路 or persona、
  measurement 非再入)。reproducibility Done は満たすが organ が channel 未 exercise。

## Dependencies
- **Issue 001 (apparatus) + Issue 002 (verify test) 緑後**。**人手実行** (autonomous loop 外)。Issue 004 の前提。

## Status
QUEUED (manual gate)

## Execution Result
(sealed run 後に記入 — O1-O5 実測値 + branch 判定)
