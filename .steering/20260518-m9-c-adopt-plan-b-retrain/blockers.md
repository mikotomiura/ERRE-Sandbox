# ブロッカー記録

## ブロッカー 1: SGLang 初回起動 OOM (BF16 で Qwen3-8B が 16 GB VRAM に fit せず)

- **発生日時**: 2026-05-16 13:49 JST
- **症状**: Plan B next-session prompt 通り
  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
  --port 30000 --mem-fraction-static 0.85 --chunked-prefill-size 8192
  --max-running-requests 8 --disable-cuda-graph` を起動 → shards loading 後
  `RuntimeError: Not enough memory. Please try to increase
  --mem-fraction-static. Current value: mem_fraction_static=0.85` →
  child sigquit で server 停止
- **試したこと**:
  1. K-α report (`.steering/20260508-m9-c-spike/k-alpha-report.md`) の launch
     v5 invocation を確認 — `--quantization fp8` + `--max-total-tokens 2048`
     + `--max-running-requests 1` が empirical に必須と判明
  2. `scripts/m9-c-spike/launch_sglang.sh` の参照 — fp8 quant + LoRA enable
     付きが既存運用形態
- **原因**: Plan B next-session prompt に含まれる SGLang command が BF16
  default (`dtype="auto"`) であり、Qwen3-8B (≈ 16 GB BF16) が
  16 GB VRAM の RTX 5060 Ti に静的に fit しない。`mem-fraction-static`
  を上げても KV cache + activations の余裕がなく fail する。
- **解決方法**: K-α report の launch v5 invocation に準拠し、
  `--quantization fp8 --max-total-tokens 2048 --max-running-requests 1`
  を追加して再起動 (LoRA enable は Plan B 採取は base model のため省略)。
  PID 395 で再起動成功。
- **教訓**:
  - Qwen3-8B + 16 GB VRAM SGLang 起動は **常に fp8 必須**。Plan B / Plan C
    / 後続セッションの handoff prompt にも `--quantization fp8 --max-total-
    tokens 2048 --max-running-requests 1` を明文化する
  - K-α report の launch v5 が単一 source of truth、Plan A / Plan B handoff
    の SGLang command は launch v5 から **delta だけ書く** 運用に揃える
  - memory `qwen3:8b + Ollama gotchas` と並列の SGLang メモリ memo を起こす
    候補 (本 PR の reflection で検討)
