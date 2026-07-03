"""Run the memory-recomposition seam channel-conformance verdict once.

This is the **single** entry point that turns the blind formation / idle-replay /
post-idle-walk generator
(:mod:`erre_sandbox.evidence.memory_recomp_conformance.scenario`) into a recorded
GO / NO_GO / INCONCLUSIVE verdict. It re-tunes nothing: every threshold lives in
the frozen ``memory_recomp_conformance.constants`` and the decision logic in
``verdict_report``; this script only drives the pre-registered seed bank through
them and writes the verdict + full forensic trail.

The estimand (design-final.md §2, ``.steering/20260702-m13-sub1-memseam-adr/``): the
channel ``C`` (idle-recomposition argmax transition cell → ``target_zone``) biases
an independent post-idle occupancy walk ``D``; the per-seed scale-free entropy
reduction ``conform_s`` is tested against the exact C↔D pairing-destroying null and
aggregated as ``delta_s`` with a bootstrap CI (GO ⇔ ``CI_lower > 0``).

Discipline (forking-paths guard, D0-pack / ES-2 style): run **once** with the
pre-registered ``default_seed_bank()``. Do not re-run with a tweaked generator to
flip the verdict; a different config requires a superseding ADR. The verdict is
deterministic, so a second run is only ever a byte-identical confirmation. An
INCONCLUSIVE / NO_GO is recorded as-is and **never tuned** into a GO.

Usage::

    uv run python scripts/memory_recomp_conformance_verdict_run.py
    # → prints the verdict + writes JSON to
    #   .steering/20260703-m13-sub1-memseam-impl/verdict-forensic.json
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.memory_recomp_conformance.scenario import (
    VerdictRun,
    default_seed_bank,
    run_verdict,
)
from erre_sandbox.evidence.memory_recomp_conformance.verdict_report import (
    compute_deltas,
)

_OUT_PATH: Final[Path] = Path(
    ".steering/20260703-m13-sub1-memseam-impl/verdict-forensic.json",
)

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final §4): a GO means the memory-recomposition state "
    "gives an independent downstream discrete choice a NON-CIRCULAR causal bias "
    "(necessary-substrate type, identical to ES-1 / ES-3), NOT proof of H4 "
    "(embodiment produces divergence). live_agent_connected=False; the walks are "
    "synthetic (claim_scope=synthetic_post_idle_walk_only).",
    "NO_GO is a PROGRESSIVE finding (this C→D pairing does not couple → a different "
    "pairing needs a fresh pre-register with the §6 4-part guard), not a refutation. "
    "INCONCLUSIVE (few valid seeds / ill-posed or degenerate channel / underpowered "
    "synthetic-power gate / cost-ceiling abort) is kept distinct from NO_GO.",
    "non-circularity (design-final §5): D's visit_count never reads C's replay-walk "
    "state; the sole C→D path is the scalar target_zone bonus (reusing POLYA_ALPHA, "
    "no new free effect parameter). The independence pin test asserts a different C "
    "trace with the same target_zone leaves D byte-identical.",
    "the C↔D pairing-destroying null is computed EXACTLY over the Z=5 target_zone "
    "population (the N_PERM→∞ limit the design noted as identical, §4-4), so it is "
    "deterministic. The synthetic power gate is a synthetic-data-only feasibility "
    "check (a maximally informative channel injected at 1.0×POLYA_ALPHA must reach "
    "≥0.80 CI_lower>0 recovery); it never reads this verdict.",
    "estimand class TRANSITION (design-final §1): output-diversity (ES-2, which "
    "ended INCONCLUSIVE at low power) → channel-conformance (ES-1/ES-3 type). The "
    "ES-2 same-estimand-class re-run is forbidden (disposition ADR §4-1).",
)


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _forensic_dict(run: VerdictRun) -> dict[str, Any]:
    v = run.verdict
    valid = [s for s in run.seeds if s.valid]
    deltas = compute_deltas(valid)
    delta_by_seed = dict(zip([s.seed for s in valid], deltas, strict=True))
    return {
        "recomposition_channel_status": v.recomposition_channel_status,
        "estimand": "channel_conformance_entropy_reduction_vs_pairing_null",
        "claim_scope": v.claim_scope,
        "live_agent_connected": v.live_agent_connected,
        "coupling_strength_used": v.coupling_strength_used,
        "caveats": list(_CAVEATS),
        "reasons": list(v.reasons),
        "n_valid_seeds": v.n_valid_seeds,
        "median_conform_delta": v.median_conform,
        "ci_lower": v.ci_lower,
        "ci_upper": v.ci_upper,
        "median_argmax_stability": v.median_argmax_stability,
        "median_channel_effective_support": v.median_channel_effective_support,
        "synthetic_power_pass_rate": v.synthetic_power_pass_rate,
        "synthetic_power_curve": {
            str(k): val for k, val in run.synthetic_power_curve.items()
        },
        "seeds": [
            {
                "seed": s.seed,
                "valid": s.valid,
                "start_zone": s.start_zone,
                "target_zone": s.target_zone,
                "conform_row": list(s.conform_row),
                "conform_at_target": s.conform_row[s.target_zone],
                "delta": delta_by_seed.get(s.seed),
                "argmax_stability": s.argmax_stability,
                "channel_effective_support": s.channel_effective_support,
            }
            for s in run.seeds
        ],
    }


def _main() -> None:
    seed_bank = default_seed_bank()
    run = run_verdict(seed_bank)
    report = _forensic_dict(run)

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")

    v = run.verdict
    print(f"memory-recomp seam verdict: {v.recomposition_channel_status}")  # noqa: T201
    for reason in v.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(  # noqa: T201
        f"n_valid={v.n_valid_seeds} "
        f"median(delta)={v.median_conform:.4f} "
        f"CI=[{v.ci_lower:.4f}, {v.ci_upper:.4f}] "
        f"median(argmax_stability)={v.median_argmax_stability:.4f} "
        f"median(eff_support)={v.median_channel_effective_support:.2f} "
        f"synthetic_power@1.0={v.synthetic_power_pass_rate:.4f} "
        f"coupling={v.coupling_strength_used}",
    )
    print(  # noqa: T201
        "synthetic power curve: "
        + " ".join(f"{k}={val:.3f}" for k, val in run.synthetic_power_curve.items()),
    )


if __name__ == "__main__":
    _main()
