"""``erre-sandbox export-log`` — dump ``dialog_turns`` to JSONL.

Reads the sqlite ``dialog_turns`` table populated by the M8 L6-D1 sink
(see ``.steering/20260425-m8-episodic-log-pipeline/``) and streams matching
rows as newline-delimited JSON. Consumed by the M9 LoRA training pipeline
and the forthcoming ``m8-baseline-quality-metric`` spike.

Scope choices baked in (decisions D4):

* JSONL is the only supported format. ``--format`` is still exposed so the
  flag surface is stable when Parquet is added in a later milestone, but any
  value other than ``jsonl`` is rejected at parse time.
* Filters are AND-composed (``--persona`` and ``--since``); adding OR /
  expression trees is deferred until a real use case demands it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from erre_sandbox.memory import MemoryStore

if TYPE_CHECKING:
    from collections.abc import Iterator


SUPPORTED_FORMATS: tuple[str, ...] = ("jsonl",)
"""Formats accepted by ``--format``. Parquet joins this set in the M9 LoRA task."""


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the ``export-log`` sub-command to the root argparse tree."""
    parser = subparsers.add_parser(
        "export-log",
        help="Export dialog_turns log to JSONL (M8 L6-D1 precondition).",
        description=(
            "Stream the contents of the sqlite ``dialog_turns`` table as "
            "newline-delimited JSON. Intended for M9 LoRA training-data "
            "preparation and for baseline turn-count reporting."
        ),
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="var/kant.db",
        help="Path to the sqlite database (default: var/kant.db).",
    )
    parser.add_argument(
        "--format",
        default="jsonl",
        choices=SUPPORTED_FORMATS,
        help=(
            "Output format. Only ``jsonl`` is supported in M8 — Parquet is "
            "deferred to the M9 LoRA task (decisions D4)."
        ),
    )
    parser.add_argument(
        "--persona",
        default=None,
        help=(
            "Filter by ``speaker_persona_id`` (e.g. ``kant``). "
            "Omit to export every persona."
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "Only include rows whose ``created_at`` is at or after this "
            "ISO-8601 timestamp (e.g. ``2026-04-24T00:00:00+00:00``)."
        ),
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default="-",
        help="Output path; use ``-`` for stdout (default).",
    )


def _parse_since(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        msg = f"--since expected ISO-8601 (e.g. 2026-04-24T00:00:00+00:00), got {raw!r}"
        raise SystemExit(msg) from exc


def _open_output(out_path: str):  # type: ignore[no-untyped-def]
    """Return (writer, close_fn) for ``out_path``; ``-`` means stdout."""
    if out_path == "-":
        return sys.stdout, lambda: None
    handle = Path(out_path).open("w", encoding="utf-8")  # noqa: SIM115
    return handle, handle.close


def run(args: argparse.Namespace) -> int:
    """Execute the ``export-log`` sub-command.

    Returns the POSIX exit code (0 on success, non-zero on failure).
    """
    if args.format not in SUPPORTED_FORMATS:  # defence in depth vs. choices=
        print(
            f"--format {args.format!r} is not supported (choose one of "
            f"{SUPPORTED_FORMATS}).",
            file=sys.stderr,
        )
        return 2

    since = _parse_since(args.since)
    store = MemoryStore(db_path=args.db_path)
    # Caller may hand us a fresh DB that has not had ``create_schema`` run
    # yet — idempotent, so the cost of calling it here is zero when it has.
    store.create_schema()

    writer, close_fn = _open_output(args.out_path)
    try:
        row_count = 0
        for row in store.iter_dialog_turns(persona=args.persona, since=since):
            writer.write(json.dumps(row, ensure_ascii=False))
            writer.write("\n")
            row_count += 1
        if hasattr(writer, "flush"):
            writer.flush()
    finally:
        close_fn()

    # Report to stderr when writing to a file so a chained caller sees the
    # count without contaminating the JSONL stream on stdout.
    if args.out_path != "-":
        print(
            f"export-log: wrote {row_count} row(s) to {args.out_path}",
            file=sys.stderr,
        )
    return 0
