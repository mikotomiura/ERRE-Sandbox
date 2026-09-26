# 実行環境

- Python 3.11、`uv.lock` 固定。追加依存なし (numpy のみ)。
- 本 PR (凍結) は CPU のみ。GPU・ネットワーク・モデル forward を使わない。
- pilot 実走 (凍結後、別途 user 裁定): G-GEAR、Windows native Ollama、`qwen3:8b`、`think=False`。
  要求条件 (sampling / num_ctx / num_predict) は `scripts/skill_lever_battery.py` の凍結値で、
  run は `scripts/skill_lever_scorer.request_meta()` と一致する `meta.json` を書く。
