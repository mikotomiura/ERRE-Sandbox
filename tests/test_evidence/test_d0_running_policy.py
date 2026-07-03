"""Running-trace generator: determinism, schema conformance, policy grammar.

Structural/wiring checks only — never the R1/Δ_1 verdict (forking-paths seal,
design-final.md §5-6). The policy grammar freeze (design-final.md §5, 6 items)
is pinned here + in the module docstring.
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running.policy import (
    build_seed_pair_running,
    generate_running_arm,
)
from erre_sandbox.evidence.d0_substrate.stub import draw_start_terminal, trace_checksum
from erre_sandbox.world.zones import locate_zone


@pytest.mark.asyncio
async def test_replay_checksum_deterministic() -> None:
    first = await generate_running_arm(3, "A", "P-A")
    second = await generate_running_arm(3, "A", "P-A")
    assert trace_checksum(first.trace.rows) == trace_checksum(second.trace.rows)
    assert first.physics_ticks == second.physics_ticks


@pytest.mark.asyncio
async def test_trace_schema_conforms() -> None:
    arm = await generate_running_arm(1, "A", "P-A")
    assert len(arm.trace.rows) == _c.M_MEMORIES
    assert [r.tick_index for r in arm.trace.rows] == list(range(_c.M_MEMORIES))
    for r in arm.trace.rows:
        assert r.seed == 1
        assert r.pitch == 0.0
        # position agrees with its assigned zone (10 m jitter stays in-cell).
        assert locate_zone(r.x, r.y, r.z) == r.zone


@pytest.mark.asyncio
async def test_terminal_zone_concentration_exceeds_k() -> None:
    # P-A anchors to terminal: after phase A the agent stays and forages there,
    # so > K_RETRIEVE memories land in the terminal zone (necessary condition for
    # Δ_1 > 0, design-final.md §0.1 fact 1). Structural, not the R1 verdict.
    _start, terminal = draw_start_terminal(5)
    arm = await generate_running_arm(5, "A", "P-A")
    terminal_count = sum(1 for r in arm.trace.rows if r.zone == terminal)
    assert terminal_count > _c.K_RETRIEVE


@pytest.mark.asyncio
async def test_forage_rollouts_reflect_clamped_into_terminal_cell() -> None:
    _start, terminal = draw_start_terminal(2)
    arm = await generate_running_arm(2, "A", "P-A")
    assert arm.forage_rollouts  # phase B produced forage events
    for ro in arm.forage_rollouts:
        px, pz = ro.post_clamp_dest
        assert locate_zone(px, 0.0, pz) == terminal


@pytest.mark.asyncio
async def test_two_arms_share_endpoints_and_diverge() -> None:
    trace_a, trace_b, start, terminal = await build_seed_pair_running(4)
    assert (start, terminal) == draw_start_terminal(4)
    # independent jitter substreams => the arms are not byte-identical.
    assert trace_checksum(trace_a.rows) != trace_checksum(trace_b.rows)


@pytest.mark.asyncio
async def test_memoryless_forage_uses_terminal_centroid_baseline() -> None:
    # C-memoryless (P-C): forage centroid == terminal centroid (δ = 0), the
    # concentration-without-history control (design-final.md §4.1).
    arm = await generate_running_arm(0, "A", "memoryless")
    assert arm.forage_rollouts
    for ro in arm.forage_rollouts:
        assert ro.retrieved_centroid == ro.terminal_centroid


@pytest.mark.asyncio
async def test_all_policy_forms_generate_valid_traces() -> None:
    for policy in (
        "P-A",
        "memoryless",
        "spontaneous",
        "no-reflect",
        "uniform-centroid",
        "top-1-centroid",
    ):
        arm = await generate_running_arm(1, "A", policy)  # type: ignore[arg-type]
        assert len(arm.trace.rows) == _c.M_MEMORIES
