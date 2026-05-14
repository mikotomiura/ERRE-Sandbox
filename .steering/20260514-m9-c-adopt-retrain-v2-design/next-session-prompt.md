# Next-session prompt — m9-c-adopt retrain v2 implementation + re-evaluation

**用途**: 新セッション最初に貼り付け
**前提**: 本 design PR (`feature/m9-c-adopt-retrain-v2-design`) merge 済
**branch**: 新規 `feature/m9-c-adopt-retrain-v2-implementation` を main から
切る

---

```
M9-C-adopt の **retrain v2 implementation + multi-turn pilot recapture +
DA-14 4 軸 intersection 再評価** を実行する。本 design PR で DA-14 ADR
(signal-driven retrain v2 spec + re-calibrated thresholds vs no-LoRA
SGLang baseline) と Codex review HIGH 4 件反映 spec が確定済。本セッションは
training kick-off → recapture → ADOPT/REJECT 判定までを overnight ~6h で
完遂する。

## 目的 (本セッション、G-GEAR overnight ~6h)

1. **WeightedTrainer 実装** (~30 min、TDD で先に test):
   - `src/erre_sandbox/training/dataset.py` に `build_weighted_examples()`
     adapter 追加 (`{"text": chatml, "weight": float, "weight_metadata": {...}}`)
   - `src/erre_sandbox/training/weighting.py` 新規: `compute_example_weight()`
     関数 + normalisation + weight-audit emitter
   - `src/erre_sandbox/training/train_kant_lora.py` に `WeightedTrainer`
     (Trainer subclass) を追加、`compute_loss` を override
   - group-aware split + monolog re-cast ロジック追加
   - tests: `tests/test_training/test_weighting.py` (5 case 程度)、
     `tests/test_training/test_weighted_trainer.py` (compute_loss 単体)
2. **Pre-training audit** (~5 min):
   - `weight-audit.json` 出力 (per-lang weighted mass / top 5% weight
     share / N_eff)
   - DA-14 fallback trigger 判定 (N_eff < 1000 OR top 5% ≥ 50% → Candidate
     C へ escalate、本 PR 完遂は別経路)
3. **Training execution** (~3-5h、G-GEAR overnight):
   - `python -m erre_sandbox.training.train_kant_lora \
       --duckdb-glob "data/eval/golden/kant_*.duckdb" \
       --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/ \
       --rank 8 --max-steps 4000 --weighted` (新 flag)
   - peak VRAM 監視、12GB safety margin 維持
   - checkpoint cadence save_steps=500、`save_total_limit=2`
4. **Multi-turn pilot recapture** (~1h):
   - `bash scripts/m9-c-adopt/launch_sglang_icc.sh --max-lora-rank 8`
     (新 adapter pin)
   - `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \
       --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ \
       --multi-turn-max 6 --output .steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
   - validation gate: `python scripts/m9-c-adopt/validate_multiturn_shards.py`
     (HIGH-4 acceptance、8/8 PASS 必須)
5. **Consumer + matrix** (~30 min):
   - Vendi/Burrows/ICC 算出 (既存 consumer reuse、no-LoRA SGLang baseline
     artefacts reuse)
   - `python scripts/m9-c-adopt/da1_matrix_multiturn.py \
       --thresholds-file .steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json \
       --persona kant --output .steering/<task>/da1-matrix-v2-kant.json`
