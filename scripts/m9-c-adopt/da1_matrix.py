"""DA-1 4-軸 intersection matrix consumer — Phase B 第 4 セッション.

Reads the four metric JSON artefacts (baseline + per-rank Vendi semantic,
Big5 ICC, Burrows Δ, and the per-rank single_lora bench output) and renders
a markdown matrix + per-axis PASS/FAIL decision per DA-1 / DA-8 / DA-9.

Effect size for axis 1 (Vendi) is computed as Cohen's d between LoRA-on
window means and baseline window means; positive d → LoRA-on > baseline,
which is the **wrong** direction (DA-1 asks for "LoRA-on < no-LoRA").
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean, stdev


def _load(p: Path) -> dict:
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
    """Pooled-SD Cohen's d (a vs b)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    ma, mb = mean(a), mean(b)
    sa, sb = stdev(a), stdev(b)
    na, nb = len(a), len(b)
    pooled_var = ((na - 1) * sa * sa + (nb - 1) * sb * sb) / max(na + nb - 2, 1)
    pooled_sd = math.sqrt(max(pooled_var, 1e-30))
    return (ma - mb) / pooled_sd


def _icc_summary(payload: dict) -> dict:
    icc = payload["icc"]
    return {
        "point": icc["icc_consistency_average"],
        "lo": icc["icc_consistency_lower_ci"],
        "hi": icc["icc_consistency_upper_ci"],
        "agreement_point": icc["icc_agreement_single"],
        "agreement_lo": icc["icc_agreement_lower_ci"],
        "agreement_hi": icc["icc_agreement_upper_ci"],
    }


