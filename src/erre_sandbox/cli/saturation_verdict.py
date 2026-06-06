"""CLI: score N=3 saturation trace DuckDBs into a verdict JSON sidecar (ADR 3.4).

A thin assembler over the existing loader, with its **own** argparse so the
golden-capture CLI (:mod:`erre_sandbox.cli.eval_run_golden`) stays byte-invariant.
Invoked as ``python -m erre_sandbox.cli.saturation_verdict`` (the repo convention;
only ``erre-sandbox`` lives in ``[project.scripts]``).

Pipeline: open each ``--capture`` DuckDB **read-only**, read its rows via
:func:`~erre_sandbox.evidence.saturation.loader.read_saturation_trace_rows`, union
the rows in Python, and call
:func:`~erre_sandbox.evidence.saturation.loader.score_saturation` — which owns the
**entire** 3-way decision (per-seed partition, ``T_run >= 25``, provenance, NaN,
gates, exactly ``N=3``, label agreement). The CLI adds **no** verdict logic (ADR
section 7 forking-paths guard); it only aggregates the inputs and renders the result
+ per-source provenance + frozen thresholds as an auditable JSON sidecar.

Aggregation is the plain "open each file, read via the loader API, concatenate"
path rather than a DuckDB ``ATTACH`` + ``UNION ALL``: ``score_saturation`` already
partitions a row sequence by ``seed``, and ``read_saturation_trace_rows`` already
reads one connection in column-lockstep, so reusing them avoids a second SQL path
that would duplicate the column order / schema / scoring (design-comparison.md).

``--schema`` / ``--table`` are validated as bare SQL identifiers before they reach
the loader's string-composed ``SELECT`` (the loader trusts its caller), so an
arbitrary string can never flow into the query.
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
from erre_sandbox.evidence.saturation.loader import (
    read_saturation_trace_rows,
    score_saturation,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
)
from erre_sandbox.evidence.saturation.verdict_report import (
    SourceProvenance,
    build_saturation_verdict_report,
    build_source_provenance,
    saturation_verdict_sidecar_path_for,
    write_saturation_verdict_sidecar_atomic,
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
    file are caught too.
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
        prog="erre-saturation-verdict",
        description=(
            "Score N=3 SWM saturation trace DuckDBs into a frozen-ADR 3-way verdict "
            "(SATURATED / NON-SATURATED / INCONCLUSIVE) JSON sidecar."
        ),
    )
    parser.add_argument(
        "--capture",
        action="append",
        required=True,
        metavar="DUCKDB",
        help=(
            "Path to one persisted natural-run .duckdb carrying the saturation "
            "trace. Repeat for every paired seed (the probe binds a verdict only "
            "for exactly 3 agreeing valid seeds; ADR section 3.4)."
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
            "Default: <first --capture>.saturation_verdict.json."
        ),
    )
    parser.add_argument(
        "--schema",
        default=METRICS_SCHEMA,
        type=_sql_identifier,
        help="Schema holding the saturation trace table (default %(default)s).",
    )
    parser.add_argument(
        "--table",
        default=TABLE_NAME,
        type=_sql_identifier,
        help="Saturation trace table name (default %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)

    capture_paths = [Path(c) for c in args.capture]
    all_rows: list[SaturationTraceRow] = []
    sources: list[SourceProvenance] = []
    for path in capture_paths:
        con = duckdb.connect(str(path), read_only=True)
        try:
            rows = read_saturation_trace_rows(con, schema=args.schema, table=args.table)
        finally:
            con.close()
        all_rows.extend(rows)
        sources.append(build_source_provenance(path, rows))

    result = score_saturation(all_rows)
    report = build_saturation_verdict_report(
        result,
        run_id=args.run_id,
        computed_at=datetime.now(UTC),
        sources=tuple(sources),
    )
    out_path = (
        Path(args.out)
        if args.out is not None
        else saturation_verdict_sidecar_path_for(capture_paths[0])
    )
    _reject_out_capture_collision(out_path, capture_paths)
    write_saturation_verdict_sidecar_atomic(out_path, report)
    logger.info(
        "saturation verdict run_id=%s verdict=%s median_sat_frac=%s "
        "n_valid_seeds=%d out=%s",
        report.run_id,
        report.verdict,
        report.median_sat_frac,
        report.n_valid_seeds,
        out_path,
    )
    logger.info("notes: %s", report.notes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
