"""CLI: score a bond-affinity capture matrix into a verdict JSON sidecar (+ Phase 0).

A thin assembler over :mod:`erre_sandbox.evidence.relational` with its **own** argparse
so the golden-capture CLI ``eval_run_golden`` stays byte-invariant.
Invoked as ``python -m erre_sandbox.cli.bond_affinity_verdict`` (the repo convention;
only ``erre-sandbox`` lives in ``[project.scripts]``).

Two modes:

* **verdict mode** (default): read each ``--capture`` (read-only) via
  :func:`erre_sandbox.evidence.relational.trace_reader.read_bond_capture` (sidecar
  matrix keys + the bond + saturation traces), then call
  :func:`erre_sandbox.evidence.relational.loader.score_bond_affinity_captures` — which
  assembles the ``arm_of`` / ``replicate_of`` maps, applies the matrix-integrity gate,
  and delegates the **entire** statistical decision to the pure ``score_bond_affinity``.
  The CLI adds **no** verdict logic (forking-paths guard); it only aggregates the inputs
  and renders the result + per-source provenance + frozen §1 thresholds as an auditable
  JSON sidecar. What it writes is verdict-*readiness* (a compute path), not a verdict —
  no GPU live-exec bond-affinity data exists yet.
* **Phase 0 mode** (``--phase0``): apply the freeze-ADR §5 stop-gate
  :func:`erre_sandbox.evidence.relational.loader.has_eligible_near_miss` to a **single**
  smoke capture and report whether it carries >= 1 diagnostic-eligible near-miss before
  committing to the 12-run GPU matrix. The caller must satisfy the live §5.3 horizon
  convention first — a short-horizon empty is **not** a stop signal (the gate cannot
  tell the two apart; that is the operator's responsibility).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from erre_sandbox.evidence.capture_sidecar import sidecar_path_for
from erre_sandbox.evidence.relational.loader import (
    has_eligible_near_miss,
    score_bond_affinity_captures,
)
from erre_sandbox.evidence.relational.trace_reader import (
    BondAffinityCapture,
    read_bond_capture,
)
from erre_sandbox.evidence.relational.verdict_report import (
    SourceProvenance,
    bond_affinity_verdict_sidecar_path_for,
    build_bond_affinity_verdict_report,
    file_sha256,
    write_bond_affinity_verdict_sidecar_atomic,
)

logger = logging.getLogger(__name__)

_PHASE0_GO: str = "GO"
"""Phase 0 stdout token: the smoke carries >= 1 diagnostic-eligible near-miss."""

_PHASE0_NO_NEAR_MISS: str = "INCONCLUSIVE_NO_NEAR_MISS"
"""Phase 0 stdout token: no eligible near-miss (empty / short-horizon / flag-off)."""


def _source_provenance(path: Path, capture: BondAffinityCapture) -> SourceProvenance:
    """Build one capture's provenance record (content hash + matrix keys + counts)."""
    return SourceProvenance(
        path=str(path),
        sha256=file_sha256(path),
        seed=capture.seed,
        arm=capture.arm,
        replicate_id=capture.replicate_id,
        bond_row_count=len(capture.bond_rows),
        saturation_row_count=len(capture.saturation_rows),
    )


