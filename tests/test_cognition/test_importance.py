"""Unit tests for :mod:`erre_sandbox.cognition.importance`."""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.importance import estimate_importance
from erre_sandbox.schemas import (
    AffordanceEvent,
    BiorhythmEvent,
    ERREModeName,
    ERREModeShiftEvent,
    InternalEvent,
    PerceptionEvent,
    ProximityEvent,
    SpeechEvent,
    TemporalEvent,
    TimeOfDay,
    Zone,
    ZoneTransitionEvent,
)


def test_perception_base() -> None:
    obs = PerceptionEvent(
        tick=0,
        agent_id="a",
        modality="sight",
        source_zone=Zone.STUDY,
        content="shelves",
        intensity=0.5,
    )
    # intensity 0.5 = no delta, so base 0.3.
    assert estimate_importance(obs) == pytest.approx(0.3)


def test_perception_intensity_boosts() -> None:
    obs = PerceptionEvent(
        tick=0,
        agent_id="a",
        modality="sight",
        source_zone=Zone.STUDY,
        content="explosion",
        intensity=1.0,
    )
    # base 0.3 + 0.3 * (1.0 - 0.5) = 0.45
    assert estimate_importance(obs) == pytest.approx(0.45)


def test_speech_absolute_impact() -> None:
    obs = SpeechEvent(
        tick=0,
        agent_id="a",
        speaker_id="b",
        utterance="...",
        emotional_impact=-0.9,
    )
    # base 0.6 + 0.3 * |−0.9| = 0.87
    assert estimate_importance(obs) == pytest.approx(0.87)


def test_zone_transition_returns_base() -> None:
    obs = ZoneTransitionEvent(
        tick=0,
        agent_id="a",
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    assert estimate_importance(obs) == pytest.approx(0.5)


def test_erre_mode_shift_returns_base() -> None:
    obs = ERREModeShiftEvent(
        tick=0,
        agent_id="a",
        previous=ERREModeName.DEEP_WORK,
        current=ERREModeName.PERIPATETIC,
        reason="zone",
    )
    assert estimate_importance(obs) == pytest.approx(0.8)


def test_internal_hint_scales() -> None:
    high = InternalEvent(
        tick=0,
        agent_id="a",
        content="deep insight",
        importance_hint=1.0,
    )
    low = InternalEvent(
        tick=0,
        agent_id="a",
        content="idle thought",
        importance_hint=0.0,
    )
    assert estimate_importance(high) > estimate_importance(low)
    # Both must stay in [0, 1].
    assert 0.0 <= estimate_importance(low) <= 1.0
    assert 0.0 <= estimate_importance(high) <= 1.0


def test_clamped_to_unit() -> None:
    obs = SpeechEvent(
        tick=0,
        agent_id="a",
        speaker_id="b",
        utterance="...",
        emotional_impact=1.0,
    )
    # base 0.6 + 0.3 = 0.9, still within [0,1]
    value = estimate_importance(obs)
    assert 0.0 <= value <= 1.0


# ---------- M6-A-2b: new Observation variants (default handling) ----------


def test_affordance_returns_base() -> None:
    obs = AffordanceEvent(
        tick=0,
        agent_id="a",
        prop_id="tea_bowl_01",
        prop_kind="tea_bowl",
        zone=Zone.CHASHITSU,
        distance=0.8,
        salience=0.9,
    )
    assert estimate_importance(obs) == pytest.approx(0.5)


def test_proximity_returns_base() -> None:
    obs = ProximityEvent(
        tick=0,
        agent_id="a",
        other_agent_id="b",
        distance_prev=7.0,
        distance_now=3.0,
        crossing="enter",
    )
    assert estimate_importance(obs) == pytest.approx(0.4)


def test_temporal_returns_base() -> None:
    obs = TemporalEvent(
        tick=0,
        agent_id="a",
        period_prev=TimeOfDay.DAWN,
        period_now=TimeOfDay.MORNING,
    )
    assert estimate_importance(obs) == pytest.approx(0.3)


def test_biorhythm_returns_base() -> None:
    obs = BiorhythmEvent(
        tick=0,
        agent_id="a",
        signal="fatigue",
        level_prev=0.4,
        level_now=0.6,
        threshold_crossed="up",
    )
    assert estimate_importance(obs) == pytest.approx(0.6)
