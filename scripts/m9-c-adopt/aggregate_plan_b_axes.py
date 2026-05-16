r"""m9-c-adopt Plan B — aggregate per-condition Burrows / throughput axes
into the JSON format consumed by ``da14_verdict_plan_b.py``.

Reads:

* Burrows: two per-condition Burrows JSONs produced by
  ``compute_burrows_delta.py`` (LoRA-on and no-LoRA Plan B shards).
* ICC: a single ``compute_big5_icc.py`` JSON for the LoRA-on shards
  (kant_r8v3 adapter, SGLang). Falls through to ``v2_point`` field for
  the verdict aggregator.
* Throughput: derives `throughput_pct_of_baseline` from the per-shard
  metadata stored in each DuckDB shard (focal_per_s rate). LoRA-on
  rate / no-LoRA rate × 100.

Writes 3 separate JSONs in the format expected by ``da14_verdict_plan_b.
py``:

* ``--out-burrows``: ``{"reduction_pct": float, "ci_lower": float,
  "ci_upper": float, "v2_mean": float, "no_lora_mean": float}``
* ``--out-icc``: ``{"v2_point": float}``
* ``--out-throughput``: ``{"throughput_pct_of_baseline": float}``

Usage::

    python scripts/m9-c-adopt/aggregate_plan_b_axes.py \
        --burrows-v2 .steering/.../tier-b-plan-b-kant-r8v3-burrows.json \
        --burrows-nolora .steering/.../tier-b-plan-b-kant-planb-nolora-burrows.json \
        --icc-v2 .steering/.../tier-b-plan-b-kant-r8v3-icc.json \
        --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb \
                    data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb \
        --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
                        data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
        --out-burrows .steering/.../da14-burrows-plan-b-kant.json \
        --out-icc .steering/.../da14-icc-plan-b-kant.json \
        --out-throughput .steering/.../da14-throughput-plan-b-kant.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import numpy as np


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _window_means(payload: dict[str, Any]) -> list[float]:
    """Extract per-window mean_burrows (skipping None) from a
    compute_burrows_delta.py output."""
    return [
        float(w["mean_burrows"])
        for w in payload.get("per_window", [])
        if w.get("mean_burrows") is not None
    ]


def _shard_focal_rate_from_log(log_path: Path, run_tag: str) -> float | None:
    """Parse final 'pilot done ... elapsed=X.X min completed=N' line for a
    given run tag (e.g. ``r8 run=0`` or ``nolora run=0``).

    Returns rate in focal/s, or None if the line is not yet present."""
    if not log_path.exists():
        return None
    rate: float | None = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if "pilot done" in line and run_tag in line:
            # Format: ... completed=N elapsed=X.X min ...
            try:
                completed_part = line.split("completed=")[1].split()[0]
                elapsed_part = line.split("elapsed=")[1].split()[0]
                completed = int(completed_part)
                elapsed_min = float(elapsed_part)
                rate = completed / (elapsed_min * 60.0)
            except (IndexError, ValueError):
                continue
    return rate


def _bootstrap_diff_pct_ci(
    v2: list[float],
    nolora: list[float],
    *,
    seed: int,
    n_resamples: int,
) -> tuple[float, float, float]:
    """Bootstrap CI for reduction%: (nolora_mean - v2_mean) / nolora_mean × 100.

    Returns (point_pct, ci_lo_pct, ci_hi_pct).
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(v2, dtype=float)
    b = np.asarray(nolora, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan"), float("nan")
    point = (float(b.mean()) - float(a.mean())) / float(b.mean()) * 100.0
    diffs: list[float] = []
    for _ in range(n_resamples):
        ra = rng.choice(a, size=a.size, replace=True)
        rb = rng.choice(b, size=b.size, replace=True)
        rm = float(rb.mean())
        if rm == 0:
            continue
        diffs.append((rm - float(ra.mean())) / rm * 100.0)
    if not diffs:
        return point, float("nan"), float("nan")
    diffs.sort()
    n = len(diffs)
    return point, diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-aggregate-plan-b-axes")
    p.add_argument("--burrows-v2", required=True, type=Path)
    p.add_argument("--burrows-nolora", required=True, type=Path)
    p.add_argument("--icc-v2", required=True, type=Path)
    p.add_argument(
        "--icc-point-key",
        default="icc_agreement_single",
        help=(
            "Field name (inside the 'icc' block of the compute_big5_icc.py"
            " output, or top-level) holding the ICC(A,1) point estimate."
            " Default matches McGraw-Wong 'icc_agreement_single'."
        ),
    )
    p.add_argument("--v2-shards", nargs="+", required=True, type=Path)
    p.add_argument("--nolora-shards", nargs="+", required=True, type=Path)
    p.add_argument(
        "--eval-log",
        type=Path,
        required=True,
        help="Path to eval-sequence.log (used to derive per-run focal/s).",
    )
    p.add_argument("--out-burrows", required=True, type=Path)
    p.add_argument("--out-icc", required=True, type=Path)
    p.add_argument("--out-throughput", required=True, type=Path)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-resamples", type=int, default=2000)
    args = p.parse_args(argv)

    # ---- Burrows axis ----
    v2_payload = _load_json(args.burrows_v2)
    nolora_payload = _load_json(args.burrows_nolora)
    v2_means = _window_means(v2_payload)
    nolora_means = _window_means(nolora_payload)
    point, lo, hi = _bootstrap_diff_pct_ci(
        v2_means, nolora_means, seed=args.seed, n_resamples=args.n_resamples,
    )
    burrows_out = {
        "v2_mean": float(mean(v2_means)) if v2_means else None,
        "v2_stdev": float(stdev(v2_means)) if len(v2_means) > 1 else None,
        "no_lora_mean": float(mean(nolora_means)) if nolora_means else None,
        "no_lora_stdev": float(stdev(nolora_means)) if len(nolora_means) > 1 else None,
        "reduction_pct": point,
        "ci_lower": lo,
        "ci_upper": hi,
        "n_windows_v2": len(v2_means),
        "n_windows_nolora": len(nolora_means),
        "threshold_pct": 5.0,
        "note": (
            "reduction% = (no_lora_mean - v2_mean) / no_lora_mean × 100."
            " CI via 2000-iteration window-level bootstrap. DA-14 gate:"
            " reduction_pct >= 5 AND ci_lower > 0."
        ),
    }
    args.out_burrows.parent.mkdir(parents=True, exist_ok=True)
    args.out_burrows.write_text(
        json.dumps(burrows_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # ---- ICC axis (single-condition, kernel-independent) ----
    icc_payload = _load_json(args.icc_v2)
    # compute_big5_icc.py output has icc.icc_agreement_single (= ICC(A,1))
    icc_block = icc_payload.get("icc", {})
    icc_point = (
        icc_block.get(args.icc_point_key)
        or icc_block.get("icc_agreement_single")
        or icc_payload.get(args.icc_point_key)
        or icc_payload.get("v2_point")
        or icc_payload.get("point")
    )
    icc_out = {
        "v2_point": float(icc_point) if icc_point is not None else None,
        "icc_source_path": str(args.icc_v2),
        "icc_field_used": args.icc_point_key,
        "threshold": 0.55,
        "note": (
            "ICC(A,1) absolute-agreement Big-5 ICC. DA-14 gate: point ≥"
            " 0.55. Kernel-independent (computed via SGLang T=0.7 inference"
            " on focal utterances)."
        ),
    }
    args.out_icc.parent.mkdir(parents=True, exist_ok=True)
    args.out_icc.write_text(
        json.dumps(icc_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # ---- Throughput axis ----
    # LoRA-on rates come from "pilot done persona=kant tag=r8 run=N ..."
    # no-LoRA rates come from "pilot done persona=kant tag=nolora run=N ..."
    v2_rates = [
        _shard_focal_rate_from_log(args.eval_log, f"tag=r8 run={i}")
        for i in range(len(args.v2_shards))
    ]
    nolora_rates = [
        _shard_focal_rate_from_log(args.eval_log, f"tag=nolora run={i}")
        for i in range(len(args.nolora_shards))
    ]
    v2_valid = [r for r in v2_rates if r is not None]
    nolora_valid = [r for r in nolora_rates if r is not None]
    v2_rate = float(mean(v2_valid)) if v2_valid else float("nan")
    nolora_rate = float(mean(nolora_valid)) if nolora_valid else float("nan")
    if nolora_rate and nolora_rate != 0 and nolora_rate == nolora_rate:
        throughput_pct = v2_rate / nolora_rate * 100.0
    else:
        throughput_pct = float("nan")
    throughput_out = {
        "v2_focal_per_s": v2_rate,
        "no_lora_focal_per_s": nolora_rate,
        "throughput_pct_of_baseline": throughput_pct,
        "v2_rates_per_shard": v2_rates,
        "no_lora_rates_per_shard": nolora_rates,
        "threshold_pct": 70.0,
        "note": (
            "throughput_pct_of_baseline = v2 mean rate / no-LoRA mean rate"
            " × 100. DA-14 gate: ≥ 70%. Rates pulled from each shard's"
            " raw_dialog.metadata['pilot_rate_focal_per_s']."
        ),
    }
    args.out_throughput.parent.mkdir(parents=True, exist_ok=True)
    args.out_throughput.write_text(
        json.dumps(throughput_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    print(
        f"burrows reduction_pct={point:.4f} "
        f"icc_v2={icc_out['v2_point']} "
        f"throughput_pct={throughput_pct:.2f}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
