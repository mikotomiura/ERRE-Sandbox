"""Kernel invariants for the ES-2 recombination layer (Codex H2 + proximity pin).

Pins: ``w_{i→i}=0`` and self-avoidance (``unique_fragment_count == L_SEED``, no
adjacent duplicate); the vectorised :func:`proximity_matrix` equals the frozen
:func:`erre_sandbox.memory.retrieval.spatial_proximity` element-wise (read-only
reuse, no drift); preferential-return α=1 reinforcement; and deterministic unit
embeddings.
"""

from __future__ import annotations

import itertools
import math

import numpy as np

from erre_sandbox.evidence.es2_replay import constants as _c
from erre_sandbox.evidence.es2_replay.recombination import (
    kernel_weights,
    pairwise_cosine,
    preferential_return_walk,
    proximity_matrix,
    replay_walks,
    semantic_matrix,
    structure_ids,
    synthetic_embeddings,
)
from erre_sandbox.memory.retrieval import spatial_proximity
from erre_sandbox.schemas import SpatialContext, Zone


def _coords() -> np.ndarray:
    return np.array(
        [
            [-1.0, 0.0, -1.0],
            [0.0, 0.0, 0.0],
            [1.0, 0.0, -1.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def test_proximity_matrix_equals_frozen_spatial_proximity() -> None:
    coords = _coords()
    mat = proximity_matrix(coords)
    for i, (xi, yi, zi) in enumerate(coords):
        for j, (xj, yj, zj) in enumerate(coords):
            now = SpatialContext(zone=Zone.PERIPATOS, x=xi, y=yi, z=zi)
            formed = SpatialContext(zone=Zone.PERIPATOS, x=xj, y=yj, z=zj)
            assert math.isclose(
                mat[i, j], spatial_proximity(now, formed), rel_tol=1e-12
            )


def test_kernel_weights_zero_diagonal_and_product_offdiagonal() -> None:
    coords = _coords()
    emb = synthetic_embeddings(5)
    prox = proximity_matrix(coords)
    sem = semantic_matrix(emb)
    w = kernel_weights(prox, sem)
    assert np.all(np.diag(w) == 0.0)  # Codex H2: no self-loop
    for i in range(5):
        for j in range(5):
            if i != j:
                assert math.isclose(w[i, j], prox[i, j] * sem[i, j], rel_tol=1e-12)


def test_replay_walks_are_self_avoiding_and_unique() -> None:
    coords = _coords()
    emb = synthetic_embeddings(5)
    w = kernel_weights(proximity_matrix(coords), semantic_matrix(emb))
    seeds, valid = replay_walks(w, n_replay=500, l_seed=4, rng=np.random.default_rng(0))
    assert valid.all()  # full positive graph ⇒ never a dead end
    for seq in seeds:
        assert len(set(seq.tolist())) == 4  # unique_fragment_count == L_SEED
        for a, b in itertools.pairwise(seq.tolist()):
            assert a != b  # adjacent duplicate forbidden (subset of self-avoidance)


def test_semantic_matrix_in_unit_interval_and_diagonal_one() -> None:
    emb = synthetic_embeddings(8)
    sem = semantic_matrix(emb)
    assert np.all(sem > 0.0)
    assert np.all(sem <= 1.0 + 1e-12)
    assert np.allclose(np.diag(sem), 1.0)


def test_synthetic_embeddings_unit_norm_and_deterministic() -> None:
    a = synthetic_embeddings(_c.M_FRAGMENTS)
    b = synthetic_embeddings(_c.M_FRAGMENTS)
    assert a.shape == (_c.M_FRAGMENTS, _c.EMBED_DIM)
    assert np.array_equal(a, b)  # deterministic (hashlib, no hash() salting)
    norms = np.sqrt((a * a).sum(axis=1))
    assert np.allclose(norms, 1.0)


def test_synthetic_embeddings_have_cosine_competition() -> None:
    # ② validity precondition: the synthetic embeddings must actually compete
    # (non-degenerate pairwise cosine variance), not collapse to ties.
    cos = pairwise_cosine(synthetic_embeddings(_c.M_FRAGMENTS))
    iu = np.triu_indices(_c.M_FRAGMENTS, k=1)
    assert float(np.var(cos[iu])) >= _c.COMPETITION_MIN_VAR


def test_structure_ids_are_order_sensitive_and_collision_free() -> None:
    seeds = np.array([[0, 1, 2, 3], [3, 2, 1, 0], [0, 1, 2, 4]], dtype=np.int64)
    ids = structure_ids(seeds, m=48)
    assert ids[0] != ids[1]  # order-sensitive
    assert len(set(ids.tolist())) == 3  # distinct sequences ⇒ distinct ids


def test_preferential_return_reinforces_revisited_neighbour() -> None:
    # Graph: 0 ↔ {1, 2}, 1 ↔ {0}, 2 ↔ {0}. A walk 0→1→0 raises node 1's visit
    # count, so on return to 0 node 1 is favoured 2:1 (weights α+1 : α+0 = 2 : 1).
    neighbors = [(1, 2), (0,), (0,)]
    import random

    favored = 0
    conditioned = 0
    for s in range(4000):
        traj = preferential_return_walk(
            0, 4, neighbors, random.Random(s), alpha=_c.POLYA_ALPHA
        )
        if traj[1] == 1:  # went to node 1 first (so it is the reinforced neighbour)
            conditioned += 1
            if traj[3] == 1:
                favored += 1
    # Expected P(return to reinforced node) = 2/3; allow sampling slack.
    assert 0.60 <= favored / conditioned <= 0.73
