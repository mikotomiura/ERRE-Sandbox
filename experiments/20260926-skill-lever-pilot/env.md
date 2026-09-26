# 実行環境

- Python 3.11、`uv.lock` 固定。追加依存なし (numpy のみ)。
- 本 PR (凍結) は CPU のみ。GPU・ネットワーク・モデル forward を使わない。
- pilot 実走 (凍結後、別途 user 裁定): G-GEAR、Windows native Ollama、`qwen3:8b`、`think=False`。
  要求条件 (sampling / num_ctx / num_predict) は `scripts/skill_lever_battery.py` の凍結値で、
  run は `scripts/skill_lever_scorer.request_meta()` と一致する `meta.json` を書く。

## 実走時の環境 (2026-09-26、`results/run/provenance.json` が一次記録)

- 実行: `scripts/skill_lever_driver.py` (main=`95b2eb4`、#122)、G-GEAR、Windows native、`Start-Process -WindowStyle Hidden`
  (PYTHONUTF8=1)。2026-09-26T11:44:01Z〜11:47:18Z (UTC)、1,200 呼び出し逐次、再送 0・length 打ち切り 0。
- Ollama 0.32.12、`qwen3:8b` digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` (開始・終了で同一)。
  OLLAMA_FLASH_ATTENTION=1、OLLAMA_KV_CACHE_TYPE=q8_0、OLLAMA_NUM_PARALLEL=4 (driver は逐次なので並列は使っていない)、
  OLLAMA_HOST=0.0.0.0:11434。
- GPU: NVIDIA GeForce RTX 5060 Ti 16 GB (他の GPU 計算プロセスなし)。
- 起動前検査 (`launch_problems()`) は空 = driver certification (31/31 KILLED、driver・test の sha256) 一致、固定ファイルは HEAD と一致。
  provenance の `git_dirty: true` は追跡外の `tmlr-submit/`・`tmp/` と実走中に作られた `results/run/` による。
