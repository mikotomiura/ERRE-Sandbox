"""Distill ``results/metrics.json`` from ``results/external-audit.json`` (Loop I-008).

Read-only extraction of the primary indicators (design-final.md / issue
008's ``notes.md`` prompt): per corpus x split, the §6 verdict tuple,
``class_sizes``, and per-candidate ``auc_full_at_median_draw`` /
``auc_lao_at_median_draw`` / ``drop_at_median_draw`` /
``potency_at_median_draw`` / ``collapsed_draw_share`` / the §5.2 bootstrap
``AUC_LAO`` CI. No wall-clock is ever written; every float leaf is
6-decimal quantized (``feedback_golden_crossplatform_float_drift.md`` --
``results/external-audit.json``'s own leaves are already quantized by
``scripts/paper01_external_audit.py``'s ``_quantize_json``, this module
re-quantizes defensively so ``metrics.json`` never depends on that).

Scope (issue 008 Allowed Files): new file under
``experiments/20260907-paper01-g1/``. Never re-computes a statistic --
every value here is read straight out of the already-persisted
``external-audit.json``, never recomputed through
``scripts/paper01_external_audit.py``'s statistics/verdict layer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent
EXTERNAL_AUDIT_PATH = EXPERIMENT_DIR / "results" / "external-audit.json"
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


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    """One candidate's primary indicators (already computed upstream)."""
    if not candidate.get("available"):
        return {"available": False}
    aggregate = candidate.get("aggregate", {})
    if not candidate.get("bootstrapped"):
        # Lexical (X5/X6): never bootstrapped, never verdict-eligible --
        # only the §5.1 draw-aggregate fields exist.
        return {
            "available": True,
            "bootstrapped": False,
            "eligible": aggregate.get("eligible"),
            "engaged": aggregate.get("engaged"),
            "collapsed": aggregate.get("collapsed"),
            "collapsed_draw_share": aggregate.get("collapsed_draw_share"),
            "median_drop": aggregate.get("median_drop"),
        }
    report = candidate.get("report", {})
    bootstrap = candidate.get("bootstrap", {})
    return {
        "available": True,
        "bootstrapped": True,
        "auc_full_at_median_draw": report.get("auc_full_at_median_draw"),
        "auc_lao_at_median_draw": report.get("auc_lao_at_median_draw"),
        "drop_at_median_draw": report.get("drop_at_median_draw"),
        "potency_at_median_draw": report.get("potency_at_median_draw"),
        "collapsed_draw_share": aggregate.get("collapsed_draw_share"),
        "auc_lao_ci": bootstrap.get("auc_lao_ci"),
    }


def _split_summary(split: dict[str, Any]) -> dict[str, Any]:
    """One split's §6 verdict tuple + per-candidate primary indicators."""
    verdict = split.get("verdict", {})
    candidates = {
        key: _candidate_summary(candidate)
        for key, candidate in split.get("candidates", {}).items()
    }
    return {
        "verdict": verdict.get("verdict"),
        "collapse_reproduced": verdict.get("collapse_reproduced"),
        "survivors": verdict.get("survivors"),
        "eligible": verdict.get("eligible"),
        "engaged": verdict.get("engaged"),
        "class_sizes": split.get("class_sizes", {}),
        "candidates": candidates,
    }


def build_metrics(audit: dict[str, Any]) -> dict[str, Any]:
    """Corpus-keyed primary-indicator summary of an ``external-audit.json`` payload."""
    metrics: dict[str, Any] = {}
    for corpus_key, corpus in audit.items():
        status = corpus.get("status")
        if status != "ok":
            metrics[corpus_key] = {"status": status}
            continue
        metrics[corpus_key] = {
            "status": "ok",
            "splits": {
                scheme: _split_summary(split)
                for scheme, split in corpus.get("splits", {}).items()
            },
        }
    return metrics


def write_metrics(
    audit_path: Path = EXTERNAL_AUDIT_PATH, metrics_path: Path = METRICS_PATH
) -> dict[str, Any]:
    """Read ``audit_path``, distill it, write ``metrics_path`` deterministically."""
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    metrics = _quantize(build_metrics(audit))
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
