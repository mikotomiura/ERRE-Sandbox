"""``erre-sandbox source-index`` — compile a persona source-navigator index.

Loads ``<personas-dir>/<persona>.yaml``, links each ``cognitive_habit`` to
its cited source + bibliographic provenance, and writes a depth-2 index
(``INDEX.md`` + ``index.json``) under ``<out-dir>/<persona>/``.

The output is deterministic (no timestamp); ``--check`` recompiles in
memory and byte-compares against the committed artefacts, exiting non-zero
on drift or absence so CI can assert the committed index is current.

Not connected to the runtime cognition tick — this is a compile-time
evidence-audit tool.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

from erre_sandbox.evidence.source_navigator.compiler import compile_from_dir
from erre_sandbox.evidence.source_navigator.render import (
    render_json,
    render_markdown,
)

_INDEX_MD: str = "INDEX.md"
_INDEX_JSON: str = "index.json"

# Same shape the orchestrator's --personas path enforces (__main__._PERSONA_ID_RE):
# persona_id is joined into both the input and output file paths, so anything
# with ``..`` / path separators / leading dots must be rejected before use.
_PERSONA_ID_RE: Final[re.Pattern[str]] = re.compile(r"\A[a-z][a-z0-9_-]{0,63}\Z")


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the ``source-index`` sub-command to the root argparse tree."""
    parser = subparsers.add_parser(
        "source-index",
        help="Compile a persona source-navigator index (markdown + JSON).",
        description=(
            "Link a persona's cognitive_habits to their cited sources and "
            "bibliographic provenance, emitting a deterministic depth-2 "
            "index. bibliographic_only sources carry no committed document "
            "body — a citation is not evidence."
        ),
    )
    parser.add_argument(
        "--persona",
        default="kant",
        help="persona_id to compile (default: kant — the MVP scope).",
    )
    parser.add_argument(
        "--personas-dir",
        dest="personas_dir",
        default="personas",
        help="Directory containing <persona>.yaml files (default: personas/).",
    )
    parser.add_argument(
        "--out-dir",
        dest="out_dir",
        default="data/corpus_index",
        help=(
            "Output root; index lands in <out-dir>/<persona>/"
            " (default: data/corpus_index)."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help=(
            "Do not write. Recompile in memory and byte-compare against the "
            "committed artefacts; exit non-zero on drift or absence."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``source-index`` sub-command (POSIX exit code)."""
    if not _PERSONA_ID_RE.fullmatch(args.persona):
        print(
            f"source-index: --persona {args.persona!r} rejected; must match"
            f" {_PERSONA_ID_RE.pattern} (lowercase alnum + _ -, <=64 chars)",
            file=sys.stderr,
        )
        return 2

    personas_dir = Path(args.personas_dir)
    persona_dir = Path(args.out_dir) / args.persona
    md_path = persona_dir / _INDEX_MD
    json_path = persona_dir / _INDEX_JSON

    index = compile_from_dir(personas_dir, args.persona)
    md_text = render_markdown(index)
    json_text = render_json(index)

    if args.check:
        return _check(args.persona, md_path, md_text, json_path, json_text)

    persona_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8", newline="\n")
    json_path.write_text(json_text, encoding="utf-8", newline="\n")
    print(
        f"source-index: wrote {md_path} and {json_path}",
        file=sys.stderr,
    )
    return 0


def _check(
    persona: str,
    md_path: Path,
    md_text: str,
    json_path: Path,
    json_text: str,
) -> int:
    drift: list[str] = []
    for path, expected in ((md_path, md_text), (json_path, json_text)):
        if not path.is_file():
            drift.append(f"missing: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            drift.append(f"stale: {path}")
    if drift:
        for line in drift:
            print(f"source-index --check: {line}", file=sys.stderr)
        print(
            f"source-index --check: {persona} index is out of date;"
            " regenerate with `python -m erre_sandbox source-index"
            f" --persona {persona}`",
            file=sys.stderr,
        )
        return 1
    print(f"source-index --check: {persona} index is current", file=sys.stderr)
    return 0


__all__ = ["register", "run"]
