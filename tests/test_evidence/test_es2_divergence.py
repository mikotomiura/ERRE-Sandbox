"""Falsifiability + non-saturation pins for the ES-2 JS scoring (measurable ADR §6).

These tests are the machine guarantee that the superseding Jensen-Shannon metric is
**able to fail** (has discriminating power) and is **non-saturating** (the defect
that made the old set-Jaccard ``D_obs`` ≡ 1 on the ``48^4`` tuple support, forcing
INCONCLUSIVE). They pin only metric *properties*; the verdict value itself is
produced once by ``scripts/es2_verdict_run.py`` and recorded in ``.steering/`` —
never baked into a test.

Mandatory conditions (measurable ADR §6):

* **JS properties** — identical ⇒ 0, disjoint ⇒ 1, symmetric, ∈[0,1].
* **identity-coords fixture** — an identical kernel + identical draw ⇒ ``D_obs ≈ 0``
  (the metric can read 0; it is not an "always divergent" metric).
* **matched-null** — the content-stratified swap null produces *low* divergences
  (the null can lower ``D``), not a saturated ceiling.
* **consistency (non-saturation)** — two samples of the **same** distribution give a
  JS that *shrinks* with sample size, contrasted with a high-support set-Jaccard
  that stays saturated regardless of ``n`` (the structural reason for the switch).
* **canonical key / no-spurious** — a semantic-isomorphic relabel ⇒ JS = 0 (the raw
  per-arm id never enters a transition cell, Codex H1).
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es2_replay.divergence import (
    js_divergence,
    transition_distribution,
    tv_distance,
)
from erre_sandbox.evidence.es2_replay.permutation_null import n_a_null_distribution
from erre_sandbox.evidence.es2_replay.recombination import (
    kernel_weights,
    proximity_matrix,
    replay_walks,
    semantic_matrix,
    synthetic_embeddings,
)
from erre_sandbox.evidence.es2_replay.scenario import build_seed_result

# --- JS divergence properties -------------------------------------------------


def test_js_identical_distributions_is_zero() -> None:
    p = np.array([0.5, 0.5, 0.0, 0.0])
    assert js_divergence(p, p) == 0.0


def test_js_disjoint_support_is_one() -> None:
    p = np.array([0.5, 0.5, 0.0, 0.0])
    q = np.array([0.0, 0.0, 0.5, 0.5])
    assert abs(js_divergence(p, q) - 1.0) < 1e-12


def test_js_is_symmetric_and_bounded() -> None:
    rng = np.random.default_rng(0)
    for _ in range(50):
        p = rng.random(30)
        q = rng.random(30)
        d_pq = js_divergence(p, q)
        d_qp = js_divergence(q, p)
        assert abs(d_pq - d_qp) < 1e-12  # symmetric
        assert 0.0 <= d_pq <= 1.0  # bounded


def test_js_accepts_unnormalised_counts() -> None:
    # The same shape at different totals must give the identical JS (internal norm).
    p = np.array([2.0, 6.0, 0.0])
    q = np.array([20.0, 60.0, 0.0])
    assert js_divergence(p, q) == 0.0


def test_zero_mass_input_is_zero_not_nan() -> None:
    # An empty (all-zero) distribution is ill-defined; the function returns 0.0
    # rather than NaN (the under-sampling gate, not this function, rejects it).
    p = np.zeros(5)
    q = np.array([0.0, 1.0, 0.0, 0.0, 0.0])
    assert js_divergence(p, q) == 0.0
    assert tv_distance(p, q) == 0.0


# --- identity-coords fixture (discriminating power) ---------------------------


def _identity_kernel_seeds(seed: int, n: int) -> tuple[np.ndarray, np.ndarray]:
    m = 16
    coords = np.random.default_rng(99).standard_normal((m, 3))
    weights = kernel_weights(
        proximity_matrix(coords), semantic_matrix(synthetic_embeddings(m))
    )
    return replay_walks(weights, n, 4, np.random.default_rng(seed))


def test_identity_coords_gives_zero_d_obs() -> None:
    # Same kernel + same rng draw ⇒ identical seeds ⇒ identical transition
    # distributions ⇒ D_obs = 0. The metric can read 0 (it is not always-divergent).
    seeds1, valid1 = _identity_kernel_seeds(5, 1024)
    seeds2, valid2 = _identity_kernel_seeds(5, 1024)
    p1 = transition_distribution(seeds1, valid1, 16)
    p2 = transition_distribution(seeds2, valid2, 16)
    assert np.array_equal(seeds1, seeds2)
    assert js_divergence(p1, p2) == 0.0


# --- matched-null can lower D -------------------------------------------------


def test_matched_null_produces_low_divergences() -> None:
    # The content-stratified swap null destroys the A/B path binding; the JS scores
    # then sit LOW (the null can lower D), not pinned at a saturated ceiling.
    m = 16
    rng0 = np.random.default_rng(0)
    coords_a = rng0.standard_normal((m, 3))
    coords_b = rng0.standard_normal((m, 3))
    sem = semantic_matrix(synthetic_embeddings(m))
    d_perm = n_a_null_distribution(
        coords_a,
        coords_b,
        sem,
        n_perm=64,
        n_replay=256,
        l_seed=4,
        rng=np.random.default_rng(1),
    )
    assert float(np.median(d_perm)) < 0.5  # null mass sits low, not saturated
    assert float(d_perm.max()) < 0.9  # never the spurious set-Jaccard ceiling


# --- consistency: JS non-saturating vs set-Jaccard saturating -----------------


def test_js_shrinks_with_sample_size_on_same_distribution() -> None:
    # Two samples of the SAME multinomial: JS shrinks as n grows (consistent
    # estimator). This is the property the old set-Jaccard lacked.
    rng = np.random.default_rng(7)
    base = rng.random(20)
    base /= base.sum()
    js_small = js_divergence(rng.multinomial(50, base), rng.multinomial(50, base))
    js_large = js_divergence(rng.multinomial(20000, base), rng.multinomial(20000, base))
    assert js_large < js_small
    assert js_large < 0.01  # converges toward 0


def test_set_jaccard_stays_saturated_on_high_support() -> None:
    # Contrast: a set over a support ≫ the sample (the 48^4 regime) gives a Jaccard
    # near 1 for the SAME distribution regardless of n — the structural saturation
    # the measurable ADR replaces. Both n give a near-ceiling distance.
    rng = np.random.default_rng(11)
    k = 10_000

    def jaccard_of_two_samples(n: int) -> float:
        s1 = set(rng.integers(0, k, n).tolist())
        s2 = set(rng.integers(0, k, n).tolist())
        return 1.0 - len(s1 & s2) / len(s1 | s2)

    assert jaccard_of_two_samples(100) > 0.9
    assert jaccard_of_two_samples(400) > 0.9  # does not shrink (saturated)


# --- canonical key / no-spurious (Codex H1) -----------------------------------


def test_no_spurious_margin_is_zero_under_isomorphic_relabel() -> None:
    # A semantic-isomorphic relabel (raw id namespace changed, semantic matrix
    # preserved) leaves the de-novo directed-transition distribution bit-identical,
    # so the JS margin is exactly 0 — the raw per-arm id never enters a cell.
    _result, forensic = build_seed_result(0, m=16, n_replay=256, n_perm=4, l_seed=4)
    assert forensic.no_spurious_margin == 0.0


def test_transition_distribution_is_on_content_index_only() -> None:
    # The cells depend only on the integer content-index sequences: two seed arrays
    # with the same sequences give the identical distribution irrespective of how
    # they were produced (no external raw-id channel).
    seeds = np.array([[0, 3, 1, 2], [4, 1, 0, 7]], dtype=np.int64)
    valid = np.array([True, True])
    p1 = transition_distribution(seeds, valid, 16)
    p2 = transition_distribution(seeds.copy(), valid.copy(), 16)
    assert np.array_equal(p1, p2)
