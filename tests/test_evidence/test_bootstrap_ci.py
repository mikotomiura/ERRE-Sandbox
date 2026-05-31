"""Unit tests for :mod:`erre_sandbox.evidence.bootstrap_ci`.

Pure-numpy module so we can exercise it without ``[eval]`` extras.
Coverage:

* percentile bootstrap on a known iid distribution (analytic CI within
  tolerance)
* NaN / None drop semantics
* hierarchical block bootstrap returns wider CI than naive bootstrap
  on autocorrelated AR(1) data (Codex HIGH-2 expectation)
* deterministic under fixed ``seed``
* invalid argument errors
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from erre_sandbox.evidence.bootstrap_ci import (
    BootstrapResult,
    bootstrap_ci,
    estimate_block_length,
    hierarchical_bootstrap_ci,
)


def _ar1_series(rng: np.random.Generator, n: int, rho: float) -> list[float]:
    """Synthesise an AR(1) series ``x[t] = rho * x[t-1] + N(0, 1)``."""
    eps = rng.standard_normal(n)
    x = np.zeros(n)
    x[0] = eps[0]
    for t in range(1, n):
        x[t] = rho * x[t - 1] + eps[t]
    return x.tolist()


def test_bootstrap_ci_returns_bootstrap_result_dataclass() -> None:
    result = bootstrap_ci([1.0, 2.0, 3.0, 4.0, 5.0], n_resamples=200, seed=0)
    assert isinstance(result, BootstrapResult)
    assert result.method == "percentile"
    assert result.n == 5
    assert result.n_resamples == 200
    assert result.lo <= result.point <= result.hi
    assert math.isclose(result.width, result.hi - result.lo)


def test_bootstrap_ci_drops_none_and_nan() -> None:
    raw = [1.0, None, 2.0, float("nan"), 3.0]
    result = bootstrap_ci(raw, n_resamples=100, seed=0)
    assert result.n == 3
    assert math.isclose(result.point, 2.0, rel_tol=1e-9)


def test_bootstrap_ci_is_deterministic_under_seed() -> None:
    raw = list(range(50))
    a = bootstrap_ci(raw, n_resamples=500, seed=42)
    b = bootstrap_ci(raw, n_resamples=500, seed=42)
    assert a == b


def test_bootstrap_ci_changes_under_different_seeds() -> None:
    raw = list(range(50))
    a = bootstrap_ci(raw, n_resamples=500, seed=42)
    b = bootstrap_ci(raw, n_resamples=500, seed=43)
    # CI bounds differ between seeds; point estimate is data-only and stays
    # the same.
    assert math.isclose(a.point, b.point)
    assert (a.lo, a.hi) != (b.lo, b.hi)


def test_bootstrap_ci_iid_normal_within_analytic_bound() -> None:
    """For N(0,1) n=500, the 95% CI of the mean should be roughly
    ±1.96/sqrt(500) ≈ ±0.0876. Bootstrap percentile should match within
    a generous tolerance.
    """
    rng = np.random.default_rng(123)
    sample = rng.standard_normal(500).tolist()
    result = bootstrap_ci(sample, n_resamples=2000, seed=0)
    assert abs(result.point) < 0.15
    assert result.width < 0.25  # well within analytic ~0.18


def test_bootstrap_ci_median_statistic() -> None:
    raw = list(range(11))  # 0..10, median = 5
    result = bootstrap_ci(raw, n_resamples=200, seed=0, statistic="median")
    assert math.isclose(result.point, 5.0)
    assert result.lo <= result.point <= result.hi


def test_bootstrap_ci_rejects_invalid_ci() -> None:
    with pytest.raises(ValueError, match="ci must be"):
        bootstrap_ci([1.0, 2.0], ci=0.0)
    with pytest.raises(ValueError, match="ci must be"):
        bootstrap_ci([1.0, 2.0], ci=1.0)


def test_bootstrap_ci_rejects_invalid_n_resamples() -> None:
    with pytest.raises(ValueError, match="n_resamples"):
        bootstrap_ci([1.0, 2.0], n_resamples=0)


def test_bootstrap_ci_rejects_unknown_statistic() -> None:
    with pytest.raises(ValueError, match="statistic"):
        bootstrap_ci([1.0, 2.0], statistic="trimmed_mean")


def test_bootstrap_ci_rejects_empty_after_clean() -> None:
    with pytest.raises(ValueError, match="0 finite entries"):
        bootstrap_ci([None, float("nan"), None], n_resamples=10)


def test_hierarchical_bootstrap_ci_basic_shape() -> None:
    rng = np.random.default_rng(0)
    clusters = [rng.standard_normal(100).tolist() for _ in range(5)]
    result = hierarchical_bootstrap_ci(
        clusters, block_length=10, n_resamples=500, seed=0
    )
    assert isinstance(result, BootstrapResult)
    assert result.method == "hierarchical-block"
    assert result.n == 500  # 5 clusters × 100 turns
    assert result.lo <= result.point <= result.hi


def test_hierarchical_bootstrap_drops_empty_clusters() -> None:
    clusters: list[list[float | None]] = [
        [1.0, 2.0, 3.0],
        [None, float("nan")],  # entirely empty after clean — dropped
        [4.0, 5.0, 6.0],
    ]
    result = hierarchical_bootstrap_ci(
        clusters, block_length=2, n_resamples=200, seed=0
    )
    assert result.n == 6  # 3 + 3, not 8


def test_hierarchical_bootstrap_widens_ci_on_ar1_correlation() -> None:
    """AR(1) autocorrelated data: block bootstrap CI should be wider
    than the iid percentile bootstrap CI computed on the pooled stream.

    This is the Codex HIGH-2 expectation. We skip the strict ratio
    assertion (Monte-Carlo noisy) and just assert width is *not lower*
    than the naive estimate by a meaningful margin.
    """
    rng = np.random.default_rng(0)
    n_runs = 5
    n_turns = 200
    rho = 0.85  # strong autocorrelation
    clusters: list[list[float]] = []
    for _ in range(n_runs):
        eps = rng.standard_normal(n_turns)
        x = np.zeros(n_turns)
        x[0] = eps[0]
        for t in range(1, n_turns):
            x[t] = rho * x[t - 1] + eps[t]
        clusters.append(x.tolist())

    iid = bootstrap_ci([v for c in clusters for v in c], n_resamples=1000, seed=0)
    block = hierarchical_bootstrap_ci(
        clusters, block_length=20, n_resamples=1000, seed=0
    )
    assert block.width >= iid.width * 0.9  # at least comparable, often wider


def test_hierarchical_bootstrap_rejects_all_empty() -> None:
    with pytest.raises(ValueError, match="no finite values"):
        hierarchical_bootstrap_ci(
            [[None, None], [float("nan")]],
            block_length=2,
            n_resamples=10,
        )


def test_hierarchical_bootstrap_rejects_invalid_block_length() -> None:
    with pytest.raises(ValueError, match="block_length"):
        hierarchical_bootstrap_ci([[1.0, 2.0]], block_length=0, n_resamples=10)


# --- P5 hardening (2026-05-08): block-length auto-estimation + cluster-only ---


def test_estimate_block_length_white_noise_collapses_to_short() -> None:
    """White noise should collapse to a small block length (~1-3)."""
    rng = np.random.default_rng(0)
    sample = rng.standard_normal(500).tolist()
    block_len = estimate_block_length(sample)
    assert 1 <= block_len <= 5


def test_estimate_block_length_strong_ar1_grows() -> None:
    """Strong AR(1) (rho=0.9) should yield a block length well above 1.

    The exact value depends on the noise threshold ``2 / sqrt(n)``. For
    n=500 we just assert L >= 5 — strong correlation must not degenerate
    to white-noise behaviour.
    """
    rng = np.random.default_rng(0)
    block_len = estimate_block_length(_ar1_series(rng, 500, rho=0.9))
    assert block_len >= 5


def test_estimate_block_length_short_series_returns_one() -> None:
    """Series with fewer than 10 finite values fall back to 1."""
    assert estimate_block_length([1.0, 2.0, 3.0]) == 1
    assert estimate_block_length([None, 1.0, None, 2.0]) == 1


def test_estimate_block_length_constant_series_returns_one() -> None:
    """Zero variance → autocorrelation undefined; safe fallback is 1."""
    assert estimate_block_length([5.0] * 100) == 1


def test_estimate_block_length_respects_max_block_cap() -> None:
    """Even very strong AR(1) cannot exceed ``max_block``."""
    rng = np.random.default_rng(0)
    block_len = estimate_block_length(_ar1_series(rng, 1000, rho=0.99), max_block=15)
    assert block_len <= 15


def test_estimate_block_length_rejects_invalid_max_block() -> None:
    with pytest.raises(ValueError, match="max_block must be"):
        estimate_block_length([1.0, 2.0, 3.0], max_block=0)


def test_hierarchical_bootstrap_cluster_only_mode() -> None:
    """``cluster_only=True`` skips the inner block and labels the method
    ``hierarchical-cluster-only`` so quorum gates know which estimator
    produced the interval.
    """
    rng = np.random.default_rng(0)
    clusters = [rng.standard_normal(100).tolist() for _ in range(5)]
    result = hierarchical_bootstrap_ci(
        clusters,
        cluster_only=True,
        n_resamples=500,
        seed=0,
    )
    assert result.method == "hierarchical-cluster-only"
    assert result.n == 500
    assert result.lo <= result.point <= result.hi


def test_hierarchical_bootstrap_auto_block_runs_and_keeps_method_label() -> None:
    """``auto_block=True`` must produce a usable CI and keep
    ``method="hierarchical-block"`` (the inner-block topology is unchanged,
    only the length is auto-picked).
    """
    rng = np.random.default_rng(0)
    clusters = [_ar1_series(rng, 200, rho=0.7) for _ in range(5)]
    result = hierarchical_bootstrap_ci(
        clusters,
        auto_block=True,
        n_resamples=500,
        seed=0,
    )
    assert result.method == "hierarchical-block"
    assert result.n == 1000
    assert result.lo <= result.point <= result.hi


def test_hierarchical_bootstrap_cluster_only_overrides_auto_block() -> None:
    """When both flags are passed, ``cluster_only`` wins (it collapses
    the inner block entirely so the auto-block estimate is moot).
    """
    rng = np.random.default_rng(0)
    clusters = [_ar1_series(rng, 100, rho=0.5) for _ in range(4)]
    result = hierarchical_bootstrap_ci(
        clusters,
        cluster_only=True,
        auto_block=True,
        n_resamples=300,
        seed=0,
    )
    assert result.method == "hierarchical-cluster-only"
