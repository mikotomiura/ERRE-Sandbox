"""Unit tests for ``WorldRuntime.apply_affinity_delta`` (M7δ Commit C4).

The M7γ surface only mutated ``RelationshipBond.affinity``,
``ichigo_ichie_count`` and ``last_interaction_tick``. M7δ adds two
behaviours:

1. ``last_interaction_zone`` is written when a ``zone`` argument is
   supplied — feeds the Godot ``ReasoningPanel`` "last in <zone>" UI.
2. Negative deltas past ``_NEGATIVE_DELTA_TRIGGER`` (``-0.05``) raise
   ``Physical.emotional_conflict`` by ``abs(delta) * 0.5`` (clamped),
   closing the dangling-read at ``cognition/state.py::sleep_penalty``
   (R3 M4).

These tests build a ``WorldRuntime`` with a single registered agent
(reusing the ``world_harness`` fixture from ``conftest.py``) so the
mutation paths are exercised in isolation without invoking the dialog
scheduler or the bootstrap sink.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erre_sandbox.schemas import (
    AgentState,
    CognitiveHabit,
    ERREMode,
    ERREModeName,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    Physical,
    Position,
    Zone,
)

if TYPE_CHECKING:
    from .conftest import RuntimeHarness


def _make_persona(persona_id: str = "kant") -> PersonaSpec:
    return PersonaSpec(
        persona_id=persona_id,
        display_name=persona_id.title(),
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
        preferred_zones=[Zone.PERIPATOS],
    )


def _make_state(
    persona_id: str = "kant",
    *,
    zone: Zone = Zone.STUDY,
    emotional_conflict: float = 0.0,
) -> AgentState:
    return AgentState(
        agent_id=f"a_{persona_id}_001",
        persona_id=persona_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=zone),
        physical=Physical(emotional_conflict=emotional_conflict),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
    )


def _register(harness: RuntimeHarness, persona_id: str, *, zone: Zone) -> str:
    persona = _make_persona(persona_id)
    state = _make_state(persona_id, zone=zone)
    harness.runtime.register_agent(state, persona)
    return state.agent_id


# ---------- last_interaction_zone (Axis 5) --------------------------------


def test_apply_affinity_delta_writes_last_interaction_zone(
    world_harness: RuntimeHarness,
) -> None:
    """``zone`` argument is persisted on the new bond."""
    a = _register(world_harness, "kant", zone=Zone.CHASHITSU)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.10,
        tick=5,
        zone=Zone.CHASHITSU,
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert len(bonds) == 1
    assert bonds[0].last_interaction_zone is Zone.CHASHITSU


def test_apply_affinity_delta_zone_default_is_none(
    world_harness: RuntimeHarness,
) -> None:
    """Backward compat: callers that omit ``zone`` see ``None`` on the bond."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.10,
        tick=5,
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert bonds[0].last_interaction_zone is None


def test_apply_affinity_delta_overwrites_zone_on_subsequent_calls(
    world_harness: RuntimeHarness,
) -> None:
    """Latest zone wins — supports an agent moving between zones across turns."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.10,
        tick=5,
        zone=Zone.STUDY,
    )
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.10,
        tick=10,
        zone=Zone.GARDEN,
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert bonds[0].last_interaction_zone is Zone.GARDEN
    assert bonds[0].ichigo_ichie_count == 2


# ---------- emotional_conflict on negative delta (Axis 2) ------------------


def test_apply_affinity_delta_writes_emotional_conflict_on_negative(
    world_harness: RuntimeHarness,
) -> None:
    """A -0.30 delta past the trigger raises emotional_conflict by 0.15."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=-0.30,
        tick=5,
    )
    physical = world_harness.runtime._agents[a].state.physical
    assert physical.emotional_conflict == pytest.approx(0.15)


def test_apply_affinity_delta_does_not_write_conflict_on_small_negative(
    world_harness: RuntimeHarness,
) -> None:
    """Below the trigger threshold the field is left at its previous value."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=-0.04,  # above the -0.05 trigger (less negative)
        tick=5,
    )
    physical = world_harness.runtime._agents[a].state.physical
    assert physical.emotional_conflict == 0.0


def test_apply_affinity_delta_does_not_write_conflict_on_positive(
    world_harness: RuntimeHarness,
) -> None:
    """Positive deltas do not affect emotional_conflict."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.20,
        tick=5,
    )
    physical = world_harness.runtime._agents[a].state.physical
    assert physical.emotional_conflict == 0.0


def test_apply_affinity_delta_clamps_emotional_conflict_at_one(
    world_harness: RuntimeHarness,
) -> None:
    """Repeated large negative deltas saturate emotional_conflict at 1.0."""
    persona = _make_persona("kant")
    state = _make_state("kant", zone=Zone.STUDY, emotional_conflict=0.9)
    world_harness.runtime.register_agent(state, persona)
    world_harness.runtime.apply_affinity_delta(
        agent_id=state.agent_id,
        other_agent_id="a_other_001",
        delta=-1.0,
        tick=5,
    )
    physical = world_harness.runtime._agents[state.agent_id].state.physical
    # 0.9 + 1.0*0.5 = 1.4, clamped to 1.0.
    assert physical.emotional_conflict == 1.0


def test_apply_affinity_delta_accumulates_emotional_conflict(
    world_harness: RuntimeHarness,
) -> None:
    """Two negative events compound additively before clamping."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    for _ in range(2):
        world_harness.runtime.apply_affinity_delta(
            agent_id=a,
            other_agent_id="a_other_001",
            delta=-0.30,
            tick=5,
        )
    physical = world_harness.runtime._agents[a].state.physical
    # 0.0 + 0.15 + 0.15 = 0.30
    assert physical.emotional_conflict == pytest.approx(0.30)


# ---------- get_agent_zone / get_bond_affinity accessors (Axes 1+5) --------


def test_get_agent_zone_returns_position_zone(
    world_harness: RuntimeHarness,
) -> None:
    a = _register(world_harness, "kant", zone=Zone.PERIPATOS)
    assert world_harness.runtime.get_agent_zone(a) is Zone.PERIPATOS


def test_get_agent_zone_returns_none_for_unknown_id(
    world_harness: RuntimeHarness,
) -> None:
    assert world_harness.runtime.get_agent_zone("unregistered") is None


def test_get_bond_affinity_returns_zero_when_no_bond(
    world_harness: RuntimeHarness,
) -> None:
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    assert world_harness.runtime.get_bond_affinity(a, "a_other_001") == 0.0


def test_get_bond_affinity_returns_current_after_mutation(
    world_harness: RuntimeHarness,
) -> None:
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.10,
        tick=5,
    )
    assert world_harness.runtime.get_bond_affinity(a, "a_other_001") == pytest.approx(
        0.10,
    )