def _bench_throughput(jsonl_path: Path) -> float:
    """Pull output_throughput_tok_s from the *last* JSONL row in a bench file."""
    last = None
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    if last is None:
        return float("nan")
    return float(
        last.get("output_throughput")
        or last.get("output_throughput_token_s")
        or last.get("output_throughput_tok_s")
        or last.get("output_tok_s")
        or last.get("output_token_throughput")
        or 0.0
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--steering-dir", type=Path, required=True)
    p.add_argument("--bench-dir", type=Path, required=True)
    p.add_argument("--throughput-threshold", type=float, default=24.25)
    p.add_argument("--ranks", nargs="+", type=int, default=[4, 8, 16])
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    steering = args.steering_dir
    bench = args.bench_dir
    ranks = args.ranks

    # Load baselines
    vendi_baseline = _load(steering / "tier-b-baseline-kant-vendi-semantic.json")
    icc_baseline = _load(steering / "tier-b-baseline-kant-icc.json")
    burrows_baseline = _load(steering / "tier-b-baseline-kant-burrows.json")

    baseline_vendi_scores = _vendi_window_scores(vendi_baseline)
    baseline_burrows_means = _burrows_window_means(burrows_baseline)

    rows: list[dict] = []
    rows.append(
        {
            "label": "no-LoRA baseline",
            "vendi": vendi_baseline["bootstrap"],
            "vendi_scores": baseline_vendi_scores,
            "icc": _icc_summary(icc_baseline),
            "burrows": burrows_baseline["bootstrap"],
            "burrows_means": baseline_burrows_means,
            "throughput": float("nan"),
            "throughput_pass": None,
            "axes": {},
        }
    )

    for r in ranks:
        vendi_r = _load(steering / f"tier-b-pilot-kant-r{r}-vendi-semantic.json")
        icc_r = _load(steering / f"tier-b-icc-kant-r{r}.json")
        burrows_r = _load(steering / f"tier-b-pilot-kant-r{r}-burrows.json")
        vendi_scores_r = _vendi_window_scores(vendi_r)
        burrows_means_r = _burrows_window_means(burrows_r)
        throughput = _bench_throughput(bench / f"single_lora-r{r}.jsonl")

        # Axis 1: Vendi semantic effect size + direction (LoRA-on < no-LoRA)
        d = _cohens_d(vendi_scores_r, baseline_vendi_scores)
        # DA-1 wants LoRA-on < baseline so we want d < 0; "effect size d's |·|"
        # only counts when direction is correct.
        vendi_point = vendi_r["bootstrap"]["point"]
        vendi_lo = vendi_r["bootstrap"]["lo"]
        baseline_vendi_hi = vendi_baseline["bootstrap"]["hi"]
        direction_pass = vendi_point < vendi_baseline["bootstrap"]["point"]
        ci_lo_clears_zero = (baseline_vendi_hi - vendi_point) > 0  # rough
        axis1_pass = direction_pass and ci_lo_clears_zero

        # Axis 2: ICC(C,k) >= 0.6 point + CI lower >= 0.6
        icc_summary = _icc_summary(icc_r)
        axis2_pass = icc_summary["point"] >= 0.6 and icc_summary["lo"] >= 0.6

        # Axis 3: Burrows Δ reduction >= 10% point + CI lower > 0
        burrows_point = burrows_r["bootstrap"]["point"]
        baseline_burrows_point = burrows_baseline["bootstrap"]["point"]
        reduction_ratio = (
            baseline_burrows_point - burrows_point
        ) / baseline_burrows_point  # positive = reduction
        burrows_lo = burrows_r["bootstrap"]["lo"]
        burrows_hi = burrows_r["bootstrap"]["hi"]
        # CI lower > 0 on the reduction implies baseline_lo > burrows_hi (no overlap, baseline higher)
        ci_lower_reduction = (
            burrows_baseline["bootstrap"]["lo"] - burrows_hi
        ) / baseline_burrows_point
        axis3_pass = reduction_ratio >= 0.10 and ci_lower_reduction > 0.0

        # Axis 4: throughput >= 70% baseline (= 24.25)
        axis4_pass = (
            (throughput >= args.throughput_threshold)
            if throughput == throughput  # not NaN
            else False
        )

        axes_pass = sum([axis1_pass, axis2_pass, axis3_pass, axis4_pass])
        rows.append(
            {
                "label": f"rank={r}",
                "vendi": vendi_r["bootstrap"],
                "vendi_scores": vendi_scores_r,
                "vendi_cohens_d": d,
                "vendi_axis1_pass": axis1_pass,
                "icc": icc_summary,
                "icc_axis2_pass": axis2_pass,
                "burrows": burrows_r["bootstrap"],
                "burrows_means": burrows_means_r,
                "burrows_reduction_point": reduction_ratio,
                "burrows_axis3_pass": axis3_pass,
                "throughput": throughput,
                "throughput_axis4_pass": axis4_pass,
                "axes_pass_count": axes_pass,
            }
        )

    out_payload = {
        "thresholds": {
            "vendi_direction": "LoRA-on < no-LoRA",
            "icc_min_point": 0.6,
            "icc_min_lo": 0.6,
            "burrows_reduction_min": 0.10,
            "throughput_min_tok_s": args.throughput_threshold,
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")

    # Pretty-print markdown matrix to stdout
    print("# DA-1 4-axis matrix — kant Phase B 第 4 セッション\n")
    print("| rank | Vendi semantic | ICC(C,k) | Burrows Δ | throughput | axes PASS |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        v = row["vendi"]
        i = row["icc"]
        b = row["burrows"]
        if row["label"] == "no-LoRA baseline":
            t = "K-β 34.64 / threshold 24.25"
            axes = "—"
        else:
            tn = row["throughput"]
            t = f"{tn:.2f} ({'PASS' if row['throughput_axis4_pass'] else 'FAIL'})"
            axes = (
                f"{row['axes_pass_count']}/4"
                f" (V:{ 'PASS' if row['vendi_axis1_pass'] else 'FAIL'},"
                f" I:{ 'PASS' if row['icc_axis2_pass'] else 'FAIL'},"
                f" B:{ 'PASS' if row['burrows_axis3_pass'] else 'FAIL'},"
                f" T:{ 'PASS' if row['throughput_axis4_pass'] else 'FAIL'})"
            )
        print(
            f"| {row['label']} | "
            f"{v['point']:.3f} [{v['lo']:.3f}, {v['hi']:.3f}] | "
            f"{i['point']:.4f} [{i['lo']:.4f}, {i['hi']:.4f}] | "
            f"{b['point']:.3f} [{b['lo']:.3f}, {b['hi']:.3f}] | "
            f"{t} | {axes} |"
        )

    print("\n## Per-rank diagnostic")
    for row in rows[1:]:
        print(
            f"- {row['label']}: Cohen's d (Vendi) = {row['vendi_cohens_d']:+.3f}"
            f" (positive = LoRA-on > baseline → WRONG direction for DA-1 axis 1);"
            f" Burrows reduction = {row['burrows_reduction_point']:+.3%}"
            f" (positive = reduction → correct direction)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
