"""Tests for the `fixtures/control_envelope/` wire-contract specimens (T07).

Every fixture must be a valid ``ControlEnvelope`` under the current schema,
its filename must match its ``kind`` discriminator, and round-tripping through
Pydantic must be semantically stable. All seven kinds must be represented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel, TypeAdapter

from erre_sandbox.schemas import SCHEMA_VERSION, ControlEnvelope

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures" / "control_envelope"


def _kinds_from_schema() -> frozenset[str]:
    """Extract the discriminator literal of every member of the
    ``ControlEnvelope`` union, so the test stays in sync with schemas.py
    when new envelope kinds are added. ``ControlEnvelope`` is an
    ``Annotated[Union[...], Field(discriminator="kind")]`` TypeAlias.
    """
    annotated_args = get_args(ControlEnvelope)
    union_type = annotated_args[0]
    members: tuple[type[BaseModel], ...] = get_args(union_type)
    return frozenset(m.model_fields["kind"].default for m in members)


EXPECTED_KINDS: frozenset[str] = _kinds_from_schema()

_ADAPTER: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
_FIXTURE_PATHS: list[Path] = sorted(FIXTURES_DIR.glob("*.json"))


def test_all_expected_kinds_have_fixture() -> None:
    stems = {p.stem for p in _FIXTURE_PATHS}
    missing = EXPECTED_KINDS - stems
    extra = stems - EXPECTED_KINDS
    assert not missing, f"missing kind fixtures: {sorted(missing)}"
    assert not extra, f"unexpected fixtures (not a known kind): {sorted(extra)}"


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=lambda p: p.stem,
)
def test_fixture_validates_and_kind_matches_filename(
    fixture_path: Path,
) -> None:
    # validate_json exercises the same path used when a WebSocket peer hands
    # raw bytes to Pydantic — more fidelity than json.loads + validate_python.
    envelope = _ADAPTER.validate_json(fixture_path.read_bytes())
    assert envelope.kind == fixture_path.stem


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=lambda p: p.stem,
)
def test_fixture_round_trip_is_semantically_stable(
    fixture_path: Path,
) -> None:
    original = _ADAPTER.validate_python(
        json.loads(fixture_path.read_text(encoding="utf-8")),
    )
    re_serialised = _ADAPTER.dump_python(original, mode="json")
    re_loaded = _ADAPTER.validate_python(re_serialised)
    assert re_loaded == original


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=lambda p: p.stem,
)
def test_fixture_schema_version_matches(fixture_path: Path) -> None:
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION, (
        f"{fixture_path.name} declares schema_version={data['schema_version']!r}, "
        f"but SCHEMA_VERSION is {SCHEMA_VERSION!r} — regenerate fixtures."
    )


def test_agent_update_fixture_references_kant_persona() -> None:
    data = json.loads((FIXTURES_DIR / "agent_update.json").read_text(encoding="utf-8"))
    assert data["kind"] == "agent_update"
    assert data["agent_state"]["persona_id"] == "kant"
    assert data["agent_state"]["position"]["zone"] == "peripatos"


# Fixture stems whose ``tick`` legitimately diverges from the coherent
# tick-42 scenario. ``handshake`` is session-start; ``world_layout`` is the
# M7γ on-connect single-shot snapshot that conventionally rides at tick 0.
_TICK_42_EXEMPT_STEMS: frozenset[str] = frozenset({"handshake", "world_layout"})


def test_shared_invariants_across_fixtures() -> None:
    """Coherent-scenario fixtures share tick 42, the same sent_at, and agent id."""
    for path in _FIXTURE_PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["sent_at"] == "2026-04-18T12:00:00Z", path.name
        if path.stem not in _TICK_42_EXEMPT_STEMS:
            assert data["tick"] == 42, f"{path.name} should be tick 42"
        else:
            assert data["tick"] == 0, (
                f"{path.name} is exempt from tick 42 but should be at tick 0"
            )
        if "agent_id" in data:
            assert data["agent_id"] == "a_kant_001", path.name
