# G-GEAR collection runbook — Plan B de-focused monolog

> **scope**: 本 PR merge 後の retrain session で実行する collection
> workflow。本 file は instruction only、実行は本 PR scope 外。

## 1. 環境前提

- **実行マシン**: G-GEAR (Windows 11、RTX 3060 Ti、VRAM 16 GB)
- **SGLang 実行**: WSL2 Linux 上の `/root/erre-sandbox/.venv` (Phase B
  判断 9、native CUDA + larger context にためここを使用)
- **driver 実行**: **Windows native** の `.venv`、`PYTHONUTF8=1`
  必須 (Phase B 判断 8、`reference_wsl2_ollama_unreachable.md` の
  通り WSL2 から Windows native Ollama / Ollama-on-loopback は不通、
  逆方向 = Windows → WSL2 上 SGLang の 0.0.0.0:30000 は到達可)
- **memory**: 8GB-RAM driver process + 14GB-VRAM SGLang server で共存可
- **Python**: 3.11 系 (`uv sync --frozen` 済)

## 2. SGLang server 起動 (WSL2 内、base model のみ、LoRA 不要)

```bash
# WSL2 Ubuntu terminal
cd /root/erre-sandbox
source .venv/bin/activate
PYTHONUTF8=1 python -m sglang.launch_server \
    --model-path Qwen/Qwen3-8B \
    --host 0.0.0.0 \
    --port 30000 \
    --mem-fraction-static 0.85 \
    --chunked-prefill-size 8192 \
    --max-running-requests 8 \
    --disable-cuda-graph
```

**LoRA adapter 不要**: Plan B 採取は **base model** から de-monolog を
生成する (LoRA-on は v2 で既に corpus を歪めているので、新規 corpus
shape を作るには no-LoRA base が正解)。`tier_b_pilot.py` の
`--no-lora-control` mode を流用、`--rank 0`。

`http://<G-GEAR-LAN-IP>:30000/v1/models` で base model 応答確認。

## 3. driver smoke / dry-run (Windows native、~30 min)

```powershell
# Windows PowerShell (G-GEAR)
cd C:\ERRE-Sand_Box
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
python scripts\m9-c-adopt\de_focused_monolog_collector.py `
    --persona kant `
    --target-net 50 `
    --max-attempts 200 `
    --sglang-host http://<WSL2-IP>:30000 `
    --output data\eval\m9-c-adopt-plan-b\smoke\kant_de_monolog_smoke.duckdb `
    --dry-run
```

- `--dry-run`: shard を `_smoke/` 直下に書き出し、`pilot_state` を保存
  しない (resume なし)
- **acceptance rate を測定** (採取 50 attempt の中で post-hoc filter
  pass 率)。
- 期待 acceptance rate: 30-40%。< 25% なら persona prompt augmentation
  を強化 (Critique 原文短文を system に paste) して再 dry-run。

## 4. main collection run (~3h、acceptance rate 31% 想定)

```powershell
# Windows PowerShell
$env:PYTHONUTF8 = "1"
python scripts\m9-c-adopt\de_focused_monolog_collector.py `
    --persona kant `
    --target-net 250 `
    --max-attempts 800 `
    --temperature 0.7 `
    --frequency-penalty 0.3 `
    --presence-penalty 0.3 `
    --sglang-host http://<WSL2-IP>:30000 `
    --output data\eval\m9-c-adopt-plan-b\kant_de_monolog_run0.duckdb
```

- 250 net 到達で自動停止 (target_net 引数で driver が逐次 count、
  post-hoc filter で reject された row は subtract)
- max_attempts=800 hit したが 250 未達 → ロールバック (driver は exit 2、
  decisions.md DI-α-FAIL として記録)

## 5. shard validation (~30s)

```powershell
python scripts\m9-c-adopt\validate_multiturn_shards.py `
    --persona kant `
    --focal-target 250 `
    --shards-glob "data\eval\m9-c-adopt-plan-b\kant_de_monolog_run*.duckdb" `
    --output .steering\20260517-m9-c-adopt-plan-b-design\validation-plan-b-shards.json
