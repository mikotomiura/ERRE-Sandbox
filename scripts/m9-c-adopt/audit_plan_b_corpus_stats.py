r"""Plan B (Candidate C hybrid retrain) achieved-corpus-stats gate — CLI wrapper.

Thin operator wrapper around :func:`erre_sandbox.training.plan_b_gate.
audit_corpus`. Use this for the G-GEAR collection runbook pre-check
(``.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md``
§6); the same gate logic is invoked automatically inside
``train_kant_lora.py`` when ``--plan-b-gate`` is set.

Thresholds are **module-level constants** in
``erre_sandbox.training.plan_b_gate`` (Codex review HIGH-2: preregistered
gates must not expose post-hoc threshold-movement CLI flags). To
experiment with alternative thresholds, edit the constants in source
and record the change in ``decisions.md`` — this script will not let
you do it via argv.

Usage::

    python scripts/m9-c-adopt/audit_plan_b_corpus_stats.py \\
        --weight-audit data/lora/m9-c-adopt-v2/kant_r8_v3/weight-audit.json \\
        --merge-sha "$(git rev-parse HEAD)" \\
        --output data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from erre_sandbox.training.plan_b_gate import (
    GATE_FAIL_EXIT_CODE,
    audit_corpus,
)

logger = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m9-c-adopt-audit-plan-b-corpus-stats",
        description=(
            "Apply the Plan B 4-axis achieved-corpus-stats hard gate to an"
            " existing weight-audit.json. Exits 0 on pass / 8 on fail."
            " Thresholds are preregistered module constants and NOT"
            " overrideable from the CLI (Codex HIGH-2)."
        ),
    )
    p.add_argument(
        "--weight-audit",
        required=True,
        type=Path,
        help="Path to weight-audit.json emitted by train_kant_lora.",
    )
    p.add_argument(
        "--merge-sha",
        required=True,
        help=(
            "Git SHA of the PR merging the Plan B design + driver"
            " (provenance pin for the gate verdict)."
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output path for plan-b-corpus-gate.json. Defaults to the"
            " parent dir of --weight-audit."
        ),
    )
    p.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )
    weight_audit_path: Path = args.weight_audit
    if not weight_audit_path.exists():
        logger.error("weight-audit not found: %s", weight_audit_path)
        return 2
    weight_audit = json.loads(weight_audit_path.read_text(encoding="utf-8"))

    output_path: Path = (
        args.output
        if args.output is not None
        else weight_audit_path.parent / "plan-b-corpus-gate.json"
    )

    result = audit_corpus(
        weight_audit,
        weight_audit_path=str(weight_audit_path),
        merge_sha=args.merge_sha,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    achieved = result["achieved"]
    thresholds = result["thresholds"]
    logger.info(
        "plan-b-corpus-gate: %s (n_eff=%.1f/%.0f top_5%%=%.3f/%.3f"
        " de+en=%.3f/%.2f de=%.3f/%.2f)",
        result["plan_b_gate"].upper(),
        achieved["n_eff"],
        thresholds["n_eff_min"],
        achieved["top_5_pct_weight_share"],
        thresholds["top_5_pct_max"],
        achieved["de_en_mass"],
        thresholds["de_en_mass_min"],
        achieved["de_mass"],
        thresholds["de_mass_min"],
    )
    logger.info("plan-b-corpus-gate output: %s", output_path)

    if result["failed_axes"]:
        logger.error(
            "plan-b-corpus-gate FAIL on axes: %s",
            ", ".join(result["failed_axes"]),
        )
        return GATE_FAIL_EXIT_CODE
    return 0


if __name__ == "__main__":
    sys.exit(main())
