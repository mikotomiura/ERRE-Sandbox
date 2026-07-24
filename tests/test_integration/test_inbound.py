"""Issue 001 (M13 live-loop-closure): inbound schema + pure-mapping tests.

Covers ``.steering/20260724-m13-live-loop-closure/design-final.md`` Issue
001's four Acceptance Criteria:

* AC1 — :class:`WorldPerturbationMsg` is bounded (``extra="forbid"``, range
  clamps, closed modality set, bounded content).
* AC2 — the :data:`InboundEnvelope` adapter validates a
  :class:`WorldPerturbationMsg` payload and rejects an outbound
  (:data:`ControlEnvelope`) kind.
* AC3 — :data:`ControlEnvelope`'s kind set is unchanged (does **not** grow
  ``"world_perturbation"``) — the HIGH-3 guard mirrored from
  ``test_envelope_kind_sync.py``.
* AC4 — :func:`world_perturbation_to_perception` is a pure field-for-field
  mapping and never carries ``correlation_id`` onto the resulting
  :class:`PerceptionEvent` (grill G2).
"""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from erre_sandbox.integration.inbound import world_perturbation_to_perception
from erre_sandbox.schemas import (
    ControlEnvelope,
    InboundEnvelope,
    MoveMsg,
    PerceptionEvent,
    Position,
    WorldPerturbationMsg,
    Zone,
)

_VALID_KWARGS: dict[str, object] = {
    "tick": 3,
    "target_agent_id": "kant-01",
    "modality": "sight",
    "source_zone": Zone.PERIPATOS,
    "content": "a gust of wind crosses the path",
    "intensity": 0.7,
}


def test_world_perturbation_bounded_validation() -> None:
    """AC1: bounded field constraints reject out-of-contract payloads."""
    # A well-formed payload is accepted (control case).
    msg = WorldPerturbationMsg(**_VALID_KWARGS)
    assert msg.kind == "world_perturbation"

    # extra="forbid" (inherited from _EnvelopeBase) rejects unknown fields.
    with pytest.raises(ValidationError):
        WorldPerturbationMsg(**_VALID_KWARGS, unexpected_field="nope")

    # intensity above the _Unit upper bound (1.0) is rejected.
    with pytest.raises(ValidationError):
        WorldPerturbationMsg(**{**_VALID_KWARGS, "intensity": 1.5})

    # intensity below the _Unit lower bound (0.0) is rejected.
    with pytest.raises(ValidationError):
        WorldPerturbationMsg(**{**_VALID_KWARGS, "intensity": -0.1})

    # modality outside the closed Literal enum is rejected.
    with pytest.raises(ValidationError):
        WorldPerturbationMsg(**{**_VALID_KWARGS, "modality": "taste"})

    # content past the 512-char bound is rejected; exactly 512 is accepted.
    at_bound = WorldPerturbationMsg(**{**_VALID_KWARGS, "content": "x" * 512})
    assert len(at_bound.content) == 512
    with pytest.raises(ValidationError):
        WorldPerturbationMsg(**{**_VALID_KWARGS, "content": "x" * 513})


def test_inbound_adapter_rejects_outbound_kind() -> None:
    """AC2: the InboundEnvelope adapter validates inbound, rejects outbound."""
    adapter: TypeAdapter[WorldPerturbationMsg] = TypeAdapter(InboundEnvelope)

    inbound_msg = WorldPerturbationMsg(**_VALID_KWARGS)
    validated = adapter.validate_python(inbound_msg.model_dump(mode="json"))
    assert validated.kind == "world_perturbation"
    assert validated == inbound_msg

    # A well-formed *outbound* ControlEnvelope member (MoveMsg) must be
    # rejected by the inbound-only adapter — it is a different kind and
    # lacks WorldPerturbationMsg's required fields.
    outbound_msg = MoveMsg(
        tick=3,
        agent_id="kant-01",
        target=Position(x=1.0, y=2.0, z=0.0, zone=Zone.PERIPATOS),
        speed=1.3,
    )
    with pytest.raises(ValidationError):
        adapter.validate_python(outbound_msg.model_dump(mode="json"))


def _control_envelope_kinds() -> set[str]:
    """Extract ``kind`` literals from the ControlEnvelope discriminated union.

    Mirrors ``test_envelope_kind_sync.py::_python_kinds`` (same extraction
    technique) so AC3 can pin the exact set without importing test-internal
    helpers across files.
    """
    annotated_args = get_args(ControlEnvelope)
    union_type = annotated_args[0]
    classes = get_args(union_type)
    return {cls.model_fields["kind"].default for cls in classes}


_EXPECTED_OUTBOUND_KINDS: frozenset[str] = frozenset(
    {
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
        "reasoning_trace",
        "reflection_event",
        "world_layout",
    },
)


def test_control_envelope_unchanged() -> None:
    """AC3 (HIGH-3): ControlEnvelope's 13 outbound kinds are unchanged.

    ``"world_perturbation"`` must never be folded into ControlEnvelope — it
    lives only on the separate InboundEnvelope system.
    """
    kinds = _control_envelope_kinds()
    assert kinds == _EXPECTED_OUTBOUND_KINDS
    assert "world_perturbation" not in kinds


def test_perturbation_to_perception_mapping() -> None:
    """AC4: world_perturbation_to_perception is a pure, correlation-id-free mapping."""
    msg = WorldPerturbationMsg(
        tick=1,  # deliberately different from the injection tick below
        target_agent_id="kant-01",
        modality="smell",
        source_zone=Zone.GARDEN,
        content="fresh-cut grass",
        intensity=0.42,
        correlation_id="corr-abc123",
    )

    perception = world_perturbation_to_perception(msg, tick=7)

    assert isinstance(perception, PerceptionEvent)
    assert perception.tick == 7  # caller-supplied tick, not msg.tick
    assert perception.agent_id == msg.target_agent_id
    assert perception.modality == msg.modality
    assert perception.source_zone == msg.source_zone
    assert perception.content == msg.content
    assert perception.intensity == msg.intensity
    assert perception.source_agent_id is None

    # G2: correlation_id must not leak onto PerceptionEvent (schema has no
    # such field at all — this pins that the field is structurally absent,
    # not merely unset).
    assert not hasattr(perception, "correlation_id")
    assert "correlation_id" not in type(perception).model_fields

    # Purity: calling again with the same inputs produces an equal (but
    # distinct) PerceptionEvent, and the source msg is untouched.
    perception_again = world_perturbation_to_perception(msg, tick=7)
    assert perception_again.model_dump(
        exclude={"wall_clock"},
    ) == perception.model_dump(exclude={"wall_clock"})
    assert msg.correlation_id == "corr-abc123"
