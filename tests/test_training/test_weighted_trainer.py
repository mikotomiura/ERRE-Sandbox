"""Unit tests for ``compute_weighted_causal_lm_loss`` (the WeightedTrainer math).

The WeightedTrainer class lives inside
:func:`erre_sandbox.training.train_kant_lora._run_trainer_weighted` (lazy
construction so the gate-only path stays installable without
``[training]`` extras). The actual loss math is in
:func:`compute_weighted_causal_lm_loss`, which is what these tests
exercise — that is the function the trainer calls per batch.

These tests ``pytest.importorskip("torch")`` so the CI default profile
(no ``[training]`` extras) silently skips them. On the G-GEAR /
training-extras install they enforce the **DA-16 ADR DA16-2** semantics
(``.mean()`` reduce, replaces the prior Codex HIGH-C
``sum/weights.sum()`` reduce):

* per-example mean over valid (non-``-100``) label positions,
* batch-level reduction ``(per_example_loss * weights).mean()`` so
  per-example weight is preserved in the gradient under
  ``per_device_train_batch_size=1`` (the regression that DA-14
  weighting was no-opped by — retrain blockers.md Blocker 2).

The three batch=1 / variable-margin regression tests at the bottom
(``test_..._batch1_weight_changes_loss_magnitude``,
``test_..._batch1_grad_norm_scales_with_weight``,
``test_..._batch2_diff_per_example_weight_effect``) exist
specifically so that any future reduce-form change that re-introduces
the batch=1 weight cancellation will fail loudly.
"""

from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")

from erre_sandbox.training.weighting import (  # noqa: E402
    compute_weighted_causal_lm_loss,
)


def _build_logits_targeting(
    labels: torch.Tensor,
    *,
    vocab: int = 5,
    margins: list[float] | None = None,
) -> torch.Tensor:
    """Build logits whose argmax at each shifted position equals the target.

    Used as a fixture so manual-loss computation against the function's
    output is tractable (we control the exact per-token CE values).

    Args:
        labels: ``(batch, seq)`` tensor of target tokens.
        vocab: vocabulary size; logits will be ``(batch, seq, vocab)``.
        margins: optional per-example margin override. When ``None``
            (default) all examples use ``margin=2.0`` (the historical
            behaviour, used by the two ``..._matches_manual`` /
            ``..._handles_label_minus_100`` tests). When supplied as a
            list, ``margins[b]`` controls the margin for example ``b`` —
            this lets the new ``..._per_example_loss_differs_...`` test
            construct a fixture where per-example CE values are NOT
            identical, restoring weight-detection power that the
            uniform-margin fixture lacks (DA-16 ADR codex-review.md
            HIGH-2).
    """
    batch, seq = labels.shape
    if margins is None:
        margins_list = [2.0] * batch
    else:
        if len(margins) != batch:
            msg = (
                f"_build_logits_targeting: margins length {len(margins)} != "
                f"batch {batch}"
            )
            raise ValueError(msg)
        margins_list = list(margins)
    logits = torch.zeros(batch, seq, vocab)
    # We want logits[:, :-1, :] to predict labels[:, 1:].
    # At position i (i in [0, seq-2]) the model predicts label[i+1].
    for b in range(batch):
        margin = margins_list[b]
        for i in range(seq - 1):
            target = int(labels[b, i + 1].item())
            if target == -100:
                continue
            # Make the target logit dominate so CE is well-bounded and
            # roughly equal to log(1 + (vocab-1)*exp(-margin)) for the
            # configured margin.
            logits[b, i, :] = -margin / 2.0
            logits[b, i, target] = margin / 2.0
    return logits


