"""NLI contradiction unit tests — stub-based aggregation.

Heavy ML model integration is gated behind ``@pytest.mark.eval`` and
not exercised here; we only verify that the aggregation logic does the
right thing given a stub scorer that returns deterministic
contradiction probabilities.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from erre_sandbox.evidence.tier_a.nli import compute_nli_contradiction


def _const_scorer(value: float):  # type: ignore[no-untyped-def]
    """Return a stub scorer that gives every pair the same probability."""

    def scorer(pairs: Sequence[tuple[str, str]]) -> list[float]:
        return [value] * len(pairs)

    return scorer


def test_empty_pairs_returns_none() -> None:
    result = compute_nli_contradiction([], scorer=_const_scorer(0.5))
    assert result is None


def test_constant_scorer_yields_constant_mean() -> None:
    pairs = [("p1", "h1"), ("p2", "h2"), ("p3", "h3")]
    result = compute_nli_contradiction(pairs, scorer=_const_scorer(0.42))
    assert result == pytest.approx(0.42)


def test_mixed_scorer_averages_correctly() -> None:
    pairs = [("p1", "h1"), ("p2", "h2"), ("p3", "h3"), ("p4", "h4")]

    def scorer(_pairs: Sequence[tuple[str, str]]) -> list[float]:
        return [0.0, 0.0, 0.5, 1.0]

    result = compute_nli_contradiction(pairs, scorer=scorer)
    assert result == pytest.approx(0.375)


def test_scorer_returning_empty_yields_none() -> None:
    pairs = [("p1", "h1")]

    def scorer(_pairs: Sequence[tuple[str, str]]) -> list[float]:
        return []

    result = compute_nli_contradiction(pairs, scorer=scorer)
    assert result is None


def test_persona_discriminative_contradiction_gap() -> None:
    # A "consistent" persona's pairs always score 0.05 contradiction;
    # a "self-contradicting" persona scores 0.7 on average. The metric
    # must surface this gap regardless of pair count.
    pairs = [("p", "h")] * 10
    consistent = compute_nli_contradiction(pairs, scorer=_const_scorer(0.05))
    contradicting = compute_nli_contradiction(pairs, scorer=_const_scorer(0.7))
    assert consistent is not None
    assert contradicting is not None
    assert contradicting - consistent > 0.5
