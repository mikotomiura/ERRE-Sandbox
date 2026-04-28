"""Unit tests for ``_pick_trigger_event`` (M9-A event-boundary observability).

Covers the priority vote, ``zone`` / ``ref_id`` mapping by kind, and
``secondary_kinds`` collection. Each test exercises one column of the
priority/resolution matrix in isolation so a regression on either axis
points directly at the offending row.

The helper is a pure function, so all fixtures are inline observations —
no ``CognitionCycle`` plumbing is required. Empty input returns ``None``;
every other input returns a fully-populated :class:`TriggerEventTag`.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.cycle import _pick_trigger_event
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
    TriggerEventTag,
    Zone,
    ZoneTransitionEvent,
)

# ---------- §1 Empty / fallback ---------------------------------------------


def test_empty_observations_returns_none() -> None:
    """No observations → ``None`` (not a phantom ``unknown`` tag)."""
    assert _pick_trigger_event((), Zone.PERIPATOS) is None


# ---------- §2 Per-kind happy paths -----------------------------------------


def test_zone_transition_winner_carries_to_zone_and_ref() -> None:
    """zone_transition wins; zone + ref_id come from ``to_zone``."""
    obs = ZoneTransitionEvent(
        agent_id="a_kant_001",
        tick=10,
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    tag = _pick_trigger_event((obs,), Zone.STUDY)
    assert tag is not None
    assert tag.kind == "zone_transition"
    assert tag.zone is Zone.PERIPATOS
    assert tag.ref_id == "peripatos"
    assert tag.secondary_kinds == []


def test_affordance_winner_picks_highest_salience() -> None:
    """affordance wins among multiple; highest salience determines ref_id."""
    low = AffordanceEvent(
        agent_id="a_kant_001",
        tick=10,
        prop_id="bench_01",
        prop_kind="seat",
        zone=Zone.PERIPATOS,
        distance=2.0,
        salience=0.3,
    )
    high = AffordanceEvent(
        agent_id="a_kant_001",
        tick=10,
        prop_id="bowl_01",
        prop_kind="vessel",
        zone=Zone.CHASHITSU,
        distance=1.0,
        salience=0.9,
    )
    tag = _pick_trigger_event((low, high), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "affordance"
    assert tag.zone is Zone.CHASHITSU
    assert tag.ref_id == "bowl_01"


def test_proximity_winner_uses_initiator_zone_and_enter_target() -> None:
    """proximity wins; zone = initiator (current_zone), ref_id = first 'enter'."""
    leave_first = ProximityEvent(
        agent_id="a_kant_001",
        tick=10,
        other_agent_id="a_nietzsche_001",
        distance_prev=1.5,
        distance_now=2.0,
        crossing="leave",
    )
    enter = ProximityEvent(
        agent_id="a_kant_001",
        tick=10,
        other_agent_id="a_rikyu_001",
        distance_prev=1.5,
        distance_now=0.8,
        crossing="enter",
    )
    tag = _pick_trigger_event((leave_first, enter), Zone.AGORA)
    assert tag is not None
    assert tag.kind == "proximity"
    assert tag.zone is Zone.AGORA
    assert tag.ref_id == "a_rikyu_001"


def test_biorhythm_winner_has_no_zone_or_ref() -> None:
    """biorhythm is non-spatial; zone + ref_id stay None."""
    obs = BiorhythmEvent(
        agent_id="a_kant_001",
        tick=10,
        signal="fatigue",
        level_prev=0.5,
        level_now=0.8,
        threshold_crossed="up",
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "biorhythm"
    assert tag.zone is None
    assert tag.ref_id is None


def test_erre_mode_shift_winner_has_no_zone_or_ref() -> None:
    """erre_mode_shift is non-spatial; zone + ref_id stay None."""
    obs = ERREModeShiftEvent(
        agent_id="a_kant_001",
        tick=10,
        previous=ERREModeName.PERIPATETIC,
        current=ERREModeName.SHU_KATA,
        reason="zone",
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "erre_mode_shift"
    assert tag.zone is None
    assert tag.ref_id is None


def test_temporal_winner_has_no_zone_or_ref() -> None:
    """temporal is non-spatial; zone + ref_id stay None."""
    obs = TemporalEvent(
        agent_id="a_kant_001",
        tick=10,
        period_prev=TimeOfDay.NIGHT,
        period_now=TimeOfDay.MORNING,
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "temporal"
    assert tag.zone is None
    assert tag.ref_id is None


def test_internal_winner_has_no_zone_or_ref() -> None:
    """internal is non-spatial; zone + ref_id stay None."""
    obs = InternalEvent(
        agent_id="a_kant_001",
        tick=10,
        content="reconsidering the route",
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "internal"
    assert tag.zone is None
    assert tag.ref_id is None


def test_speech_winner_has_no_zone_or_ref() -> None:
    """speech is non-spatial (the agent's own utterance); zone + ref_id stay None."""
    obs = SpeechEvent(
        agent_id="a_kant_001",
        tick=10,
        speaker_id="a_kant_001",
        utterance="duty before inclination",
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "speech"
    assert tag.zone is None


def test_perception_winner_has_no_zone_or_ref() -> None:
    """perception is non-spatial; zone + ref_id stay None."""
    obs = PerceptionEvent(
        agent_id="a_kant_001",
        tick=10,
        modality="sight",
        source_zone=Zone.PERIPATOS,
        content="dust motes drift in the morning light",
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "perception"
    assert tag.zone is None


# ---------- §3 Priority resolution -------------------------------------------


def test_zone_transition_outranks_affordance_when_both_fire() -> None:
    """zone_transition is the top priority among spatial kinds."""
    aff = AffordanceEvent(
        agent_id="a_kant_001",
        tick=10,
        prop_id="bowl_01",
        prop_kind="vessel",
        zone=Zone.CHASHITSU,
        distance=1.0,
        salience=0.9,
    )
    zt = ZoneTransitionEvent(
        agent_id="a_kant_001",
        tick=10,
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    tag = _pick_trigger_event((aff, zt), Zone.STUDY)
    assert tag is not None
    assert tag.kind == "zone_transition"
    assert "affordance" in tag.secondary_kinds


def test_affordance_outranks_proximity_when_both_fire() -> None:
    """affordance > proximity in the priority order."""
    prox = ProximityEvent(
        agent_id="a_kant_001",
        tick=10,
        other_agent_id="a_nietzsche_001",
        distance_prev=1.5,
        distance_now=0.8,
        crossing="enter",
    )
    aff = AffordanceEvent(
        agent_id="a_kant_001",
        tick=10,
        prop_id="bowl_01",
        prop_kind="vessel",
        zone=Zone.CHASHITSU,
        distance=1.0,
        salience=0.7,
    )
    tag = _pick_trigger_event((prox, aff), Zone.CHASHITSU)
    assert tag is not None
    assert tag.kind == "affordance"
    assert tag.secondary_kinds == ["proximity"]


def test_temporal_only_quiet_tick_still_fires_trigger() -> None:
    """A tick with only temporal still produces a tag (firing condition relaxed)."""
    obs = TemporalEvent(
        agent_id="a_kant_001",
        tick=10,
        period_prev=TimeOfDay.DUSK,
        period_now=TimeOfDay.NIGHT,
    )
    tag = _pick_trigger_event((obs,), Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "temporal"
    assert tag.secondary_kinds == []


# ---------- §4 secondary_kinds collection -----------------------------------


def test_secondary_kinds_lists_priority_order_excluding_winner() -> None:
    """Multiple losers surface in priority order, deduplicated."""
    obs_list = [
        InternalEvent(
            agent_id="a_kant_001",
            tick=10,
            content="consider the route",
        ),
        ProximityEvent(
            agent_id="a_kant_001",
            tick=10,
            other_agent_id="a_nietzsche_001",
            distance_prev=1.5,
            distance_now=0.8,
            crossing="enter",
        ),
        AffordanceEvent(
            agent_id="a_kant_001",
            tick=10,
            prop_id="bench_01",
            prop_kind="seat",
            zone=Zone.PERIPATOS,
            distance=1.5,
            salience=0.6,
        ),
        BiorhythmEvent(
            agent_id="a_kant_001",
            tick=10,
            signal="fatigue",
            level_prev=0.4,
            level_now=0.7,
            threshold_crossed="up",
        ),
    ]
    tag = _pick_trigger_event(obs_list, Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "affordance"
    # Priority order excluding winner: proximity > biorhythm > internal
    assert tag.secondary_kinds == ["proximity", "biorhythm", "internal"]


def test_secondary_kinds_capped_at_eight() -> None:
    """secondary_kinds never exceeds 8 even if every other kind fired."""
    # Construct 9 different-kind observations including the winner.
    obs_list = [
        ZoneTransitionEvent(
            agent_id="a",
            tick=1,
            from_zone=Zone.STUDY,
            to_zone=Zone.PERIPATOS,
        ),
        AffordanceEvent(
            agent_id="a",
            tick=1,
            prop_id="p",
            prop_kind="seat",
            zone=Zone.PERIPATOS,
            distance=1.0,
            salience=0.5,
        ),
        ProximityEvent(
            agent_id="a",
            tick=1,
            other_agent_id="b",
            distance_prev=1.5,
            distance_now=1.0,
            crossing="enter",
        ),
        BiorhythmEvent(
            agent_id="a",
            tick=1,
            signal="fatigue",
            level_prev=0.3,
            level_now=0.5,
            threshold_crossed="up",
        ),
        ERREModeShiftEvent(
            agent_id="a",
            tick=1,
            previous=ERREModeName.PERIPATETIC,
            current=ERREModeName.SHU_KATA,
            reason="zone",
        ),
        TemporalEvent(
            agent_id="a",
            tick=1,
            period_prev=TimeOfDay.NIGHT,
            period_now=TimeOfDay.MORNING,
        ),
        InternalEvent(agent_id="a", tick=1, content="x"),
        SpeechEvent(agent_id="a", tick=1, speaker_id="a", utterance="y"),
        PerceptionEvent(
            agent_id="a",
            tick=1,
            modality="sight",
            source_zone=Zone.PERIPATOS,
            content="z",
        ),
    ]
    tag = _pick_trigger_event(obs_list, Zone.PERIPATOS)
    assert tag is not None
    assert tag.kind == "zone_transition"
    # 8 losers should be present (cap at 8); the 9th is dropped.
    assert len(tag.secondary_kinds) == 8


# ---------- §5 Schema integration -------------------------------------------


def test_returned_tag_validates_against_schema() -> None:
    """The helper output is a valid :class:`TriggerEventTag` instance."""
    obs = ZoneTransitionEvent(
        agent_id="a_kant_001",
        tick=10,
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    tag = _pick_trigger_event((obs,), Zone.STUDY)
    assert isinstance(tag, TriggerEventTag)
    # Round-trip through Pydantic to confirm the shape is wire-valid.
    re_loaded = TriggerEventTag.model_validate_json(tag.model_dump_json())
    assert re_loaded == tag


# ---------- §6 Defensive / contract -----------------------------------------


@pytest.mark.parametrize("zone", list(Zone))
def test_proximity_uses_passed_current_zone_for_each_zone_value(zone: Zone) -> None:
    """current_zone is propagated as-is to ProximityEvent triggers."""
    obs = ProximityEvent(
        agent_id="a_kant_001",
        tick=10,
        other_agent_id="a_nietzsche_001",
        distance_prev=1.5,
        distance_now=0.5,
        crossing="enter",
    )
    tag = _pick_trigger_event((obs,), zone)
    assert tag is not None
    assert tag.zone is zone
