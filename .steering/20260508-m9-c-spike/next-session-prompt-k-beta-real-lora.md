# Next-session handoff prompt — M9-C-spike Phase K-β real Kant LoRA training (G-GEAR、WSL2)

**作成**: 2026-05-13 (PR #160 merged、Phase B+C 30 cell golden baseline 確定直後)
**前提**: B-1 (PR-A merged) + B-2 (Phase B+C 30 cell golden baseline 完成、PR #160) 両 trigger 解消済
**用途**: 新セッション (G-GEAR、Auto mode、Opus、overnight) の最初の prompt として貼り付け
**本セッションは Phase K-β 実訓練 (Kant rank=8 QLoRA NF4) を kick して real adapter 生成 + SGLang real load + bench を完遂する**

---

```
M9-C-spike Phase K-β (real Kant LoRA training) を kick する。K-α (mock infrastructure proof、PR #154/#155 merged)
は完了済、WSL2 + SGLang stack + src/erre_sandbox/training/ + mock_kant_r8 すべて in place。
本セッションは初の **本物の LoRA adapter 生成 + SGLang real load + adapter swap latency + bench**。

## 直近完了状態 (2026-05-13 時点)

- PR #160 merged (Phase B+C 30 cell golden baseline、`feature/m9-eval-phase-b-stimulus-baseline` → main)
- PR #161 merged (.gitattributes LF 強制、codex_issue #6)
- main HEAD = c6d8b85
- M9-C-spike B-1 (m9-individual-layer-schema-add PR-A) 解消済
- M9-C-spike B-2 (M9-eval P3 golden baseline 採取完了) 解消済 ← 本日 PR #160 で
- K-α infrastructure 完了 (mock_kant_r8 adapter / WSL2 sglang 0.5.10.post1 / launch v5 invocation 確定)

## S-0: 前提確認 + 訓練データソース判定 (BLOCKING、~20 min)

### S-0.1: HEAD と repo 状態

```bash
git checkout main && git pull origin main
git log -1 --oneline                      # 期待: c6d8b85 (PR #161) 以降
git status --short                        # working tree clean を期待
git branch -a | grep -i "k-beta\|m9-c-spike-k-beta"   # K-β branch 既存? 期待: empty
```

### S-0.2: 訓練データソース判定 (CRITICAL、未解決設計事項)

**問題**: `train_kant_lora.py` は `connect_training_view(db_path)` 経由で
`epoch_phase != "evaluation" AND individual_layer_enabled = FALSE` 行のみ採用する。
Phase B+C 30 cell golden cells が `epoch_phase=evaluation` なら **訓練に使えない** (CS-3 hard-fail)。

**確認手順**:

```bash
# (a) data/eval/golden/kant_*.duckdb の epoch_phase 分布を確認
PYTHONUTF8=1 uv run python -c "
import duckdb, glob
for p in sorted(glob.glob('data/eval/golden/kant_*.duckdb')):
    con = duckdb.connect(p, read_only=True)
    rows = con.execute(\"SELECT epoch_phase, COUNT(*) FROM raw_dialog.dialog GROUP BY epoch_phase\").fetchall()
    print(p, rows)
    con.close()
"
# (b) connect_training_view 経由で kant_*.duckdb を 1 件 mount し、行数を確認
PYTHONUTF8=1 uv run python -c "
from erre_sandbox.evidence.eval_store import connect_training_view
r = connect_training_view('data/eval/golden/kant_natural_run0.duckdb')
print('rows after training-view filter:', sum(1 for _ in r.iter_rows()))
r.close()
"
# (c) base training corpus (Phase B+C 以外) の存在確認
ls -la data/training/raw_dialog/ 2>/dev/null || echo "(no data/training/raw_dialog/)"
ls -la data/training/ 2>/dev/null || echo "(no data/training/)"
find data -name "*.duckdb" -not -path "*/eval/*" 2>/dev/null
```

**判定**:
- **Case A**: Phase B+C cells の一部が `epoch_phase=base` (非 evaluation) → そのまま訓練可
- **Case B**: 全 Phase B+C cells が `epoch_phase=evaluation` のみ → 別 source の base corpus が必要
  - `.steering/20260430-m9-b-lora-execution-plan/design-final.md` §E (DB5 Raw training table) を
    再確認、base corpus の生成プロセスがどこかに defer されていれば本 prompt 中断 + 再 plan
- **Case C**: base corpus 不在 + Phase B+C も使えない → user に報告、訓練データ生成タスクを先行

**Case B/C で停止する場合**: 本セッションを scaffold + plan のみで終了、blockers.md に新規 B-3
「base training corpus 不在」を起票し、後続セッションで data 生成を kick。

### S-0.3: WSL2 stack 再確認 (K-α PR #154/#155 で構築済)

```bash
# Windows-side check
ls -la checkpoints/mock_kant_r8/ 2>/dev/null  # mock adapter 残存確認
cat scratch_kalpha/step2_launch.sh 2>/dev/null | head -n 20

# WSL2-side check (G-GEAR WSL2 Ubuntu)
wsl -d Ubuntu-22.04 -- bash -c "ls -la /root/erre-sandbox/checkpoints/"
wsl -d Ubuntu-22.04 -- bash -c "source /root/erre-sandbox/.venv/bin/activate && python -c 'import sglang; print(sglang.__version__)'"
# 期待: 0.5.10.post1
```

## S-1: feature branch + scaffold (~5 min)

```bash
git checkout -b feature/m9-c-spike-k-beta-real-kant-lora
# 既存 .steering/20260508-m9-c-spike/ を踏襲、K-β 用 sub-folder は不要
```

## S-2: `assert_phase_beta_ready()` gate 通過確認 (~10 min、CS-3 hard-fail clear)

```bash
# 4 種 hard-fail check (CS-3): epoch_phase=evaluation / individual_layer_enabled=true /
# allow-list lockstep / min_examples
PYTHONUTF8=1 uv run pytest tests/test_training/ -v -k "phase_beta_ready or contamination" 2>&1 | tail -n 30
# 期待: 全 PASS (PR-A merge 後の現行コードで)
```

train CLI で gate を実走:

```bash
PYTHONUTF8=1 uv run python -m erre_sandbox.training.train_kant_lora \
  --dry-run \
  --duckdb-glob "data/eval/golden/kant_*.duckdb" \
  --persona kant 2>&1 | tail -n 20
# 期待: gate PASS、min_examples >= threshold (Phase B+C kant cells で ~7500 rows 想定、CS-3 default 充足)
# 失敗時は S-0.2 Case B/C 経路へ
```

## S-3: Kant rank=8 QLoRA NF4 train run (WSL2、~2-4h、CS-4 config)

### S-3.1: 訓練 kick (WSL2 で実行、PYTHONUTF8 不要)

```bash
# Windows shell から WSL2 経由で起動 (or 直接 WSL2 shell に入る)
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox &&
  source .venv/bin/activate &&
  cd /mnt/c/ERRE-Sand_Box &&
  python -m erre_sandbox.training.train_kant_lora \
    --persona kant \
    --duckdb-glob 'data/eval/golden/kant_*.duckdb' \
    --output-dir checkpoints/kant_r8_real \
    --rank 8 \
    --quantization nf4 \
    --max-steps 2000 \
    --learning-rate 2e-4 \
    --batch-size 4 \
    --gradient-accumulation 4 \
    --save-steps 500 \
    2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-train-log.txt
"
```

実装側で CLI 引数が異なる場合は `--help` で実引数を確認:

```bash
wsl -d Ubuntu-22.04 -- bash -c "
  cd /root/erre-sandbox && source .venv/bin/activate &&
  cd /mnt/c/ERRE-Sand_Box &&
  python -m erre_sandbox.training.train_kant_lora --help
"
```

### S-3.2: 進捗 watch (bg + Monitor)

`run_in_background=true` で kick した場合は Monitor で loss / step / OOM / Traceback を grep:

```bash
tail -F .steering/20260508-m9-c-spike/k-beta-train-log.txt 2>&1 | \
  grep -E --line-buffered "step.*loss=|train_loss|epoch=|saving|OOM|Traceback|CUDA out of memory|Killed|FATAL"
```

### S-3.3: VRAM 監視 (CS-4 amendment、PEFT QLoRA NF4 で 16GB 内に収まる想定)

```bash
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader -l 60 > /tmp/k-beta-vram.csv &
# 訓練終了後に peak VRAM を確認、CS-4 に amendment 記録
```

### S-3.4: checkpoint export 確認

```bash
ls -la checkpoints/kant_r8_real/
# 期待: adapter_config.json + adapter_model.safetensors + tokenizer.json (or 同等)
# adapter_model.safetensors サイズ確認 (rank=8 で ~20-40 MB 想定)
```

## S-4: SGLang real adapter load + chat round trip (~20 min)

### S-4.1: SGLang 再起動 (launch v5、real Kant adapter pinned で)

```bash
# K-α の step2_launch.sh を改変
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
    2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-sglang-log.txt
" &
sleep 30
```

### S-4.2: real Kant adapter を /load_lora_adapter で load

```bash
curl -s -X POST http://localhost:30000/load_lora_adapter \
  -H "Content-Type: application/json" \
  -d '{"lora_name": "kant_r8_real", "lora_path": "/mnt/c/ERRE-Sand_Box/checkpoints/kant_r8_real"}' | jq
# 期待: success=true、load latency 記録
```

### S-4.3: Kant identity chat round trip (mock との style 差を確認)

```bash
curl -s -X POST http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "kant_r8_real", "messages": [{"role":"user","content":"純粋理性と実践理性の関係を、あなた自身の語り口で簡潔に。"}], "max_tokens": 300}' | jq
# 期待: mock_kant_r8 (= base model 同等) と異なる、Kant の文体を強く帯びた応答
```

## S-5: adapter swap latency 5 condition 実測 (CS-8、~30 min)

```bash
# 5 conditions: cold load / warm reload / pinned / unpinned / no-LoRA baseline
# 詳細手順は m9-c-spike/decisions.md CS-8 参照
# 各 condition で curl で /load_lora_adapter / /unload_lora_adapter / chat completion latency を実測
# 結果を data/eval/spike/m9-c-spike-bench/k-beta-swap-latency.jsonl に保存
```

## S-6: SGLang `bench_serving` N=3 throughput 実測 (CS-7、~45 min)

```bash
# 3 baseline: no-LoRA / single-LoRA (kant_r8_real) / N=3 multi-LoRA (kant + nietzsche + rikyu の mock)
# CS-7 4 trigger 確認: p95 e2e > 2x / output tok/s < 70% / adapter-misrouting / timeout
# 結果を data/eval/spike/m9-c-spike-bench/k-beta-bench-serving.jsonl に保存
```

## S-7: DB3 fallback fire 最終判断 (CS-8、~15 min)

real adapter 経由で K-α #1 retract が永続的か再評価:
- CS-7 4 trigger のいずれかが fire → DB3 vLLM fallback 再起動
- 全 trigger 不発 → SGLang-first 確定、vLLM defer (D-1 blocker 維持)

決定を `decisions.md` の CS-8 セクションに verbatim 追記。

## S-8: runbook 起草 (~30 min)

```bash
# docs/runbooks/m9-c-adapter-swap-runbook.md を起草 (M9-B DB8 完了)
# 内容: SGLang launch / adapter load/unload / OOM 対処 / vLLM fallback 切替手順
```

## S-9: 中間 commit + push + PR 起票

```bash
git add checkpoints/kant_r8_real/  # adapter_config.json + adapter_model.safetensors (.gitignore 対象なら別 receipt 戦略)
# 大きい場合は md5 receipt のみ commit
git add .steering/20260508-m9-c-spike/k-beta-train-log.txt
git add .steering/20260508-m9-c-spike/k-beta-sglang-log.txt
git add .steering/20260508-m9-c-spike/decisions.md   # CS-N amendment
git add .steering/20260508-m9-c-spike/tasklist.md    # K-β rows [x] 化
git add data/eval/spike/m9-c-spike-bench/k-beta-*.jsonl
git add docs/runbooks/m9-c-adapter-swap-runbook.md

git commit -m "$(cat <<'EOF'
feat(training): m9-c-spike — Phase K-β real Kant LoRA training 完遂

- Kant rank=8 PEFT QLoRA NF4 train (M steps, N hours wall on G-GEAR WSL2)
- real adapter export: checkpoints/kant_r8_real/
- SGLang /load_lora_adapter で real load OK、chat round trip で Kant 文体確認
- adapter swap latency 5 condition 実測 (CS-8): [実測値を verbatim]
- bench_serving N=3 throughput (CS-7): [実測値を verbatim]
- CS-7 4 trigger 全不発 / fire 状況: [判断結果]
- DB3 vLLM fallback 判断: [SGLang-first 確定 or fire]

Refs:
- .steering/20260508-m9-c-spike/decisions.md (CS-1 〜 CS-9 amendment)
- .steering/20260430-m9-b-lora-execution-plan/design-final.md (DB1-DB10)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push -u origin feature/m9-c-spike-k-beta-real-kant-lora
gh pr create --base main --title "feat(training): m9-c-spike — Phase K-β real Kant LoRA training 完遂" --body "..."
```

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止 (peft / transformers / bitsandbytes は OK、bpy は禁止)
- WSL2 で訓練、Windows で SGLang launch は NG (K-α #1 で fire 済)
- 訓練中は GPU 占有 → 並列で Ollama / 別タスクを kick しない
- K-α PR #155 で確定した launch v5 invocation を踏襲 (fp8 / lora-target-modules 4 種 / mem-fraction 0.85)
- adapter 本体 (~20-40 MB) は `.gitignore` 戦略次第、md5 receipt 化を考慮
- Codex independent review (gpt-5.5 xhigh) を本 PR merge 前に挟む (CS-N amendment は judgment 案件)

## 完了条件 (本セッション)

### S-0 pre-check
- [ ] HEAD = c6d8b85 (or 以降)、working tree clean
- [ ] 訓練データソース判定 (Case A/B/C のどれか)
- [ ] WSL2 stack 再確認 OK

### S-2 gate
- [ ] `assert_phase_beta_ready()` 4 種 hard-fail 全 PASS
- [ ] `train_kant_lora --dry-run` PASS、min_examples 充足

### S-3 train
- [ ] checkpoints/kant_r8_real/adapter_config.json + adapter_model.safetensors 生成
- [ ] k-beta-train-log.txt に train_loss 降下 + epoch 完了 marker

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
- 判断: `.steering/20260508-m9-c-spike/decisions.md` (CS-1〜CS-9)
- blockers: `.steering/20260508-m9-c-spike/blockers.md` (B-1/B-2 解消済、S-1/S-2/S-3 spike 内、D-* defer)
- K-α report: `.steering/20260508-m9-c-spike/k-alpha-report.md` (前回 mock infrastructure proof)
- K-α launch invocation: `scratch_kalpha/step2_launch.sh` (SGLang v5)
- Codex review: `.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md` (HIGH 3 / MEDIUM / LOW)

まず S-0 pre-check (HEAD + 訓練データソース判定 + WSL2 stack) を完了させ、Case A なら S-1〜S-9 を順次実行。
Case B/C の場合は user に報告 + 別タスク (base corpus 生成) を起票して本セッションを scaffold + plan のみで切る。
```
