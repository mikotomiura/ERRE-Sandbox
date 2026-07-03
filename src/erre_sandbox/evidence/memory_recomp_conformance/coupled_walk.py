"""Downstream decision ``D``: the independent post-idle occupancy walk (§2 / §5).

``D`` re-instantiates the **same frozen Pólya-urn preferential-return mechanism**
as the ES-2 formation walk, but with an **independent RNG stream and independent
``visit_count`` initialisation** (design-final.md §5). Its *only* coupling to the
channel ``C`` is a ``target_zone`` match bonus that reuses the frozen
``POLYA_ALPHA`` (no new free effect parameter, §6):

    weight(z) = POLYA_ALPHA + visit_count(z) + (bonus if z == target_zone else 0)

The walk is a 5-zone **occupancy** walk (we read where it dwells, not which
fragments it forms). It is vectorised across a batch of configurations that share
the **same per-step uniform draws** so a coupled / marginal / permuted-target
comparison is *paired* (only the bonus term differs): this is what makes
``conform_s(z)`` an exact deterministic function of the bonus zone ``z`` for a
fixed seed (design-final.md §2, ``DA-MEMSEAM-IMPL-2``).

**Non-circularity (§5)**: no function here takes any ``C`` / replay-walk state.
The sole channel input is the scalar ``target_zone`` index. The independence pin
test (:mod:`tests`) asserts that the same ``target_zone`` from a *different* ``C``
trace leaves the weights byte-identical.
"""

from __future__ import annotations

import numpy as np


def neighbor_weights(
    here: int,
    visit_count: np.ndarray,
    adjacency_mask: np.ndarray,
    target_zone: int,
    *,
    alpha: float,
    bonus: float,
) -> np.ndarray:
    """One-step transition weights over the ``Z`` zones from ``here`` (§2 formula).

    ``weight(z) = alpha + visit_count[z] + (bonus if z == target_zone else 0)`` for
    zones ``z`` adjacent to ``here`` (``adjacency_mask[here, z]``), else 0.
    ``target_zone < 0`` disables the bonus (the marginal / no-channel config).

    Reference single-step implementation. Reads **no** ``C`` state — only the
    scalar ``target_zone`` — which the §5 independence pin test relies on.
    """
    z = adjacency_mask.shape[0]
    zones = np.arange(z)
    bonus_vec = bonus * (zones == target_zone) if target_zone >= 0 else 0.0
    base = alpha + visit_count + bonus_vec
    return np.where(adjacency_mask[here], base, 0.0)


def post_idle_walk_occupancies(
    start: int,
    steps: int,
    adjacency_mask: np.ndarray,
    uniforms: np.ndarray,
    target_zones: np.ndarray,
    *,
    alpha: float,
    bonus: float,
) -> np.ndarray:
    """Pooled post-idle occupancy per config, paired across configs on shared noise.

    Estimates the **expected** occupancy distribution of each config by pooling
    ``R`` independent walk realizations (design-final.md §2 conditions ``D`` on ``C``
    *in distribution*; a single realization makes ``conform`` degenerate,
    ``DA-MEMSEAM-IMPL-5``). All configs reuse the **same** ``R`` per-step
    uniform-draw vectors, so a config-to-config comparison is *paired* (only the
    ``target_zone`` bonus differs, realization for realization).

    Each of the ``C = target_zones.size`` configs runs ``R`` preferential-return
    walks from the shared ``start`` zone; realization ``r`` of every config consumes
    ``uniforms[r, t]`` at step ``t``. ``visit_count`` starts fresh per walk (``start``
    seeded to 1) — independent of any ``C`` replay walk (§5). ``target_zones[c] < 0``
    ⇒ marginal (no bonus).

    Args:
        start: Shared blind-drawn start zone index (shared with the formation walk).
        steps: Walk length (occupancy positions counted) = ``M_FRAGMENTS``.
        adjacency_mask: ``(Z, Z)`` bool zone adjacency.
        uniforms: ``(R, steps)`` per-realization per-step uniform draws in
            ``[0, 1)`` (shared across configs).
        target_zones: ``(C,)`` bonus-zone index per config (``-1`` ⇒ marginal).
        alpha: Pólya prior (``POLYA_ALPHA``).
        bonus: coupling bonus strength (``POLYA_ALPHA`` for the real verdict; a
            ladder multiple for the synthetic power sim).

    Returns:
        ``(C, Z)`` occupancy counts pooled over the ``R`` realizations (each row sums
        to ``R * steps``). Deterministic in
        ``(start, uniforms, target_zones, alpha, bonus)``; no ``C`` dependence.
    """
    z = adjacency_mask.shape[0]
    c = int(target_zones.size)
    r = int(uniforms.shape[0])
    b = c * r
    zones = np.arange(z)

    # Batch row layout: config-major, realization-minor → row = cfg*R + rea.
    cfg = np.repeat(np.arange(c), r)  # (B,)
    rea = np.tile(np.arange(r), c)  # (B,)
    tgt = target_zones[cfg]  # (B,)
    bonus_grid = bonus * ((tgt[:, None] == zones[None, :]) & (tgt[:, None] >= 0))

    here = np.full(b, start, dtype=np.int64)
    rows = np.arange(b)
    visit = np.zeros((b, z), dtype=np.float64)
    visit[:, start] = 1.0
    occ = np.zeros((b, z), dtype=np.float64)
    occ[:, start] += 1.0  # position 0 = start (every walk)

    for t in range(1, steps):
        cand = adjacency_mask[here]  # (B, Z) bool
        w = np.where(cand, alpha + visit + bonus_grid, 0.0)
        totals = w.sum(axis=1)
        safe = np.where(totals > 0.0, totals, 1.0)
        cdf = np.cumsum(w / safe[:, None], axis=1)
        u = uniforms[rea, t]  # (B,) — realization r's step-t draw, shared over configs
        nxt = np.clip((cdf < u[:, None]).sum(axis=1), 0, z - 1)
        here = nxt
        visit[rows, nxt] += 1.0
        occ[rows, nxt] += 1.0

    pooled = np.zeros((c, z), dtype=np.float64)
    np.add.at(pooled, cfg, occ)  # sum realizations per config
    return pooled


__all__ = ["neighbor_weights", "post_idle_walk_occupancies"]
