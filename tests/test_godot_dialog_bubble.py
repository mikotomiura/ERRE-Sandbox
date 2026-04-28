"""M5 godot-zone-visuals: dialog_turn delegation chain regression.

Launches the same ``FixtureHarness.tscn`` as ``test_godot_peripatos`` and
asserts that a ``dialog_turn`` envelope propagates all the way from the
EnvelopeRouter signal through AgentManager routing and AgentController
delegation into the new ``DialogBubble`` Label3D. Each hop prints a
distinct ``[Prefix]`` line, so a test failure localises the break cleanly.

FixturePlayer.gd::DEFAULT_PLAYLIST was extended in M5 to include
``dialog_turn.json`` (and its siblings), so no harness forking is needed.
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
    """Launch FixtureHarness.tscn once; ``None`` if Godot is unavailable."""
    godot = resolve_godot()
    if godot is None:
        yield None
        return
    if not FIXTURES_CONTROL_ENVELOPE.is_dir():
        yield None
        return
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


def test_agent_manager_routes_dialog_turn(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """AgentManager must connect ``dialog_turn_received`` and dispatch."""
    combined = _combined(harness_result)
    # dialog_turn.json has speaker_id=a_kant_001 and a Latin utterance.
    assert "[AgentController] show_dialog_turn agent_id=a_kant_001" in combined, (
        "dialog_turn envelope did not reach AgentController via AgentManager:\n"
        + combined
    )


def test_dialog_bubble_invoked_on_speaker(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """DialogBubble.show_for must be invoked with the envelope utterance."""
    combined = _combined(harness_result)
    assert "[DialogBubble] show agent_id=a_kant_001" in combined, (
        "DialogBubble child did not receive the dialog_turn utterance:\n" + combined
    )


def test_no_unknown_kind_warning(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """EnvelopeRouter must recognise every kind in the extended playlist."""
    combined = _combined(harness_result)
    assert "Unknown kind" not in combined, (
        "EnvelopeRouter reported an unknown kind (playlist drift?):\n" + combined
    )
