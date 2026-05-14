# M9-C-adopt retrain v2 spec design

## 背景

PR #166 (m9-c-adopt-pilot-multiturn investigation、DA-13 ADR) で empirical に確定した事実:

- **DA-12 "direction failure" の主因 = backend confound** (Ollama → SGLang 単独で
  Vendi +2.144 / Burrows +5.391)
- **LoRA effect proper baseline** (rank=8 no-LoRA SGLang vs LoRA-on SGLang) は
  near-zero: Vendi +0.446 / Burrows -0.960
- pre-registered Scenario II verdict は literal true、ただし direction failure の
  root cause が LoRA failure ではなく backend confound に再帰属

retrain v2 spec を **proper SGLang baseline 基準** で再構築し、persona-discriminative
signal を強化して LoRA effect size を底上げする必要がある。

加えて Phase 1 探索で判明した **最重要 finding**:
`data/lora/m9-c-adopt/archive/rank_8/kant/train_metadata.json` の `realized_examples = 5,022`
(CS-3 SLO 1000 の **5x margin で既に実施済**)。DA-9 の literal な解釈 ("1000 → 3000")
は不正確で、真の問題は **per-example discriminative signal の弱さ**。retrain v2 spec
は **signal-driven engineering** に rebrand する必要がある (user 承認済方針)。

## ゴール

本 PR (`feature/m9-c-adopt-retrain-v2-design`、design only) で以下を完遂:

1. 既存 5,022 training examples の **特性分析** (5 metrics) + gap finding
2. **retrain v2 spec** (signal-driven 推奨、`/reimagine` で 3 候補比較) 確定
3. **DA-1 thresholds の re-calibration** (DA-14 ADR、no-LoRA SGLang baseline 基準)
4. **Codex independent review** で HIGH/MEDIUM/LOW 反映方針確定
5. 次セッション (training kickoff + multi-turn pilot recapture + ADOPT/REJECT) の
   **handoff prompt** 起草

## スコープ

### 含むもの (本セッション)

- `scripts/analysis/analyze_kant_training_corpus.py` 実装 + 3-case smoke test
- 5 metrics 算出 (token length / persona self-reference markers / dialog-monolog
  ratio / per-stim category coverage / utterance language distribution)
- `corpus-analysis-kant.{json,md}` artefact 生成
- `design-final.md` (Plan mode + `/reimagine` 適用、signal-driven 採用)
- `codex-review-prompt.md` + `codex-review.md` (verbatim 保存) + 反映
- `DA-14 ADR` (`.steering/20260513-m9-c-adopt/decisions.md` 追記、5-element pattern)
- `da1-thresholds-recalibrated.json` (機械可読 thresholds pin)
- `next-session-prompt.md` (training kickoff + re-evaluation)
- design-only PR (commit + push + `gh pr create`)

### 含まないもの (本セッション)

- training v2 **実行** (別 PR `feature/m9-c-adopt-retrain-v2-implementation`、次セッション)
- multi-turn pilot 再採取 (training 完了後)
- nietzsche / rikyu の同 retrain spec (Phase C、kant ADOPT 後)
- Phase D (`MultiBackendChatClient`)
- Phase E A-6 (retrain v2 ADOPT 後 7500-turn full Tier B)
- production placement (Phase F)

## 受け入れ条件

- [ ] `pytest tests/test_analysis/` 3 case green
- [ ] `ruff format --check && ruff check` clean (src/ + scripts/ + tests/)
- [ ] `src/erre_sandbox/` 配下に `bpy` import / GPL dep なし (architecture-rules)
- [ ] `corpus-analysis-kant.md` に **falsifiable claim** 最低 1 件
  (例: "self-reference marker density 5x below literature anchor")
- [ ] `design-final.md` が **Plan mode で user 承認** 済
- [ ] Codex `codex-review.md` verbatim 保存 + HIGH 反映が `decisions.md` DR-1 に記録
- [ ] DA-14 cross-link が `.steering/20260513-m9-c-adopt/decisions.md` ↔
  `20260514-m9-c-adopt-retrain-v2-design/decisions.md` で双方向解決
- [ ] handoff prompt が fresh compacted session から実行可能 (self-contained)
- [ ] `gh pr create` 成功、PR description に "design-only, no training" 明記

## 関連ドキュメント

- `docs/architecture.md` (training pipeline / inference backends 節)
- `docs/development-guidelines.md` (test 方針 / Codex review 運用)
- `.steering/20260513-m9-c-adopt/decisions.md` (DA-1, DA-9, DA-12, DA-13)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/decisions.md` (D-1 Codex HIGH 4 件)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/report.md` (4-axis matrix)
- `.steering/20260514-m9-c-adopt-pilot-multiturn/next-session-prompt-scenario-II-retrain-v2.md`
  (本 PR の precursor、spec amendment 4 件)
- `data/lora/m9-c-adopt/archive/rank_8/kant/train_metadata.json` (realized=5022)
