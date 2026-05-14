# 設計 — m9-c-adopt retrain v2 implementation

参照 spec: `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` §3 全節。
本 file は **本 PR の実装上の選択** のみ記録 (spec verbatim 再掲はしない)。

## アプローチ概要

PR #167 で landed した DA-14 spec を **TDD で実装** → G-GEAR overnight training
→ pilot recapture → DA-14 4 軸 intersection 判定。3 軸の追加 module + 既存
`train_kant_lora.py` の拡張で完結。

## 変更対象 (新規 + 既存)

### 新規ファイル

- `src/erre_sandbox/training/example_features.py`:
  per-row metric extraction の共有 module。
  - `classify_language(text) -> str` ("de"/"en"/"ja"/"mixed")
  - `count_markers(text) -> tuple[int, int]` (self_ref, kantian)
  - `estimate_token_count(text, *, use_real_tokenizer=False) -> int`
  - `extract_example_metadata(row, source_shard) -> dict`
  - これらは `scripts/analysis/analyze_kant_training_corpus.py` の private
    helpers を昇格 (DR-2 で flag されていた duplicate-risk の解消も兼ねる)。
- `src/erre_sandbox/training/weighting.py`:
  - `compute_example_weight(metadata) -> float` (design-final.md §3.2 verbatim)
  - `normalise_weights_to_mean_one(raw) -> list[float]`
  - `emit_weight_audit(weights, metadata, output_path) -> dict`
  - `WEIGHT_CLAMP_MIN = 0.1`, `WEIGHT_CLAMP_MAX = 3.0`
- `tests/test_training/test_weighting.py` (5 case)
- `tests/test_training/test_weighted_trainer.py` (2 case)

### 既存ファイル拡張

- `src/erre_sandbox/training/dataset.py`:
  - `build_weighted_examples(rows, persona_id) -> list[{"text", "weight_metadata"}]`
    既存 filter chain 同一 + per-example metadata 付与
- `src/erre_sandbox/training/train_kant_lora.py`:
  - `--weighted` CLI flag
  - `WeightedTrainer(transformers.Trainer)` class + `compute_loss` override
    (codex HIGH-C verbatim code sketch)
  - `_collect_from_shards_weighted()` (新 helper、既存 `_collect_from_shards` は不変)
    - group-aware 90/10 split (seed=42、stratified by source_shard_type)
    - monolog re-cast (train_groups のみ、natural shards から Kant 連続 2 turn 抽出)
    - hard-fail assert `len(set(train_dialog_ids) & set(eval_dialog_ids)) == 0`
  - Pre-training audit (`weight-audit.json` 出力、fallback trigger 判定)
  - train_metadata.json 新 fields: `weighted`, `weight_audit_path`,
    `synthetic_monolog_n`, `eval_split_size`, `train_dialog_ids_n`, `eval_dialog_ids_n`
  - exit code 6 (N_eff fallback) / 7 (top-5% concentration fallback) 追加

## 設計上の選択

### S-1: `example_features.py` を src/ に新設し scripts/analysis から refactor

- **背景**: codex-review.md MEDIUM-1 で "analyse script が build_examples を
  mirror している → DR-2 で maintenance risk を記録すべき" と指摘済。
  本 PR で training 側に同 metric (language / tokens / marker) を持ち込むと
  ことを **三重重複** になるため、src/ 共有 module 化で **decay risk を縮減**。
- **採用**: 新規 `src/erre_sandbox/training/example_features.py` に共有 helper
  を昇格。scripts/analysis/analyze_kant_training_corpus.py は import 経路へ
  refactor (内部 helpers は public alias で互換維持)。
- **代替案**:
  - A: weighting.py に duplicate (refactor 不要だが decay risk 増)
  - B: scripts/ 配下に共通モジュール (scripts/ は package 化されていない)
- **トレードオフ**: 本 PR の変更面積が ~50 行増 (refactor)、ただし
  long-term maintenance risk が大幅に縮む。

### S-2: group split の uniqueness key は `(source_shard, dialog_id)` の複合

- **背景**: 異なる shard で同一 `dialog_id` 値が再利用される可能性は低いが
  ゼロではない (各 shard は独立 driver run)。安全側で複合 key。
- **採用**: `group_key = (source_shard, dialog_id)` で group 化、
  `numpy.random.default_rng(42)` で 90/10 random split、
  stratification は `source_shard_type` ("natural"/"stimulus") で 2 層。
- **assert**: train ↔ eval の `(source_shard, dialog_id)` 集合は disjoint
  かつ monolog re-cast 後も unaffected (train_groups からのみ生成、
  `<orig>_mono` で record されるが group_key は元 dialog_id 由来)。

