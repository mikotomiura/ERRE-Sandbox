# m9-c-adopt Plan B retrain verdict 計算

## 背景

PR #181 (`feature/m9-c-adopt-plan-b-retrain`、merge SHA `f68ac63`) で
Plan B retrain (lexical-5gram + 750 monolog corpus + DR-5/DR-6
WeightedTrainer perf + retrain kickoff) を完走させた。retrain artifact
`data/lora/m9-c-adopt-v2/kant_r8_v3/` に best checkpoint (step 1500、
eval_loss=0.18259、v2 baseline envelope 0.166–0.180 の **上端**) が生成済。
EarlyStoppingCallback は step 1750 (eval_loss=0.1813) で fire (patience=2
+ min_delta=0.005、step 1500→1750 の improvement が 0.0013 < 0.005)。

本セッションは retrain artifact の **DA-14 rerun verdict** を 4-encoder
agreement axis (MPNet / E5-large / lexical-5gram / BGE-M3) で計算し、
kant ADOPT or Phase E A-6 (rank=16) 移行を判定する。

## ゴール

- Plan B kant_r8_v3 best checkpoint (step 1500) を 4 encoder × Vendi +
  Burrows + ICC + throughput で verdict 計算し、`da14-verdict-plan-b-kant.json`
  + `da14-verdict-plan-b-kant.md` を生成
- encoder agreement axis (3 primary のうち 2 以上 で natural d ≤ -0.5
  AND CI upper < 0 AND lang-balanced d ≤ -0.5 AND length-balanced d ≤ -0.5
  AND 符号一致) を評価
- Burrows ≥5% point + CI lower > 0、ICC ≥0.55、throughput ≥70%
  baseline の DA-14 thresholds (不変) を合わせて評価
- kant ADOPT (全 gate pass) or Phase E A-6 migration (1 axis 以上 fail)
  を decisions.md で確定

## スコープ

### 含むもの
- Plan B eval shard 生成 (kant_r8v3 LoRA + no-LoRA SGLang baseline、
  ~250 stim × 6 cycle、同 protocol で v2 と apples-to-apples)
- 4 encoder の rescore (MPNet / E5-large / lexical-5gram / BGE-M3)
- Burrows / ICC / throughput cross-recompute
- encoder agreement axis 評価 + ADOPT/REJECT verdict
- Codex independent review
- Pre-push CI parity check + commit + PR open

### 含まないもの
- nietzsche / rikyu の Plan B 展開 (kant ADOPT 後の別 PR)
- WeightedTrainer Blocker 2 (sample weight collapse) の修正
  (ADOPT なら保留、REJECT なら別 PR で優先)
- 新規 corpus 採取 (現在の 750 de-monolog で gate PASS 済)
- retrain 再実行 (eval_loss=0.1826 の checkpoint を使う)

## 受け入れ条件

- [ ] Plan B eval shards (`kant_r8v3_run{0,1}_stim.duckdb` +
      `kant_planb_nolora_run{0,1}_stim.duckdb` を新規生成、
      v2 baseline と同 protocol)
- [ ] 4 encoder の rescore JSON 生成 (`da14-rescore-{encoder}-plan-b-kant.json`)
- [ ] Burrows / ICC / throughput verdict 計算
- [ ] encoder agreement axis 評価 (3-of-4、2 以上要件)
- [ ] kant ADOPT or Phase E A-6 判定 + decisions.md DR-? に記録
- [ ] Codex independent review 起票 + `codex-review.md` verbatim 保存
- [ ] `pre-push-check.sh|.ps1` 全 pass 確認 → commit + push + `gh pr create`
- [ ] ADOPT 時: nietzsche / rikyu の Plan B 展開 next-session prompt 起票
- [ ] Phase E A-6 移行時: DA-16 ADR 起票 (rank=16 spike)

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-plan-b-design/design.md` §1.5 / §7
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1〜DR-7
- `.steering/20260516-m9-c-adopt-da15-impl/d2-encoder-allowlist.json` (Plan A、参照)
- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
- `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` (D-2 primary、本セッション開始時に既存)
- memory `reference_qwen3_sglang_fp8_required.md` (SGLang DR-4 invocation)
- memory `feedback_pre_push_ci_parity.md` (push 前 4 段階 check 必須)
- CLAUDE.md 「禁止事項」(pre-push CI parity + extras-only 3 点セット)
