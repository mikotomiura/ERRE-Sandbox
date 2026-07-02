"""Run the M13-SUB1 D0 pack structural-track verdict once.

This is the **single** entry point that turns the D0a blind generator
(:mod:`erre_sandbox.evidence.d0_substrate.stub`) + the R0-R3 ladder
(:mod:`erre_sandbox.evidence.d0_substrate.ladder`) + the D0b-runtime veto
smoke (:mod:`erre_sandbox.evidence.d0_substrate.smoke`) into a recorded
``structural_status`` / ``R*`` verdict
(:mod:`erre_sandbox.evidence.d0_substrate.verdict_report`). It re-tunes
nothing: every threshold lives in the frozen ``evidence.d0_substrate.
constants`` and the decision logic in ``verdict_report``; this script only
drives the pre-registered seed bank through them and writes the verdict +
the full forensic trail + the cross-machine handoff artifact
(design-final.md §6).

Discipline (forking-paths guard, ES-1/ES-3/ES-4 style): run **once** with the
pre-registered :func:`~erre_sandbox.evidence.d0_substrate.stub.default_seed_bank`.
Do not re-run with a tweaked generator/gain/floor to flip the verdict; a
different config requires a superseding ADR. The apparatus is deterministic,
so a second run is only ever a byte-identical confirmation.

Usage::

    uv run python scripts/d0_structural_verdict_run.py
    # -> prints the verdict + writes JSON to
    #    .steering/20260702-m13-sub1-d0-structural/verdict-forensic.json
    #    .steering/20260702-m13-sub1-d0-structural/handoff.json
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
    evaluate_r0_and_r1,
    evaluate_r2,
    evaluate_r3,
)
from erre_sandbox.evidence.d0_substrate.smoke import (
    D0B_SEED,
    D0B_TICK_HZ,
    SmokeResult,
    run_smoke,
)
from erre_sandbox.evidence.d0_substrate.stub import (
    build_trace,
    default_seed_bank,
)
from erre_sandbox.evidence.d0_substrate.verdict_report import render_structural_verdict
from erre_sandbox.schemas import Zone

_OUT_DIR: Final[Path] = Path(".steering/20260702-m13-sub1-d0-structural")
_FORENSIC_PATH: Final[Path] = _OUT_DIR / "verdict-forensic.json"
_HANDOFF_PATH: Final[Path] = _OUT_DIR / "handoff.json"
_SAMPLE_REPLAY_DIR: Final[Path] = _OUT_DIR / "sample_replay"

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final.md §6, over-claim guard): STRUCTURAL_READY means "
    "substrate wiring + measurement capability were demonstrated non-circularly "
    "(necessary-substrate + measurement-capability, ES-1/ES-3 style) -- G-GEAR "
    "runtime-ready, NOT Godot render-ready, and NOT a test of the divergence "
    "hypothesis. ES-1/ES-3 supply target/wiring only; their own GO verdicts are "
    "never re-cited here as divergence evidence.",
    "semantic track (fork C / LAO) is OUT OF SCOPE for this run (corpus "
    "materialization gate unresolved, .steering/20260702-m13-sub1-d0-structural/"
    "requirement.md). The 2x2 stop rule's semantic axis is NO_VALID_SCORER "
    "UNEVALUATED here, not a NO_VALID_SCORER finding -- divergence-forward claims "
    "require a separate semantic-track run first.",
    "R2/R3 honest default prediction (DA-D0S-1, .steering/20260702-m13-sub1-d0-"
    "structural/decisions.md): the current world.zones.ZONE_PROPS fixture is "
    "CHASHITSU-only (1 prop-bearing zone) < MIN_PROP_ZONES=2, so R2 (and, by "
    "contiguity, R3) is expected to report INCONCLUSIVE without this being tuned "
    "around -- props are never added, floors never lowered, to force R2/R3 to "
    "evaluate.",
    "anti-ES-1-collapse gate (design-final.md §2 #5, the most load-bearing gate "
    "in this apparatus): R1+ requires the seed-paired residual Delta_r = D_r - "
    "D_r^quantized to clear RESIDUAL_JACCARD_FLOOR with CI_lower(Delta_r) > 0, so "
    "R1 cannot PASS by silently re-measuring ES-1's own discrete-zone substrate.",
    "frozen constants (design-final.md §5 + DA-D0S-1 defer-constant freeze, "
    ".steering/20260702-m13-sub1-d0-structural/decisions.md): "
    f"LANDSCAPE_JACCARD_FLOOR={_c.LANDSCAPE_JACCARD_FLOOR} "
    f"RESIDUAL_JACCARD_FLOOR={_c.RESIDUAL_JACCARD_FLOOR} "
    f"CLOSURE_AMP_FLOOR={_c.CLOSURE_AMP_FLOOR} R_MIN={_c.R_MIN} "
    f"ZERO_TOL={_c.ZERO_TOL} CI_ALPHA={_c.CI_ALPHA} N_RESAMPLES={_c.N_RESAMPLES} "
    f"B={_c.B} MIN_VALID_SEEDS={_c.MIN_VALID_SEEDS} "
    f"CONE_APERTURE_DEG={_c.CONE_APERTURE_DEG} CONE_RANGE_M={_c.CONE_RANGE_M} "
    f"PROP_FIXTURE_MIN={_c.PROP_FIXTURE_MIN} MIN_PROP_ZONES={_c.MIN_PROP_ZONES}. "
    "Tuning any of these to flip the verdict is a forking-paths violation; "
    "record as-is.",
    "D0b-runtime veto (design-final.md §3, Codex MEDIUM-4): STRUCTURAL_READY via "
    "this smoke is G-GEAR runtime-ready, not Godot render-ready (D0b-render / "
    "cross-machine coupling deferred). AgentUpdateMsg gets a schema-only "
    "round-trip (cognition-side emission in production); Position/MoveMsg/"
    "ZoneTransitionEvent get a real runtime round-trip.",
)


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


def _smoke_dict(smoke: SmokeResult) -> dict[str, Any]:
    return {
        "passed": smoke.passed,
        "monotone_gap_free": smoke.monotone_gap_free,
        "affordance_order_deterministic": smoke.affordance_order_deterministic,
        "position_round_trip_ok": smoke.position_round_trip_ok,
        "move_msg_round_trip_ok": smoke.move_msg_round_trip_ok,
        "zone_transition_round_trip_ok": smoke.zone_transition_round_trip_ok,
        "agent_update_schema_round_trip_ok": (smoke.agent_update_schema_round_trip_ok),
        "n_ticks": smoke.n_ticks,
        "n_zone_transitions": smoke.n_zone_transitions,
        "n_affordance_events": smoke.n_affordance_events,
        "reasons": list(smoke.reasons),
    }


async def _run_ladder(seed_bank: tuple[int, ...]) -> dict[RungName, RungResult]:
    # evaluate_r0_and_r1 shares one trace-generation/retrieval pass across
    # both rungs (TASK-POST HIGH fix, code-reviewer: evaluate_r0 + evaluate_r1
    # independently doubled the 64-seed cost for identical SeedPointR0R1 data).
    r0, r1 = await evaluate_r0_and_r1(seed_bank)
    r2 = await evaluate_r2(seed_bank)
    r3 = await evaluate_r3(seed_bank)
    return {"R0": r0, "R1": r1, "R2": r2, "R3": r3}


def _not_computed_rung(rung: RungName, reason: str) -> RungResult:
    """Placeholder for a rung the D0b-runtime veto prevented from computing.

    design-final.md §3: a failed smoke must downgrade the verdict to
    ``INCONCLUSIVE_STRUCTURAL`` *without trusting the ladder estimand* — the
    ladder must not even be computed on a smoke failure (TASK-POST MEDIUM
    fix, Codex: the runner previously computed the full ladder before
    checking the smoke result).
    """
    return RungResult(
        rung=rung,
        n_valid_seeds=0,
        median_estimand=0.0,
        max_null=0.0,
        ratio=0.0,
        ci_lower=0.0,
        ci_upper=0.0,
        null_ok=False,
        control_ok=False,
        control_value=0.0,
        prop_fixture_valid=False,
        reasons=(reason,),
    )


def _write_handoff(seed_bank: tuple[int, ...]) -> None:
    """Cross-machine handoff artifact contract (design-final.md §6)."""
    _SAMPLE_REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    sample_seed = seed_bank[0]
    trace = build_trace(sample_seed, "A", Zone.PERIPATOS)
    sample_rows = [
        {
            "tick_index": r.tick_index,
            "seed": r.seed,
            "zone": r.zone.value,
            "x": r.x,
            "y": r.y,
            "z": r.z,
            "yaw": r.yaw,
            "pitch": r.pitch,
            "action_id": r.action_id,
            "affordance_ids": list(r.affordance_ids),
        }
        for r in trace.rows
    ]
    sample_path = _SAMPLE_REPLAY_DIR / f"seed-{sample_seed}-arm-A.json"
    sample_blob = json.dumps(sample_rows, indent=2, sort_keys=True, ensure_ascii=False)
    sample_path.write_text(sample_blob, "utf-8")
    sample_sha256 = hashlib.sha256(sample_blob.encode("utf-8")).hexdigest()

    handoff = {
        "trace_row_schema": [
            "tick_index:int",
            "seed:int",
            "zone:str",
            "x:float",
            "y:float",
            "z:float",
            "yaw:float",
            "pitch:float",
            "action_id:int",
            "affordance_ids:list[str]",
        ],
        "schema_version": "d0-structural-v1",
        "godot_version_pin": "4.6",
        "coordinate_convention": {
            "handedness": "right-handed",
            "up_axis": "y",
            "ground_plane": "xz",
            "origin": "PERIPATOS centroid",
            "units": "metres",
            "world_size_m": _c.WORLD_SIZE_M,
            "zone_tie_break": "Zone enum declaration order (world.zones.locate_zone)",
        },
        "tick_rate_hz": D0B_TICK_HZ,
        "seed_bank": list(seed_bank),
        "d0b_smoke_seed": D0B_SEED,
        "determinism_checklist": [
            "RNG substreams named f'd0-seed-{seed}-{arm}-{stream}' "
            "(random.Random, never the global RNG)",
            "no wall-clock in the generation path (SmokeClock is a fixed-dt "
            "counter, not time.monotonic())",
            "replay-checksum re-run byte-identical "
            "(erre_sandbox.evidence.d0_substrate.stub.trace_checksum)",
            "single-machine-only determinism caveat: true cross-machine "
            "(G-GEAR<->MacBook) Godot float/physics determinism is NOT "
            "established by this run (design-final.md §7 risk 2)",
        ],
        "sample_replay": {
            "path": sample_path.relative_to(_OUT_DIR).as_posix(),
            "seed": sample_seed,
            "arm": "A",
            "sha256": sample_sha256,
            "replay_checksum": trace.replay_checksum,
        },
    }
    _HANDOFF_PATH.write_text(
        json.dumps(handoff, indent=2, sort_keys=True, ensure_ascii=False), "utf-8"
    )


def _main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    seed_bank = default_seed_bank()

    # D0b-runtime veto FIRST (design-final.md §3): a failed smoke must
    # prevent the ladder estimand from being computed at all, not merely be
    # ignored after the fact (TASK-POST MEDIUM fix, Codex).
    smoke = run_smoke()
    if smoke.passed:
        rung_results = asyncio.run(_run_ladder(seed_bank))
    else:
        rung_results = {
            rung: _not_computed_rung(
                rung, "D0b-runtime veto smoke failed; ladder not computed"
            )
            for rung in ("R0", "R1", "R2", "R3")
        }
    verdict = render_structural_verdict(rung_results, smoke)

    report = {
        "structural_status": verdict.structural_status,
        "r_star": verdict.r_star,
        "claim_boundary": verdict.claim_boundary,
        "reasons": list(verdict.reasons),
        "caveats": list(_CAVEATS),
        "rungs": {rv.rung: _rung_dict(rv.result) for rv in verdict.rung_verdicts},
        "rung_states": {rv.rung: rv.state for rv in verdict.rung_verdicts},
        "rung_reasons": {rv.rung: list(rv.reasons) for rv in verdict.rung_verdicts},
        "smoke": _smoke_dict(smoke),
        "semantic_track": (
            "NOT_EVALUATED (out of scope; corpus materialization gate unresolved)"
        ),
    }

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    _FORENSIC_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), "utf-8"
    )
    _write_handoff(seed_bank)

    print(f"D0 structural verdict: {verdict.structural_status}")  # noqa: T201
    print(f"R* = {verdict.r_star}")  # noqa: T201
    for rv in verdict.rung_verdicts:
        print(  # noqa: T201
            f"  {rv.rung}: {rv.state} "
            f"(median={rv.result.median_estimand:.4f} "
            f"null={rv.result.max_null:.4f} ratio={rv.result.ratio:.3f} "
            f"ci_lower={rv.result.ci_lower:.4f} "
            f"delta_median={rv.result.delta_median} "
            f"delta_ci_lower={rv.result.delta_ci_lower})",
        )
        for reason in rv.reasons:
            print(f"    - {reason}")  # noqa: T201
    print(f"D0b-runtime smoke: passed={smoke.passed}")  # noqa: T201
    for reason in smoke.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(f"wrote {_FORENSIC_PATH}")  # noqa: T201
    print(f"wrote {_HANDOFF_PATH}")  # noqa: T201


if __name__ == "__main__":
    _main()
