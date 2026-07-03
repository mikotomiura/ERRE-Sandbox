"""Channel-conformance statistics: entropy, conform, exact null, argmax, power."""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.memory_recomp_conformance import constants as _c
from erre_sandbox.evidence.memory_recomp_conformance.conformance_stats import (
    argmax_stability,
    channel_effective_support,
    conform_vector,
    deltas_ci,
    exact_permutation_null_quantile,
    occupancy_entropy,
    synthetic_power_curve,
)

_ADJ = np.array(
    [
        [0, 1, 0, 0, 0],
        [1, 0, 1, 1, 1],
        [0, 1, 0, 0, 1],
        [0, 1, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    dtype=bool,
)


def test_occupancy_entropy_bounds() -> None:
    assert occupancy_entropy(np.array([5.0, 0.0, 0.0])) == 0.0  # single zone → 0
    assert occupancy_entropy(np.array([0.0, 0.0, 0.0])) == 0.0  # empty → 0
    # uniform over 4 → log2(4) = 2 bits.
    assert abs(occupancy_entropy(np.ones(4)) - 2.0) < 1e-12


def test_conform_vector_positive_when_coupled_more_concentrated() -> None:
    marginal = np.array([10.0, 10.0, 10.0, 10.0])  # uniform, high entropy
    coupled = np.array(
        [
            [40.0, 0.0, 0.0, 0.0],  # z0: fully concentrated → big reduction
            [10.0, 10.0, 10.0, 10.0],  # z1: unchanged → 0
            [25.0, 5.0, 5.0, 5.0],  # z2: partial
            [10.0, 10.0, 10.0, 10.0],
        ]
    )
    conf = conform_vector(marginal, coupled)
    assert conf[0] > conf[2] > 0.0
    assert abs(conf[1]) < 1e-12


def test_conform_vector_invalid_when_marginal_collapsed() -> None:
    marginal = np.array([12.0, 0.0, 0.0])  # H = 0 → seed invalid
    coupled = np.zeros((3, 3))
    conf = conform_vector(marginal, coupled)
    assert np.all(np.isnan(conf))


def test_exact_permutation_null_quantile_excludes_self() -> None:
    conform_row = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    # other seeds' target zones: all point at zone 4 → null values all 0.4.
    target_zones = np.array([2, 4, 4, 4, 4])
    q = exact_permutation_null_quantile(conform_row, target_zones, 0, 0.95)
    assert abs(q - 0.4) < 1e-12


def test_argmax_stability_high_for_dominant_cell() -> None:
    # Seeds all carrying the same (0->1) bigram → argmax rock-stable under resample.
    m = 4
    seeds = np.tile(np.array([0, 1, 2, 3]), (200, 1))
    valid = np.ones(200, dtype=bool)
    rate = argmax_stability(seeds, valid, m, np.random.default_rng(0), 100)
    assert rate == 1.0


def test_channel_effective_support_matches_es2_diagnostic() -> None:
    from erre_sandbox.evidence.es2_replay.divergence import effective_support

    dist = np.array([0.5, 0.25, 0.25, 0.0])
    assert channel_effective_support(dist) == effective_support(dist).simpson


def test_deltas_ci_lower_positive_for_clearly_positive_deltas() -> None:
    ci = deltas_ci([0.3] * 40, n_resamples=500, ci_alpha=0.10)
    assert ci.lo > 0.0


def test_synthetic_power_null_rung_low_full_rung_higher() -> None:
    # k=0 (no injected effect) must detect near-never; k=1.0 must detect more often.
    curve = synthetic_power_curve(
        _ADJ,
        steps=24,
        realizations=64,
        n_seed=16,
        ladder=(0.0, 1.0),
        n_replicates=20,
        alpha=_c.POLYA_ALPHA,
        quantile=_c.PERM_NULL_QUANTILE,
        n_resamples=300,
        ci_alpha=_c.CI_ALPHA,
        rng=np.random.default_rng(0),
    )
    assert curve[0.0] <= 0.2  # null-calibration: rare false detection
    assert curve[1.0] > curve[0.0]  # injected effect detected more often
