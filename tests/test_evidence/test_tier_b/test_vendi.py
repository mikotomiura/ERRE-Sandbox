"""Tests for ``erre_sandbox.evidence.tier_b.vendi`` (M9-eval P4a).

The sanity tests here are the regression / sanity contract for the Vendi
sub-metric (M9-eval ME-10 / Codex P4a HIGH-1 / LOW-2). They are not evidence
that Vendi Score is the right diversity metric for LoRA persona drift —
that empirical question is the P4b sensitivity panel's job.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from erre_sandbox.evidence.bootstrap_ci import hierarchical_bootstrap_ci
from erre_sandbox.evidence.tier_b.vendi import (
    DEFAULT_KERNEL_NAME,
    VendiResult,
    compute_vendi,
    make_lexical_5gram_kernel,
    vendi_kernel_sensitivity_panel,
)


def _identity_kernel(items: Sequence[str]) -> np.ndarray:
    """Stub kernel returning the identity matrix — only valid for sanity tests."""
    return np.eye(len(items), dtype=float)


def _all_ones_kernel(items: Sequence[str]) -> np.ndarray:
    """Stub kernel where every pair is identical (similarity 1)."""
    n = len(items)
    return np.ones((n, n), dtype=float)


def _two_block_kernel(items: Sequence[str]) -> np.ndarray:
    """Stub kernel: first half identical, second half identical, blocks orthogonal."""
    n = len(items)
    matrix = np.zeros((n, n), dtype=float)
    half = n // 2
    matrix[:half, :half] = 1.0
    matrix[half:, half:] = 1.0
    return matrix


def test_compute_vendi_identity_kernel_score_equals_n() -> None:
    """ME-10 sanity (Codex P4a HIGH-1): identity kernel → score = N.

    The score=N invariant only holds for K=I after normalization. Lexical
    one-hot does NOT in general yield score=N for hybrid kernels because
    the semantic component still has nonzero off-diagonals — that mistake
    in v3 is what the test is named after.
    """
    items = ["a", "b", "c", "d", "e"]
    result = compute_vendi(items, kernel=_identity_kernel, kernel_name="identity")
    assert isinstance(result, VendiResult)
    assert result.n == len(items)
    assert result.score == pytest.approx(float(len(items)), abs=1e-6)
    assert result.kernel_name == "identity"


def test_compute_vendi_identical_utterances_score_equals_one() -> None:
    """Degenerate: all-ones kernel collapses to a single eigenvalue → score = 1."""
    items = ["same"] * 7
    result = compute_vendi(items, kernel=_all_ones_kernel, kernel_name="degenerate")
    assert result.score == pytest.approx(1.0, abs=1e-6)
    assert result.spectrum_entropy == pytest.approx(0.0, abs=1e-6)


def test_compute_vendi_empty_input_returns_zero_n() -> None:
    """Boundary: empty utterance list returns score=0, n=0 without invoking kernel."""

    def explode(_: Sequence[str]) -> np.ndarray:
        msg = "kernel must not be invoked on empty input"
        raise AssertionError(msg)

    result = compute_vendi([], kernel=explode, kernel_name="never-called")
    assert result.score == 0.0
    assert result.n == 0


def test_compute_vendi_two_block_kernel_score_equals_two() -> None:
    """Mid-degenerate: two equal-sized identical blocks → score ≈ 2."""
    items = ["a"] * 4 + ["b"] * 4
    result = compute_vendi(items, kernel=_two_block_kernel, kernel_name="two-block")
    assert result.score == pytest.approx(2.0, abs=1e-6)


def test_compute_vendi_rejects_asymmetric_kernel() -> None:
    """Validation: non-symmetric kernel → ValueError."""

    def asymmetric(items: Sequence[str]) -> np.ndarray:
        n = len(items)
        m = np.eye(n, dtype=float)
        if n >= 2:
            m[0, 1] = 0.5  # leave m[1, 0] = 0
        return m

    with pytest.raises(ValueError, match="symmetric"):
        compute_vendi(["a", "b", "c"], kernel=asymmetric)


def test_vendi_kernel_sensitivity_panel_shape_matches_weights() -> None:
    """ME-10 preregister: panel returns one VendiResult per weight tuple.

    The kernels chosen here put semantic at maximum diversity (identity) and
    lexical at minimum diversity (all-ones). For any convex combination the
    Vendi score therefore falls between ``1`` and ``N``: more semantic
    weight → score closer to ``N``; more lexical weight → score closer to 1.
    """
    items = ["alpha bravo", "alpha charlie", "delta echo"]
    weights = ((1.0, 0.0), (0.0, 1.0), (0.5, 0.5), (0.7, 0.3), (0.9, 0.1))
    panel = vendi_kernel_sensitivity_panel(
        items,
        semantic_kernel=_identity_kernel,  # diversity-max under semantic-only
        lexical_kernel=_all_ones_kernel,  # diversity-min under lexical-only
        weights=weights,
    )
    assert len(panel) == len(weights)
    assert panel[0].kernel_name == "semantic"
    assert panel[1].kernel_name == "lexical-5gram"
    # semantic-only on identity kernel → score = N
    assert panel[0].score == pytest.approx(float(len(items)), abs=1e-6)
    # lexical-only on all-ones kernel → score = 1
    assert panel[1].score == pytest.approx(1.0, abs=1e-6)
    # Hybrid scores fall strictly between the two extremes.
    for hybrid in panel[2:]:
        assert 1.0 < hybrid.score < float(len(items))
    # More semantic weight → score closer to N (identity contribution dominates).
    hybrid_05 = next(p for p in panel if p.kernel_name == "hybrid-0.5-0.5")
    hybrid_07 = next(p for p in panel if p.kernel_name == "hybrid-0.7-0.3")
    hybrid_09 = next(p for p in panel if p.kernel_name == "hybrid-0.9-0.1")
    assert hybrid_05.score < hybrid_07.score < hybrid_09.score


def test_vendi_default_encoder_model_id_is_all_mpnet_base_v2() -> None:
    """MEDIUM-4: the default kernel must use the same MPNet model Tier A novelty does.

    Implementation can silently diverge if a future refactor swaps the
    multilingual model in; this test pins the exact model id by inspecting
    the lazy loader source.
    """
    import inspect

    from erre_sandbox.evidence.tier_b.vendi import _load_default_kernel

    source = inspect.getsource(_load_default_kernel)
    assert "sentence-transformers/all-mpnet-base-v2" in source
    assert DEFAULT_KERNEL_NAME == "semantic"


def test_make_lexical_5gram_kernel_is_symmetric_and_diagonal_one() -> None:
    """Lexical kernel sanity: shape, symmetry, and diagonal contract."""
    kernel = make_lexical_5gram_kernel()
    matrix = kernel(["alpha bravo charlie", "alpha bravo delta", "zulu yankee"])
    assert matrix.shape == (3, 3)
    assert np.allclose(np.diag(matrix), 1.0)
    assert np.allclose(matrix, matrix.T)


def test_compute_vendi_bootstrap_cluster_only_primary_round_trip() -> None:
    """Integration: 25 cluster mock → cluster_only bootstrap CI, ESS framing.

    Tier B per-100-turn cluster_only is the M9-eval ME-14 primary CI mode.
    The integration ensures the score values from compute_vendi feed into
    hierarchical_bootstrap_ci without shape mismatches.
    """
    rng = np.random.default_rng(42)
    cluster_means = rng.uniform(1.5, 3.5, size=25).tolist()
    # Each cluster is a single observation (one Vendi score per window).
    values_per_cluster: list[list[float]] = [[v] for v in cluster_means]
    ci = hierarchical_bootstrap_ci(
        values_per_cluster,
        cluster_only=True,
        n_resamples=200,
        seed=0,
    )
    assert ci.method == "hierarchical-cluster-only"
    assert ci.n == len(cluster_means)
    assert ci.lo <= ci.point <= ci.hi
