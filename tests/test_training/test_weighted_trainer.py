"""Unit tests for ``compute_weighted_causal_lm_loss`` (the WeightedTrainer math).

The WeightedTrainer class lives inside
:func:`erre_sandbox.training.train_kant_lora._run_trainer_weighted` (lazy
construction so the gate-only path stays installable without
``[training]`` extras). The actual loss math is in
:func:`compute_weighted_causal_lm_loss`, which is what these tests
exercise — that is the function the trainer calls per batch.

Both tests ``pytest.importorskip("torch")`` so the CI default profile
(no ``[training]`` extras) silently skips them. On the G-GEAR /
training-extras install they enforce the Codex HIGH-C verbatim
semantics:

* per-example mean over valid (non-``-100``) label positions,
* weighted sum divided by ``weights.sum()`` with epsilon clamp.
"""

from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")

from erre_sandbox.training.weighting import (  # noqa: E402
    compute_weighted_causal_lm_loss,
)


def _build_logits_targeting(labels: torch.Tensor, *, vocab: int = 5) -> torch.Tensor:
    """Build logits such that the argmax at each shifted position equals the target.

    Used as a fixture so manual-loss computation against the function's
    output is tractable (we control the exact per-token CE values).
    """
    batch, seq = labels.shape
    logits = torch.zeros(batch, seq, vocab)
    # We want logits[:, :-1, :] to predict labels[:, 1:].
    # At position i (i in [0, seq-2]) the model predicts label[i+1].
    for b in range(batch):
        for i in range(seq - 1):
            target = int(labels[b, i + 1].item())
            if target == -100:
                continue
            # Make the target logit dominate so CE is well-bounded and
            # roughly equal to log(1 + (vocab-1)*exp(-margin)) for margin we set.
            margin = 2.0
            logits[b, i, :] = -margin / 2.0
            logits[b, i, target] = margin / 2.0
    return logits


def test_weighted_trainer_compute_loss_weighted_sum_matches_manual() -> None:
    """The function's output equals ``sum_i (w_i * mean_loss_i) / sum_i w_i``.

    Build a 2-example batch with controlled labels + logits so we can
    compute the expected weighted-mean loss in pure Python and compare.
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
    # average within each example, then take weighted mean over batch.
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
    expected = (per_example_loss * weights).sum() / weights.sum()

    assert math.isclose(
        float(weighted_loss.item()),
        float(expected.item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )

    # The two examples are constructed to have IDENTICAL per-token CE per
    # position (same margin construction), so per_example_loss is the same
    # for both. The weighted mean then collapses to that shared value
    # regardless of the (3.0, 1.0) weight vector.
    assert math.isclose(
        float(per_example_loss[0].item()),
        float(per_example_loss[1].item()),
        rel_tol=1e-6,
        abs_tol=1e-7,
    )


def test_weighted_trainer_compute_loss_handles_label_minus_100() -> None:
    """``-100`` label positions are ignored in both numerator and denominator.

    A batch where one example has ALL labels set to ``-100`` after shift
    must not produce NaN — the function clamps the denominator at 1.0.
    Codex MEDIUM-2: contamination-resistant reduction.
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
    # example A: per-token CE for labels [2, 3] (positions 1, 2 in shifted),
    #            divided by 2 valid positions
    # example B: all -100 → valid_counts clamped to 1.0, sum of zero-masked CE = 0,
    #            so per_example_loss = 0
    # weighted_loss = (2.0 * per_A + 1.0 * 0.0) / 3.0
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
    expected = (per_example_loss * weights).sum() / weights.sum()

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
