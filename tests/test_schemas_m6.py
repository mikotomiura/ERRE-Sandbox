"""Contract tests for M6 additive schema (0.4.0-m6).

Each ``test_*`` documents one concrete clause of the M6 wire contract
addition, mirroring the convention established by
``tests/test_schemas_m5.py``:

* ``SCHEMA_VERSION == "0.4.0-m6"``
* :class:`TimeOfDay` enum values (six periods)
* :class:`AffordanceEvent` / :class:`ProximityEvent` /
  :class:`TemporalEvent` / :class:`BiorhythmEvent` round-trip through the
  :class:`Observation` discriminated union
* :class:`BiorhythmEvent.signal` and ``threshold_crossed`` literal
  vocabularies

All four new variants are additive to the M5 ``Observation`` union —
producers that only emit the original five variants stay wire-compatible.
Firing logic (``world/tick.py`` for Affordance / Proximity / Temporal and
``cognition/cycle.py`` for Biorhythm) is tested in M6-A-2b alongside the
producer implementations; this file covers only the frozen wire contract.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AffordanceEvent,
    BiorhythmEvent,
    Observation,
    ProximityEvent,
    TemporalEvent,
    TimeOfDay,
    Zone,
)

# ---------- §1 SCHEMA_VERSION ------------------------------------------------


def test_schema_version_is_m6() -> None:
    # M6 introduced AffordanceEvent / ProximityEvent / TemporalEvent /
    # BiorhythmEvent + the TimeOfDay enum. Subsequent milestones (M8+) stay
    # compatible with those additions — this file exercises the M6 surface
    # against whatever the current SCHEMA_VERSION happens to be, so we track
    # the active milestone pin here too.
    assert SCHEMA_VERSION == "0.5.0-m8"


# ---------- §2 TimeOfDay enum ------------------------------------------------


def test_time_of_day_has_six_periods() -> None:
    values = {member.value for member in TimeOfDay}
    assert values == {"dawn", "morning", "noon", "afternoon", "dusk", "night"}


# ---------- §5 Observation additions ----------------------------------------


def test_affordance_event_round_trips() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    obs = adapter.validate_python(
        {
            "event_type": "affordance",
            "tick": 7,
            "agent_id": "a_rikyu_001",
            "prop_id": "tea_bowl_01",
            "prop_kind": "tea_bowl",
            "zone": "chashitsu",
            "distance": 1.4,
            "salience": 0.8,
        },
    )
    assert isinstance(obs, AffordanceEvent)
    assert obs.zone is Zone.CHASHITSU
    assert obs.distance == pytest.approx(1.4)


def test_affordance_event_rejects_negative_distance() -> None:
    with pytest.raises(ValidationError):
        AffordanceEvent(
            tick=1,
            agent_id="a",
            prop_id="p",
            prop_kind="k",
            zone=Zone.STUDY,
            distance=-0.1,
        )


def test_proximity_event_round_trips() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    obs = adapter.validate_python(
        {
            "event_type": "proximity",
            "tick": 11,
            "agent_id": "a_kant_001",
            "other_agent_id": "a_nietzsche_001",
            "distance_prev": 6.2,
            "distance_now": 3.8,
            "crossing": "enter",
        },
    )
    assert isinstance(obs, ProximityEvent)
    assert obs.crossing == "enter"


def test_proximity_event_rejects_bad_crossing() -> None:
    with pytest.raises(ValidationError):
        ProximityEvent(
            tick=1,
            agent_id="a",
            other_agent_id="b",
            distance_prev=1.0,
            distance_now=2.0,
            crossing="approach",  # type: ignore[arg-type]
        )


def test_temporal_event_round_trips() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    obs = adapter.validate_python(
        {
            "event_type": "temporal",
            "tick": 360,
            "agent_id": "a_kant_001",
            "period_prev": "morning",
            "period_now": "noon",
        },
    )
    assert isinstance(obs, TemporalEvent)
    assert obs.period_prev is TimeOfDay.MORNING
    assert obs.period_now is TimeOfDay.NOON


def test_biorhythm_event_round_trips() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    obs = adapter.validate_python(
        {
            "event_type": "biorhythm",
            "tick": 42,
            "agent_id": "a_kant_001",
            "signal": "fatigue",
            "level_prev": 0.45,
            "level_now": 0.65,
            "threshold_crossed": "up",
        },
    )
    assert isinstance(obs, BiorhythmEvent)
    assert obs.signal == "fatigue"
    assert obs.threshold_crossed == "up"


@pytest.mark.parametrize("signal", ["fatigue", "hunger", "stress"])
def test_biorhythm_event_accepts_all_signals(signal: str) -> None:
    BiorhythmEvent(
        tick=1,
        agent_id="a",
        signal=signal,  # type: ignore[arg-type]
        level_prev=0.5,
        level_now=0.5,
        threshold_crossed="up",
    )


def test_biorhythm_event_rejects_bad_signal() -> None:
    with pytest.raises(ValidationError):
        BiorhythmEvent(
            tick=1,
            agent_id="a",
            signal="morale",  # type: ignore[arg-type]
            level_prev=0.5,
            level_now=0.5,
            threshold_crossed="up",
        )


def test_biorhythm_event_unit_bounds_on_level() -> None:
    with pytest.raises(ValidationError):
        BiorhythmEvent(
            tick=1,
            agent_id="a",
            signal="fatigue",
            level_prev=1.5,  # out of [0, 1]
            level_now=0.5,
            threshold_crossed="down",
        )


# ---------- §5 Observation union still rejects unknown variants --------------


def test_observation_union_rejects_unknown_event_type_after_m6() -> None:
    adapter: TypeAdapter[Observation] = TypeAdapter(Observation)
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"event_type": "telepathy", "tick": 0, "agent_id": "a"},
        )
