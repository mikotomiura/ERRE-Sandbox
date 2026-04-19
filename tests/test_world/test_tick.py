"""Tests for ``erre_sandbox.world.tick`` (T13).

Because the runtime is asyncio-native the tests advance
:class:`ManualClock` in small increments and yield control with
``asyncio.sleep(0)`` to let the scheduler coroutine consume each woken
waiter. The pattern is:

1. Start the runtime as a background task.
2. Advance the clock by the target duration.
3. ``await asyncio.sleep(0)`` enough times for all scheduled handlers to
   run (one yield per scheduler iteration).
4. Assert on ``cycle.calls`` and ``runtime.drain_envelopes()``.
5. Call ``runtime.stop()`` and let the run task finish.
"""

from __future__ import annotations

import asyncio
import heapq
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition import CycleResult
from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    MoveMsg,
    PersonaSpec,
    Position,
    WorldTickMsg,
    Zone,
    ZoneTransitionEvent,
)
from erre_sandbox.world import ManualClock
from erre_sandbox.world.tick import ScheduledEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from .conftest import MockCycleCall, RuntimeHarness


async def _pump(times: int = 10) -> None:
    """Yield to the event loop ``times`` times so scheduled waiters can run."""
    for _ in range(times):
        await asyncio.sleep(0)


async def _pump_until_stable(
    probe: Callable[[], int],
    *,
    max_iter: int = 2000,
    settle: int = 5,
) -> int:
    """Yield until ``probe()`` stops growing for ``settle`` consecutive yields.

    Used in tests that advance the clock by multi-second intervals where
    N = physics_hz * dt handlers need to fire and each handler needs one or
    two event-loop yields to propagate. Returns the final probe value so the
    caller can assert on it directly.
    """
    last = probe()
    stable = 0
    for _ in range(max_iter):
        await asyncio.sleep(0)
        now_value = probe()
        if now_value == last:
            stable += 1
            if stable >= settle:
                return now_value
        else:
            stable = 0
            last = now_value
    return last


# =============================================================================
# ManualClock
# =============================================================================


class TestManualClock:
    async def test_advance_releases_due_waiters(self) -> None:
        clock = ManualClock()
        completed: list[int] = []

        async def waiter(due: float, tag: int) -> None:
            await clock.sleep_until(due)
            completed.append(tag)

        t1 = asyncio.create_task(waiter(1.0, 1))
        t2 = asyncio.create_task(waiter(2.0, 2))
        await _pump()
        assert completed == []

        clock.advance(1.0)
        await _pump()
        assert completed == [1]

        clock.advance(1.0)
        await _pump()
        assert completed == [1, 2]
        await asyncio.gather(t1, t2)

    async def test_same_due_at_resolves_in_insertion_order(self) -> None:
        clock = ManualClock()
        order: list[int] = []

        async def waiter(tag: int) -> None:
            await clock.sleep_until(1.0)
            order.append(tag)

        tasks = [asyncio.create_task(waiter(i)) for i in range(3)]
        await _pump()
        clock.advance(1.0)
        await _pump()
        await asyncio.gather(*tasks)
        assert order == [0, 1, 2]

    async def test_immediate_due_at_returns_without_waiting(self) -> None:
        clock = ManualClock(start=5.0)
        await clock.sleep_until(3.0)  # already past — must not block

    def test_advance_rejects_negative_dt(self) -> None:
        clock = ManualClock()
        with pytest.raises(ValueError, match="backward"):
            clock.advance(-1.0)


# =============================================================================
# ScheduledEvent ordering
# =============================================================================


class TestScheduledEvent:
    def test_heapq_orders_by_due_at_then_seq(self) -> None:
        async def noop() -> None: ...

        events = [
            ScheduledEvent(due_at=2.0, seq=1, period=1.0, handler=noop, name="a"),
            ScheduledEvent(due_at=1.0, seq=2, period=1.0, handler=noop, name="b"),
            ScheduledEvent(due_at=1.0, seq=1, period=1.0, handler=noop, name="c"),
        ]
        heap: list[ScheduledEvent] = []
        for ev in events:
            heapq.heappush(heap, ev)
        popped = [heapq.heappop(heap).name for _ in range(3)]
        assert popped == ["c", "b", "a"]  # (1.0,1), (1.0,2), (2.0,1)


