"""Run the M13-ES2 path-recombination replay verdict once (measurable estimand).

This is the **single** entry point that turns the blind preferential-return /
replay generator (:mod:`erre_sandbox.evidence.es2_replay.scenario`) into a
recorded GO / NO_GO / INCONCLUSIVE verdict. It re-tunes nothing: every threshold
lives in the frozen ``evidence.es2_replay.constants`` and the decision logic in
``verdict_report``; this script only drives the pre-registered seed bank through
them and writes the verdict + full forensic trail.

Scoring is the **measurable estimand** of the superseding ADR
(``.steering/20260628-es2-measurable-adr/``): the A/B de-novo directed-transition
distributions scored by Jensen-Shannon divergence (non-saturating), with a
self-calibrating gate (``CI_lower > 0`` + the relative split-half noise gate, no
absolute floor). The forensic trail records the **effective-support diagnostics**
(Codex H2) so an INCONCLUSIVE — if it recurs — can be read as a true low-power
result rather than a metric artifact, and the **superseded Jaccard contrast** so
the saturation that motivated the switch is visible in the same run.

Discipline (forking-paths guard, III-a / ES-1 style): run **once** with the
pre-registered ``default_seed_bank()``. Do not re-run with a tweaked generator to
flip the verdict; a different config requires a superseding ADR. The verdict is
deterministic, so a second run is only ever a byte-identical confirmation. An
INCONCLUSIVE is recorded as-is and **never tuned** into a pass.

Usage::

    uv run python scripts/es2_verdict_run.py
    # → prints the verdict + writes JSON to
    #   .steering/20260628-es2-measurable-adr/verdict-forensic.json
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.es2_replay.scenario import (
    VerdictRun,
    default_seed_bank,
    run_verdict,
)

_OUT_PATH: Final[Path] = Path(
    ".steering/20260628-es2-measurable-adr/verdict-forensic.json",
)

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final §0): a GO means ELIGIBLE TO PROCEED TO ES-3 "
    "(the recombination substrate generates de-novo, path-dependent novel seeds "
    "above the matched N-a null), NOT the full hypothesis (LLM-level de-novo "
    "cognitive divergence). The hippocampal-replay analogy is a design warrant, "
    "not direct causal evidence.",
    "NO_GO is a PROGRESSIVE finding (recombination alone is insufficient → ES-3 / "
    "richer primitive), not a refutation. INCONCLUSIVE (low power / invalid "
    "apparatus / noisy null) is kept distinct from NO_GO.",
    "claim stratification (Codex M1): on GO, the N-b within-agent pairing "
    "sensitivity stratifies the claim — N-b CI lower > 0 ⇒ ordered "
    "content-location pairing path-dependence; N-b CI lower <= 0 ⇒ home-range / "
    "path-label path-dependence only. Do not over-claim ordered pairing on N-a alone.",
    "non-circularity: the replay kernel is verdict-blind (no temporal order, A/B "
    "label, or novelty term); crossover is rejected; the temporal-replay control "
    "must fail novelty (apparatus-validity floor); the null is content-stratified; "
    "the comparison key is canonical; the bootstrap unit is the scenario seed.",
    "measurable estimand (superseding ADR .steering/20260628-es2-measurable-adr/): "
    "D_obs is the Jensen-Shannon divergence over the de-novo directed-transition "
    "distributions (support M^2-M=2256 << ~12288 transitions/arm, so the estimator "
    "is CONSISTENT — D_self shrinks with sample size instead of saturating at 1). "
    "The gate is self-calibrating (CI_lower>0 + median(D_obs)>1.5*median(D_self); "
    "FLOOR_REL=0.0, no absolute JS floor). Non-saturation makes discrimination "
    "POSSIBLE, not guaranteed: an INCONCLUSIVE can still recur if the A/B "
    "difference does not exceed split-half noise — read the effective-support "
    "diagnostics to tell a true low-power result from a metric artifact. The "
    "forensic fields (TV, R-2 co-occurrence, R-3 unigram, novel-only JS, the "
    "superseded Jaccard contrast, effective support) are NON-PROMOTING (Codex M3).",
)


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _effective_support_summary(run: VerdictRun) -> dict[str, float]:
    """Median effective-support diagnostics across seeds (Codex H2, forensic)."""
    return {
        "median_d_obs_jaccard": _median([s.d_obs_jaccard for s in run.seeds]),
        "median_tv_obs": _median([s.tv_obs for s in run.seeds]),
        "median_novel_only_js": _median([s.novel_only_js for s in run.seeds]),
        "median_cooccur_js": _median([s.cooccur_js for s in run.seeds]),
        "median_unigram_js": _median([s.unigram_js for s in run.seeds]),
        "median_eff_support": _median(
            [s.eff_support_a for s in run.seeds] + [s.eff_support_b for s in run.seeds]
        ),
        "median_hill1": _median(
            [s.hill1_a for s in run.seeds] + [s.hill1_b for s in run.seeds]
        ),
        "median_nonzero": _median(
            [float(s.nonzero_a) for s in run.seeds]
            + [float(s.nonzero_b) for s in run.seeds]
        ),
        "median_coverage": _median(
            [s.coverage_a for s in run.seeds] + [s.coverage_b for s in run.seeds]
        ),
        "median_temporal_nonzero": _median(
            [float(s.temporal_nonzero) for s in run.seeds]
        ),
    }


def _forensic_dict(run: VerdictRun) -> dict[str, Any]:
    v = run.verdict
    return {
        "verdict": v.verdict,
        "estimand": "transition_distribution_among_de_novo_eligible_seeds",
        "divergence": "jensen_shannon_base2",
        "caveats": list(_CAVEATS),
        "reasons": list(v.reasons),
        "n_valid_seeds": v.n_valid_seeds,
        "median_d_obs": v.median_d_obs,
        "median_novel_transition_rate": v.median_novel_transition_rate,
        "median_exact_de_novo_rate": v.median_exact_de_novo_rate,
        "median_temporal_novel_rate": v.median_temporal_novel_rate,
        "ci_lower": v.ci_lower,
        "ci_upper": v.ci_upper,
        "n_b_ci_lower": v.n_b_ci_lower,
        "n_b_ci_upper": v.n_b_ci_upper,
        "min_denovo_seeds": v.min_denovo_seeds,
        "min_effective_zones": v.min_effective_zones,
        "median_d_self": v.median_d_self,
        "median_no_spurious_margin": v.median_no_spurious_margin,
        "var_cosine": v.var_cosine,
        "effective_support_summary": _effective_support_summary(run),
        "seeds": [
            {
                "seed": s.seed,
                "start_zone": s.start_zone.value,
                "effective_zones_a": s.effective_zones_a,
                "effective_zones_b": s.effective_zones_b,
                "d_obs": s.d_obs,
                "null_q_a": s.null_q_a,
                "delta_a": s.delta_a,
                "null_q_b": s.null_q_b,
                "delta_b": s.delta_b,
                "novel_transition_rate": s.novel_transition_rate,
                "exact_de_novo_rate": s.exact_de_novo_rate,
                "temporal_novel_rate": s.temporal_novel_rate,
                "n_denovo_a": s.n_denovo_a,
                "n_denovo_b": s.n_denovo_b,
                "d_self": s.d_self,
                "no_spurious_margin": s.no_spurious_margin,
                "var_cosine": s.var_cosine,
                "d_obs_jaccard": s.d_obs_jaccard,
                "tv_obs": s.tv_obs,
                "novel_only_js": s.novel_only_js,
                "cooccur_js": s.cooccur_js,
                "unigram_js": s.unigram_js,
                "eff_support_a": s.eff_support_a,
                "eff_support_b": s.eff_support_b,
                "hill1_a": s.hill1_a,
                "hill1_b": s.hill1_b,
                "nonzero_a": s.nonzero_a,
                "nonzero_b": s.nonzero_b,
                "coverage_a": s.coverage_a,
                "coverage_b": s.coverage_b,
                "temporal_nonzero": s.temporal_nonzero,
                "trajectory_a": [z.value for z in s.trajectory_a],
                "trajectory_b": [z.value for z in s.trajectory_b],
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
    print(f"ES-2 verdict: {v.verdict}")  # noqa: T201
    for reason in v.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(  # noqa: T201
        f"median(D_obs)={v.median_d_obs:.4f} "
        f"median(novel)={v.median_novel_transition_rate:.4f} "
        f"median(temporal)={v.median_temporal_novel_rate:.4f} "
        f"N-a CI=[{v.ci_lower:.4f}, {v.ci_upper:.4f}] "
        f"N-b CI=[{v.n_b_ci_lower:.4f}, {v.n_b_ci_upper:.4f}] "
        f"median(D_self)={v.median_d_self:.4f} "
        f"no_spurious={v.median_no_spurious_margin:.4f} "
        f"var_cosine={v.var_cosine:.4f} "
        f"min_denovo={v.min_denovo_seeds} min_zones={v.min_effective_zones}",
    )
    ess = _effective_support_summary(run)
    print(  # noqa: T201
        f"forensic: jaccard_contrast={ess['median_d_obs_jaccard']:.4f} "
        f"TV={ess['median_tv_obs']:.4f} eff_support={ess['median_eff_support']:.1f} "
        f"nonzero={ess['median_nonzero']:.0f}/{2256} "
        f"coverage={ess['median_coverage']:.3f} "
        f"novel_only_JS={ess['median_novel_only_js']:.4f}",
    )


if __name__ == "__main__":
    _main()
