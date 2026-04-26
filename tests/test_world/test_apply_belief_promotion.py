"""Unit tests for ``WorldRuntime.apply_belief_promotion`` (M7ζ-2 Commit C3).

The M7δ relational loop already promotes a :class:`SemanticMemoryRecord` past
the ``|affinity| × N`` gates, but the Godot ``ReasoningPanel`` cannot afford
a semantic_memory query on every panel refresh. M7ζ-2 stamps the typed
classification onto :attr:`RelationshipBond.latest_belief_kind` directly so
the next ``AgentUpdateMsg`` snapshot carries the icon-prefix value the panel
renders next to the bond row.

These tests build a ``WorldRuntime`` with a single registered agent (reusing
the ``world_harness`` fixture from ``conftest.py``) so the mutation path is
exercised in isolation without invoking the dialog scheduler or the
bootstrap sink.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.schemas import (
    AgentState,
    CognitiveHabit,
    ERREMode,
    ERREModeName,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
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


def _make_state(persona_id: str = "kant", *, zone: Zone = Zone.STUDY) -> AgentState:
    return AgentState(
        agent_id=f"a_{persona_id}_001",
        persona_id=persona_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=zone),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
    )


def _register(harness: RuntimeHarness, persona_id: str, *, zone: Zone) -> str:
    persona = _make_persona(persona_id)
    state = _make_state(persona_id, zone=zone)
    harness.runtime.register_agent(state, persona)
    return state.agent_id


def test_apply_belief_promotion_writes_kind_on_existing_bond(
    world_harness: RuntimeHarness,
) -> None:
    """Happy path: an existing bond gains ``latest_belief_kind=`trust```."""
    a = _register(world_harness, "kant", zone=Zone.CHASHITSU)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.80,
        tick=5,
        zone=Zone.CHASHITSU,
    )
    world_harness.runtime.apply_belief_promotion(
        agent_id=a,
        other_agent_id="a_other_001",
        belief_kind="trust",
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert len(bonds) == 1
    assert bonds[0].latest_belief_kind == "trust"
    # Other M7δ fields are untouched by the promotion stamp.
    assert bonds[0].last_interaction_zone is Zone.CHASHITSU
    assert bonds[0].ichigo_ichie_count == 1


def test_apply_belief_promotion_overwrites_prior_kind(
    world_harness: RuntimeHarness,
) -> None:
    """Subsequent promotions of the same dyad replace the prior classification."""
    a = _register(world_harness, "kant", zone=Zone.CHASHITSU)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a,
        other_agent_id="a_other_001",
        delta=0.40,
        tick=5,
        zone=Zone.CHASHITSU,
    )
    world_harness.runtime.apply_belief_promotion(
        agent_id=a, other_agent_id="a_other_001", belief_kind="curious",
    )
    world_harness.runtime.apply_belief_promotion(
        agent_id=a, other_agent_id="a_other_001", belief_kind="trust",
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert bonds[0].latest_belief_kind == "trust"


def test_apply_belief_promotion_no_op_when_bond_missing(
    world_harness: RuntimeHarness,
) -> None:
    """A promotion without a prior bond is silently dropped (sink fail-soft)."""
    a = _register(world_harness, "kant", zone=Zone.STUDY)
    world_harness.runtime.apply_belief_promotion(
        agent_id=a, other_agent_id="a_unknown_999", belief_kind="trust",
    )
    bonds = world_harness.runtime._agents[a].state.relationships
    assert bonds == []


def test_apply_belief_promotion_no_op_when_agent_unregistered(
    world_harness: RuntimeHarness,
) -> None:
    """A promotion against an unknown agent does not crash."""
    world_harness.runtime.apply_belief_promotion(
        agent_id="a_unregistered", other_agent_id="a_other_001", belief_kind="clash",
    )


def test_apply_belief_promotion_preserves_other_bonds(
    world_harness: RuntimeHarness,
) -> None:
    """Stamping one bond's belief_kind does not touch sibling bonds."""
    a = _register(world_harness, "kant", zone=Zone.AGORA)
    world_harness.runtime.apply_affinity_delta(
        agent_id=a, other_agent_id="a_friend_001", delta=0.50, tick=1,
    )
    world_harness.runtime.apply_affinity_delta(
        agent_id=a, other_agent_id="a_rival_001", delta=-0.50, tick=2,
    )
    world_harness.runtime.apply_belief_promotion(
        agent_id=a, other_agent_id="a_rival_001", belief_kind="clash",
    )
    bonds_by_other = {
        b.other_agent_id: b
        for b in world_harness.runtime._agents[a].state.relationships
    }
    assert bonds_by_other["a_friend_001"].latest_belief_kind is None
    assert bonds_by_other["a_rival_001"].latest_belief_kind == "clash"
