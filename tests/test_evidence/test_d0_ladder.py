"""R0->R3 ladder: null/control collapse + anti-collapse gate falsifiability."""

from __future__ import annotations

import math
import random

import pytest

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import (
    _closure_c_ao,
    _cone_affordance_set,
    evaluate_r0,
    evaluate_r1,
    evaluate_r2,
    evaluate_r3,
    r0_r1_seed_point,
)
from erre_sandbox.schemas import Zone

_SMALL_SEED_BANK = list(range(16))

# --- R0 / R1: retrieval-landscape rungs -------------------------------------


@pytest.mark.asyncio
async def test_r0_r1_ablation_null_collapses_exactly() -> None:
    """spatial_weight=0 makes both arms retrieve the same top-k deterministically."""
    for seed in range(8):
        point = await r0_r1_seed_point(seed)
        assert point.d0_null == 0.0
        assert point.d1_null == 0.0


@pytest.mark.asyncio
async def test_anti_collapse_delta_can_be_nonzero() -> None:
    """Falsifiability: Delta_1 is not a metric artefact that is always 0.

    Seed 30 is a deterministic existence proof (found by exhaustive scan over
    the default seed bank) that continuous position can register beyond the
    zone-quantized baseline.
    """
    point = await r0_r1_seed_point(30)
    assert abs(point.delta) > 1e-9


@pytest.mark.asyncio
async def test_r0_control_degenerates_to_null_ablation() -> None:
    r0 = await evaluate_r0(_SMALL_SEED_BANK)
    assert r0.control_value == r0.max_null
    assert r0.control_ok == r0.null_ok


@pytest.mark.asyncio
async def test_r1_situated_function_control_is_bit_identical_zero() -> None:
    """Delta on a doubly-quantized pair reads exactly 0 (ES-3 control iii style)."""
    r1 = await evaluate_r1(_SMALL_SEED_BANK)
    assert r1.control_value == 0.0
    assert r1.control_ok is True


@pytest.mark.asyncio
async def test_r0_r1_null_ok_when_ablation_collapses() -> None:
    r0 = await evaluate_r0(_SMALL_SEED_BANK)
    r1 = await evaluate_r1(_SMALL_SEED_BANK)
    assert r0.null_ok is True
    assert r1.null_ok is True
    assert r0.max_null == 0.0
    assert r1.max_null == 0.0


@pytest.mark.asyncio
async def test_r1_delta_median_and_ci_present() -> None:
    r1 = await evaluate_r1(_SMALL_SEED_BANK)
    assert r1.delta_median is not None
    assert r1.delta_ci_lower is not None


# --- R2: perception-cone geometry -------------------------------------------


def test_cone_detects_prop_directly_ahead_within_range() -> None:
    prop_zone = Zone.CHASHITSU
    prop = _c.ZONE_PROPS[prop_zone][0]
    cx, _cy, cz = _c.ZONE_CENTERS[prop_zone]

    bearing_to_prop = math.atan2(prop.z - cz, prop.x - cx)
    hits = _cone_affordance_set(cx, cz, bearing_to_prop, prop_zone)
    assert prop.prop_id in hits


def test_cone_excludes_prop_directly_behind() -> None:
    prop_zone = Zone.CHASHITSU
    prop = _c.ZONE_PROPS[prop_zone][0]
    cx, _cy, cz = _c.ZONE_CENTERS[prop_zone]
    bearing_to_prop = math.atan2(prop.z - cz, prop.x - cx)
    opposite_yaw = bearing_to_prop + math.pi
    hits = _cone_affordance_set(cx, cz, opposite_yaw, prop_zone)
    assert prop.prop_id not in hits


def test_cone_excludes_prop_beyond_range() -> None:
    far_zone = Zone.GARDEN
    # No props in GARDEN on the real fixture; assert the empty-set contract.
    hits = _cone_affordance_set(0.0, 0.0, 0.0, far_zone)
    assert hits == frozenset()


@pytest.mark.asyncio
async def test_r2_real_fixture_prop_gate_blocks_evaluation() -> None:
    r2 = await evaluate_r2(_SMALL_SEED_BANK)
    assert r2.prop_fixture_valid is False
    assert r2.n_valid_seeds == 0


@pytest.mark.asyncio
async def test_r3_real_fixture_prop_gate_blocks_evaluation() -> None:
    r3 = await evaluate_r3(_SMALL_SEED_BANK)
    assert r3.prop_fixture_valid is False


# --- R3: closure invariant --------------------------------------------------


def test_c_ao_control_obs_purely_zone_determined_collapses_exactly() -> None:
    """Situated-function control: obs=f(zone) only -> residual reads exactly 0."""
    combos = [
        (Zone.STUDY, 0),
        (Zone.STUDY, 1),
        (Zone.CHASHITSU, 0),
        (Zone.CHASHITSU, 1),
    ]
    rows = combos * 30
    rng = random.Random("d0-test-r3-control")
    rng.shuffle(rows)
    zones = [z for z, _a in rows]
    actions = [a for _z, a in rows]
    obs = [z == Zone.CHASHITSU for z in zones]
    seeds = list(range(len(rows)))
    assert _closure_c_ao(zones, actions, obs, seeds) == 0.0


def test_c_ao_detects_genuine_action_linked_structure() -> None:
    """obs depends on (zone, action) jointly beyond zone alone -> residual > 0."""
    combos = [
        (Zone.STUDY, 0),
        (Zone.STUDY, 1),
        (Zone.CHASHITSU, 0),
        (Zone.CHASHITSU, 1),
    ]
    rows = combos * 30
    rng = random.Random("d0-test-r3-joint")
    rng.shuffle(rows)
    zones = [z for z, _a in rows]
    actions = [a for _z, a in rows]
    obs = [(z == Zone.CHASHITSU and a == 1) for z, a in rows]
    seeds = list(range(len(rows)))
    residual = _closure_c_ao(zones, actions, obs, seeds)
    assert residual > 0.10


def test_c_ao_structure_destroying_null_shuffled_action_collapses() -> None:
    """Permuting the action<->obs pairing destroys the joint predictor's edge."""
    combos = [
        (Zone.STUDY, 0),
        (Zone.STUDY, 1),
        (Zone.CHASHITSU, 0),
        (Zone.CHASHITSU, 1),
    ]
    rows = combos * 30
    rng = random.Random("d0-test-r3-null")
    rng.shuffle(rows)
    zones = [z for z, _a in rows]
    actions = [a for _z, a in rows]
    obs = [(z == Zone.CHASHITSU and a == 1) for z, a in rows]
    seeds = list(range(len(rows)))

    real_residual = _closure_c_ao(zones, actions, obs, seeds)
    assert real_residual > 0.0

    shuffle_rng = random.Random("d0-test-r3-null-shuffle")
    shuffled_actions = actions[:]
    shuffle_rng.shuffle(shuffled_actions)
    null_residual = _closure_c_ao(zones, shuffled_actions, obs, seeds)
    assert null_residual <= _c.LANDSCAPE_JACCARD_FLOOR
    assert null_residual < real_residual
