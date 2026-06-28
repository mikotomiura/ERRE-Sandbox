"""Run the M13-ES2 path-recombination replay verdict once over the blind scenario.

This is the **single** entry point that turns the blind preferential-return /
replay generator (:mod:`erre_sandbox.evidence.es2_replay.scenario`) into a
recorded GO / NO_GO / INCONCLUSIVE verdict. It re-tunes nothing: every threshold
lives in the frozen ``evidence.es2_replay.constants`` and the decision logic in
``verdict_report``; this script only drives the pre-registered seed bank through
them and writes the verdict + full forensic trail.

Discipline (forking-paths guard, III-a / ES-1 style): run **once** with the
pre-registered ``default_seed_bank()``. Do not re-run with a tweaked generator to
flip the verdict; a different generator config requires a superseding ADR. The
verdict is deterministic, so a second run is only ever a byte-identical
confirmation.

Usage::

    uv run python scripts/es2_verdict_run.py
    # → prints the verdict + writes JSON to
    #   .steering/20260628-m13-es2-replay/verdict-forensic.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.es2_replay.scenario import (
    VerdictRun,
    default_seed_bank,
    run_verdict,
)

_OUT_PATH: Final[Path] = Path(
    ".steering/20260628-m13-es2-replay/verdict-forensic.json",
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
)


def _forensic_dict(run: VerdictRun) -> dict[str, Any]:
    v = run.verdict
    return {
        "verdict": v.verdict,
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


if __name__ == "__main__":
    _main()
