"""Smoke tests for the T05 schemas-freeze contract.

Covers: default instantiation, ``extra="forbid"``, enum JSON round-trip, and
Pydantic discriminated-union dispatch for ``Observation`` / ``ControlEnvelope``.
Full behavioural tests are T08's scope.
"""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentState,
    AgentUpdateMsg,
    CognitiveHabit,
    ControlEnvelope,
    ERREMode,
    ERREModeName,
    HabitFlag,
    HandshakeMsg,
    MemoryEntry,
    MemoryKind,
    Observation,
    PerceptionEvent,
    PersonalityTraits,
    PersonaSpec,
    Physical,
    Position,
    SpeechEvent,
    Zone,
)


def _make_agent_state() -> AgentState:
    return AgentState(
        agent_id="a1",
        persona_id="kant",
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
    )


def test_agent_state_defaults_match_csdg_human_condition() -> None:
    state = _make_agent_state()
    assert state.physical.sleep_quality == pytest.approx(0.7)
    assert state.physical.physical_energy == pytest.approx(0.7)
    assert state.physical.mood_baseline == pytest.approx(0.0)
    assert state.physical.cognitive_load == pytest.approx(0.2)
    assert state.schema_version == SCHEMA_VERSION


def test_extra_forbid_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Physical.model_validate({"sleep_quality": 0.5, "bogus_field": 1})


def test_unit_and_signed_ranges_are_enforced() -> None:
    # _Unit field ([0, 1]) rejects values above 1.0
    with pytest.raises(ValidationError):
        Physical.model_validate({"sleep_quality": 1.5})
    # _Signed field ([-1, 1]) rejects values below -1.0
    with pytest.raises(ValidationError):
        Physical.model_validate({"mood_baseline": -2.0})


def test_str_enum_round_trip_as_json() -> None:
    entry = MemoryEntry(
        id="m1",
        agent_id="a1",
        kind=MemoryKind.EPISODIC,
        content="walked the peripatos",
        importance=0.7,
    )
    payload = json.loads(entry.model_dump_json())
    assert payload["kind"] == "episodic"
    assert MemoryEntry.model_validate(payload).kind is MemoryKind.EPISODIC


def test_observation_union_dispatches_on_event_type() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    perceived = adapter.validate_python(
        {
            "event_type": "perception",
            "tick": 3,
            "agent_id": "a1",
            "modality": "sight",
            "source_zone": "peripatos",
            "content": "a fellow walker approaches",
            "intensity": 0.8,
        },
    )
    assert isinstance(perceived, PerceptionEvent)

    spoken = adapter.validate_python(
        {
            "event_type": "speech",
            "tick": 3,
            "agent_id": "a1",
            "speaker_id": "a2",
            "utterance": "Guten Tag",
        },
    )
    assert isinstance(spoken, SpeechEvent)

    with pytest.raises(ValidationError):
        adapter.validate_python({"event_type": "unknown", "tick": 0, "agent_id": "a1"})


def test_control_envelope_union_dispatches_on_kind() -> None:
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    handshake = adapter.validate_python(
        {
            "kind": "handshake",
            "tick": 0,
            "peer": "g-gear",
            "capabilities": ["agent_update", "speech"],
        },
    )
    assert isinstance(handshake, HandshakeMsg)

    update = adapter.validate_python(
        {
            "kind": "agent_update",
            "tick": 0,
            "agent_state": _make_agent_state().model_dump(mode="json"),
        },
    )
    assert isinstance(update, AgentUpdateMsg)

    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "not_a_kind", "tick": 0})


def test_persona_spec_requires_cognitive_habit_with_flag() -> None:
    spec = PersonaSpec(
        persona_id="kant",
        display_name="Immanuel Kant",
        era="1724-1804",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="15:30 daily walk",
                source="kuehn2001",
                flag=HabitFlag.FACT,
                mechanism="DMN activation via rhythmic locomotion",
            ),
        ],
        preferred_zones=[Zone.STUDY, Zone.PERIPATOS],
    )
    assert spec.cognitive_habits[0].flag is HabitFlag.FACT
    assert spec.schema_version == SCHEMA_VERSION
