"""Run the M13-ES3 locomotion → sampling conformance verdict once.

This is the **single** entry point that turns the blind walk generator
(:mod:`erre_sandbox.evidence.es3_locomotion.scenario`) into a recorded
GO / NO_GO / INCONCLUSIVE verdict. It re-tunes nothing: every threshold lives in
the frozen ``evidence.es3_locomotion.constants`` and the decision logic in
``verdict_report``; this script only drives the pre-registered seed bank through
them and writes the verdict + the full forensic trail.

The estimand is the **headroom-normalised within-cell amplitude** ``D_loco`` over
the nested reduced model ``E ~ C(p, z)`` (ADR §2), with the per-walk-seed
bootstrap CI as the verdict statistic (``CI_lower(D_loco) ≥ AMP_FLOOR`` → GO). The
forensic trail records the **zone-function control** (must collapse to 0), the
**ablation bit-equality**, the **N_hist sensitivity** diagnostics, and the
per-cell headroom / λ-spread breakdown so an INCONCLUSIVE — if it occurs — can be
read as a *true* structural absence vs an apparatus limit (the ES-2 effective-
support discipline), never tuned into a pass.

Discipline (forking-paths guard, ES-1 / ES-2 style): run **once** with the
pre-registered ``default_seed_bank()``. Do not re-run with a tweaked generator /
gain / floor to flip the verdict; a different config requires a superseding ADR.
The verdict is deterministic, so a second run is only ever a byte-identical
confirmation.

Usage::

    uv run python scripts/es3_verdict_run.py
    # → prints the verdict + writes JSON to
    #   .steering/20260629-m13-es3-impl/verdict-forensic.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Final

from erre_sandbox.evidence.es3_locomotion.constants import AMP_FLOOR
from erre_sandbox.evidence.es3_locomotion.controls import run_controls
from erre_sandbox.evidence.es3_locomotion.decomposition import Decomposition, decompose
from erre_sandbox.evidence.es3_locomotion.scenario import (
    build_observations,
    default_seed_bank,
)
from erre_sandbox.evidence.es3_locomotion.verdict_report import (
    Es3Verdict,
    evaluate_verdict,
)

_OUT_PATH: Final[Path] = Path(
    ".steering/20260629-m13-es3-impl/verdict-forensic.json",
)

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final §0/§8): a GO means ELIGIBLE TO PROCEED TO ES-4 "
    "/ divergence measurement (the locomotion->sampling channel is wired: causal, "
    "separated from the location/zone channel, ablation-identity), NOT a test of "
    "walking -> creative divergence itself (that needs LLM power, deferred). "
    "Oppezzo 2014 is a design warrant, not direct causal evidence.",
    "NO_GO is a PROGRESSIVE finding (the channel cannot convert sufficient "
    "headroom into effective modulation -> channel re-design), not a refutation. "
    "INCONCLUSIVE (invalid apparatus / no within-cell lambda spread / headroom "
    "saturation / too few valid walk-seeds) is kept distinct from NO_GO.",
    "non-tautology: the zone-function positive control forces lambda=h(z) and the "
    "forensic field zone_function_d_loco must collapse to ~0 (<= ZERO_TOL) -- the "
    "estimand CAN read 0, so a non-zero D_loco on the blind walk is a real "
    "within-cell locomotion signal, not a constructive guarantee (v1 rejected for "
    "exactly this; v2 estimand adopted).",
    "estimand (ADR §2, Codex HIGH-1/HIGH-2): D_loco is the cell-equal-weighted "
    "median over headroom-valid cells of a_s = std_within(E_full)/H_s, where the "
    "reduced model E~C(p,z) absorbs the persona + static-zone-mode (location) "
    "contribution so the residual is the WITHIN-zone locomotion signal. The "
    "bootstrap unit is the per-walk-seed aggregate D_loco^(b) (the EMA "
    "autocorrelation forbids a step-row bootstrap, HIGH-4).",
    "frozen constants (design-final §5, user-ratified pre-registration): "
    "B=64 T=200 ALPHA=0.3 LOCO_GAIN_T=0.3 LOCO_GAIN_P=0.1 HEADROOM_MIN=0.3 "
    "LOCO_SPREAD_MIN=0.0025 MIN_CELLS=8 MIN_CELL_N=30 HEADROOM_VALID_FRAC=0.5 "
    "MIN_WALK_SEEDS=32 AMP_FLOOR=0.02 CI_ALPHA=0.10 N_RESAMPLES=10000. Tuning any "
    "of these to flip the verdict is a forking-paths violation; record as-is.",
    "secondary (M3): top_p is headroom-gated (base top_p ~0.8-0.9 clamps fast), so "
    "median_top_p_amplitude over top_p-headroom-valid cells is FORENSIC ONLY and "
    "does not drive the verdict (temperature is the primary divergence coordinate).",
)


def _cell_rows(decomp: Decomposition) -> list[dict[str, Any]]:
    return [
        {
            "persona_id": c.persona_id,
            "zone": c.zone.value,
            "n": c.n,
            "e_abl": c.e_abl,
            "headroom": c.headroom,
            "headroom_valid": c.headroom_valid,
            "lam_var": c.lam_var,
            "spread_valid": c.spread_valid,
            "n_valid": c.n_valid,
            "e_full_std": c.e_full_std,
            "amplitude": c.amplitude,
            "measurement_valid": c.measurement_valid,
            "repeat_penalty_var": c.repeat_penalty_var,
            "top_p_headroom": c.top_p_headroom,
        }
        for c in decomp.cells
    ]


def _forensic_dict(verdict: Es3Verdict, decomp: Decomposition) -> dict[str, Any]:
    return {
        "verdict": verdict.verdict,
        "estimand": "headroom_normalised_within_cell_amplitude_D_loco",
        "reduced_model": "E ~ C(persona, zone)",
        "caveats": list(_CAVEATS),
        "reasons": list(verdict.reasons),
        "d_loco": verdict.d_loco,
        "ci_lower": verdict.ci_lower,
        "ci_upper": verdict.ci_upper,
        "amp_floor": AMP_FLOOR,
        "n_cells": verdict.n_cells,
        "n_headroom_valid": verdict.n_headroom_valid,
        "headroom_valid_fraction": verdict.headroom_valid_fraction,
        "n_n_valid": verdict.n_n_valid,
        "n_spread_valid": verdict.n_spread_valid,
        "n_measurement_valid": verdict.n_measurement_valid,
        "n_valid_walk_seeds": verdict.n_valid_walk_seeds,
        "max_repeat_penalty_var": verdict.max_repeat_penalty_var,
        "ablation_bit_equal": verdict.ablation_bit_equal,
        "ablation_max_abs_diff": verdict.ablation_max_abs_diff,
        "zone_function_d_loco": verdict.zone_function_d_loco,
        "n_hist_history_shuffle_d_loco": verdict.n_hist_history_shuffle_d_loco,
        "n_hist_lambda_shuffle_d_loco": verdict.n_hist_lambda_shuffle_d_loco,
        "n_top_p_headroom_valid": verdict.n_top_p_headroom_valid,
        "median_top_p_amplitude": verdict.median_top_p_amplitude,
        "per_seed_d_loco": list(decomp.per_seed_d_loco),
        "cells": _cell_rows(decomp),
    }


def _main() -> None:
    # The frozen reasons / caveats carry non-ASCII (≥, ∧, λ); make stdout UTF-8 so
    # the print does not crash on a cp932 (Windows) console.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    seed_bank = default_seed_bank()
    decomp = decompose(build_observations(seed_bank))
    controls = run_controls(seed_bank)
    verdict = evaluate_verdict(decomp, controls)
    report = _forensic_dict(verdict, decomp)

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")

    print(f"ES-3 verdict: {verdict.verdict}")  # noqa: T201
    for reason in verdict.reasons:
        print(f"  - {reason}")  # noqa: T201
    print(  # noqa: T201
        f"D_loco={verdict.d_loco:.4f} "
        f"CI=[{verdict.ci_lower:.4f}, {verdict.ci_upper:.4f}] "
        f"valid_cells={verdict.n_measurement_valid}/{verdict.n_cells} "
        f"valid_walk_seeds={verdict.n_valid_walk_seeds} "
        f"headroom_frac={verdict.headroom_valid_fraction:.3f}",
    )
    print(  # noqa: T201
        f"controls: ablation_bit_equal={verdict.ablation_bit_equal} "
        f"(max|Δ|={verdict.ablation_max_abs_diff:.2e}) "
        f"zone_function_D_loco={verdict.zone_function_d_loco:.2e} "
        f"repeat_penalty_var={verdict.max_repeat_penalty_var:.2e}",
    )
    print(  # noqa: T201
        f"forensic: N_hist(hist_shuffle)={verdict.n_hist_history_shuffle_d_loco:.4f} "
        f"N_hist(lam_shuffle)={verdict.n_hist_lambda_shuffle_d_loco:.4f} "
        f"top_p_amp={verdict.median_top_p_amplitude:.4f} "
        f"(valid {verdict.n_top_p_headroom_valid} cells)",
    )


if __name__ == "__main__":
    _main()