# =============================================================================
# WorldRuntime — basic scheduler behaviour
# =============================================================================


def _make_agent(
    make_agent_state: Any,
    zone: Zone = Zone.PERIPATOS,
) -> AgentState:
    return make_agent_state(
        position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": zone.value},
    )


def _make_persona(make_persona_spec: Any) -> PersonaSpec:
    return make_persona_spec()


class TestWorldRuntimeLifecycle:
    async def test_stop_returns_from_run(
        self,
        world_harness: RuntimeHarness,
    ) -> None:
        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await asyncio.wait_for(task, timeout=1.0)

    async def test_no_agents_means_cognition_and_physics_are_noops(
        self,
        world_harness: RuntimeHarness,
    ) -> None:
        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)
        await _pump(400)
        assert len(world_harness.cycle.calls) == 0
        # Heartbeat still fires even with zero agents.
        envs = world_harness.runtime.drain_envelopes()
        assert len(envs) >= 1
        assert all(isinstance(e, WorldTickMsg) for e in envs)
        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task


class TestWorldRuntimeCognition:
    async def test_cognition_tick_calls_step_for_each_agent(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        for i in range(3):
            world_harness.runtime.register_agent(
                make_agent_state(agent_id=f"a_{i}"),
                make_persona_spec(),
            )

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)
        await _pump(800)
        assert len(world_harness.cycle.calls) == 3
        called_ids = {c.agent_state.agent_id for c in world_harness.cycle.calls}
        assert called_ids == {"a_0", "a_1", "a_2"}

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task

    async def test_cognition_tick_swaps_pending_observations(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        state = make_agent_state(agent_id="a_kant_001")
        world_harness.runtime.register_agent(state, make_persona_spec())
        obs = ZoneTransitionEvent(
            tick=0,
            agent_id="a_kant_001",
            from_zone=Zone.STUDY,
            to_zone=Zone.PERIPATOS,
        )
        world_harness.runtime.inject_observation("a_kant_001", obs)

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)
        await _pump(400)
        assert world_harness.cycle.calls[0].observations == [obs]

        # pending must have been swapped — second cognition tick sees nothing.
        world_harness.clock.advance(10.0)
        await _pump(400)
        assert world_harness.cycle.calls[1].observations == []

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task

    async def test_exception_in_one_agent_does_not_cancel_others(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        async def responder(call: MockCycleCall) -> object:
            if call.agent_state.agent_id == "a_bad":
                msg = "synthetic cognition failure"
                raise RuntimeError(msg)
            return CycleResult(
                agent_state=call.agent_state,
                envelopes=[
                    AgentUpdateMsg(
                        tick=call.agent_state.tick,
                        agent_state=call.agent_state,
                    ),
                ],
            )

        world_harness.cycle.set_responder(responder)
        world_harness.runtime.register_agent(
            make_agent_state(agent_id="a_ok"),
            make_persona_spec(),
        )
        world_harness.runtime.register_agent(
            make_agent_state(agent_id="a_bad"),
            make_persona_spec(),
        )

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)
        await _pump(800)

        envs = world_harness.runtime.drain_envelopes()
        agent_updates = [e for e in envs if isinstance(e, AgentUpdateMsg)]
        assert any(e.agent_state.agent_id == "a_ok" for e in agent_updates)
        assert not any(e.agent_state.agent_id == "a_bad" for e in agent_updates)

        # Loop must continue to next cognition tick.
        world_harness.clock.advance(10.0)
        await _pump(800)
        assert len(world_harness.cycle.calls) == 4  # 2 agents × 2 ticks

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task

    async def test_llm_fell_back_result_does_not_stop_loop(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        async def responder(call: MockCycleCall) -> object:
            return CycleResult(
                agent_state=call.agent_state,
                envelopes=[],
                llm_fell_back=True,
            )

        world_harness.cycle.set_responder(responder)
        world_harness.runtime.register_agent(
            make_agent_state(),
            make_persona_spec(),
        )

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(30.0)
        await _pump(1500)
        assert len(world_harness.cycle.calls) == 3
        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task


class TestWorldRuntimePhysics:
    async def test_move_msg_drives_next_physics_tick(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        state = make_agent_state(
            agent_id="a_kant_001",
            position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        )
        world_harness.runtime.register_agent(state, make_persona_spec())

        target = Position(x=20.0, y=0.0, z=0.0, zone=Zone.PERIPATOS)

        async def responder(call: MockCycleCall) -> object:
            # First call returns a MoveMsg; subsequent calls do nothing.
            envelopes: list[Any]
            if len(world_harness.cycle.calls) == 1:
                envelopes = [
                    MoveMsg(
                        tick=call.agent_state.tick,
                        agent_id=call.agent_state.agent_id,
                        target=target,
                        speed=10.0,
                    ),
                ]
            else:
                envelopes = []
            return CycleResult(
                agent_state=call.agent_state,
                envelopes=envelopes,
            )

        world_harness.cycle.set_responder(responder)

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)  # first cognition tick → MoveMsg
        await _pump(800)

        # Advance enough physics ticks for the agent to reach the target.
        world_harness.clock.advance(3.0)  # 3 s × 30 Hz = 90 ticks
        await _pump(1500)

        rt = world_harness.runtime._agents["a_kant_001"]
        assert rt.kinematics.position.x == pytest.approx(20.0, abs=1e-6)
        assert rt.kinematics.destination is None

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task

    async def test_zone_crossing_enqueues_zone_transition_observation(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        state = make_agent_state(
            agent_id="a_kant_001",
            position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        )
        world_harness.runtime.register_agent(state, make_persona_spec())

        async def responder(call: MockCycleCall) -> object:
            if len(world_harness.cycle.calls) == 1:
                envelopes: list[Any] = [
                    MoveMsg(
                        tick=call.agent_state.tick,
                        agent_id=call.agent_state.agent_id,
                        target=Position(
                            x=20.0,
                            y=0.0,
                            z=20.0,
                            zone=Zone.GARDEN,
                        ),
                        speed=100.0,
                    ),
                ]
            else:
                envelopes = []
            return CycleResult(
                agent_state=call.agent_state,
                envelopes=envelopes,
            )

        world_harness.cycle.set_responder(responder)

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(10.0)  # first cognition → MoveMsg
        await _pump(800)
        # Let physics snap the agent to the destination.
        world_harness.clock.advance(1.0)
        await _pump(800)
        # Next cognition tick should see the ZoneTransitionEvent.
        world_harness.clock.advance(10.0)
        await _pump(800)

        second_call = world_harness.cycle.calls[1]
        transitions = [
            o for o in second_call.observations if isinstance(o, ZoneTransitionEvent)
        ]
        assert len(transitions) >= 1
        # HIGH regression: from_zone must be the previous (peripatos), not the
        # new one. A bug found in code review had both fields equal to GARDEN.
        assert transitions[0].from_zone is Zone.PERIPATOS
        assert transitions[0].to_zone is Zone.GARDEN

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task


class TestWorldRuntimeHeartbeat:
    async def test_heartbeat_emits_world_tick_msgs_periodically(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        world_harness.runtime.register_agent(
            make_agent_state(),
            make_persona_spec(),
        )

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        world_harness.clock.advance(5.0)
        await _pump(1500)

        envs = world_harness.runtime.drain_envelopes()
        heartbeats = [e for e in envs if isinstance(e, WorldTickMsg)]
        assert len(heartbeats) == 5
        for hb in heartbeats:
            assert hb.active_agents == 1

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task


class TestDrainOrdering:
    async def test_drain_is_fifo(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        world_harness.runtime.register_agent(
            make_agent_state(),
            make_persona_spec(),
        )

        task = asyncio.create_task(world_harness.runtime.run())
        await _pump()
        # Heartbeat @1s should arrive before cognition @10s.
        world_harness.clock.advance(1.0)
        await _pump(400)
        world_harness.clock.advance(9.0)
        await _pump(800)

        envs = world_harness.runtime.drain_envelopes()
        kinds = [e.kind for e in envs]
        # First envelope must be the 1 s heartbeat.
        assert kinds[0] == "world_tick"
        # After the cognition tick we expect at least one agent_update.
        assert "agent_update" in kinds

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task
