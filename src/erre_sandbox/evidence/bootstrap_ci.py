"""Bootstrap confidence intervals for Tier A / Tier B metric aggregates.

m9-eval-system P5 (Codex HIGH-2 in `codex-review.md`): hierarchical
bootstrap with **outer cluster (run) + inner block (circular block of
turn-level samples)** for autocorrelation-aware CI estimation. The DB9
quorum semantics in `design-final.md` requires CI width per
sub-metric to gate ratio confirmation.

This module is drafted in P3a-decide (ahead of the formal P5 phase) so
the stimulus-side ratio sanity-check can run on the pilot DuckDB files
once they are rsync'd from G-GEAR. The full P5 features (block-length
auto-estimation via autocorrelation, AR(1) sensitivity grid) will be
layered on top in the dedicated P5 PR — the public API in this module
is forward-compatible because callers consume CI tuples, not internal
parameters.

Quick reference:

* :func:`bootstrap_ci` — minimum viable percentile bootstrap. Pure
  numpy, deterministic under explicit ``seed``. Works for the P3a-decide
  use-case (per-cell aggregate metrics, no within-cell autocorrelation
  to model because each cell is one persona run).
* :func:`hierarchical_bootstrap_ci` — outer cluster + inner block
  resampling. Used by P3 / P3-validate when there are 5 runs × 500
  turns per persona; the inner block protects the CI from
  underestimating standard error when consecutive turns are correlated.

Both helpers return :class:`BootstrapResult` so plotting / quorum gates
can read ``point / lo / hi / width`` uniformly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_N_RESAMPLES: int = 2000
"""Default bootstrap iteration count.

2000 is enough for percentile CI stability at width <0.005 for
N>=30 sample sizes — the M8 baseline metric pipeline used the same
budget and shipped without observability complaints. For DB9 ratio
gating the stability matters more than the iteration count, so the
parameter is exposed and the script overrides up to 10K when running
overnight.
"""

DEFAULT_CI: float = 0.95
"""Default 2-sided percentile CI (95%)."""


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Bootstrap CI summary returned by every public helper here."""

    point: float
    """The point estimate computed from the original (un-resampled) sample."""
    lo: float
    """Lower percentile bound."""
    hi: float
    """Upper percentile bound."""
    width: float
    """``hi - lo``. Pre-computed because callers compare widths directly
    (DB9 quorum, ME-4 ratio decision) and the dataclass is frozen so
    storing the derived value is safe."""
    n: int
    """Effective sample size used (after dropping NaN/None)."""
    n_resamples: int
    """Bootstrap iteration count."""
    method: str
    """One of ``"percentile"`` / ``"hierarchical-block"``. Surfaced in
    the JSON output so the consumer knows which estimator produced the
    interval."""


