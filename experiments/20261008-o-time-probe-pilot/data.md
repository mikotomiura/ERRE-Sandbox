# データ

- 第 1 段 (PILOT-FROZEN) まで: 実データなし。モデルの出力は 1 件も持っていない。
  - 見取り図 (`results/sketch.json`) は合成の選択の模擬だけ。
  - fixture 表 (`results/fixture_table.json`) は、凍結した設計の上の決定的な計算だけ。
  - 既存の実走記録 (v2〜v5・G) は、判定にも見取り図にも使っていない (prereg §0 #16・#17)。
- null pilot の後 (第 1 段の凍結と別の user 裁定の後): `results/pilot/records.jsonl` (1 行 1 呼び出し、schema は prereg §4) と
  `results/pilot/meta.json`・`results/pilot/provenance.json`、機械判定の出力 `results/pilot/gate.json`。
- 本走の後 (第 2 段の凍結と別の user 裁定の後): `results/run/records.jsonl`・`results/run/meta.json`・判定の出力 `results/run/results.json`。
- 凍結 manifest: `manifest.json` (第 1 段) と `manifest_main.json` (第 2 段)。prereg §9。
