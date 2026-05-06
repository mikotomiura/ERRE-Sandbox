"""``eval_audit`` — gate that decides whether a capture is usable for analysis.

Spec: ``.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`` §2,
ME-9 ADR. Reads ``<output>.duckdb`` plus its sidecar
(``<output>.duckdb.capture.json``, see :mod:`erre_sandbox.evidence.capture_sidecar`)
and decides PASS / FAIL based on row-count cross-check, run-id integrity
(Codex H1, 2026-05-06), and the recorded ``status`` Literal.

Single-cell return codes::

    0  PASS   — status=complete and focal_observed >= focal_target,
                or status=partial with explicit --allow-partial
    4  missing sidecar (legacy capture or operator deleted it)
    5  DB / sidecar mismatch (rows / focal / run_id) or unreadable sidecar
    6  incomplete (complete + focal<target) or partial without --allow-partial
       (also covers status=fatal, which should not normally have a published
        DuckDB file but is treated as FAIL if encountered)

Batch mode (``--duckdb-glob``) audits every match and writes a JSON report;
the overall exit code is the *worst* (numerically max) single-cell result so
launch-prompts can fail-fast on any non-zero return.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import duckdb
from pydantic import ValidationError

from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    expected_run_id,
    read_sidecar,
    sidecar_path_for,
)
from erre_sandbox.evidence.eval_store import atomic_temp_rename

logger = logging.getLogger(__name__)

EXIT_PASS: Final[int] = 0
EXIT_MISSING_SIDECAR: Final[int] = 4
EXIT_MISMATCH: Final[int] = 5
EXIT_INCOMPLETE: Final[int] = 6


# ---------------------------------------------------------------------------
# Single-cell audit
# ---------------------------------------------------------------------------


def _count_rows(
    con: duckdb.DuckDBPyConnection, persona: str
) -> tuple[int, int, set[str]]:
    """Return ``(total_rows, focal_rows, run_ids)`` from a read-only handle."""
    total = con.execute("SELECT COUNT(*) FROM raw_dialog.dialog").fetchone()
    focal = con.execute(
        "SELECT COUNT(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
        [persona],
    ).fetchone()
    run_id_rows = con.execute(
        "SELECT DISTINCT run_id FROM raw_dialog.dialog"
    ).fetchall()
    total_rows = int(total[0]) if total else 0
    focal_rows = int(focal[0]) if focal else 0
    run_ids = {str(row[0]) for row in run_id_rows}
    return total_rows, focal_rows, run_ids


def _audit_single(  # noqa: C901, PLR0911, PLR0912
    duckdb_path: Path,
    *,
    focal_target: int,
    allow_partial: bool,
) -> tuple[int, dict[str, Any]]:
    """Audit one capture cell. Returns ``(exit_code, detail_dict)``.

    The branchy shape mirrors the spec's decision table (missing sidecar /
    unreadable / row mismatch / focal mismatch / run_id mismatch / status
    eval); flattening it would obscure the contract.
    """
    detail: dict[str, Any] = {"duckdb_path": str(duckdb_path)}
    sidecar_path = sidecar_path_for(duckdb_path)

    if not sidecar_path.exists():
        detail.update(reason="missing_sidecar", sidecar_path=str(sidecar_path))
        return EXIT_MISSING_SIDECAR, detail

    try:
        payload: SidecarV1 = read_sidecar(sidecar_path)
    except (ValidationError, json.JSONDecodeError, OSError) as exc:
        detail.update(reason="sidecar_unreadable", error=repr(exc))
        return EXIT_MISMATCH, detail

    detail.update(
        sidecar_path=str(sidecar_path),
        status=payload.status,
        stop_reason=payload.stop_reason,
        focal_observed=payload.focal_observed,
        focal_target=focal_target,
        sidecar_total_rows=payload.total_rows,
        persona=payload.persona,
        condition=payload.condition,
        run_idx=payload.run_idx,
    )

    if not duckdb_path.exists():
        detail.update(reason="missing_duckdb")
        return EXIT_MISMATCH, detail

    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        try:
            actual_total, actual_focal, actual_run_ids = _count_rows(
                con, payload.persona
            )
        except duckdb.Error as exc:
            detail.update(reason="duckdb_query_failed", error=repr(exc))
            return EXIT_MISMATCH, detail
    finally:
        con.close()

    detail.update(
        actual_total_rows=actual_total,
        actual_focal_rows=actual_focal,
        actual_run_ids=sorted(actual_run_ids),
    )

    expected = expected_run_id(payload)
    detail["expected_run_id"] = expected

    if actual_total != payload.total_rows:
        detail.update(reason="rows_mismatch")
        return EXIT_MISMATCH, detail
    if actual_focal != payload.focal_observed:
        detail.update(reason="focal_mismatch")
        return EXIT_MISMATCH, detail
    if actual_run_ids != {expected}:
        # Codex H1 (2026-05-06): same-run integrity — a foreign run_id means
        # the sidecar may be from a different cell.
        detail.update(reason="run_id_mismatch")
        return EXIT_MISMATCH, detail

    if payload.status == "complete" and actual_focal >= focal_target:
        detail.update(reason="complete_pass")
        return EXIT_PASS, detail
    if payload.status == "partial" and allow_partial:
        detail.update(reason="partial_diagnostic_pass")
        return EXIT_PASS, detail
    if payload.status == "complete":
        detail.update(reason="incomplete_below_target")
    elif payload.status == "partial":
        detail.update(reason="partial_refused_no_flag")
    else:  # fatal — should not normally reach audit because rename refused
        detail.update(reason="fatal_published")
    return EXIT_INCOMPLETE, detail


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------


_TRAINING_PATH_MARKERS: Final[tuple[str, ...]] = (
    "/eval/training/",
    "training_view",
)


def _path_smells_like_training(path: Path) -> bool:
    """Heuristic check used by :func:`_write_report_atomic` (Codex M3, 2026-05-06)."""
    posix = path.as_posix()
    return any(marker in posix for marker in _TRAINING_PATH_MARKERS)


def _write_report_atomic(report_path: Path, report: dict[str, Any]) -> None:
    """Write the batch JSON report atomically (temp + same-fs rename)."""
    if _path_smells_like_training(report_path):
        # Codex M3 (2026-05-06): warn (not refuse) so operators can still
        # opt into a non-conventional path; the marker keeps the audit-vs-
        # training-egress separation visible in stderr.
        sys.stderr.write(
            f"warning: --report-json {report_path!s} looks like a"
            " training-egress path; audit reports should live outside the"
            " training corpus.\n",
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(report_path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_temp_rename(tmp, report_path)


def _audit_batch(
    duckdb_glob: str,
    *,
    focal_target: int,
    allow_partial: bool,
    report_path: Path | None,
) -> int:
    """Audit every glob match; emit a JSON report; return ``max()`` exit code.

    A worst-result-wins exit code lets launch prompts treat the audit as a
    single gate (``if eval_audit ... ; then proceed ; else fail``).
    """
    # ``glob.glob`` (rather than ``Path.glob``) handles both absolute and
    # relative patterns symmetrically — the spec example
    # ``data/eval/phase2/*_run*.duckdb`` is relative but operators may pass
    # absolute paths from a launch prompt.
    matches = sorted(Path(p) for p in glob.glob(duckdb_glob))  # noqa: PTH207
    if not matches:
        # Code reviewer (2026-05-06 MEDIUM): silent success on a typo'd glob
        # is the easiest way to lose an entire run; warn loudly even though
        # the empty-match return code stays EXIT_PASS for backward compat.
        logger.warning(
            "audit batch: no files matched glob=%s — verify the pattern"
            " (typos / wrong cwd / missing rsync)",
            duckdb_glob,
        )
    counts = {
        "complete": 0,
        "partial": 0,
        "missing_sidecar": 0,
        "mismatch": 0,
        "fail": 0,
    }
    details: list[dict[str, Any]] = []
    overall = EXIT_PASS

    for duckdb_path in matches:
        code, detail = _audit_single(
            duckdb_path,
            focal_target=focal_target,
            allow_partial=allow_partial,
        )
        detail["exit_code"] = code
        details.append(detail)
        overall = max(overall, code)
        status = detail.get("status")
        if code == EXIT_PASS:
            if status == "complete":
                counts["complete"] += 1
            elif status == "partial":
                counts["partial"] += 1
        elif code == EXIT_MISSING_SIDECAR:
            counts["missing_sidecar"] += 1
        elif code == EXIT_MISMATCH:
            counts["mismatch"] += 1
        else:
            counts["fail"] += 1

    report = {
        "audited_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duckdb_glob": duckdb_glob,
        "focal_target": focal_target,
        "allow_partial": allow_partial,
        "total": len(matches),
        **counts,
        "overall_exit_code": overall,
        "details": details,
    }

    if report_path is not None:
        _write_report_atomic(report_path, report)
    else:
        # Without --report-json, log a one-line summary to stderr so the
        # caller still sees aggregate counts even in non-batch CI modes.
        logger.info(
            "audit batch glob=%s total=%d complete=%d partial=%d"
            " missing_sidecar=%d mismatch=%d fail=%d overall_exit=%d",
            duckdb_glob,
            len(matches),
            counts["complete"],
            counts["partial"],
            counts["missing_sidecar"],
            counts["mismatch"],
            counts["fail"],
            overall,
        )
    return overall


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-eval-audit",
        description=(
            "Audit one or more capture DuckDB files against their sidecar"
            " metadata. Used as a gate before downstream analysis"
            " (m9-eval Phase 3 audit, ME-9 ADR)."
        ),
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--duckdb",
        type=Path,
        help="Audit a single DuckDB capture file.",
    )
    target.add_argument(
        "--duckdb-glob",
        type=str,
        help=(
            "Glob pattern; audit every match and return max() exit code."
            " Use --report-json to capture per-cell results."
        ),
    )
    parser.add_argument(
        "--focal-target",
        type=int,
        required=True,
        help="Focal-row count required for status=complete to PASS.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help=(
            "Treat status=partial as PASS (diagnostic mode). Default: refuse"
            " (return 6) so production gates do not silently accept partials."
        ),
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help=(
            "Batch mode only — write a JSON report to this path."
            " Atomic temp+rename; warns if the path looks like a"
            " training-egress location."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
        help="Root logger level.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    if args.duckdb_glob is not None:
        return _audit_batch(
            args.duckdb_glob,
            focal_target=args.focal_target,
            allow_partial=args.allow_partial,
            report_path=args.report_json,
        )

    code, detail = _audit_single(
        args.duckdb,
        focal_target=args.focal_target,
        allow_partial=args.allow_partial,
    )
    if code == EXIT_PASS:
        logger.info("audit PASS %s", detail)
    else:
        logger.warning("audit FAIL exit=%d %s", code, detail)
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "EXIT_INCOMPLETE",
    "EXIT_MISMATCH",
    "EXIT_MISSING_SIDECAR",
    "EXIT_PASS",
    "main",
]
