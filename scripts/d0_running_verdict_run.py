"""Run the M13 running-substrate D0a re-run verdict once (SEALED, one-shot).

This is the **single** entry point that turns the running-trace generator
(:mod:`erre_sandbox.evidence.d0_substrate.running.policy`) + the frozen R0->R3
ladder readout driven by a running builder
(:mod:`~erre_sandbox.evidence.d0_substrate.running.running_ladder`) + the
history-ablation running-ness gate
(:mod:`~erre_sandbox.evidence.d0_substrate.running.runningness`) + the §4
forensic controls (:mod:`~erre_sandbox.evidence.d0_substrate.running.forensic`)
into a recorded ``structural_status_running`` verdict
(:mod:`~erre_sandbox.evidence.d0_substrate.running.verdict_running`). It
re-tunes nothing: every threshold lives in the frozen constants and the
decision logic in ``verdict_running``; this script only drives the
pre-registered seed bank through them and writes the verdict + forensic trail.

**Forking-paths seal (design-final.md §5-5/§5-6, ES-4 discipline)**: run
**once** with the pre-registered
:func:`~erre_sandbox.evidence.d0_substrate.stub.default_seed_bank`. Do not
re-run with a tweaked policy/floor to flip the verdict; a different config
requires a superseding ADR. A non-PASS/INCONCLUSIVE result is the **true
trigger** of the disposition §5 arc-close-reconsideration ADR (a mandatory
filing, not a re-run licence). The apparatus is deterministic, so a second run
is only ever a byte-identical confirmation.

**Not executed by the apparatus-implementation task**: the apparatus is frozen
and committed first; this script is run from committed frozen code in a
separate fresh session (airtight seal). See the apparatus-implementation ADR
"この prompt の位置と次工程".

Usage::

    uv run python scripts/d0_running_verdict_run.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import (
    RungName,
    RungResult,
    SeedPointR0R1,
    _r0_result_from_points,
    _r1_result_from_points,
    evaluate_r0_and_r1,
    evaluate_r2,
    evaluate_r3,
)
from erre_sandbox.evidence.d0_substrate.running.forensic import compute_forensic
from erre_sandbox.evidence.d0_substrate.running.policy import (
    RunningArmResult,
    generate_running_arm,
)
from erre_sandbox.evidence.d0_substrate.running.running_ladder import (
    r0_r1_seed_point_running,
)
from erre_sandbox.evidence.d0_substrate.running.runningness import compute_runningness
from erre_sandbox.evidence.d0_substrate.running.verdict_running import (
    RunningVerdict,
    render_running_verdict,
)
from erre_sandbox.evidence.d0_substrate.smoke import run_smoke
from erre_sandbox.evidence.d0_substrate.stub import (
    Trace3D,
    default_seed_bank,
    draw_start_terminal,
    trace_checksum,
)
from erre_sandbox.evidence.d0_substrate.verdict_report import render_structural_verdict

_OUT_DIR: Final[Path] = Path(".steering/20260703-m13-running-apparatus-impl")
_FORENSIC_PATH: Final[Path] = _OUT_DIR / "running-verdict-forensic.json"

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final.md §6/§7, over-claim guard): "
    "STRUCTURAL_READY_RUNNING means within-zone situated structural outcome is "
    "measurable non-circularly ON A RUNNING TRACE and the frozen<->running "
    "distinction is real -- a terminal-anchored existence-proof under a "
    "return-to-home errand, NOT a divergence test, and the R1 advance is NOT "
    "itself running-specific (the running-ness gate certifies history-dependence "
    "separately; the C-memoryless control shows the same concentration passes R1 "
    "without history).",
    "running-ness gate (design-final.md §3, Codex HIGH-1 counterfactual rollout): "
    "history-dependence is certified by CI_lower(TV) > RUNNINGNESS_TV_FLOOR over a "
    "counterfactual-rollout ablation (memory positions collapsed to the terminal "
    "centroid, same jitter); a memoryless/frozen-replay policy fails it.",
    "forensic controls are non-gating but a FROZEN required component "
    "(design-final.md §7): C-memoryless (expected R1 PASS + gate FAIL), "
    "C-spontaneous (expected R1 FAIL), policy-form variants -- recorded to bound "
    "the claim, never to change the verdict.",
    "one-shot kill (design-final.md §5-5): a NO_STRUCTURAL_FLOOR_RUNNING / "
    "INCONCLUSIVE_RUNNING result triggers a MANDATORY arc-close-reconsideration "
    "ADR (project_m13_arc_disposition); the §4 saturation forensic is attribution "
    "input only and does NOT license an automatic re-run.",
    "semantic track (fork C / LAO) is NOT_EVALUATED here (scoping §8 2x2 "
    "inheritance); STRUCTURAL_READY_RUNNING is a structural floor, not a "
    "divergence-forward claim.",
    "GPU=0 (hard, design-final.md §6-b): fixed-unit embedding + CPU retrieval, no "
    "LLM/SGLang/embedding GPU path; gpu_hours=0.0.",
)


class _ArmCache:
    """Memoise the primary P-A arm pairs across the run's consumers.

    The ladder points, the running-ness gate, and the geometry forensic all
    reuse one generation per seed instead of regenerating three times.
    """

    def __init__(self) -> None:
        self._cache: dict[int, tuple[RunningArmResult, RunningArmResult]] = {}

    async def pair(self, seed: int) -> tuple[RunningArmResult, RunningArmResult]:
        if seed not in self._cache:
            arm_a = await generate_running_arm(seed, "A", "P-A")
            arm_b = await generate_running_arm(seed, "B", "P-A")
            self._cache[seed] = (arm_a, arm_b)
        return self._cache[seed]

    async def builder(self, seed: int) -> tuple[Trace3D, Trace3D, Any, Any]:
        arm_a, arm_b = await self.pair(seed)
        start, terminal = draw_start_terminal(seed)
        return arm_a.trace, arm_b.trace, start, terminal

    def snapshot(self) -> dict[int, tuple[RunningArmResult, RunningArmResult]]:
        return dict(self._cache)


def _rung_dict(result: RungResult) -> dict[str, Any]:
    return {
        "rung": result.rung,
        "n_valid_seeds": result.n_valid_seeds,
        "median_estimand": result.median_estimand,
        "max_null": result.max_null,
        "ratio": result.ratio,
        "ci_lower": result.ci_lower,
        "ci_upper": result.ci_upper,
        "null_ok": result.null_ok,
        "control_ok": result.control_ok,
        "control_value": result.control_value,
        "delta_median": result.delta_median,
        "delta_ci_lower": result.delta_ci_lower,
        "prop_fixture_valid": result.prop_fixture_valid,
        "reasons": list(result.reasons),
    }


def _verdict_dict(verdict: RunningVerdict) -> dict[str, Any]:
    return {
        "structural_status_running": verdict.structural_status_running,
        "running_r_star": verdict.running_r_star,
        "frozen_r_star": verdict.frozen_r_star,
        "running_ness_tv_ci_lower": verdict.running_ness_tv_ci_lower,
        "running_ness_gate_pass": verdict.running_ness_gate_pass,
        "running_tv_indep_baseline": verdict.running_tv_indep_baseline,
        "running_tv_other_cloud_baseline": verdict.running_tv_other_cloud_baseline,
        "replay_checksum": verdict.replay_checksum,
        "replay_ok": verdict.replay_ok,
        "n_valid_seeds": verdict.n_valid_seeds,
        "d1_degenerate": verdict.d1_degenerate,
        "within_zone_geometry_present": verdict.within_zone_geometry_present,
        "topk_zone_saturated": verdict.topk_zone_saturated,
        "clamp_rate": verdict.clamp_rate,
        "per_zone_memory_count": dict(verdict.per_zone_memory_count),
        "per_zone_delta1_contribution": dict(verdict.per_zone_delta1_contribution),
        "prop_free_zone_delta1": verdict.prop_free_zone_delta1,
        "memoryless_r1_pass": verdict.memoryless_r1_pass,
        "memoryless_running_tv_ci_lower": verdict.memoryless_running_tv_ci_lower,
        "spontaneous_r1_pass": verdict.spontaneous_r1_pass,
        "spontaneous_median_delta1": verdict.spontaneous_median_delta1,
        "spontaneous_terminal_zone_memory_count": (
            verdict.spontaneous_terminal_zone_memory_count
        ),
        "no_reflect_r1_pass": verdict.no_reflect_r1_pass,
        "uniform_centroid_r1_pass": verdict.uniform_centroid_r1_pass,
        "top1_centroid_r1_pass": verdict.top1_centroid_r1_pass,
        "rung_states": dict(verdict.rung_states),
        "claim_scope": verdict.claim_scope,
        "reasons": list(verdict.reasons),
        "semantic_status": verdict.semantic_status,
        "gpu_hours": verdict.gpu_hours,
    }


async def _replay_ok(cache: _ArmCache, seed_bank: tuple[int, ...]) -> tuple[bool, str]:
    """Determinism check over the WHOLE seed bank (Codex MEDIUM-1).

    Regenerates every seed's **both** arms and compares a manifest hash over all
    replay checksums — not just seed 0 / arm A — so a non-determinism on any arm
    or tie/explore branch is caught. Returns ``(all_match, manifest_sha256)``.
    """
    ok = True
    manifest_parts: list[str] = []
    for seed in seed_bank:
        arm_a, arm_b = await cache.pair(seed)
        for arm_name, cached in (("A", arm_a), ("B", arm_b)):
            rerun = await generate_running_arm(seed, arm_name, "P-A")
            cached_sum = trace_checksum(cached.trace.rows)
            if cached_sum != trace_checksum(rerun.trace.rows):
                ok = False
            manifest_parts.append(f"{seed}:{arm_name}:{cached_sum}")
    manifest = hashlib.sha256("\n".join(manifest_parts).encode("utf-8")).hexdigest()
    return ok, manifest


async def _run() -> tuple[RunningVerdict, dict[RungName, RungResult]]:
    seed_bank = default_seed_bank()
    cache = _ArmCache()

    # Running R0/R1 via the frozen readout recipe on the P-A running builder.
    points: list[SeedPointR0R1] = [
        await r0_r1_seed_point_running(s, cache.builder) for s in seed_bank
    ]
    running_r0 = _r0_result_from_points(points, 0)
    running_r1 = _r1_result_from_points(points, 0)
    # R2/R3: on the frozen CHASHITSU-only fixture the prop-fixture gate returns
    # INCONCLUSIVE *without generating any trace*, so the frozen evaluate_r2/r3
    # never touch blind data here. The assert makes that reuse safe: if props
    # are ever added (a future milestone), this fails LOUDLY instead of silently
    # scoring running R2/R3 on blind stub traces (code-reviewer MEDIUM-5 / Codex
    # MEDIUM-2). A running R2/R3 builder is then required before removing it.
    running_r2 = await evaluate_r2(seed_bank)
    running_r3 = await evaluate_r3(seed_bank)
    assert not running_r2.prop_fixture_valid, (
        "prop fixture now valid — running R2/R3 must not reuse blind evaluate_r2/r3"
    )
    running_rungs: dict[RungName, RungResult] = {
        "R0": running_r0,
        "R1": running_r1,
        "R2": running_r2,
        "R3": running_r3,
    }
    max_d1 = max((p.d1 for p in points), default=0.0)

    # Frozen (blind) R* on the SAME apparatus (paired-contrast, design-final.md §4.3).
    smoke = run_smoke()
    blind_r0, blind_r1 = await evaluate_r0_and_r1(seed_bank)
    blind_rungs: dict[RungName, RungResult] = {
        "R0": blind_r0,
        "R1": blind_r1,
        "R2": running_r2,
        "R3": running_r3,
    }
    frozen_verdict = render_structural_verdict(blind_rungs, smoke)
    # Pass the blind R* through as Optional (Codex HIGH-2): a blind
    # INCONCLUSIVE / R0-fail yields ``r_star=None``, which must NOT be coerced to
    # "R0" or the paired contrast would be falsely corroborated.
    frozen_r_star: RungName | None = frozen_verdict.r_star

    runningness = await compute_runningness(seed_bank, "P-A", arm_provider=cache.pair)
    forensic = await compute_forensic(seed_bank, points, cache.snapshot())
    replay_ok, replay_checksum = await _replay_ok(cache, seed_bank)

    verdict = render_running_verdict(
        running_rungs,
        frozen_r_star=frozen_r_star,
        runningness=runningness,
        forensic=forensic,
        replay_checksum=replay_checksum,
        replay_ok=replay_ok,
        max_d1=max_d1,
    )
    return verdict, running_rungs


def _main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    verdict, running_rungs = asyncio.run(_run())

    report = {
        "verdict": _verdict_dict(verdict),
        "rungs": {rung: _rung_dict(result) for rung, result in running_rungs.items()},
        "caveats": list(_CAVEATS),
        "seed_bank_size": _c.B,
        "frozen_constants": {
            "RESIDUAL_JACCARD_FLOOR": _c.RESIDUAL_JACCARD_FLOOR,
            "LANDSCAPE_JACCARD_FLOOR": _c.LANDSCAPE_JACCARD_FLOOR,
            "STRUCTURAL_READY_MIN_RUNG": _c.STRUCTURAL_READY_MIN_RUNG,
            "MIN_VALID_SEEDS": _c.MIN_VALID_SEEDS,
            "K_RETRIEVE": _c.K_RETRIEVE,
            "M_MEMORIES": _c.M_MEMORIES,
        },
    }

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    _FORENSIC_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), "utf-8"
    )

    print(f"running structural verdict: {verdict.structural_status_running}")  # noqa: T201
    print(f"running R* = {verdict.running_r_star}, frozen R* = {verdict.frozen_r_star}")  # noqa: T201
    print(  # noqa: T201
        f"running-ness gate: pass={verdict.running_ness_gate_pass} "
        f"CI_lower(TV)={verdict.running_ness_tv_ci_lower:.4f}"
    )
    for reason in verdict.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(f"claim_scope: {verdict.claim_scope}")  # noqa: T201
    print(f"wrote {_FORENSIC_PATH}")  # noqa: T201


if __name__ == "__main__":
    _main()
