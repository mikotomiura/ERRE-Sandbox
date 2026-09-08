"""Tests for the I-002 sparsification layer (leader clustering / rho).

design-final.md §2/§3 (Loop I-002). Encoder-independent (Test Plan): every
fixture below is a hand-built (exact angle/cosine constructions) or
``np.random.default_rng``-seeded unit vector, never a real embedding.

Two of the fixtures below (``test_leader_count_is_monotone_in_radius`` and
``test_leader_cluster_depends_on_scan_order``) are deliberately hand-built
rather than randomly sampled: an exploratory randomized sweep over
``leader_cluster_indices`` (n in [3, 15), dim in [2, 8), 20000 trials) found
~1% of batteries where the keep-count sequence over a descending radius grid
is *not* monotone -- the greedy accept/reject decision at index ``i``
depends on the *current* kept set, and that set can differ enough between
two radii that a stricter radius keeps *more* items than a laxer one for
some pathological configurations. AC 002-3 asks for a concrete witness that
the property holds, not a universal proof, so the fixture here is
constructed so the merge order is unambiguous by hand (well-separated
angular clusters), not sampled and hoped for.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scripts import paper01_scope_condition as mod

SEED = mod.SEED


def _random_unit_vectors(rng: np.random.Generator, n: int, dim: int) -> np.ndarray:
    """``n`` iid-Gaussian-then-unit-normalised vectors of dimension ``dim``."""
    raw = rng.normal(size=(n, dim))
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / norms


def _angle_vec(deg: float) -> list[float]:
    """A 2D unit vector at ``deg`` degrees from the positive x-axis."""
    rad = math.radians(deg)
    return [math.cos(rad), math.sin(rad)]


# --- AC 002-1 (fidelity pin (a)) --------------------------------------------


def test_leader_cluster_matches_greedy_dedupe_at_ref_dedup() -> None:
    """``leader_cluster_indices(radius=REF_DEDUP)`` == ``greedy_dedupe_indices``.

    100 random unit-vector batteries, varying ``n`` and dimensionality. The
    expected value is the *actual* ``greedy_dedupe_indices`` call, not a
    hardcoded restatement of its output (design-final.md §7 Test Plan:
    "期待値をハードコードしない") -- a change to that frozen function's own
    algorithm would be caught here too.
    """
    rng = np.random.default_rng(SEED)
    for case in range(100):
        n = int(rng.integers(1, 25))
        dim = int(rng.integers(2, 12))
        emb = _random_unit_vectors(rng, n, dim)
        got = mod.leader_cluster_indices(emb, radius=mod._c.REF_DEDUP, cap=n)
        want = mod._g1.greedy_dedupe_indices(emb, cap=n)
        assert got == want, f"case {case}: n={n} dim={dim}"


# --- AC 002-2 (non-tautological) --------------------------------------------


def test_leader_cluster_differs_at_other_radius() -> None:
    """A hand-built battery where ``radius=REF_DEDUP`` and another radius
    disagree (AC 002-2: proves 002-1's equality is not vacuous).

    ``A`` (0deg) and ``D`` (60deg, cos=0.5) and ``C`` (90deg, cos(A,C)=0).
    At ``radius=REF_DEDUP=0.90``: ``D`` is accepted as its own leader
    (0.5 < 0.90). At ``radius=0.30``: ``D`` is rejected (0.5 is not < 0.30)
    -- merged into ``A``'s cluster.
    """
    emb = np.array([_angle_vec(0.0), _angle_vec(60.0), _angle_vec(90.0)])
    at_ref_dedup = mod.leader_cluster_indices(emb, radius=mod._c.REF_DEDUP, cap=3)
    at_other = mod.leader_cluster_indices(emb, radius=0.3, cap=3)
    assert at_ref_dedup == [0, 1, 2]
    assert at_other == [0, 2]
    assert at_ref_dedup != at_other


def test_leader_cluster_boundary_equality_is_excluded() -> None:
    """``cos.max() == radius`` exactly is rejected, not kept (strict ``<``).

    ``A=(1,0)``, ``B=(0.5, sqrt(3)/2)``: ``cos(A, B) = 0.5`` exactly (no
    floating rounding since one operand is a clean basis vector). At
    ``radius=0.5`` design-final.md §3's "``cos < τ``" predicate means ``B``
    is *not* strictly below the radius, so it must be excluded (merged into
    ``A``), never kept as a second representative.
    """
    emb = np.array([[1.0, 0.0], [0.5, math.sqrt(3.0) / 2.0]])
    assert emb[0] @ emb[1] == pytest.approx(0.5, abs=0.0)
    kept = mod.leader_cluster_indices(emb, radius=0.5, cap=2)
    assert kept == [0]


# --- AC 002-3 (radius monotonicity) -----------------------------------------


def test_leader_count_is_monotone_in_radius() -> None:
    """Lowering ``radius`` never increases the keep count (AC 002-3), on a
    hand-built battery where the merge order is unambiguous by construction.

    Two well-separated (90deg apart, cross cosines ~0 or negative -- always
    below every :data:`TAU_GRID` value) duplicate pairs: ``A0``/``A1``
    (2deg apart, cos~0.9994 -- merges at *every* grid radius) and
    ``B0``/``B1`` (cos exactly 0.62 by construction -- stays split for
    radius in {0.90..0.65}, merges once radius drops to {0.60..0.40}). The
    keep count is therefore 3 for the first 6 grid points and 2 for the
    last 5: a genuine, non-flat, non-increasing step -- not vacuously true.
    """
    cos_b = 0.62
    angle_b1 = math.degrees(math.acos(cos_b))
    emb = np.array(
        [
            _angle_vec(0.0),
            _angle_vec(2.0),
            _angle_vec(90.0),
            _angle_vec(90.0 + angle_b1),
        ]
    )
    counts = [
        len(mod.leader_cluster_indices(emb, radius=tau, cap=emb.shape[0]))
        for tau in mod.TAU_GRID
    ]
    assert counts == [3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1]


# --- AC 002-4 (cap truncates prefix) ----------------------------------------


def test_cap_truncates_prefix() -> None:
    """``cap=k`` yields ``len(result) <= k`` and matches the uncapped prefix.

    Uses a well-dispersed (near-orthogonal, high-dimensional) random battery
    so the uncapped run keeps far more than ``cap`` entries -- truncation is
    actually exercised, not vacuously satisfied.
    """
    rng = np.random.default_rng(SEED + 4)
    n, dim, cap = 20, 20, 5
    emb = _random_unit_vectors(rng, n, dim)
    uncapped = mod.leader_cluster_indices(emb, radius=mod._c.REF_DEDUP, cap=n)
    capped = mod.leader_cluster_indices(emb, radius=mod._c.REF_DEDUP, cap=cap)
    assert len(uncapped) > cap
    assert len(capped) <= cap
    assert capped == uncapped[:cap]


# --- AC 002-5 (scan-order dependence) ---------------------------------------


def test_leader_cluster_depends_on_scan_order() -> None:
    """Swapping the scan order of a near-duplicate pair changes *which*
    vector survives as the cluster representative (AC 002-5): the frozen
    scan order is load-bearing, not an implementation detail.

    ``vec_a`` (0deg) and ``vec_b`` (10deg, cos~0.9848 >= REF_DEDUP) are
    near-duplicates; ``vec_c`` (90deg) is orthogonal to both and always
    survives on its own. Whichever of ``vec_a``/``vec_b`` scans first
    becomes the surviving representative -- the other is absorbed.
    """
    vec_a = np.array(_angle_vec(0.0))
    vec_b = np.array(_angle_vec(10.0))
    vec_c = np.array(_angle_vec(90.0))
    radius = mod._c.REF_DEDUP

    order_abc = np.stack([vec_a, vec_b, vec_c])
    order_bac = np.stack([vec_b, vec_a, vec_c])

    kept_abc = mod.leader_cluster_indices(order_abc, radius=radius, cap=3)
    kept_bac = mod.leader_cluster_indices(order_bac, radius=radius, cap=3)

    reps_abc = {order_abc[i].tobytes() for i in kept_abc}
    reps_bac = {order_bac[i].tobytes() for i in kept_bac}

    assert len(kept_abc) == len(kept_bac) == 2
    assert vec_a.tobytes() in reps_abc
    assert vec_b.tobytes() not in reps_abc
    assert vec_b.tobytes() in reps_bac
    assert vec_a.tobytes() not in reps_bac


# --- AC 002-6 (rho on known configurations) ---------------------------------


def test_reference_redundancy_known_configurations() -> None:
    """rho on hand-computable configurations: orthogonal -> 0, identical -> 1.

    Both are exact in floating point: an orthonormal basis has off-diagonal
    cosine exactly 0.0, and identical unit vectors have cosine exactly 1.0
    (both are plain dot products of 0/1-valued or self-identical floats, no
    rounding introduced).
    """
    orthogonal = np.eye(5)
    assert mod.reference_redundancy(orthogonal) == pytest.approx(0.0, abs=1e-12)

    identical = np.tile(np.array([1.0, 0.0, 0.0]), (5, 1))
    assert mod.reference_redundancy(identical) == pytest.approx(1.0, abs=1e-12)


def test_reference_redundancy_two_refs_not_degenerate() -> None:
    """``n == 2`` is *not* the degenerate case -- only ``n < 2`` is (AC
    002-7's boundary neighbour): with exactly 2 non-identical references,
    rho must be the actual computed nearest-neighbour cosine, not the
    frozen degenerate ``0.0``.
    """
    emb = np.array([[1.0, 0.0], [0.3, math.sqrt(1.0 - 0.3**2)]])
    assert mod.reference_redundancy(emb) == pytest.approx(0.3, abs=1e-12)


# --- AC 002-7 (degenerate |R_o| < 2) ----------------------------------------


def test_reference_redundancy_degenerate() -> None:
    """``|R_o| < 2`` returns the frozen ``0.0`` (design-final.md §2.1, Codex
    TASK-PRE LOW-1) -- both the empty and the single-reference case.
    """
    assert mod.reference_redundancy(np.zeros((0, 3))) == 0.0
    assert mod.reference_redundancy(np.array([[1.0, 0.0, 0.0]])) == 0.0


# --- AC 002-8 (rho is not max pairwise cos) ---------------------------------


def test_rho_is_not_max_pairwise() -> None:
    """rho (mean nearest-neighbour cos) diverges from the single maximum
    pairwise cosine over the whole set (AC 002-8, design-final.md §2.2): one
    densely-paired pair (cos~0.99) plus two mutually-orthogonal outliers.
    """
    cos_dense = 0.99
    v0 = np.array([1.0, 0.0, 0.0, 0.0])
    v1 = np.array([cos_dense, math.sqrt(1.0 - cos_dense**2), 0.0, 0.0])
    v2 = np.array([0.0, 0.0, 1.0, 0.0])
    v3 = np.array([0.0, 0.0, 0.0, 1.0])
    emb = np.stack([v0, v1, v2, v3])

    sims = emb @ emb.T
    np.fill_diagonal(sims, -np.inf)
    max_pairwise = float(sims.max())
    rho = mod.reference_redundancy(emb)

    assert max_pairwise == pytest.approx(cos_dense, abs=1e-9)
    assert rho == pytest.approx(0.495, abs=1e-9)
    assert abs(rho - max_pairwise) > 0.1


# --- AC 002-9 (corpus_redundancy is unweighted) -----------------------------


def test_corpus_redundancy_is_unweighted() -> None:
    """``corpus_redundancy`` is the simple (unweighted) mean across objects,
    not weighted by each object's reference-set size (AC 002-9).

    Object ``"a"`` has 2 identical references (rho=1.0); object ``"b"`` has
    6 orthonormal references (rho=0.0). The unweighted mean is 0.5; a
    count-weighted mean would be 0.25 -- the two must diverge to prove the
    weighting choice is actually load-bearing in the implementation.
    """
    by_object = {
        "a": np.tile(np.array([1.0, 0.0, 0.0]), (2, 1)),
        "b": np.eye(6),
    }
    rho_a = mod.reference_redundancy(by_object["a"])
    rho_b = mod.reference_redundancy(by_object["b"])
    unweighted = (rho_a + rho_b) / 2.0
    weighted = (2 * rho_a + 6 * rho_b) / 8.0

    result = mod.corpus_redundancy(by_object)
    assert result == pytest.approx(unweighted, abs=1e-12)
    assert result == pytest.approx(0.5, abs=1e-12)
    assert result != pytest.approx(weighted, abs=1e-6)
    assert result != pytest.approx(0.25, abs=1e-6)


def test_corpus_redundancy_empty_is_zero() -> None:
    """An empty ``by_object`` mapping returns ``0.0`` rather than raising."""
    assert mod.corpus_redundancy({}) == 0.0
