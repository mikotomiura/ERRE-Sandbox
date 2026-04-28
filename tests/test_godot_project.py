"""T15/T16 godot-project scaffold guardrails.

1. Required files exist (``project.godot`` / ``MainScene.tscn`` / T16 scripts).
2. No Python files under ``godot_project/`` (architecture-rules enforcement).
3. Godot 4.x opens the project headlessly without errors. Skipped if Godot
   is not installed on the local machine, so CI without Godot stays green.
"""

from __future__ import annotations

import subprocess

import pytest

from tests._godot_helpers import (
    GODOT_PROJECT,
    HEADLESS_TIMEOUT_SEC,
    resolve_godot,
)


def test_required_project_files_exist() -> None:
    # T15 scaffold
    assert (GODOT_PROJECT / "project.godot").is_file()
    assert (GODOT_PROJECT / "scenes" / "MainScene.tscn").is_file()
    assert (GODOT_PROJECT / "icon.svg").is_file()
    assert (GODOT_PROJECT / "scripts" / "WorldManager.gd").is_file()
    # T16 production scripts
    assert (GODOT_PROJECT / "scripts" / "WebSocketClient.gd").is_file()
    assert (GODOT_PROJECT / "scripts" / "EnvelopeRouter.gd").is_file()
    assert (GODOT_PROJECT / "scripts" / "AgentManager.gd").is_file()
    # T16 developer fixture harness
    assert (GODOT_PROJECT / "scripts" / "dev" / "FixturePlayer.gd").is_file()
    assert (GODOT_PROJECT / "scenes" / "dev" / "FixtureHarness.tscn").is_file()
    # T17 peripatos scene + avatar prefab + controller
    assert (GODOT_PROJECT / "scenes" / "zones" / "Peripatos.tscn").is_file()
    assert (GODOT_PROJECT / "scenes" / "agents" / "AgentAvatar.tscn").is_file()
    assert (GODOT_PROJECT / "scripts" / "AgentController.gd").is_file()


def test_godot_project_contains_no_python() -> None:
    """architecture-rules: ``godot_project/`` must not contain Python files.

    Python-Godot communication is via WebSocket (schemas.py ControlEnvelope),
    not direct import. See ``.claude/skills/architecture-rules/SKILL.md``.
    """
    py_files = sorted(GODOT_PROJECT.rglob("*.py"))
    assert py_files == [], f"Python files found under godot_project/: {py_files}"


@pytest.mark.godot
def test_godot_project_boots_headless() -> None:
    godot = resolve_godot()
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
        timeout=HEADLESS_TIMEOUT_SEC,
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
