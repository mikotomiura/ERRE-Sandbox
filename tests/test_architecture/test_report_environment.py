"""``scripts/report_environment.py`` must be stdlib-only and public-safe.

Two properties this module exists to guarantee, both checked mechanically
rather than by inspection:

1. It runs with a bare ``python scripts/report_environment.py`` -- no ``uv``,
   no third-party import, no import from ``erre_sandbox`` -- because it is
   exactly the machine a failed ``uv sync`` most needs to report from
   (.steering/20260926-public-env-diagnostics/decisions.md D2).
2. Its output never contains a filesystem path, username or hostname. The
   allowlist keeps that true by construction (D3), but a check that only
   restates the allowlist would be self-referential and prove nothing
   (memory ``feedback_negative_fixture_must_not_be_self_referential``); the
   positive control below mutates the rendered text and checks the helper
   itself actually notices.

This also checks that ``scripts/verify_committed_artifacts.py`` prints the
same block, first, before any target -- the wiring the whole task exists for.
"""

from __future__ import annotations

import ast
import getpass
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from scripts.report_environment import HEADER, collect, render

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
REPORT_ENVIRONMENT_PATH: Final = REPO_ROOT / "scripts" / "report_environment.py"
VERIFY_COMMITTED_ARTIFACTS_PATH: Final = (
    REPO_ROOT / "scripts" / "verify_committed_artifacts.py"
)

# Written by hand, not imported from ``report_environment.ALLOWLIST_ORDER`` --
# otherwise a change to the module and to the frozen contract would be the
# same edit, and this test could never catch either one drifting alone.
EXPECTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "os.name",
        "os.release",
        "os.version",
        "os.arch",
        "c_runtime",
        "python.version",
        "python.implementation",
        "uv.version",
        "encoding.locale_preferred",
        "encoding.stdout",
        "encoding.pythonutf8",
        "source.git_checkout",
        "source.git_version",
        "source.core_autocrlf",
        "source.core_eol",
        "source.commit",
        "source.tree_clean",
        "hardware.cpu_model",
        "hardware.cpu_logical_count",
        "hardware.ram_gb",
    }
)

_SUBPROCESS_ENV: Final = {**os.environ, "PYTHONUTF8": "1"}
_PASS_OR_FAIL_LINE_RE: Final = re.compile(
    r"^(?:PASS|FAIL) \[ecl-v0-golden\] exit \d+(?: \([^)]*\))? \(\d+\.\d+s\)$"
)


def test_collect_keys_match_the_frozen_allowlist() -> None:
    """The key set is a contract; growing or shrinking it must be deliberate."""
    assert set(collect().keys()) == EXPECTED_KEYS


def test_render_starts_with_the_public_safe_header() -> None:
    rendered = render(collect())
    assert rendered.splitlines()[0] == HEADER == "=== environment (public-safe) ==="


def test_render_emits_exactly_one_line_per_allowlisted_key() -> None:
    rendered = render(collect())
    body_lines = rendered.splitlines()[1:]
    assert len(body_lines) == len(EXPECTED_KEYS)
    keys_in_output = {line.split(": ", 1)[0] for line in body_lines}
    assert keys_in_output == EXPECTED_KEYS


# --------------------------------------------------------------------------- #
# Public safety: no path, username or hostname -- checked, not assumed
# --------------------------------------------------------------------------- #


def _forbidden_values() -> dict[str, str]:
    """Values that must never appear in the rendered block.

    Very short values (e.g. a single-letter username) are skipped: they would
    make the check fail on coincidence rather than on an actual leak.
    """
    candidates = {
        "home": str(Path.home()),
        "user": getpass.getuser(),
        "host": socket.gethostname(),
        "repo_root": str(REPO_ROOT),
    }
    return {label: value for label, value in candidates.items() if len(value) >= 3}


def _assert_public_safe(rendered: str) -> None:
    for label, value in _forbidden_values().items():
        assert value not in rendered, (
            f"rendered environment block leaks {label} ({value!r})"
        )


def test_render_is_public_safe() -> None:
    _assert_public_safe(render(collect()))


