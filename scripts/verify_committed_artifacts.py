"""One command that replays every committed artifact this repository's
determinism claim rests on, and checks their checked-out bytes against
``docs/artifact-hashes.md``.

Why this exists
---------------
``scripts/repro.sh`` used to be the only "one command reproduction" entry point,
and it verified the **ECL v0 golden fixture alone**. The sealed real-model
bundles that actually carry the cross-platform byte-parity claim
(``experiments/20260907-m13-society-live/artifacts/`` and
``experiments/20260904-m13-live-loop-live/artifacts/``) were never touched by
it, so a reader told to "run this" verified a smaller, different artifact than
the one being claimed.

What it does
------------
Five targets, each run as its own subprocess so that per-bundle environment
pins stay per-bundle:

* ``society-real`` / ``society-rehearsal`` -- the N=3 society closure bundles
* ``live-loop-real`` / ``live-loop-rehearsal`` -- the N=1 live-loop bundles
* ``ecl-v0-golden`` -- the ECL v0 golden fixture

Every one of them is a **replay-verify**: the committed records are replayed and
the re-rendered bytes are compared against the committed bytes. The replay
itself contacts no language model, no GPU and no network -- the replay clients
are fed from the committed records and assert ``inner_invocations == 0``. That
is the property this script is here to let a third party check for themselves.
(Installing the runtime dependencies beforehand does of course need a package
index or a warm ``uv`` cache; the claim is about the replay, not the install --
Codex independent review 2026-09-12, HIGH-2.)

It is **not** a re-bake. Baking the bundles requires a real Ollama host and a
ratified spend; this command can never produce one, and a green run must not be
read as "the artifacts were regenerated here".

Environment pins
----------------
``ERRE_ZONE_BIAS_P`` is read by ``erre_sandbox.cognition.cycle`` at construction
time, so a value exported into the whole shell leaks into every replay. Each
bundle records the value it was baked under in ``manifest.json``'s ``env_pins``,
and this script sets **that** value for **that** subprocess only. Nothing is
exported process-wide.

This is reconstructing a sealed artifact's *recorded provenance* in order to
replay it, not searching for a setting that makes the check pass: running a
bundle under some other value would be verifying a different artifact, and the
value used is printed for every target so a reader can see which one it was.

Usage
-----
    uv run --frozen --no-dev python scripts/verify_committed_artifacts.py
    uv run --frozen --no-dev python scripts/verify_committed_artifacts.py --write-hashes

``--frozen --no-dev`` is not decoration: it pins the environment to ``uv.lock``
and installs the runtime dependencies **only**. A green run under it is the
evidence that replaying these bundles needs neither the test tooling nor the
machine-learning extras -- let alone a GPU.

Exit code is 0 only when every selected target verified and (on a full run) the
hash table matched byte for byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # noqa: S404 -- runs this repo's own scripts, argv is fixed below
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
HASH_TABLE_RELATIVE: Final[str] = "docs/artifact-hashes.md"
HASH_TABLE_PATH: Final[Path] = REPO_ROOT / "docs" / "artifact-hashes.md"

# The single command REPRODUCING.md documents and CI's ``repro`` job runs, on
# both operating systems. It is one string on purpose: two OS-specific shell
# scripts would put the documented procedure and the enforced one in different
# files, and nothing could then assert they agree
# (.steering/20260912-paper03-repro-path/decisions.md DA-P03R-1).
# tests/test_architecture/test_reproducing_doc_parity.py enforces the agreement.
CANONICAL_COMMAND: Final[str] = (
    "uv run --frozen --no-dev python scripts/verify_committed_artifacts.py"
)

# Read by ``erre_sandbox.cognition.cycle`` when a cycle is constructed. Pinned
# per bundle rather than exported, see the module docstring.
ZONE_BIAS_ENV_VAR: Final[str] = "ERRE_ZONE_BIAS_P"

# Placeholder in a target's argv, replaced with a fresh temporary directory so
# a verify never rewrites the committed side annotations in place.
ANNOTATION_DIR: Final[str] = "<annotation-dir>"


@dataclass(frozen=True)
class Target:
    """One committed artifact set and the command that replay-verifies it."""

    name: str
    directory: str
    """Repository-relative directory whose files are hashed."""

    argv: tuple[str, ...]
    """Arguments after the interpreter. ``ANNOTATION_DIR`` is substituted."""

    expected_annotations: tuple[str, ...]
    """Side-annotation filenames the replay must derive, or ``()`` for none.

    Frozen rather than discovered so that a harness change which stops deriving
    an annotation is a failure, not a silently smaller check: the committed file
    would still be there, the hash table would still agree, and only the
    documented "re-derived and compared" claim would quietly become false.
    """

    description: str


TARGETS: Final[tuple[Target, ...]] = (
    Target(
        name="society-real",
        directory="experiments/20260907-m13-society-live/artifacts",
        argv=(
            "scripts/m13_society_live_capture.py",
            "--verify",
            "--real",
            "--out-dir",
            "experiments/20260907-m13-society-live/artifacts",
            "--annotation-dir",
            ANNOTATION_DIR,
        ),
        expected_annotations=(
            "plane_g_parity.json",
            "request_conformance.json",
            "firing_annotation.json",
        ),
        description=(
            "sealed real qwen3:8b + nomic-embed-text society run "
            "(N=3 agents x 12 cognition x 20 physics ticks)"
        ),
    ),
    Target(
        name="society-rehearsal",
        directory="experiments/20260907-m13-society-live/rehearsal",
        argv=(
            "scripts/m13_society_live_capture.py",
            "--verify",
            "--out-dir",
            "experiments/20260907-m13-society-live/rehearsal",
            "--annotation-dir",
            ANNOTATION_DIR,
        ),
        expected_annotations=(
            "plane_g_parity.json",
            "request_conformance.json",
            "firing_annotation.json",
        ),
        description="the Ollama-free rehearsal at the same pre-registered shape",
    ),
    Target(
        name="live-loop-real",
        directory="experiments/20260904-m13-live-loop-live/artifacts",
        argv=(
            "scripts/m13_live_loop_capture.py",
            "--verify",
            "--artifact-dir",
            "experiments/20260904-m13-live-loop-live/artifacts",
            "--annotation-dir",
            ANNOTATION_DIR,
        ),
        expected_annotations=(
            "wiring_reachability.json",
            "two_phase_firing_annotation.json",
        ),
        description="sealed real qwen3:8b live-loop run (N=1, 32 cognition ticks)",
    ),
    Target(
        name="live-loop-rehearsal",
        directory="experiments/20260904-m13-live-loop-live/rehearsal",
        argv=(
            "scripts/m13_live_loop_capture.py",
            "--verify",
            "--artifact-dir",
            "experiments/20260904-m13-live-loop-live/rehearsal",
            "--annotation-dir",
            ANNOTATION_DIR,
        ),
        expected_annotations=(
            "wiring_reachability.json",
            "two_phase_firing_annotation.json",
        ),
        description="the Ollama-free rehearsal at the same pre-registered shape",
    ),
    Target(
        name="ecl-v0-golden",
        directory="tests/fixtures/ecl_v0_golden",
        argv=(
            "scripts/ecl_v0_golden.py",
            "--verify",
            "--golden-dir",
            "tests/fixtures/ecl_v0_golden",
        ),
        expected_annotations=(),
        description="the ECL v0 golden fixture (single-agent, scripted Plane 2)",
    ),
)

# Files outside any bundle directory whose checked-out bytes a committed
# manifest pins. Keeping the rule narrow is deliberate: hashing mutable sources
# would make the table churn on every commit and mean nothing. ``uv.lock`` is
# here because every sealed manifest carries ``env_pins.uv_lock_sha256``, and
# because a checkout that rewrites its line endings silently breaks that pin
# (.steering/20260911-ci-selection-ssot/decisions.md DA-CIS-6).
PROVENANCE_PATHS: Final[tuple[str, ...]] = ("uv.lock",)


def target_by_name(name: str) -> Target:
    for target in TARGETS:
        if target.name == name:
            return target
    known = ", ".join(t.name for t in TARGETS)
    msg = f"unknown target {name!r}; known targets: {known}"
    raise KeyError(msg)


# --------------------------------------------------------------------------- #
# Hash inventory
# --------------------------------------------------------------------------- #


def hashed_paths() -> tuple[str, ...]:
    """Every repository-relative path the hash table covers, in table order.

    Bundle directories are walked **recursively** and sorted, so adding a file
    anywhere under a bundle -- including in a subdirectory that does not exist
    today -- shows up as a table change rather than slipping past the check
    (Codex independent review 2026-09-12, MEDIUM-3).
    """
    paths: list[str] = []
    for target in TARGETS:
        directory = REPO_ROOT / target.directory
        if not directory.is_dir():
            msg = f"{target.directory} is a declared target but is not a directory"
            raise FileNotFoundError(msg)
        relatives = sorted(
            entry.relative_to(directory).as_posix()
            for entry in directory.rglob("*")
            if entry.is_file()
        )
        paths.extend(f"{target.directory}/{relative}" for relative in relatives)
    paths.extend(PROVENANCE_PATHS)
    return tuple(paths)


def _sha256_and_size(relative: str) -> tuple[str, int]:
    data = (REPO_ROOT / relative).read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def render_hash_table() -> str:
    """Render ``docs/artifact-hashes.md`` from the bytes currently checked out."""
    lines: list[str] = [
        "# Expected artifact hashes",
        "",
        "<!-- GENERATED FILE -- do not edit by hand.",
        "     Regenerate with:",
        f"       {CANONICAL_COMMAND} --write-hashes",
        "-->",
        "",
        "SHA-256 and byte count of the **checked-out bytes** of every committed",
        "artifact the two-plane determinism claim rests on. `REPRODUCING.md`",
        "explains how to replay them; this file is what the replay is checked",
        "against, and `scripts/verify_committed_artifacts.py` compares the two on",
        "every run (and in CI, on `ubuntu-latest` and `windows-latest`).",
        "",
        "These are hashes of what `git checkout` puts on disk, not of the blobs.",
        "That is the point: a checkout that rewrites line endings changes them,",
        "which is exactly the defect the Windows CI leg caught in `uv.lock` on",
        "2026-09-11. `tests/test_architecture/test_reproducing_doc_parity.py`",
        "therefore also asks `git check-attr` whether each path below has a",
        "stable checkout representation.",
        "",
        "Scope rule (frozen): every file of the four committed bundles and of the",
        "ECL v0 golden fixture, plus every non-bundle file whose bytes a committed",
        "manifest pins (`uv.lock`). Source files are deliberately absent -- they",
        "change every commit, so hashing them would make this table noise.",
        "",
        "Which file is authoritative: each bundle's own `manifest.json` is the",
        "replay contract -- it pins the SHA-256 of the artifacts the replay must",
        "re-render, and the verifier checks against it. This table is a generated",
        "projection of the *checked-out bytes* on top of that, and doubles as the",
        "line-ending sentinel. It never overrides a manifest; if the two ever",
        "disagree the manifest is right and this table is stale.",
        "",
        "Not to be confused with `paper/data-hashes.md`, which is a *transport*",
        "record for the separate paper 01 / 02 repositories: it is generated by",
        "`paper/gather.ps1`, lives outside version control, and is a record rather",
        "than a check. This file is tracked and is enforced.",
        "",
        "| path | sha256 | bytes |",
        "|---|---|---|",
    ]
    for relative in hashed_paths():
        digest, size = _sha256_and_size(relative)
        lines.append(f"| `{relative}` | `{digest}` | {size} |")
    lines.append("")
    return "\n".join(lines)


def check_hash_table(table_path: Path = HASH_TABLE_PATH) -> bool:
    """Return True when ``table_path`` matches a freshly rendered table."""
    try:
        expected = render_hash_table()
    except OSError as exc:
        # A missing target directory or an unreadable artifact is a failure of
        # this check, not a crash: the caller still has to print the verdict
        # line it promised.
        print(f"FAIL [hashes] could not read the artifacts on disk: {exc}")
        return False
    if not table_path.exists():
        print(f"FAIL [hashes] {table_path} is missing; run --write-hashes")
        return False
    actual = table_path.read_text(encoding="utf-8")
    if actual == expected:
        rows = len(hashed_paths())
        print(f"PASS [hashes] {rows} artifact hashes match {HASH_TABLE_RELATIVE}")
        return True
    print(f"FAIL [hashes] {HASH_TABLE_RELATIVE} does not match the bytes on disk")
    _print_table_diff(actual=actual, expected=expected)
    return False


def _print_table_diff(*, actual: str, expected: str) -> None:
    """Print the differing lines only -- a full diff of 40 hashes is unreadable."""
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    shown = 0
    for index in range(max(len(actual_lines), len(expected_lines))):
        committed = actual_lines[index] if index < len(actual_lines) else "<missing>"
        fresh = expected_lines[index] if index < len(expected_lines) else "<missing>"
        if committed == fresh:
            continue
        shown += 1
        if shown > 10:
            print("       ... (further differences suppressed)")
            return
        print(f"       line {index + 1}:")
        print(f"         in file : {committed}")
        print(f"         on disk : {fresh}")
    if shown == 0:
        print("       (line-for-line equal; the difference is trailing whitespace)")


# --------------------------------------------------------------------------- #
# Replay-verify
# --------------------------------------------------------------------------- #


def _zone_bias_pin(target: Target) -> str | None:
    """The ``ERRE_ZONE_BIAS_P`` this bundle was baked under, from its manifest."""
    manifest_path = REPO_ROOT / target.directory / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pin = manifest.get("env_pins", {}).get(ZONE_BIAS_ENV_VAR)
    return None if pin is None else str(pin)


def compare_side_annotations(target: Target, annotation_dir: Path) -> bool:
    """Compare freshly derived side annotations against the committed ones.

    The harnesses' own ``verify`` writes a side annotation when the destination
    file is **absent** and compares it only when it is present. Pointing them at
    an empty temporary directory -- which is what keeps the committed evidence
    from being rewritten -- therefore turns their annotation step into a write,
    not a check. This function is the check: it reads what the replay just
    derived and compares it byte-for-byte with what is committed.

    Without it, "the annotations are re-derived and compared" would be an
    over-claim; the annotations would only be covered indirectly, by the hash
    table (Codex independent review 2026-09-12, HIGH-1).
    """
    derived = sorted(path for path in annotation_dir.iterdir() if path.is_file())
    ok = True
    actual = {path.name for path in derived}
    expected = set(target.expected_annotations)
    if actual != expected:
        print(
            f"FAIL [{target.name}] the replay derived {sorted(actual)} but this "
            f"target declares {sorted(expected)}. A target that stops deriving "
            f"an annotation must fail here, not quietly check less."
        )
        ok = False
    if not derived:
        # The golden fixture derives no side annotations, and says so.
        return ok
    for fresh in derived:
        committed = REPO_ROOT / target.directory / fresh.name
        if not committed.exists():
            print(
                f"FAIL [{target.name}] {fresh.name} is derived by replay but is "
                f"not committed next to the bundle"
            )
            ok = False
        elif fresh.read_bytes() != committed.read_bytes():
            print(
                f"FAIL [{target.name}] {fresh.name} differs from the committed "
                f"annotation"
            )
            ok = False
        else:
            print(f"PASS [{target.name}] {fresh.name} matches the committed bytes")
    return ok


def run_target(target: Target) -> bool:
    """Replay-verify one target in its own subprocess. Returns True on success."""
    # ``ignore_cleanup_errors``: on Windows an indexer or anti-virus can still
    # hold a handle when the block exits, and a PermissionError there would turn
    # a successful verification into a red job.
    with tempfile.TemporaryDirectory(
        prefix="erre-verify-", ignore_cleanup_errors=True
    ) as annotation_dir:
        argv = [annotation_dir if arg == ANNOTATION_DIR else arg for arg in target.argv]
        env = dict(os.environ)
        # The child writes em-dashes; Windows' legacy console codepage would
        # raise UnicodeEncodeError (memory feedback_powershell_cp932_subprocess_test).
        env["PYTHONUTF8"] = "1"
        pin = _zone_bias_pin(target)
        if pin is not None:
            env[ZONE_BIAS_ENV_VAR] = pin
        else:
            env.pop(ZONE_BIAS_ENV_VAR, None)
        pin_note = f"{ZONE_BIAS_ENV_VAR}={pin}" if pin is not None else "no env pin"
        print(f"\n=== {target.name} ({pin_note}) ===")
        print(f"    {target.description}")
        # The child writes straight to the inherited stdout. Without this flush
        # our header would sit in the parent's block buffer (CI always pipes)
        # and the child's output would appear before the header it belongs to.
        sys.stdout.flush()
        completed = subprocess.run(  # noqa: S603 -- argv is a module-level constant
            [sys.executable, *argv],
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        annotations_ok = compare_side_annotations(target, Path(annotation_dir))
    ok = completed.returncode == 0 and annotations_ok
    note = "" if annotations_ok else " (side annotations differ)"
    print(
        f"{'PASS' if ok else 'FAIL'} [{target.name}] exit {completed.returncode}{note}"
    )
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay-verify every committed artifact and check its hashes. "
            "The replay contacts no language model, no GPU and no network."
        )
    )
    parser.add_argument(
        "--only",
        metavar="TARGET",
        default=None,
        help=(
            "verify a single target instead of all of them. The hash table "
            "check is skipped, because the table covers every target."
        ),
    )
    parser.add_argument(
        "--write-hashes",
        action="store_true",
        help=f"regenerate {HASH_TABLE_RELATIVE} from the bytes on disk and exit",
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="print the target names and exit",
    )
    args = parser.parse_args(argv)

    if args.list_targets:
        for target in TARGETS:
            print(f"{target.name}\t{target.directory}\t{target.description}")
        return 0

    if args.write_hashes:
        HASH_TABLE_PATH.write_text(render_hash_table(), encoding="utf-8", newline="\n")
        print(f"[hashes] wrote {len(hashed_paths())} rows to {HASH_TABLE_RELATIVE}")
        return 0

    if args.only is not None:
        try:
            selected = (target_by_name(args.only),)
        except KeyError as exc:
            parser.error(str(exc))
    else:
        selected = TARGETS

    results = [(target.name, run_target(target)) for target in selected]

    print("\n=== summary ===")
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")

    hashes_ok = True
    if args.only is None:
        hashes_ok = check_hash_table()
    else:
        print(
            f"SKIP [hashes] {HASH_TABLE_RELATIVE} covers every target; "
            f"run without --only to check it"
        )

    ok = hashes_ok and all(ok for _, ok in results)
    print(
        "\n[verify-committed-artifacts] "
        + ("ALL OK" if ok else "FAILED")
        + " -- replay-verify of committed bytes only; this is not a re-bake"
    )
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover -- CLI entry point
    sys.exit(main())