### S-3: monolog re-cast detection

- **入力**: 全 raw_dialog 行 (`speaker_persona_id != "kant"` も含む)、
  natural shards のみ (source_shard_type == "natural")
- **検出**: 同 dialog 内で `turn_index` 連続する 3 turn (t=k, t=k+1, t=k+2) のうち
  t=k と t=k+2 で `speaker_persona_id == "kant"`、t=k+1 で
  `speaker_persona_id != "kant"` のパターン。
- **生成**: `t=k.utterance + " " + t=k+2.utterance` を結合、`addressee=None`、
  `dialog_id = f"{orig_dialog_id}_mono"`、metadata に
  `synthetic_source_dialog_id`, `synthetic_source_turn_indices=[k, k+2]`,
  `synthesised_at_commit=<git_sha>` を付与。
- **cap**: ~150-300 rows (spec §3.3 範囲内)、natural train_groups の Kant 連続
  2-turn pair 数に依存 (Step 1 corpus で natural=2502、monolog 0% から推定)。
- **eval split 隔離**: monolog re-cast は **train_groups のみ** から派生し、
  train split に追加 (eval split には絶対に出ない)。

### S-4: pre-training audit を training kickoff の直前に置く

- **理由**: weight 分布が pathological (top 5% に過集中、ja heavy など)
  なら training 3-5h を消費する前に STOP する。Codex HIGH-A #2 要件。
- **出力**: `data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json` に
  per-lang mass / top 5% share / N_eff / bucket histogram を json で書く。
- **exit code 6** (N_eff < 1000): `InsufficientEffectiveSampleSizeError`
  (新 exception、`exceptions.py` 追加)
- **exit code 7** (top 5% ≥ 0.50): `WeightConcentrationError`
  (新 exception、`exceptions.py` 追加)
- **soft warning** (de+en < 0.60): `_LOGGER.warning(...)` のみ、continue training

### S-5: HF Trainer integration の最小化

- **方針**: `Trainer` を override せず `WeightedTrainer(Trainer)` で
  `compute_loss` だけ override。それ以外 (data collator、optimiser、scheduler) は
  既存 `_run_trainer` パスを使い回し。
- **weight column 注入**: `tokenizer.map(_tokenize, batched=True)` の中で
  `encoded["sample_weight"] = ...` を併載。`DataCollatorForLanguageModeling`
  は未知 column を自動 pass-through するため、特殊 collator は不要。
  (codex HIGH-C #1 の `inputs.pop("sample_weight")` で消費)
- **eval split**: `eval_dataset` を渡し、`evaluation_strategy="steps"` +
  `eval_steps=500` で loss-only eval (HIGH-B guard)。eval split は
  `sample_weight=1.0` 一律 (un-weighted) で監視。
- **early stopping**: `EarlyStoppingCallback` は本 PR 対象外 (spec §3.5 で
  `save_steps=500 → 8 checkpoints` と明示、early stopping は scope 外)。
  ただし overfit detection は eval_loss 推移を `train_metadata.json` に記録。

## テスト戦略

### TDD 順序

1. `tests/test_training/test_weighting.py` (pure functions、依存ゼロ、最速):
   - `test_compute_example_weight_clamp_range_upper`
   - `test_compute_example_weight_kantian_de_120tok_monolog_max_marker`
   - `test_compute_example_weight_ja_short_dialog_zero_marker`
   - `test_normalise_weights_to_mean_one_preserves_relative_order`
   - `test_emit_weight_audit_reports_lang_mass_and_n_eff`
2. `tests/test_training/test_weighted_trainer.py` (torch fixture が必要):
   - `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`
   - `test_weighted_trainer_compute_loss_handles_label_minus_100`
3. (任意、本 PR 範囲外: monolog re-cast detection / group split 隔離テスト
   は `test_train_kant_lora.py` に追記検討、time-budget 次第で defer)

### CI 互換性

- `torch` は `[training]` extras。`test_weighted_trainer.py` は torch import を
  module top-level でなく lazy にし、`pytest.importorskip("torch")` で
  CI default profile では skip 可能に。
- `test_weighting.py` は stdlib のみで完結 (numpy も使わない)。

## 影響範囲

- `src/erre_sandbox/training/{__init__.py, dataset.py, train_kant_lora.py,
  exceptions.py, example_features.py (new), weighting.py (new)}`
- `tests/test_training/{test_weighting.py (new), test_weighted_trainer.py (new)}`
- `scripts/analysis/analyze_kant_training_corpus.py` (import 経路 refactor、
  外部 API は不変)
- `data/lora/m9-c-adopt-v2/kant_r8_v2/` (新ディレクトリ、artefact 生成)
