"""Contract tests for M7γ additive schema (0.6.0-m7g).

Each ``test_*`` documents one concrete clause of the M7γ wire contract
addition, mirroring the convention established by
``tests/test_schemas_m6.py``:

* ``SCHEMA_VERSION == "0.6.0-m7g"`` (the active milestone pin lives in
  ``test_schemas.py::test_schema_version_is_current_milestone``; this file
  re-asserts it so a regression on the M7γ-specific surface fails here too)
* :class:`WorldLayoutMsg` discriminator + :class:`ZoneLayout` /
  :class:`PropLayout` row shapes
* :class:`ReasoningTrace` gains three default-empty list fields
  (``observed_objects``, ``nearby_agents``, ``retrieved_memories``) and the
  M8 wire-shape (no extra fields) is preserved for backward compatibility

All additions are additive: existing M8 producers that emit traces without
the new fields, or that never emit ``world_layout``, remain wire-compatible.
This file covers only the frozen wire contract — production logic for
``WorldRuntime.layout_snapshot()`` and the cognition-cycle trace fill lives
in Slice γ Commits 2-3.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    ControlEnvelope,
    PropLayout,
    ReasoningTrace,
    ReasoningTraceMsg,
    RelationshipBond,
    TriggerEventTag,
    WorldLayoutMsg,
    Zone,
    ZoneLayout,
)

# ---------- §1 SCHEMA_VERSION ------------------------------------------------


def test_schema_version_is_m7g() -> None:
    """M7γ pinned the wire contract; subsequent milestones track current.

    M7γ introduced WorldLayoutMsg + the three ReasoningTrace observability
    fields. M7δ added belief promotion fields, M7ε bumps for the internal
    ``dialog_turns.epoch_phase`` column, M7ζ bumps for additive panel
    context (``ReasoningTrace.persona_id`` /
    ``RelationshipBond.latest_belief_kind``), and M9-A adds
    ``ReasoningTrace.trigger_event``. The surface this file exercises
    remains valid against the current SCHEMA_VERSION pin
    (``0.10.0-m7h``).
    """
    assert SCHEMA_VERSION == "0.10.0-m7h"


# ---------- §7 WorldLayoutMsg discriminator ----------------------------------


def test_world_layout_msg_dispatches_via_control_envelope() -> None:
    """The ``world_layout`` discriminator routes to :class:`WorldLayoutMsg`."""
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    envelope = adapter.validate_python(
        {
            "kind": "world_layout",
            "tick": 0,
            "zones": [
                {"zone": "study", "x": -33.3, "y": 0.0, "z": -33.3},
                {"zone": "peripatos", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "props": [
                {
                    "prop_id": "chawan_01",
                    "prop_kind": "tea_bowl",
                    "zone": "chashitsu",
                    "x": 32.83,
                    "y": 0.4,
                    "z": -32.83,
                    "salience": 0.7,
                },
            ],
        },
    )
    assert isinstance(envelope, WorldLayoutMsg)
    assert envelope.kind == "world_layout"
    assert len(envelope.zones) == 2
    assert envelope.zones[0].zone is Zone.STUDY
    assert envelope.props[0].prop_kind == "tea_bowl"


def test_world_layout_msg_defaults_to_empty_zones_and_props() -> None:
    """Empty zones / props list is a valid no-content layout snapshot."""
    msg = WorldLayoutMsg(tick=0)
    assert msg.zones == []
    assert msg.props == []


def test_world_layout_msg_round_trip_is_lossless() -> None:
    """JSON round-trip preserves zones and props list contents."""
    original = WorldLayoutMsg(
        tick=0,
        zones=[ZoneLayout(zone=Zone.STUDY, x=-33.3, y=0.0, z=-33.3)],
        props=[
            PropLayout(
                prop_id="chawan_01",
                prop_kind="tea_bowl",
                zone=Zone.CHASHITSU,
                x=32.83,
                y=0.4,
                z=-32.83,
                salience=0.7,
            ),
        ],
    )
    re_loaded = WorldLayoutMsg.model_validate_json(original.model_dump_json())
    assert re_loaded == original


def test_zone_layout_rejects_unknown_zone() -> None:
    """``ZoneLayout.zone`` is the same closed enum as :class:`Zone`."""
    with pytest.raises(ValidationError):
        ZoneLayout.model_validate({"zone": "valhalla", "x": 0.0, "y": 0.0, "z": 0.0})


def test_zone_layout_rejects_extra_fields() -> None:
    """``extra="forbid"`` guards typos like ``zone_name`` vs ``zone``."""
    with pytest.raises(ValidationError):
        ZoneLayout.model_validate(
            {"zone": "study", "x": 0.0, "y": 0.0, "z": 0.0, "name": "Study"},
        )


def test_prop_layout_clamps_salience_unit() -> None:
    """``PropLayout.salience`` shares the unit-interval bound with affordance."""
    PropLayout.model_validate(
        {
            "prop_id": "p",
            "prop_kind": "k",
            "zone": "chashitsu",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "salience": 1.0,
        },
    )
    with pytest.raises(ValidationError):
        PropLayout.model_validate(
            {
                "prop_id": "p",
                "prop_kind": "k",
                "zone": "chashitsu",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "salience": 1.01,
            },
        )


# ---------- §6 ReasoningTrace additive fields --------------------------------


def test_reasoning_trace_defaults_extended_fields_to_empty() -> None:
    """The three M7γ fields default to empty lists, preserving M8 producer compat."""
    trace = ReasoningTrace(
        agent_id="a_kant_001",
        tick=42,
        mode="peripatetic",
    )
    assert trace.observed_objects == []
    assert trace.nearby_agents == []
    assert trace.retrieved_memories == []


def test_reasoning_trace_round_trip_preserves_extended_fields() -> None:
    """``observed_objects`` / ``nearby_agents`` / ``retrieved_memories`` round-trip."""
    trace = ReasoningTrace(
        agent_id="a_kant_001",
        tick=42,
        mode="peripatetic",
        decision="continue walking; affinity=+0.04 with nietzsche",
        observed_objects=["chawan_01", "chawan_02"],
        nearby_agents=["a_nietzsche_001"],
        retrieved_memories=["m_obs_010", "m_obs_011", "m_ref_002"],
    )
    re_loaded = ReasoningTrace.model_validate_json(trace.model_dump_json())
    assert re_loaded == trace


def test_reasoning_trace_msg_carries_extended_trace() -> None:
    """The :class:`ReasoningTraceMsg` envelope passes the new fields untouched."""
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    payload: dict[str, object] = {
        "kind": "reasoning_trace",
        "tick": 42,
        "trace": {
            "agent_id": "a_kant_001",
            "tick": 42,
            "mode": "peripatetic",
            "observed_objects": ["chawan_01"],
            "nearby_agents": ["a_nietzsche_001"],
            "retrieved_memories": ["m_obs_010"],
        },
    }
    envelope = adapter.validate_python(payload)
    assert isinstance(envelope, ReasoningTraceMsg)
    assert envelope.trace.observed_objects == ["chawan_01"]
    assert envelope.trace.nearby_agents == ["a_nietzsche_001"]
    assert envelope.trace.retrieved_memories == ["m_obs_010"]


def test_reasoning_trace_rejects_extra_fields() -> None:
    """``extra="forbid"`` still applies after the M7γ field additions."""
    with pytest.raises(ValidationError):
        ReasoningTrace.model_validate(
            {
                "agent_id": "a",
                "tick": 0,
                "mode": "peripatetic",
                "rogue_field": "should be rejected",
            },
        )


# ---------- M7ζ RelationshipBond.latest_belief_kind --------------------------


def test_relationship_bond_latest_belief_kind_defaults_to_none() -> None:
    """M7ζ-additive: pre-0.9.0-m7z bonds deserialise without the field."""
    bond = RelationshipBond.model_validate({"other_agent_id": "a_nietzsche_001"})
    assert bond.latest_belief_kind is None


@pytest.mark.parametrize("kind", ["trust", "clash", "wary", "curious", "ambivalent"])
def test_relationship_bond_latest_belief_kind_accepts_each_literal(kind: str) -> None:
    """All five SemanticMemoryRecord.belief_kind values round-trip on the bond."""
    bond = RelationshipBond(
        other_agent_id="a_other_001",
        latest_belief_kind=kind,  # type: ignore[arg-type]
    )
    re_loaded = RelationshipBond.model_validate_json(bond.model_dump_json())
    assert re_loaded.latest_belief_kind == kind


def test_relationship_bond_latest_belief_kind_rejects_unknown_value() -> None:
    """An unrecognised literal must fail validation rather than silently pass."""
    with pytest.raises(ValidationError):
        RelationshipBond.model_validate(
            {
                "other_agent_id": "a_other_001",
                "latest_belief_kind": "ecstatic",
            },
        )


def test_world_layout_fixture_round_trips_against_envelope_union() -> None:
    """The ``world_layout`` fixture must validate cleanly against ControlEnvelope."""
    fixture = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "control_envelope"
        / "world_layout.json"
    )
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    envelope = adapter.validate_json(fixture.read_bytes())
    assert isinstance(envelope, WorldLayoutMsg)
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["tick"] == 0


# ---------- M9-A TriggerEventTag + ReasoningTrace.trigger_event --------------


def test_trigger_event_tag_round_trip_minimal() -> None:
    """``TriggerEventTag`` round-trips with required ``kind`` only."""
    tag = TriggerEventTag(kind="zone_transition")
    re_loaded = TriggerEventTag.model_validate_json(tag.model_dump_json())
    assert re_loaded == tag
    assert re_loaded.zone is None
    assert re_loaded.ref_id is None
    assert re_loaded.secondary_kinds == []


def test_trigger_event_tag_round_trip_full() -> None:
    """All fields populated, including ``secondary_kinds`` ordering."""
    tag = TriggerEventTag(
        kind="affordance",
        zone=Zone.CHASHITSU,
        ref_id="bowl_01",
        secondary_kinds=["proximity", "biorhythm"],
    )
    re_loaded = TriggerEventTag.model_validate_json(tag.model_dump_json())
    assert re_loaded == tag
    assert re_loaded.zone is Zone.CHASHITSU
    assert re_loaded.ref_id == "bowl_01"
    assert re_loaded.secondary_kinds == ["proximity", "biorhythm"]


def test_trigger_event_tag_rejects_extra_fields() -> None:
    """``model_config = ConfigDict(extra="forbid")`` must reject unknown nested keys."""
    with pytest.raises(ValidationError):
        TriggerEventTag.model_validate(
            {
                "kind": "affordance",
                "rogue_nested_field": "should be rejected",
            },
        )


def test_trigger_event_tag_rejects_unknown_kind() -> None:
    """Only the nine :class:`Observation` event_types are accepted as ``kind``."""
    with pytest.raises(ValidationError):
        TriggerEventTag.model_validate({"kind": "unknown"})


def test_trigger_event_tag_ref_id_max_length_64() -> None:
    """``ref_id`` over 64 chars must fail validation."""
    with pytest.raises(ValidationError):
        TriggerEventTag.model_validate(
            {"kind": "affordance", "ref_id": "x" * 65},
        )


def test_trigger_event_tag_secondary_kinds_max_length_8() -> None:
    """``secondary_kinds`` over 8 entries must fail validation."""
    with pytest.raises(ValidationError):
        TriggerEventTag.model_validate(
            {
                "kind": "zone_transition",
                "secondary_kinds": ["affordance"] * 9,
            },
        )


def test_reasoning_trace_trigger_event_defaults_to_none() -> None:
    """M9-A additive: pre-0.10.0-m7h traces deserialise without the field."""
    trace = ReasoningTrace(
        agent_id="a_kant_001",
        tick=42,
        mode="peripatetic",
    )
    assert trace.trigger_event is None


def test_reasoning_trace_round_trip_with_trigger_event() -> None:
    """``trigger_event`` round-trips through ReasoningTrace serialization."""
    trace = ReasoningTrace(
        agent_id="a_kant_001",
        tick=42,
        mode="peripatetic",
        trigger_event=TriggerEventTag(
            kind="zone_transition",
            zone=Zone.PERIPATOS,
            ref_id="peripatos",
        ),
    )
    re_loaded = ReasoningTrace.model_validate_json(trace.model_dump_json())
    assert re_loaded == trace
    assert re_loaded.trigger_event is not None
    assert re_loaded.trigger_event.kind == "zone_transition"
    assert re_loaded.trigger_event.zone is Zone.PERIPATOS


def test_reasoning_trace_msg_carries_trigger_event() -> None:
    """The :class:`ReasoningTraceMsg` envelope passes ``trigger_event`` untouched."""
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    payload: dict[str, object] = {
        "kind": "reasoning_trace",
        "tick": 42,
        "trace": {
            "agent_id": "a_kant_001",
            "tick": 42,
            "mode": "peripatetic",
            "trigger_event": {
                "kind": "affordance",
                "zone": "chashitsu",
                "ref_id": "bowl_01",
                "secondary_kinds": ["proximity"],
            },
        },
    }
    envelope = adapter.validate_python(payload)
    assert isinstance(envelope, ReasoningTraceMsg)
    assert envelope.trace.trigger_event is not None
    assert envelope.trace.trigger_event.kind == "affordance"
    assert envelope.trace.trigger_event.ref_id == "bowl_01"
    assert envelope.trace.trigger_event.secondary_kinds == ["proximity"]


def test_reasoning_trace_legacy_payload_without_trigger_event_is_valid() -> None:
    """Pre-0.10.0-m7h payload (no ``trigger_event`` key) deserialises cleanly."""
    legacy_payload: dict[str, object] = {
        "agent_id": "a_kant_001",
        "tick": 42,
        "mode": "peripatetic",
        "observed_objects": ["chawan_01"],
        "nearby_agents": [],
        "retrieved_memories": [],
    }
    trace = ReasoningTrace.model_validate(legacy_payload)
    assert trace.trigger_event is None


def test_trigger_event_tag_in_public_surface() -> None:
    """``TriggerEventTag`` is exported via ``__all__`` for downstream consumers."""
    from erre_sandbox import schemas as schemas_module

    assert "TriggerEventTag" in schemas_module.__all__
