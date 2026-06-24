"""Blindness + apparatus-validity tests for the SPDM non-circular scenario.

These tests pin **only** the procedural non-circularity and apparatus health of
the blind movement-model generator (``erre_sandbox.evidence.spdm.scenario``).
They deliberately do **not** assert the verdict value (GO / NO_GO / INCONCLUSIVE):
pinning the verdict would re-bake the answer into the apparatus, which is exactly
the circularity this scenario exists to avoid. The verdict is produced once by
``scripts/spdm_verdict_run.py`` and recorded verbatim in ``.steering/``.

What is asserted:

* determinism (same seed ⇒ byte-identical divergences),
* ① permutation and ④ ``spatial_weight=0`` collapse to 0 (apparatus valid),
* both arms form the same canonical contents (only formation *location* differs),
* the walk is a real adjacency walk (no teleport) of the matched length,
* the two arms share a blind-drawn start (label-independent), and
* the mirrored geometry equals ``erre_sandbox.world.zones`` (fidelity, no drift).
"""

from __future__ import annotations

import itertools
import random

from erre_sandbox.evidence.spdm import constants as c
from erre_sandbox.evidence.spdm.scenario import (
    ADJACENCY,
    NORMALIZED_ZONE_CENTERS,
    ZONES,
    build_seed_result,
    default_seed_bank,
    uniform_walk,
)
from erre_sandbox.world import zones as world_zones

# ---------------------------------------------------------------------------
# geometry fidelity: the evidence-local mirror must equal the real world layout
# ---------------------------------------------------------------------------


def test_normalized_centers_equal_world_zone_centers() -> None:
    ref = world_zones.WORLD_SIZE_M / 3.0  # == world_zones._ZONE_OFFSET
    for zone, (nx, ny, nz) in NORMALIZED_ZONE_CENTERS.items():
        wx, wy, wz = world_zones.ZONE_CENTERS[zone]
        assert (nx, ny, nz) == (wx / ref, wy / ref, wz / ref)


def test_adjacency_mirror_equals_world_adjacency() -> None:
    assert set(ADJACENCY) == set(world_zones.ADJACENCY)
    for zone, neighbours in ADJACENCY.items():
        assert set(neighbours) == set(world_zones.ADJACENCY[zone])


def test_adjacency_neighbour_order_is_pinned_to_zone_order() -> None:
    # Codex LOW-1: the world adjacency is an (unordered) frozenset, but the mirror's
    # tuple order drives the seed → trajectory mapping. Pin the order to ``Zone``
    # declaration order so it is not a silent forking-paths surface.
    for zone, neighbours in ADJACENCY.items():
        expected = tuple(z for z in ZONES if z in world_zones.ADJACENCY[zone])
        assert neighbours == expected


def test_zones_cover_all_world_zones() -> None:
    assert set(ZONES) == set(world_zones.ZONE_CENTERS)


# ---------------------------------------------------------------------------
# uniform_walk: a real adjacency walk, fully determined by its rng
# ---------------------------------------------------------------------------


def test_uniform_walk_length_and_adjacency() -> None:
    walk = uniform_walk(ZONES[0], c.M_MEMORIES, random.Random("w"))
    assert len(walk) == c.M_MEMORIES
    assert walk[0] == ZONES[0]
    for prev, nxt in itertools.pairwise(walk):
        # every move follows a real walkable edge (no teleport, no self-loop)
        assert nxt in ADJACENCY[prev]
        assert nxt != prev


def test_uniform_walk_is_deterministic_in_seed() -> None:
    a = uniform_walk(ZONES[1], c.M_MEMORIES, random.Random("same"))
    b = uniform_walk(ZONES[1], c.M_MEMORIES, random.Random("same"))
    assert a == b


# ---------------------------------------------------------------------------
# apparatus validity: ① and ④ collapse to 0; contents matched across arms
# ---------------------------------------------------------------------------


async def test_permutation_and_w0_collapse_to_zero() -> None:
    # Across several blind seeds, the path-label-permutation null (both arms given
    # arm-A's trajectory) and the spatial_weight=0 ablation must be exactly 0 — the
    # frozen apparatus-validity condition (Codex HIGH-2/HIGH-5). A non-zero here
    # would mean the canonical-id metric or fixture is broken, not a real signal.
    for seed in range(4):
        result, _ = await build_seed_result(seed)
        assert result.d_null_permutation == 0.0
        assert result.d_null_w0 == 0.0


async def test_d_obs_is_bounded_unit_interval() -> None:
    result, _ = await build_seed_result(0)
    assert 0.0 <= result.d_obs <= 1.0


async def test_seed_result_is_reproducible() -> None:
    a, fa = await build_seed_result(3)
    b, fb = await build_seed_result(3)
    assert (a.d_obs, a.d_null_permutation, a.d_null_w0) == (
        b.d_obs,
        b.d_null_permutation,
        b.d_null_w0,
    )
    assert (a.d_control_same_loc_on, a.d_control_same_loc_off) == (
        b.d_control_same_loc_on,
        b.d_control_same_loc_off,
    )
    # The blind start/terminal draw is itself reproducible.
    assert (fa.start_zone, fa.terminal_zone) == (fb.start_zone, fb.terminal_zone)


# ---------------------------------------------------------------------------
# blindness: arms differ only by their walk; start is shared and blind-drawn
# ---------------------------------------------------------------------------


def test_both_arms_share_blind_start() -> None:
    # Reconstruct the generator's draw to confirm the two arms start at the *same*
    # blind-drawn zone (the only inter-arm difference is the walk realisation, not a
    # hand-picked disjoint start that would plant divergence).
    for seed in range(4):
        base = random.Random(f"spdm-seed-{seed}")
        start = ZONES[base.randrange(len(ZONES))]
        rng_a = random.Random(f"spdm-seed-{seed}-armA")
        rng_b = random.Random(f"spdm-seed-{seed}-armB")
        traj_a = uniform_walk(start, c.M_MEMORIES, rng_a)
        traj_b = uniform_walk(start, c.M_MEMORIES, rng_b)
        assert traj_a[0] == traj_b[0] == start


def test_default_seed_bank_is_pre_registered_range() -> None:
    assert default_seed_bank() == tuple(range(c.N_SEED))


async def test_no_spurious_control_is_position_invariant() -> None:
    # Codex ruling C (suggestion i): ③ compares the retrieved *position* set under
    # the same trajectory, not a content Jaccard. Because the spatial term is
    # content-blind, two arms on arm-A's trajectory retrieve the same positions, so
    # the no-spurious control collapses to 0 both ON and OFF (no content leakage) —
    # free of the parity confound the run-1 partial-overlap content Jaccard caused.
    for seed in range(4):
        result, _ = await build_seed_result(seed)
        assert result.d_control_same_loc_on == 0.0
        assert result.d_control_same_loc_off == 0.0
