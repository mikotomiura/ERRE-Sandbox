"""CLI: score N hint-engagement trace DuckDBs into a verdict JSON sidecar (ADR §6).

A thin assembler over the existing loader, with its **own** argparse so the
golden-capture CLI (:mod:`erre_sandbox.cli.eval_run_golden`) stays byte-invariant.
Invoked as ``python -m erre_sandbox.cli.hint_engagement_verdict`` (the repo convention;
only ``erre-sandbox`` lives in ``[project.scripts]``).

Pipeline: open each ``--capture`` DuckDB **read-only**, read its rows via
:func:`~erre_sandbox.evidence.hint_engagement.loader.read_hint_engagement_trace_rows`,
union the rows in Python, and call
:func:`~erre_sandbox.evidence.hint_engagement.loader.score_hint_engagement` — which owns
the **entire** routing decision (global stability gate, the (a)/(b)/(c) precedence
cascade, boundary ties, the provenance-false short-circuit). The CLI adds **no** verdict
logic (ADR §8 forking-paths guard); it only aggregates the inputs and renders the result
+ per-source provenance + frozen thresholds as an auditable JSON sidecar.

Unlike the saturation verdict CLI, there is **no exactly-N gating**: the engagement
instrument pools any number of seeds/runs (DA-EII-12). ``score_hint_engagement`` unions
the eligible ticks for the rates and keys adopted-nudge channels by full run identity,
so every capture's rows are concatenated and handed straight through.

``--schema`` / ``--table`` are validated as bare SQL identifiers before they reach the
loader's string-composed ``SELECT`` (the loader trusts its caller), so an arbitrary
string can never flow into the query. The resolved ``--out`` path is rejected if it
collides with any input capture (DA-HEV-1): the sidecar writer's
``atomic_temp_rename`` would otherwise ``replace`` an input DuckDB with JSON.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import duckdb

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.loader import (
    read_hint_engagement_trace_rows,
    score_hint_engagement,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME,
    HintEngagementTraceRow,
)
from erre_sandbox.evidence.hint_engagement.verdict_report import (
    SourceProvenance,
    build_hint_engagement_verdict_report,
    build_source_provenance,
    hint_engagement_verdict_sidecar_path_for,
    write_hint_engagement_verdict_sidecar_atomic,
)

logger = logging.getLogger(__name__)

_SQL_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""A bare, unquoted SQL identifier — the only shape the loader's SELECT accepts."""


def _sql_identifier(value: str) -> str:
    """Reject (as an argparse ``type=`` guard) anything not a bare SQL identifier.

    The loader composes ``SELECT ... FROM {schema}.{table}`` from these strings and
    trusts its caller, so validating here closes the injection surface at the CLI
    boundary (the verdict path is the only externally-driven caller).
    """
    if not _SQL_IDENTIFIER_RE.match(value):
        msg = (
            f"not a valid SQL identifier: {value!r} (expected ^[A-Za-z_][A-Za-z0-9_]*$)"
        )
        raise argparse.ArgumentTypeError(msg)
    return value


def _reject_out_capture_collision(out_path: Path, capture_paths: list[Path]) -> None:
    """Refuse to write the verdict over any input capture (DA-HEV-1 / DA-HEV-6).

    The sidecar writer first ``write_text``s a fixed ``<out>.tmp`` and then
    ``atomic_temp_rename``s it onto ``out`` (``Path.replace``). **Both** the final path
    and that intermediate temp path would silently overwrite an input DuckDB if
    ``--out`` (or its ``.tmp`` sibling) aliased a ``--capture`` — e.g.
    ``--capture x.json.tmp --out x.json`` clobbers the capture via the temp write even
    though the final path differs (Codex HIGH-1). Compare every writer-touched path
    against every capture on
    ``Path.resolve(strict=False)`` so symlinks and relative paths that point at the same
    file are caught too (the captures need not exist after being read, hence
    ``strict=False``).
    """
    tmp_path = out_path.with_name(out_path.name + ".tmp")  # mirrors the writer
    touched = {out_path.resolve(strict=False), tmp_path.resolve(strict=False)}
    for cap in capture_paths:
        if cap.resolve(strict=False) in touched:
            raise SystemExit(
                f"--out {out_path} (or its .tmp sibling) resolves to input capture "
                f"{cap}; refusing to overwrite the trace with the verdict JSON"
            )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-hint-engagement-verdict",
        description=(
            "Score N SWM hint-engagement trace DuckDBs into a frozen-ADR routing "
            "verdict (INSTRUMENT_INCONCLUSIVE / STATE_A_EMISSION_RARE / "
            "STATE_B_ADOPTION_REJECTED / STATE_C_DIRECTION_INCONSISTENT / "
            "STATE_ALL_HEALTHY) JSON sidecar."
        ),
    )
    parser.add_argument(
        "--capture",
        action="append",
        required=True,
        metavar="DUCKDB",
        help=(
            "Path to one persisted natural-run .duckdb carrying the hint-engagement "
            "trace. Repeat for every pooled seed/run (the instrument pools any number "
            "of seeds; ADR §5 / DA-EII-12)."
        ),
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Run id stamped into the verdict sidecar.",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help=(
            "Verdict sidecar output path. "
            "Default: <first --capture>.hint_engagement_verdict.json."
        ),
    )
    parser.add_argument(
        "--schema",
        default=METRICS_SCHEMA,
        type=_sql_identifier,
        help="Schema holding the hint-engagement trace table (default %(default)s).",
    )
    parser.add_argument(
        "--table",
        default=TABLE_NAME,
        type=_sql_identifier,
        help="Hint-engagement trace table name (default %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)

    capture_paths = [Path(c) for c in args.capture]
    all_rows: list[HintEngagementTraceRow] = []
    sources: list[SourceProvenance] = []
    for path in capture_paths:
        con = duckdb.connect(str(path), read_only=True)
        try:
            rows = read_hint_engagement_trace_rows(
                con, schema=args.schema, table=args.table
            )
        finally:
            con.close()
        all_rows.extend(rows)
        sources.append(build_source_provenance(path, rows))

    out_path = (
        Path(args.out)
        if args.out is not None
        else hint_engagement_verdict_sidecar_path_for(capture_paths[0])
    )
    _reject_out_capture_collision(out_path, capture_paths)

    result = score_hint_engagement(all_rows)
    report = build_hint_engagement_verdict_report(
        result,
        run_id=args.run_id,
        computed_at=datetime.now(UTC),
        sources=tuple(sources),
    )
    write_hint_engagement_verdict_sidecar_atomic(out_path, report)
    logger.info(
        "hint-engagement verdict run_id=%s verdict=%s emission_rate=%s "
        "adoption_rate=%s n_emitted=%d n_eligible_channels=%d out=%s",
        report.run_id,
        report.verdict,
        report.emission_rate,
        report.adoption_rate,
        report.n_emitted,
        report.n_eligible_channels,
        out_path,
    )
    logger.info("notes: %s", report.notes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
