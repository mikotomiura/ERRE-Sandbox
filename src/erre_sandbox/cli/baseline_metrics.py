"""``erre-sandbox baseline-metrics`` — compute M8 baseline quality JSON.

Reads the sqlite ``dialog_turns`` + ``bias_events`` tables populated by the
M8 L6-D1 sinks and emits a JSON document shaped for M9 LoRA comparison. The
metrics themselves (fidelity + bias_fired_rate, with affinity deferred)
live in :mod:`erre_sandbox.evidence.metrics`; this module is the argparse
shell around them.

Scope decisions for this spike (see
``.steering/20260425-m8-baseline-quality-metric/decisions.md``):

* Output format is JSON only — the aggregated metrics are a handful of
  scalars, not a stream that benefits from JSONL.
* Aggregation is post-hoc (decision D4): the CLI does not need the live
  run to still be up. Pointing it at a read-only copy of the DB is fine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from erre_sandbox.evidence import aggregate


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the ``baseline-metrics`` sub-command to the root argparse tree."""
    parser = subparsers.add_parser(
        "baseline-metrics",
        help="Compute M8 baseline quality metrics from a run DB (post-hoc).",
        description=(
            "Aggregate self_repetition_rate / cross_persona_echo_rate / "
            "bias_fired_rate from the sqlite ``dialog_turns`` + "
            "``bias_events`` tables and emit a JSON document. The shape is "
            "stable so M9 LoRA comparison runs can diff against it."
        ),
    )
    parser.add_argument(
        "--run-db",
        dest="db_path",
        required=True,
        help="Path to the sqlite database populated by a live run.",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default="-",
        help="Output path; use ``-`` for stdout (default).",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``baseline-metrics`` sub-command.

    Returns the POSIX exit code (0 on success, non-zero on failure).
    """
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(
            f"baseline-metrics: {db_path!s} does not exist",
            file=sys.stderr,
        )
        return 2

    result = aggregate(db_path)
    payload = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out_path == "-":
        sys.stdout.write(payload)
        sys.stdout.write("\n")
        return 0

    Path(args.out_path).write_text(payload + "\n", encoding="utf-8")
    print(
        f"baseline-metrics: wrote aggregate JSON to {args.out_path}",
        file=sys.stderr,
    )
    return 0
