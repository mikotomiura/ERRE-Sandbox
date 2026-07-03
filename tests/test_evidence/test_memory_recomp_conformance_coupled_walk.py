"""Post-idle walk ``D``: determinism, pooling, and the §5 independence pin.

The independence pin is the design's central non-circularity guarantee
(design-final.md §5): ``D`` is a pure function of ``(start, uniforms, target_zone,
alpha, bonus)`` — it reads **no** ``C`` / replay state — so feeding the same
``target_zone`` from a *different* ``C`` trace leaves the weights byte-identical.
"""

from __future__ import annotations

import inspect

import numpy as np

from erre_sandbox.evidence.memory_recomp_conformance.coupled_walk import (
    neighbor_weights,
    post_idle_walk_occupancies,
)

# 5-zone hub-and-spokes adjacency (STUDY-PERIPATOS-... shape, self-contained).
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
_CONFIGS = np.array([-1, 0, 1, 2, 3, 4], dtype=np.int64)


def _uniforms(seed: int, r: int, steps: int) -> np.ndarray:
    return np.random.default_rng(seed).random((r, steps))


def test_pooled_shape_and_row_sums() -> None:
    r, steps = 32, 20
    occ = post_idle_walk_occupancies(
        1, steps, _ADJ, _uniforms(0, r, steps), _CONFIGS, alpha=1.0, bonus=1.0
    )
    assert occ.shape == (_CONFIGS.size, _ADJ.shape[0])
    # each config pools R realizations of `steps` occupied positions.
    assert np.allclose(occ.sum(axis=1), r * steps)


def test_deterministic_under_identical_inputs() -> None:
    r, steps = 16, 24
    u = _uniforms(7, r, steps)
    a = post_idle_walk_occupancies(2, steps, _ADJ, u, _CONFIGS, alpha=1.0, bonus=1.0)
    b = post_idle_walk_occupancies(2, steps, _ADJ, u, _CONFIGS, alpha=1.0, bonus=1.0)
    assert np.array_equal(a, b)


def test_independence_pin_same_target_zone_byte_identical_regardless_of_channel() -> (
    None
):
    # §5: two DIFFERENT "C traces" that happen to select the SAME target_zone must
    # give byte-identical D. D takes no C, so it is a pure function of its inputs;
    # this pin guards against a future regression wiring C state into D.
    r, steps = 40, 30
    u = _uniforms(11, r, steps)
    target_zone = 3
    # "channel A" and "channel B" are irrelevant to the call — only target_zone is.
    d_from_channel_a = post_idle_walk_occupancies(
        0, steps, _ADJ, u, np.array([-1, target_zone]), alpha=1.0, bonus=1.0
    )
    d_from_channel_b = post_idle_walk_occupancies(
        0, steps, _ADJ, u, np.array([-1, target_zone]), alpha=1.0, bonus=1.0
    )
    assert np.array_equal(d_from_channel_a, d_from_channel_b)

    # And the walk signature exposes no channel / replay-state parameter.
    params = set(inspect.signature(post_idle_walk_occupancies).parameters)
    assert not (params & {"seeds", "channel", "c", "replay", "dist_c", "valid_c"})


def test_bonus_shifts_occupancy_toward_target_zone() -> None:
    # The bonus is the ONLY coupling; it must measurably concentrate D on the leaf
    # target zone relative to the marginal (else conform would be structurally 0).
    r, steps = 256, 48
    u = _uniforms(3, r, steps)
    occ = post_idle_walk_occupancies(
        1, steps, _ADJ, u, np.array([-1, 0]), alpha=1.0, bonus=1.0
    )
    marginal, coupled_z0 = occ[0], occ[1]
    # zone 0 is a leaf reachable only from the hub; a bonus there raises its share.
    assert coupled_z0[0] / coupled_z0.sum() > marginal[0] / marginal.sum()


def test_marginal_config_ignores_bonus() -> None:
    # target_zone = -1 (marginal) must equal a run with bonus = 0.
    r, steps = 16, 20
    u = _uniforms(5, r, steps)
    occ_marg = post_idle_walk_occupancies(
        2, steps, _ADJ, u, np.array([-1]), alpha=1.0, bonus=1.0
    )
    occ_zero = post_idle_walk_occupancies(
        2, steps, _ADJ, u, np.array([-1]), alpha=1.0, bonus=0.0
    )
    assert np.array_equal(occ_marg, occ_zero)


def test_neighbor_weights_formula() -> None:
    visit = np.array([0.0, 2.0, 1.0, 0.0, 3.0])
    w = neighbor_weights(1, visit, _ADJ, target_zone=4, alpha=1.0, bonus=1.0)
    # from hub (zone 1): neighbors 0,2,3,4; zone 4 gets the +1 bonus.
    assert w[0] == 1.0 + 0.0  # alpha + visit
    assert w[2] == 1.0 + 1.0
    assert w[4] == 1.0 + 3.0 + 1.0  # + bonus
    assert w[1] == 0.0  # non-neighbor (self) masked
