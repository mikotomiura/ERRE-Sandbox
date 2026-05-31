"""Regenerate fixture JSONs and JSON-Schema goldens from ``schemas.py``.

This script is the canonical way to propagate a ``SCHEMA_VERSION`` bump (or any
additive schema change) to the two artifact sets that otherwise have to be
hand-edited:

* ``fixtures/control_envelope/*.json`` — human-authored on-wire examples.
  Every file's ``schema_version`` is rewritten to match the current
  ``erre_sandbox.schemas.SCHEMA_VERSION``. Known-required additive fields are
  injected when missing (see ``_FIXTURE_ADDITIVE_PATCHES``).

* ``tests/schema_golden/*.schema.json`` — pinned JSON Schema that
  ``tests/test_schema_contract.py::test_json_schema_matches_golden`` diffs
  against ``pydantic`` output. Rewritten in full using the same
  ``TypeAdapter(...).json_schema()`` sort/indent conventions described in
  ``tests/schema_golden/README.md``.

Running this script is **idempotent**: a second run produces no diff. This is
how we prove the fixtures and goldens agree with ``schemas.py`` at any commit.

Usage
-----
From repo root::

    uv run python scripts/regen_schema_artifacts.py

Exit code 0 = success. Stdout lists each file updated and the diff size.
Non-zero exit means an unrecoverable error (missing directory, malformed
fixture, etc.); read the traceback.

Guardrails
----------
* Fixture files are read as UTF-8 JSON and written back pretty-printed with
  ``indent=2`` + trailing newline, matching the hand-authored style.
* This script **never** deletes fixture keys. It only rewrites
  ``schema_version`` and injects missing required additive fields per the
  ``_FIXTURE_ADDITIVE_PATCHES`` table below. To retire a field, edit the
  fixtures by hand after schema removal.
* Goldens are regenerated in full; hand edits to them will be clobbered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

# Import is deferred until we've located the repo root so running the script
# from either repo root or ``scripts/`` both work without PYTHONPATH fiddling.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from erre_sandbox.schemas import (  # noqa: E402
    SCHEMA_VERSION,
    AgentState,
    ControlEnvelope,
    PersonaSpec,
)

FIXTURE_DIR = REPO_ROOT / "fixtures" / "control_envelope"
GOLDEN_DIR = REPO_ROOT / "tests" / "schema_golden"

# Required-additive-field patches applied to specific fixture ``kind`` values
# when the field is absent. Runs after the ``schema_version`` rewrite.
# Extend this table when future bumps introduce new required additive fields.
_FIXTURE_ADDITIVE_PATCHES: dict[str, dict[str, Any]] = {
    "dialog_turn": {"turn_index": 0},
}

_GOLDEN_TARGETS: dict[str, type] = {
    "agent_state": AgentState,
    "persona_spec": PersonaSpec,
    "control_envelope": ControlEnvelope,
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> bool:
    """Write ``data`` as pretty JSON; return True if content changed on disk."""
    new_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if new_text == old_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _regen_fixtures() -> list[str]:
    """Rewrite ``schema_version`` and apply top-level additive patches.

    Patches are applied only to the top-level dict of each fixture (``kind`` is
    looked up at the root). Nested payloads (e.g. ``agent_state`` inside an
    ``agent_update`` envelope) are out of scope; extend this helper if a
    future milestone introduces required fields on a nested type.

    After patching, each fixture is **re-validated** against
    :class:`ControlEnvelope` so a malformed patch table fails the regen run
    immediately rather than silently producing fixtures that only fail at
    pytest time.
    """
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    if not FIXTURE_DIR.is_dir():
        msg = f"fixture directory not found: {FIXTURE_DIR}"
        raise RuntimeError(msg)
    updated: list[str] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = _read_json(path)
        data["schema_version"] = SCHEMA_VERSION
        patches = _FIXTURE_ADDITIVE_PATCHES.get(data.get("kind", ""), {})
        for key, value in patches.items():
            data.setdefault(key, value)
        adapter.validate_python(data)  # raises on schema drift — fail fast
        if _write_json(path, data):
            updated.append(path.relative_to(REPO_ROOT).as_posix())
    return updated


def _regen_goldens() -> list[str]:
    if not GOLDEN_DIR.is_dir():
        msg = f"golden directory not found: {GOLDEN_DIR}"
        raise RuntimeError(msg)
    updated: list[str] = []
    for name, target in _GOLDEN_TARGETS.items():
        adapter = TypeAdapter(target)
        schema = adapter.json_schema()
        text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        path = GOLDEN_DIR / f"{name}.schema.json"
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        if text != old_text:
            path.write_text(text, encoding="utf-8")
            updated.append(path.relative_to(REPO_ROOT).as_posix())
    return updated


def main() -> int:
    print(f"SCHEMA_VERSION = {SCHEMA_VERSION}")  # noqa: T201
    fixtures = _regen_fixtures()
    goldens = _regen_goldens()
    if fixtures:
        print(f"updated {len(fixtures)} fixture file(s):")  # noqa: T201
        for name in fixtures:
            print(f"  - {name}")  # noqa: T201
    else:
        print("fixtures: no changes")  # noqa: T201
    if goldens:
        print(f"updated {len(goldens)} golden file(s):")  # noqa: T201
        for name in goldens:
            print(f"  - {name}")  # noqa: T201
    else:
        print("goldens: no changes")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
