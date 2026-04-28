"""T16 godot-ws-client: headless fixture-replay regression.

Launches ``FixtureHarness.tscn`` under ``godot --headless`` with the absolute
path to ``fixtures/control_envelope`` injected via ``--fixture-dir=``. The
harness disables the real WebSocketClient and replays each fixture through
the production EnvelopeRouter, which re-emits typed signals consumed by
AgentManager and WorldManager log stubs.

We then assert that every kind's log line appears in stdout, in the fixed
playlist order, with no "Unknown kind" warning. Skipped if Godot is not
installed (identical behaviour to ``test_godot_project.py``).
"""

from __future__ import annotations

import subprocess

import pytest

from tests._godot_helpers import (
    FIXTURES_CONTROL_ENVELOPE,
    GODOT_PROJECT,
    HEADLESS_TIMEOUT_SEC,
    resolve_godot,
)

# Order must match FixturePlayer.gd DEFAULT_PLAYLIST. The dialog_* trio was
# added in M5 so test_godot_dialog_bubble can replay a dialog_turn envelope
# through the shared FixtureHarness without a separate playlist.
_EXPECTED_PLAYBACK_ORDER: tuple[str, ...] = (
    "handshake",
    "agent_update",
    "speech",
    "move",
    "animation",
    "world_tick",
    "error",
    "dialog_initiate",
    "dialog_turn",
    "dialog_close",
)

# Dispatch log lines emitted by FixturePlayer.gd (one per envelope).
_DISPATCH_LINE_TEMPLATE = "[FixturePlayer] dispatching {filename} kind={kind}"


@pytest.mark.godot
def test_fixture_harness_dispatches_seven_kinds_in_order() -> None:
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")
    assert FIXTURES_CONTROL_ENVELOPE.is_dir(), (
        "Expected fixtures/control_envelope/ to exist (T07)"
    )
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
    combined = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, (
        f"Fixture harness exited with rc={result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Each fixture file produces exactly one dispatch log line, in playlist order.
    positions: list[int] = []
    for kind in _EXPECTED_PLAYBACK_ORDER:
        expected = _DISPATCH_LINE_TEMPLATE.format(
            filename=f"{kind}.json",
            kind=kind,
        )
        pos = combined.find(expected)
        assert pos >= 0, (
            f"Missing dispatch log for kind={kind!r}. Expected substring:\n"
            f"  {expected}\n"
            f"Combined output:\n{combined}"
        )
        positions.append(pos)
    assert positions == sorted(positions), (
        "Fixture dispatch order violated the expected playlist sequence.\n"
        f"positions: {positions}\noutput:\n{combined}"
    )

    # Unknown kinds should never appear — the router must recognise all seven.
    assert "Unknown kind" not in combined, (
        f"EnvelopeRouter reported an unknown kind:\n{combined}"
    )

    # FixturePlayer announces completion before quitting.
    assert "[FixturePlayer] playlist complete, quitting" in combined, (
        f"Missing FixturePlayer completion log:\n{combined}"
    )
