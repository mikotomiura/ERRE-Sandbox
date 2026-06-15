"""CLI: re-score arm-tagged saturation captures into a **horizon-reserved** verdict.

A thin plumbing layer over the horizon compose scorer
(:func:`~erre_sandbox.evidence.saturation.horizon_versioned_loader.score_horizon_versioned_saturation`).
Mirrors :mod:`erre_sandbox.cli.versioned_saturation_verdict` exactly (read-only DuckDB →
assemble → score delegation → frozen sidecar → atomic + collision guard) and adds **no**
verdict logic; it only swaps the scorer + report builder for the horizon-reserved
(Conditional-V2) variant. Invoked as
``python -m erre_sandbox.cli.horizon_versioned_saturation_verdict``.

**Two-layer exit (mirrors the versioned CLI).** A *structural* anomaly (manifest
parse/path/schema, mixed run_id, multi-seed, natural-key dup, hint identity mismatch,
bundle/pairing dup, population mismatch, on-disk swap, ``--out`` collision) exits
non-zero and writes no sidecar. A *scientific* outcome (INCONCLUSIVE, NO_PAIR, N!=3,
V3 NOT EVALUATED/INVALID, OFF incomplete, CV2 INCONCLUSIVE) is the scorer's authority:
the sidecar is written and the CLI exits 0.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.saturation.horizon_versioned_loader import (
    score_horizon_versioned_saturation,
)
from erre_sandbox.evidence.saturation.horizon_versioned_verdict_report import (
    build_horizon_versioned_verdict_report,
    horizon_versioned_saturation_verdict_sidecar_path_for,
    write_horizon_versioned_saturation_verdict_sidecar_atomic,
)
from erre_sandbox.evidence.saturation.trace_ddl import TABLE_NAME
from erre_sandbox.evidence.saturation.verdict_report import file_sha256
from erre_sandbox.evidence.saturation.versioned_loader import (
    VersionedSaturationLoaderError,
)
from erre_sandbox.evidence.saturation.versioned_verdict_report import (
    VersionedVerdictAssemblyError,
    VersionedVerdictManifest,
    VersionedVerdictManifestError,
    assemble_bundles,
    load_manifest,
    resolve_manifest_ref,
)

logger = logging.getLogger(__name__)

_STRUCTURAL_EXIT: Final[int] = 2
"""Non-zero exit for a structural anomaly: no sidecar is written."""

_SQL_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""A bare, unquoted SQL identifier — the only shape the loader's SELECT accepts."""


def _sql_identifier(value: str) -> str:
    """Reject (as an argparse ``type=`` guard) anything not a bare SQL identifier."""
    if not _SQL_IDENTIFIER_RE.match(value):
        msg = (
            f"not a valid SQL identifier: {value!r} (expected ^[A-Za-z_][A-Za-z0-9_]*$)"
        )
        raise argparse.ArgumentTypeError(msg)
    return value


def _collect_input_paths(
    manifest: VersionedVerdictManifest, manifest_path: Path
) -> list[Path]:
    """Every writer-protected input: the manifest + all captures + all hint captures."""
    paths: list[Path] = [manifest_path]
    for entry in manifest.entries:
        paths.append(resolve_manifest_ref(manifest_path, entry.capture))
        if entry.hint_capture is not None:
            paths.append(resolve_manifest_ref(manifest_path, entry.hint_capture))
    return paths


def _reject_out_input_collision(out_path: Path, input_paths: list[Path]) -> None:
    """Refuse to write the verdict over any input file (mirrors the versioned CLI)."""
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    touched = [out_path, tmp_path]
    touched_resolved = {p.resolve(strict=False) for p in touched}
    for inp in input_paths:
        if inp.resolve(strict=False) in touched_resolved:
            raise SystemExit(
                f"--out {out_path} (or its .tmp sibling) resolves to input {inp}; "
                "refusing to overwrite an input with the verdict JSON"
            )
        for t in touched:
            if t.exists() and inp.exists() and t.samefile(inp):
                raise SystemExit(
                    f"--out {out_path} (or its .tmp sibling) is the same file as "
                    f"input {inp} (hardlink); refusing to overwrite it"
                )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-horizon-versioned-saturation-verdict",
        description=(
            "Re-score arm-tagged SWM saturation captures into the horizon-reserved "
            "(Conditional-V2 over the evaluable subset) retained-across-fingerprint-"
            "change verdict JSON sidecar. The horizon scorer is the sole verdict "
            "authority; this CLI only assembles, validates, delegates, and renders."
        ),
    )
    parser.add_argument(
        "--manifest",
        required=True,
        metavar="JSON",
        help=(
            "Path to the contrast manifest (案 C external arm tagging): a JSON object "
            "with schema_version / contrast_kind / optional envelope / entries, each "
            "entry = {capture, arm: ON|OFF, source_run_id, hint_capture: path|null}."
        ),
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Operator run id stamped into the verdict sidecar.",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help=(
            "Verdict sidecar output path. Default: "
            "<first manifest capture>.horizon_versioned_saturation_verdict.json."
        ),
    )
    parser.add_argument(
        "--schema",
        default=METRICS_SCHEMA,
        type=_sql_identifier,
        help="Schema holding the trace tables (default %(default)s).",
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
    manifest_path = Path(args.manifest)

    try:
        manifest = load_manifest(manifest_path)
        first_capture = resolve_manifest_ref(manifest_path, manifest.entries[0].capture)
        out_path = (
            Path(args.out)
            if args.out is not None
            else horizon_versioned_saturation_verdict_sidecar_path_for(first_capture)
        )
        _reject_out_input_collision(
            out_path, _collect_input_paths(manifest, manifest_path)
        )
        bundles, sources = assemble_bundles(
            manifest, manifest_path, schema=args.schema, table=args.table
        )
        result = score_horizon_versioned_saturation(bundles)
        report = build_horizon_versioned_verdict_report(
            result,
            run_id=args.run_id,
            computed_at=datetime.now(UTC),
            contrast_kind=manifest.contrast_kind,
            manifest_sha256=file_sha256(manifest_path),
            manifest=manifest,
            sources=sources,
        )
        write_horizon_versioned_saturation_verdict_sidecar_atomic(out_path, report)
    except (
        VersionedVerdictManifestError,
        VersionedVerdictAssemblyError,
        VersionedSaturationLoaderError,
    ) as exc:
        logger.error("structural anomaly (no sidecar written): %s", exc)  # noqa: TRY400
        return _STRUCTURAL_EXIT

    logger.info(
        "horizon versioned saturation verdict run_id=%s on_verdict=%s "
        "overall_verdict=%s off_control_complete=%s n_on=%d n_off=%d out=%s",
        report.run_id,
        report.on_verdict,
        report.overall_verdict,
        report.off_control_complete,
        len(report.on_partitions),
        len(report.off_partitions),
        out_path,
    )
    logger.info("notes: %s", report.notes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
