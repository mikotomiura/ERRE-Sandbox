# データ

- 起草時 (DRAFT): 実データなし。モデルの出力は 1 件も持っていない。
  - 見取り図 (`results/sketch.json`) は合成の選択の模擬だけ。
  - fixture 表 (`results/fixture_table.json`) と probe key の選定 (`results/key_selection.json`) は、凍結した設計の上の決定的な計算だけ。
  - 雑音構造の目安として、v2 の実走記録 (`experiments/20260926-skill-lever-pilot/results/run/samples.jsonl`) を読んだ
    (セル内 K = 10 の最頻の割合 0.992。用途 = K と単位の設計の目安。v2 の verdict は再評価しない。prereg §2.5)。
- null pilot の後 (第 1 段の凍結と別の user 裁定の後): `results/pilot/records.jsonl` (1 行 1 呼び出し、schema は prereg §4) と
  `results/pilot/meta.json`、機械判定の出力 `results/pilot/gate.json`。
- 本走の後 (第 2 段の凍結と別の user 裁定の後): `results/run/records.jsonl`・`results/run/meta.json`・判定の出力 `results/run/results.json`。
- 凍結 manifest: `manifest.json` (第 1 段) と `manifest_main.json` (第 2 段)。prereg §9。
  - `manifest_main.json` (2026-10-05、user 裁定 DP-3): 第 2 段の封印。34 ファイル (第 1 段の対象 25 + `manifest.json`・`results/pilot/` の
    records・meta・provenance・gate.json・driver・driver の harness・driver の test・driver の certification) の sha256 と `prereg_body_sha256`。
    モデルの出力は含まない (pilot の記録の sha256 だけ)。決定的な計算 (`--write --stage main`)、sha256 は env.md の「第 2 段の凍結」節。
