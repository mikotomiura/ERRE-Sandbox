"""Tests for the M7 B1 AffordanceEvent firing in :class:`WorldRuntime`.

The runtime caches the previous-tick XZ distance of every (agent, prop)
pair against :data:`ZONE_PROPS` and emits an
:class:`~erre_sandbox.schemas.AffordanceEvent` when the agent first crosses
:data:`_AFFORDANCE_RADIUS_M` (2 m). Only the entry edge fires; a stationary
agent inside the radius does not re-emit every tick, mirroring the
proximity event's edge-only contract.

These tests poke :meth:`WorldRuntime._fire_affordance_events` directly
(rather than advancing the 30 Hz heap) because the firing logic is
independent of the scheduler — everything interesting is expressible via
agent positions mutated between calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from erre_sandbox.schemas import AffordanceEvent, Zone
from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world.tick import _AFFORDANCE_RADIUS_M
from erre_sandbox.world.zones import ZONE_PROPS

if TYPE_CHECKING:
    from collections.abc import Callable


# chashitsu tea bowl ground-truth pulled from ``world/zones.py`` — since
# Slice β derives prop coordinates from :data:`WORLD_SIZE_M`, pegging the
# literals would force a parallel edit every time the world rescales. We
# still assert the agent-prop geometry (distance deltas) loudly; only the
# absolute XZ origin tracks the source table.
_CHAWAN_01 = ZONE_PROPS[Zone.CHASHITSU][0]
_CHAWAN_01_X = _CHAWAN_01.x
_CHAWAN_01_Z = _CHAWAN_01.z


def _move(runtime: WorldRuntime, agent_id: str, *, x: float, z: float) -> None:
    """Teleport an agent's runtime position for an affordance-only test."""
    rt = runtime._agents[agent_id]
    new_pos = rt.state.position.model_copy(update={"x": x, "z": z})
    rt.state = rt.state.model_copy(update={"position": new_pos})
    rt.kinematics.position = new_pos


async def test_first_observation_primes_cache_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """An agent spawned inside a prop's radius must NOT fire on tick 0.

    Without this guard, every agent that starts life in chashitsu (a common
    fixture) would immediately emit a spurious entry even when the agent
    has not moved. The prime-then-compare pattern keeps the event tied to
    *motion across the edge*, not *presence inside the zone*.
    """
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # Position the agent 1 m from chawan_01 — inside the 2 m radius from
    # frame zero, which is the hostile case for the prime guard.
    runtime.register_agent(
        make_agent_state(
            agent_id="a_rikyu_001",
            persona_id="rikyu",
            position={"x": _CHAWAN_01_X + 1.0, "z": _CHAWAN_01_Z},
        ),
        make_persona_spec(persona_id="rikyu"),
    )

    runtime._fire_affordance_events()

    assert runtime._agents["a_rikyu_001"].pending == []
    # Cache IS primed so the next call can detect a re-entry.
    assert ("a_rikyu_001", "chawan_01") in runtime._agent_prop_distances


