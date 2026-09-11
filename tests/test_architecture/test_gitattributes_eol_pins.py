"""Every SHA-256-pinned file must survive checkout on any platform unchanged.

The determinism apparatus pins ``uv_lock_sha256`` inside its manifests, and
``paper/data-hashes.md`` pins a SHA-256 plus a byte count for each artifact it
ships to the paper repositories. Both are hashes of *checked-out bytes*, so any
file whose line endings git is free to rewrite has an unstable pin.

``.gitattributes`` already forces ``eol=lf`` for the extensions that carry
bundle artifacts, and says why. What it missed was the files with no extension
(or an extension not in that list). GitHub's ``windows-latest`` image sets
``core.autocrlf=true``, so on 2026-09-11 the Windows CI leg computed
``uv_lock_sha256 = a08cda6d…`` (449,321 B, CRLF) against a committed
``9cc70f9d…`` (445,491 B, LF) and
``test_m13_live_loop_capture.py::test_committed_rehearsal_is_rebakeable``
failed. The author's machine never saw it: ``core.autocrlf=input`` there leaves
the working tree in LF.

This test is the backstop for that class. It asks git itself what attributes
apply, rather than pattern-matching ``.gitattributes`` by hand, so a rule that
is present but shadowed by a later rule is still caught.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

# Files whose checked-out bytes are hashed somewhere durable. Extend this list
# whenever a new artifact gets a pinned SHA-256.
EOL_PINNED_PATHS: Final[tuple[str, ...]] = (
    # Hashed by the capture harnesses into every sealed manifest's env_pins.
    "uv.lock",
    # Pinned with SHA-256 + byte count in paper/data-hashes.md.
    "pyproject.toml",
    "LICENSE",
    "LICENSE-MIT",
    "experiments/20260907-paper01-g1/SEED",
    # The committed replay bundles that gate G1 of paper 03 rests on.
    "experiments/20260907-m13-society-live/artifacts/manifest.json",
    "experiments/20260907-m13-society-live/artifacts/ecl_trace.jsonl",
    "experiments/20260904-m13-live-loop-live/artifacts/manifest.json",
)


def _check_attr(attribute: str, path: str) -> str:
    """Return git's effective value of ``attribute`` for ``path``."""
    result = subprocess.run(  # noqa: S603
        ["git", "check-attr", attribute, "--", path],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    # Output shape: "<path>: <attribute>: <value>"
    return result.stdout.rsplit(": ", 1)[-1].strip()


def test_sha_pinned_files_have_stable_line_endings_on_checkout() -> None:
    """Git must not be free to rewrite line endings in a SHA-pinned file.

    Two settings are safe: ``text`` set together with ``eol=lf`` (git always
    writes LF), or ``text`` unset (git treats the file as binary and never
    converts). ``unspecified`` is the dangerous one — it hands the decision to
    the local ``core.autocrlf``, which differs between the author's machine and
    the Windows CI runner.
    """
    for relative in EOL_PINNED_PATHS:
        assert (REPO_ROOT / relative).exists(), (
            f"{relative} is listed as SHA-pinned but does not exist"
        )
        text = _check_attr("text", relative)
        eol = _check_attr("eol", relative)
        stable = text == "unset" or (text == "set" and eol == "lf")
        assert stable, (
            f"{relative} has an unstable checkout representation "
            f"(text={text!r}, eol={eol!r}).\n"
            f"Its SHA-256 is pinned, so a checkout that rewrites line endings "
            f"changes the hash. GitHub's windows-latest runner defaults to "
            f"core.autocrlf=true, so 'unspecified' means the pin holds on the "
            f"author's machine and breaks in Windows CI. Add a rule to "
            f".gitattributes (`text eol=lf`, or `binary` for real binaries)."
        )


def test_forensic_run_logs_are_excluded_from_eol_conversion() -> None:
    """Raw run logs are verbatim evidence and must never be normalised.

    This is the mirror image of the rule above: for these, ``text`` must be
    *unset* so git stores exactly what the run emitted, trailing carriage
    returns included (memory ``feedback_forensic_raw_log_whitespace``).
    """
    sample = "experiments/20260907-m13-society-live/sealed-run.log"
    assert (REPO_ROOT / sample).exists(), f"{sample} is missing"
    text = _check_attr("text", sample)
    assert text == "unset", (
        f"{sample} has text={text!r}; forensic run logs must be `-text` so "
        f"their bytes are preserved verbatim."
    )
