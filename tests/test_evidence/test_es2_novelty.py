"""De-novo novelty + temporal-replay apparatus-validity floor (Codex H3).

Pins: the temporal-replay negative control scores **below** the novelty floor
(the apparatus-validity floor — the novelty test can fail); and the boundary
between a recorded consecutive run and a recombined seed with a novel directed
transition.
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es2_replay import constants as _c
from erre_sandbox.evidence.es2_replay.novelty import (
    de_novo_eligible,
    de_novo_structure_ids,
    novel_transition_rate,
    temporal_replay_seeds,
)
from erre_sandbox.evidence.es2_replay.recombination import structure_ids


def test_consecutive_run_is_not_de_novo() -> None:
    # A contiguous formation-order run [k, k+1, …] has only recorded (i, i+1)
    # transitions ⇒ not de-novo-eligible.
    seeds = np.array([[0, 1, 2, 3], [10, 11, 12, 13]], dtype=np.int64)
    assert not de_novo_eligible(seeds).any()


def test_seed_with_novel_transition_is_de_novo() -> None:
    # A single non-(i, i+1) jump makes the seed de-novo-eligible.
    seeds = np.array(
        [[0, 1, 2, 5], [5, 3, 1, 0], [7, 8, 20, 21]],
        dtype=np.int64,
    )
    assert de_novo_eligible(seeds).all()


def test_temporal_replay_control_fails_novelty() -> None:
    # Codex H3 apparatus-validity floor: a stream replay that follows formation
    # order scores 0 novel-transition rate, i.e. strictly below NOVELTY_FLOOR, so
    # the novelty test is demonstrably able to fail.
    seeds = temporal_replay_seeds(
        _c.M_FRAGMENTS, _c.L_SEED, 2000, np.random.default_rng(0)
    )
    valid = np.ones(seeds.shape[0], dtype=bool)
    rate = novel_transition_rate(seeds, valid)
    assert rate == 0.0
    assert rate < _c.NOVELTY_FLOOR


def test_temporal_replay_seeds_are_contiguous_and_in_range() -> None:
    seeds = temporal_replay_seeds(48, 4, 500, np.random.default_rng(1))
    assert seeds.min() >= 0
    assert seeds.max() <= 47
    diffs = seeds[:, 1:] - seeds[:, :-1]
    assert np.all(diffs == 1)  # every step is the recorded next fragment


def test_novel_transition_rate_only_counts_valid_seeds() -> None:
    seeds = np.array([[0, 1, 2, 3], [0, 5, 9, 2]], dtype=np.int64)
    valid = np.array([False, True])
    # Only the 2nd (de-novo) seed is valid ⇒ rate 1.0.
    assert novel_transition_rate(seeds, valid) == 1.0


def test_de_novo_structure_ids_filters_to_valid_and_eligible() -> None:
    seeds = np.array(
        [[0, 1, 2, 3], [0, 5, 9, 2], [4, 9, 1, 7]],
        dtype=np.int64,
    )
    valid = np.array([True, True, False])
    struct = structure_ids(seeds, m=48)
    kept = de_novo_structure_ids(struct, seeds, valid)
    # seed 0 dropped (not de-novo), seed 2 dropped (invalid) ⇒ only seed 1 remains.
    assert kept.tolist() == [struct[1]]
