"""Running-ness gate: counterfactual-rollout history-ablation (design-final.md §3).

Certifies that the policy's transition kernel genuinely reads its own history
(``s_{t+1} = T(s_t, H_t; ξ_t)``) rather than being memoryless / frozen-replay
(design-final.md §1.1). This is the **gating validity** the paired
frozen/running contrast alone cannot supply.

**Counterfactual rollout ablation (Codex HIGH-1, DA-RUNIMPL-C1)** — the earlier
"tick-shuffle" ablation is invalid because shuffling *preserves the memory
position set*, so a strength-weighted-centroid policy is nearly invariant under
it and a genuinely history-dependent policy would be **falsely** failed. Here
the ablation instead replaces the memory positions the retriever reads with a
history-independent baseline (the terminal centroid — the most conservative
memoryless counterfactual) and recomputes the forage destination **under the
same jitter draw**. ``δ`` is the distance between the two **post-clamp**
transition destinations (design-final.md §3.1): the real one is the recorded
:attr:`~...policy.ForageRollout.post_clamp_dest`, the ablated one is
``terminal_centroid + same_jitter``. Measuring post-clamp is what keeps the
gate honest — if reflect-clamp collapses both onto the same disc, ``δ → 0``
and the gate reports that history is not effective (clamp over-fired). In the
common (no-clamp) case this reduces to ``δ = ||retrieved_centroid −
terminal_centroid||`` since the shared jitter cancels.

The per-event history effect is the **non-overlap fraction** of two
``CELL_MICRO_RADIUS_M``-radius jitter discs centred ``δ`` apart
(:func:`two_disc_overlap_fraction`); ``δ = 0`` (memoryless) -> effect 0,
``δ >= 2R`` -> effect 1. The per-seed TV is the mean effect over both arms'
forage events; the gate is
``CI_lower(TV) > RUNNINGNESS_TV_FLOOR`` (bootstrap over the seed bank).

Two **robustness** baselines (non-gating, recorded so the ablation-baseline
choice is shown not to drive the gate, design-final.md §3.1) replace the
terminal centroid with (a) an independent disc-uniform point in the terminal
cell and (b) the sibling arm's own terminal-zone memory cloud centroid.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running import constants as _rc
from erre_sandbox.evidence.d0_substrate.running.policy import generate_running_arm

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from erre_sandbox.evidence.d0_substrate.running.policy import (
        PolicyForm,
        RunningArmResult,
    )

_R: float = _c.CELL_MICRO_RADIUS_M


def two_disc_overlap_fraction(delta: float, radius: float = _R) -> float:
    """Overlap area / disc area of two equal-radius discs ``delta`` apart.

    Closed form for the lens area of two circles of radius ``radius`` whose
    centres are ``|delta|`` apart, normalised by one disc's area. ``delta = 0``
    -> 1.0 (coincident); ``|delta| >= 2·radius`` -> 0.0 (disjoint); monotone
    decreasing in between. Symmetric in ``delta``.
    """
    if radius <= 0.0:
        return 0.0
    d = abs(delta)
    if d >= 2.0 * radius:
        return 0.0
    if d == 0.0:
        return 1.0
    ratio = min(1.0, max(-1.0, d / (2.0 * radius)))
    lens = 2.0 * radius * radius * math.acos(ratio) - (d / 2.0) * math.sqrt(
        max(0.0, 4.0 * radius * radius - d * d)
    )
    return lens / (math.pi * radius * radius)


def _history_effect(
    real_dest: tuple[float, float], ablated_dest: tuple[float, float]
) -> float:
    """``1 − overlap(δ)`` for one forage event, ``δ = ||real_dest − ablated_dest||``.

    Both destinations are the **post-clamp** transition points (design-final.md
    §3.1): the real one is the recorded ``ForageRollout.post_clamp_dest``, the
    ablated one is ``baseline + jitter`` (same forage jitter). Measuring
    post-clamp is what makes the gate honest — if reflect-clamp collapses the
    real and ablated destinations onto the same disc, ``δ → 0`` and the gate
    correctly reports that history is not effective (clamp over-fired), which a
    pre-clamp centroid difference would miss.
    """
    delta = math.hypot(real_dest[0] - ablated_dest[0], real_dest[1] - ablated_dest[1])
    return 1.0 - two_disc_overlap_fraction(delta, _R)


def _terminal_cloud_centroid(arm: RunningArmResult) -> tuple[float, float] | None:
    """Mean (x, z) of the arm's memories in its terminal zone, or ``None``.

    The sibling arm's history cloud used by the ``other-cloud`` robustness
    baseline (design-final.md §3.1). Terminal zone = the ``terminal_centroid``
    the forage rollouts anchor to; falls back to ``None`` when the arm has no
    forage rollout (a non-P-A-family policy).
    """
    if not arm.forage_rollouts:
        return None
    terminal_xz = arm.forage_rollouts[0].terminal_centroid
    pts = [
        (r.x, r.z)
        for r in arm.trace.rows
        if math.hypot(r.x - terminal_xz[0], r.z - terminal_xz[1]) <= _R
    ]
    if not pts:
        return None
    return (
        sum(p[0] for p in pts) / len(pts),
        sum(p[1] for p in pts) / len(pts),
    )


@dataclass(frozen=True)
class RunningnessResult:
    """History-ablation running-ness verdict + robustness forensic (§3)."""

    tv_ci_lower: float
    tv_median: float
    gate_pass: bool
    n_seeds: int
    per_seed_tv: tuple[float, ...]
    tv_ci_lower_indep_baseline: float
    tv_ci_lower_other_cloud_baseline: float
    n_forage_events: int


def _ci_lower(values: list[float], bootstrap_seed: int) -> float:
    if not values:
        return 0.0
    return bootstrap_ci(
        values,
        n_resamples=_c.N_RESAMPLES,
        ci=1.0 - _c.CI_ALPHA,
        seed=bootstrap_seed,
        statistic="mean",
    ).lo


async def compute_runningness(
    seed_bank: Sequence[int],
    policy: PolicyForm = "P-A",
    *,
    bootstrap_seed: int = 0,
    arm_provider: (
        Callable[[int], Awaitable[tuple[RunningArmResult, RunningArmResult]]] | None
    ) = None,
) -> RunningnessResult:
    """Run the history-ablation gate over ``seed_bank`` (design-final.md §3).

    ``arm_provider`` lets a caller (the sealed-run script) inject already
    generated arm pairs to avoid regenerating them; the default generates the
    two arms deterministically per seed.
    """
    per_seed_tv: list[float] = []
    per_seed_tv_indep: list[float] = []
    per_seed_tv_other: list[float] = []
    n_forage = 0

    for seed in seed_bank:
        if arm_provider is not None:
            arm_a, arm_b = await arm_provider(seed)
        else:
            arm_a = await generate_running_arm(seed, "A", policy)
            arm_b = await generate_running_arm(seed, "B", policy)

        cloud_a = _terminal_cloud_centroid(arm_a)
        cloud_b = _terminal_cloud_centroid(arm_b)

        effects: list[float] = []
        effects_indep: list[float] = []
        effects_other: list[float] = []
        for arm_name, arm, other_cloud in (
            ("A", arm_a, cloud_b),
            ("B", arm_b, cloud_a),
        ):
            # Per-arm ablate substream (code-reviewer LOW-7): arm A's forage
            # count must not shift arm B's independent-baseline jitter.
            ablate_rng = random.Random(f"run-seed-{seed}-{arm_name}-ablate")  # noqa: S311
            for ro in arm.forage_rollouts:
                jx, jz = ro.jitter
                # Gating: baseline = terminal centroid. Real/ablated are both the
                # POST-clamp transition (design-final.md §3.1): real is the
                # recorded post_clamp_dest, ablated is terminal_centroid + same
                # jitter (within-cell, so clamp is a no-op there).
                ablated = (ro.terminal_centroid[0] + jx, ro.terminal_centroid[1] + jz)
                effects.append(_history_effect(ro.post_clamp_dest, ablated))
                # (a) independent disc-uniform baseline point in the terminal cell.
                jr = _c.CELL_MICRO_RADIUS_M * math.sqrt(ablate_rng.random())
                jt = ablate_rng.uniform(0.0, 2.0 * math.pi)
                indep = (
                    ro.terminal_centroid[0] + jr * math.cos(jt) + jx,
                    ro.terminal_centroid[1] + jr * math.sin(jt) + jz,
                )
                effects_indep.append(_history_effect(ro.post_clamp_dest, indep))
                # (b) sibling arm's terminal-zone memory-cloud centroid + jitter.
                base_other = (
                    other_cloud if other_cloud is not None else ro.terminal_centroid
                )
                ablated_other = (base_other[0] + jx, base_other[1] + jz)
                effects_other.append(_history_effect(ro.post_clamp_dest, ablated_other))

        n_forage += len(effects)
        if effects:
            per_seed_tv.append(statistics.fmean(effects))
            per_seed_tv_indep.append(statistics.fmean(effects_indep))
            per_seed_tv_other.append(statistics.fmean(effects_other))

    tv_ci_lower = _ci_lower(per_seed_tv, bootstrap_seed)
    tv_median = statistics.median(per_seed_tv) if per_seed_tv else 0.0
    return RunningnessResult(
        tv_ci_lower=tv_ci_lower,
        tv_median=tv_median,
        gate_pass=tv_ci_lower > _rc.RUNNINGNESS_TV_FLOOR,
        n_seeds=len(per_seed_tv),
        per_seed_tv=tuple(per_seed_tv),
        tv_ci_lower_indep_baseline=_ci_lower(per_seed_tv_indep, bootstrap_seed + 1),
        tv_ci_lower_other_cloud_baseline=_ci_lower(
            per_seed_tv_other, bootstrap_seed + 2
        ),
        n_forage_events=n_forage,
    )


__all__ = [
    "RunningnessResult",
    "compute_runningness",
    "two_disc_overlap_fraction",
]
