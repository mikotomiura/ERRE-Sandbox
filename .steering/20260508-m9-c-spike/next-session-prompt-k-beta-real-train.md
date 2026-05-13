# Next-session handoff prompt — M9-C-spike Phase K-β real train run (G-GEAR、WSL2)

**作成**: 2026-05-13 (Phase K-β 実装 PR 起票直後)
**前提**: B-1 (PR-A merged) + B-2 (PR #160 30 cell golden baseline) + 実装 PR
(`feature/m9-c-spike-k-beta-train-impl`) merge 済
**用途**: 新セッション (G-GEAR、Auto mode、Opus、overnight ~6-8h) の最初の prompt
**本セッションは初の実 Kant LoRA adapter 生成 + SGLang real load + bench + DB3 fire 最終判断**

---

```
M9-C-spike Phase K-β 実訓練 run を kick する。実装 PR
(feature/m9-c-spike-k-beta-train-impl) で train_kant_lora の inner loop +
argparse CLI が ready、dry-run でも real golden data 5022 examples で gate
通過確認済。本セッションは GPU 実走で初の本物 Kant rank=8 LoRA adapter 生成
→ SGLang load → adapter swap latency + bench + DB3 fallback 最終判断。

## 直近完了状態 (2026-05-13 時点)

- PR #160 merged (Phase B+C 30 cell golden baseline)
- PR #161 merged (.gitattributes LF 強制)
- 実装 PR merged: train_kant_lora inner loop + argparse CLI (`feature/
  m9-c-spike-k-beta-train-impl`、HEAD は実装 PR merge コミット)
- M9-C-spike B-1 / B-2 解消済
- B-3 (WSL2 training venv 未構築) は本セッション S-1 で解消する

## S-0: 前提確認 (BLOCKING、~10 min)

### S-0.1: HEAD + 実装到達確認

```bash
git checkout main && git pull origin main
git log -1 --oneline                                   # 実装 PR merge を期待
PYTHONUTF8=1 uv run python -m erre_sandbox.training.train_kant_lora \
  --duckdb-glob "data/eval/golden/kant_*.duckdb" \
  --output-dir checkpoints/kant_r8_real \
  --dry-run -v 2>&1 | tail -3
# 期待: rc=0、{"realised_examples": 5022, ..., "training_executed": false}
```

### S-0.2: WSL2 stack 現状

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  python -c 'import sglang; print(\"sglang\", sglang.__version__)' &&
  python -c 'import torch; print(\"torch\", torch.__version__,
                                  \"cuda\", torch.cuda.is_available())' &&
  python -c 'import transformers; print(\"transformers\", transformers.__version__)' &&
  for mod in peft bitsandbytes accelerate datasets; do
    python -c \"import \$mod; print('\$mod', \$mod.__version__)\" 2>&1 | head -1
  done
"
# 期待: sglang 0.5.10.post1 / torch cu128 + cuda=True / transformers 5.3.0
# 期待 (B-3 未解消なら): peft / bitsandbytes / accelerate は ImportError
```

## S-1: WSL2 training venv 構築 (B-3 解消、~30 min)

**選択肢** (decisions.md CS-3 amendment 2026-05-13 / blockers.md B-3 参照):

### 推奨: A 案 — 既存 SGLang venv に追加 install

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  pip install 'peft>=0.19,<1' 'bitsandbytes>=0.49,<1' 'accelerate>=1,<2' 'datasets>=3,<4'
"
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  python -c '
import peft, bitsandbytes, accelerate, datasets, torch, transformers, sglang
print(\"peft\", peft.__version__)
print(\"bnb\", bitsandbytes.__version__)
print(\"accel\", accelerate.__version__)
print(\"datasets\", datasets.__version__)
print(\"transformers\", transformers.__version__)
print(\"sglang\", sglang.__version__)
print(\"torch cuda\", torch.cuda.is_available())
'
"
# A 案 fail (transformers 5.x 衝突など) → B 案 (別 venv) へ
```

### B 案 — 別 venv (`/root/erre-sandbox/.venv-training`)

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox &&
  python -m venv .venv-training &&
  source .venv-training/bin/activate &&
  pip install --upgrade pip &&
  pip install torch --index-url https://download.pytorch.org/whl/cu128 &&
  pip install 'transformers>=4.45,<5' 'peft>=0.13,<1' 'bitsandbytes>=0.43,<1' \
              'accelerate>=0.30,<2' 'datasets>=3,<4'
"
# 訓練終了後は SGLang serving 時に元 .venv に戻す
```

**判断記録**: blockers.md B-3 解消メモに採用案 + 理由 + 実 install version を verbatim 記録

## S-2: feature branch + S-2 gate 再確認 (~5 min)

```bash
git checkout -b feature/m9-c-spike-k-beta-real-train
# 既存 .steering/20260508-m9-c-spike/ を踏襲、K-β real-train 用 sub-folder は不要
```

dry-run を WSL2 venv 経由で再走 (Linux path + cu128 環境での確認):

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  cd /mnt/c/ERRE-Sand_Box &&
  PYTHONUTF8=1 python -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob 'data/eval/golden/kant_*.duckdb' \
    --output-dir checkpoints/kant_r8_real \
    --dry-run -v 2>&1 | tail -3
"
# 期待: rc=0、realised_examples=5022
```

## S-3: Kant rank=8 QLoRA NF4 train run (WSL2、~2-4h、CS-4 config)

### S-3.1: 訓練 kick (CS-4 defaults: batch=1, grad_accum=8, seq=2048)

```bash
mkdir -p .steering/20260508-m9-c-spike/k-beta-logs
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  cd /mnt/c/ERRE-Sand_Box &&
  PYTHONUTF8=1 python -m erre_sandbox.training.train_kant_lora \
    --persona kant \
    --duckdb-glob 'data/eval/golden/kant_*.duckdb' \
    --output-dir checkpoints/kant_r8_real \
    --rank 8 \
    --quantization nf4 \
    --batch-size 1 \
    --gradient-accumulation 8 \
    --max-seq-length 2048 \
    --max-steps 2000 \
    --learning-rate 2e-4 \
    --save-steps 500 \
    --min-examples 1000 \
    --seed 42 \
    -v \
    2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs/train.log
"
# Claude Code から起動するなら run_in_background=true、Monitor で loss/step/OOM grep
```

### S-3.2: VRAM peak watch (CS-4 amendment 用)

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total \
    --format=csv,noheader -l 30
" > .steering/20260508-m9-c-spike/k-beta-logs/vram.csv &
# 訓練終了後に peak を確認、CS-4 amendment に記録
```

### S-3.3: checkpoint 確認

```bash
ls -la checkpoints/kant_r8_real/
# 期待: adapter_config.json + adapter_model.safetensors (rank=8 で ~20-40 MB)
#       + train_metadata.json (本 PR で追加した audit trail)
cat checkpoints/kant_r8_real/train_metadata.json | jq .train_loss .peak_vram_bytes .realised_examples
```

## S-4: SGLang real adapter load + chat round trip (~20 min)

```bash
# step2_launch.sh の改変。K-α の launch v5 invocation を踏襲
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  python -m sglang.launch_server \
    --model-path qwen3-8b \
    --quantization fp8 \
    --enable-lora \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --disable-cuda-graph \
    --max-running-requests 1 \
    --port 30000 \
    2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs/sglang.log
" &
sleep 30
curl -s -X POST http://localhost:30000/load_lora_adapter \
  -H "Content-Type: application/json" \
  -d '{"lora_name": "kant_r8_real", "lora_path": "/mnt/c/ERRE-Sand_Box/checkpoints/kant_r8_real"}' | jq
# 期待: success=true
curl -s -X POST http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "kant_r8_real", "messages": [{"role":"user","content":"純粋理性と実践理性の関係を、あなた自身の語り口で簡潔に。"}], "max_tokens": 300}' | jq
# 期待: mock との style 差 (Kant 文体強化) 確認
```

## S-5 / S-6 / S-7: latency 5 condition / bench_serving / DB3 判断

前回 prompt (`next-session-prompt-k-beta-real-lora.md`) §S-5 / S-6 / S-7 を **そのまま**
踏襲 (本 PR は S-3 を kick できる状態にするまでが scope)。

## S-8: m9-c-adapter-swap-runbook.md 起草 (~30 min)

`docs/runbooks/m9-c-adapter-swap-runbook.md` を起草 (M9-B DB8 完了):
- SGLang launch SOP (CS-1 launch args)
- PEFT directory 構造と `/load_lora_adapter` payload 例 (CS-6)
- 5 condition latency 実測値 (CS-8 amendment)
- N=3 throughput 実測値 (CS-7 amendment)
- DB3 fallback fire 判断履歴

## S-9: 中間 commit + push + PR 起票

```bash
git add checkpoints/kant_r8_real/  # adapter_config.json + adapter_model.safetensors
# 大きい場合は .gitignore + md5 receipt
git add .steering/20260508-m9-c-spike/k-beta-logs/
git add .steering/20260508-m9-c-spike/decisions.md
git add .steering/20260508-m9-c-spike/tasklist.md
git add .steering/20260508-m9-c-spike/blockers.md
git add data/eval/spike/m9-c-spike-bench/  # bench JSONL
git add docs/runbooks/m9-c-adapter-swap-runbook.md

git commit -m "$(cat <<'EOF'
feat(training): m9-c-spike — Phase K-β real Kant LoRA training 完遂

- Kant rank=8 PEFT QLoRA NF4 train (M steps、N hours wall on G-GEAR WSL2)
- real adapter export: checkpoints/kant_r8_real/
- SGLang /load_lora_adapter で real load OK、chat round trip で Kant 文体確認
- adapter swap latency 5 condition 実測 (CS-8): [verbatim]
- bench_serving N=3 throughput (CS-7): [verbatim]
- CS-7 4 trigger 全不発 / fire 状況: [判断結果]
- DB3 vLLM fallback 判断: [SGLang-first 確定 or fire]
- B-3 解消 (WSL2 training venv 構築方式 verbatim 記録)

Refs:
- .steering/20260508-m9-c-spike/decisions.md (CS-1〜CS-9 + amendments)
- .steering/20260508-m9-c-spike/blockers.md (B-1/B-2/B-3 全解消)
- .steering/20260430-m9-b-lora-execution-plan/design-final.md (DB1-DB10)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push -u origin feature/m9-c-spike-k-beta-real-train
gh pr create --base main --title "feat(training): m9-c-spike — Phase K-β real Kant LoRA training 完遂" --body "..."
```

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止 (peft / transformers / bitsandbytes は OK)
- WSL2 で訓練、Windows native で SGLang は NG (K-α #1 で fire 済)
- 訓練中は GPU 占有 → 並列で Ollama / 別タスクを kick しない
- adapter 本体 (~20-40 MB) は `.gitignore` 戦略次第、md5 receipt 化を考慮
- Codex independent review (gpt-5.5 xhigh) を本 PR merge 前に挟む (CS-N amendment は judgment 案件)

## 完了条件 (本セッション)

### S-0/S-1 pre + venv
- [ ] HEAD = 実装 PR merge 以降、dry-run rc=0
- [ ] B-3 解消 (peft/bitsandbytes/accelerate import OK on WSL2 + cuda available)

### S-3 train
- [ ] checkpoints/kant_r8_real/adapter_config.json + adapter_model.safetensors +
  train_metadata.json 生成
- [ ] k-beta-logs/train.log に train_loss 降下 + epoch 完了 marker
- [ ] peak VRAM <= 12GB (CS-4 amendment 条件)、超過なら batch / accum / seq 再調整

### S-4 SGLang real load
- [ ] /load_lora_adapter success=true
- [ ] chat round trip で Kant 文体 (mock との差別化確認)

### S-5/S-6 measurements
- [ ] adapter swap latency 5 condition 実測値 (CS-8)
- [ ] bench_serving N=3 throughput (CS-7、3 baseline)
- [ ] CS-7 4 trigger 判定

### S-7/S-8/S-9 closure
- [ ] DB3 fallback 最終判断 verbatim
- [ ] m9-c-adapter-swap-runbook.md 起草
- [ ] PR 起票、Mac master review 待ち

## 参照

- 設計: `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (DB1-DB10)
- 判断: `.steering/20260508-m9-c-spike/decisions.md` (CS-1〜CS-9 + 2026-05-13 amendment)
- blockers: `.steering/20260508-m9-c-spike/blockers.md` (B-1/B-2/B-3 状況)
- 実装 PR: feature/m9-c-spike-k-beta-train-impl (本 prompt 起草の前提となる PR)
- 旧 prompt: `.steering/20260508-m9-c-spike/next-session-prompt-k-beta-real-lora.md`
  (前提崩れにより本 prompt で置換、scope を S-3 実走 + S-9 PR に絞った)
- K-α launch invocation: `scratch_kalpha/step2_launch.sh` (SGLang v5)
- Codex review: `.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md`

まず S-0 (HEAD + dry-run) → S-1 (B-3 解消) → S-2 (branch + WSL2 dry-run) を確実に通し、
S-3 で実訓練 kick (run_in_background でも foreground でも可)。
```
