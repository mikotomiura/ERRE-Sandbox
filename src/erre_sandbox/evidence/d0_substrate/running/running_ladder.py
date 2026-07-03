"""R0/R1 ladder readout driven by a swappable trace builder (design-final.md §2.1).

The frozen :mod:`erre_sandbox.evidence.d0_substrate.ladder` binds
``stub.build_seed_pair`` at import time and calls it directly inside
``r0_r1_seed_point``, so the blind generator cannot be drop-in replaced and
monkeypatching it is a **forbidden** tune path (Codex HIGH-3). This module
instead re-implements the **same readout recipe** — position-quantize to R1,
four :func:`~...ladder._retrieval_divergence` calls (D0/D0-null/D1/D1-null),
``Δ = D1 − D0`` — while taking the ``(trace_a, trace_b, start, terminal)``
builder as a parameter, and imports the frozen ladder's estimand/statistic
helpers **read-only** so the arithmetic is byte-identical.

A **blind-equivalence golden test**
(``tests/test_evidence/test_d0_running_golden.py``) pins that driving this
recipe with the blind :func:`~...stub.build_seed_pair` reproduces
``ladder.evaluate_r0_and_r1`` byte-for-byte, proving the recipe is a faithful
copy and any difference in the sealed run is attributable to the running
*generator* alone (not an apparatus reparameterisation) — the non-circular
paired-frozen/running contrast the ADR requires (design-final.md §4.3).

``ladder.py`` / ``stub.py`` / ``constants.py`` stay byte-unchanged; this module
only imports them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import (
    RungResult,
    SeedPointR0R1,
    _r0_result_from_points,
    _r1_result_from_points,
    _retrieval_divergence,
)
from erre_sandbox.evidence.d0_substrate.running.policy import build_seed_pair_running
from erre_sandbox.evidence.d0_substrate.stub import build_seed_pair, quantize_trace
from erre_sandbox.schemas import SpatialContext

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from erre_sandbox.evidence.d0_substrate.running.policy import PolicyForm
    from erre_sandbox.evidence.d0_substrate.stub import Trace3D
    from erre_sandbox.schemas import Zone


async def r0_r1_seed_point_running(
    seed: int,
    builder: Callable[[int], Awaitable[tuple[Trace3D, Trace3D, Zone, Zone]]],
) -> SeedPointR0R1:
    """One seed's R0/R1 divergence/null/Δ, identical recipe to ``ladder``.

    A verbatim copy of :func:`ladder.r0_r1_seed_point`'s body with the single
    substitution ``build_seed_pair(seed) -> await builder(seed)``. Every other
    step — terminal ``SpatialContext``, ``quantize_trace(., "R1")``, the four
    ``_retrieval_divergence`` calls, ``delta = d1 - d0`` — is the frozen recipe
    reused read-only (byte-identical golden guarantee).
    """
    trace_a, trace_b, _start, terminal_zone = await builder(seed)
    terminal = SpatialContext(
        zone=terminal_zone,
        x=_c.ZONE_CENTERS[terminal_zone][0],
        y=_c.ZONE_CENTERS[terminal_zone][1],
        z=_c.ZONE_CENTERS[terminal_zone][2],
    )
    quant_a = quantize_trace(trace_a, "R1")
    quant_b = quantize_trace(trace_b, "R1")

    d0 = await _retrieval_divergence(quant_a, quant_b, terminal, spatial_weight=1.0)
    d0_null = await _retrieval_divergence(
        quant_a, quant_b, terminal, spatial_weight=0.0
    )
    d1 = await _retrieval_divergence(trace_a, trace_b, terminal, spatial_weight=1.0)
    d1_null = await _retrieval_divergence(
        trace_a, trace_b, terminal, spatial_weight=0.0
    )
    return SeedPointR0R1(
        seed=seed, d0=d0, d0_null=d0_null, d1=d1, d1_null=d1_null, delta=d1 - d0
    )


async def evaluate_r0_and_r1_running(
    seed_bank: Sequence[int],
    builder: Callable[[int], Awaitable[tuple[Trace3D, Trace3D, Zone, Zone]]],
    *,
    bootstrap_seed: int = 0,
) -> tuple[RungResult, RungResult]:
    """R0 + R1 over ``seed_bank`` for ``builder`` (frozen result aggregation).

    Mirrors :func:`ladder.evaluate_r0_and_r1`: one seed point per seed, then the
    frozen ``_r0_result_from_points`` / ``_r1_result_from_points`` reused
    read-only so the RungResult shape / floors / bootstrap are byte-identical.
    """
    points = [await r0_r1_seed_point_running(s, builder) for s in seed_bank]
    return (
        _r0_result_from_points(points, bootstrap_seed),
        _r1_result_from_points(points, bootstrap_seed),
    )


async def blind_builder(seed: int) -> tuple[Trace3D, Trace3D, Zone, Zone]:
    """Async adapter over the frozen blind ``stub.build_seed_pair`` (golden test)."""
    return build_seed_pair(seed)


def running_builder(
    policy: PolicyForm = "P-A",
) -> Callable[[int], Awaitable[tuple[Trace3D, Trace3D, Zone, Zone]]]:
    """A ``seed -> running trace pair`` builder for the given policy (§4.5).

    ``policy="P-A"`` is the primary sealed-run generator; the forensic-control
    policies drive the same readout for the non-gating variant fields.
    """

    async def _build(seed: int) -> tuple[Trace3D, Trace3D, Zone, Zone]:
        return await build_seed_pair_running(seed, policy=policy)

    return _build


__all__ = [
    "blind_builder",
    "evaluate_r0_and_r1_running",
    "r0_r1_seed_point_running",
    "running_builder",
]