async def test_crossing_into_radius_emits_affordance(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """Walking from > 2 m to < 2 m emits a single AffordanceEvent."""
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # Start 5 m east of chawan_01 — well outside the 2 m radius.
    runtime.register_agent(
        make_agent_state(
            agent_id="a_rikyu_001",
            persona_id="rikyu",
            position={"x": _CHAWAN_01_X + 5.0, "z": _CHAWAN_01_Z},
        ),
        make_persona_spec(persona_id="rikyu"),
    )
    runtime._fire_affordance_events()  # prime

    # Step into 1 m from chawan_01 — inside the 2 m radius.
    _move(runtime, "a_rikyu_001", x=_CHAWAN_01_X + 1.0, z=_CHAWAN_01_Z)
    runtime._fire_affordance_events()

    pending = runtime._agents["a_rikyu_001"].pending
    # The second tea bowl (chawan_02) also sits nearby; we only assert on the
    # chawan_01 entry here. The table-scan order is ZONE_PROPS declaration
    # order so chawan_01 appears first if both fire simultaneously.
    affordances = [e for e in pending if isinstance(e, AffordanceEvent)]
    assert affordances, "expected at least one AffordanceEvent on entry"
    event = next(e for e in affordances if e.prop_id == "chawan_01")
    assert event.prop_kind == "tea_bowl"
    assert event.zone == Zone.CHASHITSU
    assert event.distance < _AFFORDANCE_RADIUS_M


async def test_staying_inside_radius_does_not_re_emit(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """A stationary agent inside the radius must not re-emit every tick.

    Guards against the chashitsu visitor spamming the observation stream
    while sitting next to a tea bowl — which is the common case for Rikyu.
    """
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(
            agent_id="a_rikyu_001",
            persona_id="rikyu",
            position={"x": _CHAWAN_01_X + 5.0, "z": _CHAWAN_01_Z},
        ),
        make_persona_spec(persona_id="rikyu"),
    )
    runtime._fire_affordance_events()  # prime outside

    _move(runtime, "a_rikyu_001", x=_CHAWAN_01_X + 1.0, z=_CHAWAN_01_Z)
    runtime._fire_affordance_events()  # entry: emits
    # Drop what was just emitted so the stay-still delta is observable.
    runtime._agents["a_rikyu_001"].pending.clear()

    # Two more ticks of staying still — no motion, no new edge.
    runtime._fire_affordance_events()
    runtime._fire_affordance_events()

    pending = runtime._agents["a_rikyu_001"].pending
    affordances = [e for e in pending if isinstance(e, AffordanceEvent)]
    assert affordances == [], (
        f"stationary agent re-emitted {len(affordances)} affordance(s)"
    )


async def test_leaving_and_re_entering_emits_again(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """After leaving the radius, a second entry re-fires."""
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(
            agent_id="a_rikyu_001",
            persona_id="rikyu",
            position={"x": _CHAWAN_01_X + 5.0, "z": _CHAWAN_01_Z},
        ),
        make_persona_spec(persona_id="rikyu"),
    )
    runtime._fire_affordance_events()  # prime outside
    _move(runtime, "a_rikyu_001", x=_CHAWAN_01_X + 1.0, z=_CHAWAN_01_Z)
    runtime._fire_affordance_events()  # entry 1
    runtime._agents["a_rikyu_001"].pending.clear()

    # Walk back out (> 2 m).
    _move(runtime, "a_rikyu_001", x=_CHAWAN_01_X + 5.0, z=_CHAWAN_01_Z)
    runtime._fire_affordance_events()
    # Walk back in.
    _move(runtime, "a_rikyu_001", x=_CHAWAN_01_X + 1.0, z=_CHAWAN_01_Z)
    runtime._fire_affordance_events()

    pending = runtime._agents["a_rikyu_001"].pending
    affordances = [
        e
        for e in pending
        if isinstance(e, AffordanceEvent) and e.prop_id == "chawan_01"
    ]
    assert len(affordances) == 1, (
        "second entry after leaving must fire exactly once for chawan_01"
    )


async def test_agent_in_empty_zone_fires_nothing(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """Zones with no props in ZONE_PROPS produce zero affordance events."""
    # Sanity check: the MVP fixture only populates chashitsu.
    assert ZONE_PROPS[Zone.STUDY] == ()
    assert ZONE_PROPS[Zone.PERIPATOS] == ()

    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(
            agent_id="a_kant_001",
            position={"x": -20.0, "z": -20.0},  # study centroid
        ),
        make_persona_spec(),
    )

    runtime._fire_affordance_events()  # prime
    _move(runtime, "a_kant_001", x=-18.0, z=-20.0)  # move inside study
    runtime._fire_affordance_events()

    # No prop in STUDY → agent observed nothing. The chashitsu props are
    # far away in world space (20 m+) so their radius never triggers here.
    pending = runtime._agents["a_kant_001"].pending
    affordances = [e for e in pending if isinstance(e, AffordanceEvent)]
    assert affordances == []
