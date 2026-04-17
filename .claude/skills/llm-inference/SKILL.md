---
name: llm-inference
description: >
  ローカル LLM 推論バックエンドの構成・起動・VRAM 管理・パフォーマンス監視。
  SGLang / Ollama / vLLM のサーバーを起動・設定する時、
  モデルをダウンロード・デプロイする時、VRAM 予算を計算する時に必須参照。
  sglang_adapter.py / ollama_adapter.py / inference/server.py を変更する時に自動召喚される。
  nvidia-smi / ollama list を実行して現在の推論状態を動的に確認できる。
  ペルソナ管理・ERRE モード・サンプリングパラメータは persona-erre Skill を参照。
  エラーハンドリング・フォールバックは error-handling Skill を参照。
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash(ollama *), Bash(curl *), Bash(nvidia-smi *)
---

# LLM Inference

## このスキルの目的

ERRE-Sandbox は RTX 5060 Ti 16GB という限られた VRAM で 8-10 ペルソナの並列推論を
安定稼働させる。このスキルは推論バックエンドの「構成と運用」に特化する。
「何を推論するか (ペルソナ・ERRE モード)」は persona-erre Skill、
「障害時の回復」は error-handling Skill にそれぞれ委譲する。

## 現在の推論環境

!`nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "(GPU not available on this machine)"`

!`ollama list 2>/dev/null || echo "(Ollama not running)"`

!`curl -s http://localhost:30000/health 2>/dev/null && echo "SGLang: healthy" || echo "SGLang: not reachable"`

## 推論バックエンドの構成

| バックエンド | 用途 | エンドポイント | タイムアウト | 備考 |
|---|---|---|---|---|
| SGLang | 本番 | `http://g-gear.local:30000` | 30s | RadixAttention で prefix KV 共有 |
| Ollama | 開発 | `http://localhost:11434` | 60s | 環境変数で並列数・KV 設定を制御 |
| vLLM | 将来 (M9+) | 未定 | 未定 | `--enable-lora` で per-persona LoRA |

## ルール 1: Ollama の環境変数を必ず設定

```bash
# ✅ 推奨 — 環境変数を設定して起動
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
ollama serve
```

```bash
# ❌ デフォルト設定のまま起動 → 8 エージェントが逐次実行
ollama serve
```

## ルール 2: SGLang サーバーの起動��定

```bash
# ✅ RadixAttention 前提の起動
python -m sglang.launch_server \
  --model-path /models/Qwen3-8B-Q5_K_M.gguf \
  --port 30000 --host 0.0.0.0 \
  --mem-fraction-static 0.85
```

## ルール 3: VRAM 予算内のモデル選定

16GB の予算配分:

| 項目 | 使用量 |
|---|---|
| ベースモデル重み (Q5_K_M) | ~5.5 GB |
| KV キャッシュ (q8_0, 8並列 x 4K) | ~5-6 GB |
| RadixAttention 共有 prefix 節約 | -30% (KV 部分) |
| CUDA コンテキスト | ~2 GB |
| **合計** | **~13 GB / 16 GB** |

**量子化方式**: Q5_K_M を標準。Q4_K_M は品質劣化大、Q6_K は VRAM 超過。

```python
# ✅ VRAM に収まるモデル
DEFAULT_MODEL = "qwen3:8b-q5_K_M"          # ~5.5 GB
ALTERNATIVE_MODEL = "llama-3.1-swallow:8b-q5_K_M"
```

```python
# ❌ VRAM オーバー
DEFAULT_MODEL = "qwen3:14b-q5_K_M"         # ~9 GB → KV 込みで超過
```

## ルール 4: context 長とバッチサイズのトレードオフ

```
context 4K × 8並列 → ~13 GB (推奨)
context 8K × 6並列 → ~13 GB (長文必要時)
context 8K × 8並列 → ~16 GB (非推奨)
```

並列数を減らすと認知サイクルのスループットが低下する。
context 4K で十分な場合は並列数を優先する。

## ルール 5: パフォーマンス監視

30 tok/s を下回った場合:
1. `nvidia-smi` で VRAM 使用量を確認
2. 並列数の削減 (8 → 6) を検討
3. context 長の短縮 (8K → 4K) を検討

## チェックリスト

- [ ] Ollama 環境変数 (NUM_PARALLEL, FLASH_ATTENTION, KV_CACHE_TYPE) を設定したか
- [ ] モデルが Q5_K_M 量子化で VRAM 13GB 以内に収まるか
- [ ] `nvidia-smi` で VRAM 16GB を超えていないか
- [ ] SGLang の RadixAttention で共有 prefix が設計されているか
- [ ] サーバー起動が CLI で再現可能か

## 補足資料

- `operations.md` — サーバー起動手順、モデルダウンロード、VRAM 計算ワークシート、トラブルシューティング

## 関連する他の Skill

- `persona-erre` — ERRE モード別サンプリングパラメータ、ペルソナ YAML、system prompt
- `error-handling` — SGLang → Ollama フォールバック、タイムアウト処理、リトライ
- `architecture-rules` — inference/ のレイヤー依存方向