```

- turn_index=0 のみで構成されるので Check 1 (alternation) は trivial
  pass、Check 2 (focal count ±5%) と Check 3 (incomplete dialog) が
  meaningful
- Plan B shard は dialog 1-row なので Check 3 (turn_index gap) も trivial
  pass

## 6. pre-training audit (Plan B corpus gate) (~10s)

採取完了後、retrain 起動の **直前** に audit を走らせて gate を pre-check。
本 audit script は train_kant_lora の `--plan-b-gate` flag によって
training kickoff 時にも自動で呼ばれるが、事前に走らせて gate fail を
早期検出するのが安全。

```powershell
# まず weight-audit.json を取得 (train_kant_lora --dry-run --weighted で生成)
python -m erre_sandbox.training.train_kant_lora `
    --duckdb-glob "data\eval\golden\kant_*.duckdb data\eval\m9-c-adopt-plan-b\kant_de_monolog_run*.duckdb" `
    --output-dir data\lora\m9-c-adopt-v2\kant_r8_v3 `
    --rank 8 --max-steps 4000 --weighted --dry-run -v

# 次に audit script で gate check
python scripts\m9-c-adopt\audit_plan_b_corpus_stats.py `
    --weight-audit data\lora\m9-c-adopt-v2\kant_r8_v3\weight-audit.json `
    --merge-sha (git rev-parse HEAD) `
    --output data\lora\m9-c-adopt-v2\kant_r8_v3\plan-b-corpus-gate.json
```

- exit code 0: gate pass、retrain 起動
- exit code 8: gate fail (`PlanBCorpusGateError`)、retrain skip、
  `decisions.md` DI-α-FAIL として記録、ADR D-15 re-evaluate

## 7. shard naming + manifest convention

- **shard**: `data/eval/m9-c-adopt-plan-b/kant_de_monolog_run<N>.duckdb`
  - run<N>: 0-based、複数 run 時は run0 / run1 / ... と increment
  - SHA は manifest.json 側で管理 (filename には embedded しない)
- **manifest** (`data/eval/m9-c-adopt-plan-b/kant_de_monolog_run0_manifest.json`):
  ```json
  {
    "schema_version": 1,
    "shard": "kant_de_monolog_run0.duckdb",
    "persona": "kant",
    "collection_mode": "de_focused_monolog",
    "base_model": "Qwen/Qwen3-8B",
    "sglang_version": "<runtime detected>",
    "merge_sha": "<本 PR merge SHA>",
    "captured_at_utc": "...",
    "target_net": 250,
    "max_attempts": 800,
    "achieved_net": ...,
    "acceptance_rate": ...,
    "stimulus_subset_ids": [...],
    "sampling_params": {
      "temperature": 0.7,
      "frequency_penalty": 0.3,
      "presence_penalty": 0.3,
      "max_tokens": 320
    },
    "filter_thresholds": {
      "min_token_count": 60,
      "min_marker_density": 1.0,
      "trigram_loop_max": 4
    }
  }
  ```

## 8. retrain kickoff (~20h G-GEAR overnight)

```powershell
# WSL2 GPU 経由が必要 (Phase B 判断 9)、Windows native では torch+cpu のみ
wsl -d Ubuntu -e bash -c "
cd /root/erre-sandbox &&
source .venv/bin/activate &&
PYTHONPATH=/mnt/c/ERRE-Sand_Box/src \
PYTHONUTF8=1 \
python -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb /mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-plan-b/kant_de_monolog_run*.duckdb' \
    --output-dir /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3 \
    --rank 8 \
    --max-steps 2500 \
    --eval-steps 250 \
    --weighted \
    --plan-b-gate \
    --lang-stratified-split \
    -v 2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260517-m9-c-adopt-plan-b-design/retrain-stdout.log
"
```

- `--plan-b-gate`: hard gate 4 axes (n_eff / top_5 / de_en / de) +
  EarlyStoppingCallback patience=2 min_delta=0.005 を attach
- `--lang-stratified-split`: stratify_by_language=True で eval split に
  de-monolog を 10% 含める

## 9. abort / abnormal termination 処理

- `PlanBCorpusGateError` (exit 8): `plan-b-corpus-gate.json` の
  `failed_axes` を確認、driver の再採取 (target_net 増、persona prompt
  augmentation 強化) か Phase E A-6 migration を decisions.md に記録
- early stopping fire (eval_loss 上昇 ≥3 step): best checkpoint
  (`checkpoint-XXXX`) を kant_r8_v3 root に再配置、verdict 計算は
  best checkpoint で実行
- SGLang server crash: collection は resume 可 (driver の `pilot_state`
  table)、retrain は中断 checkpoint から resume 可 (HF Trainer 標準)

## 10. 次セッション開始時 file pointers

- `.steering/20260517-m9-c-adopt-plan-b-design/design.md` §7 (handoff)
- `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-6
  (lexical-5gram 実装は next-session scope)
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
  (verdict 計算時の encoder pin)
- 本 runbook
