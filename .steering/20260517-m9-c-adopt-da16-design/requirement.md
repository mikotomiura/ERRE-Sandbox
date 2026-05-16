# DA-16 ADR — kant Plan B PHASE_E_A6 順序判断 (WeightedTrainer fix vs rank=16 spike)

## 背景

PR #184 (`feature/m9-c-adopt-plan-b-eval-gen`) で kant Plan B retrain
(rank=8, kant_r8_v3) に対する 4-encoder rescore + Burrows + ICC +
throughput verdict を完走、`da14-verdict-plan-b-kant.json` の routing は
**`PHASE_E_A6`** (REJECT) に確定した
(`.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1)。

### REJECT の根拠 (verdict 4 axis)

| axis | result | gate | 数値 |
|---|---|---|---|
| Encoder agreement | **FAIL** | 3-of-4 primary, 2+ pass all 3 axes | 0/3 primaries pass; direction discipline FAIL (MPNet `−0.5264` / E5 `+0.4781` / lex5 `+0.1805`) |
| Burrows reduction% | **FAIL** | ≥5pt + CI lower > 0 | `−1.95%` (LoRA-on Burrows `114.71` > no-LoRA `112.52`) |
| ICC(A,1) | PASS | ≥0.55 | `0.9083` |
| Throughput pct | PASS | ≥70% | `99.17%` |

特筆すべきは **per-encoder direction disagreement**: MPNet 視点では
retrain で Vendi semantic が下がったが (`d=−0.53`、ただし std_pass=False)、
E5-large・lexical_5gram 視点では逆に **上がった** (`d=+0.48`, `+0.18`)。
これは "magnitude 不足" ではなく "training signal の direction 自体が
encoder 間で incoherent" を示唆する。

### 根因仮説 2 つ

1. **WeightedTrainer Blocker 2 (sample weight collapse)** — retrain
   blockers.md ブロッカー 2 + decisions.md DR-1 根因仮説 1 で記録:
   `compute_weighted_causal_lm_loss` (`src/erre_sandbox/training/
   weighting.py:411`) の reduce 式 `(per_example_loss * weights).sum() /
   torch.clamp(weights.sum(), min=1e-8)` は `per_device_train_batch_size=1`
   (DI-7 で確定、Qwen3-8B + 16 GB VRAM で batch≥2 不可) のとき
   `(l[0] * w[0]) / w[0] = l[0]` で **weight が数学的に相殺** される。
   DA-14 weighting (de_monolog 0.35 / dialog 0.20 / aphorism 0.15 / quote
   0.30、normalise to mean=1) が training 中に **gradient へ反映されて
   いなかった** 可能性。eval_loss は下がる (general LM objective) が
   DA-14 style/diversity gate は改善しない結果と整合。
2. **rank=8 capacity 不足** — kant の Burrows/style 信号は de_monolog に
   集中しており、rank=8 では LoRA adapter capacity が足りない可能性。
   rank=16 spike で再 retrain して切り分ける。

両仮説を **どの順序で切り分けるか** が本 ADR の主論点。

### nietzsche / rikyu Plan B 展開はブロック中

kant verdict が ADOPT に至らない限り、他 persona の Plan B retrain を
回しても同じ encoder agreement FAIL を踏む確率が高い。本 ADR の
順序判断確定までは nietzsche / rikyu Plan B 展開を **保留**。

## ゴール

1. **順序判断の確定** (decisions.md DA16-1): rank=8 + WeightedTrainer fix
   先行 (候補 A) / rank=16 spike 先行 (候補 B) / 両方同時 (候補 C) のいずれ
   かを採用、根拠を verbatim 引用で記録
2. **WeightedTrainer fix の実装方針確定** (decisions.md DA16-2): retrain
   blockers.md ブロッカー 2 の暫定対応案 (a)/(b)/(c) のどれを採用するか、
   batch=1 + grad_accum=8 セマンティクスを明文化
3. **続 PR scope 分割の明文化** (design.md): PR-2 (WeightedTrainer fix
   実装) / PR-3 (kant_r8_v4 retrain) / PR-4 (DA-14 rerun verdict) /
   PR-5 (rank=16 spike、PR-4 REJECT 時のみ) の dependency graph を提示
4. **WeightedTrainer Blocker 2 を本 PR scope 外として持ち越し** (blockers.md):
   PR-2 への handoff を明文化、続 PR-2 用 next-session prompt を起票
5. **Codex independent review** WSL2 経由で取得、verbatim 保存

## スコープ

### 含むもの

- `decisions.md` DA16-1 (順序判断) + DA16-2 (WeightedTrainer fix 方針)
  + DA16-3 (続 PR scope 分割) + DA16-4 (DA-14 thresholds 不変宣言)
- `design.md` — 採用候補の実装方針、影響範囲、テスト戦略、ロールバック計画
- `tasklist.md` — 本 ADR セッション内の作業、PR-2/PR-3/PR-4/PR-5 への
  handoff item
- `blockers.md` — WeightedTrainer Blocker 2 を別 PR-2 として持ち越し
- `codex-review-prompt.md` + `codex-review.md` (WSL2 経由 verbatim)
- 続 PR-2 用 next-session prompt
  (`.steering/<task>/next-session-prompt-FINAL-pr2-weighted-trainer-fix.md`)
- memory `project_plan_b_kant_phase_e_a6.md` を採用候補確定で update

### 含まないもの

- WeightedTrainer Blocker 2 の **実装修正** (別 PR-2 scope)
- rank=16 spike の **実装** (別 PR-5 scope、PR-4 verdict REJECT 時のみ)
- 新 retrain (kant_r8_v4) の実行 (別 PR-3 scope)
- 新 eval shard 生成 (別 PR-4 scope)
- nietzsche / rikyu の Plan B 展開 (kant verdict ADOPT 待ち、現在保留)
- `da14-verdict-plan-b-kant.json` の thresholds 変更 (DA-14 thresholds は
  Plan B でも不変、ADR DA-16 で再確認のみ)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-da16-design` branch (main 派生) で commit
- [ ] `.steering/20260517-m9-c-adopt-da16-design/` 5 標準 file 完成
- [ ] decisions.md DA16-1〜DA16-4 が記載、verbatim 引用で根拠明示
- [ ] design.md で続 PR scope (PR-2 / PR-3 / PR-4 / PR-5) の dependency
      graph + 影響範囲が明文化
- [ ] blockers.md で WeightedTrainer Blocker 2 を別 PR-2 へ持ち越し
- [ ] Codex independent review **WSL2 経由で起動**、`codex-review.md`
      verbatim 保存、HIGH/MEDIUM/LOW summary 含む
- [ ] 続 PR-2 用 next-session prompt が `.steering/<task>/
      next-session-prompt-FINAL-pr2-weighted-trainer-fix.md` に起票
- [ ] `pre-push-check.sh` または `.ps1` 4 段全 pass (本 PR は doc-only
      でも CLAUDE.md 禁止事項に従い必須)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を採用候補 + PR-2/3/4/5
      scope 確定で update
- [ ] `gh pr create` で main 向け PR を起票

## 関連ドキュメント

- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DE-1〜DR-1
  (本 ADR が依拠する verdict 結果 + 根因仮説)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`
  (4-axis verdict + per-encoder direction 結果)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/blockers.md` ブロッカー 2
  (Codex Windows hook 干渉教訓、本 PR で WSL2 経由を採用)
- `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2
  (WeightedTrainer sample weight collapse の根拠 + 暫定対応案 (a)/(b)/(c))
- `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-5 / DR-6
  (WeightedTrainer.compute_loss 構造 + 関連パッチ歴)
- `src/erre_sandbox/training/weighting.py:411`
  (`compute_weighted_causal_lm_loss` の数式実装、本 ADR で修正方針を確定)
- `src/erre_sandbox/training/train_kant_lora.py:1690-1715`
  (WeightedTrainer.compute_loss + DR-5 patch 適用後の現状)
- `tests/test_training/test_weighted_trainer.py`
  (既存 weighting unit test、batch=2 のみで pass する盲点)
- memory `project_plan_b_kant_phase_e_a6.md` (本 ADR の起点となる verdict)
- memory `feedback_pre_push_ci_parity.md` (push 前 4 段 check 必須)
- memory `feedback_claude_md_strict_compliance.md` (Plan mode 必須、
  /reimagine 必須、Skill Read 必須)
