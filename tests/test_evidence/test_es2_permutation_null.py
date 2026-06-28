"""① null fidelity for the ES-2 apparatus (Codex H4 + jaccard reuse pin).

Pins: the fast integer :func:`jaccard_distance_int` equals the frozen
:func:`erre_sandbox.evidence.spdm.probe.jaccard_distance` (so the hot permutation
loop cannot drift from the headline ``D_obs``); and the N-a content-stratified
paired permutation preserves each arm's **full content multiset** (Codex H4:
location binding swaps, composition is never nulled).
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es2_replay.permutation_null import (
    jaccard_distance_int,
    stratified_swap,
)
from erre_sandbox.evidence.spdm.probe import jaccard_distance


def test_jaccard_int_matches_frozen_string_jaccard() -> None:
    rng = np.random.default_rng(0)
    for _ in range(50):
        a = rng.integers(0, 30, size=rng.integers(0, 20)).astype(np.int64)
        b = rng.integers(0, 30, size=rng.integers(0, 20)).astype(np.int64)
        fast = jaccard_distance_int(a, b)
        ref = jaccard_distance(
            frozenset(str(x) for x in a.tolist()),
            frozenset(str(x) for x in b.tolist()),
        )
        assert abs(fast - ref) < 1e-12


def test_jaccard_int_empty_sets_are_identical() -> None:
    empty = np.array([], dtype=np.int64)
    assert jaccard_distance_int(empty, empty) == 0.0


def test_stratified_swap_preserves_content_multiset() -> None:
    # Codex H4: each permuted arm keeps every content exactly once; the swap only
    # moves a content's location between the A-path and B-path binding.
    m = 12
    coords_a = np.arange(m * 3, dtype=np.float64).reshape(m, 3)
    coords_b = coords_a + 1000.0  # disjoint locations so binding is identifiable
    rng = np.random.default_rng(1)
    for _ in range(20):
        coin = rng.integers(0, 2, size=m).astype(bool)
        arm_a, arm_b = stratified_swap(coords_a, coords_b, coin)
        assert arm_a.shape == coords_a.shape  # every content present once
        for i in range(m):
            # content i's two locations are split one-per-arm (no dup, no drop).
            pair_in = {tuple(coords_a[i]), tuple(coords_b[i])}
            pair_out = {tuple(arm_a[i]), tuple(arm_b[i])}
            assert pair_out == pair_in
        # the union of both arms equals the union of both original arms (composition
        # preserved: no content location invented or lost).
        union_in = {tuple(r) for r in np.vstack([coords_a, coords_b])}
        union_out = {tuple(r) for r in np.vstack([arm_a, arm_b])}
        assert union_out == union_in


def test_stratified_swap_unset_coin_is_identity() -> None:
    coords_a = np.arange(9, dtype=np.float64).reshape(3, 3)
    coords_b = coords_a + 100.0
    arm_a, arm_b = stratified_swap(coords_a, coords_b, np.zeros(3, dtype=bool))
    assert np.array_equal(arm_a, coords_a)
    assert np.array_equal(arm_b, coords_b)
