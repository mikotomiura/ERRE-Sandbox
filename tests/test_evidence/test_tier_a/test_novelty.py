"""Semantic novelty unit tests — stub embeddings + numpy aggregation.

Real MPNet integration is gated behind ``@pytest.mark.eval`` and not
exercised here; the aggregation logic is verified with hand-crafted
embedding fixtures whose cosine geometry is known up front.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from erre_sandbox.evidence.tier_a.novelty import compute_semantic_novelty


def _stub(embeddings: list[list[float]]):  # type: ignore[no-untyped-def]
    def encoder(_batch: Sequence[str]) -> list[list[float]]:
        return embeddings

    return encoder


def test_too_few_utterances_returns_none() -> None:
    assert compute_semantic_novelty([]) is None
    assert compute_semantic_novelty(["only one"]) is None


def test_identical_embeddings_yield_zero_novelty() -> None:
    encoder = _stub([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    result = compute_semantic_novelty(
        ["a", "b", "c"],
        encoder=encoder,
    )
    assert result == pytest.approx(0.0, abs=1e-9)


def test_orthogonal_embeddings_yield_unit_distance() -> None:
    # Each turn is orthogonal to the prior centroid → cosine sim 0
    # → distance 1.0 per turn after the first.
    encoder = _stub([[1.0, 0.0], [0.0, 1.0]])
    result = compute_semantic_novelty(
        ["a", "b"],
        encoder=encoder,
    )
    assert result == pytest.approx(1.0, abs=1e-9)


def test_antipodal_embeddings_collapse_to_max_novelty() -> None:
    # Prior centroid = 0 vector after [+x, -x]; the implementation
    # falls back to 1.0 distance for the third turn rather than
    # NaN — this is the documented fallback.
    encoder = _stub([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0]])
    result = compute_semantic_novelty(
        ["a", "b", "c"],
        encoder=encoder,
    )
    # Turn 1 vs unit(turn0) = (1, 0): cos sim -1 → distance 2
    # Turn 2 vs prior centroid 0 → fallback 1.0
    # Mean = (2 + 1) / 2 = 1.5
    assert result == pytest.approx(1.5, abs=1e-9)


def test_encoder_returning_empty_yields_none() -> None:
    encoder = _stub([])
    # Even with two utterances, an empty encoder → None.
    result = compute_semantic_novelty(["a", "b"], encoder=encoder)
    assert result is None


def test_encoder_returning_wrong_shape_raises() -> None:
    encoder = _stub([[1.0, 0.0]])  # 1 row for 2 utterances
    with pytest.raises(ValueError, match="2D with 2 rows"):
        compute_semantic_novelty(["a", "b"], encoder=encoder)


def test_persona_discriminative_novelty_gap() -> None:
    # "Cyclic" persona: 8 turns alternating between two embeddings.
    cyclic = _stub([[1.0, 0.0], [0.0, 1.0]] * 4)
    cyclic_score = compute_semantic_novelty(
        ["t"] * 8,
        encoder=cyclic,
    )
    # "Diverse" persona: 8 turns each on a fresh axis (rotated).
    diverse_embeddings = []
    import math

    for i in range(8):
        # Rotate around the unit circle.
        theta = i * math.pi / 4
        diverse_embeddings.append([math.cos(theta), math.sin(theta)])
    diverse_score = compute_semantic_novelty(
        ["t"] * 8,
        encoder=_stub(diverse_embeddings),
    )
    assert cyclic_score is not None
    assert diverse_score is not None
    # Diverse persona must register strictly higher novelty.
    assert diverse_score > cyclic_score
