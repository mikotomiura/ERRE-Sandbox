"""① matched permutation nulls for the M13-ES2 replay apparatus (§7, Codex H4/H5).

Two nulls over the A/B de-novo seed-structure divergence ``D_obs`` (a Jaccard
distance over ``canonical_seed_structure_id`` sets):

* **N-a — content-stratified paired permutation** (primary, Codex H4). For each
  canonical content ``c_i`` the two fragments — A's at ``loc_A(i)`` and B's at
  ``loc_B(i)`` — have their A/B label swapped by an **independent Bernoulli coin**.
  Each permuted arm therefore keeps the **full content multiset** (every content
  once); only the per-content location *binding* (A-path vs B-path) is reshuffled,
  so the null destroys the coherent A/B path structure **without** turning into a
  content-composition null. Replay + de-novo filter are re-run on the permuted
  locations and the Jaccard recomputed → one ``D_perm`` per permutation.
* **N-b — within-agent pairing permutation** (mandatory sensitivity / claim
  stratifier, Codex M1). Each agent's content↔location pairing is permuted within
  the agent, preserving its **visited-location marginal** but destroying the
  *ordered* pairing. It is **not** promoted to primary; it is run after a GO to
  stratify the claim (N-b pass → ordered content-location pairing; N-b fail →
  home-range / path-label only; ``design-final.md`` §0).

The bootstrap that turns these into a verdict uses the **scenario seed** as the
outer independent unit (Codex H5): per seed ``null_q_s = quantile(D_perm_s,
PERM_NULL_QUANTILE)`` and ``delta_s = D_obs_s - null_q_s``; ``N_PERM`` only
estimates the per-seed quantile and is never a bootstrap sample size. That step
lives in :mod:`verdict_report`; this module produces the per-seed ``D_perm``
distributions.

**Scoring (measurable ADR §3)**: the permutation *mechanism* is frozen
(:func:`stratified_swap` content-stratified swap / the N-b within-agent pairing),
but the per-permutation score is the **Jensen-Shannon divergence over the
directed-transition distribution** (:mod:`divergence`), matching the superseded
headline ``D_obs``. The legacy set-Jaccard primitive :func:`jaccard_distance_int`
is retained as a **forensic contrast only** (it lets the run record the old
saturated metric side-by-side) and is pinned byte-equal to the frozen
:func:`erre_sandbox.evidence.spdm.probe.jaccard_distance` in the test.
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es2_replay.divergence import (
    js_divergence,
    transition_distribution,
)
from erre_sandbox.evidence.es2_replay.recombination import (
    kernel_weights,
    proximity_matrix,
    replay_walks,
)


def jaccard_distance_int(a: np.ndarray, b: np.ndarray) -> float:
    """Jaccard distance ``1 - |a∩b| / |a∪b|`` over integer id sets ∈ [0, 1].

    Mirrors :func:`erre_sandbox.evidence.spdm.probe.jaccard_distance` (two empty
    sets ⇒ distance 0) but on ``numpy`` integer arrays. **Forensic contrast only**
    after the measurable ADR (the superseded set metric); pinned equal to the frozen
    string-set version in the test.
    """
    sa = np.unique(a)
    sb = np.unique(b)
    union = sa.size + sb.size
    if union == 0:
        return 0.0
    inter = np.intersect1d(sa, sb, assume_unique=True).size
    denom = union - inter
    if denom == 0:
        return 0.0
    return 1.0 - inter / denom


def stratified_swap(
    coords_a: np.ndarray,
    coords_b: np.ndarray,
    coin: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Content-stratified A/B location swap for one permutation (Codex H4).

    ``coin`` is a boolean per-content vector. Where it is set, content ``i``'s A/B
    locations swap; the returned ``(arm_a, arm_b)`` therefore each hold **every
    content exactly once** (the full content multiset is preserved — composition is
    never nulled), with only the per-content location *binding* reshuffled.
    """
    c = coin[:, None]
    arm_a = np.where(c, coords_b, coords_a)
    arm_b = np.where(c, coords_a, coords_b)
    return arm_a, arm_b


def _arm_transition_distribution(
    coords: np.ndarray,
    semantic: np.ndarray,
    n_replay: int,
    l_seed: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Replay one arm → its de-novo directed-transition distribution (measurable ADR).

    The replay kernel (proximity × semantic), self-avoiding walk and de-novo filter
    are the frozen apparatus; only the readout is the JS-scored transition
    distribution instead of the superseded structure-id set.
    """
    weights = kernel_weights(proximity_matrix(coords), semantic)
    seeds, valid = replay_walks(weights, n_replay, l_seed, rng)
    return transition_distribution(seeds, valid, coords.shape[0])


def n_a_null_distribution(
    coords_a: np.ndarray,
    coords_b: np.ndarray,
    semantic: np.ndarray,
    *,
    n_perm: int,
    n_replay: int,
    l_seed: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """``(n_perm,)`` ``D_perm`` under content-stratified paired permutation (N-a).

    ``coords_a`` / ``coords_b`` are the ``(m, 3)`` fragment locations of arms A / B
    (content ``i`` shares ``semantic`` row ``i`` across arms; only location
    differs). Each permutation flips a per-content coin: where the coin is set,
    content ``i``'s A/B locations swap, so each permuted arm keeps every content
    exactly once. Deterministic under ``rng`` (all coins drawn first, then the
    per-permutation replay stream).
    """
    coins = rng.integers(0, 2, size=(n_perm, coords_a.shape[0])).astype(bool)
    d_perm = np.empty(n_perm, dtype=np.float64)
    for p in range(n_perm):
        arm_a, arm_b = stratified_swap(coords_a, coords_b, coins[p])
        dist_a = _arm_transition_distribution(arm_a, semantic, n_replay, l_seed, rng)
        dist_b = _arm_transition_distribution(arm_b, semantic, n_replay, l_seed, rng)
        d_perm[p] = js_divergence(dist_a, dist_b)
    return d_perm


def n_b_null_distribution(
    coords_a: np.ndarray,
    coords_b: np.ndarray,
    semantic: np.ndarray,
    *,
    n_perm: int,
    n_replay: int,
    l_seed: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """``(n_perm,)`` ``D_perm`` under within-agent pairing permutation (N-b).

    Each permutation independently permutes the content↔location pairing inside
    each agent (``coords[perm]``), preserving each agent's visited-location
    marginal while destroying the ordered pairing. Sharper path-dependence
    isolation than N-a but a distinct estimand (Codex M1) — used to stratify the
    claim, never as the primary gate. Deterministic under ``rng``.
    """
    m = coords_a.shape[0]
    d_perm = np.empty(n_perm, dtype=np.float64)
    for p in range(n_perm):
        arm_a = coords_a[rng.permutation(m)]
        arm_b = coords_b[rng.permutation(m)]
        dist_a = _arm_transition_distribution(arm_a, semantic, n_replay, l_seed, rng)
        dist_b = _arm_transition_distribution(arm_b, semantic, n_replay, l_seed, rng)
        d_perm[p] = js_divergence(dist_a, dist_b)
    return d_perm


__all__ = [
    "jaccard_distance_int",
    "n_a_null_distribution",
    "n_b_null_distribution",
    "stratified_swap",
]
