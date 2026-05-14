# 要求仕様 — m9-c-adopt retrain v2 implementation + verdict

## 背景

PR #167 で `feature/m9-c-adopt-retrain-v2-design` (DA-14 ADR + corpus-analysis
+ Codex HIGH-A/B/C/D 反映 spec) が 2026-05-14 に main へ merged 済。
本 PR は **DA-14 spec の training + multi-turn pilot recapture + 4 軸 intersection
ADOPT/REJECT 判定** を G-GEAR overnight ~6h で完遂する。

参照:
- `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` (spec)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/codex-review.md` (HIGH 反映 guidance)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json` (機械可読 thresholds pin)
- `.steering/20260513-m9-c-adopt/decisions.md` DA-14

## ゴール (本セッション)

1. WeightedTrainer + signal weighting + group-aware split + monolog re-cast 実装
   (TDD、Codex HIGH-C verbatim code sketch 準拠)
2. Pre-training audit (weight-audit.json) + fallback trigger 判定
3. Training execution (max_steps=4000、weighted、rank=8) → `data/lora/m9-c-adopt-v2/kant_r8_v2/`
4. Multi-turn pilot recapture (`tier-b-pilot-multiturn-kant-r8-v2.duckdb`、validation 8/8 PASS)
5. Consumer (Vendi/Burrows/ICC、no-LoRA SGLang baseline 比較) + matrix + DA-14 4 軸 intersection
6. ADOPT/REJECT verdict + decisions.md D-1 記録 + 次セッション handoff prompt

## 受け入れ条件

- [ ] `feature/m9-c-adopt-retrain-v2-implementation` branch (main 派生)
- [ ] WeightedTrainer.compute_loss override 実装 (token CE reduction='none' → per-example mean → weighted sum / normaliser)
- [ ] weights normalised to mean=1.0 on train split (effective LR silent shift 防止)
- [ ] group-aware 90/10 split (seed=42、stratified by source_shard_type)
- [ ] monolog re-cast train_groups のみ (synthetic_source_dialog_id metadata + dialog_id="<orig>_mono")
- [ ] hard-fail assert `len(set(train_dialog_ids) & set(eval_dialog_ids)) == 0`
- [ ] `tests/test_training/test_weighting.py` 5 case green
- [ ] `tests/test_training/test_weighted_trainer.py` 2 case green
- [ ] ruff format + check + pytest green
- [ ] `weight-audit.json` 出力 (per-lang mass / top 5% / N_eff / bucket histogram)
- [ ] fallback trigger 判定 (N_eff < 1000 exit 6 / top 5% ≥ 50% exit 7 / de+en < 60% soft warning)
- [ ] training artefacts: `adapter_model.safetensors` + `adapter_config.json` + `train_metadata.json` (新 fields: weighted=True, weight_audit_path, synthetic_monolog_n, eval_split_size, train_dialog_ids_n, eval_dialog_ids_n)
- [ ] multi-turn pilot artefacts + validation 8/8 PASS
- [ ] `da1-matrix-v2-kant.json` (DA-14 thresholds 適用)
- [ ] ADOPT or REJECT verdict + per-axis 数値 + quorum 判定 + `decisions.md` D-1 記録
- [ ] 次セッション handoff prompt (ADOPT → Phase E A-6 / REJECT → DA-15 起票)
- [ ] commit + push + `gh pr create`
- [ ] DA-14 `trace.HEAD` を本 PR merge 後 SHA で埋め込み

## compute envelope

| Phase | 時間 |
|---|---|
| WeightedTrainer 実装 + tests | 30-45 min |
| Pre-training audit | 5 min |
| Training | 3-5h |
| Pilot recapture | 1h |
| Consumer + matrix | 30 min |
| **合計** | **5-7h** (envelope **8h** abort) |

## Abort triggers

- training >7h かつ収束兆候なし → kill、checkpoint で部分評価
- multi-turn pilot validation 8/8 でない → STOP、redesign
- VRAM peak > 12GB → gradient_accumulation 16 → 32 (それでも超過なら user 確認)
- N_eff fallback (exit 6) or top-5% fallback (exit 7) → STOP、Candidate C escalate