def test_public_safety_helper_fails_on_an_injected_leak() -> None:
    """Positive control: the helper above must actually be able to fail.

    Without this, a helper that always passes (e.g. because of a typo) would
    look identical to a genuinely public-safe render.
    """
    forbidden = _forbidden_values()
    assert forbidden, (
        "expected at least one of home/user/host/repo_root to be long enough "
        "to test with on this machine"
    )
    label, value = next(iter(forbidden.items()))
    tampered = render(collect()) + f"\nleaked.{label}: {value}"
    with pytest.raises(AssertionError):
        _assert_public_safe(tampered)


# --------------------------------------------------------------------------- #
# Stdlib-only: parsed from the AST, not from a hand-kept list
# --------------------------------------------------------------------------- #


def _imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.partition(".")[0])
    return roots


def test_report_environment_imports_nothing_outside_the_standard_library() -> None:
    roots = _imported_top_level_modules(REPORT_ENVIRONMENT_PATH)
    assert roots, "expected scripts/report_environment.py to import something"
    non_stdlib = {root for root in roots if root not in sys.stdlib_module_names}
    assert not non_stdlib, (
        f"scripts/report_environment.py imports non-stdlib module(s) "
        f"{sorted(non_stdlib)!r}. It must run with a bare "
        f"`python scripts/report_environment.py`: no uv, no third-party "
        f"dependency, and no import from erre_sandbox."
    )


def test_report_environment_runs_standalone_with_bare_python() -> None:
    """The literal claim this module exists to satisfy: a bare interpreter."""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(REPORT_ENVIRONMENT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=_SUBPROCESS_ENV,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines()[0] == "=== environment (public-safe) ==="


# --------------------------------------------------------------------------- #
# Wiring into the verifier
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def ecl_v0_golden_only_run() -> subprocess.CompletedProcess[str]:
    """One real ``--only ecl-v0-golden`` run, shared by the tests below.

    ``ecl-v0-golden`` is the cheapest target (no real model, no rehearsal
    replay), so this stays fast while still exercising the actual CLI entry
    point rather than calling ``main()`` in-process.
    """
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(VERIFY_COMMITTED_ARTIFACTS_PATH),
            "--only",
            "ecl-v0-golden",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env=_SUBPROCESS_ENV,
        check=False,
    )


def test_verify_only_run_exits_zero(
    ecl_v0_golden_only_run: subprocess.CompletedProcess[str],
) -> None:
    assert ecl_v0_golden_only_run.returncode == 0, ecl_v0_golden_only_run.stderr


def test_verifier_prints_environment_header_before_the_first_target(
    ecl_v0_golden_only_run: subprocess.CompletedProcess[str],
) -> None:
    lines = ecl_v0_golden_only_run.stdout.splitlines()
    header_index = lines.index("=== environment (public-safe) ===")
    target_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("=== ecl-v0-golden")
    )
    assert header_index < target_index, (
        "the environment block must come before the first target so a "
        "reporter who pastes the whole log has both in one paste"
    )


def test_verify_only_run_is_public_safe(
    ecl_v0_golden_only_run: subprocess.CompletedProcess[str],
) -> None:
    _assert_public_safe(ecl_v0_golden_only_run.stdout)


def test_ecl_v0_golden_pass_line_reports_elapsed_seconds(
    ecl_v0_golden_only_run: subprocess.CompletedProcess[str],
) -> None:
    matches = [
        line
        for line in ecl_v0_golden_only_run.stdout.splitlines()
        if line.startswith(("PASS [ecl-v0-golden]", "FAIL [ecl-v0-golden]"))
    ]
    assert len(matches) == 1, (
        f"expected exactly one PASS/FAIL line for ecl-v0-golden, got {matches!r}"
    )
    assert _PASS_OR_FAIL_LINE_RE.match(matches[0]), matches[0]


def test_git_fields_are_not_borrowed_from_an_enclosing_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A ZIP/Zenodo copy unpacked inside some other git repository has no
    # ``.git`` of its own; every git-derived field must then say so rather than
    # report the outer repository's commit or status.
    from scripts import report_environment

    monkeypatch.setattr(report_environment, "_REPO_ROOT", tmp_path)
    data = collect()
    assert data["source.git_checkout"] == "no"
    for key in (
        "source.core_autocrlf",
        "source.core_eol",
        "source.commit",
        "source.tree_clean",
    ):
        assert data[key] == "n/a (not a git checkout)", key
