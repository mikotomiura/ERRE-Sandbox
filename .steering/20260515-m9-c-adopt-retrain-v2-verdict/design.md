# 設計 — retrain v2 training execution + verdict

## 実装アプローチ

**コード変更ゼロ**。本 task は landed 済 implementation の execution + artefact
生成 + verdict 判定のみ。

## 実行手順 (sequential、G-GEAR overnight ~6h)

### Phase 1: real-tokenizer audit (~10 min)
```bash
python -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob "data/eval/golden/kant_*.duckdb" \
    --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/ \
    --rank 8 --max-steps 4000 --weighted --dry-run -v
```
- `--no-real-tokenizer-for-weights` は **不指定** (real Qwen3-8B tokenizer 使用)
- inspect `weight-audit.json`:
  - N_eff >= 1000 (fallback trigger、DA-14)
  - top 5% <= 0.50 (fallback trigger、DA-14)
  - de+en weighted mass: 観測のみ (DI-4 proxy 0.501 と比較)

### Phase 2: training execution (~3-5h)
```bash
python -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob "data/eval/golden/kant_*.duckdb" \
    --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/ \
    --rank 8 --max-steps 4000 --weighted -v
```
- peak VRAM 監視 (12GB safety margin)
- save_steps=500 → 8 checkpoints、最終のみ archive
- abort: training >7h かつ収束兆候なし

### Phase 3: multi-turn pilot recapture (~1h)
```bash
bash .steering/20260513-m9-c-adopt/phase-b-logs/launch_sglang_icc.sh \
    --max-lora-rank 8
bash .steering/20260513-m9-c-adopt/phase-b-logs/multi_pin_sanity.sh \
    --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/
python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \
    --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ \
    --multi-turn-max 6 --max-focal-per-shard 300 \
    --output .steering/20260515-m9-c-adopt-retrain-v2-verdict/tier-b-pilot-multiturn-kant-r8-v2.duckdb
python scripts/m9-c-adopt/validate_multiturn_shards.py \
    --output .steering/20260515-m9-c-adopt-retrain-v2-verdict/validation-v2-kant.json
```
- validation 8/8 PASS 必須、不足なら STOP & redesign

### Phase 4: consumer + matrix + verdict (~30 min)
- Vendi semantic / Burrows / ICC(A,1) consumer 実行
  (no-LoRA SGLang baseline `.steering/20260514-m9-c-adopt-pilot-multiturn/` 再利用)
- `da1_matrix_multiturn.py --thresholds-file <DA-14 recalibrated>` で 4 軸判定
- ADOPT/REJECT を `decisions.md` D-1 に verbatim 埋め

## DA-14 4 軸 intersection (kant quorum 2-of-3)

- Vendi semantic Cohen's d <= -0.5 (point + CI upper < 0)
- Burrows reduction >= 5% (point + CI lower > 0)
- ICC(A,1) >= 0.55 (point + CI lower >= 0.50)
- throughput >= 70%

**HIGH-3 禁止**: post-hoc threshold movement 禁止。ADOPT/REJECT 判定後に
thresholds を緩めるのは DA-15 起票が正路。

## abort triggers

- training >7h かつ収束兆候なし → kill、checkpoint で部分評価
- multi-turn pilot validation 8/8 でない → STOP、redesign
- VRAM peak > 12GB → `gradient_accumulation` を 16 → 32
- exit 6 (N_eff < 1000) / exit 7 (top 5% >= 50%) → STOP、Candidate C escalate

## artefact 配置

- `data/lora/m9-c-adopt-v2/kant_r8_v2/` — LoRA adapter + train_metadata.json
- `data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json` — real-tokenizer audit
- `.steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb` — pilot output
- `.steering/<task>/validation-v2-kant.json` — 8/8 validation
- `.steering/<task>/da1-matrix-v2-kant.json` — 4 軸数値

## ロールバック計画

- training abort → checkpoint で部分評価して decisions.md に記録、PR は draft 維持
- multi-turn pilot 失敗 → no commit、redesign task
- VRAM OOM → grad_accum 32 で retry (1 回のみ)
