# Next-session 開始プロンプト — Plan B retrain verdict 計算

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR #181 (`feature/m9-c-adopt-plan-b-retrain`、lexical-5gram + 750 monolog
  corpus + DR-5/DR-6 WeightedTrainer perf + retrain kickoff + CI fix +
  pre-push workflow) **merged 済** (merge SHA `f68ac63`)
- retrain (`train_kant_lora --plan-b-gate --lang-stratified-split --rank 8
  --max-steps 2500 --eval-steps 250 --weighted`) が `data/lora/m9-c-adopt-v2/
  kant_r8_v3/` に best checkpoint を artifact 化済 (本セッション開始時に
  retrain は完走している前提、PID 387 in WSL2 monitor で確認可能)
- 観測済 eval_loss trajectory (PR #181 最終 push 時点、step 1250 までで
  全 evals 改善継続、early stopping fire なし):
    | step | epoch | eval_loss |
    |---|---|---|
    | 250  | 0.35  | 0.2582 |
    | 500  | 0.70  | 0.2161 |
    | 750  | 1.05  | 0.1965 |
    | 1000 | 1.40  | 0.1897 |
    | 1250 | 1.76  | 0.1845 |
  v2 baseline の envelope 0.166–0.180 に接近、retrain 完走時の best は
  step 1500–2500 の範囲想定 (EarlyStoppingCallback patience=2 / min_delta=0.005)
- step pace ~4 s/it stable (v2 baseline 14 s/it の **3.3× 高速化**、
  DR-5 / DR-6 patch 実効、`compute_loss` の `labels.pop()` + eval-side
  `prediction_loss_only=True`)
- corpus gate PASS (n_eff=4355.5 / top_5%=0.125 / de+en=0.601 / de=0.385)
- D-2 allowlist (Plan B): MPNet + E5-large + lexical-5gram primary、BGE-M3
  exploratory (`.steering/20260517-m9-c-adopt-plan-b-design/
  d2-encoder-allowlist-plan-b.json`)
- G-GEAR (RTX 5060 Ti SM120、16 GB VRAM) + WSL2 Ubuntu の SGLang fp8
  + disable-piecewise-cuda-graph 環境前提 (DR-4)
- **Pre-push CI parity check 必須** (`bash scripts/dev/pre-push-check.sh` /
  `pwsh scripts/dev/pre-push-check.ps1`、PR #181 reflection で本セッション
  追加、CLAUDE.md 禁止事項に明記)

**branch**: 新規 `feature/m9-c-adopt-plan-b-verdict` を **main** から切る
**compute**: DA-14 rerun verdict 計算 (~2h、4 encoder × Vendi + Burrows
+ ICC cross-recompute、CI bootstrap) + Codex independent review (~30 min)
= **~2-2.5h** envelope

---

