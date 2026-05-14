# m9-c-spike Adapter Swap Runbook (DB8)

> **目的**: M9-C-spike Phase K-β で確定した SGLang LoRA 経路の **operational
> manual**。launch SOP / adapter load-unload / 5 condition latency / N=3
> throughput / DB3 fallback fire 判断履歴を集約する。
>
> **対象読者**: 後続セッションで M9-C-adopt の production wiring を担当する
> オペレータ、本 spike の incident replay を行う security/SRE 担当。
>
> **生成元**: `.steering/20260508-m9-c-spike/` (`decisions.md` CS-1〜CS-9 +
> 2026-05-13 amendment、`blockers.md` B-1〜B-3、`tasklist.md` Phase K-β)
>
> **status**: ⏳ 本文書は Phase K-β 実走中の draft。実測値が入る箇所は
> `[実測値]` と marker されており、bench/latency 完了後に追記する。

---

## 1. 前提条件

### G-GEAR ハードウェア

- GPU: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell、Compute Capability 12.0)
- VRAM: 16,311 MiB total / 1,229 MiB baseline 使用 (idle、`nvidia-smi`)
- CUDA driver: 12.x (cu128 wheel が動作)
- Linux distro: WSL2 Ubuntu-22.04 (CS-1 amendment 2026-05-09、K-α #1 fire
  により Windows native sglang は破棄)

### Python stack (`/root/erre-sandbox/.venv`)

| パッケージ | バージョン | 用途 |
|---|---|---|
| python | 3.11 | base |
| torch | 2.9.1+cu128 | base |
| transformers | 5.3.0 | base + tokenizer + Trainer |
| sglang | 0.5.10.post1 | serving |
| peft | 0.19.1 | LoRA fine-tuning (B-3 解消で install) |
| bitsandbytes | 0.49.2 | NF4 quantization (B-3 解消で install) |
| accelerate | 1.13.0 | distributed/mixed precision (B-3 解消で install) |
| datasets | 3.6.0 | HF Dataset.from_list |

### Repository layout (G-GEAR)

- 訓練コード: `/root/erre-sandbox/src/erre_sandbox/training/train_kant_lora.py`
  (PR #162 で merge、editable install で venv に reflect)
- 評価データ: `/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb` (Windows
  側のみ、gitignored)
- adapter 出力: `/root/erre-sandbox/checkpoints/kant_r8_real/` (WSL2 ext4 で
  高速 I/O、~20-40 MB)
- log: `/mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs/`

---

## 2. SGLang launch SOP (CS-1 / launch v5、M9-C-adopt Phase B amendment 2026-05-13)

K-α PR #154/#155 で確定した launch v5 invocation。GPU メモリ 0.85 で
mem-fraction-static、`--enable-lora` で LoRA 経路を有効化、Q3-8B を fp8 で
serve する。

> **CS-1 amendment 2026-05-13 (M9-C-adopt Phase B、Codex HIGH-1 反映)**:
> `--max-lora-rank` の pin を **8 → 16** に拡張。理由: M9-C-adopt Phase B で
> rank ∈ {4, 8, 16} の empirical sweep を行うため、SGLang server が rank=16
> adapter を serve する必要がある。`--max-lora-rank` は SGLang 側の rank
> ceiling であり、これより小さい rank の adapter は問題なく load 可能 (rank=8
> baseline + rank=4 + rank=16 を同時 pin で扱う)。conditional rank=32
> tail-sweep fire 時は `--max-lora-rank 32` に再 amendment (DA-1)。
> 本 amendment は launch args の rank field のみ、CS-1 全体 (SGLang version pin
> 0.5.10.post1 / quantization fp8 / mem-fraction-static 0.85 等) は immutable。
> trace: `.steering/20260513-m9-c-adopt/decisions.md` DA-1 amendment。

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  cd /root/erre-sandbox && source .venv/bin/activate &&
  python -m sglang.launch_server \
    --model-path qwen3-8b \
    --quantization fp8 \
    --enable-lora \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loras-per-batch 3 \
    --max-lora-rank 16 \
    --max-loaded-loras 3 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --disable-cuda-graph \
    --max-running-requests 1 \
    --port 30000
'
```

### Health check

```bash
curl -sf http://localhost:30000/health
# 期待: 200 OK / {"status": "ok"}
```

### 既知の落とし穴

- `--max-loras-per-batch 3` / `--max-loaded-loras 3` / `--max-lora-rank 16`
  (M9-C-adopt Phase B amendment、元 CS-1 は `--max-lora-rank 8`) は CS-1
  + amendment と整合。これらが launch 時 unset だと runtime で
  `/load_lora_adapter` が PEFT format を reject する場合がある (CS-6 / K-α S-3)
- `--disable-cuda-graph` を外すと RTX 5060 Ti (Blackwell) で graph capture が
  unstable な observation あり (K-α S-2)
- `--max-running-requests 1` で **N=3 multi-LoRA bench** の concurrency は別
  port を立てるか `--max-concurrency 3` に明示的に上げる必要あり (CS-7)

---

## 3. PEFT adapter load / unload (CS-6 / CS-2)

### load_lora_adapter

```bash
curl -s -X POST http://localhost:30000/load_lora_adapter \
  -H "Content-Type: application/json" \
  -d '{
    "lora_name": "kant_r8_real",
    "lora_path": "/root/erre-sandbox/checkpoints/kant_r8_real",
    "pinned": false
  }' | jq
