# DA-15 Phase 1 implementation — Plan A (Vendi kernel swap)

## 背景

DA-14 verdict は kant retrain v2 を REJECT した (primary axis 1-of-3、Vendi
d=-0.18 / Burrows +0.43% / ICC PASS / throughput PASS、2-of-3 quorum 未達)。

`.steering/20260516-m9-c-adopt-da15-adr/` で DA-15 ADR を起票し、Plan A → Plan
B sequential + Hybrid H-α を採用案として確定 (PR #177 merge 済)。Codex review
は ADOPT-WITH-CHANGES verdict、HIGH-1 (versioned metric) / HIGH-2 (calibration
panel) / MEDIUM 3 件 / LOW-1 をすべて反映済。

本セッションは Plan A の **literal 実装** + Codex review + verdict 出力までの
一気通貫。

## ゴール

1. Plan A 実装 (vendi.py + compute_baseline_vendi.py の encoder 引数化、
   backward-compat、MPNet default 維持)
2. Plan A eligibility gate (calibration panel + balanced bootstrap + within-
   language d) の実装
3. DA-15 新 metric `vendi_semantic_v2_encoder_swap` で kant ADOPT/REJECT 確定
4. Burrows named limitation を verdict 文書に記載 (Codex LOW-1)
5. Codex independent review + HIGH 反映
6. PR 起票

## スコープ

### 含むもの
- `src/erre_sandbox/evidence/tier_b/vendi.py` encoder 引数化
- `scripts/m9-c-adopt/compute_baseline_vendi.py` --encoder CLI 引数
- `scripts/m9-c-adopt/da15_calibration_panel.py` 新規 (Kant vs Heidegger 制御
  AUC ≥ 0.75 gate)
- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` 新規 (v2 + no-LoRA pilot を
  multiple encoder で rescore、balanced bootstrap + within-language d)
- encoder + revision pin pre-registration commit (rescore 前)
- `da15-verdict-kant.json` + `da15-verdict-kant.md` (verdict 文書)
- `scripts/m9-c-adopt/da1_matrix_multiturn.py` comparator 切替 (MATCHED
  HISTORICAL Ollama → no-LoRA SGLang DA-14 baseline)
- Codex independent review

### 含まないもの
- Plan B (Phase 2) の実装 (Plan A 失敗時の別 PR で起票)
- nietzsche / rikyu の Plan A 展開 (kant ADOPT 後の Phase C 判断)
- Phase E A-6 / Plan C (rank=16) (本 ADR scope 外)
- DA-15 trace.HEAD への本 PR merge SHA 埋め込み (本 PR merge 後の別 chore PR)
- Hybrid H-α (Plan B driver pre-stage) (isolated branch で並行)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-da15-implementation` branch (main 派生)
- [ ] `.steering/20260516-m9-c-adopt-da15-impl/` の 5 標準 file (requirement,
      design, tasklist, decisions, blockers)
- [ ] vendi.py の encoder 引数化 (backward-compat、MPNet default 維持、
      unit test 通過)
- [ ] compute_baseline_vendi.py の `--encoder` 引数追加
- [ ] da15_calibration_panel.py で multilingual-e5-large + bge-m3 を test、
      AUC ≥ 0.75 pass gate (fail なら Phase 2 へ fall through)
- [ ] encoder + revision pin pre-registration commit (rescore 前に decisions.md
      D-2 へ固定)
- [ ] rescore_vendi_alt_kernel.py で v2 + no-LoRA を apples-to-apples で再 score
      (balanced bootstrap + within-language d、seed=42)
- [ ] DA-15 verdict (`da15-verdict-kant.json` + `.md`) で kant ADOPT/REJECT 確定
- [ ] kant ADOPT 時は Burrows named limitation を verdict 文書に必須記載
- [ ] da1_matrix_multiturn.py comparator 切替 (同 PR or 別 PR)
- [ ] Codex independent review 起票 + HIGH 反映
- [ ] commit + push + `gh pr create`

## 関連ドキュメント

- `.steering/20260516-m9-c-adopt-da15-adr/decisions.md` D-1, D-2
- `.steering/20260516-m9-c-adopt-da15-adr/design.md`
- `.steering/20260516-m9-c-adopt-da15-adr/codex-review.md`
- `.steering/20260513-m9-c-adopt/decisions.md` (DA-1〜DA-15 cross-cutting ADR)
- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
- `src/erre_sandbox/evidence/tier_b/vendi.py:294-322`
- `scripts/m9-c-adopt/compute_baseline_vendi.py`
- `tests/test_evidence/test_tier_b/test_vendi.py`
