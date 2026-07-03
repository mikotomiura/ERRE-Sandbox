"""Forensic controls (design-final.md §4): geometry derivation + prop-free split.

The geometry forensic is derived from the primary P-A run with **synthetic**
seed points (so no real R1/Δ_1 verdict is exposed — forking-paths seal); the
control-orchestration cost (5 variant runs) is exercised end-to-end only in the
sealed run, not here.
"""

from __future__ import annotations

import statistics

import pytest

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import SeedPointR0R1
from erre_sandbox.evidence.d0_substrate.running.forensic import (
    _PROP_FREE_ZONES,
    ForensicReport,
    _derive_geometry,
    _terminal_count_from_pairs,
    compute_forensic,
)
from erre_sandbox.evidence.d0_substrate.running.policy import generate_running_arm
from erre_sandbox.evidence.d0_substrate.running.running_ladder import (
    r0_r1_seed_point_running,
    running_builder,
)
from erre_sandbox.evidence.d0_substrate.stub import draw_start_terminal
from erre_sandbox.schemas import Zone


def test_prop_free_zones_exclude_chashitsu() -> None:
    # CHASHITSU is the only prop-bearing zone on the frozen fixture; the four
    # others are prop-free (design-final.md §8.1 claim_scope input).
    assert Zone.CHASHITSU.value not in _PROP_FREE_ZONES
    assert len(_PROP_FREE_ZONES) == 4


@pytest.mark.asyncio
async def test_derive_geometry_fields_are_well_formed() -> None:
    seed_bank = tuple(range(2))
    arm_pairs = {
        s: (
            await generate_running_arm(s, "A", "P-A"),
            await generate_running_arm(s, "B", "P-A"),
        )
        for s in seed_bank
    }
    # Synthetic seed points: real generator arms, chosen deltas (no R1 exposure).
    points = [
        SeedPointR0R1(seed=s, d0=0.0, d0_null=0.0, d1=0.5, d1_null=0.0, delta=0.3)
        for s in seed_bank
    ]
    geom = _derive_geometry(seed_bank, points, arm_pairs)

    assert 0.0 <= geom.clamp_rate <= 1.0
    assert 0.0 <= geom.topk_zone_saturated <= 1.0
    # Each arm forms exactly M_MEMORIES memories, so the per-zone mean counts
    # sum to M across the five zones.
    assert abs(sum(geom.per_zone_memory_count.values()) - _c.M_MEMORIES) < 1e-9
    # Independent jitter => the two arms sit at different within-terminal-zone
    # mean positions.
    assert geom.within_zone_geometry_present is True
    assert geom.within_zone_arm_distance_median > 0.0
    # δ = 0.3 for every seed => any prop-free-terminal seed yields 0.3, else 0.
    assert geom.prop_free_zone_delta1 in (0.0, 0.3)


@pytest.mark.asyncio
async def test_topk_saturation_counts_zero_delta_seeds() -> None:
    seed_bank = tuple(range(2))
    arm_pairs = {
        s: (
            await generate_running_arm(s, "A", "P-A"),
            await generate_running_arm(s, "B", "P-A"),
        )
        for s in seed_bank
    }
    # Both seeds carry Δ_1 = 0 => fully saturated (membership invariant under
    # quantize); this exercises the topk_zone_saturated branch, not a verdict.
    points = [
        SeedPointR0R1(seed=s, d0=0.0, d0_null=0.0, d1=0.0, d1_null=0.0, delta=0.0)
        for s in seed_bank
    ]
    geom = _derive_geometry(seed_bank, points, arm_pairs)
    assert geom.topk_zone_saturated == 1.0


@pytest.mark.asyncio
async def test_compute_forensic_orchestration_wiring() -> None:
    # End-to-end wiring smoke for the control orchestration (5 variant runs +
    # spontaneous count) that is otherwise only exercised in the one-shot sealed
    # run. Asserts a well-formed ForensicReport with sane ranges — never a
    # pinned verdict value (forking-paths seal). Tiny seed bank for speed.
    seed_bank = tuple(range(2))
    builder = running_builder("P-A")
    points = [await r0_r1_seed_point_running(s, builder) for s in seed_bank]
    arm_pairs = {
        s: (
            await generate_running_arm(s, "A", "P-A"),
            await generate_running_arm(s, "B", "P-A"),
        )
        for s in seed_bank
    }
    report = await compute_forensic(seed_bank, points, arm_pairs)

    assert isinstance(report, ForensicReport)
    assert 0.0 <= report.clamp_rate <= 1.0
    assert 0.0 <= report.topk_zone_saturated <= 1.0
    assert report.spontaneous_terminal_zone_memory_count >= 0.0
    # Control booleans are populated (real bools, not None); values not pinned.
    assert isinstance(report.memoryless_r1_pass, bool)
    assert isinstance(report.spontaneous_r1_pass, bool)
    assert isinstance(report.no_reflect_r1_pass, bool)
    assert isinstance(report.uniform_centroid_r1_pass, bool)
    assert isinstance(report.top1_centroid_r1_pass, bool)


@pytest.mark.asyncio
async def test_terminal_count_from_pairs_matches_manual_count() -> None:
    # Unit test for the shared spontaneous terminal-count (code-reviewer M3/M6):
    # median memories the emergent P-B policy drops in the drawn terminal zone.
    seed_bank = (0, 1)
    pairs = {
        s: (
            await generate_running_arm(s, "A", "spontaneous"),
            await generate_running_arm(s, "B", "spontaneous"),
        )
        for s in seed_bank
    }
    result = _terminal_count_from_pairs(seed_bank, pairs)

    manual: list[int] = []
    for s in seed_bank:
        terminal_value = draw_start_terminal(s)[1].value
        manual.extend(
            sum(1 for r in arm.trace.rows if r.zone.value == terminal_value)
            for arm in pairs[s]
        )
    assert result == statistics.median(manual)
    assert result >= 0.0
