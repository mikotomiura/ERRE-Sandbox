"""Run the M13-ES1 SPDM definitive verdict once over the blind scenario generator.

This is the **single** entry point that turns the blind movement-model generator
(:mod:`erre_sandbox.evidence.spdm.scenario`) into a recorded GO / NO_GO /
INCONCLUSIVE verdict. It re-tunes nothing: every threshold lives in the frozen
``evidence.spdm.constants`` and the decision logic in ``verdict_report``; this
script only drives the pre-registered seed bank through them and prints the
result plus the full forensic trail (per-seed start/terminal zones, divergences,
cosine distribution, rank-weighted overlap, cutoff margin).

Discipline (forking-paths guard, III-a style): run **once** with the
pre-registered ``default_seed_bank()``. Do not re-run with a tweaked generator to
flip the verdict; a different generator config requires a superseding ADR. The
verdict is reproducible (deterministic), so a second run is only ever a
byte-identical confirmation.

Usage::

    uv run python scripts/spdm_verdict_run.py
    # → prints the verdict + forensic JSON to stdout; writes the JSON to
    #   .steering/20260624-m13-es1-spdm/verdict-forensic.json
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.spdm.scenario import (
    VerdictRun,
    default_seed_bank,
    run_verdict,
)

_OUT_PATH: Final[Path] = Path(
    ".steering/20260624-m13-es1-spdm/verdict-forensic.json",
)


_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary: this is a NECESSARY-SUBSTRATE CONFORMANCE diagnostic, not a "
    "matched-null path-dependence test. ① collapses to 0 (apparatus-validity floor) "
    "so the verdict reads D_obs against the absolute practical floor, not a "
    "permutation null; the matched-null path-dependence test is ES-2's job "
    "(Codex HIGH-1, accepted). GO = the spatial binding reliably wires movement "
    "history into the retrieval landscape (eligible for ES-2), NOT a sub-claim proof.",
    "HIGH-2: under the fixed-unit embedding (cosine held constant to isolate the "
    "spatial term) every battery query embeds identically, so the EFFECTIVE "
    "independent query count is 1; the formal Q_BATTERY_MIN gate is satisfied but "
    "all statistical power rests on the N_SEED seed bank (MIN_VALID_SEEDS), not the "
    "query battery.",
    "MEDIUM-1: the terminal zone is blind-drawn per seed and independent of the "
    "path; the per-seed start_zone / terminal_zone are recorded below so any "
    "terminal-dependent variance is auditable.",
    "MEDIUM-3: ranking inside an equal-proximity group falls to the recency "
    "tie-break; per-seed cutoff_margin is recorded so seeds with a razor-thin top-k "
    "boundary are interpretable.",
)


def _forensic_dict(run: VerdictRun) -> dict[str, Any]:
    v = run.verdict
    return {
        "verdict": v.verdict,
        "caveats": list(_CAVEATS),
        "effective_query_count": 1,
        "reasons": list(v.reasons),
        "n_valid_seeds": v.n_valid_seeds,
        "n_queries": v.n_queries,
        "median_d_obs": run.median_d_obs,
        "iqr_d_obs": run.iqr_d_obs,
        "max_verdict_null": v.max_verdict_null,
        "ratio": v.ratio,
        "ci_lower": v.ci_lower,
        "ci_upper": v.ci_upper,
        "obs_spread_iqr": v.obs_spread,
        "null_spread_iqr": v.null_spread,
        "positive_control_ratio": v.positive_control_ratio,
        "no_spurious_margin": v.no_spurious_margin,
        "w0_floor_median": v.w0_floor_median,
        "gate1": {
            "passed": run.gate1.passed,
            "ratio": run.gate1.ratio,
            "zone_free_ratio": run.gate1.zone_free_ratio,
            "ablation_collapsed": run.gate1.ablation_collapsed,
        },
        "seeds": [
            {
                "seed": s.seed,
                "start_zone": s.start_zone.value,
                "terminal_zone": s.terminal_zone.value,
                "d_obs": s.d_obs,
                "d_null_permutation": s.d_null_permutation,
                "d_null_w0": s.d_null_w0,
                "d_control_same_loc_on": s.d_control_same_loc_on,
                "d_control_same_loc_off": s.d_control_same_loc_off,
                "rank_weighted_overlap": s.rank_weighted_overlap,
                "cutoff_margin": s.cutoff_margin,
                "cosine": dataclasses.asdict(s.cosine),
            }
            for s in run.seeds
        ],
    }


async def _main() -> None:
    seed_bank = default_seed_bank()
    run = await run_verdict(seed_bank)
    report = _forensic_dict(run)

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")

    print(f"SPDM verdict: {run.verdict.verdict}")  # noqa: T201
    for reason in run.verdict.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(  # noqa: T201
        f"median(D_obs)={run.median_d_obs:.4f} IQR(D_obs)={run.iqr_d_obs:.4f} "
        f"max_verdict_null={run.verdict.max_verdict_null:.4f} "
        f"ratio={run.verdict.ratio:.3f} "
        f"CI=[{run.verdict.ci_lower:.4f}, {run.verdict.ci_upper:.4f}]",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_main())
