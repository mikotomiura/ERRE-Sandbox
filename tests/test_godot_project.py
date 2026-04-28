"""T15/T16 godot-project scaffold guardrails.

1. Required files exist (``project.godot`` / ``MainScene.tscn`` / T16 scripts).
2. No Python files under ``godot_project/`` (architecture-rules enforcement).
3. Godot 4.x opens the project headlessly without errors. Skipped if Godot
   is not installed on the local machine, so CI without Godot stays green.
4. M9-A regression: non-spatial trigger payloads with ``zone=null`` /
   ``ref_id=null`` must not crash ``EnvelopeRouter.on_envelope_received``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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


@pytest.mark.godot
def test_envelope_router_null_trigger_fields_do_not_crash(tmp_path: Path) -> None:
    """M9-A regression: non-spatial trigger_event with explicit JSON null.

    Live G-GEAR run on 2026-04-28 hit
    ``EnvelopeRouter.on_envelope_received: Trying to assign value of type
    'Nil' to a variable of type 'String'`` because
    ``Dictionary.get(key, default)`` in GDScript returns the actual ``null``
    when the key is present-but-null (default only kicks in for missing
    keys). The hotfix routes through ``Variant`` and coerces empty-or-null
    to ``""``; this test pins that behaviour by driving
    ``EnvelopeRouter.on_envelope_received`` directly with a non-spatial
    trigger payload and asserting (a) no GDScript runtime error and
    (b) no ``zone_pulse_requested`` emission for the non-spatial kind.
    """
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    script = tmp_path / "null_trigger_regression.gd"
    script.write_text(
        """extends SceneTree

# GDScript 4 lambdas capture by value, not by reference, so we use SceneTree
# instance vars + named handlers to count signal emissions deterministically.
var _pulse_count: int = 0
var _reasoning_count: int = 0


func _on_pulse(_agent: String, _kind: String, _zone: String, _tick: int) -> void:
\t_pulse_count += 1


func _on_reasoning(_agent: String, _tick: int, _trace: Dictionary) -> void:
\t_reasoning_count += 1


func _init() -> void:
\tvar Router := load("res://scripts/EnvelopeRouter.gd")
\tvar router = Router.new()
\troot.add_child(router)
\trouter.zone_pulse_requested.connect(_on_pulse)
\trouter.reasoning_trace_received.connect(_on_reasoning)
\trouter.on_envelope_received({
\t\t"kind": "reasoning_trace",
\t\t"tick": 42,
\t\t"trace": {
\t\t\t"agent_id": "a_kant_001",
\t\t\t"tick": 42,
\t\t\t"mode": "shu_kata",
\t\t\t"trigger_event": {
\t\t\t\t"kind": "biorhythm",
\t\t\t\t"zone": null,
\t\t\t\t"ref_id": null,
\t\t\t\t"secondary_kinds": [],
\t\t\t},
\t\t},
\t})
\tif _reasoning_count != 1:
\t\tpush_error("expected 1 reasoning_trace_received, got %d" % _reasoning_count)
\t\tquit(1)
\t\treturn
\tif _pulse_count != 0:
\t\tpush_error(
\t\t\t"non-spatial null-zone trigger emitted phantom pulse (count=%d)"
\t\t\t% _pulse_count
\t\t)
\t\tquit(1)
\t\treturn
\tquit(0)
""",
        encoding="utf-8",
    )

    # All argv from known locations (resolve_godot path, fixed project path,
    # tmp_path written by this test). No user-supplied input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "--script",
            str(script),
        ],
        capture_output=True,
        text=True,
        timeout=HEADLESS_TIMEOUT_SEC,
        check=False,
    )
    assert result.returncode == 0, (
        f"null-trigger regression script failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # The exact wording of the original crash, must not reappear.
    assert "Trying to assign value of type 'Nil'" not in result.stderr, (
        f"Nil→String type error reproduced:\n{result.stderr}"
    )
    # Any GDScript ERROR: line is also a regression of the hotfix's intent.
    assert "ERROR:" not in result.stderr, (
        f"Godot emitted runtime errors:\n{result.stderr}"
    )
