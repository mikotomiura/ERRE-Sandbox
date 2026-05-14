# Kant LoRA training corpus — characteristics analysis

**Purpose**: identify why persona-discriminative signal is weak in the
existing K-β rank=8 LoRA (DA-13 Backend Confound Discovery, LoRA
effect proper ±0.5 vs no-LoRA SGLang baseline).

**Shards analysed**: 10
**Realised Kant examples**: 5022

## 1. Token-length distribution

- Mean: 24.1
- Median: 23.0
- p10 / p90: 9.0 / 39.0
- **Short utterance ratio (tokens < 30)**: 69.0%

Histogram bins (token range → count):

- `0-9` tokens: 538 (10.7%)
- `10-29` tokens: 2926 (58.3%)
- `30-59` tokens: 1509 (30.0%)
- `60-119` tokens: 48 (1.0%)
- `120-239` tokens: 1 (0.0%)
- `240-479` tokens: 0 (0.0%)
- `480+` tokens: 0 (0.0%)

> **Tokenizer proxy in effect**: Qwen3-8B tokenizer unavailable; token counts are whitespace+punctuation × 1.3 estimates (CJK chars counted 1:1). Distribution shape is preserved but absolute counts may differ by ~10-20%.

## 2. Persona-discriminative marker density

- **Combined marker density (per 100 tokens)**: mean=1.52, median=0.00
- Self-reference marker density: 0.30 per 100 tokens
- Kantian-philosophy marker density: 1.23 per 100 tokens
- Literature anchor target: 2.00 per 100 tokens
- **Observed / anchor ratio**: 0.76x (<1.0 = below anchor, signal-weakening)

## 3. Dialog vs monolog

- Dialog (has addressee): 100.0%
- Monolog: 0.0%

Top addressees:
- `interlocutor`: 2520
- `nietzsche`: 1258
- `rikyu`: 1244

## 4. Per-shard / stimulus category coverage

- Natural shards: 2502
- Stimulus shards: 2520

Per-shard breakdown:

- `kant_natural_run0.duckdb`: 501 Kant examples
- `kant_natural_run1.duckdb`: 500 Kant examples
- `kant_natural_run2.duckdb`: 500 Kant examples
- `kant_natural_run3.duckdb`: 500 Kant examples
- `kant_natural_run4.duckdb`: 501 Kant examples
- `kant_stimulus_run0.duckdb`: 504 Kant examples
- `kant_stimulus_run1.duckdb`: 504 Kant examples
- `kant_stimulus_run2.duckdb`: 504 Kant examples
- `kant_stimulus_run3.duckdb`: 504 Kant examples
- `kant_stimulus_run4.duckdb`: 504 Kant examples

**kant.yaml stim battery reference** (target distribution):

- `stimuli`: 70 items

> **Note**: ``raw_dialog`` does not expose ``stimulus_id``,
> so per-stim-category corpus coverage cannot be matched
> directly. The shard-level natural-vs-stimulus split is the
> closest proxy available without re-instrumenting the egress
> contract.

## 5. Mode / zone distribution

Mode (ERRE cognitive mode):

Zone (ERRE space):
- `study`: 2730
- `peripatos`: 1210
- `agora`: 776
- `chashitsu`: 156
- `garden`: 150

## 6. Utterance language distribution

Heuristic classification (langdetect not installed):

- `ja`: 2847 (56.7%)
- `en`: 1296 (25.8%)
- `de`: 798 (15.9%)
- `mixed`: 81 (1.6%)

## Falsifiable gap finding (Step 1 acceptance)

Observed combined marker density 1.52 per 100 tokens is **0.76x** the
literature anchor of 2.00
(Cambridge Edition translator-aligned Kant passages). The signal
deficit is concentrated in:
- short utterances (<30 tokens) at 69.0% of the corpus
- monolog ratio at 0.0%
- self-ref marker mean density 0.30 (anchor expects ≥1.0)

These three knobs are the targets for retrain v2 signal-driven
weighting (DR-1 in this PR's decisions.md).
