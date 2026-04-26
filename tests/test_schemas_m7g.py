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
    WorldLayoutMsg,
    Zone,
    ZoneLayout,
)

# ---------- §1 SCHEMA_VERSION ------------------------------------------------


def test_schema_version_is_m7g() -> None:
    """M7γ pinned the wire contract; subsequent milestones track current.

    M7γ introduced WorldLayoutMsg + the three ReasoningTrace observability
    fields. M7δ added belief promotion fields, M7ε bumps for the internal
    ``dialog_turns.epoch_phase`` column, and M7ζ bumps for additive panel
    context (``ReasoningTrace.persona_id`` /
    ``RelationshipBond.latest_belief_kind``). The surface this file exercises
    remains valid against the current SCHEMA_VERSION pin
    (``0.9.0-m7z``).
    """
    assert SCHEMA_VERSION == "0.9.0-m7z"


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
