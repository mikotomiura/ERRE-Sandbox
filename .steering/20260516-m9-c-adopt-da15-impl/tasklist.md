# タスクリスト — DA-15 Phase 1 implementation

## 準備
- [x] branch `feature/m9-c-adopt-da15-implementation` (main 派生)
- [x] `.steering/20260516-m9-c-adopt-da15-impl/` 5 標準 file 作成
- [x] DA-15 ADR / Codex review / DA-14 verdict / vendi.py 現状 を Read

## 実装 — code parameterisation
- [ ] `src/erre_sandbox/evidence/tier_b/vendi.py` `_load_default_kernel(
      encoder_name=None)` 引数化、MPNet default 維持
- [ ] `scripts/m9-c-adopt/compute_baseline_vendi.py` `--encoder` CLI 引数追加
- [ ] `tests/test_evidence/test_tier_b/test_vendi.py` 新規 test 追加

## 実装 — calibration panel
- [ ] `data/calibration/kant_heidegger_corpus.json` 新規 (Kant + Heidegger
      control text 各 100 文、language tag 付き)
- [ ] `scripts/m9-c-adopt/da15_calibration_panel.py` 新規 (cosine sim → AUC)

## 実装 — rescore script
- [ ] `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` 新規 (v2 + no-LoRA を
      multiple encoder で rescore、balanced bootstrap + within-lang d)

## pre-registration (rescore 前必須)
- [ ] decisions.md D-2 に encoder name + HF revision SHA + transformers
      version + sentence-transformers version + commit SHA を pin commit

## 実行 — calibration → rescore → verdict
- [x] calibration panel 実行 (multilingual-e5-large AUC=0.8865 PASS + bge-m3
      AUC=0.9055 PASS + MPNet regression AUC=0.8960 PASS)
- [x] AUC ≥ 0.75 を満たす encoder を確定 (両 candidate ともに PASS)
- [x] rescore 実行 (3 encoder で v2 + no-LoRA apples-to-apples 再 score)
- [x] DA-15 verdict 計算 (verdict=REJECT、両 candidate が rescore で
      cohens_d ≤ -0.5 + CI upper < 0 を未達)
- [x] `da15-verdict-kant.json` + `da15-verdict-kant.md` 出力
- [-] kant ADOPT 時: Burrows named limitation を md に必須記載 (kant ADOPT
      ではないので未適用、Phase 2 起票時の参照として md には記録残)

## 補足修正
- [x] `scripts/m9-c-adopt/da1_matrix_multiturn.py` comparator note 切替

## レビュー
- [x] `codex-review-prompt.md` 起草
- [ ] `codex exec` で independent review 実行
- [ ] `codex-review.md` verbatim 保存
- [ ] HIGH 指摘を反映

## 完了処理
- [ ] design.md / decisions.md 最終化
- [ ] git commit + push
- [ ] `gh pr create`
