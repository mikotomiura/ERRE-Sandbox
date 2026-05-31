"""Unit tests for the M10-C write-back path (``cognition.world_model``).

Covers the bounded LLM value-modulation channel:

* ``apply_world_model_update_hint`` — entry-local citation verification
  (DA-M10C-3), value-only bounded nudge with sign preservation (DA-M10C-4), and
  rejection of free-form / un-exposed / mismatched hints (the golden invariant).
* ``reconcile_world_model`` — evidence floor authority: a modulation is carried
  only while its floor entry is fingerprint-identical, capped at
  ``MAX_TOTAL_MODULATION``, and dropped when evidence moves (DA-M10C-2).
* ``belief_record_id`` — the single-source id helper (DA-M10C-10).
* adoption-rate **gate selectivity** on a mixed fixture (DA-M10C-8) and the STEP
  property tests (cap convergence / orphan drop / floor reset).

See ``.steering/20260526-m10-c-world-model-update-hint/decisions.md``.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.belief import maybe_promote_belief
from erre_sandbox.cognition.belief_ids import belief_record_id
from erre_sandbox.cognition.prompting import visible_entry_citations
from erre_sandbox.cognition.world_model import (
    MAX_TOTAL_MODULATION,
    VALUE_STEP,
    WorldModelRuntimeState,
    apply_world_model_update_hint,
    reconcile_world_model,
    synthesize_world_model,
)
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelUpdateHint,
)
from erre_sandbox.schemas import (
    CognitiveHabit,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    RelationshipBond,
    SemanticMemoryRecord,
    Zone,
)

_NIETZSCHE = belief_record_id("kant", "nietzsche")
_RIKYU = belief_record_id("kant", "rikyu")


def _entry(
    axis: str,
    key: str,
    *,
    value: float,
    confidence: float = 0.6,
    cited: tuple[str, ...] = (_NIETZSCHE,),
    last_updated_tick: int = 100,
) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=confidence,
        cited_memory_ids=cited,
        last_updated_tick=last_updated_tick,
    )


def _hint(
    axis: str,
    key: str,
    direction: str,
    cited: tuple[str, ...],
) -> WorldModelUpdateHint:
    return WorldModelUpdateHint(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        direction=direction,  # type: ignore[arg-type]
        cited_memory_ids=cited,
    )


def _swm(*entries: WorldModelEntry) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(entries=list(entries))


# ---------- belief_record_id single source (DA-M10C-10) --------------------


def test_belief_record_id_encoding() -> None:
    assert belief_record_id("kant", "nietzsche") == "belief_kant__nietzsche"


def test_belief_record_id_matches_minted_record() -> None:
    """The id helper matches what belief.py actually mints (parity, no drift)."""
    record = maybe_promote_belief(
        RelationshipBond(
            other_agent_id="nietzsche", affinity=0.9, ichigo_ichie_count=10
        ),
        agent_id="kant",
        persona=_persona("kant"),
        addressee_persona=_persona("nietzsche"),
    )
    assert record is not None
    assert record.id == belief_record_id("kant", "nietzsche")


# ---------- apply: adoption + bounded nudge --------------------------------


def test_apply_strengthen_increases_magnitude_only() -> None:
    swm = _swm(_entry("env", "agora", value=0.40, confidence=0.6))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "strengthen", (_NIETZSCHE,)),
        exposed,
    )
    assert out is not None
    e = out.entries[0]
    assert e.value == pytest.approx(0.40 + VALUE_STEP)
    # confidence / recency / cited are floor-derived and must NOT move (HIGH-3).
    assert e.confidence == pytest.approx(0.6)
    assert e.last_updated_tick == 100
    assert e.cited_memory_ids == (_NIETZSCHE,)


def test_apply_weaken_decreases_magnitude() -> None:
    swm = _swm(_entry("env", "agora", value=0.40))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "weaken", (_NIETZSCHE,)),
        exposed,
    )
    assert out is not None
    assert out.entries[0].value == pytest.approx(0.40 - VALUE_STEP)


def test_apply_preserves_sign_for_negative_entry() -> None:
    swm = _swm(_entry("self", "relational_disposition", value=-0.40))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("self", "relational_disposition", "strengthen", (_NIETZSCHE,)),
        exposed,
    )
    assert out is not None
    assert out.entries[0].value == pytest.approx(-(0.40 + VALUE_STEP))


def test_apply_weaken_never_crosses_zero() -> None:
    swm = _swm(_entry("env", "agora", value=0.03))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "weaken", (_NIETZSCHE,)),
        exposed,
    )
    assert out is not None
    assert out.entries[0].value == pytest.approx(0.0)  # floored at 0, no sign flip


def test_apply_no_change_is_noop() -> None:
    swm = _swm(_entry("env", "agora", value=0.40))
    exposed = visible_entry_citations(swm.entries)
    assert (
        apply_world_model_update_hint(
            swm,
            _hint("env", "agora", "no_change", (_NIETZSCHE,)),
            exposed,
        )
        is None
    )


def test_apply_zero_valued_entry_has_no_sign_to_push() -> None:
    swm = _swm(_entry("env", "agora", value=0.0))
    exposed = visible_entry_citations(swm.entries)
    assert (
        apply_world_model_update_hint(
            swm,
            _hint("env", "agora", "strengthen", (_NIETZSCHE,)),
            exposed,
        )
        is None
    )


# ---------- apply: golden rejections (the authority gate) -------------------


def test_apply_rejects_uncited_id_not_on_entry() -> None:
    """A belief id never displayed on the target entry → rejected (hallucination)."""
    swm = _swm(_entry("env", "agora", value=0.40, cited=(_NIETZSCHE,)))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "strengthen", ("belief_kant__plato",)),
        exposed,
    )
    assert out is None


def test_apply_rejects_entry_not_displayed_this_turn() -> None:
    """Hint targets an (axis,key) absent from the exposed map → rejected."""
    swm = _swm(_entry("env", "agora", value=0.40))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("self", "relational_disposition", "strengthen", (_NIETZSCHE,)),
        exposed,
    )
    assert out is None


def test_apply_rejects_free_form_when_nothing_exposed() -> None:
    """No Held entries shown ⇒ no authority root ⇒ every hint is rejected."""
    swm = _swm(_entry("env", "agora", value=0.40))
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "strengthen", (_NIETZSCHE,)),
        {},  # nothing displayed this turn
    )
    assert out is None


def test_apply_rejects_partial_citation_overreach() -> None:
    """One valid + one un-displayed id ⇒ not a subset ⇒ rejected (no laundering)."""
    swm = _swm(_entry("env", "agora", value=0.40, cited=(_NIETZSCHE,)))
    exposed = visible_entry_citations(swm.entries)
    out = apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "strengthen", (_NIETZSCHE, "belief_kant__plato")),
        exposed,
    )
    assert out is None


def test_apply_rejects_citation_truncated_off_display() -> None:
    """A real cited id that fell past the per-entry display cap is not citable."""
    # self entry with 3 cited ids; only the first 2 (sorted) are displayed.
    swm = _swm(
        _entry(
            "self",
            "relational_disposition",
            value=0.40,
            cited=("belief_kant__a", "belief_kant__b", "belief_kant__z"),
        ),
    )
    exposed = visible_entry_citations(swm.entries, max_citations=2)
    # "belief_kant__z" sorts last, so it is truncated off the display.
    out = apply_world_model_update_hint(
        swm,
        _hint("self", "relational_disposition", "strengthen", ("belief_kant__z",)),
        exposed,
    )
    assert out is None


# ---------- reconcile: evidence floor authority (DA-M10C-2) -----------------


def test_reconcile_none_state_equals_floor() -> None:
    floor = _swm(_entry("env", "agora", value=0.40))
    state = reconcile_world_model(None, floor)
    assert state.base_floor == floor
    assert state.modulated == floor


def test_reconcile_carries_modulation_when_evidence_unchanged() -> None:
    floor_entry = _entry("env", "agora", value=0.40)
    prior = WorldModelRuntimeState(
        base_floor=_swm(floor_entry),
        modulated=_swm(_entry("env", "agora", value=0.50)),  # +0.10 nudge
    )
    new_floor = _swm(_entry("env", "agora", value=0.40))  # identical evidence
    out = reconcile_world_model(prior, new_floor)
    assert out.modulated.entries[0].value == pytest.approx(0.50)  # carried


def test_reconcile_caps_carried_modulation() -> None:
    prior = WorldModelRuntimeState(
        base_floor=_swm(_entry("env", "agora", value=0.40)),
        modulated=_swm(_entry("env", "agora", value=0.90)),  # absurd drift
    )
    new_floor = _swm(_entry("env", "agora", value=0.40))
    out = reconcile_world_model(prior, new_floor)
    assert out.modulated.entries[0].value == pytest.approx(0.40 + MAX_TOTAL_MODULATION)


def test_reconcile_drops_modulation_when_evidence_moves() -> None:
    prior = WorldModelRuntimeState(
        base_floor=_swm(_entry("env", "agora", value=0.40)),
        modulated=_swm(_entry("env", "agora", value=0.50)),
    )
    # value moved 0.40 -> 0.42: fingerprint differs, so the stale nudge is dropped.
    new_floor = _swm(_entry("env", "agora", value=0.42))
    out = reconcile_world_model(prior, new_floor)
    assert out.modulated.entries[0].value == pytest.approx(0.42)


def test_reconcile_drops_orphan_when_entry_disappears() -> None:
    prior = WorldModelRuntimeState(
        base_floor=_swm(_entry("env", "agora", value=0.40)),
        modulated=_swm(_entry("env", "agora", value=0.50)),
    )
    new_floor = _swm(_entry("self", "relational_disposition", value=0.30))
    out = reconcile_world_model(prior, new_floor)
    keys = {(e.axis, e.key) for e in out.modulated.entries}
    assert keys == {("self", "relational_disposition")}


def test_reconcile_confidence_and_recency_always_from_floor() -> None:
    prior = WorldModelRuntimeState(
        base_floor=_swm(
            _entry("env", "agora", value=0.40, confidence=0.6, last_updated_tick=100)
        ),
        modulated=_swm(
            _entry("env", "agora", value=0.50, confidence=0.6, last_updated_tick=100)
        ),
    )
    new_floor = _swm(
        _entry("env", "agora", value=0.40, confidence=0.6, last_updated_tick=100)
    )
    out = reconcile_world_model(prior, new_floor)
    e = out.modulated.entries[0]
    assert e.confidence == pytest.approx(0.6)
    assert e.last_updated_tick == 100


# ---------- property: STEP behaviour over a tick loop (DA-M10C-8) -----------


def test_repeated_strengthen_converges_to_cap() -> None:
    """A persistent same-direction nudge saturates at floor + MAX_TOTAL, no further."""
    floor = _swm(_entry("env", "agora", value=0.40))
    hint = _hint("env", "agora", "strengthen", (_NIETZSCHE,))
    state: WorldModelRuntimeState | None = None
    injected: list[float] = []
    for _ in range(30):
        rec = reconcile_world_model(state, floor)
        injected.append(rec.modulated.entries[0].value)
        exposed = visible_entry_citations(rec.modulated.entries)
        nudged = apply_world_model_update_hint(rec.modulated, hint, exposed)
        state = WorldModelRuntimeState(
            base_floor=floor,
            modulated=nudged if nudged is not None else rec.modulated,
        )
    cap = 0.40 + MAX_TOTAL_MODULATION
    assert max(injected) <= cap + 1e-9  # injected prompt never shows past the cap
    assert injected[-1] == pytest.approx(cap)  # and it does reach it


def test_floor_change_resets_then_remodulates() -> None:
    """When evidence shifts the carried nudge is dropped; modulation restarts."""
    hint = _hint("env", "agora", "strengthen", (_NIETZSCHE,))
    floor_a = _swm(_entry("env", "agora", value=0.40))
    state = reconcile_world_model(None, floor_a)
    exposed = visible_entry_citations(state.modulated.entries)
    nudged = apply_world_model_update_hint(state.modulated, hint, exposed)
    assert nudged is not None
    state = WorldModelRuntimeState(base_floor=floor_a, modulated=nudged)
    # evidence moves: the nudge must not survive onto the new floor value.
    floor_b = _swm(_entry("env", "agora", value=0.10))
    out = reconcile_world_model(state, floor_b)
    assert out.modulated.entries[0].value == pytest.approx(0.10)


# ---------- adoption rate = gate selectivity (DA-M10C-8) --------------------


def test_adoption_rate_within_band_for_mixed_fixture() -> None:
    """Adopted/total on a representative mixed hint fixture lands in [0.05, 0.40].

    Per Codex MEDIUM-1 the band measures *gate selectivity* (how often a realistic
    mix of hints is accepted), not the nudge step size. The fixture is deliberately
    invalid-heavy (free-form, un-exposed, no_change, hallucinated cite dominate);
    only a few well-formed, correctly-cited hints are adopted.
    """
    swm = _swm(
        _entry("env", "agora", value=0.40, cited=(_NIETZSCHE,)),
        _entry(
            "self", "relational_disposition", value=0.30, cited=(_NIETZSCHE, _RIKYU)
        ),
    )
    exposed = visible_entry_citations(swm.entries)
    hints = [
        # adopted (2):
        _hint("env", "agora", "strengthen", (_NIETZSCHE,)),
        _hint("self", "relational_disposition", "weaken", (_RIKYU,)),
        # not adopted (10): no_change, un-exposed entries, hallucinated cites.
        _hint("env", "agora", "no_change", (_NIETZSCHE,)),
        _hint("self", "relational_disposition", "no_change", (_NIETZSCHE,)),
        _hint("concept", "freedom", "strengthen", (_NIETZSCHE,)),
        _hint("norm", "duty", "strengthen", (_NIETZSCHE,)),
        _hint("temporal", "horizon", "weaken", (_RIKYU,)),
        _hint("env", "garden", "strengthen", (_NIETZSCHE,)),
        _hint("env", "agora", "strengthen", ("belief_kant__plato",)),
        _hint("self", "relational_disposition", "strengthen", ("belief_kant__hume",)),
        _hint("env", "agora", "weaken", ("belief_kant__zzz",)),
        _hint(
            "self",
            "relational_disposition",
            "strengthen",
            (_NIETZSCHE, "belief_kant__x"),
        ),
    ]
    adopted = sum(
        1 for h in hints if apply_world_model_update_hint(swm, h, exposed) is not None
    )
    rate = adopted / len(hints)
    assert 0.05 <= rate <= 0.40, f"adoption rate {rate} out of band"


def test_reconcile_carries_through_synthesized_mean_floor() -> None:
    """HIGH-1: a floor built from float means stays fingerprint-stable on re-synth.

    Drives the *real* ``synthesize_world_model`` (value/confidence = ``sum()/len()``
    means, not hand-typed literals) twice on identical evidence, applies a nudge to
    the first floor, then reconciles against the second. The nudge must survive —
    if the fingerprint compared raw floats it could spuriously reset every tick.
    """
    records = [
        SemanticMemoryRecord(
            id=belief_record_id("kant", "nietzsche"),
            agent_id="kant",
            summary="belief about nietzsche",
            belief_kind="clash",
            confidence=0.8,
        ),
        SemanticMemoryRecord(
            id=belief_record_id("kant", "rikyu"),
            agent_id="kant",
            summary="belief about rikyu",
            belief_kind="trust",
            confidence=0.7,
        ),
    ]
    bonds = [
        RelationshipBond(
            other_agent_id="nietzsche",
            affinity=-0.7,
            familiarity=0.55,  # 0.55 has no exact binary float; exercises mean jitter
            last_interaction_zone=Zone.AGORA,
            last_interaction_tick=5,
            ichigo_ichie_count=8,
        ),
        RelationshipBond(
            other_agent_id="rikyu",
            affinity=0.6,
            familiarity=0.45,
            last_interaction_zone=Zone.CHASHITSU,
            last_interaction_tick=6,
            ichigo_ichie_count=7,
        ),
    ]
    floor1 = synthesize_world_model(records, bonds, agent_id="kant", current_tick=120)
    env = next(e for e in floor1.entries if (e.axis, e.key) == ("env", "agora"))
    nudged_value = _nudge_value_for_test(env.value)
    modulated = SubjectiveWorldModel(
        entries=[
            e.model_copy(update={"value": nudged_value})
            if (e.axis, e.key) == ("env", "agora")
            else e
            for e in floor1.entries
        ],
    )
    state = WorldModelRuntimeState(base_floor=floor1, modulated=modulated)
    # Re-synthesise identical evidence at a later tick (recency uses current_tick,
    # but env last_updated_tick keys off the fixed bond tick, so fingerprint holds).
    floor2 = synthesize_world_model(records, bonds, agent_id="kant", current_tick=121)
    out = reconcile_world_model(state, floor2)
    carried = next(
        e for e in out.modulated.entries if (e.axis, e.key) == ("env", "agora")
    )
    assert carried.value == pytest.approx(nudged_value)  # not reset to the floor


def _nudge_value_for_test(value: float) -> float:
    sign = 1.0 if value > 0 else -1.0
    return sign * min(1.0, abs(value) + VALUE_STEP)


def test_apply_is_pure_does_not_mutate_input() -> None:
    swm = _swm(_entry("env", "agora", value=0.40))
    exposed = visible_entry_citations(swm.entries)
    before = swm.model_dump()
    apply_world_model_update_hint(
        swm,
        _hint("env", "agora", "strengthen", (_NIETZSCHE,)),
        exposed,
    )
    assert swm.model_dump() == before


# ---------- shared persona fixture -----------------------------------------


def _persona(name: str) -> PersonaSpec:
    return PersonaSpec(
        persona_id=name,
        display_name=name.title(),
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
        preferred_zones=[Zone.AGORA],
    )
