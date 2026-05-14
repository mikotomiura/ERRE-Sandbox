# 重要な設計判断 — m9-c-adopt retrain v2 implementation

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-15) は `.steering/20260513-m9-c-adopt/decisions.md` に
> 追記する (immutable append convention)。

## DI-1: example_features.py で metric helpers を src/ に昇格

- **判断日時**: 2026-05-14
- **背景**: codex-review.md MEDIUM-1 が "scripts/analysis/analyze_kant_training_corpus.py
  は build_examples を mirror している" と指摘。本 PR で training 側に同 metric
  (language / tokens / marker) を持ち込むと **三重重複** になる。
- **選択肢**:
  - A: weighting.py に duplicate (refactor ゼロ、decay risk 増)
  - B: scripts/ 配下に共通モジュール (package 化されていない、import 経路が
    破綻するリスク)
  - C: `src/erre_sandbox/training/example_features.py` に昇格、analyse script を
    refactor (本 PR 変更面積 +50 行、long-term decay risk 縮小)
- **採用**: C
- **トレードオフ**: 変更面積増、ただし MEDIUM-1 で flag 済の maintenance risk
  を解消し、本 PR で導入する weight metadata pipeline と analyse script が
  literally 同じコードを参照する保証が得られる。

## DI-2: group split key is composite `(source_shard, dialog_id)`

- **判断日時**: 2026-05-14
- **背景**: 異なる shard で同一 `dialog_id` 値が再利用される可能性がゼロでは
  ない (各 shard は独立 driver run)。
- **採用**: `group_key = (source_shard, dialog_id)` で group 化、
  `numpy.random.default_rng(42)` で 90/10 random split、
  stratification は `source_shard_type` ("natural"/"stimulus") で 2 層。
- **理由**: safety-first。複合 key で eval ↔ train の `dialog_id` 衝突を
  ゼロ保証。
- **assert**: `len(set(train_group_keys) & set(eval_group_keys)) == 0` を
  hard-fail で確認。

## DI-3: synthetic monolog の cap と provenance

- **判断日時**: 2026-05-14
- **背景**: spec §3.3 で "~150-300 synthetic monolog examples" とあるが、
  natural train_groups の Kant 連続 2-turn pair 数に依存し上限不明。
- **採用**: cap は **`hard_cap = 500`** で safety net、実際の生成数は
  pair 検出結果に従う (~150-300 想定)。実数が cap を超える場合は
  `numpy.random.default_rng(42).choice` で seed-stable に sub-sample。
- **provenance**:
  - `dialog_id = f"{orig_dialog_id}_mono"`
  - `synthetic_source_dialog_id = orig_dialog_id`
  - `synthetic_source_turn_indices = [k, k+2]`
  - `synthesised_at_commit = <git_sha>` (subprocess `git rev-parse HEAD`)
  - `addressee = None`
- **理由**: cap は spec 値より緩めに置き、検出結果を尊重する。実数が
  ~150-300 から大きく外れた場合は `weight-audit.json` に記録し
  blockers.md で defer 判定。

## DI-4: Pre-training audit 結果 (dry-run、whitespace proxy tokenizer)

- **判断日時**: 2026-05-14
- **CLI**: `python -m erre_sandbox.training.train_kant_lora --duckdb-glob
  "data/eval/golden/kant_*.duckdb" --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/
  --rank 8 --max-steps 4000 --weighted --dry-run --no-real-tokenizer-for-weights -v`
- **結果** (`data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json`):
  - realised_examples = **5022** (Step 1 corpus と一致)
  - synthetic_monolog_n = **500** (hard_cap 到達、natural shards から Kant-N-Kant
    pair が 500 超検出 → subsample seed=42 で deterministic)
  - eval_split_size = **503**
  - train_dialog_ids = **2562**, eval_dialog_ids = **285** (disjoint hard-fail assert PASS)
  - **N_eff = 3560.9** ✅ (DA-14 fallback trigger 1000 を遥かに上回り、target 1500 も超過)
  - **top 5% weight share = 0.154** ✅ (DA-14 fallback trigger 0.50 を遥かに下回り、target 0.35 も下回り)
  - **de+en weighted mass = 0.501** ⚠️ (soft warning threshold 0.60 を下回るが training は継続、
    decisions.md D-1 で記録)
- **判定**: Candidate B (signal-driven、DR-1) で training continue。Candidate C
  escalate は不要。
- **soft warning の解釈**: corpus 構造 (ja=56.7%、en=25.8%、de=15.9%) で
  ja を 0.2x、en を 1.0x、de を 1.4x で重み付けしても de+en 合計が 50% 程度に
  留まる。これは Step 1 corpus の言語偏りが想定より強いことを示すが、
  N_eff と top 5% は健全範囲。Phase E A-6 で実際の persona discrimination
  signal を見てから Candidate C 補強検討。
- **caveat (Codex MEDIUM-1)**: 本 audit は whitespace × 1.3 proxy tokenizer を
  使用。production training は **real Qwen3-8B tokenizer** を必ず使う
  (`--no-real-tokenizer-for-weights` 不指定で OK)。proxy と real で
  length distribution は ~10-20% ずれる可能性。

## D-1: ADOPT/REJECT verdict (Phase 6 完了時に記録)

> Phase 6 完了時に以下を verbatim 埋める。Phase 5 までで abort した場合は
> abort 理由と blockers.md cross-link を残す。

- **判断日時**: TBD (Phase 6 完了時)
- **per-axis 数値** (DA-14 thresholds vs no-LoRA SGLang baseline):
  - Vendi semantic Cohen's d: TBD (threshold ≤ -0.5)
  - Burrows reduction: TBD (threshold ≥ 5%)
  - ICC(A,1): TBD (threshold ≥ 0.55、CI lower ≥ 0.50)
  - throughput: TBD (threshold ≥ 70%)
- **quorum 判定** (kant 2-of-3):
  - axis pass: TBD / 4
- **verdict**: TBD (ADOPT / REJECT)
- **next**: TBD
  - ADOPT → Phase E A-6 (multi-turn full Tier B 7500-turn)
  - REJECT → DA-15 ADR 起票 (Vendi kernel swap or Candidate C escalate)
- **HIGH-3 post-hoc threshold movement 禁止**: ADOPT/REJECT 判定後に
  thresholds を緩めるのは禁止。DA-15 起票が正路。
