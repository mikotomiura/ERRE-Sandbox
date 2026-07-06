# Codex TASK-POST cross-review — M13 Phase 1 sealed live run 統合 diff

Loop Engineering の **TASK-POST ゲート** (全 issue 緑 + 統合 CI 緑後、最終 merge 前)。ブランチ
`feat/ecl-v0-live-run` (main からの統合 diff) をレビューせよ。

## タスク概要
ECL v0 organ (live LLM 認知 × 3D embodiment substrate 統合器官) を **real qwen3:8b で一度封印実走**
(first-contact) し、captured Plane2 → Ollama-free deterministic replay-verify。**construction validation で
あって measurement verdict でない** (floor/landscape/verdict 非出力、measurement 非再入 holding 不可侵)。
sealed run 結果 = **GO** (O1 完走 / O2 replay 再現 / O3a-b cross-platform WSL byte 一致 / O5=32/32 / O4 非縮退)。

## レビュー対象 (統合 diff = main..feat/ecl-v0-live-run)
`git diff main..feat/ecl-v0-live-run -- src/ scripts/ tests/` の 4 ファイル (1326 行追加):
- `src/erre_sandbox/integration/embodied/live.py` — ThinkOffChatClient + run_live_capture + protocol 定数 +
  env-pin/observables overlay
- `scripts/ecl_v0_live_capture.py` — --capture (live) / --verify (Ollama-free replay-verify)
- `tests/test_integration/test_ecl_live_capture.py` — I1 apparatus test
- `tests/test_integration/test_ecl_live_golden.py` — I4 replay-verify test (live artifact = experiments/.../artifacts)
committed live artifact = `experiments/20260706-ecl-v0-live-capture/artifacts/{manifest,decisions,ecl_trace,
envelope_stream}` + env.md。

## 参照 (binding)
- FROZEN ADR: `.steering/20260706-m13-forward-primary/design-final.md` (§FROZEN、O1-O5、Done=O1∧O2∧O3a∧O3b)
- decisions: `.steering/20260706-ecl-v0-live-run/decisions.md` (D-1..8)
- TASK-PRE 反映済 (Codex): HIGH-1 ThinkOffChatClient / HIGH-2 O5 annotation 非 green-gate / MEDIUM-2 O3b env_pins
  再利用 / MEDIUM-3 O5 refinement。

## 特に見てほしい
1. **binding 遵守**: 既存 seam (loop.py/cycle.py/world/tick.py/handoff.py/ecl_v0_golden.py) 無改変か。
   measurement 非再入 (evidence/spdm/runningness 非 import、floor/landscape/verdict 非計算) は守られているか。
2. **ThinkOffChatClient**: think=False 強制転送が正しいか。inner 例外伝播 (OllamaUnavailableError) が record mode
   捕捉と競合しないか。
3. **cross-platform determinism**: verify の re-render が committed manifest env_pins/run を再利用し fresh capture
   drift を避けているか。6桁量子化の射程 (raw content 非 float は固定入力再利用) は正しいか。
4. **tune-to-pass 封鎖**: O5 が hard green gate でなく annotation (hard_gate=False)、O5==0 は branch outcome か。
   protocol 定数が sealed run 前固定か。
5. **correctness bug**: replay-verify の determinism 穴、env-pin 記録漏れ、async/リソース (store/embedding close)
   の扱い。
6. **事実誤認**は HIGH で切り出す。

## 報告
HIGH/MEDIUM/LOW + 根拠 (ファイル・行) + 推奨修正。末尾に **Verdict: Adopt / Adopt-with-changes / Revise /
Block**。doc/style 微細指摘不要、correctness + binding に集中。
