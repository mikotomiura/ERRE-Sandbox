r"""DA-1 4-軸 matrix renderer - m9-c-adopt-pilot-multiturn investigation.

Aggregates pre-registered scenario evaluation (DA-13, decisions.md D-1 HIGH-3
reflection) by comparing:

* historical baseline (Ollama no-LoRA, multi-turn metadata, PR #165 artefact)
* single-turn pilot LoRA-on (PR #165 artefact)
* multi-turn pilot LoRA-on (本 PR、3 rank)
* multi-turn pilot no-LoRA SGLang control (本 PR、HIGH-1)
* matched baseline (historical baseline downsampled to pilot's per-shard focal
  count via consumer ``--max-focal-per-shard``、HIGH-2)

The primary scenario evaluation compares the LoRA-on pilot against the
**no-LoRA SGLang control** (DA-14 authoritative baseline). The matched
historical Ollama baseline is retained in the rendered table as a
cross-pipeline reference only — DA-14 verdict gating used the no-LoRA SGLang
arm, and DA-15 keeps that as the comparator so the scenario verdict is
apples-to-apples with the rest of the m9-c-adopt evidence chain.

Outputs ``da1-matrix-multiturn-kant.json`` + a markdown table to stdout, and
runs the pre-registered scenario thresholds against the primary rank (rank=8)
to print Scenario I / II / III / IV verdict.

Usage::

    python scripts/m9-c-adopt/da1_matrix_multiturn.py \\
        --steering-historical .steering/20260513-m9-c-adopt \\
        --steering-investigation .steering/20260514-m9-c-adopt-pilot-multiturn \\
        --output .steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean, stdev


def _load(p: Path) -> dict | None:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _vendi_window_scores(payload: dict) -> list[float]:
    return [float(w["vendi_score"]) for w in payload["per_window"]]


def _burrows_window_means(payload: dict) -> list[float]:
    return [
        float(w["mean_burrows"])
        for w in payload["per_window"]
        if w["mean_burrows"] is not None
    ]


def _cohens_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    ma, mb = mean(a), mean(b)
    sa, sb = stdev(a), stdev(b)
    na, nb = len(a), len(b)
    pooled_var = ((na - 1) * sa * sa + (nb - 1) * sb * sb) / max(na + nb - 2, 1)
    pooled_sd = math.sqrt(max(pooled_var, 1e-30))
    return (ma - mb) / pooled_sd


def _bootstrap_diff_ci(
    a: list[float], b: list[float], *, n_resamples: int = 2000, seed: int = 0
) -> tuple[float, float, float]:
    """Bootstrap CI for the mean difference (a - b).

    Returns (point, lo, hi) at 95% CI. Uses paired-style resampling within each
    cluster.
    """
    import random

    rng = random.Random(seed)
    if not a or not b:
        return (float("nan"), float("nan"), float("nan"))
    point = mean(a) - mean(b)
    diffs = []
    for _ in range(n_resamples):
        ra = [a[rng.randrange(len(a))] for _ in range(len(a))]
        rb = [b[rng.randrange(len(b))] for _ in range(len(b))]
        diffs.append(mean(ra) - mean(rb))
    diffs.sort()
    lo = diffs[int(0.025 * n_resamples)]
    hi = diffs[int(0.975 * n_resamples)]
    return (point, lo, hi)


def _icc_summary(payload: dict | None) -> dict:
    if payload is None:
        return {
            "point": None,
            "lo": None,
            "hi": None,
            "agreement_point": None,
            "agreement_lo": None,
            "agreement_hi": None,
        }
    icc = payload["icc"]
    return {
        "point": icc.get("icc_consistency_average"),
        "lo": icc.get("icc_consistency_lower_ci"),
        "hi": icc.get("icc_consistency_upper_ci"),
        "agreement_point": icc.get("icc_agreement_single"),
        "agreement_lo": icc.get("icc_agreement_lower_ci"),
        "agreement_hi": icc.get("icc_agreement_upper_ci"),
    }


def _row(
    label: str, vendi: dict | None, burrows: dict | None, icc: dict | None
) -> dict:
    return {
        "label": label,
        "vendi": vendi["bootstrap"] if vendi else None,
        "vendi_window_scores": _vendi_window_scores(vendi) if vendi else [],
        "burrows": burrows["bootstrap"] if burrows else None,
        "burrows_window_means": _burrows_window_means(burrows) if burrows else [],
        "icc": _icc_summary(icc),
    }


def _scenario_verdict(
    *,
    primary_vendi_diff: tuple[float, float, float],
    primary_vendi_d: float,
    primary_burrows_reduction_point: float,
    primary_burrows_reduction_lo: float,
    sister_ranks_aligned: int,
) -> tuple[str, str]:
    """Apply pre-registered DA-13 thresholds to derive the scenario verdict.

    * Scenario I: Vendi Δ < 0 with CI upper < 0, Cohen's d < -0.5, Burrows
      reduction > 5% with CI lower > 0, AND >= 1 sister rank in same direction
      (Vendi + Burrows both axes).
    * Scenario II: Vendi point still > matched baseline OR CI spans 0; Burrows
      reduction <= 0 OR CI spans 0.
    * Scenario III: Vendi or Burrows reverses but not both, OR thresholds
      partially cleared, OR rank-mixed direction.
    * Scenario IV: pre-collection fail check / over-wide CIs (handled
      out-of-band).
    """
    vendi_point, _vendi_lo, vendi_hi = primary_vendi_diff
    vendi_reverses = vendi_point < 0 and vendi_hi < 0 and primary_vendi_d < -0.5
    burrows_reverses = (
        primary_burrows_reduction_point > 0.05 and primary_burrows_reduction_lo > 0
    )
    if vendi_reverses and burrows_reverses and sister_ranks_aligned >= 1:
        return ("I", "Reversal confirmed across Vendi + Burrows + sister rank")
    if not vendi_reverses and not burrows_reverses:
        return ("II", "No reversal — LoRA failure remains the live hypothesis")
    return (
        "III",
        f"Mixed: vendi_reverses={vendi_reverses} burrows_reverses={burrows_reverses}"
        f" sister_aligned={sister_ranks_aligned}",
    )


def main() -> int:  # noqa: PLR0915
    p = argparse.ArgumentParser()
    p.add_argument("--steering-historical", type=Path, required=True)
    p.add_argument("--steering-investigation", type=Path, required=True)
    p.add_argument("--ranks", nargs="+", type=int, default=[4, 8, 16])
    p.add_argument("--primary-rank", type=int, default=8)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    sh = args.steering_historical
    si = args.steering_investigation
    ranks = args.ranks

    # === Historical baseline (Ollama, multi-turn metadata) ===
    hist_vendi = _load(sh / "tier-b-baseline-kant-vendi-semantic.json")
    hist_burrows = _load(sh / "tier-b-baseline-kant-burrows.json")
    hist_icc = _load(sh / "tier-b-baseline-kant-icc.json")

    # === Matched baseline (historical, downsampled via --max-focal-per-shard) ===
    matched_vendi = _load(si / "tier-b-baseline-matched-kant-vendi-semantic.json")
    matched_burrows = _load(si / "tier-b-baseline-matched-kant-burrows.json")

    # === Single-turn pilot (PR #165) ===
    single_pilot_vendi: dict[int, dict | None] = {}
    single_pilot_burrows: dict[int, dict | None] = {}
    single_pilot_icc: dict[int, dict | None] = {}
    for r in ranks:
        single_pilot_vendi[r] = _load(
            sh / f"tier-b-pilot-kant-r{r}-vendi-semantic.json"
        )
        single_pilot_burrows[r] = _load(sh / f"tier-b-pilot-kant-r{r}-burrows.json")
        single_pilot_icc[r] = _load(sh / f"tier-b-icc-kant-r{r}.json")

    # === Multi-turn pilot LoRA-on (本 PR) ===
    mt_vendi: dict[int, dict | None] = {}
    mt_burrows: dict[int, dict | None] = {}
    mt_icc: dict[int, dict | None] = {}
    for r in ranks:
        mt_vendi[r] = _load(
            si / f"tier-b-pilot-multiturn-kant-r{r}-vendi-semantic.json"
        )
        mt_burrows[r] = _load(si / f"tier-b-pilot-multiturn-kant-r{r}-burrows.json")
        mt_icc[r] = _load(si / f"tier-b-icc-multiturn-kant-r{r}.json")

    # === No-LoRA SGLang control (本 PR、HIGH-1) ===
    nolora_vendi = _load(si / "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json")
    nolora_burrows = _load(si / "tier-b-pilot-multiturn-kant-nolora-burrows.json")
    nolora_icc = _load(si / "tier-b-icc-multiturn-kant-nolora.json")

    # === Build rows ===
    rows: list[dict] = [
        _row(
            "historical baseline (Ollama, multi-turn metadata)",
            hist_vendi,
            hist_burrows,
            hist_icc,
        ),
        _row(
            "matched baseline (historical, downsampled)",
            matched_vendi,
            matched_burrows,
            hist_icc,
        ),
        _row(
            "no-LoRA SGLang control (multi-turn protocol)",
            nolora_vendi,
            nolora_burrows,
            nolora_icc,
        ),
    ]
    for r in ranks:
        rows.append(
            _row(
                f"single-turn pilot LoRA r={r} (PR #165)",
                single_pilot_vendi[r],
                single_pilot_burrows[r],
                single_pilot_icc[r],
            )
        )
    for r in ranks:
        rows.append(
            _row(
                f"multi-turn pilot LoRA r={r} (本 PR)",
                mt_vendi[r],
                mt_burrows[r],
                mt_icc[r],
            )
        )

    # === Compute primary scenario evaluation ===
    pr = args.primary_rank
    primary_mt = mt_vendi.get(pr)
    primary_mt_burrows = mt_burrows.get(pr)
    # DA-14 authoritative comparator: no-LoRA SGLang control of the same
    # multi-turn protocol. The matched historical Ollama baseline is kept as
    # a cross-pipeline reference (rendered table) but does not gate the
    # scenario verdict. Fall back to the matched historical baseline only
    # when the no-LoRA SGLang arm is missing (older artefact directories).
    matched_baseline_for_compare = nolora_vendi or matched_vendi or hist_vendi
    matched_burrows_for_compare = nolora_burrows or matched_burrows or hist_burrows
    comparator_label = (
        "no-LoRA SGLang (DA-14 authoritative)"
        if nolora_vendi
        else "matched historical Ollama (DA-11 fallback)"
    )

    scenario_verdict_payload: dict = {
        "primary_rank": pr,
        "scenario": "PENDING",
        "rationale": "",
    }
    if (
        primary_mt
        and matched_baseline_for_compare
        and primary_mt_burrows
        and matched_burrows_for_compare
    ):
        a_vendi = _vendi_window_scores(primary_mt)
        b_vendi = _vendi_window_scores(matched_baseline_for_compare)
        vendi_diff = _bootstrap_diff_ci(a_vendi, b_vendi)
        vendi_d = _cohens_d(a_vendi, b_vendi)
        baseline_burrows_point = matched_burrows_for_compare["bootstrap"]["point"]
        primary_burrows_point = primary_mt_burrows["bootstrap"]["point"]
        burrows_reduction_point = (
            baseline_burrows_point - primary_burrows_point
        ) / baseline_burrows_point
        # CI lower for reduction = (baseline_lo - mt_hi) / baseline_point
        burrows_lo = (
            matched_burrows_for_compare["bootstrap"]["lo"]
            - primary_mt_burrows["bootstrap"]["hi"]
        ) / baseline_burrows_point
        # Sister ranks check: how many of {ranks} \ {primary} also reverse
        sister_aligned = 0
        for r in ranks:
            if r == pr:
                continue
            if not mt_vendi.get(r) or not mt_burrows.get(r):
                continue
            sa_v = _vendi_window_scores(mt_vendi[r])
            sister_diff = _bootstrap_diff_ci(sa_v, b_vendi)
            sister_burrows_red = (
                baseline_burrows_point - mt_burrows[r]["bootstrap"]["point"]
            ) / baseline_burrows_point
            if sister_diff[0] < 0 and sister_diff[2] < 0 and sister_burrows_red > 0.05:
                sister_aligned += 1
        verdict, rationale = _scenario_verdict(
            primary_vendi_diff=vendi_diff,
            primary_vendi_d=vendi_d,
            primary_burrows_reduction_point=burrows_reduction_point,
            primary_burrows_reduction_lo=burrows_lo,
            sister_ranks_aligned=sister_aligned,
        )
        scenario_verdict_payload = {
            "primary_rank": pr,
            "scenario": verdict,
            "rationale": rationale,
            "comparator": comparator_label,
            "primary_vendi_diff_point": vendi_diff[0],
            "primary_vendi_diff_lo": vendi_diff[1],
            "primary_vendi_diff_hi": vendi_diff[2],
            "primary_vendi_cohens_d": vendi_d,
            "primary_burrows_reduction_point": burrows_reduction_point,
            "primary_burrows_reduction_lo": burrows_lo,
            "sister_ranks_aligned": sister_aligned,
        }

    out_payload = {
        "preregistered_thresholds": {
            "scenario_I": {
                "vendi_diff_point_lt": 0,
                "vendi_diff_ci_upper_lt": 0,
                "vendi_cohens_d_lt": -0.5,
                "burrows_reduction_point_gt": 0.05,
                "burrows_reduction_ci_lower_gt": 0,
                "sister_ranks_aligned_min": 1,
            },
            "scenario_II": {
                "any_of": [
                    "vendi_point >= matched baseline",
                    "vendi CI spans 0",
                    "burrows reduction <= 0",
                    "burrows reduction CI spans 0",
                ],
            },
        },
        "verdict": scenario_verdict_payload,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")

    print("# DA-1 4-axis matrix - m9-c-adopt-pilot-multiturn investigation\n")
    print("| condition | Vendi semantic | ICC(C,k) | Burrows |")
    print("|---|---|---|---|")
    for row in rows:
        v = row["vendi"]
        b = row["burrows"]
        i = row["icc"]
        v_str = f"{v['point']:.3f} [{v['lo']:.3f}, {v['hi']:.3f}]" if v else "—"
        b_str = f"{b['point']:.3f} [{b['lo']:.3f}, {b['hi']:.3f}]" if b else "—"
        i_str = (
            f"{i['point']:.4f} [{i['lo']:.4f}, {i['hi']:.4f}]"
            if i["point"] is not None
            else "—"
        )
        print(f"| {row['label']} | {v_str} | {i_str} | {b_str} |")

    print("\n## Pre-registered scenario verdict (DA-13)\n")
    print(json.dumps(scenario_verdict_payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
