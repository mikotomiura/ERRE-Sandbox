"""Unit tests for :mod:`erre_sandbox.cognition.state` (pure CSDG math)."""

from __future__ import annotations

from random import Random

import pytest

from erre_sandbox.cognition.parse import LLMPlan
from erre_sandbox.cognition.state import (
    DEFAULT_CONFIG,
    StateUpdateConfig,
    advance_physical,
    apply_llm_delta,
)
from erre_sandbox.schemas import (
    AffordanceEvent,
    BiorhythmEvent,
    Cognitive,
    Physical,
    ProximityEvent,
    SpeechEvent,
    TemporalEvent,
    TimeOfDay,
    Zone,
    ZoneTransitionEvent,
)


def _plan(
    *,
    valence_delta: float = 0.0,
    arousal_delta: float = 0.0,
    motivation_delta: float = 0.0,
    importance_hint: float = 0.5,
) -> LLMPlan:
    return LLMPlan(
        thought="x",
        valence_delta=valence_delta,
        arousal_delta=arousal_delta,
        motivation_delta=motivation_delta,
        importance_hint=importance_hint,
    )


def test_advance_physical_returns_physical() -> None:
    out = advance_physical(Physical(), events=[], rng=Random(0))
    assert isinstance(out, Physical)


def test_advance_physical_mood_drifts_towards_zero() -> None:
    prev = Physical(mood_baseline=0.8)
    out = advance_physical(prev, events=[], config=DEFAULT_CONFIG, rng=None)
    # With decay_rate=0.05 → mood should drop from 0.8 towards 0.0.
    assert 0.0 < out.mood_baseline < 0.8


def test_advance_physical_negative_speech_raises_load() -> None:
    prev = Physical(cognitive_load=0.2)
    event = SpeechEvent(
        tick=0,
        agent_id="a",
        speaker_id="b",
        utterance="no",
        emotional_impact=-0.8,
    )
    out = advance_physical(prev, events=[event], rng=None)
    assert out.cognitive_load > 0.2 * (1.0 - DEFAULT_CONFIG.decay_rate)


