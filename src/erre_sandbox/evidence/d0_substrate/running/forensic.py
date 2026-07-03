"""Non-gating forensic controls for the running D0a re-run (design-final.md §4).

None of these change the verdict (design-final.md §4 / §7); they are recorded
so the ``STRUCTURAL_READY_RUNNING`` claim cannot be over-read, and they are a
**FROZEN required component** of the apparatus (omitting them = binding
premise unmet, design-final.md §7):

* **Geometry forensic** (derived from the primary P-A run): ``clamp_rate``
  (§1.3/§4), ``topk_zone_saturated`` + ``within_zone_geometry_present`` (§4.3
  wall-3 attribution), ``per_zone_memory_count`` /
  ``per_zone_delta1_contribution`` / ``prop_free_zone_delta1`` (§4.4/§8, the
  claim_scope narrowing input). Because P-A concentrates memories in the
  **terminal** zone, the per-zone Δ_1 decomposition is a **terminal-zone
  split**: a seed's Δ_1 (its ``SeedPointR0R1.delta``) is attributed to that
  seed's drawn terminal zone, and ``prop_free_zone_delta1`` is the median Δ_1
  over seeds whose terminal zone carries no props (``ZONE_PROPS`` empty). If
  Δ_1 clears the floor on the prop-free-terminal subset the within-zone
  structure is not a CHASHITSU-local prop artefact (design-final.md §8.1).

* **C-memoryless** (§4.1, most load-bearing): same concentration with no
  preferential return -> expected R1 PASS ∧ running-ness gate FAIL, which
  demonstrates ``R1 = concentration``, not running-ness.
* **C-spontaneous** (§4.2, = v1 / P-B): terminal-agnostic emergent dwelling ->
  expected R1 FAIL (emergent dwelling coincides with the independent terminal
  only ~1/5 of seeds), recorded with ``spontaneous_terminal_zone_memory_count``.
* **policy-form variants** (§4.5): ``no-reflect`` / ``uniform-centroid`` /
  ``top-1-centroid`` R1 pass, exposing whether the P-A functional-form choice
  drives the result.

All expectations are **pre-registered predictions**, not asserted results; the
sealed run records what actually happens.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running.policy import generate_running_arm
from erre_sandbox.evidence.d0_substrate.running.running_ladder import (
    evaluate_r0_and_r1_running,
    running_builder,
)
from erre_sandbox.evidence.d0_substrate.running.runningness import compute_runningness
from erre_sandbox.evidence.d0_substrate.stub import draw_start_terminal
from erre_sandbox.evidence.d0_substrate.verdict_report import evaluate_rung

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from erre_sandbox.evidence.d0_substrate.ladder import RungResult, SeedPointR0R1
    from erre_sandbox.evidence.d0_substrate.running.policy import RunningArmResult
    from erre_sandbox.evidence.d0_substrate.stub import Trace3D
    from erre_sandbox.schemas import Zone

_R: float = _c.CELL_MICRO_RADIUS_M
_PROP_FREE_ZONES: frozenset[str] = frozenset(
    zone.value for zone, props in _c.ZONE_PROPS.items() if not props
)
"""Zone values that carry no props on the frozen (CHASHITSU-only) fixture —
the prop-independent zones whose Δ_1 contribution guards against a
CHASHITSU-local over-read (design-final.md §8.1)."""


@dataclass(frozen=True)
class _Geometry:
    """Typed carrier for the primary-run geometry forensic (mypy-clean)."""

    within_zone_geometry_present: bool
    within_zone_arm_distance_median: float
    topk_zone_saturated: float
    clamp_rate: float
    per_zone_memory_count: dict[str, float]
    per_zone_delta1_contribution: dict[str, float]
    prop_free_zone_delta1: float


@dataclass(frozen=True)
class ForensicReport:
    """All non-gating §4 forensic fields (design-final.md §4/§8)."""

    within_zone_geometry_present: bool
    within_zone_arm_distance_median: float
    topk_zone_saturated: float
    clamp_rate: float
    per_zone_memory_count: Mapping[str, float]
    per_zone_delta1_contribution: Mapping[str, float]
    prop_free_zone_delta1: float
    memoryless_r1_pass: bool
    memoryless_running_tv_ci_lower: float
    spontaneous_r1_pass: bool
    spontaneous_median_delta1: float
    spontaneous_terminal_zone_memory_count: float
    no_reflect_r1_pass: bool
    uniform_centroid_r1_pass: bool
    top1_centroid_r1_pass: bool


def _terminal_zone_rows_mean(
    arm: RunningArmResult, terminal_value: str
) -> tuple[float, float] | None:
    pts = [(r.x, r.z) for r in arm.trace.rows if r.zone.value == terminal_value]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _r1_pass(r1: RungResult) -> bool:
    return evaluate_rung(r1).state == "PASS"


def _derive_geometry(
    seed_bank: Sequence[int],
    seed_points: Sequence[SeedPointR0R1],
    arm_pairs: Mapping[int, tuple[RunningArmResult, RunningArmResult]],
) -> _Geometry:
    """Geometry forensic from the primary P-A run (pure, no regeneration)."""
    point_by_seed = {p.seed: p for p in seed_points}
    terminal_of = {seed: draw_start_terminal(seed)[1] for seed in seed_bank}

    zone_counts: dict[str, list[int]] = {z.value: [] for z in _c.ZONES}
    per_zone_deltas: dict[str, list[float]] = {z.value: [] for z in _c.ZONES}
    arm_distances: list[float] = []
    clamp_fired = 0
    forage_total = 0
    saturated = 0

    for seed in seed_bank:
        arm_a, arm_b = arm_pairs[seed]
        terminal_value = terminal_of[seed].value
        for arm in (arm_a, arm_b):
            counts: dict[str, int] = {z.value: 0 for z in _c.ZONES}
            for row in arm.trace.rows:
                counts[row.zone.value] += 1
            for zv, c in counts.items():
                zone_counts[zv].append(c)
            for ro in arm.forage_rollouts:
                forage_total += 1
                if ro.clamp_fired:
                    clamp_fired += 1

        mean_a = _terminal_zone_rows_mean(arm_a, terminal_value)
        mean_b = _terminal_zone_rows_mean(arm_b, terminal_value)
        if mean_a is not None and mean_b is not None:
            arm_distances.append(
                ((mean_a[0] - mean_b[0]) ** 2 + (mean_a[1] - mean_b[1]) ** 2) ** 0.5
            )

        point = point_by_seed.get(seed)
        if point is not None:
            per_zone_deltas[terminal_value].append(point.delta)
            if abs(point.delta) <= _c.ZERO_TOL:
                saturated += 1

    within_distance_median = statistics.median(arm_distances) if arm_distances else 0.0
    per_zone_delta1 = {
        zv: (statistics.median(ds) if ds else 0.0) for zv, ds in per_zone_deltas.items()
    }
    prop_free_deltas = [
        d for zv, ds in per_zone_deltas.items() if zv in _PROP_FREE_ZONES for d in ds
    ]
    return _Geometry(
        within_zone_geometry_present=within_distance_median > _c.ZERO_TOL,
        within_zone_arm_distance_median=within_distance_median,
        topk_zone_saturated=(saturated / len(seed_bank)) if seed_bank else 0.0,
        clamp_rate=(clamp_fired / forage_total) if forage_total else 0.0,
        per_zone_memory_count={
            zv: (statistics.fmean(cs) if cs else 0.0) for zv, cs in zone_counts.items()
        },
        per_zone_delta1_contribution=per_zone_delta1,
        prop_free_zone_delta1=(
            statistics.median(prop_free_deltas) if prop_free_deltas else 0.0
        ),
    )


async def _spontaneous_arm_pairs(
    seed_bank: Sequence[int],
) -> dict[int, tuple[RunningArmResult, RunningArmResult]]:
    """Generate the P-B (spontaneous) arm pairs once for reuse (code-reviewer M3)."""
    return {
        seed: (
            await generate_running_arm(seed, "A", "spontaneous"),
            await generate_running_arm(seed, "B", "spontaneous"),
        )
        for seed in seed_bank
    }


def _pairs_builder(
    pairs: Mapping[int, tuple[RunningArmResult, RunningArmResult]],
) -> Callable[[int], Awaitable[tuple[Trace3D, Trace3D, Zone, Zone]]]:
    """Wrap pre-generated arm pairs as a ``running_ladder`` builder (no re-gen)."""

    async def _build(seed: int) -> tuple[Trace3D, Trace3D, Zone, Zone]:
        arm_a, arm_b = pairs[seed]
        start, terminal = draw_start_terminal(seed)
        return arm_a.trace, arm_b.trace, start, terminal

    return _build


def _terminal_count_from_pairs(
    seed_bank: Sequence[int],
    pairs: Mapping[int, tuple[RunningArmResult, RunningArmResult]],
) -> float:
    """Median count of memories an emergent policy drops in the drawn terminal."""
    counts: list[int] = []
    for seed in seed_bank:
        terminal_value = draw_start_terminal(seed)[1].value
        counts.extend(
            sum(1 for r in arm.trace.rows if r.zone.value == terminal_value)
            for arm in pairs[seed]
        )
    return statistics.median(counts) if counts else 0.0


async def compute_forensic(
    seed_bank: Sequence[int],
    seed_points: Sequence[SeedPointR0R1],
    arm_pairs: Mapping[int, tuple[RunningArmResult, RunningArmResult]],
    *,
    bootstrap_seed: int = 0,
) -> ForensicReport:
    """Full §4 forensic: geometry (from the primary run) + control orchestration.

    The forensic-control policies (``memoryless`` / ``spontaneous`` / the three
    policy-form variants) drive the **same** frozen readout via
    :func:`running_ladder.running_builder`, so they differ from the primary run
    in the generator alone.
    """
    geometry = _derive_geometry(seed_bank, seed_points, arm_pairs)

    _r0_m, r1_memoryless = await evaluate_r0_and_r1_running(
        seed_bank, running_builder("memoryless"), bootstrap_seed=bootstrap_seed
    )
    memoryless_running = await compute_runningness(
        seed_bank, "memoryless", bootstrap_seed=bootstrap_seed
    )
    # Spontaneous (P-B) arms generated once, shared by the R1 eval and the
    # terminal-count (code-reviewer MEDIUM-3: no double generation).
    spontaneous_pairs = await _spontaneous_arm_pairs(seed_bank)
    _r0_s, r1_spontaneous = await evaluate_r0_and_r1_running(
        seed_bank, _pairs_builder(spontaneous_pairs), bootstrap_seed=bootstrap_seed
    )
    _r0_nr, r1_no_reflect = await evaluate_r0_and_r1_running(
        seed_bank, running_builder("no-reflect"), bootstrap_seed=bootstrap_seed
    )
    _r0_uc, r1_uniform = await evaluate_r0_and_r1_running(
        seed_bank, running_builder("uniform-centroid"), bootstrap_seed=bootstrap_seed
    )
    _r0_t1, r1_top1 = await evaluate_r0_and_r1_running(
        seed_bank, running_builder("top-1-centroid"), bootstrap_seed=bootstrap_seed
    )
    spontaneous_terminal_count = _terminal_count_from_pairs(
        seed_bank, spontaneous_pairs
    )

    return ForensicReport(
        within_zone_geometry_present=geometry.within_zone_geometry_present,
        within_zone_arm_distance_median=geometry.within_zone_arm_distance_median,
        topk_zone_saturated=geometry.topk_zone_saturated,
        clamp_rate=geometry.clamp_rate,
        per_zone_memory_count=geometry.per_zone_memory_count,
        per_zone_delta1_contribution=geometry.per_zone_delta1_contribution,
        prop_free_zone_delta1=geometry.prop_free_zone_delta1,
        memoryless_r1_pass=_r1_pass(r1_memoryless),
        memoryless_running_tv_ci_lower=memoryless_running.tv_ci_lower,
        spontaneous_r1_pass=_r1_pass(r1_spontaneous),
        spontaneous_median_delta1=(r1_spontaneous.delta_median or 0.0),
        spontaneous_terminal_zone_memory_count=spontaneous_terminal_count,
        no_reflect_r1_pass=_r1_pass(r1_no_reflect),
        uniform_centroid_r1_pass=_r1_pass(r1_uniform),
        top1_centroid_r1_pass=_r1_pass(r1_top1),
    )


__all__ = [
    "ForensicReport",
    "compute_forensic",
]