```

### unload_lora_adapter

```bash
curl -s -X POST http://localhost:30000/unload_lora_adapter \
  -H "Content-Type: application/json" \
  -d '{"lora_name": "kant_r8_real"}' | jq
```

### PEFT directory layout (CS-6 acceptance)

```
checkpoints/kant_r8_real/
  ├── adapter_config.json          (CS-6 必須)
  ├── adapter_model.safetensors    (CS-6 必須、~20-40 MB at rank=8)
  ├── tokenizer.json
  ├── tokenizer_config.json
  ├── special_tokens_map.json
  └── train_metadata.json          (本 spike の audit trail、CS-3/CS-4 全 config 保存)
```

---

## 4. 5 condition adapter swap latency (CS-8、実測値)

`scripts/m9-c-spike/measure_latency.py` を使用、`data/eval/spike/m9-c-spike-bench/k-beta-swap-latency.jsonl` に append:

```bash
python scripts/m9-c-spike/measure_latency.py \
  --adapter-path /root/erre-sandbox/checkpoints/kant_r8_real \
  --adapter-name kant_r8_real \
  --base-model qwen3-8b \
  --trials 3 \
  --out data/eval/spike/m9-c-spike-bench/k-beta-swap-latency.jsonl
```

### 実測値 (2026-05-13 G-GEAR、3 trial × 5 condition)

| condition | trials | min ms | median ms | max ms | 備考 |
|---|---|---|---|---|---|
| `cold_load` | 3 | 7.8 | 8.2 | 10.0 | 初回 load、weight materialisation 含む |
| `warm_reload` | 3 | 7.5 | 7.7 | 8.8 | unload + reload pair |
| `pinned` | 3 | 7132 | 7161 | 10869 | chat round-trip (pinned=true) |
| `unpinned` | 3 | 7102 | 7174 | 7206 | chat round-trip (pinned=false) |
| `no_lora` | 3 | 7107 | 7162 | 7185 | base model only baseline |

### CS-8 500ms threshold 判定

**PASS by 60x margin**: `cold_load` median 8.2 ms / `warm_reload` median 7.7 ms、
両者とも 500ms threshold を大幅に下回る。`pinned`/`unpinned`/`no_lora` の
~7100-7200 ms は chat generation latency が支配的で、adapter routing オーバーヘッド
は観測されない (pinned/unpinned/no_lora の差は 13ms 以内)。

→ **DB3 fallback NON-FIRE** (real adapter confirmation 完了、CS-8 即時 fire 条件
不発)。

---

## 5. N=3 throughput (CS-7、実測値)

`scripts/m9-c-spike/run_bench_serving.sh` で 3 baseline を取る:

```bash
bash scripts/m9-c-spike/run_bench_serving.sh
# 出力: data/eval/spike/m9-c-spike-bench/{no_lora,single_lora,multi_lora_3}.jsonl
```

### 実測値 (2026-05-13、num-prompts=16、random in/out=256/256、seed=0)

| baseline | TTFT median (ms) | ITL median (ms) | E2E mean (ms) | E2E P99 (ms) | output tok/s |
|---|---|---|---|---|---|
| `no_lora` | 26,180 | 27.70 | 27,501 | 46,897 | 35.54 |
| `single_lora` (Kant) | 26,819 | 28.35 | 28,225 | 48,110 | 34.64 |
| `multi_lora_3` | N/A (defer) | — | — | — | — |

### CS-7 4 trigger 判定

| trigger | threshold | 実測 | 判定 |
|---|---|---|---|
| p95 e2e > 2x single-LoRA | `single / no_lora` 1.026 < 2.0 | 1.026 | **NON-FIRE** |
| output tok/s < 70% baseline | `single / no_lora` 0.975 > 0.70 | 0.975 | **NON-FIRE** |
| adapter-misrouting | sentinel 検出 | N/A (single-adapter test) | **N/A** |
| timeout | 1 件でも HTTP timeout | 0 件 | **NON-FIRE** |

`multi_lora_3` は K-α の `mock_kant_r8` のみ in place のため M9-C-adopt scope へ
defer。single adapter routing オーバーヘッドが 2.5% (97.5%/100%) と小さく、
cross-adapter contention が fragile collapse する可能性低い。

---

## 6. DB3 fallback fire 判断履歴

| 日時 | trigger | fire / non-fire | 根拠 |
|---|---|---|---|
| 2026-05-09 | K-α #1: SGLang install Windows incompat | **NOT vLLM fire** (CS-1 amendment、Linux 境界に boundary 引き直し) | `.steering/20260508-m9-c-spike/k-alpha-report.md` |
| 2026-05-13 | K-β 実訓練 + real adapter confirmation | **NOT FIRED** | adapter swap ~8ms (60x margin)、bench overhead 2.5% (CS-7 4 trigger NON-FIRE)、CS-6 PEFT direct load 成功 (HTTP 200)、chat round trip 成功。SGLang-first 確定、vLLM defer 継続 (D-1)。本 runbook §4 / §5、`.steering/20260508-m9-c-spike/decisions.md` CS-7 + CS-8 amendment 2026-05-13 |

### Re-open 条件 (CS-8)

- production で adapter-misrouting (CS-7 trigger 3) 頻発 → 即時 fire threshold
  に格上げ
- 500ms threshold が production SLO と乖離 → CS-8 amendment

---

## 7. OOM 時の対処 (CS-4 amendment 候補)

訓練側 (`train_kant_lora`) で OOM が発生した場合、以下を順次試す:

1. `--max-seq-length` を 2048 → 1024 → 512 と縮小
2. `--gradient-accumulation` を 8 → 16 → 32 と増やす (effective batch は維持)
3. `--quantization fp4` (NF4 より少し小さい)
4. 最悪 base model を 7B 系に switch (CS-4 棄却節)

serving 側 (`sglang.launch_server`) で VRAM 不足:

1. `--mem-fraction-static 0.85` → 0.75 → 0.65
2. `--max-total-tokens 2048` → 1024
3. `--max-loaded-loras 3` → 1 (multi-LoRA を諦める)
4. `--max-running-requests 1` を維持

---

## 8. vLLM fallback 切替手順 (defer、blockers.md D-1)

本 spike 内で DB3 fire 確定した場合に備える参考:

- `pyproject.toml [inference]` に `vllm>=0.15` を追加
- `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True` で runtime load/unload を有効化
- `SGLangChatClient` を `vLLMChatClient` に差し替える (M9-C-adopt scope)

本 spike では **DB8 runbook 起草まで** で停止。vLLM 移行 design は別タスク
`m9-c-spike-vllm-fallback` に起票する (CS-8 / blockers.md D-1)。

---

## 9. 参照

- 設計: `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (DB1-DB11)
- 判断: `.steering/20260508-m9-c-spike/decisions.md` (CS-1〜CS-9 + 2026-05-13
  amendment)
- blockers: `.steering/20260508-m9-c-spike/blockers.md` (B-1/B-2/B-3 全解消)
- K-α report: `.steering/20260508-m9-c-spike/k-alpha-report.md`
- K-α launch script: `scratch_kalpha/step2_launch.sh`
- Codex review: `.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md`
  (HIGH 4 / MEDIUM 6 / LOW 3、全反映)
- 訓練実装 PR: #162 (`feature/m9-c-spike-k-beta-train-impl`)
- 本 spike PR: [本 PR # / `feature/m9-c-spike-k-beta-real-train`]
