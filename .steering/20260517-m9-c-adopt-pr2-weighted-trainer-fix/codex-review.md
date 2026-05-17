## HIGH
- HIGH-1: none. The reducer is exactly DA16-2: `return (per_example_loss * weights).mean()` at [weighting.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/weighting.py:495). I do not see a blocker from empty-pool, zero-weight, mixed precision, or NaN behavior versus the prior reducer.
- HIGH-2: none. The new batch=1 magnitude and gradient tests at [test_weighted_trainer.py](/mnt/c/ERRE-Sand_Box/tests/test_training/test_weighted_trainer.py:253) and [test_weighted_trainer.py](/mnt/c/ERRE-Sand_Box/tests/test_training/test_weighted_trainer.py:289) should fail under the old `sum()/weights.sum()` form with ratio `1.0` instead of `2.0`. The batch=2 differential-margin test at [test_weighted_trainer.py](/mnt/c/ERRE-Sand_Box/tests/test_training/test_weighted_trainer.py:331) also has real detection power.
- HIGH-3: none. `WeightedTrainer.compute_loss` keeps the API contract: it pops `sample_weight`/`labels`, calls the model without labels, computes the custom scalar, and preserves `(loss, outputs)` for `return_outputs=True` at [train_kant_lora.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:1690).

## MEDIUM
- MEDIUM-1: Tighten the reducer docstring before merge. At [weighting.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/weighting.py:443), it says `compute_example_weight` “guarantees” mean=1 via `normalise_weights_to_mean_one`; strictly, `compute_example_weight` returns raw weights, and the training pipeline normalizes them at [train_kant_lora.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:742). Also, [weighting.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/weighting.py:447) says old/new scales are “nearly identical” for `batch_size >= 2`; that is only true in expectation over shuffled batches. For small batches, the new loss equals old loss times local `mean(weights)`, which can be materially different. This matters for future retrains with batch=2+ because someone could misread train-loss or gradient-scale changes as model/corpus effects instead of reducer semantics.

## LOW
- LOW-1: Update adjacent comment drift in `WeightedTrainer.compute_loss`. The comment says “Loss semantics are unchanged” and `compute_weighted_causal_lm_loss` is the “verbatim Codex HIGH-C implementation” at [train_kant_lora.py](/mnt/c/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:1703). After DA-16, only the shift/recompute contract is unchanged; the reducer semantics are intentionally changed. This is not behaviorally risky, but it is misleading maintenance text.

## Verdict
ADOPT-WITH-CHANGES — no HIGH blockers. I would merge after the MEDIUM docstring clarification; the LOW comment cleanup can be included in the same patch.

Verification note: I attempted the focused pytest run, but the current read-only sandbox blocks `uv run` because uv cannot create its cache lock under `/root/.cache/uv`.
