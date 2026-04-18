"""T15 godot-project-init: validate the ``godot_project/`` scaffold.

Three checks:

1. Required files exist (``project.godot`` / ``MainScene.tscn`` / ``icon.svg``).
2. No Python files under ``godot_project/`` (architecture-rules enforcement).
3. Godot 4.x opens the project headlessly without errors. Skipped if Godot
   is not installed on the local machine, so CI without Godot stays green.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GODOT_PROJECT = REPO_ROOT / "godot_project"
GODOT_BIN_MAC = Path("/Applications/Godot.app/Contents/MacOS/Godot")
_HEADLESS_TIMEOUT_SEC = 60


def _resolve_godot() -> Path | None:
    """Locate a Godot binary via ``GODOT_BIN`` env var, known Mac path, or PATH."""
    override = os.environ.get("GODOT_BIN")
    if override:
        override_path = Path(override)
        return override_path if override_path.exists() else None
    if GODOT_BIN_MAC.exists():
        return GODOT_BIN_MAC
    found = shutil.which("godot")
    return Path(found) if found else None


def test_required_project_files_exist() -> None:
    assert (GODOT_PROJECT / "project.godot").is_file()
    assert (GODOT_PROJECT / "scenes" / "MainScene.tscn").is_file()
    assert (GODOT_PROJECT / "icon.svg").is_file()
    assert (GODOT_PROJECT / "scripts" / "WorldManager.gd").is_file()


def test_godot_project_contains_no_python() -> None:
    """architecture-rules: ``godot_project/`` must not contain Python files.

    Python-Godot communication is via WebSocket (schemas.py ControlEnvelope),
    not direct import. See ``.claude/skills/architecture-rules/SKILL.md``.
    """
    py_files = sorted(GODOT_PROJECT.rglob("*.py"))
    assert py_files == [], f"Python files found under godot_project/: {py_files}"


def test_godot_project_boots_headless() -> None:
    godot = _resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")
    # All argv elements come from known locations (fixed path, PATH lookup, or
    # a GODOT_BIN env var set by the developer), not from user-supplied input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "--quit",
        ],
        capture_output=True,
        text=True,
        timeout=_HEADLESS_TIMEOUT_SEC,
        check=False,
    )
    assert result.returncode == 0, (
        f"Godot headless boot failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Some Godot errors are logged to stderr while returning rc=0; treat the
    # presence of "ERROR:" as a boot failure too.
    assert "ERROR:" not in result.stderr, (
        f"Godot headless boot emitted errors on stderr:\n{result.stderr}"
    )
