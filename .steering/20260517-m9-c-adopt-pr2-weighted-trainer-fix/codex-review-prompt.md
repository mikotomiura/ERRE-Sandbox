# Codex independent review request — PR-2 WeightedTrainer Blocker 2 fix

You are reviewing **PR-2** of the kant Plan B PHASE_E_A6 routing (Plan B
verdict REJECT recovery). The PR implements the **DA-16 ADR DA16-2**
``.mean()`` reduce confirmed in
`.steering/20260517-m9-c-adopt-da16-design/decisions.md`, plus the
batch=2 differential-margin regression test demanded by **HIGH-2** of
the DA-16 codex review
(`.steering/20260517-m9-c-adopt-da16-design/codex-review.md`).

## Context

`compute_weighted_causal_lm_loss` in
`src/erre_sandbox/training/weighting.py:411` previously reduced as:

```python
return (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
```

Under `per_device_train_batch_size=1` (the only VRAM-feasible setting
for Qwen3-8B + NF4 + rank=8 on DI-7's 16 GB GPU) this degenerates to
`(l[0] * w[0]) / w[0] = l[0]` — the per-example weight cancels out of
the gradient and DA-14's `compute_example_weight` becomes a no-op in
training. This is **retrain blockers.md Blocker 2**, suspected to have
contributed to kant Plan B v3's REJECT verdict
(`.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1).

The DA-16 ADR fixed the policy: replace with `.mean()` reduce so that
`loss = (l * w).mean()` retains weight magnitude in the gradient under
batch=1, and HF gradient accumulation aggregates weight-aware
micro-batch gradients automatically. The ADR also pre-registered the
test plan, in particular Codex HIGH-2's call for a batch=2 fixture
with differential per-example margins so the regression detector has
real weight-detection power (the prior uniform-margin fixture has
zero).

The DA-16 ADR `decisions.md` DA16-2 trade-off section also documents
that this is a **breaking semantic change** for ``train_loss`` scale
and the learning trajectory's gradient path (v3 vs v4 train_loss are
NOT directly comparable, only intra-run convergence is meaningful);
``eval_loss`` IS still comparable because eval examples carry
``sample_weight=1.0`` and ``per_device_eval_batch_size=1``, so the
old and new reduce produce identical numerics on the eval path
(HIGH-1 reflection from the DA-16 codex review).

## Scope of this PR

- `src/erre_sandbox/training/weighting.py:411` — reduce expression
  change + docstring rewrite (DA16-2 semantics)
- `tests/test_training/test_weighted_trainer.py` —
  - Existing 2 tests' `expected =` rewritten to `.mean()` form
  - Existing 1 test (`..._rejects_seq_len_one`) unchanged
  - New helper signature: `_build_logits_targeting(labels, *, vocab,
    margins=None)` so per-example margins can be supplied (DA-16
    HIGH-2 enabler; default falls back to uniform `margin=2.0`)
  - **Three new regression tests** (DA-16 codex-review.md HIGH-2 +
    Blocker 2 detectors):
    - `..._batch1_weight_changes_loss_magnitude` — batch=1 loss
      scales linearly with weight under `.mean()`; would fail under
      the prior reduce
    - `..._batch1_grad_norm_scales_with_weight` — synthetic
      `nn.Linear` gradient norm scales linearly with weight after
      `loss.backward()`; the actual training-time symptom of Blocker
      2 manifested as no-op gradient under the prior reduce
    - `..._batch2_diff_per_example_weight_effect` — fixture with
      margins=[2.0, 0.5] proves the weight vector has observable
      effect on the batch-level loss when per-example CE differs;
      the uniform-margin fixture cannot detect this
- `src/erre_sandbox/training/train_kant_lora.py:1687-1715`
  (`WeightedTrainer.compute_loss`) — **unchanged** (call-site API
  contract preserved)
- `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/` — 5
  standard steering files (this directory)

The PR is **implementation-only** of the DA-16 ADR; no new design
decisions are introduced.

## Files for you to read

1. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/requirement.md`
2. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/design.md`
3. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/decisions.md`
   (local implementation decisions, DP2-1〜DP2-3)
4. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
   (the upstream ADR this PR implements)
5. `.steering/20260517-m9-c-adopt-da16-design/codex-review.md`
   (the HIGH-1 / HIGH-2 reflections being applied here)
6. `src/erre_sandbox/training/weighting.py:411-485` (the function +
   updated docstring)
7. `src/erre_sandbox/training/train_kant_lora.py:1680-1716`
   (the call-site whose API contract must remain unchanged)
8. `tests/test_training/test_weighted_trainer.py` (the full test file
   incl. helper + 3 new tests)

## What I'd like you to evaluate

### HIGH (block-or-merge)

1. **Reduce-form correctness**: Does `(per_example_loss *
   weights).mean()` correctly implement the DA-16 ADR DA16-2 intent,
   given `compute_example_weight` enforces mean=1 normalisation over
   the training pool? Are there edge cases (e.g. empty pool, zero
   weight rows, mixed-precision numerics, NaN propagation) where it
   behaves worse than the prior `sum/weights.sum()` reduce that
   should block this PR?
2. **Test detection power**: Will the three new regression tests
   actually fail if a future change accidentally reverts to a
   batch=1-cancelling reduce form? Are the assertion tolerances
   (`rel_tol=1e-6` for the magnitude test, `rel_tol=1e-4` for the
   gradient-norm test, `rel_tol=1e-2` for the unweighted-mean
   inequality) tight enough to catch a real regression and loose
   enough to avoid false flakes under random init / fp32?
3. **API contract preservation**: Is the unchanged
   `WeightedTrainer.compute_loss` call-site truly compatible with
   the new reduce? In particular: HF Trainer's
   `prediction_loss_only=True` path, gradient accumulation
   `accumulate_grad_batches` semantics, and the `(loss, outputs)`
   return tuple for `return_outputs=True`.

### MEDIUM (resolve before merge if possible)

4. **Docstring completeness**: The DA16-2 semantic explanation in the
   docstring (~30 lines, lines 412-466 of weighting.py post-edit).
   Does it accurately describe both the math change and the upstream
   assumption (`compute_example_weight` mean=1 normalisation)? Any
   misleading or omitted caveat that a future reader maintaining the
   weighting pipeline would need?
5. **Test naming + boundary**: The new tests deliberately keep the
   existing uniform-margin test (`..._weighted_sum_matches_manual`)
   to verify the formula, and add the differential-margin test to
   verify weight-detection power. Is that boundary well-drawn, or
   would consolidating into one test be clearer?
6. **`torch.clamp(min=1e-8)` removed**: DP2-2 removed the epsilon
   defence. Is there any code path (e.g. zero-weight rows from a
   bug in `compute_example_weight` or
   `normalise_weights_to_mean_one`) where the new `.mean()` would
   silently produce a misleading loss value that the prior epsilon
   would have surfaced?

### LOW (nice-to-have, may defer to a follow-up PR)

7. **Comment / documentation drift**: Any mention of the old
   reduce form in adjacent code/comments that should also be
   updated for coherence (especially any reference in
   `train_kant_lora.py` that mentions HIGH-C verbatim or DA-14
   weighting semantics).
8. **Test ergonomics**: Could the new `_build_logits_targeting`
   helper signature be cleaner (e.g. keyword-only `margins` instead
   of optional positional)?

## Output format

Please report your findings in the following structure:

```
## HIGH
- HIGH-1 (or none): ...
- HIGH-2 (or none): ...

## MEDIUM
- MEDIUM-1 (or none): ...

## LOW
- LOW-1 (or none): ...

## Verdict
ADOPT | ADOPT-WITH-CHANGES | REJECT — reasoning
```

Be specific: cite line numbers, quote verbatim code/comment text, and
explain *why* a problem matters in concrete terms (what a wrong
verdict in the next retrain would look like, what a regression that
would slip past these tests would cost, etc.). If you find no issues
in a tier, please say so explicitly rather than omit it. Thank you.
