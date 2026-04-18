"""Shared helpers for Godot-backed tests.

Factored out of ``tests/test_godot_project.py`` during T16 so
``tests/test_godot_ws_client.py`` can reuse the same resolution + boot
logic without copy-paste. Not a pytest fixture — plain helpers.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GODOT_PROJECT = REPO_ROOT / "godot_project"
FIXTURES_CONTROL_ENVELOPE = REPO_ROOT / "fixtures" / "control_envelope"
GODOT_BIN_MAC = Path("/Applications/Godot.app/Contents/MacOS/Godot")
HEADLESS_TIMEOUT_SEC = 60


def resolve_godot() -> Path | None:
    """Locate a Godot binary via ``GODOT_BIN`` env var, known Mac path, or PATH."""
    override = os.environ.get("GODOT_BIN")
    if override:
        override_path = Path(override)
        return override_path if override_path.exists() else None
    if GODOT_BIN_MAC.exists():
        return GODOT_BIN_MAC
    found = shutil.which("godot")
    return Path(found) if found else None
