"""Channel-conformance statistics for the memory-recomposition seam (§2 / §4).

Pure ``numpy``/stdlib functions that turn the per-seed channel ``C`` and decision
``D`` into the frozen verdict inputs:

* :func:`occupancy_entropy` / :func:`conform_vector` — the scale-free entropy
  reduction ``conform_s(z) = (H(marginal) - H(coupled|z)) / H(marginal)`` that
  conditioning ``D`` on a ``target_zone = z`` bonus produces (paired on shared walk
  noise; the 5-vector over zones is exact because ``target_zone`` has ``Z = 5``
  support, ``DA-MEMSEAM-IMPL-2``);
* :func:`exact_permutation_null_quantile` — the **C↔D pairing-destroying** null:
  the empirical quantile of ``conform_s`` evaluated at *other* seeds'
  ``target_zone`` assignments. Computed exactly over the ``Z``-support population
  (the ``N_PERM → ∞`` limit, design-final.md §4-4), so it is deterministic;
* :func:`channel_effective_support` — the channel's inverse-Simpson effective
  support (degenerate-collapse guard, reuses the ES-2 diagnostic);
* :func:`argmax_stability` — the channel argmax's bootstrap-resample recovery rate
  (ill-posed-channel guard, majority rule);
* :func:`synthetic_power_curve` — a **synthetic-data-only** power ladder: with a
  maximally informative channel injected at each coupling strength, the fraction of
  replicate banks that recover ``CI_lower > 0``. The ``1.0 × POLYA_ALPHA`` rung is
  the ``SYNTHETIC_POWER_PASS_MIN`` feasibility gate. It never reads the real
  verdict (design-final.md §4-2).

Nothing here reads a raw fragment id, an A/B label, or any ``C`` replay state
beyond the scalar ``target_zone`` — the non-circularity the §5 gate protects.
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.bootstrap_ci import BootstrapResult, bootstrap_ci
from erre_sandbox.evidence.es2_replay.divergence import (
    effective_support,
    transition_distribution,
)
from erre_sandbox.evidence.memory_recomp_conformance.channel import (
    dominant_transition_cell,
)
from erre_sandbox.evidence.memory_recomp_conformance.coupled_walk import (
    post_idle_walk_occupancies,
)


def occupancy_entropy(occupancy: np.ndarray) -> float:
    """Shannon entropy (bits) of a zone-occupancy count/probability vector.

    Normalises ``occupancy`` defensively and applies the ``0·log0 = 0`` convention.
    Returns 0.0 for an all-zero or single-zone (collapsed) occupancy — the caller's
    per-seed validity guard rejects ``H(marginal) == 0`` (design-final.md §2).
    """
    p = np.asarray(occupancy, dtype=np.float64)
    total = float(p.sum())
    if total <= 0.0:
        return 0.0
    p = p / total
    nz = p[p > 0.0]
    return float(-np.sum(nz * np.log2(nz)))


def conform_vector(
    marginal_occupancy: np.ndarray,
    coupled_occupancies: np.ndarray,
) -> np.ndarray:
    """Per-zone scale-free entropy reduction ``conform_s(z)`` (design-final.md §2).

    ``marginal_occupancy`` is the ``(Z,)`` no-bonus occupancy; ``coupled_occupancies``
    is ``(Z, Z)`` — row ``z`` is the occupancy with a ``target_zone = z`` bonus, on
    the **same** shared walk noise (paired). Returns a ``(Z,)`` vector
    ``(H(marginal) - H(coupled[z])) / H(marginal)``. If ``H(marginal) == 0`` (the
    marginal walk collapsed to one zone) the seed is invalid; an all-``nan`` vector
    is returned so the caller's validity guard drops it.
    """
    h_marginal = occupancy_entropy(marginal_occupancy)
    z = coupled_occupancies.shape[0]
    if h_marginal <= 0.0:
        return np.full(z, np.nan, dtype=np.float64)
    reductions = np.array(
        [(h_marginal - occupancy_entropy(coupled_occupancies[k])) for k in range(z)],
        dtype=np.float64,
    )
    return reductions / h_marginal


def channel_effective_support(distribution: np.ndarray) -> float:
    """Inverse-Simpson effective support of the channel transition distribution.

    Reuses the frozen ES-2 :func:`effective_support` (Hill number order 2). Below
    ``EFFECTIVE_SUPPORT_MIN`` the channel argmax is the sole occupant, not a
    competitive winner ⇒ degenerate ⇒ INCONCLUSIVE (design-final.md §4-4).
    """
    return effective_support(distribution).simpson


def argmax_stability(
    seeds: np.ndarray,
    valid: np.ndarray,
    m: int,
    rng: np.random.Generator,
    n_resamples: int,
) -> float:
    """Bootstrap-resample recovery rate of the channel argmax cell (majority rule).

    Resamples the idle-recomposition replay seeds (rows, with replacement)
    ``n_resamples`` times, recomputes the ``transition_distribution`` argmax cell
    each time, and returns the fraction matching the original argmax. Below
    ``ARGMAX_STABILITY_MIN`` the channel is ill-posed ⇒ INCONCLUSIVE
    (design-final.md §4-4).
    """
    n = seeds.shape[0]
    if n == 0:
        return 0.0
    orig = dominant_transition_cell(transition_distribution(seeds, valid, m), m)
    hits = 0
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        dist_r = transition_distribution(seeds[idx], valid[idx], m)
        if dominant_transition_cell(dist_r, m) == orig:
            hits += 1
    return hits / n_resamples


def exact_permutation_null_quantile(
    conform_row: np.ndarray,
    target_zones: np.ndarray,
    s_index: int,
    quantile: float,
) -> float:
    """Exact C↔D pairing-destroying null quantile for seed ``s_index``.

    The null is ``{conform_row[target_zones[s']] : s' != s_index}`` — seed ``s``'s
    own ``conform`` vector evaluated at every *other* seed's ``target_zone`` (the
    pairing broken). Because ``target_zone`` support is only ``Z`` zones this is the
    **deterministic exact Type-7 empirical quantile** over that finite population
    (design-final.md §4-4). Two caveats (``DA-MEMSEAM-IMPL-7``): (a) it is "exact" only
    under the ``MIN_VALID_SEEDS`` gate — an extremely small population would lean on
    ``np.quantile`` interpolation; (b) the population Type-7 quantile differs from the
    ``N_PERM → ∞`` *sampling* limit (inverse-CDF) by ``≤ 0.00247`` on the verdict run,
    **verdict-invariant**. Returns the ``quantile``.
    """
    others = np.delete(np.asarray(target_zones, dtype=np.int64), s_index)
    if others.size == 0:
        return float("nan")
    null_values = conform_row[others]
    return float(np.quantile(null_values, quantile))


def deltas_ci(
    deltas: list[float],
    *,
    n_resamples: int,
    ci_alpha: float,
    seed: int = 0,
) -> BootstrapResult:
    """Bootstrap CI of the per-seed ``{delta_s}`` (GO ⇔ ``lo > 0``, design §4-4).

    Uses the frozen ES-1 percentile bootstrap (``mean`` statistic) at a two-sided
    ``1 - ci_alpha`` coverage — the same one-sided lower-bound gate as ES-2's N-a CI.
    """
    return bootstrap_ci(
        deltas,
        n_resamples=n_resamples,
        ci=1.0 - ci_alpha,
        seed=seed,
        statistic="mean",
    )


def _bank_detection(
    conform_rows: np.ndarray,
    injected_targets: np.ndarray,
    *,
    quantile: float,
    n_resamples: int,
    ci_alpha: float,
) -> bool:
    """One synthetic bank: ``CI_lower(delta_s) > 0`` with the injected channel."""
    n_seed = conform_rows.shape[0]
    deltas = [
        float(conform_rows[s, injected_targets[s]])
        - exact_permutation_null_quantile(
            conform_rows[s], injected_targets, s, quantile
        )
        for s in range(n_seed)
    ]
    finite = [d for d in deltas if np.isfinite(d)]
    if len(finite) < 2:  # noqa: PLR2004 — need ≥2 to bootstrap a CI
        return False
    ci = deltas_ci(finite, n_resamples=n_resamples, ci_alpha=ci_alpha)
    return ci.lo > 0.0


def synthetic_power_curve(
    adjacency_mask: np.ndarray,
    *,
    steps: int,
    realizations: int,
    n_seed: int,
    ladder: tuple[float, ...],
    n_replicates: int,
    alpha: float,
    quantile: float,
    n_resamples: int,
    ci_alpha: float,
    rng: np.random.Generator,
) -> dict[float, float]:
    """Synthetic-data-only detection-rate ladder (feasibility gate, §4-2).

    For each coupling strength ``k`` in ``ladder`` (× ``alpha``) and each of
    ``n_replicates`` synthetic banks, injects a **maximally informative** channel —
    every synthetic seed's ``target_zone`` is set to the argmax of its own
    ``conform`` vector at strength ``k`` — and records whether the bootstrap CI
    recovers ``lo > 0``. Returns ``{k: detection_rate}``. The ``k = 0`` rung is a
    null-calibration check (detection ≈ ``ci_alpha``); the ``k = 1.0`` rung is the
    ``SYNTHETIC_POWER_PASS_MIN`` gate. Reads no real-verdict data — it validates
    that the statistics *can* detect a real channel at the design's strength.

    The best-case injection (argmax of the seed's own conform vector) is the
    strongest honest channel: if even it cannot reach the pass bar the apparatus is
    genuinely underpowered (→ INCONCLUSIVE), never tuned to pass.
    """
    z = adjacency_mask.shape[0]
    config_targets = np.concatenate([[-1], np.arange(z)]).astype(np.int64)  # marginal+Z
    curve: dict[float, float] = {}
    for k in ladder:
        bonus = k * alpha
        detections = 0
        for _ in range(n_replicates):
            conform_rows = np.empty((n_seed, z), dtype=np.float64)
            injected = np.empty(n_seed, dtype=np.int64)
            for s in range(n_seed):
                start = int(rng.integers(0, z))
                uniforms = rng.random((realizations, steps))
                occ = post_idle_walk_occupancies(
                    start,
                    steps,
                    adjacency_mask,
                    uniforms,
                    config_targets,
                    alpha=alpha,
                    bonus=bonus,
                )
                row = conform_vector(occ[0], occ[1:])
                conform_rows[s] = row
                injected[s] = 0 if not np.all(np.isfinite(row)) else int(np.argmax(row))
            if _bank_detection(
                conform_rows,
                injected,
                quantile=quantile,
                n_resamples=n_resamples,
                ci_alpha=ci_alpha,
            ):
                detections += 1
        curve[k] = detections / n_replicates
    return curve


__all__ = [
    "argmax_stability",
    "channel_effective_support",
    "conform_vector",
    "deltas_ci",
    "exact_permutation_null_quantile",
    "occupancy_entropy",
    "synthetic_power_curve",
]
