"""T17 godot-peripatos-scene: headless fixture-replay regression for 3D wiring.

Runs the same ``FixtureHarness.tscn`` as ``test_godot_ws_client`` but asserts
the Peripatos scene spawned, the Kant avatar was lazily instantiated, and each
Router signal actually reached the avatar with the envelope's payload intact
(most importantly the move ``speed`` from ``move.json`` = 1.3).

A module-scoped fixture runs the Godot subprocess once and shares the captured
stdout/stderr across the six ``test_*`` functions, keeping CI time bounded
while expanding coverage versus T16.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from tests._godot_helpers import (
    FIXTURES_CONTROL_ENVELOPE,
    GODOT_PROJECT,
    HEADLESS_TIMEOUT_SEC,
    resolve_godot,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.godot


@pytest.fixture(scope="module")
def harness_result() -> Iterator[subprocess.CompletedProcess[str] | None]:
    """Launch FixtureHarness.tscn once; ``None`` if Godot is unavailable.

    Individual ``test_*`` functions ``pytest.skip`` on ``None`` so the module
    stays CI-friendly on hosts without Godot installed.
    """
    godot = resolve_godot()
    if godot is None:
        yield None
        return
    if not FIXTURES_CONTROL_ENVELOPE.is_dir():
        yield None
        return
    # argv comes from resolve_godot (fixed paths) + repo-local paths, not user input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "res://scenes/dev/FixtureHarness.tscn",
            "--",
            f"--fixture-dir={FIXTURES_CONTROL_ENVELOPE}",
        ],
        capture_output=True,
        text=True,
        timeout=HEADLESS_TIMEOUT_SEC,
        check=False,
    )
    yield result


def _combined(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        pytest.skip("Godot not installed or fixtures missing")
    return f"{result.stdout}\n{result.stderr}"


def test_zone_spawned_on_boot(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    combined = _combined(harness_result)
    assert "[WorldManager] zone spawned name=peripatos" in combined, (
        "Peripatos was not spawned under ZoneManager on boot:\n" + combined
    )


def test_avatar_spawned_lazily(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    combined = _combined(harness_result)
    assert "[AgentManager] avatar spawned agent_id=a_kant_001" in combined, (
        "Kant avatar was not instantiated on first agent_update:\n" + combined
    )


def test_move_uses_envelope_speed(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """Guard against V1-W2: envelope ``speed`` must reach AgentController.

    ``fixtures/control_envelope/move.json`` carries ``speed=1.3``; the
    controller prints it with ``%.2f``, so we expect ``speed=1.30``.
    """
    combined = _combined(harness_result)
    assert "speed=1.30" in combined, (
        "envelope speed=1.3 did not reach AgentController.set_move_target:\n" + combined
    )


def test_speech_reaches_avatar(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    combined = _combined(harness_result)
    assert "[AgentController] speech agent_id=a_kant_001 zone=peripatos" in combined, (
        "Kant speech was not routed to the avatar:\n" + combined
    )


def test_animation_set(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    combined = _combined(harness_result)
    assert "[AgentController] animation agent_id=a_kant_001 name=walk" in combined, (
        "walk animation change did not reach AgentController:\n" + combined
    )


def test_no_errors_and_clean_exit(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    combined = _combined(harness_result)  # centralises the skip-when-None logic
    assert harness_result is not None  # narrow the type for mypy after _combined
    assert harness_result.returncode == 0, (
        f"Fixture harness exited with rc={harness_result.returncode}:\n{combined}"
    )
    assert "ERROR:" not in harness_result.stderr, (
        f"Fixture run emitted engine-level errors:\n{harness_result.stderr}"
    )
