"""Guard against drift between the CI test selection and the pre-push scripts.

``.github/workflows/ci.yml``'s ``test`` job owns the source-of-truth for which
tests run. ``scripts/dev/pre-push-check.ps1`` and ``.sh`` — the gate CLAUDE.md
points at for "run CI's conditions locally before pushing" — hand-copy the same
marker expression. Without this test a CI change silently leaves both scripts
stale, which is exactly what happened: they passed ``--ignore=tests/test_godot``
for a directory that **does not exist**, so the flag was a no-op while the step
label claimed "(non-godot)". A Godot install on the author's machine then turned
previously self-skipping tests live and a docs-only change failed pre-push
(``.steering/20260911-paper03-two-plane-determinism/blockers.md`` B-P03-6).

The shape here follows ``tests/test_envelope_kind_sync.py``: parse the SSOT,
parse the follower, compare the extracted values. Everything runs in pure Python
with ``pyyaml`` (a core dependency) and ``tomllib`` (stdlib), so it is cheap and
always-on in CI.

``on:`` is deliberately never read — PyYAML's YAML 1.1 rules would turn that key
into the boolean ``True`` (Codex LOW-1). Only ``jobs`` is touched.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Final

import yaml

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CI_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PRE_PUSH_PS1: Final = REPO_ROOT / "scripts" / "dev" / "pre-push-check.ps1"
PRE_PUSH_SH: Final = REPO_ROOT / "scripts" / "dev" / "pre-push-check.sh"
PYPROJECT: Final = REPO_ROOT / "pyproject.toml"

# The markers CI deselects by default. Kept as an explicit list rather than
# "every marker registered in pyproject" so that adding a *classifying* marker
# later (``slow``, say) does not silently become an exclusion obligation
# (Codex MEDIUM-7). Widening or narrowing CI's selection therefore requires
# editing this set on purpose, and the test below says so by name.
CI_DEFAULT_OFF_MARKERS: Final[frozenset[str]] = frozenset(
    {"godot", "eval", "spike", "training", "inference"}
)

# The replay-verify tests that carry gate G1 of paper 03 (cross-platform
# byte-identical replay of the committed bundles). If a future marker were to
# deselect these, both CI legs could stay green while the paper's evidence
# quietly left the run (Codex MEDIUM-5).
G1_WITNESS_NODE_IDS: Final[tuple[str, ...]] = (
    "tests/test_integration/test_m13_society_live_capture.py::test_committed_rehearsal_bundle_verifies",
    "tests/test_integration/test_m13_society_live_capture.py::test_committed_sealed_real_bundle_verifies",
    "tests/test_integration/test_m13_live_loop_capture.py::test_committed_sealed_real_bundle_verifies",
)

# Reader-facing files that quote the selection verbatim. They are *allowed* to
# restate it — a third party reproducing the suite should not have to chase a
# workflow file to learn what to run (paper 03 gates G5/G7) — but the copy has
# to stay true, which is what the test below enforces. Before this guard
# existed, all four carried `-m "not godot"`, missing four of the five markers
# CI actually deselects (Codex MEDIUM-6).
CANONICAL_EXPRESSION_DOCS: Final[tuple[str, ...]] = (
    "README.md",
    "README.ja.md",
    "docs/architecture.md",
    "docs/development-guidelines.md",
)

_PS1_MARKER_RE: Final = re.compile(
    r'^\$CiMarkerExpression\s*=\s*"([^"]+)"', re.MULTILINE
)
_SH_MARKER_RE: Final = re.compile(r'^CI_MARKER_EXPRESSION="([^"]+)"', re.MULTILINE)
_CLI_MARKER_RE: Final = re.compile(r'-m\s+"([^"]+)"')
_IGNORE_PATH_RE: Final = re.compile(r"--ignore=(\S+)")
_NEGATED_MARKER_RE: Final = re.compile(r"not\s+([A-Za-z_][A-Za-z0-9_]*)")


def _ci_test_job() -> dict:
    """Return the ``test`` job of the CI workflow (the selection SSOT)."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["test"]


def _ci_marker_expression() -> str:
    """Extract the ``-m "..."`` expression from the CI ``test`` job's pytest step.

    Scoped to steps whose ``run`` invokes pytest so the step's ``name`` (which
    restates the expression for the Checks UI) cannot be picked up instead.
    """
    steps = [s for s in _ci_test_job()["steps"] if "pytest" in (s.get("run") or "")]
    assert len(steps) == 1, (
        f"expected exactly one pytest step in the CI test job, found {len(steps)}. "
        f"A second invocation means the selection SSOT is ambiguous."
    )
    found = _CLI_MARKER_RE.findall(steps[0]["run"])
    assert len(found) == 1, (
        f'expected exactly one -m "..." in the CI pytest step, found {found!r}'
    )
    return found[0]


