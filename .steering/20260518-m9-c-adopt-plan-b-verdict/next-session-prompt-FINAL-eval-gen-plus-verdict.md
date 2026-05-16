# Next-session 開始プロンプト — Plan B eval generation + verdict 計算

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR (`feature/m9-c-adopt-plan-b-verdict`) で本 prep PR が merged 済
  (retrain artifact forensic JSON が tracked 化、steering 文書化済)
- PR #181 (`feature/m9-c-adopt-plan-b-retrain`、merge SHA `f68ac63`) の
  retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/`) が
  G-GEAR local disk に存在 (best checkpoint = step 1500、
  eval_loss=0.18259、EarlyStoppingCallback fire at step 1750)
- vendi_lexical_5gram.py + `_load_default_kernel(kernel_type='lexical_5gram')`
  dispatch は PR #181 で merged 済 (src/erre_sandbox/evidence/tier_b/vendi.py
  L312-345 で wired)
- corpus gate PASS (n_eff=4355.5 / top_5%=0.125 / de+en=0.601 / de=0.385)
- D-2 allowlist (Plan B): MPNet + E5-large + lexical-5gram primary、
  BGE-M3 exploratory (`.steering/20260517-m9-c-adopt-plan-b-design/
  d2-encoder-allowlist-plan-b.json`)
- G-GEAR (RTX 5060 Ti SM120、16 GB VRAM) + WSL2 Ubuntu の SGLang fp8
  + disable-piecewise-cuda-graph 環境前提 (DR-4)
- **Pre-push CI parity check 必須** (CLAUDE.md 禁止事項)

**branch**: 新規 `feature/m9-c-adopt-plan-b-eval-gen` を **main** から切る
**compute**: SGLang serve + LoRA-on/no-LoRA shard 採取 (~5h GPU overnight) +
4-encoder rescore (~1-2h CPU) + Burrows/ICC/throughput (~30 min) + verdict
aggregator + Codex review = **~7-8h envelope** (1 session 完結は厳しい、
overnight job + 翌日 verdict が現実的)

---

```
m9-c-adopt **Plan B eval generation + verdict 計算** を実行する。
PR `feature/m9-c-adopt-plan-b-verdict` (prep PR) の DV-1 で次 PR へ
分離された scope を実装する。

retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500/`、
eval_loss=0.18259) を SGLang adapter として load し、v2 baseline と
**同 protocol** で stim eval shards を採取、4 encoder × Vendi + Burrows
+ ICC + throughput で verdict を計算、encoder agreement axis (3-of-4、
2 以上要件) で kant ADOPT or Phase E A-6 (rank=16) 移行を判定する。

## 目的 (本セッション、~7-8h、overnight job を含む)

1. **`/start-task`** で `.steering/<YYYYMMDD>-m9-c-adopt-plan-b-eval-gen/`
   を起票 (5 標準 file)
2. **`rescore_vendi_alt_kernel.py` の CLI flag 拡張** (blocker 2 解決):
   - `--v2-shards` / `--nolora-shards` を kw-only flag で追加
   - default は既存 hard-coded path (backward-compat)
   - test 追加 (`tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`)
3. **SGLang server start + Plan B adapter load** (G-GEAR WSL2):
   - K-α launch v5 invocation: `--quantization fp8 --max-total-tokens
     2048 --max-running-requests 1 --disable-cuda-graph
     --disable-piecewise-cuda-graph` + `--lora-paths
     kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/
     checkpoint-1500 --max-loras-per-batch 1 --max-lora-rank 8`
4. **Plan B eval shard 採取** (~5h GPU):
   - LoRA-on run × 2: `tier_b_pilot.py --persona kant --rank 8
     --run-idx {0,1} --turn-count 300 --cycle-count 6 --multi-turn-max 6
     --sglang-host http://127.0.0.1:30000 --output
     data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run{0,1}_stim.duckdb`
   - no-LoRA run × 2: `--no-lora-control --rank 0 --run-idx {0,1}
     --turn-count 300 --cycle-count 6 --multi-turn-max 6 --output
     data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`
   - **stimulus protocol** は v2 baseline と完全に同一 (apples-to-apples)
5. **shard 検証**: `validate_multiturn_shards.py` で alternation + row
   count + multi-turn 整合性を確認
6. **4-encoder rescore** (改修済 rescore_vendi_alt_kernel.py、~1-2h CPU):
   - MPNet (primary): `python scripts/m9-c-adopt/rescore_vendi_alt_kernel.py
     --encoder sentence-transformers/all-mpnet-base-v2
     --v2-shards <Plan B kant_r8v3 run0 run1>
     --nolora-shards <Plan B no-LoRA run0 run1>
     --output .steering/<task>/da14-rescore-mpnet-plan-b-kant.json`
   - E5-large (primary): 同 (encoder swap)
   - lexical-5gram (primary): `--kernel-type lexical_5gram` (新 CLI flag、
     `_load_default_kernel(kernel_type='lexical_5gram')` 経由)
   - BGE-M3 (exploratory): 同 (報告 obligatory だが ADOPT 不寄与)
7. **Burrows / ICC / throughput**:
   - `compute_burrows_delta.py` で Plan B vs no-LoRA Burrows reduction%
   - `compute_big5_icc.py` で ICC(A,1) cross-recompute (kernel-independent)
   - throughput: `da1_matrix_multiturn.py` の throughput axis を Plan B
     shards で再計算
8. **verdict aggregator** (新規 `da14_verdict_plan_b.py` or `da15_verdict.py`
   拡張):
   - encoder agreement axis 評価 (3 primary のうち 2 以上 で natural d
     ≤ -0.5 AND CI upper < 0 AND lang-balanced d ≤ -0.5 AND length-balanced
     d ≤ -0.5 AND 符号一致)
   - Burrows ≥5% point + CI lower > 0、ICC ≥0.55、throughput ≥70%
   - `da14-verdict-plan-b-kant.json` + `da14-verdict-plan-b-kant.md` emit
9. **kant ADOPT or Phase E A-6 判定**:
   - 全 gate pass → **ADOPT**、decisions.md DR-? に記録
   - 1 axis でも fail → **Phase E A-6 migration** (rank=16 spike、別 ADR
     DA-16 候補)、decisions.md に記録
10. **Codex independent review** (~30 min):
    - `.steering/<task>/codex-review-prompt.md` 作成 →
      `cat ... | codex exec --skip-git-repo-check`
    - HIGH/MEDIUM/LOW を `codex-review.md` に verbatim 保存、本 PR scope
      で HIGH 全件反映、MEDIUM は decisions.md で採否、LOW は blockers.md
11. **commit + push 前に必ず `pre-push-check`**:
    - `bash scripts/dev/pre-push-check.sh` (WSL2) or
      `pwsh scripts/dev/pre-push-check.ps1` (Windows)
    - 4 段階 (ruff format --check / ruff check / mypy src / pytest -q)
      全 pass で push 可。1 段でも fail なら push 禁止
      (memory `feedback_pre_push_ci_parity.md` 参照)

## NOT in scope (本セッション)

- nietzsche / rikyu の Plan B 展開 (kant verdict ADOPT 後の別 PR)
- WeightedTrainer Blocker 2 (sample weight collapse) の修正
  (Plan B verdict ADOPT なら保留、REJECT なら別 PR で優先)
- 新規 retrain (kant_r8_v3 checkpoint-1500 を verdict 判定用に使う、
  別 checkpoint や rank=16 spike は本 PR scope 外)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260518-m9-c-adopt-plan-b-verdict/decisions.md` DV-1〜DV-3
