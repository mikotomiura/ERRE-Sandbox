"""Smoke tests for the T05 schemas-freeze contract.

Covers: default instantiation, ``extra="forbid"``, enum JSON round-trip, and
Pydantic discriminated-union dispatch for ``Observation`` / ``ControlEnvelope``.
Full behavioural tests are T08's scope.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentSpec,
    AgentState,
    AgentUpdateMsg,
    CognitiveHabit,
    ControlEnvelope,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogScheduler,
    DialogTurnMsg,
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
    ReflectionEvent,
    SamplingBase,
    SamplingDelta,
    SemanticMemoryRecord,
    SpeechEvent,
    Zone,
)


def _make_agent_state() -> AgentState:
    """Inline helper matching the ``make_agent_state`` conftest factory default.

    Kept alongside the conftest factory so module-level payload dicts (envelope
    tests below) can construct an AgentState without a fixture injection.
    """
    return AgentState(
        agent_id="a_kant_001",
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


# =========================================================================
# T08 Layer 1 — boundary tables, union negatives, round-trips
# =========================================================================


# Boundary table: (model_cls, payload_valid, payload_invalid_below,
# payload_invalid_above). ``payload_valid`` MUST validate; each invalid
# payload MUST raise. Covers _Unit, _Signed, and explicit ge/le fields.
_BOUNDARY_CASES: list[
    tuple[
        type[BaseModel],
        dict[str, object],
        dict[str, object],
        dict[str, object] | None,
    ]
] = [
    (
        Physical,
        {"sleep_quality": 0.0},
        {"sleep_quality": -0.01},
        {"sleep_quality": 1.01},
    ),
    (
        Physical,
        {"fatigue": 1.0},
        {"fatigue": -0.01},
        {"fatigue": 1.01},
    ),
    (
        Physical,
        {"mood_baseline": -1.0},
        {"mood_baseline": -1.01},
        {"mood_baseline": 1.01},
    ),
]


@pytest.mark.parametrize(
    ("model_cls", "valid", "below", "above"),
    _BOUNDARY_CASES,
    ids=[f"{c[0].__name__}.{next(iter(c[1]))}" for c in _BOUNDARY_CASES],
)
def test_numeric_field_boundaries(
    model_cls: type[BaseModel],
    valid: dict[str, object],
    below: dict[str, object],
    above: dict[str, object] | None,
) -> None:
    model_cls.model_validate(valid)  # must succeed
    with pytest.raises(ValidationError):
        model_cls.model_validate(below)
    if above is not None:
        with pytest.raises(ValidationError):
            model_cls.model_validate(above)


def test_sampling_base_rejects_out_of_range() -> None:
    SamplingBase.model_validate(
        {"temperature": 0.0, "top_p": 0.5, "repeat_penalty": 0.5},
    )
    with pytest.raises(ValidationError):
        SamplingBase.model_validate({"temperature": -0.01})
    with pytest.raises(ValidationError):
        SamplingBase.model_validate({"temperature": 2.01})
    with pytest.raises(ValidationError):
        SamplingBase.model_validate({"repeat_penalty": 0.49})


def test_sampling_delta_is_tight_signed_unit() -> None:
    SamplingDelta.model_validate({"temperature": 0.0})
    SamplingDelta.model_validate(
        {"temperature": 1.0, "top_p": -1.0, "repeat_penalty": 1.0},
    )
    with pytest.raises(ValidationError):
        SamplingDelta.model_validate({"temperature": 1.01})
    with pytest.raises(ValidationError):
        SamplingDelta.model_validate({"temperature": -1.01})


def test_erre_mode_requires_entered_at_tick_non_negative() -> None:
    ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0)
    with pytest.raises(ValidationError):
        ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=-1)


def test_agent_state_tick_non_negative() -> None:
    with pytest.raises(ValidationError):
        AgentState.model_validate(
            {
                "agent_id": "a",
                "persona_id": "kant",
                "tick": -1,
                "position": {"x": 0, "y": 0, "z": 0, "zone": "study"},
                "erre": {"name": "deep_work", "entered_at_tick": 0},
            },
        )


def test_control_envelope_rejects_missing_kind() -> None:
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    with pytest.raises(ValidationError):
        adapter.validate_python({"tick": 0, "peer": "g-gear"})


def test_observation_rejects_missing_event_type() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    with pytest.raises(ValidationError):
        adapter.validate_python({"tick": 0, "agent_id": "a"})


def test_all_observation_event_types_validate() -> None:
    """Every Observation kind instantiates via its required fields."""
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    cases: list[dict[str, object]] = [
        {
            "event_type": "perception",
            "tick": 1,
            "agent_id": "a",
            "modality": "sight",
            "source_zone": "peripatos",
            "content": "...",
        },
        {
            "event_type": "speech",
            "tick": 1,
            "agent_id": "a",
            "speaker_id": "b",
            "utterance": "...",
        },
        {
            "event_type": "zone_transition",
            "tick": 1,
            "agent_id": "a",
            "from_zone": "study",
            "to_zone": "peripatos",
        },
        {
            "event_type": "erre_mode_shift",
            "tick": 1,
            "agent_id": "a",
            "previous": "deep_work",
            "current": "peripatetic",
            "reason": "zone",
        },
        {
            "event_type": "internal",
            "tick": 1,
            "agent_id": "a",
            "content": "...",
        },
    ]
    for payload in cases:
        result = adapter.validate_python(payload)
        assert result.event_type == payload["event_type"]


def test_agent_state_json_round_trip_is_lossless() -> None:
    original = _make_agent_state()
    re_loaded = AgentState.model_validate_json(original.model_dump_json())
    assert re_loaded == original


def test_persona_spec_json_round_trip_is_lossless() -> None:
    spec = PersonaSpec(
        persona_id="kant",
        display_name="Immanuel Kant",
        era="1724-1804",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="15:30 walk",
                source="kuehn2001",
                flag=HabitFlag.FACT,
                mechanism="DMN",
            ),
        ],
        preferred_zones=[Zone.STUDY, Zone.PERIPATOS],
    )
    re_loaded = PersonaSpec.model_validate_json(spec.model_dump_json())
    assert re_loaded == spec


def test_conftest_factory_matches_inline_helper(agent_state_kant: AgentState) -> None:
    """Factory fixture default is equal to the inline ``_make_agent_state``.

    Excludes ``wall_clock`` which is a ``datetime.now(UTC)`` default factory and
    will differ between two separate instantiations.
    """
    lhs = agent_state_kant.model_dump(exclude={"wall_clock"})
    rhs = _make_agent_state().model_dump(exclude={"wall_clock"})
    assert lhs == rhs


# =========================================================================
# M4 foundation — AgentSpec / ReflectionEvent / SemanticMemoryRecord
# / Dialog* variants / DialogScheduler Protocol
# =========================================================================


def test_schema_version_is_m4() -> None:
    """Top-level SCHEMA_VERSION has been bumped for the M4 foundation freeze."""
    assert SCHEMA_VERSION == "0.2.0-m4"


def test_agent_spec_validates_minimal_shape() -> None:
    spec = AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS)
    assert spec.persona_id == "kant"
    assert spec.initial_zone is Zone.PERIPATOS


def test_agent_spec_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate(
            {"persona_id": "kant", "initial_zone": "peripatos", "rogue": True},
        )


def test_agent_spec_requires_known_zone() -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({"persona_id": "kant", "initial_zone": "valhalla"})


def test_reflection_event_round_trip() -> None:
    event = ReflectionEvent(
        agent_id="a_kant_001",
        tick=120,
        summary_text="Clarity after the 15:30 walk.",
        src_episodic_ids=["m1", "m2"],
    )
    re_loaded = ReflectionEvent.model_validate_json(event.model_dump_json())
    assert re_loaded == event


def test_reflection_event_rejects_negative_tick() -> None:
    with pytest.raises(ValidationError):
        ReflectionEvent.model_validate(
            {"agent_id": "a", "tick": -1, "summary_text": "x"},
        )


def test_semantic_memory_record_accepts_empty_embedding() -> None:
    record = SemanticMemoryRecord(
        id="sm1",
        agent_id="a_kant_001",
        summary="Idea X refined.",
    )
    assert record.embedding == []
    assert record.origin_reflection_id is None


def test_semantic_memory_record_round_trip_with_embedding() -> None:
    record = SemanticMemoryRecord(
        id="sm1",
        agent_id="a_kant_001",
        embedding=[0.1, 0.2, -0.3],
        summary="Idea X refined.",
        origin_reflection_id="rf1",
    )
    re_loaded = SemanticMemoryRecord.model_validate_json(record.model_dump_json())
    assert re_loaded == record


def _dialog_envelope_cases() -> list[tuple[str, dict[str, object], type[BaseModel]]]:
    return [
        (
            "dialog_initiate",
            {
                "kind": "dialog_initiate",
                "tick": 42,
                "initiator_agent_id": "a_kant_001",
                "target_agent_id": "a_nietzsche_001",
                "zone": "peripatos",
            },
            DialogInitiateMsg,
        ),
        (
            "dialog_turn",
            {
                "kind": "dialog_turn",
                "tick": 42,
                "dialog_id": "d1",
                "speaker_id": "a_kant_001",
                "addressee_id": "a_nietzsche_001",
                "utterance": "Guten Tag.",
            },
            DialogTurnMsg,
        ),
        (
            "dialog_close",
            {
                "kind": "dialog_close",
                "tick": 42,
                "dialog_id": "d1",
                "reason": "completed",
            },
            DialogCloseMsg,
        ),
    ]


@pytest.mark.parametrize(
    ("kind", "payload", "expected_cls"),
    _dialog_envelope_cases(),
    ids=[c[0] for c in _dialog_envelope_cases()],
)
def test_control_envelope_union_dispatches_dialog_variants(
    kind: str,
    payload: dict[str, object],
    expected_cls: type[BaseModel],
) -> None:
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    envelope = adapter.validate_python(payload)
    assert isinstance(envelope, expected_cls)
    assert envelope.kind == kind


def test_dialog_close_reason_is_literal_set() -> None:
    DialogCloseMsg(tick=1, dialog_id="d1", reason="interrupted")
    DialogCloseMsg(tick=1, dialog_id="d1", reason="timeout")
    with pytest.raises(ValidationError):
        DialogCloseMsg.model_validate(
            {"kind": "dialog_close", "tick": 1, "dialog_id": "d1", "reason": "bored"},
        )


def test_dialog_scheduler_protocol_exposes_required_methods() -> None:
    """The Protocol is interface-only; concrete impl comes in orchestrator task."""
    for method_name in ("schedule_initiate", "record_turn", "close_dialog"):
        assert hasattr(DialogScheduler, method_name), (
            f"DialogScheduler is missing required method {method_name!r}"
        )
