# M9-C adopt retrain v2 — training execution + multi-turn pilot recapture + verdict

## 背景

`feature/m9-c-adopt-retrain-v2-implementation` (PR #168) で WeightedTrainer + group
split + monolog re-cast + audit が landed 済。pre-training audit (dry-run、proxy
tokenizer) で N_eff=3560.9 / top 5%=15.4% / de+en=50.1% (soft warning) を確認した
が、production training は real Qwen3-8B tokenizer で再計算する必要がある
(Codex MEDIUM-1)。

本 task で training を執行し、multi-turn pilot を recapture して DA-14 4 軸
intersection で ADOPT/REJECT を確定する。

## ゴール

1. real-tokenizer pre-training audit で N_eff / top 5% を再確認
2. Qwen3-8B + LoRA rank 8 weighted training (4000 steps、~3-5h on G-GEAR)
3. multi-turn Tier B pilot (kant、max_focal=300、multi_turn_max=6) を recapture
4. DA-14 4 軸 (Vendi semantic / Burrows / ICC / throughput) で ADOPT or REJECT
   verdict を確定し `decisions.md` D-1 に記録
5. 次セッション handoff prompt を生成 (ADOPT → Phase E A-6、REJECT → DA-15 ADR)

## スコープ

### 含むもの
- training execution (kant のみ、rank=8)
- multi-turn pilot recapture (kant のみ)
- Vendi / Burrows / ICC consumer 実行
- da1_matrix_multiturn.py で 4 軸判定
- ADOPT/REJECT verdict + handoff prompt

### 含まないもの
- コード変更 (本 task は execution + verdict のみ)
- nietzsche / rikyu の retrain v2 (Phase C、kant ADOPT 後)
- Candidate C targeted hybrid 採取 (fallback 発火時のみ別 PR)
- DA-15 ADR 起票 (REJECT 確定時に別 PR)
- Phase E A-6 (ADOPT 後、別 overnight session)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-retrain-v2-train-execution` branch (main 派生) で作業
- [ ] real-tokenizer `weight-audit.json` 生成、N_eff / top 5% / de+en 数値を
      decisions.md DI-5 で記録 (proxy 結果と比較)
- [ ] `data/lora/m9-c-adopt-v2/kant_r8_v2/` artefacts (peak_vram + train_loss +
      eval_loss を train_metadata.json に記録)
- [ ] multi-turn pilot recapture (validation 8/8 PASS、`validation-v2-kant.json`)
- [ ] `da1-matrix-v2-kant.json` (DA-14 thresholds 適用)
- [ ] ADOPT or REJECT verdict + `decisions.md` D-1 記録
- [ ] 次セッション handoff prompt 生成
- [ ] commit + push + `gh pr create`

## 関連ドキュメント

- `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` (DI-1〜DI-4)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` §3
- `.steering/20260513-m9-c-adopt/decisions.md` DA-14
- `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
- `.steering/20260514-m9-c-adopt-pilot-multiturn/` no-LoRA SGLang baseline artefacts