def _reject_out_capture_collision(out_path: Path, capture_paths: list[Path]) -> None:
    """Refuse to write the verdict over any input capture **or its sidecar**.

    Both the final path and the intermediate ``<out>.tmp`` the writer touches are
    compared against every capture's ``.duckdb`` **and** its ``.capture.json`` sidecar
    on ``Path.resolve(strict=False)`` so symlinks / relative paths to the same file are
    caught too. The sidecar is included (Codex MEDIUM) because overwriting it destroys
    the matrix identity / provenance the audit depends on, like overwriting the trace.
    """
    tmp_path = out_path.with_name(out_path.name + ".tmp")  # mirrors the writer
    touched = {out_path.resolve(strict=False), tmp_path.resolve(strict=False)}
    for cap in capture_paths:
        forbidden = {
            cap.resolve(strict=False),
            sidecar_path_for(cap).resolve(strict=False),
        }
        hit = touched & forbidden
        if hit:
            raise SystemExit(
                f"--out {out_path} (or its .tmp sibling) resolves to input capture "
                f"{cap} (or its sidecar); refusing to overwrite a source file with "
                "the verdict JSON"
            )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-bond-affinity-verdict",
        description=(
            "Score a bond-affinity 12-run paired-arm capture matrix "
            "(seed x arm{ON,OFF} x replicate{0,1}) into a frozen-ADR cross-arm "
            "near-miss verdict JSON sidecar, or (--phase0) apply the §5 stop-gate "
            "to a single smoke capture."
        ),
    )
    parser.add_argument(
        "--capture",
        action="append",
        required=True,
        metavar="DUCKDB",
        help=(
            "Path to one persisted natural-run .duckdb carrying the bond-affinity + "
            "saturation traces. Repeat for every matrix cell in verdict mode (12 runs "
            "= 3 seeds x 2 arms x 2 replicates; an incomplete matrix routes to "
            "INCONCLUSIVE_LOW_POWER, a duplicate / role-swapped one to "
            "INVALID_MEASUREMENT). In --phase0 mode exactly one capture is allowed."
        ),
    )
    parser.add_argument(
        "--phase0",
        action="store_true",
        help=(
            "Phase 0 stop-gate (freeze ADR §5): report whether the single --capture "
            "smoke carries >= 1 diagnostic-eligible near-miss. The caller must satisfy "
            "the live §5.3 horizon convention first (a short-horizon empty is not a "
            "stop signal). Prints GO or INCONCLUSIVE_NO_NEAR_MISS."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run id stamped into the verdict sidecar (required in verdict mode).",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help=(
            "Verdict sidecar output path (verdict mode only). "
            "Default: <first --capture>.bond_affinity_verdict.json."
        ),
    )
    return parser


def _run_phase0(capture_paths: list[Path]) -> int:
    """Apply the §5 stop-gate to a single smoke capture; print the token, return 0."""
    if len(capture_paths) != 1:
        raise SystemExit(
            f"--phase0 takes exactly one --capture (got {len(capture_paths)})"
        )
    capture = read_bond_capture(capture_paths[0])
    eligible = has_eligible_near_miss(capture.bond_rows, capture.saturation_rows)
    token = _PHASE0_GO if eligible else _PHASE0_NO_NEAR_MISS
    print(token)  # machine-readable stop-gate token on stdout
    logger.info(
        "bond-affinity phase0 capture=%s eligible=%s -> %s",
        capture_paths[0],
        eligible,
        token,
    )
    return 0


def _run_verdict(capture_paths: list[Path], *, run_id: str, out: str | None) -> int:
    """Read every capture, score the matrix, and write the verdict sidecar; return 0."""
    captures: list[BondAffinityCapture] = []
    sources: list[SourceProvenance] = []
    for path in capture_paths:
        capture = read_bond_capture(path)
        captures.append(capture)
        sources.append(_source_provenance(path, capture))

    result = score_bond_affinity_captures(captures)
    report = build_bond_affinity_verdict_report(
        result,
        run_id=run_id,
        computed_at=datetime.now(UTC),
        sources=tuple(sources),
    )
    out_path = (
        Path(out)
        if out is not None
        else bond_affinity_verdict_sidecar_path_for(capture_paths[0])
    )
    _reject_out_capture_collision(out_path, capture_paths)
    write_bond_affinity_verdict_sidecar_atomic(out_path, report)
    logger.info(
        "bond-affinity verdict run_id=%s verdict=%s paired_seeds=%s out=%s",
        report.run_id,
        report.verdict,
        report.paired_seeds,
        out_path,
    )
    logger.info("notes: %s", report.notes)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)
    capture_paths = [Path(c) for c in args.capture]

    if args.phase0:
        return _run_phase0(capture_paths)

    if args.run_id is None:
        raise SystemExit(
            "--run-id is required in verdict mode (omit only with --phase0)"
        )
    return _run_verdict(capture_paths, run_id=args.run_id, out=args.out)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
