# PR description draft — feature/m9-c-adopt-da15-implementation

## Summary

- **DA-15 Phase 1 (Plan A = Vendi kernel swap) を実装**。新規 training なし、
  新規 data 採取なし、measurement-side swap のみ。
- **vendi.py** `_load_default_kernel(encoder_name)` を引数化 (MPNet default
  維持、backward-compat)。
- **新規 metric** `vendi_semantic_v2_encoder_swap` (DA-14 thresholds 不変)
  を versioned 起こす。DA-14 MPNet `vendi_semantic` は historical record
  として併報告 (Codex HIGH-1)。
- **calibration panel** (Codex HIGH-2): Kant + Nietzsche control corpus を
  language-stratified に build、各 encoder で overall AUC + within-language
  AUC が 0.75 を超えるかを gate。
- **balanced bootstrap**: standard + language-balanced + length-balanced +
  within-language d を全て report。
- **encoder + revision pin** を rescore 実行前に decisions.md D-2 に固定
  (Codex HIGH-1)。
- **da1_matrix_multiturn.py** comparator を MATCHED HISTORICAL Ollama から
  no-LoRA SGLang (DA-14 authoritative) に切替。
- **kant ADOPT 時** は Burrows named limitation を verdict 文書に必須記載
  (Codex LOW-1)。

## Test plan

- [x] Plan A 実装 + unit test (vendi.py encoder parameterisation regression)
- [x] Pre-registration commit (encoder name + HF revision SHA + library
      versions) を rescore 前に固定
- [x] MPNet regression calibration: overall AUC=0.896、d_de=0.84、d_en=0.93
      (within-language pass)
- [ ] multilingual-e5-large calibration: AUC ≥ 0.75 gate 判定
- [ ] BAAI/bge-m3 calibration: AUC ≥ 0.75 gate 判定
- [ ] rescore (v2 + no-LoRA、apples-to-apples、seed=42)
- [ ] DA-15 verdict (kant ADOPT / REJECT) 確定
- [ ] Codex independent review 完了 + HIGH 反映
- [x] `pytest tests/test_evidence/` 全 pass (273 passed, 2 skipped)

## Verdict

(verdict 文書を `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.md`
に保存後、本欄に要約を貼る)

## Related

- Refs: `.steering/20260516-m9-c-adopt-da15-adr/decisions.md` D-1, D-2
- Refs: `.steering/20260516-m9-c-adopt-da15-adr/codex-review.md`
- Refs: `.steering/20260513-m9-c-adopt/decisions.md` DA-15
- Refs: `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`

## 留意点

- **HIGH-3 遵守**: DA-14 thresholds 不変、`vendi_semantic_v2_encoder_swap` は
  versioned new metric、MPNet は historical record として併報告
- **Plan A fail 時の Phase 2**: Plan A REJECT (両 candidate encoder で
  calibration AUC < 0.75 or balanced d > -0.5) なら Phase 2 (Plan B-2) を
  別 PR で起票
- **Hybrid H-α isolation** (Codex MEDIUM-3): 本 PR には含めない (別 branch
  で並行作業の前提)
- **DA-15 trace.HEAD 埋め込み**: 本 PR merge 後の別 chore PR (DA-14 convention)
