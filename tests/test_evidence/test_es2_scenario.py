"""World-geometry mirror + blindness pins for the ES-2 scenario generator.

These tests pin **only** the procedural non-circularity and geometric fidelity of
the blind generator (``erre_sandbox.evidence.es2_replay.scenario``). They
deliberately do **not** assert the verdict value (GO / NO_GO / INCONCLUSIVE):
pinning the verdict would re-bake the answer into the apparatus. The verdict is
produced once by ``scripts/es2_verdict_run.py`` and recorded verbatim in
``.steering/``.
"""

from __future__ import annotations

import itertools

from erre_sandbox.evidence.es2_replay.scenario import (
    ADJACENCY,
    NORMALIZED_ZONE_CENTERS,
    ZONES,
    build_seed_result,
    default_seed_bank,
)
from erre_sandbox.world import zones as world_zones

# --- geometry fidelity: the evidence-local mirror must equal the world layout ---


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
    # The world adjacency is an (unordered) frozenset, but the mirror's tuple order
    # drives the walk's neighbour sampling. Pin the order to ``Zone`` declaration
    # order so it is not a silent forking-paths surface.
    for zone, neighbours in ADJACENCY.items():
        expected = tuple(z for z in ZONES if z in world_zones.ADJACENCY[zone])
        assert neighbours == expected


# --- blindness / non-circularity of the generator -----------------------------


def test_default_seed_bank_is_range_n_seed() -> None:
    from erre_sandbox.evidence.es2_replay import constants as c

    assert default_seed_bank() == tuple(range(c.N_SEED))


def test_arms_share_blind_start_zone() -> None:
    # Both arms are drawn from one blind start (label-independent matched nuisance);
    # trajectory[0] is therefore identical across arms.
    _, forensic = build_seed_result(0, m=12, n_replay=64, n_perm=4, l_seed=4)
    assert forensic.trajectory_a[0] == forensic.start_zone
    assert forensic.trajectory_b[0] == forensic.start_zone


def test_trajectories_are_real_adjacency_walks() -> None:
    # No teleport: every consecutive zone pair in a trajectory is a real edge.
    _, forensic = build_seed_result(1, m=16, n_replay=64, n_perm=4, l_seed=4)
    for traj in (forensic.trajectory_a, forensic.trajectory_b):
        assert len(traj) == 16
        for here, nxt in itertools.pairwise(traj):
            assert nxt in world_zones.ADJACENCY[here]


def test_arms_diverge_under_preferential_return() -> None:
    # Same base, same blind start, different RNG sub-stream ⇒ the two arms generally
    # form distinct trajectories (the divergence the apparatus measures must be able
    # to arise from the walk alone).
    _, forensic = build_seed_result(2, m=24, n_replay=64, n_perm=4, l_seed=4)
    assert forensic.trajectory_a != forensic.trajectory_b


def test_determinism_same_seed_byte_identical() -> None:
    r1, _ = build_seed_result(3, m=16, n_replay=128, n_perm=8, l_seed=4)
    r2, _ = build_seed_result(3, m=16, n_replay=128, n_perm=8, l_seed=4)
    assert r1 == r2
