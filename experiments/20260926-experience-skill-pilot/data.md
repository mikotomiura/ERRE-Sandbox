# データ

- 合成の経験 (成否集計) は `scripts/skill_experience_battery.py` が決定的に生成する。LLM は使わない。
- power 表は合成模擬のみ (`results/power_table.json`)。
- 凍結 manifest: `manifest.json` (判定に関わる全ファイルの sha256、prereg v3 §8)。

## 実走記録 (2026-09-27)

判定の入力:
- `results/run/samples.jsonl`: 2,160 行。1 行 1 sample で、欄は call_index / arm / replicate / probe_id / k / seed /
  prompt_sha256 / raw / parsed (schema は prereg v3 §4)。生テキスト `raw` を全件保存している。
- `results/run/meta.json`: 送った body の観測値。

判定に使わないもの:
- `results/run/attempts.jsonl`: 送信 1 回につき 1 行。
- `results/run/provenance.json`: 来歴。`scripts/skill_experience_run_gate.py` が判定の前にこれを検査した → `RUN GATE OK`。

出力:
- `results/run/results.json`: `run.sh` の出力 (manifest 照合 → 判定 ×2 が byte 一致)。
- `results/run/describe.json`: prereg v3 §10 の記述報告 (`scripts/skill_experience_describe.py`)。判定には使わない。
