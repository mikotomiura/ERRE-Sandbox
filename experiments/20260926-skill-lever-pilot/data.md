# データ

- 凍結時 (本 PR): 実データなし。power 表は合成模擬のみ (`results/power_table.json`)。
- 実走後: `results/run/samples.jsonl` (1 行 1 sample: call_index / arm / replicate / probe_id / k / seed /
  prompt_sha256 / raw / parsed、schema は prereg §4) と `results/run/meta.json`。生テキスト `raw` を全件保存する。
- 凍結 manifest: `manifest.json` (判定に関わる全ファイルの sha256、prereg §8)。
