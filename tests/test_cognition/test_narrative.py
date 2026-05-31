"""Unit tests for the pure ``cognition.narrative`` module (M11-A).

Covers the three pure functions: deterministic SWM rendering for embedding, the
cosine-coherence helper with its honest ``None`` degeneracies, and the
structured ``NarrativeArc`` distillation (segment honesty, ordering, skip
conditions, determinism). See
``.steering/20260527-m11-a-narrative-arc-coherence/decisions.md``.
"""

from __future__ import annotations

import math

import pytest

from erre_sandbox.cognition.narrative import (
    compute_coherence,
    render_swm_for_embedding,
    synthesize_narrative_arc,
)
from erre_sandbox.cognition.world_model import synthesize_world_model
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.schemas import RelationshipBond, SemanticMemoryRecord, Zone

_AGENT = "kant"


def _entry(
    *,
    axis: str = "env",
    key: str = "agora",
    value: float = 0.6,
    confidence: float = 0.5,
    cited: tuple[str, ...] = ("m1",),
    tick: int = 100,
) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=confidence,
        cited_memory_ids=cited,
        last_updated_tick=tick,
    )


def _record(other: str, *, belief_kind: str = "trust") -> SemanticMemoryRecord:
    return SemanticMemoryRecord(
        id=f"belief_{_AGENT}__{other}",
        agent_id=_AGENT,
        summary=f"belief about {other}",
        belief_kind=belief_kind,  # type: ignore[arg-type]
        confidence=0.8,
    )


def _bond(other: str, *, zone: Zone = Zone.AGORA, tick: int = 100) -> RelationshipBond:
    return RelationshipBond(
        other_agent_id=other,
        affinity=0.6,
        familiarity=0.5,
        last_interaction_zone=zone,
        last_interaction_tick=tick,
        ichigo_ichie_count=8,
    )


# --------------------------------------------------------------------------
# render_swm_for_embedding
# --------------------------------------------------------------------------


def test_render_empty_swm_is_empty_string() -> None:
    """An empty SWM renders to "" so the caller skips embedding (user fix 3)."""
    assert render_swm_for_embedding(SubjectiveWorldModel(entries=[])) == ""


def test_render_is_deterministic_and_order_preserving() -> None:
    """Same SWM → byte-identical text; entry (salience) order is preserved."""
    swm = SubjectiveWorldModel(
        entries=[_entry(key="agora", tick=100), _entry(key="garden", tick=50)],
    )
    first = render_swm_for_embedding(swm)
    assert first == render_swm_for_embedding(swm)
    lines = first.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("env/agora")  # input order, not re-sorted
    assert lines[1].startswith("env/garden")


def test_render_excludes_cited_ids() -> None:
    """Cited ids are opaque and must not pollute the embedding text (Codex L4)."""
    swm = SubjectiveWorldModel(entries=[_entry(cited=("secret-uuid-123",))])
    assert "secret-uuid-123" not in render_swm_for_embedding(swm)


# --------------------------------------------------------------------------
# compute_coherence
# --------------------------------------------------------------------------


def test_coherence_identical_is_one() -> None:
    assert compute_coherence([3.0, 4.0], [3.0, 4.0]) == pytest.approx(1.0)