2. `.steering/20260518-m9-c-adopt-plan-b-verdict/blockers.md`
   ブロッカー 1 (eval shard 未生成、本 PR で解消) + 2 (rescore script
   hard-coded path、本 PR で改修)
3. `.steering/20260518-m9-c-adopt-plan-b-verdict/design.md` §1.2 の 9 step
4. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1〜DR-7
5. `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 1/2
6. `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
7. `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` (D-2 primary)
8. `src/erre_sandbox/evidence/tier_b/vendi.py` L312-345
   (`_load_default_kernel(kernel_type='lexical_5gram')` dispatch)
9. `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` (改修対象)
10. `scripts/m9-c-adopt/tier_b_pilot.py` (eval generation driver)
11. memory `reference_qwen3_sglang_fp8_required.md` (SGLang DR-4 invocation)
12. memory `feedback_pre_push_ci_parity.md` (push 前 4 段階 check 必須)
13. memory `feedback_retrain_handoff_must_include_eval_gen.md` (本 PR
    reflection の handoff 教訓)
14. `CLAUDE.md` 「禁止事項」(pre-push CI parity + extras-only 3 点セット)

## 留意点 (HIGH 違反防止)

- **DA-14 thresholds 不変**: Vendi d ≤ -0.5 / Burrows ≥5% / ICC ≥0.55 /
  throughput ≥70%。retrain 結果が borderline でも threshold 移動禁止
- **encoder agreement axis 不可侵**: 3 primary の 2 以上要件 (Plan B
  design V2 §5.3)
- **D-2 allowlist の encoder revision pin**: PR #179 で固定された
  revision_sha をそのまま使う (allowlist JSON の `revision_sha` 参照)
- **Plan B corpus gate は train-time check が PASS 済**: verdict 計算側で
  retroactive に threshold を動かさない
- **stim protocol は v2 baseline と apples-to-apples**: `tier_b_pilot.py`
  の引数 (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`) を
  v2 baseline 生成時 (PR #160 era) と同一にする
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)
- **best checkpoint は step 1500** (`checkpoint-1500/`)。step 1750 (eval_loss
  0.1813) checkpoint は disk に保存されていない (save_steps=500 で skip)

## 完了条件

- [ ] `feature/m9-c-adopt-plan-b-eval-gen` branch (main 派生)
- [ ] `.steering/<task>/` 5 標準 file
- [ ] `rescore_vendi_alt_kernel.py` CLI flag 拡張 + test (~30 min)
- [ ] Plan B eval shards 4 個 (LoRA-on × 2 + no-LoRA × 2、~5h GPU)
- [ ] shard 検証 (`validate_multiturn_shards.py`)
- [ ] 4-encoder rescore JSON 生成 (MPNet / E5-large / lexical-5gram /
      BGE-M3、~1-2h CPU)
- [ ] Burrows / ICC / throughput verdict 計算
- [ ] verdict aggregator JSON + MD 生成
- [ ] kant ADOPT or Phase E A-6 判定 + decisions.md DR-? に記録
- [ ] Codex independent review 起票 + `codex-review.md` verbatim
- [ ] `pre-push-check.sh|.ps1` 全 pass 確認 → commit + push +
      `gh pr create`
- [ ] **ADOPT 時**: nietzsche / rikyu の Plan B 展開 next-session prompt
      起票
- [ ] **Phase E A-6 移行時**: DA-16 ADR 起票 (rank=16 spike)
```
