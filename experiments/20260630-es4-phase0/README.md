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
- 実装 + 決定論テスト green + real wiring smoke + full-freeze + pre-flight PASS **まで完了予定**。
- **本番 8 GPU-hour Phase 0 full run は未実行** (user 裁定で次の明示 GO 待ち)。

## backend
SGLang fp8 qwen3:8b 単一 (16GB、BF16 OOM 回避)。MPNet encoder は CPU。phase-flip =
SGLang server 停止で GPU 解放 → CPU encoder (transformers swap 不要、decisions.md DA-PH0-1)。
replay-seam: Phase A が全 LLM 量を永続化、Phase B が replay + live encoder を無改変
`pipeline.run_phase` へ。
