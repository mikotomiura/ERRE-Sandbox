"""CLI: score a III-a 12-run paired-arm capture matrix into a verdict JSON sidecar.

A thin assembler over :mod:`erre_sandbox.evidence.live_carry` with its **own**
argparse so the golden-capture CLI (:mod:`erre_sandbox.cli.eval_run_golden`) stays
byte-invariant. Invoked as ``python -m erre_sandbox.cli.live_carry_verdict`` (the repo
convention; only ``erre-sandbox`` lives in ``[project.scripts]``).

Pipeline: read each ``--capture`` (read-only) via
:func:`~erre_sandbox.evidence.live_carry.trace_reader.read_capture` (sidecar matrix
keys + the three frozen traces), then call
:func:`~erre_sandbox.evidence.live_carry.scorer.score_live_carry` — which owns the
**entire** four-state decision (matrix assembly, M0/M1/M2, seed-AND routing). The CLI
adds **no** verdict logic (forking-paths guard); it only aggregates the inputs and
renders the result + per-source provenance + frozen thresholds as an auditable JSON
sidecar. What it writes is verdict-*readiness* (a compute path), not a verdict — no
GPU live-exec data exists yet.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from erre_sandbox.evidence.live_carry.scorer import score_live_carry
from erre_sandbox.evidence.live_carry.trace_reader import (
    LiveCarryCapture,
    read_capture,
)
from erre_sandbox.evidence.live_carry.verdict_report import (
    SourceProvenance,
    build_live_carry_verdict_report,
    file_sha256,
    live_carry_verdict_sidecar_path_for,
    write_live_carry_verdict_sidecar_atomic,
)

logger = logging.getLogger(__name__)


def _source_provenance(path: Path, capture: LiveCarryCapture) -> SourceProvenance:
    """Build one capture's provenance record (content hash + matrix keys + counts)."""
    return SourceProvenance(
        path=str(path),
        sha256=file_sha256(path),
        seed=capture.seed,
        arm=capture.arm,
        replicate_id=capture.replicate_id,
        floor_row_count=len(capture.floor_rows),
        saturation_row_count=len(capture.saturation_rows),
        coherence_row_count=len(capture.coherence_rows),
    )


def _reject_out_capture_collision(out_path: Path, capture_paths: list[Path]) -> None:
    """Refuse to write the verdict over any input capture (mirror saturation CLI).

    Both the final path and the intermediate ``<out>.tmp`` the writer touches are
    compared against every capture on ``Path.resolve(strict=False)`` so symlinks /
    relative paths pointing at the same file are caught too.
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
        prog="erre-live-carry-verdict",
        description=(
            "Score a III-a 12-run paired-arm capture matrix "
            "(seed x arm{ON,OFF} x replicate{0,1}) into a frozen-ADR four-state "
            "live-carry verdict JSON sidecar."
        ),
    )
    parser.add_argument(
        "--capture",
        action="append",
        required=True,
        metavar="DUCKDB",
        help=(
            "Path to one persisted natural-run .duckdb carrying the III-a traces. "
            "Repeat for every matrix cell (12 runs = 3 seeds x 2 arms x 2 "
            "replicates; an incomplete matrix routes to INVALID_MEASUREMENT)."
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
            "Default: <first --capture>.live_carry_verdict.json."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)

    capture_paths = [Path(c) for c in args.capture]
    captures: list[LiveCarryCapture] = []
    sources: list[SourceProvenance] = []
    for path in capture_paths:
        capture = read_capture(path)
        captures.append(capture)
        sources.append(_source_provenance(path, capture))

    result = score_live_carry(captures)
    report = build_live_carry_verdict_report(
        result,
        run_id=args.run_id,
        computed_at=datetime.now(UTC),
        sources=tuple(sources),
    )
    out_path = (
        Path(args.out)
        if args.out is not None
        else live_carry_verdict_sidecar_path_for(capture_paths[0])
    )
    _reject_out_capture_collision(out_path, capture_paths)
    write_live_carry_verdict_sidecar_atomic(out_path, report)
    logger.info(
        "live-carry verdict run_id=%s verdict=%s seeds=%s out=%s",
        report.run_id,
        report.verdict,
        report.seeds,
        out_path,
    )
    logger.info("notes: %s", report.notes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
