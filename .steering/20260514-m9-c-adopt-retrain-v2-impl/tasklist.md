# タスクリスト — m9-c-adopt retrain v2 implementation

## Phase 1: 実装 (TDD、~30-45 min)

- [ ] `src/erre_sandbox/training/example_features.py` 新設
  - [ ] `classify_language`, `count_markers`, `estimate_token_count`,
        `extract_example_metadata` を analyse script から refactor
  - [ ] `MARKER_PATTERNS`, `LITERATURE_ANCHOR_DENSITY` 等の constants も移動
- [ ] `src/erre_sandbox/training/exceptions.py` 拡張
  - [ ] `InsufficientEffectiveSampleSizeError` (exit 6)
  - [ ] `WeightConcentrationError` (exit 7)
- [ ] `src/erre_sandbox/training/weighting.py` 新設
  - [ ] `compute_example_weight(metadata) -> float` (clamped [0.1, 3.0])
  - [ ] `normalise_weights_to_mean_one(raw) -> list[float]`
  - [ ] `emit_weight_audit(weights, metadata, output_path) -> dict`
- [ ] `src/erre_sandbox/training/dataset.py` 拡張
  - [ ] `build_weighted_examples(rows, persona_id, source_shard) -> list[dict]`
- [ ] `src/erre_sandbox/training/train_kant_lora.py` 拡張
  - [ ] `WeightedTrainer(Trainer)` + `compute_loss` override
  - [ ] `_collect_from_shards_weighted()` (group split + monolog re-cast)
  - [ ] `_pre_training_audit()` (weight-audit.json + fallback trigger)
  - [ ] `_execute_training_run_weighted()` (sample_weight 列を tokenizer.map で併載)
  - [ ] `--weighted` CLI flag
  - [ ] `train_metadata.json` 新 fields 追加
  - [ ] exit code 6/7 を `main()` に追加
- [ ] `scripts/analysis/analyze_kant_training_corpus.py` refactor
  - [ ] `example_features` import 経路に切り替え、test green 維持
- [ ] `tests/test_training/test_weighting.py` 新設 (5 case)
- [ ] `tests/test_training/test_weighted_trainer.py` 新設 (2 case)

## Phase 2: 検証 (~5-10 min)

- [ ] `uv run ruff format src/ tests/`
- [ ] `uv run ruff check src/ tests/`
- [ ] `uv run pytest tests/test_training/ tests/test_analysis/ -x`

## Phase 3: Pre-training audit (~5 min)

- [ ] `python -m erre_sandbox.training.train_kant_lora --duckdb-glob
      "data/eval/golden/kant_*.duckdb" --output-dir
      data/lora/m9-c-adopt-v2/kant_r8_v2/ --rank 8 --max-steps 4000
      --weighted --dry-run -v`
- [ ] `weight-audit.json` を inspect (N_eff ≥ 1500、top 5% ≤ 0.35、
      de+en ≥ 0.60 を確認)
- [ ] fallback trigger 発火時: STOP + `decisions.md` D-1 記録

## Phase 4: Training execution (3-5h overnight)

- [ ] `python -m erre_sandbox.training.train_kant_lora ... --weighted -v` (full run)
- [ ] nvidia-smi で peak VRAM 監視 (12GB safety margin)
- [ ] checkpoints `data/lora/m9-c-adopt-v2/kant_r8_v2/checkpoint-*` 確認
- [ ] `train_metadata.json` 出力確認 (weighted=True、loss、peak_vram)

## Phase 5: Pilot recapture (~1h)

- [ ] `bash scripts/m9-c-adopt/launch_sglang_icc.sh --max-lora-rank 8`
- [ ] `bash scripts/m9-c-adopt/multi_pin_sanity.sh --adapter
      data/lora/m9-c-adopt-v2/kant_r8_v2/`
- [ ] `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8
      --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ --multi-turn-max 6
      --max-focal-per-shard 300 --output
      .steering/20260514-m9-c-adopt-retrain-v2-impl/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
- [ ] `python scripts/m9-c-adopt/validate_multiturn_shards.py --output
      .steering/20260514-m9-c-adopt-retrain-v2-impl/validation-v2-kant.json`
      (8/8 PASS 必須)

## Phase 6: Consumer + matrix + verdict (~30 min)

- [ ] Vendi semantic / Burrows / ICC consumer 実行
- [ ] `python scripts/m9-c-adopt/da1_matrix_multiturn.py
      --thresholds-file
      .steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json
      --persona kant --output
      .steering/20260514-m9-c-adopt-retrain-v2-impl/da1-matrix-v2-kant.json`
- [ ] DA-14 4 軸 intersection 判定 (kant quorum 2-of-3):
  - Vendi semantic Cohen's d ≤ -0.5 (point + CI upper < 0)
  - Burrows reduction ≥ 5% (point + CI lower > 0)
  - ICC(A,1) ≥ 0.55 (point + CI lower ≥ 0.50)
  - throughput ≥ 70%
- [ ] verdict: ADOPT or REJECT
- [ ] `decisions.md` D-1 記録 (per-axis 数値 + quorum + verdict)

## Phase 7: PR + handoff (~15 min)

- [ ] commit + push
- [ ] `gh pr create --title "feat(adopt): m9-c-adopt — retrain v2
      implementation + verdict"`
- [ ] 次セッション handoff prompt 作成:
  - ADOPT → `next-session-prompt-phase-e-a6.md` (Phase E A-6 multi-turn full
    Tier B 7500-turn)
  - REJECT → `next-session-prompt-da15.md` (DA-15 ADR 起票、Vendi kernel
    swap or Candidate C escalate)
- [ ] DA-14 `trace.HEAD` を本 PR merge 後 SHA で埋め込み
      (`.steering/20260513-m9-c-adopt/decisions.md`)
