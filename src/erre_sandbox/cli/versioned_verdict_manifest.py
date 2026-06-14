"""CLI: build a versioned-verdict 案 C manifest from arm-tagged paired captures (U4).

A thin operator front-end over
:func:`~erre_sandbox.evidence.saturation.versioned_verdict_manifest_builder.build_paired_manifest`.
Invoked as ``python -m erre_sandbox.cli.versioned_verdict_manifest`` (the repo
convention; only ``erre-sandbox`` lives in ``[project.scripts]``). It declares each
ON/OFF capture pair, machine-grounds the compose (sidecar cross-check + preflight
assemble + N=3 completeness — verification is always on; there is no bypass), and
atomically writes the manifest JSON the verdict CLI then consumes.

The arm tag and seed pairing are never trusted blindly: the builder fails fast on a
mis-tagged / mis-paired / stale-sidecar / wrong-seed compose, so a wrong contrast cannot
reach the scorer. It cannot prevent a wrong GPU capture from running (it runs after
capture) — only stop a wrong capture being scored as a valid pair.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import sidecar_path_for
from erre_sandbox.evidence.eval_store import atomic_temp_rename
from erre_sandbox.evidence.saturation.trace_ddl import TABLE_NAME
from erre_sandbox.evidence.saturation.versioned_verdict_manifest_builder import (
    CapturePairing,
    PairedManifestBuildError,
    build_paired_manifest,
)

logger = logging.getLogger(__name__)

_STRUCTURAL_EXIT: Final[int] = 2
"""Non-zero exit when the compose is rejected: no manifest is written."""

_REQUIRE_PAIRS: Final[int] = 3
"""N=3 binding: a single-seed contrast cannot yield a verdict."""


def _parse_pairing(value: str) -> CapturePairing:
    """Parse ``on=PATH,off=PATH[,hint_on=PATH][,hint_off=PATH]`` into a pairing."""
    fields: dict[str, str] = {}
    for part in value.split(","):
        key, sep, raw = part.partition("=")
        key = key.strip()
        if not sep or not raw.strip():
            raise argparse.ArgumentTypeError(
                f"--pairing field {part!r} is not key=PATH"
            )
        if key not in {"on", "off", "hint_on", "hint_off"}:
            raise argparse.ArgumentTypeError(
                f"--pairing unknown key {key!r} (expected on/off/hint_on/hint_off)"
            )
        if key in fields:
            raise argparse.ArgumentTypeError(f"--pairing duplicate key {key!r}")
        fields[key] = raw.strip()
    if "on" not in fields or "off" not in fields:
        raise argparse.ArgumentTypeError("--pairing requires both on= and off=")
    return CapturePairing(
        on_capture=Path(fields["on"]),
        off_capture=Path(fields["off"]),
        hint_on=Path(fields["hint_on"]) if "hint_on" in fields else None,
        hint_off=Path(fields["hint_off"]) if "hint_off" in fields else None,
    )


def _parse_envelope(items: list[str] | None) -> dict[str, object]:
    """Parse repeated ``k=v`` operator envelope declarations (audit-only)."""
    env: dict[str, object] = {}
    for item in items or []:
        key, sep, val = item.partition("=")
        if not sep:
            raise SystemExit(f"--envelope {item!r} is not key=value")
        env[key.strip()] = val.strip()
    return env


def _pairing_input_paths(pairings: list[CapturePairing]) -> list[Path]:
    """Every writer-protected input: each capture, its sidecar, and any hint capture."""
    paths: list[Path] = []
    for pair in pairings:
        for capture in (pair.on_capture, pair.off_capture):
            paths.extend((capture, sidecar_path_for(capture)))
        paths.extend(h for h in (pair.hint_on, pair.hint_off) if h is not None)
    return paths


def _reject_out_input_collision(out_path: Path, input_paths: list[Path]) -> None:
    """Refuse to write the manifest over any input (mirrors versioned verdict HIGH-4).

    The writer writes a fixed ``<out>.tmp`` then ``atomic_temp_rename``s it onto
    ``out``. Both writer-touched paths are compared against every input by
    ``Path.resolve(strict=False)`` and, for paths that exist, by ``Path.samefile``
    (hardlinks the resolve cannot see).
    """
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    touched = [out_path, tmp_path]
    touched_resolved = {p.resolve(strict=False) for p in touched}
    for inp in input_paths:
        if inp.resolve(strict=False) in touched_resolved:
            raise SystemExit(
                f"--out {out_path} (or its .tmp sibling) resolves to input {inp}; "
                "refusing to overwrite an input with the manifest JSON"
            )
        for t in touched:
            if t.exists() and inp.exists() and t.samefile(inp):
                raise SystemExit(
                    f"--out {out_path} (or its .tmp sibling) is the same file as "
                    f"input {inp} (hardlink); refusing to overwrite it"
                )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-versioned-verdict-manifest",
        description=(
            "Build a versioned-verdict 案 C manifest from arm-tagged ON/OFF capture "
            "pairs, machine-grounding the compose (sidecar cross-check + preflight "
            "assemble + N=3 completeness) before writing. Verification is always on."
        ),
    )
    parser.add_argument(
        "--pairing",
        required=True,
        action="append",
        type=_parse_pairing,
        metavar="on=PATH,off=PATH[,hint_on=PATH][,hint_off=PATH]",
        help=(
            f"One ON/OFF capture pair (repeat exactly {_REQUIRE_PAIRS} times for the "
            "N=3 binding). ON and OFF must share persona / run_idx / seed."
        ),
    )
    parser.add_argument(
        "--source-run-id-base",
        required=True,
        help="Pairing-key base; each pair gets <base>_pair<i> as its source_run_id.",
    )
    parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help="Manifest JSON output path (atomic write; refuses to overwrite an input).",
    )
    parser.add_argument(
        "--contrast-kind",
        choices=("replay", "live"),
        default="live",
        help="Recorded contrast kind (default %(default)s).",
    )
    parser.add_argument(
        "--envelope",
        action="append",
        metavar="KEY=VALUE",
        help="Operator envelope declaration (audit-only; repeatable).",
    )
    parser.add_argument(
        "--schema",
        default=METRICS_SCHEMA,
        help="Schema holding the trace tables (default %(default)s).",
    )
    parser.add_argument(
        "--table",
        default=TABLE_NAME,
        help="Saturation trace table name (default %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)
    out_path = Path(args.out)
    pairings: list[CapturePairing] = list(args.pairing)

    _reject_out_input_collision(out_path, _pairing_input_paths(pairings))

    try:
        manifest = build_paired_manifest(
            pairings,
            source_run_id_base=args.source_run_id_base,
            manifest_path=out_path,
            contrast_kind=args.contrast_kind,
            envelope=_parse_envelope(args.envelope),
            schema=args.schema,
            table=args.table,
            require_pairs=_REQUIRE_PAIRS,
        )
    except PairedManifestBuildError as exc:
        # A rejected compose is an expected control-flow outcome (mis-tagged /
        # mis-paired / stale inputs), not a crash — report and exit non-zero with no
        # manifest written.
        logger.error("manifest rejected (no manifest written): %s", exc)  # noqa: TRY400
        return _STRUCTURAL_EXIT

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    atomic_temp_rename(tmp_path, out_path)

    logger.info(
        "versioned verdict manifest written pairs=%d entries=%d out=%s",
        len(pairings),
        len(manifest.entries),
        out_path,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
