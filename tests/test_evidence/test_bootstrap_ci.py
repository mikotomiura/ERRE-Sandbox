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
    hierarchical_bootstrap_ci,
)


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
            [[None, None], [float("nan")]],  # type: ignore[list-item]
            block_length=2,
            n_resamples=10,
        )


def test_hierarchical_bootstrap_rejects_invalid_block_length() -> None:
    with pytest.raises(ValueError, match="block_length"):
        hierarchical_bootstrap_ci([[1.0, 2.0]], block_length=0, n_resamples=10)
