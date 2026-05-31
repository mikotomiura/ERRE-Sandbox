"""Unit tests for ``cognition.world_model.synthesize_world_model`` (M10-B).

Covers the pure read-only SWM synthesis: evidence→axis routing (env / self),
the observable-evidence honesty invariant (``cited ⊆ input record ids``), the
DA-9 dyadic⊥class-wise gate on the ``self`` axis, deterministic ordering, and
persona-differentiated entry profiles (the fixture-level Burrows-orthogonal
signal). See
``.steering/20260526-m10-b-swm-synthesis-prompt-injection/decisions.md``.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.belief import maybe_promote_belief
from erre_sandbox.cognition.world_model import synthesize_world_model
from erre_sandbox.schemas import (
    CognitiveHabit,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    RelationshipBond,
    SemanticMemoryRecord,
    Zone,
)

_AGENT = "kant"


def _record(
    other: str,
    *,
    agent: str = _AGENT,
    belief_kind: str | None = "trust",
    confidence: float = 0.8,
) -> SemanticMemoryRecord:
    return SemanticMemoryRecord(
        id=f"belief_{agent}__{other}",
        agent_id=agent,
        summary=f"belief about {other}",
        belief_kind=belief_kind,  # type: ignore[arg-type]
        confidence=confidence,
    )


def _bond(
    other: str,
    *,
    affinity: float = 0.6,
    familiarity: float = 0.5,
    zone: Zone | None = Zone.AGORA,
    tick: int | None = 100,
    count: int = 8,
) -> RelationshipBond:
    return RelationshipBond(
        other_agent_id=other,
        affinity=affinity,
        familiarity=familiarity,
        last_interaction_zone=zone,
        last_interaction_tick=tick,
        ichigo_ichie_count=count,
    )


# ---------- routing --------------------------------------------------------


def test_synthesizes_env_and_self_from_two_promoted_dyads() -> None:
    """Two promoted dyads in two zones → one env entry per zone + one self."""
    records = [_record("nietzsche"), _record("rikyu")]
    bonds = [
        _bond("nietzsche", affinity=0.7, zone=Zone.AGORA),
        _bond("rikyu", affinity=0.5, zone=Zone.CHASHITSU),
    ]
    swm = synthesize_world_model(
        records,
        bonds,
        agent_id=_AGENT,
        current_tick=120,
    )
    axes_keys = {(e.axis, e.key) for e in swm.entries}
    assert ("env", "agora") in axes_keys
    assert ("env", "chashitsu") in axes_keys
    assert ("self", "relational_disposition") in axes_keys


def test_env_entry_aggregates_zone_affinity() -> None:
    """Two dyads in the same zone average their affinity into one env entry."""
    records = [_record("a"), _record("b")]
    bonds = [
        _bond("a", affinity=0.2, zone=Zone.STUDY),
        _bond("b", affinity=0.8, zone=Zone.STUDY),
    ]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=10)
    env = [e for e in swm.entries if e.axis == "env"]
    assert len(env) == 1
    assert env[0].key == "study"
    assert env[0].value == pytest.approx(0.5)


def test_bond_without_zone_skips_env_but_feeds_self() -> None:
    """A ``None`` last zone yields no env entry but still counts for self."""
    records = [_record("a"), _record("b")]
    bonds = [_bond("a", zone=None), _bond("b", zone=Zone.GARDEN)]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=10)
    env_zones = {e.key for e in swm.entries if e.axis == "env"}
    assert env_zones == {"garden"}  # 'a' had no zone
    # self still sees 2 distinct dyads → emitted.
    assert any(e.axis == "self" for e in swm.entries)


# ---------- DA-9 self gate -------------------------------------------------


def test_single_dyad_emits_no_self_entry() -> None:
    """One dyad is a dyadic relabel → no class-wise self entry (DA-M10B-3)."""
    swm = synthesize_world_model(
        [_record("nietzsche")],
        [_bond("nietzsche")],
        agent_id=_AGENT,
        current_tick=10,
    )
    assert all(e.axis != "self" for e in swm.entries)


def test_self_confidence_drops_when_dyads_conflict() -> None:
    """Opposing affinity signs lower self confidence (agreement factor)."""
    uniform = synthesize_world_model(
        [_record("a"), _record("b")],
        [_bond("a", affinity=0.6), _bond("b", affinity=0.7)],
        agent_id=_AGENT,
        current_tick=10,
    )
    conflict = synthesize_world_model(
        [_record("a"), _record("b")],
        [_bond("a", affinity=0.6), _bond("b", affinity=-0.7)],
        agent_id=_AGENT,
        current_tick=10,
    )
    self_uniform = next(e for e in uniform.entries if e.axis == "self")
    self_conflict = next(e for e in conflict.entries if e.axis == "self")
    assert self_uniform.confidence > self_conflict.confidence
    assert self_conflict.confidence == pytest.approx(0.0)  # balanced signs


# ---------- honesty: cited ⊆ input, evidence gates -------------------------


def test_cited_memory_ids_subset_of_input() -> None:
    """Every cited id is one of the input record ids (honesty invariant)."""
    records = [_record("a"), _record("b"), _record("c")]
    bonds = [_bond("a"), _bond("b", zone=Zone.STUDY), _bond("c", zone=Zone.GARDEN)]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=10)
    input_ids = {r.id for r in records}
    for entry in swm.entries:
        assert set(entry.cited_memory_ids) <= input_ids


def test_bond_without_promoted_record_produces_no_entry() -> None:
    """A bond with no matching belief record is not observable evidence."""
    swm = synthesize_world_model(
        [_record("a"), _record("b")],
        [
            _bond("a"),
            _bond("b", zone=Zone.STUDY),
            _bond("unpromoted", zone=Zone.GARDEN),
        ],
        agent_id=_AGENT,
        current_tick=10,
    )
    # No entry should cite an id for the unpromoted dyad, and garden (only the
    # unpromoted bond's zone) must be absent.
    assert all(e.key != "garden" for e in swm.entries if e.axis == "env")
    all_cited = {cid for e in swm.entries for cid in e.cited_memory_ids}
    assert f"belief_{_AGENT}__unpromoted" not in all_cited


def test_foreign_agent_record_rejected() -> None:
    """A record for another agent contributes nothing."""
    foreign = _record("x", agent="nietzsche")
    bond = _bond("x")
    swm = synthesize_world_model(
        [foreign],
        [bond],
        agent_id=_AGENT,
        current_tick=10,
    )
    assert swm.entries == []


def test_non_belief_record_rejected() -> None:
    """A reflection record (belief_kind None) is not promoted evidence."""
    plain = _record("a", belief_kind=None)
    swm = synthesize_world_model(
        [plain],
        [_bond("a")],
        agent_id=_AGENT,
        current_tick=10,
    )
    assert swm.entries == []


def test_orphan_record_without_bond_rejected() -> None:
    """A belief record with no matching bond cannot be cited."""
    swm = synthesize_world_model(
        [_record("ghost"), _record("a")],
        [_bond("a")],  # only 'a' has a bond; 'ghost' is orphaned
        agent_id=_AGENT,
        current_tick=10,
    )
    all_cited = {cid for e in swm.entries for cid in e.cited_memory_ids}
    assert f"belief_{_AGENT}__ghost" not in all_cited


# ---------- determinism + bounds -------------------------------------------


def test_deterministic_for_fixed_input() -> None:
    """Same input → identical entries (axis/key/value/cited order)."""
    records = [_record("a"), _record("b"), _record("c")]
    bonds = [
        _bond("a", zone=Zone.STUDY, affinity=0.3),
        _bond("b", zone=Zone.AGORA, affinity=0.9),
        _bond("c", zone=Zone.GARDEN, affinity=-0.4),
    ]
    a = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=50)
    b = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=50)
    assert [e.model_dump() for e in a.entries] == [e.model_dump() for e in b.entries]


def test_cited_memory_ids_are_sorted() -> None:
    """cited_memory_ids is a sorted tuple (DA-M10B-8 determinism)."""
    records = [_record("b"), _record("a")]
    bonds = [_bond("b", zone=Zone.STUDY), _bond("a", zone=Zone.STUDY)]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=10)
    env = next(e for e in swm.entries if e.axis == "env")
    assert list(env.cited_memory_ids) == sorted(env.cited_memory_ids)


def test_max_entries_caps_output() -> None:
    """max_entries hard-caps the retained (top-salience) entries."""
    records = [_record(c) for c in "abcde"]
    bonds = [
        _bond("a", zone=Zone.STUDY),
        _bond("b", zone=Zone.AGORA),
        _bond("c", zone=Zone.GARDEN),
        _bond("d", zone=Zone.PERIPATOS),
        _bond("e", zone=Zone.CHASHITSU),
    ]
    swm = synthesize_world_model(
        records,
        bonds,
        agent_id=_AGENT,
        current_tick=10,
        max_entries=2,
    )
    assert len(swm.entries) == 2


def test_value_and_confidence_within_bounds() -> None:
    """Synthesised entries satisfy the schema bounds."""
    records = [_record("a"), _record("b")]
    bonds = [_bond("a", affinity=-1.0), _bond("b", affinity=1.0, zone=Zone.STUDY)]
    swm = synthesize_world_model(records, bonds, agent_id=_AGENT, current_tick=10)
    for e in swm.entries:
        assert -1.0 <= e.value <= 1.0
        assert 0.0 <= e.confidence <= 1.0
        assert len(e.cited_memory_ids) >= 1


# ---------- consistency with belief.py + persona separation ----------------


def _persona(pid: str) -> PersonaSpec:
    return PersonaSpec(
        persona_id=pid,
        display_name=pid.title(),
        era="—",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="x",
                source="x",
                flag=HabitFlag.FACT,
                mechanism="x",
            ),
        ],
        preferred_zones=[Zone.PERIPATOS],
    )


def test_belief_id_matches_belief_module() -> None:
    """The deterministic id this module reconstructs matches belief.py output.

    Guards against drift between ``world_model._belief_record_id`` and
    ``belief._belief_record_id`` without importing the private symbol.
    """
    bond = RelationshipBond(
        other_agent_id="nietzsche",
        affinity=0.9,
        ichigo_ichie_count=10,
    )
    record = maybe_promote_belief(
        bond,
        agent_id="kant",
        persona=_persona("kant"),
        addressee_persona=_persona("nietzsche"),
    )
    assert record is not None
    assert record.id == "belief_kant__nietzsche"


def test_persona_differentiated_entry_profiles() -> None:
    """Different evidence fixtures rise on different axes/values (Burrows ⊥).

    A 'social-positive' individual surfaces a strong positive self disposition;
    a 'study-recluse' individual surfaces env-dominant entries with a weak self
    — distinct entry profiles from the same synthesis function.
    """
    social = synthesize_world_model(
        [_record("a"), _record("b"), _record("c")],
        [
            _bond("a", affinity=0.8, zone=Zone.AGORA),
            _bond("b", affinity=0.7, zone=Zone.AGORA),
            _bond("c", affinity=0.75, zone=Zone.AGORA),
        ],
        agent_id=_AGENT,
        current_tick=10,
    )
    recluse = synthesize_world_model(
        [_record("a"), _record("b")],
        [
            _bond("a", affinity=0.1, zone=Zone.STUDY),
            _bond("b", affinity=-0.1, zone=Zone.PERIPATOS),
        ],
        agent_id=_AGENT,
        current_tick=10,
    )
    social_self = next(e for e in social.entries if e.axis == "self")
    recluse_self = next(e for e in recluse.entries if e.axis == "self")
    # Social: confident, strongly positive self disposition.
    assert social_self.value > 0.5
    assert social_self.confidence > 0.5
    # Recluse: near-zero / low-confidence self, env keys differ from social.
    assert abs(recluse_self.value) < 0.2
    social_zones = {e.key for e in social.entries if e.axis == "env"}
    recluse_zones = {e.key for e in recluse.entries if e.axis == "env"}
    assert social_zones != recluse_zones
