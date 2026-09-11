"""The documented reproduction procedure must be the one CI actually enforces.

``REPRODUCING.md`` tells a third party (a journal reviewer, in practice) exactly
what to run to check this repository's byte-exact replay claim. CI's ``repro``
job runs the same thing on ``ubuntu-latest`` and ``windows-latest``. If those two
drift, the paper's gate G5 quietly becomes a claim about a command nobody runs.

Making the entry point a single cross-platform Python command — rather than a
bash script plus a PowerShell script — is what makes that comparison expressible
at all: there is one string to compare, not one per operating system
(``.steering/20260912-paper03-repro-path/decisions.md`` DA-P03R-1/2).

The eol test here is the general form of the defect the Windows CI leg found on
2026-09-11: ``uv.lock`` was outside ``.gitattributes``' ``eol=lf`` coverage, so a
runner with ``core.autocrlf=true`` changed a pinned hash (DA-CIS-6). Rather than
maintain a second hand-written list of paths to protect, this asks the question
of **every path the hash table covers**.

``on:`` is deliberately never read from the workflow — PyYAML's YAML 1.1 rules
would turn that key into the boolean ``True``. Only ``jobs`` is touched.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

import pytest
import yaml
from scripts.verify_committed_artifacts import (
    CANONICAL_COMMAND,
    HASH_TABLE_PATH,
    TARGETS,
    check_hash_table,
    hashed_paths,
    render_hash_table,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CI_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REPRODUCING: Final = REPO_ROOT / "REPRODUCING.md"

_HASH_ROW_RE: Final = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|\s*(\d+)\s*\|$"
)
_FENCE_RE: Final = re.compile(r"^```", re.MULTILINE)


def _repro_job() -> dict:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert "repro" in jobs, (
        "the CI workflow no longer has a `repro` job. REPRODUCING.md promises a "
        "reader that public CI runs the documented command on both operating "
        "systems; without the job that promise is false."
    )
    return jobs["repro"]


def _repro_verify_command() -> str:
    """The ``run:`` line of the step that invokes the verifier."""
    steps = [
        step
        for step in _repro_job()["steps"]
        if "verify_committed_artifacts.py" in (step.get("run") or "")
    ]
    assert len(steps) == 1, (
        f"expected exactly one step in the `repro` job to invoke the verifier, "
        f"found {len(steps)}. More than one makes it ambiguous which command "
        f"REPRODUCING.md is supposed to agree with."
    )
    return str(steps[0]["run"]).strip()


def _fenced_blocks(markdown: str) -> list[str]:
    """Return the contents of every fenced code block, in order."""
    parts = _FENCE_RE.split(markdown)
    # parts alternates: prose, fenced, prose, fenced, ...
    return [part for index, part in enumerate(parts) if index % 2 == 1]


def test_reproducing_md_documents_the_command_ci_runs() -> None:
    """The command in REPRODUCING.md must be the one the `repro` job runs."""
    documented = [
        line.strip()
        for block in _fenced_blocks(REPRODUCING.read_text(encoding="utf-8"))
        for line in block.splitlines()
        if "verify_committed_artifacts.py" in line
    ]
    assert documented, (
        "REPRODUCING.md no longer shows a `verify_committed_artifacts.py` "
        "invocation in a fenced block. That command is the reproduction "
        "procedure; without it the file documents nothing runnable."
    )
    ci_command = _repro_verify_command()
    assert ci_command == CANONICAL_COMMAND, (
        f"the CI `repro` job runs a different command than the module constant.\n"
        f"  ci.yml                  : {ci_command!r}\n"
        f"  CANONICAL_COMMAND       : {CANONICAL_COMMAND!r}\n"
        f"Change both, or neither — REPRODUCING.md quotes the same string."
    )
    assert CANONICAL_COMMAND in documented, (
        f"REPRODUCING.md does not show the exact command CI runs.\n"
        f"  CI runs      : {CANONICAL_COMMAND!r}\n"
        f"  doc shows    : {documented!r}\n"
        f"A reviewer following this file must exercise the path public CI "
        f"enforces, not a near-miss of it."
    )
    for line in documented:
        assert line.startswith(CANONICAL_COMMAND), (
            f"REPRODUCING.md shows {line!r}, which is not the canonical command "
            f"with flags appended. Every documented invocation must start with "
            f"{CANONICAL_COMMAND!r} so a reader who copies any of them is on the "
            f"enforced path."
        )


def test_repro_job_installs_runtime_dependencies_only() -> None:
    """The `repro` job must install nothing beyond the runtime dependencies.

    REPRODUCING.md tells a reader that a green `repro` job is evidence that
    replaying the bundles needs no test tooling and no ML extras. A future
    `uv sync --all-groups`, or an extra `pip install`, would leave the documented
    command identical while quietly voiding that evidence — the doc-parity test
    above would not notice (Codex independent review 2026-09-12, MEDIUM-1).
    """
    runs = [str(step["run"]).strip() for step in _repro_job()["steps"] if "run" in step]
    assert runs == [
        "uv sync --frozen --no-dev",
        CANONICAL_COMMAND,
    ], (
        f"the `repro` job's run steps are {runs!r}. They must be exactly the "
        f"runtime-only sync followed by the documented command: any additional "
        f"install step, or a sync that pulls dependency groups, breaks the claim "
        f"that the replay needs neither the test tooling nor the ML extras."
    )


def test_repro_job_covers_both_operating_systems() -> None:
    """G5 rests on the procedure passing on a non-author machine of each family."""
    matrix = _repro_job()["strategy"]["matrix"]
    assert set(matrix["os"]) == {"ubuntu-latest", "windows-latest"}, (
        f"the `repro` job's OS matrix is {matrix['os']!r}. The cross-platform "
        f"claim needs both legs; dropping one silently narrows what REPRODUCING.md "
        f"says public CI enforces."
    )
    assert _repro_job()["strategy"].get("fail-fast") is False, (
        "the `repro` job must not fail-fast: which operating system failed is "
        "the information itself for a cross-platform claim."
    )


def test_target_registry_is_frozen_and_documented() -> None:
    """The five targets are pinned here and must appear in REPRODUCING.md.

    The defect this whole task exists to fix was a reproduction command that
    quietly covered a *smaller* artifact set than the claim. Deleting a target
    and regenerating the hash table would reproduce that defect with everything
    still green, so the set is frozen by name and directory, and the reader-facing
    table has to name the same directories
    (Codex independent review 2026-09-12, MEDIUM-2).
    """
    expected = {
        "society-real": "experiments/20260907-m13-society-live/artifacts",
        "society-rehearsal": "experiments/20260907-m13-society-live/rehearsal",
        "live-loop-real": "experiments/20260904-m13-live-loop-live/artifacts",
        "live-loop-rehearsal": "experiments/20260904-m13-live-loop-live/rehearsal",
        "ecl-v0-golden": "tests/fixtures/ecl_v0_golden",
    }
    actual = {target.name: target.directory for target in TARGETS}
    assert actual == expected, (
        f"the verifier's target set changed.\n  declared: {actual}\n  frozen  : "
        f"{expected}\nNarrowing it is exactly the defect this entry point was "
        f"built to remove; widening it is fine but must be a deliberate edit here."
    )
    doc = REPRODUCING.read_text(encoding="utf-8")
    for name, directory in expected.items():
        assert f"`{directory}/`" in doc or f"`{directory}`" in doc, (
            f"REPRODUCING.md does not mention {directory!r} (target {name!r}). "
            f"A reader must be able to see which artifacts the command covers."
        )


def test_every_manifest_pinned_non_bundle_file_is_in_the_table() -> None:
    """The scope rule is enforced in both directions, not just the easy one.

    The rule says the table carries every non-bundle file whose bytes a committed
    manifest pins. Checking only "uv.lock is there" would leave the rule open the
    way it was open before this task: the prose wider than the implementation.
    So every top-level ``<name>_sha256`` pin is resolved — if a file named
    ``<name>.*`` exists inside the bundle, the directory walk already covers it;
    otherwise it is a non-bundle pin and must be in the table
    (Codex MEDIUM-3, code review M-2).

    Only top-level ``env_pins`` keys are scanned. The nested
    ``fixed_constructor_fingerprint`` hashes in-memory constructor state, not
    files on disk, so it has nothing to appear in a table of file bytes.
    """
    hashed = set(hashed_paths())
    external: dict[str, str] = {}
    for target in TARGETS:
        manifest_path = REPO_ROOT / target.directory / "manifest.json"
        if not manifest_path.exists():
            continue
        pins = json.loads(manifest_path.read_text(encoding="utf-8")).get("env_pins", {})
        directory = REPO_ROOT / target.directory
        for key, value in pins.items():
            match = re.fullmatch(r"(.+)_sha256", key)
            if match is None or isinstance(value, dict):
                continue
            stem = match.group(1)
            if any(path.stem == stem for path in directory.iterdir() if path.is_file()):
                continue  # a bundle file; the directory walk covers it
            external[stem] = target.directory

    for stem, directory in sorted(external.items()):
        # "uv_lock" -> "uv.lock". A future non-bundle pin needs the same shape,
        # or this mapping has to grow deliberately.
        candidate = stem.replace("_", ".")
        assert candidate in hashed, (
            f"the manifest in {directory} pins {stem}_sha256, which names the "
            f"non-bundle file {candidate!r}, but that file is not in the hash "
            f"table. The frozen scope rule says manifest-pinned non-bundle files "
            f"belong in PROVENANCE_PATHS — add it there, or fix the name mapping."
        )
    assert "uv_lock" in external, (
        "no manifest pins uv_lock_sha256 any more; uv.lock is in PROVENANCE_PATHS "
        "because of that pin, so revisit the scope rule rather than leaving an "
        "unexplained entry."
    )


def test_uv_lock_is_hashed_because_a_manifest_pins_it() -> None:
    """The one non-bundle entry in the table follows the stated scope rule.

    The rule is "every file of the bundles, plus every non-bundle file whose
    bytes a committed manifest pins". ``uv.lock`` is in the table because the
    sealed manifests carry ``env_pins.uv_lock_sha256``; this checks that premise
    still holds rather than leaving the entry as an unexplained special case
    (Codex independent review 2026-09-12, MEDIUM-3).
    """
    pinning = [
        target.directory
        for target in TARGETS
        if (manifest := REPO_ROOT / target.directory / "manifest.json").exists()
        and "uv_lock_sha256"
        in json.loads(manifest.read_text(encoding="utf-8")).get("env_pins", {})
    ]
    assert pinning, (
        "no committed manifest pins uv_lock_sha256 any more. uv.lock is in the "
        "hash table because of that pin; if the pin is gone, revisit "
        "PROVENANCE_PATHS rather than leaving an unexplained entry."
    )
    assert "uv.lock" in hashed_paths(), (
        f"manifests in {pinning} pin uv_lock_sha256, so uv.lock's checked-out "
        f"bytes must be in the hash table."
    )


def test_hash_table_matches_the_bytes_on_disk() -> None:
    """``docs/artifact-hashes.md`` is a generated projection, kept honest here.

    This is the same check the CLI performs, run in the always-on suite so a
    regenerated bundle cannot land with a stale table.
    """
    assert check_hash_table(), (
        f"{HASH_TABLE_PATH.name} disagrees with the files on disk. If an "
        f"artifact legitimately changed, regenerate with "
        f"`{CANONICAL_COMMAND} --write-hashes` and commit the result."
    )


def test_hash_table_covers_every_declared_target() -> None:
    """The table's rows must parse, and be exactly the paths the script declares.

    The set equality is what stops a hand-added row for a path nothing verifies,
    and a target whose files never reach the list. The per-target loop below is
    weaker than it looks — once the set equality holds it can only fail for an
    empty bundle directory — so it is kept as a named check for that case rather
    than as independent evidence (code review L-8).
    """
    rows = [
        match.group(1)
        for line in HASH_TABLE_PATH.read_text(encoding="utf-8").splitlines()
        if (match := _HASH_ROW_RE.match(line.strip()))
    ]
    assert rows, "no hash rows parsed out of docs/artifact-hashes.md"
    assert tuple(rows) == hashed_paths(), (
        "docs/artifact-hashes.md's paths are not the ones the verifier declares. "
        "The table is generated; edit the target list in "
        "scripts/verify_committed_artifacts.py, not the table."
    )
    for target in TARGETS:
        assert any(path.startswith(f"{target.directory}/") for path in rows), (
            f"target {target.name!r} contributes no rows to the hash table"
        )


def _check_attr(attribute: str, path: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", "check-attr", attribute, "--", path],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout.rsplit(": ", 1)[-1].strip()


def test_every_hashed_path_has_a_stable_checkout_representation() -> None:
    """A SHA-256 of checked-out bytes is only meaningful if git cannot rewrite them.

    Skipped when there is no git work tree -- an unpacked source archive (the
    Zenodo tarball a reviewer may download) has the files but not the metadata
    this asks about. Every clone, and both CI legs, still run it.

    Two settings are safe: ``text`` unset (git stores and restores bytes
    verbatim), or ``text`` set together with ``eol=lf``. ``unspecified`` hands
    the decision to the local ``core.autocrlf`` — which is ``input`` on the
    author's machine and ``true`` on GitHub's Windows runner.
    """
    if not (REPO_ROOT / ".git").exists() or shutil.which("git") is None:
        pytest.skip("checkout-representation guard needs a git work tree")
    for relative in hashed_paths():
        text = _check_attr("text", relative)
        eol = _check_attr("eol", relative)
        stable = text == "unset" or (text == "set" and eol == "lf")
        assert stable, (
            f"{relative} is hashed in docs/artifact-hashes.md but has an "
            f"unstable checkout representation (text={text!r}, eol={eol!r}). "
            f"Add a rule to .gitattributes (`text eol=lf`, or `binary` for a "
            f"real binary), or the hash holds only on machines that happen to "
            f"share the author's core.autocrlf."
        )


def test_hash_check_fails_on_a_tampered_table(tmp_path: Path) -> None:
    """The comparison is not tautological: a single altered character fails it.

    Uses a copy so the committed table is never touched. A witness that passes
    whatever it is shown is worth nothing
    (memory ``feedback_witness_needs_mutation_testing``).
    """
    good = render_hash_table()
    copy = tmp_path / "artifact-hashes.md"
    copy.write_text(good, encoding="utf-8", newline="\n")
    assert check_hash_table(copy) is True, "an unmodified copy must pass"

    digest = re.search(r"`([0-9a-f]{64})`", good)
    assert digest is not None, "expected at least one SHA-256 in the rendered table"
    original = digest.group(1)
    flipped = ("0" if original[0] != "0" else "1") + original[1:]
    copy.write_text(good.replace(original, flipped, 1), encoding="utf-8", newline="\n")
    assert check_hash_table(copy) is False, (
        "flipping one character of one SHA-256 did not fail the check — the "
        "comparison is not looking at what it claims to look at"
    )

    copy.unlink()
    assert check_hash_table(copy) is False, "a missing table must fail, not pass"
