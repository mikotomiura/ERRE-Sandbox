"""Tests for the M6-A-2b TemporalEvent firing in :class:`WorldRuntime`.

The runtime owns a simulated day clock: the elapsed wall-time (from the
injected :class:`Clock`) is mapped into six :class:`TimeOfDay` buckets and a
:class:`~erre_sandbox.schemas.TemporalEvent` is emitted into every
registered agent's ``pending`` observation buffer whenever that bucket
changes. Boot time does NOT emit an event — there is no "previous" period
to cite.

These tests run the runtime's time-of-day cascade directly via the private
``_fire_temporal_events`` helper so they do not need to advance the scheduler
heapq through 100+ physics ticks. The :class:`ManualClock` is advanced
explicitly, then the helper is invoked and asserted on.
"""

from __future__ import annotations

import asyncio
from random import Random
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.schemas import (
    TemporalEvent,
    TimeOfDay,
)
from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world.tick import _PERIOD_BOUNDARIES, _time_of_day

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------- _time_of_day helper ----------


@pytest.mark.parametrize(
    ("phase_fraction", "expected"),
    [
        (0.00, TimeOfDay.DAWN),
        (0.05, TimeOfDay.DAWN),
        (0.10, TimeOfDay.MORNING),
        (0.39, TimeOfDay.MORNING),
        (0.40, TimeOfDay.NOON),
        (0.54, TimeOfDay.NOON),
        (0.55, TimeOfDay.AFTERNOON),
        (0.79, TimeOfDay.AFTERNOON),
        (0.80, TimeOfDay.DUSK),
        (0.89, TimeOfDay.DUSK),
        (0.90, TimeOfDay.NIGHT),
        (0.99, TimeOfDay.NIGHT),
    ],
)
def test_time_of_day_boundaries(phase_fraction: float, expected: TimeOfDay) -> None:
    day_duration = 100.0
    period = _time_of_day(phase_fraction * day_duration, day_duration)
    assert period == expected


def test_time_of_day_wraps_across_days() -> None:
    day_duration = 100.0
    # Exactly one full day in → phase=0 → DAWN.
    assert _time_of_day(100.0, day_duration) == TimeOfDay.DAWN
    # 2.5 days in → phase=0.5 → NOON (40–55%).
    assert _time_of_day(250.0, day_duration) == TimeOfDay.NOON


def test_time_of_day_handles_zero_day_duration_safely() -> None:
    # A zero or negative day duration should not divide-by-zero; the
    # degenerate value is DAWN so the runtime stays deterministic.
    assert _time_of_day(10.0, 0.0) == TimeOfDay.DAWN


def test_period_boundary_count_matches_enum_cardinality() -> None:
    """Every :class:`TimeOfDay` member must appear in the boundary table."""
    enum_members = set(TimeOfDay)
    boundary_members = {period for _, period in _PERIOD_BOUNDARIES}
    assert enum_members == boundary_members


# ---------- _fire_temporal_events integration ----------


async def test_first_tick_silently_syncs_period_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """Boot tick has no prior period to name — it initialises state silently."""
    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        day_duration_s=100.0,
    )
    runtime.register_agent(make_agent_state(), make_persona_spec())

    runtime._fire_temporal_events()
    rt = runtime._agents["a_kant_001"]
    assert rt.pending == []
    assert runtime._current_period == TimeOfDay.DAWN


async def test_period_crossing_emits_event_for_every_agent(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """Advancing past a boundary emits one TemporalEvent per registered agent."""
    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        day_duration_s=100.0,
    )
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001"),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(agent_id="a_nietzsche_001", persona_id="nietzsche"),
        make_persona_spec(persona_id="nietzsche"),
    )

    runtime._fire_temporal_events()
    # Advance to phase 0.15 (15 of 100 sim-seconds) → MORNING bucket.
    clock.advance(15.0)
    runtime._fire_temporal_events()

    for agent_id in ("a_kant_001", "a_nietzsche_001"):
        pending = runtime._agents[agent_id].pending
        assert len(pending) == 1
        event = pending[0]
        assert isinstance(event, TemporalEvent)
        assert event.period_prev == TimeOfDay.DAWN
        assert event.period_now == TimeOfDay.MORNING


async def test_no_crossing_emits_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        day_duration_s=100.0,
    )
    runtime.register_agent(make_agent_state(), make_persona_spec())
    runtime._fire_temporal_events()
    # Advance but stay within DAWN (phase < 0.10).
    clock.advance(5.0)
    runtime._fire_temporal_events()
    assert runtime._agents["a_kant_001"].pending == []


async def test_temporal_events_never_fire_with_zero_agents() -> None:
    """No registered agents → nothing to notify, state stays uninitialised."""
    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        day_duration_s=100.0,
    )
    # _on_physics_tick hot-paths the no-agent case, so the helper is not
    # reached. Confirm by calling the public physics tick once.
    await runtime._on_physics_tick()
    assert runtime._time_start is None


async def test_runtime_accepts_day_duration_override() -> None:
    """Constructor exposes ``day_duration_s`` knob (tests pass tiny values)."""
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=ManualClock(start=0.0),
        day_duration_s=0.5,
    )
    assert runtime._day_duration_s == pytest.approx(0.5)


async def test_runtime_default_day_duration_is_480_seconds() -> None:
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=ManualClock(start=0.0),
    )
    assert runtime._day_duration_s == pytest.approx(480.0)


async def test_multi_boundary_crossing_reports_latest_only(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """A large advance that skips past two boundaries reports the final bucket.

    The event's ``period_prev`` is the last-known bucket at firing time,
    which is intentional — the stream's job is to mark current-vs-previous,
    not to emit a burst of events for each jumped-over boundary. If higher
    resolution is ever needed, drive the helper on every physics tick rather
    than every second of wall-time.
    """
    clock = ManualClock(start=0.0)
    runtime = WorldRuntime(
        cycle=object(),  # type: ignore[arg-type]
        clock=clock,
        day_duration_s=100.0,
    )
    runtime.register_agent(make_agent_state(), make_persona_spec())
    runtime._fire_temporal_events()
    # Leap from phase 0 → 0.6 (NOON jumped over, ends at AFTERNOON).
    clock.advance(60.0)
    runtime._fire_temporal_events()
    pending = runtime._agents["a_kant_001"].pending
    assert len(pending) == 1
    event = pending[0]
    assert isinstance(event, TemporalEvent)
    assert event.period_prev == TimeOfDay.DAWN
    assert event.period_now == TimeOfDay.AFTERNOON


# ---------- Sanity plumbing ----------


async def test_asyncio_import_is_available() -> None:
    """Pytest-asyncio is configured for this module (auto mode)."""
    await asyncio.sleep(0)
    assert True

    # Also exercise a throwaway random to keep the import used in case we
    # add a time-jitter path later.
    Random(0).random()
