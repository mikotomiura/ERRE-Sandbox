"""Unit tests for ``cognition.cycle._decision_with_affinity`` (M7γ + M7δ M2).

The hint surfaces the *most salient* bond — γ MVP used recency only,
δ M7-R3-M2 tightens the rule to ``(|affinity|, last_interaction_tick)``
descending so the LLM-decision suffix matches the Godot
``ReasoningPanel`` Relationships foldout (which already sorts by
``|affinity|`` first).
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.cycle import _decision_with_affinity
from erre_sandbox.schemas import (
    AgentState,
    ERREMode,
    ERREModeName,
    Position,
    RelationshipBond,
    Zone,
)


def _make_state(*bonds: RelationshipBond) -> AgentState:
    return AgentState(
        agent_id="a_kant_001",
        persona_id="kant",
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
        relationships=list(bonds),
    )


def test_returns_decision_unchanged_when_no_bonds() -> None:
    state = _make_state()
    assert _decision_with_affinity("walk to peripatos", state) == "walk to peripatos"


def test_returns_none_when_decision_none_and_no_bonds() -> None:
    state = _make_state()
    assert _decision_with_affinity(None, state) is None


def test_picks_highest_magnitude_over_recency() -> None:
    """M7δ M2: a strong older bond outranks a weak recent bond."""
    weak_recent = RelationshipBond(
        other_agent_id="a_other_recent",
        affinity=0.05,
        last_interaction_tick=100,
    )
    strong_old = RelationshipBond(
        other_agent_id="a_other_strong",
        affinity=0.80,
        last_interaction_tick=10,
    )
    state = _make_state(weak_recent, strong_old)
    decorated = _decision_with_affinity("rationale", state)
    assert decorated is not None
    assert "a_other_strong" in decorated
    assert "a_other_recent" not in decorated


def test_negative_magnitude_outranks_positive_magnitude() -> None:
    """``|affinity|`` magnitude is what counts, not sign."""
    positive = RelationshipBond(
        other_agent_id="a_friend",
        affinity=0.30,
        last_interaction_tick=5,
    )
    negative = RelationshipBond(
        other_agent_id="a_rival",
        affinity=-0.65,
        last_interaction_tick=2,
    )
    state = _make_state(positive, negative)
    decorated = _decision_with_affinity("rationale", state)
    assert decorated is not None
    assert "a_rival" in decorated
    assert "-0.65" in decorated


def test_breaks_tie_on_recency_when_magnitudes_equal() -> None:
    """When two bonds share the same |affinity|, the more recent wins."""
    older = RelationshipBond(
        other_agent_id="a_older",
        affinity=0.50,
        last_interaction_tick=10,
    )
    newer = RelationshipBond(
        other_agent_id="a_newer",
        affinity=0.50,
        last_interaction_tick=20,
    )
    state = _make_state(older, newer)
    decorated = _decision_with_affinity("rationale", state)
    assert decorated is not None
    assert "a_newer" in decorated


def test_decoration_format_matches_panel_convention() -> None:
    """Hint format must include ``+/-NN.NN`` for the Godot panel parity."""
    bond = RelationshipBond(
        other_agent_id="a_other",
        affinity=0.65,
        last_interaction_tick=10,
    )
    state = _make_state(bond)
    decorated = _decision_with_affinity("walk", state)
    assert decorated is not None
    assert "+0.65" in decorated
    assert "affinity" in decorated


def test_hint_carries_alone_when_decision_none_but_bonds_exist() -> None:
    """When LLM decision is None and bonds exist, the hint is the entire string."""
    bond = RelationshipBond(
        other_agent_id="a_other",
        affinity=-0.45,
        last_interaction_tick=10,
    )
    state = _make_state(bond)
    decorated = _decision_with_affinity(None, state)
    assert decorated is not None
    assert "affinity" in decorated
    assert decorated.startswith("affinity=")


@pytest.mark.parametrize(
    "tick_value",
    [None, 0, 10, 100],
)
def test_handles_none_and_concrete_ticks_uniformly(tick_value: int | None) -> None:
    """``last_interaction_tick=None`` ranks below any concrete tick at equal mag."""
    none_bond = RelationshipBond(
        other_agent_id="a_no_tick",
        affinity=0.50,
        last_interaction_tick=None,
    )
    other_bond = RelationshipBond(
        other_agent_id="a_with_tick",
        affinity=0.50,
        last_interaction_tick=tick_value,
    )
    state = _make_state(none_bond, other_bond)
    decorated = _decision_with_affinity("rationale", state)
    assert decorated is not None
    if tick_value is None:
        # Both have None ticks; either is acceptable as long as we don't crash.
        assert ("a_no_tick" in decorated) or ("a_with_tick" in decorated)
    else:
        # Concrete tick wins the tie.
        assert "a_with_tick" in decorated