def test_weighted_trainer_compute_loss_weighted_sum_matches_manual() -> None:
    """The function's output equals ``(per_example_loss * weights).mean()``.

    Build a 2-example batch with controlled labels + logits so we can
    compute the expected batch reduction in pure Python and compare.

    Under the **DA-16 ADR DA16-2** ``.mean()`` reduce the batch-level
    formula is ``(per_example_loss * weights).mean()`` (replaces the
    prior ``sum/weights.sum()`` form). The existing uniform-margin
    fixture below produces identical per-example CE for both rows so
    weight-detection power here is intentionally zero — the new
    ``..._per_example_loss_differs_...`` test below covers the
    differential-margin regression that this one cannot (DA-16
    codex-review.md HIGH-2).
    """
    # batch=2, seq=4, vocab=5
    labels = torch.tensor(
        [
            [
                1,
                2,
                3,
                4,
            ],  # example A: 3 valid shifted positions (predict 2,3,4 from 1,2,3)
            [0, 1, 1, 2],  # example B: 3 valid shifted positions
        ],
        dtype=torch.long,
    )
    logits = _build_logits_targeting(labels, vocab=5)
    weights = torch.tensor([3.0, 1.0], dtype=torch.float32)

    weighted_loss = compute_weighted_causal_lm_loss(logits, labels, weights)

    # Manual computation: shift labels by 1, compute per-token CE,
    # average within each example, then take ``.mean()`` over the
    # weighted per-example losses (DA16-2).
    logits_shifted = logits[:, :-1, :]
    labels_shifted = labels[:, 1:]
    token_ce = torch.nn.functional.cross_entropy(
        logits_shifted.reshape(-1, logits_shifted.size(-1)),
        labels_shifted.reshape(-1),
        ignore_index=-100,
        reduction="none",
    ).reshape(labels_shifted.shape)
    valid_mask = (labels_shifted != -100).float()
    per_example_loss = (token_ce * valid_mask).sum(dim=1) / valid_mask.sum(
        dim=1
    ).clamp_min(1.0)
    expected = (per_example_loss * weights).mean()

    assert math.isclose(
        float(weighted_loss.item()),
        float(expected.item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )

    # The two examples are constructed to have IDENTICAL per-token CE
    # per position (same margin=2.0 default). per_example_loss is the
    # same for both, so the weighted mean collapses to that shared
    # value regardless of the (3.0, 1.0) weight vector. The
    # batch-level weight effect is verified in
    # ``..._batch2_per_example_loss_differs_weight_takes_effect``
    # below, which uses margins=[2.0, 0.5] to break this degeneracy
    # (DA-16 codex-review.md HIGH-2).
    assert math.isclose(
        float(per_example_loss[0].item()),
        float(per_example_loss[1].item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )


def test_weighted_trainer_compute_loss_handles_label_minus_100() -> None:
    """``-100`` label positions are ignored in both numerator and denominator.

    A batch where one example has ALL labels set to ``-100`` after
    shift must not produce NaN — ``valid_counts`` is clamped at 1.0 so
    the per-example loss for the all-masked row is 0 (zero numerator
    divided by clamped denominator). Codex MEDIUM-2:
    contamination-resistant reduction.

    Under DA16-2 the batch reduction is ``(per_example_loss *
    weights).mean()``, so for ``per_example_loss = [per_A, 0]`` and
    ``weights = [2.0, 1.0]`` the expected scalar is ``(2.0 * per_A +
    1.0 * 0.0) / 2``.
    """
    labels = torch.tensor(
        [
            [1, -100, 2, 3],  # example A: shifted labels [-100, 2, 3] → 2 valid
            [
                0,
                -100,
                -100,
                -100,
            ],  # example B: shifted labels [-100, -100, -100] → 0 valid
        ],
        dtype=torch.long,
    )
    logits = _build_logits_targeting(labels, vocab=4)
    weights = torch.tensor([2.0, 1.0], dtype=torch.float32)

    weighted_loss = compute_weighted_causal_lm_loss(logits, labels, weights)

    # Expected:
    # example A: per-token CE for labels [2, 3] (positions 1, 2 in
    #            shifted), divided by 2 valid positions
    # example B: all -100 → valid_counts clamped to 1.0, sum of
    #            zero-masked CE = 0, so per_example_loss[B] = 0
    # weighted_loss = (2.0 * per_A + 1.0 * 0.0) / 2  (DA16-2 .mean())
    logits_shifted = logits[:, :-1, :]
    labels_shifted = labels[:, 1:]
    token_ce = torch.nn.functional.cross_entropy(
        logits_shifted.reshape(-1, logits_shifted.size(-1)),
        labels_shifted.reshape(-1),
        ignore_index=-100,
        reduction="none",
    ).reshape(labels_shifted.shape)
    valid_mask = (labels_shifted != -100).float()
    valid_counts = valid_mask.sum(dim=1).clamp_min(1.0)
    per_example_loss = (token_ce * valid_mask).sum(dim=1) / valid_counts
    expected = (per_example_loss * weights).mean()

    assert math.isclose(
        float(weighted_loss.item()),
        float(expected.item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )
    # Sanity: example B contributes zero (all-masked rows are well-handled)
    assert float(per_example_loss[1].item()) == 0.0
    # And the function did not return NaN
    assert not math.isnan(float(weighted_loss.item()))


def test_weighted_trainer_compute_loss_rejects_seq_len_one() -> None:
    """Sequence length 1 cannot be shifted; the function raises ValueError."""
    labels = torch.tensor([[1]], dtype=torch.long)
    logits = torch.zeros(1, 1, 5)
    weights = torch.tensor([1.0], dtype=torch.float32)
    with pytest.raises(ValueError, match="seq_len"):
        compute_weighted_causal_lm_loss(logits, labels, weights)


# ---------------------------------------------------------------------------
# DA-16 ADR DA16-2 regression tests
#
# These three tests exist specifically as **regression detectors** for the
# WeightedTrainer Blocker 2 (batch=1 sample-weight collapse). The prior
# reduce form ``(l * w).sum() / w.sum()`` degenerates to ``l[0]`` for
# batch=1, no-opping DA-14 weighting in training. Any future change that
# re-introduces that cancellation (e.g. reverting to the prior form, or
# any reduce that divides by ``weights.sum()``) MUST cause these tests to
# fail. Do not weaken or remove without re-opening the DA-16 ADR.
# ---------------------------------------------------------------------------


def test_weighted_trainer_compute_loss_batch1_weight_changes_loss_magnitude() -> None:
    """Batch=1: scaling ``weights`` by k scales the returned loss by k.

    Under DA16-2 ``.mean()`` reduce: ``loss = (l[0] * w[0]).mean() =
    l[0] * w[0]`` for batch=1. Doubling ``w`` doubles the scalar — this
    is the Blocker 2 regression detector. Under the prior
    ``sum/weights.sum()`` reduce the result was ``l[0]`` regardless of
    ``w``, so that form would fail this test (which is exactly what we
    want).
    """
    labels = torch.tensor([[1, 2, 3, 4]], dtype=torch.long)
    logits = _build_logits_targeting(labels, vocab=5)

    loss_w1 = compute_weighted_causal_lm_loss(
        logits,
        labels,
        torch.tensor([1.0], dtype=torch.float32),
    )
    loss_w2 = compute_weighted_causal_lm_loss(
        logits,
        labels,
        torch.tensor([2.0], dtype=torch.float32),
    )

    # The base loss is non-zero (the fixture has 3 valid shifted positions
    # with a finite margin, so per-token CE > 0).
    assert float(loss_w1.item()) > 0.0

    assert math.isclose(
        float(loss_w2.item()) / float(loss_w1.item()),
        2.0,
        rel_tol=1e-6,
        abs_tol=1e-7,
    )


def test_weighted_trainer_compute_loss_batch1_grad_norm_scales_with_weight() -> None:
    """Batch=1: ``loss.backward()`` gradient norm scales linearly with weight.

    The training-time symptom of Blocker 2 was that DA-14 weights had
    no effect on the gradient (the prior reduce cancelled them). This
    test runs ``loss.backward()`` against a synthetic ``nn.Linear``
    parameter and asserts the parameter's gradient norm scales as the
    weight ratio. With DA16-2 ``.mean()`` reduce the ratio is 2.0; the
    prior reduce produced ratio 1.0 (cancellation), so this test fails
    if Blocker 2 reappears.
    """
    torch.manual_seed(0)
    vocab = 5
    labels = torch.tensor([[1, 2, 3, 4]], dtype=torch.long)
    # One-hot input so a single ``nn.Linear(vocab, vocab)`` produces
    # ``(1, seq, vocab)`` logits whose grad path is uncluttered.
    inp = torch.eye(vocab)[labels[0]].unsqueeze(0)  # (1, 4, 5)

    linear = torch.nn.Linear(vocab, vocab, bias=False)

    def _grad_norm_for_weight(w: float) -> float:
        linear.zero_grad()
        logits = linear(inp)  # (1, 4, 5)
        loss = compute_weighted_causal_lm_loss(
            logits,
            labels,
            torch.tensor([w], dtype=torch.float32),
        )
        loss.backward()
        grad = linear.weight.grad
        assert grad is not None, "gradient must not be None after backward"
        return float(grad.norm().item())

    g_w1 = _grad_norm_for_weight(1.0)
    g_w2 = _grad_norm_for_weight(2.0)

    # Gradient must actually flow (non-zero) so the ratio is meaningful.
    assert g_w1 > 0.0

    assert math.isclose(g_w2 / g_w1, 2.0, rel_tol=1e-4, abs_tol=1e-6)


def test_weighted_trainer_compute_loss_batch2_diff_per_example_weight_effect() -> None:
    """Batch=2 with per-example margins=[2.0, 0.5]: weights DO change the result.

    DA-16 codex-review.md HIGH-2: the existing batch=2 fixture above
    uses uniform margin=2.0, so per_example_loss is identical for both
    rows and the weighted mean collapses regardless of weight vector —
    weight-detection power is zero. This test builds a fixture where
    per-example CE values are deliberately different (margins=[2.0,
    0.5]) so that ``weighted = (per * w).mean()`` is provably different
    from ``unweighted = per.mean()`` under ``weights = [3.0, 1.0]``.

    Asserts both:

    1. The function's output matches ``(per_example_loss *
       weights).mean()`` (DA16-2 formula).
    2. That output is NOT equal to the unweighted per-example mean
       (so the weight vector is observably effective in the reduce).
    """
    labels = torch.tensor(
        [
            [1, 2, 3, 4],  # example A: 3 valid positions
            [0, 1, 1, 2],  # example B: 3 valid positions
        ],
        dtype=torch.long,
    )
    logits = _build_logits_targeting(labels, vocab=5, margins=[2.0, 0.5])
    weights = torch.tensor([3.0, 1.0], dtype=torch.float32)

    weighted_loss = compute_weighted_causal_lm_loss(logits, labels, weights)

    # Manual per-example loss
    logits_shifted = logits[:, :-1, :]
    labels_shifted = labels[:, 1:]
    token_ce = torch.nn.functional.cross_entropy(
        logits_shifted.reshape(-1, logits_shifted.size(-1)),
        labels_shifted.reshape(-1),
        ignore_index=-100,
        reduction="none",
    ).reshape(labels_shifted.shape)
    valid_mask = (labels_shifted != -100).float()
    per_example_loss = (token_ce * valid_mask).sum(dim=1) / valid_mask.sum(
        dim=1
    ).clamp_min(1.0)

    # (1) Fixture sanity: per-example losses are genuinely different
    #     (margin=0.5 gives a larger CE than margin=2.0). If this ever
    #     becomes equal, the test below has no power.
    assert not math.isclose(
        float(per_example_loss[0].item()),
        float(per_example_loss[1].item()),
        rel_tol=1e-2,
        abs_tol=1e-3,
    )

    # (2) Function output matches DA16-2 .mean() formula
    expected = (per_example_loss * weights).mean()
    assert math.isclose(
        float(weighted_loss.item()),
        float(expected.item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )

    # (3) Weight effect is observable — weighted result differs from
    #     unweighted per-example mean by more than rel_tol=1e-2. This
    #     is the HIGH-2 weight-detection check that the uniform-margin
    #     fixture lacks.
    unweighted_mean = per_example_loss.mean()
    assert not math.isclose(
        float(weighted_loss.item()),
        float(unweighted_mean.item()),
        rel_tol=1e-2,
        abs_tol=1e-3,
    )