def _clean(values: Sequence[float | None]) -> np.ndarray:
    """Drop None / NaN entries and return a float array.

    Per the M8 ``compute_*`` contract, ``None``/``NaN`` mean "no
    measurement" rather than "zero". The bootstrap path drops those
    rows up front so the resampler does not propagate NaN.
    """
    cleaned = [
        float(v)
        for v in values
        if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    return np.asarray(cleaned, dtype=float)


def bootstrap_ci(
    values: Sequence[float | None],
    *,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
    seed: int = 0,
    statistic: str = "mean",
) -> BootstrapResult:
    """Percentile bootstrap CI for ``statistic`` of ``values``.

    Args:
        values: Per-sample measurements (one per cell / turn / item).
            ``None``/``NaN`` entries are dropped via :func:`_clean`.
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.
        seed: Deterministic bitstream seed (``np.random.default_rng``).
        statistic: Either ``"mean"`` (default) or ``"median"``. The
            quorum thresholds in `design-final.md` use means, so the
            default is mean.

    Returns:
        :class:`BootstrapResult` with ``method="percentile"`` and
        ``n`` reflecting the sample size after dropping NaN/None.

    Raises:
        ValueError: If ``ci`` is not in ``(0, 1)``, ``n_resamples < 1``,
            or ``values`` is empty after cleaning.
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1) (got {ci})")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
    if statistic not in {"mean", "median"}:
        raise ValueError(f"statistic must be 'mean' or 'median' (got {statistic!r})")

    cleaned = _clean(values)
    n = cleaned.size
    if n == 0:
        raise ValueError("values has 0 finite entries — cannot bootstrap")

    rng = np.random.default_rng(seed)
    point = (
        float(np.mean(cleaned)) if statistic == "mean" else float(np.median(cleaned))
    )

    indices = rng.integers(0, n, size=(n_resamples, n))
    samples = cleaned[indices]
    if statistic == "mean":
        replicate_stats = samples.mean(axis=1)
    else:
        replicate_stats = np.median(samples, axis=1)

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_stats, alpha / 2.0))
    hi = float(np.quantile(replicate_stats, 1.0 - alpha / 2.0))
    return BootstrapResult(
        point=point,
        lo=lo,
        hi=hi,
        width=hi - lo,
        n=n,
        n_resamples=n_resamples,
        method="percentile",
    )


def hierarchical_bootstrap_ci(
    values_per_cluster: Sequence[Sequence[float | None]],
    *,
    block_length: int = 50,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
    seed: int = 0,
) -> BootstrapResult:
    """Cluster + circular-block bootstrap for autocorrelated turn streams.

    Use this for P3 golden-baseline 5 runs × 500 turns (Codex HIGH-2):
    the outer level resamples runs (clusters) with replacement, and the
    inner level draws circular blocks of length ``block_length`` so the
    within-run autocorrelation is preserved.

    Args:
        values_per_cluster: ``runs`` outer × ``turns`` inner — one
            sequence per run (cluster). NaN/None within a cluster are
            dropped (per :func:`_clean`); a cluster that ends up empty
            is dropped from the outer resample.
        block_length: Inner circular block length (turns). For 500-turn
            runs the literature default 50 covers ~1 effective sample
            per 10 blocks (sensitivity grid for tuning lives in P5).
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.
        seed: Deterministic seed.

    Returns:
        :class:`BootstrapResult` with ``method="hierarchical-block"``
        and ``n`` reflecting the **total** number of finite turn-level
        observations across non-empty clusters (not the cluster count).

    Raises:
        ValueError: On invalid arguments or all-empty clusters.
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1) (got {ci})")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
    if block_length < 1:
        raise ValueError(f"block_length must be >= 1 (got {block_length})")

    cleaned_clusters = [_clean(cluster) for cluster in values_per_cluster]
    cleaned_clusters = [c for c in cleaned_clusters if c.size > 0]
    if not cleaned_clusters:
        raise ValueError("no finite values in any cluster")

    rng = np.random.default_rng(seed)
    pooled = np.concatenate(cleaned_clusters)
    point = float(pooled.mean())
    n_total = pooled.size
    n_clusters = len(cleaned_clusters)

    replicate_means = np.empty(n_resamples, dtype=float)
    for r in range(n_resamples):
        outer_idx = rng.integers(0, n_clusters, size=n_clusters)
        replicate_concat: list[np.ndarray] = []
        for ci_idx in outer_idx:
            cluster = cleaned_clusters[ci_idx]
            cluster_n = cluster.size
            n_blocks = max(1, math.ceil(cluster_n / block_length))
            starts = rng.integers(0, cluster_n, size=n_blocks)
            for s in starts:
                # Circular block (wraps around for indices >= cluster_n).
                idx = (np.arange(block_length) + s) % cluster_n
                replicate_concat.append(cluster[idx])
        replicate = np.concatenate(replicate_concat)
        replicate_means[r] = float(replicate.mean())

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_means, alpha / 2.0))
    hi = float(np.quantile(replicate_means, 1.0 - alpha / 2.0))
    return BootstrapResult(
        point=point,
        lo=lo,
        hi=hi,
        width=hi - lo,
        n=n_total,
        n_resamples=n_resamples,
        method="hierarchical-block",
    )


__all__ = [
    "DEFAULT_CI",
    "DEFAULT_N_RESAMPLES",
    "BootstrapResult",
    "bootstrap_ci",
    "hierarchical_bootstrap_ci",
]
