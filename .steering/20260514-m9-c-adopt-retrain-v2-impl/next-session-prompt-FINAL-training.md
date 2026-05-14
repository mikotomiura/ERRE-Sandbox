# Next-session 開始プロンプト — m9-c-adopt retrain v2 **training kickoff + verdict**

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)
**前提**:
- 本 PR (`feature/m9-c-adopt-retrain-v2-implementation`、WeightedTrainer
  + group split + monolog re-cast + audit 実装 + 41/41 test green) が
  **merge 済**
- pre-training audit (dry-run、proxy tokenizer) PASS:
  N_eff=3560.9 / top 5%=15.4% / de+en=50.1% (soft warning)
**branch**: 新規 `feature/m9-c-adopt-retrain-v2-train-execution` を **main**
から切る (training 実行 + recapture + ADOPT/REJECT 判定のみ、コード変更ゼロ
想定)
**compute**: G-GEAR overnight 5-7h (envelope **8h** abort)

---

```
M9-C-adopt retrain v2 **training execution + multi-turn pilot recapture +
DA-14 4 軸 intersection 判定** を実行する。本セッションは **コード変更ゼロ**、
landed 済 implementation を起動して artefacts + verdict を生成するだけ。

## 目的 (本セッション、G-GEAR overnight ~6h)

1. **Real-tokenizer pre-training audit** (~10 min):
   - `python -m erre_sandbox.training.train_kant_lora \\
       --duckdb-glob "data/eval/golden/kant_*.duckdb" \\
       --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/ \\
       --rank 8 --max-steps 4000 --weighted --dry-run -v`
   - **real Qwen3-8B tokenizer** で weight 再計算 (proxy 結果と比較)
   - `data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json` を inspect
   - fallback trigger 確認: N_eff >= 1000 / top 5% <= 0.50 (DA-14)
2. **Training execution** (~3-5h、G-GEAR overnight):
   - `python -m erre_sandbox.training.train_kant_lora \\
       --duckdb-glob "data/eval/golden/kant_*.duckdb" \\
       --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/ \\
       --rank 8 --max-steps 4000 --weighted -v`
   - peak VRAM 監視、12GB safety margin 維持
   - save_steps=500 → 8 checkpoints、最終のみ archive
3. **Multi-turn pilot recapture** (~1h):
   - `bash scripts/m9-c-adopt/launch_sglang_icc.sh --max-lora-rank 8`
   - `bash scripts/m9-c-adopt/multi_pin_sanity.sh \\
       --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/`
   - `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \\
       --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ \\
       --multi-turn-max 6 --max-focal-per-shard 300 \\
       --output .steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
   - `python scripts/m9-c-adopt/validate_multiturn_shards.py \\
       --output .steering/<task>/validation-v2-kant.json` (8/8 PASS 必須)
4. **Consumer + matrix + verdict** (~30 min):
   - Vendi/Burrows/ICC consumer 実行 (no-LoRA SGLang baseline 再利用)
   - `python scripts/m9-c-adopt/da1_matrix_multiturn.py \\
       --thresholds-file .steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json \\
       --persona kant --output .steering/<task>/da1-matrix-v2-kant.json`
   - DA-14 4 軸 intersection (kant quorum 2-of-3):
     - Vendi semantic Cohen's d <= -0.5 (point + CI upper < 0)
     - Burrows reduction >= 5% (point + CI lower > 0)
     - ICC(A,1) >= 0.55 (point + CI lower >= 0.50)
     - throughput >= 70%
   - **ADOPT** verdict → Phase E A-6 handoff (multi-turn full Tier B 7500-turn)
   - **REJECT** verdict → DA-15 ADR 起票 (Vendi kernel swap or Candidate C escalate)
   - **HIGH-3 禁止**: post-hoc threshold movement は禁止

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` ←
   本 PR の implementation 経緯 + DI-4 (proxy audit 結果)
2. `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` §3 全節
3. `.steering/20260513-m9-c-adopt/decisions.md` DA-14
4. `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
5. `.steering/20260514-m9-c-adopt-pilot-multiturn/` の no-LoRA SGLang baseline 5 artefacts

## NOT in scope (本セッション)

- コード変更 (本 PR で landed 済)
- nietzsche / rikyu の retrain v2 (Phase C、kant ADOPT 後)
- Candidate C targeted hybrid 採取 (fallback 発火時のみ別 PR で実行)
- DA-15 ADR 起票 (REJECT 確定時に別 PR で)
- Phase E A-6 (ADOPT 後、別 overnight session)

## 完了条件

- [ ] `feature/m9-c-adopt-retrain-v2-train-execution` branch (main 派生)
- [ ] `.steering/[YYYYMMDD]-m9-c-adopt-retrain-v2-verdict/{requirement,design,
      decisions,blockers,tasklist}.md`
- [ ] real-tokenizer `weight-audit.json` 生成、N_eff / top 5% / de+en 記録
- [ ] `data/lora/m9-c-adopt-v2/kant_r8_v2/` artefacts (peak_vram + train_loss
      + eval_loss を train_metadata.json に記録)
- [ ] multi-turn pilot recapture (validation 8/8 PASS)
- [ ] `da1-matrix-v2-kant.json` (DA-14 thresholds 適用)
- [ ] ADOPT or REJECT verdict + `decisions.md` D-1 記録
- [ ] 次セッション handoff prompt:
      - ADOPT → Phase E A-6 (multi-turn full Tier B 7500-turn)
      - REJECT → DA-15 ADR 起票
- [ ] commit + push + `gh pr create` (training execution PR)
- [ ] DA-14 `trace.HEAD` を本 PR merge 後 SHA で埋め込み

## abort triggers

- training >7h かつ収束兆候なし → kill、checkpoint で部分評価
- multi-turn pilot validation 8/8 でない → STOP、redesign
- VRAM peak > 12GB → `gradient_accumulation` を 16 → 32
- exit 6 (N_eff < 1000) / exit 7 (top 5% >= 50%) → STOP、Candidate C escalate

## 既知の注意点

- **DI-4** (本 PR audit dry-run、proxy tokenizer):
  - de+en weighted mass = 0.501 (soft warning < 0.60)。training continue で OK だが、
    DA-14 4 軸 REJECT の場合 Candidate C escalate を強く検討
  - synthetic_monolog = 500 (hard_cap 到達)。Kant-N-Kant pair が 500 超
    検出された結果、subsample seed=42 で deterministic
- **Codex MEDIUM-1**: 本 audit は whitespace × 1.3 proxy。production training は
  必ず real Qwen3-8B tokenizer (`--no-real-tokenizer-for-weights` は **不指定**)
- **DA-13 教訓**: backend confound (Ollama vs SGLang) で direction failure が
  起こる。**同 backend (SGLang)** で apples-to-apples 比較
```
