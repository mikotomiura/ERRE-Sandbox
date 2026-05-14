# 重要な設計判断

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-14) は `.steering/20260513-m9-c-adopt/decisions.md` に
> 追記する (immutable append convention)。

## DR-1: signal-driven preferred for retrain v2

- **判断日時**: 2026-05-14
- **背景**: DA-13 で LoRA effect proper baseline 比 near-zero (Vendi +0.446 /
  Burrows -0.960) と判明。加えて `train_metadata.json` で realized_examples=5022
  (CS-3 SLO 1000 の 5x margin) であり、DA-9 literal "1000 → 3000" 増加は
  既に達成済。volume scaling は literature shoulder (~5k) 越えで diminishing
  returns。
- **選択肢**:
  - A: Volume-driven (5022 → 12000+ via stim battery 70 → 200 拡張)
  - B: Signal-driven (5022 維持 + per-example loss/sampling weights で
    persona self-reference markers + dialog bonus + stim category balance を bias)
  - C: Hybrid (~7500 examples + stratified diversity injection、weight なし)
- **採用**: B (signal-driven)
- **理由**:
  - DA-12/13 で discriminative signal が intrinsic に弱いことが empirical 確定
  - realized=5022 既に literature shoulder 越え、volume scaling 効果不確実
  - 新規 data 採取コスト ゼロ、本 PR design + 次 PR 実装で完結可能
- **トレードオフ**: コード変更大 (build_weighted_examples + sample-weight collator)、
  weight tuning hand-set (validation split 検討要)
- **影響範囲**:
  - 次 PR (`feature/m9-c-adopt-retrain-v2-implementation`) で
    `src/erre_sandbox/training/{dataset,train_kant_lora}.py` 改修
  - Codex HIGH-A/HIGH-C で statistical soundness 検証必要
- **見直しタイミング**: Step 1 corpus analysis で realized=5022 が **実は
  high-signal** と判明したら volume-driven (A) を再考。Codex HIGH-A で
  hybrid 推奨が出たら C へ shift も可。

## DR-2: Codex review reflection (Step 3 完了)

- **判断日時**: 2026-05-14
- **Codex verdict**: **ADOPT-WITH-CHANGES** (`codex-review.md` verbatim 保存)
- **Token cost**: 260,485 tokens (high reasoning effort)

### HIGH (即反映済、design-final.md 編集トリガー)

- **HIGH-A** (signal vs hybrid 十分性): **MODIFY → 反映済**
  - design-final.md §3.3 で group-aware validation split を strengthen
  - §3.2 で weight-concentration audit を training kickoff 直前に追加
  - §2 Candidate C を **targeted hybrid** (de/en/≥60/monolog 採取のみ) に
    narrow 化
  - Candidate C fallback trigger 条件を明示 (effective high-signal mass
    <1000 / top 5% weight share ≥50% / overfit diagnostics / DA-14 REJECT)

- **HIGH-B** (G-GEAR overnight feasibility): **ADOPT → 反映済**
  - §3.5 に compute envelope を 8h abort 維持
  - eval batch=1 + loss-only eval guard を追加
  - sample weight scalar overhead が QLoRA activation memory に対し
    negligible である根拠を Codex 引用で明記

- **HIGH-C** (weight 式 statistical soundness): **MODIFY → 反映済**
  - design-final.md §3.2 で **`sample_weight` 自動 consume 不可** を訂正
  - `WeightedTrainer.compute_loss` を自前実装する仕様を追加
    (token CE reduction='none' → per-example mean → weighted sum / normaliser)
  - mean=1.0 への normalisation 必須化、weight bucket-level mass 報告
  - 4 coefficients (0.35/0.20/0.15/0.30) を **heuristic** (NOT empirical) と
    明記
  - prior art を static importance weighting / curriculum learning (Bengio
    2009) に正、focal loss は loose analogy のみ、DAP は NOT match と訂正

- **HIGH-D** (DA-14 thresholds empirical justification): **MODIFY → 反映済**
  - §4 で Burrows ≥5% が ambitious だが acceptable の根拠を強化
    (現状 LoRA effect proper -0.83% → 5% pass は真の shift)
  - ICC(C,k) >0.97 saturated から ICC(A,1) primary 昇格の根拠を明記
  - Step 4 DA-14 ADR で正式 pin

### MEDIUM (採否記録、本 file)

- **MEDIUM-1** (Step 1 metric coverage): **採用 (proxy nature を明記、
  追加 metric は次セッション scope)**
  - tokenizer proxy + langdetect proxy の caveat は `corpus-analysis-kant.md`
    で明記済
  - 追加 metric (n-gram entropy / TTR / 構文 depth) は本 PR scope 外、
    training kickoff session で必要なら fold-in

- **MEDIUM-2** (weighted overfit risk): **採用、HIGH-A と統合反映**
  - group-aware validation split (§3.3) で対処
  - WeightedTrainer の `Trainer.compute_loss` override が reduction='mean'
    default と互換 (per-example mean → weighted sum / weights.sum)、Codex
    code sketch に従う

- **MEDIUM-3** (monolog re-cast eval intent leak): **採用、HIGH-A と統合反映**
  - design-final.md §3.3 で group-aware separation + training phase 由来
    制約 + synthetic source metadata + duplicate / source count 報告を
    必須化
  - cap ~150-300 synthetic monolog rows を明記

### LOW (`blockers.md` 持ち越し可)

- **LOW-1**: **採用** — DA-14 を `.steering/20260513-m9-c-adopt/decisions.md` に
  append + DR-2 (本 file) fill 完了。`da1-thresholds-recalibrated.json` +
  `next-session-prompt.md` は Step 4-5 で作成
- **LOW-2**: **採用** — design-final.md §3.2 で "sample_weight standard path"
  wording を訂正、"30x" clamp framing を practical min ~0.34 / max ~3.53 で
  ~10x に補正 (normalisation 後)、validation / early stopping 要件を §3
  に移動 (元 §5 Risks から §3.3 fold-up 済)