def _negated_markers(expression: str) -> frozenset[str]:
    """Parse ``not a and not b and ...`` into ``{a, b, ...}``.

    Every conjunct must be a bare negation. A term that is *not* negated (a
    ``godot and not eval ...`` drift) raises rather than being silently ignored,
    so the caller's set-equality assertion cannot be satisfied by an expression
    that selects the very markers CI means to drop.
    """
    markers: set[str] = set()
    for conjunct in expression.split(" and "):
        term = conjunct.strip()
        match = _NEGATED_MARKER_RE.fullmatch(term)
        assert match is not None, (
            f"CI selection term {term!r} is not a bare negation. The expression "
            f"must read 'not <marker> and not <marker> ...' so that this test "
            f"can tell 'deselected' from 'selected'. Full expression: {expression!r}"
        )
        markers.add(match.group(1))
    return frozenset(markers)


def _script_sources() -> dict[Path, str]:
    return {
        PRE_PUSH_PS1: PRE_PUSH_PS1.read_text(encoding="utf-8"),
        PRE_PUSH_SH: PRE_PUSH_SH.read_text(encoding="utf-8"),
    }


def _executable_lines(source: str) -> str:
    """Drop whole-line comments (both scripts comment with a leading ``#``).

    Without this, prose explaining the *historical* bug — which necessarily
    quotes ``--ignore=tests/test_godot`` — would itself trip the no-op-ignore
    check below. The same trap is recorded for the eval-egress grep gate in
    memory ``feedback_eval_egress_grep_gate_comment_literal``: a guard that
    reads comments punishes documenting the thing it guards against.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


def _script_marker_expressions() -> dict[Path, str]:
    """Extract the pinned marker expression from each pre-push script."""
    sources = _script_sources()
    found: dict[Path, str] = {}
    for path, pattern in ((PRE_PUSH_PS1, _PS1_MARKER_RE), (PRE_PUSH_SH, _SH_MARKER_RE)):
        matches = pattern.findall(_executable_lines(sources[path]))
        assert len(matches) == 1, (
            f"{path.name} must pin the CI marker expression exactly once via the "
            f"documented variable ({pattern.pattern!r}); found {matches!r}"
        )
        found[path] = matches[0]
    return found


def test_pre_push_scripts_use_the_ci_marker_expression() -> None:
    """Both pre-push scripts must run exactly the selection CI runs."""
    ci_expression = _ci_marker_expression()
    for path, script_expression in _script_marker_expressions().items():
        assert script_expression == ci_expression, (
            f"CI selection drift detected in {path.name}.\n"
            f"  ci.yml (SSOT): {ci_expression!r}\n"
            f"  {path.name}:   {script_expression!r}\n"
            f"Update the script to match ci.yml — ci.yml is the source of truth "
            f"(.steering/20260911-ci-selection-ssot/decisions.md DA-CIS-1)."
        )


def test_reader_facing_docs_quote_the_ci_marker_expression() -> None:
    """Docs that spell out ``pytest -m "..."`` must spell out CI's actual one.

    A stale copy here is worse than no copy: it is a runnable command that
    silently selects tests whose extras the reader has not installed.
    """
    ci_expression = _ci_marker_expression()
    for relative in CANONICAL_EXPRESSION_DOCS:
        path = REPO_ROOT / relative
        assert path.exists(), f"{relative} is listed here but does not exist"
        quoted = _CLI_MARKER_RE.findall(path.read_text(encoding="utf-8"))
        assert quoted, (
            f'{relative} no longer quotes a `pytest -m "..."` selection. If the '
            f"mention was removed on purpose, drop it from "
            f"CANONICAL_EXPRESSION_DOCS as well."
        )
        for expression in quoted:
            assert expression == ci_expression, (
                f"CI selection drift detected in {relative}.\n"
                f"  ci.yml (SSOT): {ci_expression!r}\n"
                f"  {relative}:    {expression!r}"
            )


def test_ci_selection_negates_exactly_the_default_off_markers() -> None:
    """The CI expression must negate every default-off marker, and only those."""
    negated = _negated_markers(_ci_marker_expression())
    assert negated == CI_DEFAULT_OFF_MARKERS, (
        f"CI selection no longer matches the declared default-off marker set.\n"
        f"  negated by ci.yml : {sorted(negated)}\n"
        f"  declared here     : {sorted(CI_DEFAULT_OFF_MARKERS)}\n"
        f"If this change is intended, edit CI_DEFAULT_OFF_MARKERS deliberately — "
        f"widening CI's exclusions is a decision, not a detail."
    )


def test_default_off_markers_are_registered_in_pyproject() -> None:
    """Every marker CI deselects must actually be a registered pytest marker.

    ``--strict-markers`` is on, so an unregistered name in the expression would
    only surface as a runtime error on the day someone uses it.
    """
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    registered = {
        entry.split(":", 1)[0].strip()
        for entry in config["tool"]["pytest"]["ini_options"]["markers"]
    }
    missing = CI_DEFAULT_OFF_MARKERS - registered
    assert not missing, (
        f"CI deselects marker(s) that pyproject.toml does not register: "
        f"{sorted(missing)}. Registered: {sorted(registered)}"
    )


def test_pre_push_scripts_enable_python_utf8_mode_before_pytest() -> None:
    """Both scripts must turn on UTF-8 mode, and do it before pytest starts.

    Checked syntactically rather than by mere substring presence: bash needs the
    assignment ``export``-ed to reach the child process, and either script could
    set it *after* the pytest step and have no effect (Codex MEDIUM-3).
    """
    sources = _script_sources()
    assignments = {
        PRE_PUSH_PS1: '$env:PYTHONUTF8 = "1"',
        PRE_PUSH_SH: "export PYTHONUTF8=1",
    }
    for path, assignment in assignments.items():
        source = _executable_lines(sources[path])
        assign_at = source.find(assignment)
        assert assign_at != -1, (
            f"{path.name} must set UTF-8 mode as `{assignment}` so the pytest "
            f"child process inherits it (memory "
            f"feedback_powershell_cp932_subprocess_test)."
        )
        pytest_at = source.find("-m pytest")
        assert pytest_at != -1, f"{path.name} no longer invokes pytest"
        assert assign_at < pytest_at, (
            f"{path.name} sets PYTHONUTF8 after it launches pytest, so the "
            f"setting has no effect on the run it is meant to fix."
        )


def test_ci_test_job_sets_python_utf8_mode() -> None:
    """CI itself must set ``PYTHONUTF8=1``.

    This is what makes the scripts' assignment *parity* rather than an extra
    local env var. Measuring parity while setting variables CI does not set is
    the mistake recorded in memory ``feedback_pre_push_script_ci_drift``.
    """
    env = _ci_test_job().get("env") or {}
    assert str(env.get("PYTHONUTF8")) == "1", (
        f'the CI test job must set PYTHONUTF8: "1"; found env={env!r}. '
        f"Without it the pre-push scripts' PYTHONUTF8=1 is an extra local "
        f"variable rather than a faithful copy of CI."
    )


def test_pre_push_scripts_pass_no_nonexistent_ignore_path() -> None:
    """Any ``--ignore=<path>`` in the scripts must point at something real.

    This pins the *class* of the original bug: ``--ignore=tests/test_godot``
    silently did nothing because no such directory exists.
    """
    for path, source in _script_sources().items():
        for ignored in _IGNORE_PATH_RE.findall(_executable_lines(source)):
            target = REPO_ROOT / ignored
            assert target.exists(), (
                f"{path.name} passes --ignore={ignored} but that path does not "
                f"exist, so the flag is a silent no-op. Use marker selection "
                f"(-m) instead, or fix the path."
            )


def test_g1_witness_tests_survive_the_ci_selection() -> None:
    """The paper-03 replay-verify witnesses must be selected by CI's expression.

    Runs pytest's own collector rather than inspecting markers by hand, so a
    marker applied from a conftest or a future plugin is caught too.
    """
    witness_files = sorted({node.split("::", 1)[0] for node in G1_WITNESS_NODE_IDS})
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            _ci_marker_expression(),
            *witness_files,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, (
        f"collect-only failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    collected = result.stdout.replace("\\", "/")
    for node_id in G1_WITNESS_NODE_IDS:
        assert node_id in collected, (
            f"{node_id} is no longer selected by the CI marker expression. "
            f"Gate G1 of paper 03 rests on this test running in public CI on "
            f"both OS legs; a green CI without it proves nothing about "
            f"cross-platform replay."
        )
