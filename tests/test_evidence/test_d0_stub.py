"""D0a generator: geometry byte-pin, replay checksum, invariants (§3)."""

from __future__ import annotations

import math

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.stub import (
    build_seed_pair,
    build_trace,
    default_seed_bank,
    quantize_trace,
    trace_checksum,
    zone_default_heading,
)
from erre_sandbox.schemas import Zone
from erre_sandbox.world import zones as world_zones


def test_zones_cover_all_world_zones() -> None:
    assert set(_c.ZONES) == set(world_zones.ZONE_CENTERS)


def test_zone_centers_byte_pin() -> None:
    for zone in _c.ZONES:
        assert _c.ZONE_CENTERS[zone] == world_zones.ZONE_CENTERS[zone]


def test_world_size_byte_pin() -> None:
    assert _c.WORLD_SIZE_M == world_zones.WORLD_SIZE_M


def test_adjacency_byte_pin() -> None:
    assert set(_c.ADJACENCY) == set(world_zones.ADJACENCY)
    for zone, neighbours in _c.ADJACENCY.items():
        assert set(neighbours) == set(world_zones.ADJACENCY[zone])


def test_zone_props_byte_pin() -> None:
    assert set(_c.ZONE_PROPS) == set(world_zones.ZONE_PROPS)
    for zone, props in _c.ZONE_PROPS.items():
        real_props = world_zones.ZONE_PROPS[zone]
        assert len(props) == len(real_props)
        for mirrored, real in zip(props, real_props, strict=True):
            assert mirrored.prop_id == real.prop_id
            assert mirrored.prop_kind == real.prop_kind
            assert mirrored.x == real.x
            assert mirrored.y == real.y
            assert mirrored.z == real.z
            assert mirrored.salience == real.salience


def test_affordance_radius_byte_pin() -> None:
    # world.tick._AFFORDANCE_RADIUS_M is private; mirrored by literal value.
    assert _c.AFFORDANCE_RADIUS_M == 2.0


def test_default_seed_bank_is_range_b() -> None:
    assert default_seed_bank() == tuple(range(_c.B))
    assert len(default_seed_bank()) == 64


def test_seed_as_only_freedom_same_seed_reproducible() -> None:
    a1, b1, start1, term1 = build_seed_pair(5)
    a2, b2, start2, term2 = build_seed_pair(5)
    assert start1 == start2
    assert term1 == term2
    assert a1.rows == a2.rows
    assert b1.rows == b2.rows


def test_two_arms_diverge_from_shared_start() -> None:
    trace_a, trace_b, start, _terminal = build_seed_pair(1)
    assert trace_a.rows[0].zone == start
    assert trace_b.rows[0].zone == start
    zones_a = [r.zone for r in trace_a.rows]
    zones_b = [r.zone for r in trace_b.rows]
    assert zones_a != zones_b  # blind walk RNG substreams are independent


def test_trace_row_schema_fields() -> None:
    trace_a, _b, start, _terminal = build_seed_pair(2)
    row = trace_a.rows[0]
    assert row.tick_index == 0
    assert row.seed == 2
    assert row.zone == start
    assert isinstance(row.action_id, int)
    assert isinstance(row.affordance_ids, tuple)


def test_monotone_tick_index() -> None:
    trace_a, _b, _start, _terminal = build_seed_pair(3)
    indices = [r.tick_index for r in trace_a.rows]
    assert indices == list(range(len(indices)))


def test_positions_in_bounds_and_zone_consistent_within_micro_radius() -> None:
    trace_a, _b, _start, _terminal = build_seed_pair(4)
    for row in trace_a.rows:
        cx, _cy, cz = _c.ZONE_CENTERS[row.zone]
        assert math.hypot(row.x - cx, row.z - cz) <= _c.CELL_MICRO_RADIUS_M + 1e-9
        assert abs(row.x) <= _c.WORLD_SIZE_M
        assert abs(row.z) <= _c.WORLD_SIZE_M


def test_replay_checksum_reproducible() -> None:
    trace1 = build_trace(7, "A", Zone.PERIPATOS)
    trace2 = build_trace(7, "A", Zone.PERIPATOS)
    assert trace_checksum(trace1.rows) == trace_checksum(trace2.rows)
    assert trace1.replay_checksum == trace2.replay_checksum


def test_replay_checksum_differs_across_arms() -> None:
    trace_a = build_trace(7, "A", Zone.PERIPATOS)
    trace_b = build_trace(7, "B", Zone.PERIPATOS)
    assert trace_a.replay_checksum != trace_b.replay_checksum


def test_quantize_r1_collapses_position_to_centroid() -> None:
    trace = build_trace(9, "A", Zone.STUDY)
    quant = quantize_trace(trace, "R1")
    for row, qrow in zip(trace.rows, quant.rows, strict=True):
        cx, cy, cz = _c.ZONE_CENTERS[row.zone]
        assert qrow.x == cx
        assert qrow.y == cy
        assert qrow.z == cz
        assert qrow.zone == row.zone  # backbone (zone/tick) untouched
        assert qrow.action_id == row.action_id
        assert qrow.yaw == row.yaw  # only position collapsed, not yaw


def test_quantize_r1_seed_paired_same_backbone() -> None:
    trace = build_trace(9, "A", Zone.STUDY)
    quant = quantize_trace(trace, "R1")
    assert [r.zone for r in trace.rows] == [r.zone for r in quant.rows]
    assert [r.tick_index for r in trace.rows] == [r.tick_index for r in quant.rows]
    assert [r.action_id for r in trace.rows] == [r.action_id for r in quant.rows]


def test_quantize_r2_collapses_yaw_to_zone_default_heading() -> None:
    trace = build_trace(10, "A", Zone.CHASHITSU)
    quant = quantize_trace(trace, "R2")
    for row, qrow in zip(trace.rows, quant.rows, strict=True):
        assert qrow.yaw == zone_default_heading(row.zone)
        assert qrow.x == row.x  # only yaw collapsed, not position
        assert qrow.z == row.z


def test_quantize_r3_collapses_action_to_null_action() -> None:
    trace = build_trace(11, "A", Zone.GARDEN)
    quant = quantize_trace(trace, "R3")
    for qrow in quant.rows:
        assert qrow.action_id == 0


def test_zone_default_heading_deterministic_pure_function() -> None:
    for zone in _c.ZONES:
        h1 = zone_default_heading(zone)
        h2 = zone_default_heading(zone)
        assert h1 == h2


def test_zone_default_heading_peripatos_is_zero() -> None:
    assert zone_default_heading(Zone.PERIPATOS) == 0.0


def test_affordance_ids_populated_near_chashitsu_props() -> None:
    prop = _c.ZONE_PROPS[Zone.CHASHITSU][0]
    trace = build_trace(0, "probe", Zone.CHASHITSU, steps=1)
    row = trace.rows[0]
    # Not asserting non-empty (depends on jitter draw); assert the detection
    # logic itself matches distance <= AFFORDANCE_RADIUS_M.
    distance = math.hypot(row.x - prop.x, row.z - prop.z)
    expected = distance <= _c.AFFORDANCE_RADIUS_M
    assert (prop.prop_id in row.affordance_ids) == expected