```
m9-c-adopt **Plan B retrain verdict 計算** を実行する。retrain artifact
(`data/lora/m9-c-adopt-v2/kant_r8_v3/`、PR #181 merge SHA `f68ac63` の
overnight retrain で生成、step 1250 時点で eval_loss=0.1845、v2 baseline
envelope 0.166–0.180 に接近) を読み、4-encoder agreement axis で natural d /
lang-balanced d / length-balanced d を計算、Burrows ≥5% + ICC ≥0.55 +
throughput ≥70% の DA-14 thresholds と合わせて kant ADOPT or Phase E A-6
(rank=16) 移行を判定する。

## 目的 (本セッション、~2-2.5h)

1. **`/start-task`** で `.steering/<YYYYMMDD>-m9-c-adopt-plan-b-verdict/`
   を起票 (5 標準 file)
2. **retrain artifact 確認**:
   - `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` の最終 eval_loss
     trajectory + best checkpoint 情報
   - `data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-<best>/` の存在確認
   - `retrain-stdout.log` で early stopping fire したか / step 何で best を取ったか
   - **retrain がまだ走っている場合**: `wsl -d Ubuntu-22.04 -- ps -p 387` で
     確認、完走 (max_steps=2500 到達 or early stop) まで待機
3. **`vendi_lexical_5gram.py` の D-2 allowlist 検証**:
   - `_load_default_kernel(kernel_type="lexical_5gram")` が
     `da1_matrix_multiturn.py` (または `da15_verdict.py`) から呼び出せるか確認
   - PR #181 commit (merge SHA `f68ac63`) の revision pin
4. **DA-14 rerun verdict 計算** (~2h):
   - `scripts/m9-c-adopt/da1_matrix_multiturn.py` (または `da15_verdict.py`)
     を 4 encoder × 2 baseline (v2 baseline vs Plan B kant_r8_v3) で実行
   - encoder set: MPNet (primary)、E5-large (primary)、lexical-5gram (primary)、
     BGE-M3 (exploratory)
   - 各 encoder で:
     - natural d ≤ -0.5 AND CI upper < 0
     - lang-balanced d ≤ -0.5
     - length-balanced d ≤ -0.5
     - 符号一致 (negative)
   - **encoder agreement axis**: 3 primary のうち 2 以上が gate clear なら ADOPT 寄与
5. **Burrows / ICC / throughput verdict**:
   - Burrows axis ≥ 5% point + CI lower > 0 (DA-14 threshold 不変)
   - ICC ≥ 0.55 (DA-14 threshold 不変)
   - throughput ≥ 70% baseline (DA-14 threshold 不変)
6. **kant ADOPT or Phase E A-6 判定**:
   - 3 primary encoder の 2 以上が agreement axis pass + Burrows ≥5% +
     ICC ≥0.55 + throughput ≥70% → **ADOPT**
   - 1 axis でも fail → **Phase E A-6 migration** (rank=16 spike、別 ADR DA-16 候補)
7. **Codex independent review** (~30 min):
   - `.steering/<task>/codex-review-prompt.md` 作成 → 
     `cat ... | codex exec --skip-git-repo-check`
   - HIGH/MEDIUM/LOW を `codex-review.md` に verbatim 保存、本 PR scope で
     HIGH 全件反映、MEDIUM は decisions.md で採否、LOW は blockers.md
8. **commit + push 前に必ず `pre-push-check`**:
   - `bash scripts/dev/pre-push-check.sh` (WSL2/macOS/Linux) or
     `pwsh scripts/dev/pre-push-check.ps1` (Windows)
   - 4 段階 (ruff format --check / ruff check / mypy src / pytest -q) 全 pass で
     push 可。1 段でも fail なら push 禁止 (memory `feedback_pre_push_ci_parity.md` 参照)

## NOT in scope (本セッション)

- retrain 再実行 (artifact が既にある前提、early stopping fire してても best
  checkpoint で verdict 計算)
- nietzsche / rikyu の Plan B 展開 (kant verdict ADOPT 後の別 PR)
- WeightedTrainer Blocker 2 (sample weight collapse) の修正
  (Plan B verdict ADOPT なら保留、REJECT なら別 PR で優先)
- 新規 corpus 採取 (現在の 750 de-monolog で gate PASS 済、追加採取不要)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1〜DR-7
2. `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 1 / 2
3. `.steering/20260518-m9-c-adopt-plan-b-retrain/artifacts/plan-b-corpus-gate-final.json`
4. `.steering/20260518-m9-c-adopt-plan-b-retrain/artifacts/run{0,1,2}_manifest.json`
5. `.steering/20260517-m9-c-adopt-plan-b-design/design.md` §1.5 / §7 +
   `d2-encoder-allowlist-plan-b.json` (encoder pin + revision_sha)
6. `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` (D-2 primary)
7. `src/erre_sandbox/training/train_kant_lora.py` の `WeightedTrainer.compute_loss`
   (DR-5 patch 適用済を確認)
8. `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` (retrain artifact、
   best checkpoint + final eval_loss trajectory)
9. `data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json` (gate PASS evidence)
10. memory `reference_qwen3_sglang_fp8_required.md` (SGLang DR-4 invocation)
11. memory `feedback_pre_push_ci_parity.md` (push 前 4 段階 check 必須)
12. `CLAUDE.md` 「禁止事項」(pre-push CI parity + extras-only 3 点セット を含む)

## 留意点 (HIGH 違反防止)

- **DA-14 thresholds 不変**: Vendi d ≤ -0.5 / Burrows ≥5% / ICC ≥0.55 /
  throughput ≥70%。retrain 結果が borderline でも threshold 移動禁止
- **encoder agreement axis 不可侵**: 3 primary の 2 以上要件 (V2 §5.3)
- **D-2 allowlist の encoder revision pin**: PR #179 で固定された
  revision_sha をそのまま使う (allowlist JSON の `revision_sha` 参照)
- **Plan B corpus gate は train-time check が PASS 済**: verdict 計算側で
  retroactive に threshold を動かさない
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)

## 完了条件

- [ ] `feature/m9-c-adopt-plan-b-verdict` branch (main 派生、main HEAD `f68ac63`)
- [ ] `.steering/<task>/` 5 標準 file
- [ ] retrain artifact 確認 (best checkpoint の eval_loss / step)
- [ ] DA-14 rerun 4-encoder verdict 計算 (natural d / lang-balanced d /
      length-balanced d 各 CI)
- [ ] Burrows / ICC / throughput verdict 計算
- [ ] encoder agreement axis 評価 (3-of-4、2 以上要件)
- [ ] kant ADOPT or Phase E A-6 判定 + decisions.md DR-? に記録
- [ ] Codex independent review 起票 + `codex-review.md` verbatim
- [ ] `pre-push-check.sh|.ps1` 全 pass 確認 → commit + push + `gh pr create`
- [ ] **ADOPT 時**: nietzsche / rikyu の Plan B 展開 next-session prompt 起票
- [ ] **Phase E A-6 移行時**: DA-16 ADR 起票 (rank=16 spike)
```