def test_advance_physical_zone_entry_nudges_mood() -> None:
    prev = Physical(mood_baseline=0.0)
    event = ZoneTransitionEvent(
        tick=0,
        agent_id="a",
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    out = advance_physical(prev, events=[event], rng=None)
    assert out.mood_baseline > 0.0


def test_advance_physical_rng_is_deterministic() -> None:
    prev = Physical(mood_baseline=0.1)
    out_a = advance_physical(prev, events=[], rng=Random(42))
    out_b = advance_physical(prev, events=[], rng=Random(42))
    assert out_a.mood_baseline == out_b.mood_baseline


def test_advance_physical_decays_emotional_conflict() -> None:
    """M7δ: emotional_conflict drops by 0.02 per tick toward 0."""
    prev = Physical(emotional_conflict=0.30)
    out = advance_physical(prev, events=[], rng=None)
    assert out.emotional_conflict == pytest.approx(0.28)


def test_advance_physical_emotional_conflict_floor_at_zero() -> None:
    """Decay does not go negative once conflict has fully decayed."""
    prev = Physical(emotional_conflict=0.01)
    out = advance_physical(prev, events=[], rng=None)
    assert out.emotional_conflict == 0.0


def test_apply_llm_delta_monotone_in_valence() -> None:
    prev = Cognitive(valence=0.0)
    pos = apply_llm_delta(prev, _plan(valence_delta=0.3), rng=None)
    neg = apply_llm_delta(prev, _plan(valence_delta=-0.3), rng=None)
    assert pos.valence > neg.valence


def test_apply_llm_delta_clips_oversized_delta() -> None:
    # Pydantic already bounds LLMPlan.valence_delta to [-1, 1]; apply_llm_delta
    # then clips further to ``max_llm_delta`` (0.3) before the weight (0.7).
    prev = Cognitive(valence=0.0)
    out = apply_llm_delta(prev, _plan(valence_delta=1.0), rng=None)
    # valence ≈ 0.0 + 0.3 * 0.7 = 0.21 (noise is 0 when rng=None).
    assert out.valence == pytest.approx(0.21)


def test_apply_llm_delta_clamps_to_range() -> None:
    prev = Cognitive(valence=0.99)
    out = apply_llm_delta(prev, _plan(valence_delta=1.0), rng=None)
    assert -1.0 <= out.valence <= 1.0


def test_apply_llm_delta_motivation_in_unit() -> None:
    prev = Cognitive(motivation=0.5)
    out = apply_llm_delta(prev, _plan(motivation_delta=1.0), rng=None)
    assert 0.0 <= out.motivation <= 1.0


def test_config_override_changes_behaviour() -> None:
    prev = Physical(mood_baseline=0.5)
    zero_decay = StateUpdateConfig(decay_rate=0.0)
    out_zero = advance_physical(prev, events=[], config=zero_decay, rng=None)
    out_default = advance_physical(prev, events=[], rng=None)
    assert out_zero.mood_baseline == pytest.approx(0.5)
    assert out_default.mood_baseline < 0.5


# ---------- M6-A-2b: default handling for new Observation variants ----------


def test_advance_physical_salient_affordance_nudges_mood_up() -> None:
    prev = Physical(mood_baseline=0.0)
    salient = AffordanceEvent(
        tick=0,
        agent_id="a",
        prop_id="tea_bowl_01",
        prop_kind="tea_bowl",
        zone=Zone.CHASHITSU,
        distance=0.4,
        salience=1.0,
    )
    out = advance_physical(prev, events=[salient], rng=None)
    assert out.mood_baseline > 0.0


def test_advance_physical_mundane_affordance_neutral() -> None:
    prev = Physical(mood_baseline=0.0)
    mundane = AffordanceEvent(
        tick=0,
        agent_id="a",
        prop_id="cushion",
        prop_kind="cushion",
        zone=Zone.CHASHITSU,
        distance=0.4,
        salience=0.5,
    )
    out = advance_physical(prev, events=[mundane], rng=None)
    # Pivoted around salience=0.5 so a neutral prop contributes exactly zero.
    assert out.mood_baseline == pytest.approx(0.0)


def test_advance_physical_proximity_enter_positive_leave_negative() -> None:
    prev = Physical(mood_baseline=0.0)
    enter = ProximityEvent(
        tick=0,
        agent_id="a",
        other_agent_id="b",
        distance_prev=7.0,
        distance_now=3.0,
        crossing="enter",
    )
    leave = enter.model_copy(
        update={
            "distance_prev": 3.0,
            "distance_now": 7.0,
            "crossing": "leave",
        },
    )
    out_enter = advance_physical(prev, events=[enter], rng=None)
    out_leave = advance_physical(prev, events=[leave], rng=None)
    assert out_enter.mood_baseline > 0.0
    assert out_leave.mood_baseline < 0.0


def test_advance_physical_temporal_flat_positive() -> None:
    prev = Physical(mood_baseline=0.0)
    event = TemporalEvent(
        tick=0,
        agent_id="a",
        period_prev=TimeOfDay.DAWN,
        period_now=TimeOfDay.MORNING,
    )
    out = advance_physical(prev, events=[event], rng=None)
    assert out.mood_baseline > 0.0


def test_advance_physical_biorhythm_is_neutral() -> None:
    """Biorhythm is a readout of Physical — feeding it back would double-count."""
    prev = Physical(mood_baseline=0.0)
    event = BiorhythmEvent(
        tick=0,
        agent_id="a",
        signal="fatigue",
        level_prev=0.4,
        level_now=0.8,
        threshold_crossed="up",
    )
    out = advance_physical(prev, events=[event], rng=None)
    assert out.mood_baseline == pytest.approx(0.0)
