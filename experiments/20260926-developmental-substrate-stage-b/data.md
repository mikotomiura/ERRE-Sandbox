# データ

- B-pre の入力 = `experiments/20260710-m13-c-proper/artifacts/bank_annotation.jsonl` (tracked、LF)。
  8 context × 2 条件 (on / off) × 300 sample、列 `pre_bias_destination_zone`。sha256 は prereg §7 に固定され、
  `results/b_pre/results.json` の `inputs` に観測値が記録される。
- B1 は合成データのみ (`tests/test_stage_b/`)。実モデル出力は使わない。
