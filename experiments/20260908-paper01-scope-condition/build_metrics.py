"""Distill ``results/metrics.json`` from ``results/scope.json`` (Loop I-007).

Read-only extraction of the headline indicators (design-final.md §5/§9,
issue 007 Scope In item 5: "metrics.json (読み取り専用抽出。統計を再計算
しない)"). Every value here is read straight out of the already-persisted
``results/scope.json`` (:func:`scripts.paper01_scope_condition.run_scope`'s
own frozen output) -- never recomputed through
``scripts/paper01_scope_condition.py``'s Stage 0/1/2/verdict layer. No wall
clock is ever written; every float leaf is re-quantized defensively (6
decimals, ``feedback_golden_crossplatform_float_drift.md``) even though
``scope.json``'s own leaves are already quantized by ``run_scope``'s
``_quantize_json`` call, so ``metrics.json`` never depends on that upstream
step happening to still be true.

Mirrors ``experiments/20260907-paper01-g1/build_metrics.py`` (issue 008's
own precedent -- design-final.md "G1 の反省を binding で持ち込む").

Scope (issue 007 Allowed Files): this file is new, lives entirely under
``experiments/20260908-paper01-scope-condition/``.

**I-007a boundary**: this module is written but never run against a real
``results/scope.json`` in this session (no live measurement -- see this
module's own test file for the synthetic-data proof that extraction never
recomputes a statistic).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent
SCOPE_PATH = EXPERIMENT_DIR / "results" / "scope.json"
METRICS_PATH = EXPERIMENT_DIR / "results" / "metrics.json"


def _quantize(value: Any) -> Any:
    """Recursively round every float leaf to 6 decimals; pass others through."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _quantize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_quantize(item) for item in value]
    return value


def _split_summary(split: dict[str, Any]) -> dict[str, Any]:
    """One Ocsai split's headline cell verdicts + τ* calibration.

    Every field is a direct lookup off ``split["arm_a"]`` /
    ``split["arm_s"]`` / ``split["tau_calibration"]`` -- design-final.md §3
    Stage 2's 2x2 grid diagonal, never a re-derivation.
    """
    arm_a = split.get("arm_a", {})
    arm_s = split.get("arm_s", {})
    tau_cal = split.get("tau_calibration", {})
    return {
        "arm_a_verdict": arm_a.get("verdict"),
        "arm_a_active_objects": arm_a.get("active_objects"),
        "arm_s_verdict": arm_s.get("verdict"),
        "arm_s_active_objects": arm_s.get("active_objects"),
        "tau_star": tau_cal.get("tau_star"),
        "k_star": tau_cal.get("k_star"),
        "rho_int_primary": tau_cal.get("rho_int_primary"),
        "single_point_dependent": tau_cal.get("single_point_dependent"),
    }


def build_metrics(scope: dict[str, Any]) -> dict[str, Any]:
    """The headline §5 verdict + §3 Stage 0/1/2 summary of a ``scope.json`` payload.

    Read-only extraction (design-final.md §7's "統計を再計算しない"): every
    leaf below is a plain ``dict.get`` off ``scope``'s own already-computed
    sections, no arithmetic. ``KeyError`` is never raised here -- a section
    :func:`scripts.paper01_scope_condition.run_scope` omitted (it never
    does, design-final.md §3: "Stage 0 / Stage 1 / 全セル / ScopeVerdict...
    が載る") reads as an empty mapping (``{}``), never a fabricated default
    *value*.
    """
    verdict = scope.get("verdict", {})
    stage1 = scope.get("stage1", {})
    stage2 = scope.get("stage2", {})
    cells = stage2.get("cells", {})
    return {
        "verdict": {
            "verdict": verdict.get("verdict"),
            "condition_c_supported": verdict.get("condition_c_supported"),
            "deflation_supported": verdict.get("deflation_supported"),
            "single_point_dependent": verdict.get("single_point_dependent"),
            "fail_reason": verdict.get("fail_reason"),
            "t_confound_note_required": verdict.get("t_confound_note_required"),
        },
        "stage1": {
            "stage1_outcome": stage1.get("stage1_outcome"),
            "deflation_supported": stage1.get("deflation_supported"),
            "median_drop": stage1.get("median_drop"),
            "eligible_fraction": stage1.get("eligible_fraction"),
            "median_draw_outcome": stage1.get("median_draw_outcome"),
        },
        "stage0_rows": [
            {
                "source": row.get("source"),
                "candidate": row.get("candidate"),
                "mean_delta_good": row.get("mean_delta_good"),
                "mean_delta_common": row.get("mean_delta_common"),
                "rho": row.get("rho"),
            }
            for row in scope.get("stage0", [])
        ],
        "cambridge_verdict": stage2.get("cambridge", {}).get("verdict"),
        "splits": {
            split_key: _split_summary(split) for split_key, split in cells.items()
        },
    }


def write_metrics(
    scope_path: Path = SCOPE_PATH, metrics_path: Path = METRICS_PATH
) -> dict[str, Any]:
    """Read ``scope_path``, extract, write ``metrics_path`` deterministically."""
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    metrics = _quantize(build_metrics(scope))
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    """CLI entry point: ``run.sh`` calls this with no arguments."""
    write_metrics()
    sys.stdout.write(f"[build_metrics] wrote {METRICS_PATH}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
