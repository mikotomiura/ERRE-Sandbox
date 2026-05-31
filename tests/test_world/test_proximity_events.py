"""Tests for the M6-A-2b ProximityEvent firing in :class:`WorldRuntime`.

The runtime caches the previous-tick XZ distance of every unordered agent
pair and emits a :class:`~erre_sandbox.schemas.ProximityEvent` when the
distance crosses :data:`_PROXIMITY_THRESHOLD_M` (5 m). Both agents on the
crossing edge receive the event into their ``pending`` buffer so the next
cognition tick's prompt surfaces "someone just walked up" / "they just
left" from each agent's own perspective.

These tests poke :meth:`WorldRuntime._fire_proximity_events` directly
(rather than advancing the 30 Hz heap) because the firing logic is
independent of the scheduler — everything interesting is expressible via
agent positions mutated between calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CycleResult
from erre_sandbox.schemas import AgentUpdateMsg, BiorhythmEvent, ProximityEvent
from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world.tick import _PROXIMITY_THRESHOLD_M

if TYPE_CHECKING:
    from collections.abc import Callable


def _move(runtime: WorldRuntime, agent_id: str, *, x: float, z: float) -> None:
    """Teleport an agent's runtime position for a proximity-only test.

    Writes directly into :class:`AgentRuntime` rather than round-tripping
    through :class:`MoveMsg` because the test only cares about the post-move
    snapshot the proximity helper sees.
    """
    rt = runtime._agents[agent_id]
    new_pos = rt.state.position.model_copy(update={"x": x, "z": z})
    rt.state = rt.state.model_copy(update={"position": new_pos})
    rt.kinematics.position = new_pos


async def test_first_observation_primes_cache_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 2.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )

    runtime._fire_proximity_events()

    # No event on the first sighting — there is no prior distance to compare.
    assert runtime._agents["a_kant_001"].pending == []
    assert runtime._agents["a_nietzsche_001"].pending == []
    # The pair distance IS cached so the next call can detect crossings.
    assert len(runtime._pair_distances) == 1


async def test_crossing_below_threshold_emits_enter_to_both_agents(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # Start far apart (> threshold), then walk into each other.
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 10.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    runtime._fire_proximity_events()  # prime

    _move(runtime, "a_nietzsche_001", x=2.0, z=0.0)
    runtime._fire_proximity_events()

    for agent_id, other_id in (
        ("a_kant_001", "a_nietzsche_001"),
        ("a_nietzsche_001", "a_kant_001"),
    ):
        pending = runtime._agents[agent_id].pending
        assert len(pending) == 1
        event = pending[0]
        assert isinstance(event, ProximityEvent)
        assert event.crossing == "enter"
        assert event.other_agent_id == other_id
        assert event.distance_prev > _PROXIMITY_THRESHOLD_M
        assert event.distance_now < _PROXIMITY_THRESHOLD_M


async def test_crossing_above_threshold_emits_leave(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 2.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    runtime._fire_proximity_events()  # prime at distance 2 (< threshold)

    _move(runtime, "a_nietzsche_001", x=10.0, z=0.0)
    runtime._fire_proximity_events()

    for agent_id in ("a_kant_001", "a_nietzsche_001"):
        pending = runtime._agents[agent_id].pending
        assert len(pending) == 1
        event = pending[0]
        assert isinstance(event, ProximityEvent)
        assert event.crossing == "leave"


async def test_stable_above_threshold_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 10.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    runtime._fire_proximity_events()  # prime

    _move(runtime, "a_nietzsche_001", x=12.0, z=0.0)
    runtime._fire_proximity_events()

    assert runtime._agents["a_kant_001"].pending == []
    assert runtime._agents["a_nietzsche_001"].pending == []


async def test_stable_below_threshold_no_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 2.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    runtime._fire_proximity_events()  # prime inside radius

    _move(runtime, "a_nietzsche_001", x=3.0, z=0.0)
    runtime._fire_proximity_events()

    assert runtime._agents["a_kant_001"].pending == []
    assert runtime._agents["a_nietzsche_001"].pending == []


async def test_multiple_pairs_independent(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """Three agents → one pair crosses, another stays stable."""
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a_kant_001", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_nietzsche_001",
            persona_id="nietzsche",
            position={"x": 10.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="a_rikyu_001",
            persona_id="rikyu",
            position={"x": 20.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="rikyu"),
    )
    runtime._fire_proximity_events()  # prime

    # Kant walks close to Nietzsche; Rikyu holds position.
    _move(runtime, "a_kant_001", x=9.0, z=0.0)
    runtime._fire_proximity_events()

    kant_events = runtime._agents["a_kant_001"].pending
    # Kant sees exactly one event (Nietzsche). The Kant-Rikyu pair stayed
    # above threshold (distance went from 20 to 11 m — still > 5 m).
    assert len(kant_events) == 1
    assert isinstance(kant_events[0], ProximityEvent)
    assert kant_events[0].other_agent_id == "a_nietzsche_001"
    assert kant_events[0].crossing == "enter"
    # Rikyu sees nothing because neither of his pairs crossed.
    assert runtime._agents["a_rikyu_001"].pending == []


async def test_single_agent_world_is_noop(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """`_fire_proximity_events` is skipped by ``_on_physics_tick`` for <2 agents."""
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(),
        make_persona_spec(),
    )
    # Even a direct call must not crash with a single agent — itertools.combinations
    # returns an empty iterator for N=1, so no pair is touched.
    runtime._fire_proximity_events()
    assert runtime._pair_distances == {}


async def test_consume_result_drains_follow_up_observations(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    """CycleResult.follow_up_observations must land in rt.pending.

    Covered here (rather than in test_cognition) because the runtime's
    ``_consume_result`` is the load-bearing hand-off between the cycle's
    deferred-event carrier and the next tick's observation window.
    """
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    state = make_agent_state()
    runtime.register_agent(state, make_persona_spec())
    rt = runtime._agents[state.agent_id]

    stress = BiorhythmEvent(
        tick=state.tick + 1,
        agent_id=state.agent_id,
        signal="stress",
        level_prev=0.30,
        level_now=0.70,
        threshold_crossed="up",
    )
    result = CycleResult(
        agent_state=state,
        envelopes=[AgentUpdateMsg(tick=state.tick, agent_state=state)],
        follow_up_observations=[stress],
    )

    runtime._consume_result(rt, result)
    assert rt.pending == [stress]
