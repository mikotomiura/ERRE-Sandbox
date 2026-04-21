"""M5 godot-zone-visuals: ERRE-mode tint delegation chain regression.

``agent_update.json`` carries ``agent_state.erre.name = "peripatetic"``, so a
single fixture replay should walk the full chain:

    EnvelopeRouter.agent_updated
      → AgentManager._on_agent_updated
          → AgentController.apply_erre_mode
              → BodyTinter.apply_mode (material_override.albedo_color tween)

Each hop prints a distinct ``[Prefix]`` line, matching the pattern used by
``test_godot_peripatos`` and ``test_godot_dialog_bubble``.
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


@pytest.fixture(scope="module")
def harness_result() -> Iterator[subprocess.CompletedProcess[str] | None]:
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


def test_agent_controller_applies_erre_mode(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """AgentManager must extract ``erre.name`` and delegate to the controller."""
    combined = _combined(harness_result)
    assert (
        "[AgentController] apply_erre_mode agent_id=a_kant_001 mode=peripatetic"
        in combined
    ), "AgentController.apply_erre_mode was not invoked from agent_update:\n" + combined


def test_body_tinter_applies_color(
    harness_result: subprocess.CompletedProcess[str] | None,
) -> None:
    """BodyTinter must log the tint application with the expected mode."""
    combined = _combined(harness_result)
    assert "[BodyTinter] mode=peripatetic" in combined, (
        "BodyTinter did not receive apply_mode delegation:\n" + combined
    )