def test_coherence_opposite_is_minus_one() -> None:
    assert compute_coherence([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_coherence_orthogonal_is_zero() -> None:
    assert compute_coherence([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_coherence_clamped_to_unit_interval() -> None:
    score = compute_coherence([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert score is not None
    assert -1.0 <= score <= 1.0


@pytest.mark.parametrize(
    ("u", "v"),
    [
        ([], [1.0]),  # empty
        ([1.0, 0.0], [1.0]),  # length mismatch
        ([0.0, 0.0], [1.0, 1.0]),  # zero norm
        ([math.nan, 1.0], [1.0, 1.0]),  # non-finite element
        ([math.inf, 1.0], [1.0, 1.0]),  # non-finite element
    ],
)
def test_coherence_degenerate_inputs_return_none(
    u: list[float],
    v: list[float],
) -> None:
    """Undefined cosine → honest ``None`` (never a fabricated number, Codex M2)."""
    assert compute_coherence(u, v) is None


# --------------------------------------------------------------------------
# synthesize_narrative_arc
# --------------------------------------------------------------------------


def test_synthesize_fills_all_required_fields() -> None:
    swm = SubjectiveWorldModel(entries=[_entry()])
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=200,
        coherence_score=0.42,
        last_episodic_id="ep-1",
    )
    assert arc is not None
    assert arc.synthesized_at_tick == 200
    assert arc.coherence_score == pytest.approx(0.42)
    assert arc.last_episodic_pointer == "ep-1"
    assert len(arc.arc_segments) == 1
    seg = arc.arc_segments[0]
    assert seg.segment_label == "env/agora"
    assert seg.start_tick == seg.end_tick == 100
    assert seg.summary is None  # structured, never prose (DA-6)


def test_synthesize_segment_cited_subset_of_entry_cited() -> None:
    """Pure honesty: each segment's cited ids come verbatim from its entry."""
    swm = SubjectiveWorldModel(
        entries=[_entry(cited=("a", "b")), _entry(key="garden", cited=("c",))],
    )
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=10,
        coherence_score=0.1,
        last_episodic_id="ep",
    )
    assert arc is not None
    entry_cited = {cid for e in swm.entries for cid in e.cited_memory_ids}
    for seg in arc.arc_segments:
        assert set(seg.cited_memory_ids).issubset(entry_cited)


def test_synthesize_honesty_through_world_model_path() -> None:
    """Composition honesty: cited ⊆ belief record ids when SWM is synthesised."""
    records = [_record("nietzsche"), _record("rikyu")]
    bonds = [_bond("nietzsche", zone=Zone.AGORA), _bond("rikyu", zone=Zone.CHASHITSU)]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=120)
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=120,
        coherence_score=0.3,
        last_episodic_id="ep",
    )
    assert arc is not None
    belief_ids = {r.id for r in records}
    for seg in arc.arc_segments:
        assert set(seg.cited_memory_ids).issubset(belief_ids)


def test_synthesize_orders_segments_chronologically() -> None:
    """Top-K by salience are re-ordered by tick to read as an update-point list."""
    swm = SubjectiveWorldModel(
        entries=[
            _entry(key="agora", tick=300),
            _entry(key="garden", tick=100),
            _entry(key="study", tick=200),
        ],
    )
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=300,
        coherence_score=0.0,
        last_episodic_id="ep",
    )
    assert arc is not None
    ticks = [s.start_tick for s in arc.arc_segments]
    assert ticks == sorted(ticks)


def test_synthesize_caps_and_clamps_segments() -> None:
    """≤5 segments; an over-large max_segments clamps (no ValidationError, L3)."""
    swm = SubjectiveWorldModel(
        entries=[_entry(key=f"z{i}", tick=i) for i in range(8)],
    )
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=10,
        coherence_score=0.0,
        last_episodic_id="ep",
        max_segments=10,
    )
    assert arc is not None
    assert len(arc.arc_segments) == 5


def test_synthesize_clamps_coherence_score() -> None:
    swm = SubjectiveWorldModel(entries=[_entry()])
    arc = synthesize_narrative_arc(
        swm,
        synthesized_at_tick=1,
        coherence_score=1.5,
        last_episodic_id="ep",
    )
    assert arc is not None
    assert arc.coherence_score == 1.0


@pytest.mark.parametrize("last_episodic_id", [None, ""])
def test_synthesize_skips_without_pointer(last_episodic_id: str | None) -> None:
    """No episodic pointer → None (never an empty last_episodic_pointer)."""
    swm = SubjectiveWorldModel(entries=[_entry()])
    assert (
        synthesize_narrative_arc(
            swm,
            synthesized_at_tick=1,
            coherence_score=0.0,
            last_episodic_id=last_episodic_id,
        )
        is None
    )


def test_synthesize_skips_empty_swm() -> None:
    assert (
        synthesize_narrative_arc(
            SubjectiveWorldModel(entries=[]),
            synthesized_at_tick=1,
            coherence_score=0.0,
            last_episodic_id="ep",
        )
        is None
    )


def test_synthesize_is_deterministic() -> None:
    swm = SubjectiveWorldModel(
        entries=[_entry(key="agora", tick=100), _entry(key="garden", tick=50)],
    )
    kwargs = {
        "synthesized_at_tick": 100,
        "coherence_score": 0.25,
        "last_episodic_id": "ep",
    }
    first = synthesize_narrative_arc(swm, **kwargs)  # type: ignore[arg-type]
    second = synthesize_narrative_arc(swm, **kwargs)  # type: ignore[arg-type]
    assert first is not None
    assert second is not None
    assert first.model_dump() == second.model_dump()
