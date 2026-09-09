"""Boundary-predicate gates ``run.sh`` evaluates (Loop I-007).

``run.sh`` (this directory) orchestrates the paper01 scope-condition
measurement end to end (``.steering/20260908-paper01-scope-condition/
design-final.md``, ``docs/experiment-tracking.md``). Every *judgment* it
makes along the way is implemented here as a plain, directly testable
Python function -- ``run.sh`` itself only calls into this module's CLI (or
``scripts/paper01_scope_condition.py``'s own ``--fidelity`` exit code for
the fidelity-pin gate) and reacts to the process exit code. Keeping every
judgment as an importable function is what lets a mutation-testing pass
exercise it directly instead of only observing a shell exit code
(``feedback_witness_needs_mutation_testing.md``).

Mirrors ``experiments/20260907-paper01-g1/run_gate.py`` (issue 008's own
run-gate, the direct precedent this issue is modelled on -- design-final.md
"G1 の反省を binding で持ち込む") almost line for line: same SHA-256
byte-identity gate, same completion-marker discipline, same
Limitations-marker completeness check generalised from G1's six to this
issue's own eight (design-final.md §8) plus the DA-SC-19 pre-registration-
amendment note.

Scope (issue 007 Allowed Files): this file is new, lives entirely under
``experiments/20260908-paper01-scope-condition/``, and never imports or
duplicates ``scripts/paper01_scope_condition.py``'s own scoring/statistics/
verdict layer -- it only reads already-written JSON/text artifacts that
layer produced.

**I-007a boundary**: this module is written but never run against a real
``run.sh`` invocation in this session (no live measurement -- see this
module's own test file for the synthetic-data proof of each predicate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

REQUIRED_LIMITATIONS: tuple[str, ...] = (
    "LIMITATION:rho-is-proxy",
    "LIMITATION:tau-star-upstream-factor",
    "LIMITATION:arm-s-constructed",
    "LIMITATION:c4-most-circular",
    "LIMITATION:t-driven-not-rejected",
    "LIMITATION:ocsai-brick-weight-concentration",
    "LIMITATION:cambridge-underpowered",
    "LIMITATION:codex-70-80-percent-inconclusive",
)
"""design-final.md §8's eight pre-registered Limitations, in the same
order as §8's own numbered list (1..8):

1. rho-is-proxy: "ρ は S の proxy であって代数的対応物ではない" (MEDIUM-1).
2. tau-star-upstream-factor: "τ* の較正は外部 anchor プールの幾何を使う"
   (MEDIUM-3).
3. arm-s-constructed: "ARM-S は我々が構成した配置" であり実在のスコアラ運用
   の証拠ではない。
4. c4-most-circular: 内部 C4 は G1 ADR §2 が「最も circular な配置」と明記。
5. t-driven-not-rejected: T 由来の可能性は棄却していない (HIGH-3)。
6. ocsai-brick-weight-concentration: Ocsai は brick に重みが集中 (LOW-2)。
7. cambridge-underpowered: Cambridge は検出力不足であり確証には使わない。
8. codex-70-80-percent-inconclusive: Codex の見立てでは「特定できない」に
   倒れる確率は 70-80%。

Each is a stable, grep-able HTML-comment anchor placed next to the
human-readable Limitations bullet it names -- invisible when the Markdown
is rendered, but not dependent on any specific Japanese wording surviving
future edits (mirrors G1's ``REQUIRED_LIMITATIONS`` convention exactly).
"""

PREREGISTRATION_AMENDMENT_MARKER: str = "PREREGISTRATION-AMENDMENT:stage1-three-state"
"""DA-SC-19's own binding instruction: "notes.md (I-007) の Limitations に
「事前登録は2026-09-08に一度修正されている(実測前・Stage 1三状態化)」を必ず
書く。修正の事実を伏せない。" -- a ninth, distinct marker (the amendment is
not one of the eight design-final.md §8 items; it belongs next to them but
is not interchangeable with any of them)."""

COMPLETION_MARKER: str = "PAPER01_SCOPE_CONDITION_RUN_COMPLETE"
"""The literal ``run.sh`` must emit as its final log line so a monitor can
tell the run finished from the log tail without relying on tqdm's most
recent (possibly stale, carriage-return-overwritten) line
(``feedback_log_tail_completion_marker.md`` /
``feedback_wsl_bg_launch_needs_disown.md``)."""


def sha256_of_file(path: Path) -> str:
    """SHA-256 hex digest of ``path``'s bytes (AC 007-2's byte-identity check)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes_match(hash_a: str, hash_b: str) -> bool:
    """AC 007-2 boundary predicate: two ``--scope`` runs must byte-match.

    mutation target (issue 007's own "SHA-256 一致ゲートを常に真にする"):
    forcing this to always return ``True`` would let ``run.sh`` silently
    accept a non-reproducible ``scope.json``.
    """
    return hash_a == hash_b


def notes_has_required_limitations(
    text: str, required: Sequence[str] = REQUIRED_LIMITATIONS
) -> bool:
    """AC 007-6 boundary predicate: every required Limitations marker is present.

    mutation target: shrinking ``required`` (or this module's own
    :data:`REQUIRED_LIMITATIONS`) would let ``notes.md`` report fewer than
    the pre-registered eight Limitations and still pass.
    """
    return all(marker in text for marker in required)


def notes_has_preregistration_amendment(
    text: str, marker: str = PREREGISTRATION_AMENDMENT_MARKER
) -> bool:
    """DA-SC-19 boundary predicate: the pre-registration-amendment note is present.

    Distinct from :func:`notes_has_required_limitations` -- the DA-SC-19
    note is not one of the eight design-final.md §8 Limitations items, so a
    ``notes.md`` that carries all eight but omits this marker must still
    fail this check.
    """
    return marker in text


def run_sh_has_completion_marker(text: str, marker: str = COMPLETION_MARKER) -> bool:
    """AC 007-1 boundary predicate: ``run.sh``'s own source emits the marker.

    mutation target: removing the marker-emitting line from ``run.sh`` (or
    disabling this check) would let ``run.sh`` finish without a detectable
    completion signal, defeating the PID-survival + log-tail progress
    judgement this issue requires instead of trusting tqdm's latest line.

    Codex TASK-POST LOW-1: a bare ``marker in text`` containment check is a
    false-positive waiting to happen -- the literal surviving only in a shell
    comment (or in this docstring's own constant) would satisfy it while
    ``run.sh`` no longer emits anything. ``run.sh`` emits the marker as a JSON
    line, so require a non-comment line that actually carries a JSON object
    whose ``event`` **equals** the marker.
    """
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        start = line.find("{")
        end = line.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            payload = json.loads(line[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == marker:
            return True
    return False


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
        description="paper01 scope-condition run.sh boundary-predicate gates"
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
    """CLI entry point (Loop I-007)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
