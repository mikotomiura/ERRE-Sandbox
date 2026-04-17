# LLM Inference — 運用手順書

---

## サーバー起動手順

### Ollama (開発環境)

```bash
# 1. 環境変数を設定
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0

# 2. サーバー起���
ollama serve

# 3. モデルが存在することを確認
ollama list

# 4. ヘルスチェック
curl http://localhost:11434/api/tags
```

### SGLang (本番環境、G-GEAR)

```bash
# 1. モデルファイルが /models/ に存在することを確認
ls -lh /models/Qwen3-8B-Q5_K_M.gguf

# 2. サーバー起動
python -m sglang.launch_server \
  --model-path /models/Qwen3-8B-Q5_K_M.gguf \
  --port 30000 \
  --host 0.0.0.0 \
  --mem-fraction-static 0.85

# 3. ヘルスチェック
curl http://g-gear.local:30000/health
```

---

## モデルダウンロードチェックリスト

```bash
# Ollama 経由でダウンロード
ollama pull qwen3:8b-q5_K_M

# または GGUF を直接ダウンロード (HuggingFace Hub)
huggingface-cli download \
  Qwen/Qwen3-8B-GGUF \
  qwen3-8b-q5_k_m.gguf \
  --local-dir /models/
```

ダウンロード後の確認:
- [ ] ファイルサイズが ~5.5 GB であること
- [ ] `ollama run qwen3:8b-q5_K_M "Hello"` で応答が返ること
- [ ] 日本語で `ollama run qwen3:8b-q5_K_M "こんにちは"` が正しく返ること

---

## VRAM 計算ワークシート

```
モデル: Qwen3-8B Q5_K_M
��子化: 5-bit K-quant mixed
パラメータ数: 8B

=== 重み ===
8B × 5bit / 8 = 5.0 GB
+ K-quant metadata overhead ~0.5 GB
= ~5.5 GB

=== KV キャッシュ (q8_0) ===
計算式: 2 × n_layers × (n_kv_heads × head_dim) × context_len × batch_size × 1byte
Qwen3-8B: 2 × 32 × (8 × 128) × 4096 × 8 × 1
= ~2.1 GB (q8_0)
RadixAttention 共有 prefix 節約: -30%
= ~1.5 GB 実効

=== CUDA / アクティベーション ===
~2 GB

=== 合計 ===
5.5 + 1.5 + 2.0 + overhead ≒ 13 GB (16 GB に収まる)
```

---

## トラブルシューティング

### 症状: Ollama が応答しない

```bash
# 1. プロセス確認
pgrep -f ollama

# 2. ポート確認
lsof -i :11434

# 3. ログ確認
journalctl -u ollama -f  # systemd の場合

# 4. VRAM 確認
nvidia-smi

# 5. 解決策
# a. VRAM 不足 → 並列数を減らす (OLLAMA_NUM_PARALLEL=2)
# b. プロセスハング → killall ollama && ollama serve
# c. モデル破損 → ollama rm qwen3:8b-q5_K_M && ollama pull qwen3:8b-q5_K_M
```

### 症状: SGLang の tok/s が低い

```bash
# 1. メトリクス確認
curl http://g-gear.local:30000/metrics | grep throughput

# 2. GPU 使用率確認
nvidia-smi dmon -d 1

# 3. 解決策
# a. GPU 使用率が低い → batch サイズ増加
# b. VRAM が 100% → --mem-fraction-static を下げる (0.85 → 0.80)
# c. prefix 再利用率が低い → system prompt の共通部分を前方に配置
```
