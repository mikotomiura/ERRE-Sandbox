# experiments/20260630-es4-phase0

M13-ES4 Phase 0 (feasibility/power binary gate, ADR §4.1) の再現ディレクトリ。

## 構成
- `run.sh` — 1 コマンド再現 (pre-flight assert → SGLang 起動 → Phase A → phase-flip →
  Phase B → verdict)。WSL root GPU venv + `/mnt/c` の src を `PYTHONPATH` で実行。
- `run-manifest.json` — full-freeze snapshot (§5 constants + battery/recipe/model/sglang
  hash)。verdict 生成前に焼く (forking-paths seal)。**本番 run 前に生成**。
- `smoke/` — real wiring smoke (縮小 subset、非科学的) の永続物。
- `phaseA/` — 本番 Phase A 永続物 (generations/judgements/scores jsonl + manifest)。**次 GO 後**。
- `verdict-phase0.json` — 本番 Phase 0 verdict + forensic。**次 GO 後**。

## 状態 (2026-06-30)
- 実装 + 決定論テスト green + real wiring smoke + full-freeze + pre-flight PASS 完了。
- **本番 Phase 0 full run = 実行完了 (2026-06-30、不可逆 sealed)**:
  - **VERDICT = INVALID_SCORER** (§4.1 PASS-STOP step 1 = scorer 非トートロジー gate)。
  - (a1) temp-stratified min AUC 0.500 < 0.80 ∧ (a2) held-out residual ΔDQ CI_lower −0.0083 ≤ 0。
  - run valid (replay_misses 全ゼロ / n_clusters 48 / phase0_total 3.82 GPU-hr ≤ 8 / adversarial AUC 0.9125)。
  - apparatus 完全不変・tune ゼロ (forking-paths seal 保持)。**非 PASS = Phase 1 へ進まない**。
  - 詳細 = `.steering/20260630-m13-es4-phase0/verdict-record.md`、verdict = `verdict-phase0.json`。

## backend
SGLang fp8 qwen3:8b 単一 (16GB、BF16 OOM 回避)。MPNet encoder は CPU。phase-flip =
SGLang server 停止で GPU 解放 → CPU encoder (transformers swap 不要、decisions.md DA-PH0-1)。
replay-seam: Phase A が全 LLM 量を永続化、Phase B が replay + live encoder を無改変
`pipeline.run_phase` へ。
