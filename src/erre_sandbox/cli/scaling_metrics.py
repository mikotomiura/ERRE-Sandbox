"""``erre-sandbox scaling-metrics`` — compute M8 scaling profile JSON.

Reads the sqlite ``dialog_turns`` table populated by the M8 L6-D1 sink
(M1/M2 inputs) and, optionally, a probe NDJSON journal (M3 zone
snapshots) and emits a JSON document shaped for L6 D2 scaling-trigger
evaluation. The metrics live in
:mod:`erre_sandbox.evidence.scaling_metrics`; this module is the
argparse shell.

Scope decisions for this spike:

* Output format is JSON only; the metrics are a handful of scalars.
* Aggregation is post-hoc — the live run does not need to be up.
* ``--journal`` is optional. Without it the zone metric (M3) is
  omitted, the alert evaluation excludes M3, and the CLI exits 0/1
  based on M1/M2 alone (graceful degradation per D3).
* Exit codes: ``0`` (no thresholds breached), ``1`` (≥1 threshold
  breached), ``2`` (input file missing or unreadable).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from erre_sandbox.evidence.scaling_metrics import aggregate


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the ``scaling-metrics`` sub-command to the root argparse tree."""
    parser = subparsers.add_parser(
        "scaling-metrics",
        help="Compute M8 scaling bottleneck metrics from a run DB (post-hoc).",
        description=(
            "Aggregate pair_information_gain / late_turn_fraction / "
            "zone_kl_from_uniform from the sqlite ``dialog_turns`` table and "
            "(optionally) a probe NDJSON journal, then evaluate them against "
            "analytic-bound thresholds. Emits a JSON document; appends one "
            "TSV line per breached threshold to ``--alert-log``."
        ),
    )
    parser.add_argument(
        "--run-db",
        dest="db_path",
        required=True,
        help="Path to the sqlite database populated by a live run.",
    )
    parser.add_argument(
        "--journal",
        dest="journal_path",
        default=None,
        help=(
            "Optional probe NDJSON journal. Required for the zone metric "
            "(M3); omit to compute M1/M2 only with M3 = null."
        ),
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default="-",
        help="Output path; use ``-`` for stdout (default).",
    )
    parser.add_argument(
        "--alert-log",
        dest="alert_log_path",
        default="var/scaling_alert.log",
        help=(
            "TSV log appended one line per threshold breach "
            "(default: var/scaling_alert.log)."
        ),
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        default=None,
        help=(
            "Identifier recorded in alert log entries; defaults to the run "
            "DB filename stem when omitted."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``scaling-metrics`` sub-command.

    Returns the POSIX exit code:
    ``0`` no alerts, ``1`` ≥1 alert, ``2`` input file missing.
    """
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(
            f"scaling-metrics: {db_path!s} does not exist",
            file=sys.stderr,
        )
        return 2

    journal_path: Path | None = None
    if args.journal_path is not None:
        journal_path = Path(args.journal_path)
        if not journal_path.exists():
            print(
                f"scaling-metrics: {journal_path!s} does not exist",
                file=sys.stderr,
            )
            return 2

    alert_log_path = Path(args.alert_log_path) if args.alert_log_path else None

    result = aggregate(
        db_path,
        journal_path,
        run_id=args.run_id,
        alert_log_path=alert_log_path,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out_path == "-":
        sys.stdout.write(payload)
        sys.stdout.write("\n")
    else:
        Path(args.out_path).write_text(payload + "\n", encoding="utf-8")
        print(
            f"scaling-metrics: wrote aggregate JSON to {args.out_path}",
            file=sys.stderr,
        )

    alerts = result.get("alerts") or []
    return 1 if alerts else 0
