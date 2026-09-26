# データ

- 凍結時 (本 PR): 実データなし。power 表は合成模擬のみ (`results/power_table.json`)。
- 実走後: `results/run/samples.jsonl` (1 行 1 sample: call_index / arm / replicate / probe_id / k / seed /
  prompt_sha256 / raw / parsed、schema は prereg §4) と `results/run/meta.json`。生テキスト `raw` を全件保存する。
- 凍結 manifest: `manifest.json` (判定に関わる全ファイルの sha256、prereg §8)。

## 実走記録 (2026-09-26)

- `results/run/samples.jsonl` (1,200 行、判定入力)・`results/run/meta.json` (送った body の観測値、判定入力)。
- `results/run/attempts.jsonl` (送信 1 回 1 行)・`results/run/provenance.json` (来歴) — 判定に使わない。
- `results/run/results.json` = `run.sh` の出力 (manifest 照合 → 判定 ×2 byte 一致)。
- `results/run/describe.json` = prereg §10 の記述報告 (`scripts/skill_lever_describe.py`、判定に使わない)。