6. **ADOPT / REJECT 判定**:
   - DA-14 4 軸 intersection (kant quorum 2-of-3): Vendi d ≤ -0.5、
     Burrows ≥ 5%、ICC(A,1) ≥ 0.55、throughput ≥ 70%
   - ADOPT 確定 → Phase E A-6 (multi-turn full Tier B 7500-turn) 経路
   - REJECT (1 axis quorum 未達) → DA-15 起票 (Vendi kernel swap or
     Candidate C targeted hybrid に escalate)
   - 採用判定を本 PR `decisions.md` D-1 に記録

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` — **本セッションの execution spec**、§3 全節 (Codex HIGH 反映済)
2. `.steering/20260513-m9-c-adopt/decisions.md` **DA-14** (本 retrain v2 spec ADR + thresholds)
3. `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.md` — 4 gap finding (weighting design の根拠)
4. `.steering/20260514-m9-c-adopt-retrain-v2-design/codex-review.md` — HIGH 反映の operational guidance、特に WeightedTrainer 実装 sketch
5. `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json` — 機械可読 thresholds pin
6. `.steering/20260514-m9-c-adopt-retrain-v2-design/decisions.md` DR-1 / DR-2 (signal-driven + Codex 反映)
7. `data/lora/m9-c-adopt/archive/rank_8/kant/train_metadata.json` — 現 rank=8 baseline (peak_vram=10.55GB / train_loss=0.2155 / max_steps=2000、本セッションで 2x scaling)
8. `src/erre_sandbox/training/{dataset,train_kant_lora,prompt_builder}.py` — 改修対象 + 同 setup を継承

## scope

### 1. Training data + weighting + group split (~30-45 min、TDD)

- 新規 `src/erre_sandbox/training/weighting.py`:
  - `compute_example_weight(metadata: dict) -> float`
    (design-final.md §3.2 verbatim)
  - `normalise_weights_to_mean_one(raw: list[float]) -> list[float]`
  - `emit_weight_audit(weights, metadata) -> dict` (per-lang mass / top 5% /
    N_eff / bucket histogram)
- `dataset.py` に `build_weighted_examples()` adapter (raw_dialog rows →
  list of `{"text", "weight", "weight_metadata"}`)
- `train_kant_lora.py` の `_collect_from_shards()` 拡張:
  - `(source_shard, dialog_id)` group 化 + 90/10 split (seed=42、stratified
    by `source_shard_type`)
  - monolog re-cast (training group の natural shards から Kant 連続 2 turn
    結合、~150-300 examples)
  - `assert len(set(train_dialog_ids) & set(eval_dialog_ids)) == 0` hard-fail
- `WeightedTrainer(Trainer).compute_loss` override
  (design-final.md §3.2 verbatim code sketch)

### 2. Pre-training audit + fallback trigger (~5 min)

- `weight-audit.json` 出力: per-lang weighted mass / top 5% weight share /
  N_eff = (Σw)²/Σw²
- DA-14 fallback trigger 判定:
  - N_eff < 1,000 → STOP、Candidate C へ escalate (本 PR 完遂しない、
    別 PR で targeted hybrid 採取)
  - top 5% weight share ≥ 50% → 同上
  - de+en weighted mass < 60% → soft warning (training は継続、log に記録)
- 各 trigger は CLI exit code で区別:
  - 6 = N_eff fallback
  - 7 = top-5% concentration fallback

### 3. Training execution (~3-5h G-GEAR overnight)

- CLI: `python -m erre_sandbox.training.train_kant_lora` に
  `--weighted` flag を追加。flag ON で weighted path:
  - `_collect_from_shards` → group split → monolog re-cast → weight 計算 →
    `weight-audit.json` 出力 → WeightedTrainer で training
- output: `data/lora/m9-c-adopt-v2/kant_r8_v2/`
  - `adapter_model.safetensors`, `adapter_config.json`, `train_metadata.json`
    (新 fields: `weighted=True`, `weight_audit_path`, `synthetic_monolog_n`,
    `eval_split_size`)
- VRAM 監視: 12GB safety margin 維持、超過時は `gradient_accumulation` を
  16 に上げる (effective batch 同一)
- save_steps=500 → 8 checkpoints、最終のみ archive

### 4. Multi-turn pilot recapture (~1h)

- SGLang server 起動: `bash scripts/m9-c-adopt/launch_sglang_icc.sh
  --max-lora-rank 8`
- adapter pin: `bash scripts/m9-c-adopt/multi_pin_sanity.sh \
    --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/`
- pilot 採取: `python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --rank 8 --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ \
    --multi-turn-max 6 --max-focal-per-shard 300 --output ...`
  (matched baseline downsampling 300、HIGH-2 protocol)
- validation gate: `python scripts/m9-c-adopt/validate_multiturn_shards.py \
    --output .steering/<task>/validation-v2-kant.json` (8/8 PASS 必須、
  HIGH-4 acceptance)

### 5. Consumer + matrix + verdict (~30 min)

- Vendi semantic + Burrows + ICC consumer を本 PR の no-LoRA SGLang
  baseline artefact (`tier-b-pilot-multiturn-kant-nolora-*.json`) と比較
- da1_matrix_multiturn.py で 4 軸 intersection 自動判定:
  - thresholds: `da1-thresholds-recalibrated.json`
  - output: `da1-matrix-v2-kant.json` (scenario + per-axis verdict)
- ADOPT verdict 4 axis すべて pass + quorum 2-of-3:
  - kant ADOPT 確定 → Phase E A-6 経路、`decisions.md` D-1 記録
- REJECT verdict:
  - DA-15 起票 (Vendi kernel swap or Candidate C escalate)
  - DA-1 thresholds 再調整は NOT (HIGH-3 post-hoc movement 禁止)

## NOT in scope (本セッション)

- nietzsche / rikyu の同 retrain v2 (Phase C、kant ADOPT 後)
- Phase D (`MultiBackendChatClient`)
- Phase E A-6 (本セッション ADOPT 後の overnight run)
- production placement (Phase F)
- Candidate C targeted hybrid 採取 (fallback trigger 発火時のみ別 PR で実行)
- DA-15 ADR 起票 (REJECT 確定時に別 PR で)

## compute envelope + abort criteria

| Phase | 時間 |
|---|---|
| WeightedTrainer 実装 + tests | ~30-45 min |
| Pre-training audit | ~5 min |
| Training | 3-5h |
| Pilot recapture | 1h |
| Consumer + matrix | 30 min |
| **合計** | **5-7h** (envelope **8h**) |

**Abort triggers**:
- training >7h かつ収束兆候なし → kill、checkpoint で部分評価
- multi-turn pilot validation 8/8 でない → STOP、redesign
- Vendi/Burrows direction が proper baseline 比で再 fail → DA-15 escalate
- VRAM peak > 12GB → gradient_accumulation を 16 に上げて retry、それでも
  超過なら rank=4 に下げて smaller run (本来 spec から逸脱、決定は user 確認)

## 注意 (incident 教訓 + 既知の落とし穴)

- **DA-13 教訓**: backend confound (Ollama vs SGLang) で direction failure
  が起こる。本 PR 以降の評価は必ず **同 backend (SGLang)** で apples-to-apples
  比較 (Ollama baseline は historical reference only)
- **Codex HIGH-C 訂正**: HF Trainer は `sample_weight` を自動 consume しない。
  WeightedTrainer の `compute_loss` override が必須 (design-final.md §3.2)
- **Codex MEDIUM-3 注意**: monolog re-cast は **training group のみ**、
  eval split は monolog 含めない。`assert len(set(train_dialog_ids) &
  set(eval_dialog_ids)) == 0` hard-fail
- **HIGH-3 post-hoc threshold movement 禁止**: ADOPT/REJECT 判定後に
  thresholds を緩めるのは禁止。DA-15 起票で正式 amend するのが正路
- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止

## 完了条件 (本セッション = training + recapture + verdict)

- [ ] `feature/m9-c-adopt-retrain-v2-implementation` branch
- [ ] WeightedTrainer + weighting + group split 実装 (test green)
- [ ] `weight-audit.json` 出力、fallback trigger 判定 (継続 / escalate)
- [ ] `data/lora/m9-c-adopt-v2/kant_r8_v2/` artefacts (peak_vram /
      train_loss 記録)
- [ ] multi-turn pilot recapture (`tier_b_pilot.py --rank 8 v2 adapter`、
      validation 8/8 PASS)
- [ ] `da1-matrix-v2-kant.json` (DA-14 thresholds 適用、scenario 判定)
- [ ] ADOPT or REJECT verdict + `decisions.md` D-1 記録
- [ ] 次セッション handoff prompt (ADOPT → Phase E A-6、REJECT → DA-15)
- [ ] commit + push + `gh pr create` (training PR、本 PR の design とは別)

## 参照

- design: `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md`
- DA-14: `.steering/20260513-m9-c-adopt/decisions.md`
- thresholds pin: `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
- corpus finding: `.steering/20260514-m9-c-adopt-retrain-v2-design/corpus-analysis-kant.md`
- codex review: `.steering/20260514-m9-c-adopt-retrain-v2-design/codex-review.md`
- no-LoRA SGLang baseline artefacts:
  `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`

まず **DA-14 ADR + design-final.md §3 (signal weighting + WeightedTrainer +
group split + monolog re-cast)** を完全に内面化し、本セッションの **目的が
"DA-14 spec の training + recapture + ADOPT/REJECT 判定"** であることを
理解した上で Step 1 (WeightedTrainer 実装、TDD) から着手する。
コンテキスト使用率 50% 超で `/smart-compact` で区切る。

本セッション完了後、ADOPT なら Phase E A-6 (multi-turn full Tier B
7500-turn) を fire、REJECT なら DA-15 ADR 起票 (Vendi kernel swap or
Candidate C targeted hybrid escalate) で経路修正。
```
