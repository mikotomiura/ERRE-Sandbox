"""Pin the M13-ES3 scenario non-circularity, determinism, and geometry fidelity.

These tests pin **only** the apparatus mechanics — the mirrored world geometry,
the blind-walk generator's determinism and graph-faithfulness, the λ EMA, and the
ablation (no-locomotion) composition. The verdict value is deliberately **not**
pinned (that would re-bake the answer into the apparatus, the discipline ES-1/ES-2
established).
"""

from __future__ import annotations

from erre_sandbox.erre import SAMPLING_DELTA_BY_MODE, ZONE_TO_DEFAULT_ERRE_MODE
from erre_sandbox.evidence.es3_locomotion import constants as _c
from erre_sandbox.evidence.es3_locomotion.scenario import (
    ADJACENCY,
    MODE_DELTA_BY_ZONE,
    ZONES,
    build_observations,
    default_seed_bank,
    ema_lambda,
    trajectory,
    walk_options,
)
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.world import zones as world_zones


def test_zones_cover_all_world_zones() -> None:
    assert set(ZONES) == set(world_zones.ZONE_CENTERS)


def test_adjacency_mirror_matches_world() -> None:
    assert set(ADJACENCY) == set(world_zones.ADJACENCY)
    for zone, neighbours in ADJACENCY.items():
        assert set(neighbours) == set(world_zones.ADJACENCY[zone])


def test_adjacency_neighbour_order_is_pinned_to_zone_order() -> None:
    # Tuple order drives the seed → trajectory mapping; pin it to ``Zone`` order
    # so the mirror cannot silently drift while staying set-equal.
    for zone, neighbours in ADJACENCY.items():
        expected = tuple(z for z in ZONES if z in world_zones.ADJACENCY[zone])
        assert neighbours == expected


def test_walk_options_include_self_for_stay() -> None:
    for zone in ZONES:
        opts = walk_options(zone)
        assert zone in opts  # self = stay
        assert set(opts) == set(world_zones.ADJACENCY[zone]) | {zone}
        # stay probability = 1/(deg+1), graph-determined (not a knob).
        assert len(opts) == len(world_zones.ADJACENCY[zone]) + 1


def test_mode_delta_by_zone_matches_canonical_mapping() -> None:
    for zone in ZONES:
        expected = SAMPLING_DELTA_BY_MODE[ZONE_TO_DEFAULT_ERRE_MODE[zone]]
        assert MODE_DELTA_BY_ZONE[zone] == expected


def test_trajectory_is_deterministic() -> None:
    a = trajectory(7)
    b = trajectory(7)
    assert a == b
    assert len(a.zones) == _c.T
    assert len(a.moves) == _c.T


def test_trajectory_respects_adjacency_and_stay() -> None:
    walk = trajectory(3)
    for prev, nxt in zip(walk.zones, walk.zones[1:], strict=False):
        assert nxt in walk_options(prev)  # adjacency ∪ self


def test_moves_first_is_zero_and_indicator_matches_zone_change() -> None:
    walk = trajectory(11)
    assert walk.moves[0] == 0
    for t in range(1, len(walk.zones)):
        assert walk.moves[t] == int(walk.zones[t] != walk.zones[t - 1])


def test_ema_lambda_matches_recurrence() -> None:
    moves = [0, 1, 1, 0, 0, 1]
    lams = ema_lambda(moves, 0.3)
    expected = 0.0
    for m, got in zip(moves, lams, strict=True):
        expected = 0.7 * expected + 0.3 * m
        assert got == expected
    assert lams[0] == 0.0  # move_0 = 0 ⇒ λ_0 = 0


def test_blind_walk_produces_within_zone_lambda_variation() -> None:
    """Sanity: the self-loop walk yields non-trivial λ variation (not degenerate)."""
    walk = trajectory(0)
    lams = ema_lambda(walk.moves, _c.ALPHA)
    assert max(lams) - min(lams) > 0.1


def test_observation_ablation_is_bit_identical_none_path() -> None:
    """``e_abl`` equals the explicit two-arg composition for every observation."""
    obs = build_observations((0, 1))
    base_by_id = dict(_c.PERSONA_ROSTER)
    for o in obs:
        expected = compose_sampling(
            base_by_id[o.persona_id], MODE_DELTA_BY_ZONE[o.zone]
        )
        assert o.e_abl == expected.temperature
        assert o.top_p_abl == expected.top_p


def test_default_seed_bank_is_range_b() -> None:
    assert default_seed_bank() == tuple(range(_c.B))


def test_build_observations_count() -> None:
    obs = build_observations((0,))
    # one walk × 3 personas × T steps
    assert len(obs) == 3 * _c.T


def test_observations_are_deterministic() -> None:
    assert build_observations((5,)) == build_observations((5,))
