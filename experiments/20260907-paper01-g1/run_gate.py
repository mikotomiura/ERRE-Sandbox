"""Boundary-predicate gates ``run.sh`` evaluates (Loop I-008).

``run.sh`` (this directory) orchestrates the paper01 G1 external-audit
reproduction end to end (``.steering/20260907-paper01-g1-external-audit/
design-final.md``, ``docs/experiment-tracking.md``). Every *judgment* it
makes along the way is implemented here as a plain, directly testable
Python function -- ``run.sh`` itself only calls into this module's CLI (or
``scripts/paper01_external_audit.py``'s own ``--audit`` exit code for the
corpus-availability gate, see ``both_corpora_available`` there) and reacts
to the process exit code. Keeping every judgment as an importable function
is what lets ``tests/test_paper01_g1/test_run_artifacts.py`` mutation-test
it directly instead of only observing a shell exit code
(``feedback_witness_needs_mutation_testing.md``).

Scope (issue 008 Allowed Files): this file is new, lives entirely under
``experiments/20260907-paper01-g1/``, and never imports or duplicates
``scripts/paper01_external_audit.py``'s own scoring/statistics/verdict
layer -- it only reads already-written JSON/text artifacts that layer
produced.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

REQUIRED_LIMITATIONS: tuple[str, ...] = (
    "LIMITATION:participant-id",
    "LIMITATION:cambridge-no-a2",
    "LIMITATION:rater-rotation",
    "LIMITATION:ocsai-motes-provenance",
    "LIMITATION:small-good-class",
    "LIMITATION:narrow-object-set",
)
"""``notes.md``'s six pre-registered Limitations markers (issue 008 task
prompt / design-final.md §8). Each is a stable, grep-able HTML-comment
anchor placed next to the human-readable Limitations bullet it names --
invisible when the Markdown is rendered, but not dependent on any specific
Japanese wording surviving future edits."""

COMPLETION_MARKER: str = "PAPER01_G1_RUN_COMPLETE"
"""The literal ``run.sh`` must emit as its final log line so a monitor can
tell the run finished from the log tail without relying on tqdm's most
recent (possibly stale, carriage-return-overwritten) line
(``feedback_log_tail_completion_marker.md`` /
``feedback_wsl_bg_launch_needs_disown.md``)."""


def sha256_of_file(path: Path) -> str:
    """SHA-256 hex digest of ``path``'s bytes (AC 008-4's byte-identity check)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes_match(hash_a: str, hash_b: str) -> bool:
    """AC 008-4 boundary predicate: two ``--audit`` runs must byte-match.

    mutation target (2, issue 008 AC-MUT): forcing this to always return
    ``True`` would let ``run.sh`` silently accept a non-reproducible run.
    """
    return hash_a == hash_b


def notes_has_required_limitations(
    text: str, required: Sequence[str] = REQUIRED_LIMITATIONS
) -> bool:
    """AC 008-5 boundary predicate: every required Limitations marker is present.

    mutation target (3, issue 008 AC-MUT): shrinking ``required`` (or this
    module's own :data:`REQUIRED_LIMITATIONS`) would let ``notes.md`` report
    fewer than the pre-registered six Limitations and still pass.
    """
    return all(marker in text for marker in required)


def run_sh_has_completion_marker(text: str, marker: str = COMPLETION_MARKER) -> bool:
    """AC 008-6 boundary predicate: ``run.sh``'s own source emits the marker.

    mutation target (4, issue 008 AC-MUT): removing the marker-emitting
    line from ``run.sh`` (or disabling this check) would let ``run.sh``
    finish without a detectable completion signal, defeating the
    PID-survival + log-tail progress judgement this issue requires instead
    of trusting tqdm's latest line.
    """
    return marker in text


def _cmd_check_hashes(args: argparse.Namespace) -> int:
    first = Path(args.first)
    second = Path(args.second)
    hash_a = sha256_of_file(first)
    hash_b = sha256_of_file(second)
    if hashes_match(hash_a, hash_b):
        sys.stdout.write(f"[run_gate] hashes match: {hash_a}\n")
        return 0
    sys.stderr.write(
        f"[run_gate] HASH MISMATCH -- {first}={hash_a} {second}={hash_b}\n"
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    """The ``run_gate.py`` CLI -- ``run.sh`` calls the ``check-hashes`` subcommand."""
    parser = argparse.ArgumentParser(
        description="paper01 G1 run.sh boundary-predicate gates"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    check_hashes = sub.add_parser(
        "check-hashes", help="exit 0 iff two files' SHA-256 digests match"
    )
    check_hashes.add_argument("first")
    check_hashes.add_argument("second")
    check_hashes.set_defaults(func=_cmd_check_hashes)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point (Loop I-008)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
