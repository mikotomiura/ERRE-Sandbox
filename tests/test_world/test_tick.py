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
from erre_sandbox.world import ManualClock, WorldRuntime
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
        # M7ζ-3 phase wheel: ``_on_cognition_tick`` reads ``clock.monotonic``
        # at handler entry, so a single ``advance(30.0)`` would fire three
        # heap events that all see ``now=30`` and only the first would step
        # (the rest would observe ``next_cognition_due=40 > now``). Advance
        # in three 10 s increments so each tick gets a fresh ``now``.
        for _ in range(3):
            world_harness.clock.advance(10.0)
            await _pump(500)
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
        # SH-5: the heartbeat queue is coalescing (maxsize=1, latest-wins).
        # Five heartbeat ticks fired but drain returns at most one — the
        # most recent — so consumers always see the freshest world tick
        # rather than a backlog.
        assert len(heartbeats) == 1
        assert heartbeats[0].active_agents == 1

        world_harness.runtime.stop()
        world_harness.clock.advance(1.0)
        await _pump()
        await task


class TestWorldModelRuntimeWriteBack:
    """M10-C: AgentRuntime owns the carried world-model state (DA-M10C-6)."""

    async def test_runtime_state_round_trips_through_agent_runtime(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """``CycleResult.world_model_runtime`` is written back and re-supplied."""
        from erre_sandbox.cognition import WorldModelRuntimeState
        from erre_sandbox.contracts.cognition_layers import (
            SubjectiveWorldModel,
            WorldModelEntry,
        )

        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        agent_id = runtime.agent_ids[0]
        rt = runtime._agents[agent_id]
        assert rt.world_model_runtime is None  # flag-off default

        entry = WorldModelEntry(
            axis="env",
            key="agora",
            value=0.45,
            confidence=0.6,
            cited_memory_ids=("belief_x__y",),
            last_updated_tick=3,
        )
        produced = WorldModelRuntimeState(
            base_floor=SubjectiveWorldModel(entries=[entry]),
            modulated=SubjectiveWorldModel(entries=[entry]),
        )

        async def responder(call: MockCycleCall) -> object:
            return CycleResult(
                agent_state=call.agent_state,
                world_model_runtime=produced,
            )

        world_harness.cycle.set_responder(responder)

        # First step: nothing carried in yet; the result seeds the runtime.
        res = await runtime._step_one(rt)
        assert world_harness.cycle.calls[-1].world_model_runtime is None
        runtime._consume_result(rt, res)
        assert rt.world_model_runtime == produced  # written back

        # Second step: the stored state is handed back to the cycle.
        await runtime._step_one(rt)
        assert world_harness.cycle.calls[-1].world_model_runtime == produced

    async def test_none_result_does_not_clobber_stored_state(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """A ``None`` carry (e.g. flag-off result) leaves an existing state intact."""
        from erre_sandbox.cognition import WorldModelRuntimeState
        from erre_sandbox.contracts.cognition_layers import SubjectiveWorldModel

        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        rt.world_model_runtime = WorldModelRuntimeState(
            base_floor=SubjectiveWorldModel(),
            modulated=SubjectiveWorldModel(),
        )
        kept = rt.world_model_runtime

        async def responder(call: MockCycleCall) -> object:
            return CycleResult(agent_state=call.agent_state)  # world_model_runtime=None

        world_harness.cycle.set_responder(responder)
        res = await runtime._step_one(rt)
        runtime._consume_result(rt, res)
        assert rt.world_model_runtime is kept  # untouched

    async def test_narrative_arc_carries_forward_on_none(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """M11-A: a built arc is written back; a ``None`` result keeps the last one."""
        from erre_sandbox.contracts.cognition_layers import ArcSegment, NarrativeArc

        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        assert rt.narrative_arc is None  # flag-off default

        arc = NarrativeArc(
            synthesized_at_tick=3,
            arc_segments=[
                ArcSegment(
                    segment_label="env/agora",
                    start_tick=3,
                    end_tick=3,
                    cited_memory_ids=("belief_x__y",),
                ),
            ],
            coherence_score=0.42,
            last_episodic_pointer="ep-1",
        )

        # First step produces an arc → written back.
        async def with_arc(call: MockCycleCall) -> object:
            return CycleResult(agent_state=call.agent_state, narrative_arc=arc)

        world_harness.cycle.set_responder(with_arc)
        runtime._consume_result(rt, await runtime._step_one(rt))
        assert rt.narrative_arc == arc

        # Second step synthesises nothing (silent / outage) → previous arc kept.
        async def no_arc(call: MockCycleCall) -> object:
            return CycleResult(agent_state=call.agent_state)  # narrative_arc=None

        world_harness.cycle.set_responder(no_arc)
        runtime._consume_result(rt, await runtime._step_one(rt))
        assert rt.narrative_arc is arc  # carried forward, not cleared

    async def test_development_state_carries_forward_and_threads_back(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """M11-B: an advanced state is written back, re-supplied to the next step,
        and a ``None`` result (silent / flag-off tick) keeps the prior one."""
        from erre_sandbox.contracts.cognition_layers import DevelopmentState

        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        assert rt.development_state is None  # flag-off default

        produced = DevelopmentState(stage="S2_exploring", maturity_score=0.5)

        async def with_state(call: MockCycleCall) -> object:
            return CycleResult(agent_state=call.agent_state, development_state=produced)

        world_harness.cycle.set_responder(with_state)
        # First step: nothing carried in yet; the result seeds the runtime.
        res = await runtime._step_one(rt)
        assert world_harness.cycle.calls[-1].development_state is None
        runtime._consume_result(rt, res)
        assert rt.development_state == produced  # written back

        # Second step: the stored state is handed back to the cycle.
        await runtime._step_one(rt)
        assert world_harness.cycle.calls[-1].development_state == produced

        # A ``None`` result (non-observation) leaves the prior state untouched.
        async def no_state(call: MockCycleCall) -> object:
            return CycleResult(agent_state=call.agent_state)  # development_state=None

        world_harness.cycle.set_responder(no_state)
        runtime._consume_result(rt, await runtime._step_one(rt))
        assert rt.development_state is produced  # carried forward, not cleared


class TestRegisterAgentCollisionGuard:
    """M11-C1 (DA-M11C1-3): a duplicate agent_id raises; distinct ids coexist."""

    def test_duplicate_agent_id_raises(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        with pytest.raises(ValueError, match="already registered"):
            runtime.register_agent(make_agent_state(), make_persona_spec())

    def test_same_base_distinct_ordinals_coexist(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """Same-base 2-3 individuals register without collision (M11-C1 acceptance)."""
        runtime = world_harness.runtime
        for ordinal in (1, 2, 3):
            state = make_agent_state(
                agent_id=f"a_rikyu_{ordinal:03d}",
                persona_id="rikyu",
            )
            runtime.register_agent(state, make_persona_spec(persona_id="rikyu"))
        assert runtime.agent_ids == ["a_rikyu_001", "a_rikyu_002", "a_rikyu_003"]


class TestSnapshotProfile:
    """M11-C1 (DA-M11C1-5/6): snapshot_profile() = faithful, alias-free read-model."""

    @staticmethod
    def _populate(rt: Any) -> None:
        """Set all three carried fields to known non-None values on a runtime."""
        from erre_sandbox.cognition import WorldModelRuntimeState
        from erre_sandbox.contracts.cognition_layers import (
            ArcSegment,
            DevelopmentState,
            NarrativeArc,
            SubjectiveWorldModel,
            WorldModelEntry,
        )

        entry = WorldModelEntry(
            axis="env",
            key="agora",
            value=0.45,
            confidence=0.6,
            cited_memory_ids=("belief_x__y",),
            last_updated_tick=3,
        )
        rt.world_model_runtime = WorldModelRuntimeState(
            base_floor=SubjectiveWorldModel(entries=[entry]),
            modulated=SubjectiveWorldModel(entries=[entry]),
        )
        rt.narrative_arc = NarrativeArc(
            synthesized_at_tick=3,
            arc_segments=[
                ArcSegment(
                    segment_label="env/agora",
                    start_tick=3,
                    end_tick=3,
                    cited_memory_ids=("belief_x__y",),
                ),
            ],
            coherence_score=0.42,
            last_episodic_pointer="ep-1",
        )
        rt.development_state = DevelopmentState(
            stage="S2_exploring", maturity_score=0.5
        )

    def test_snapshot_equals_live_state(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        from erre_sandbox.cognition.world_model import project_world_model_snapshot
        from erre_sandbox.contracts.cognition_layers import PersonalityDrift

        runtime = world_harness.runtime
        runtime.register_agent(
            make_agent_state(agent_id="a_rikyu_002", persona_id="rikyu"),
            make_persona_spec(persona_id="rikyu"),
        )
        rt = runtime._agents["a_rikyu_002"]
        self._populate(rt)

        profile = rt.snapshot_profile()
        assert profile.individual_id == "a_rikyu_002"
        assert profile.base_persona_id == "rikyu"
        assert profile.world_model == project_world_model_snapshot(
            rt.world_model_runtime,
        )
        assert profile.development_state == rt.development_state
        assert profile.narrative_arc == rt.narrative_arc
        assert profile.personality_drift_offset == PersonalityDrift()

    def test_snapshot_projects_none_faithfully(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """Fresh agent (flag-off / pre-synthesis): None stays None, no fabrication."""
        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        profile = rt.snapshot_profile()
        assert profile.world_model is None
        assert profile.development_state is None
        assert profile.narrative_arc is None

    def test_snapshot_does_not_alias_live_state(
        self,
        world_harness: RuntimeHarness,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """Mutating the snapshot must not write back into the single-source runtime."""
        runtime = world_harness.runtime
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        self._populate(rt)

        snap = rt.snapshot_profile()
        # Mutate every nested mutable structure on the snapshot side. (WorldModelEntry
        # is non-frozen at time of writing; if it becomes frozen, the `.value = ...`
        # line below must switch to another mutable path so this stays an alias test,
        # not a frozen-raises test.)
        assert snap.world_model is not None
        assert snap.narrative_arc is not None
        assert snap.development_state is not None
        snap.world_model.base_floor.entries.clear()
        snap.world_model.modulated.entries[0].value = 0.99
        snap.narrative_arc.arc_segments.clear()
        snap.development_state.transition_evidence["injected"] = 7

        # The live runtime state is untouched (deep-copy severed the alias).
        assert rt.world_model_runtime is not None
        assert rt.narrative_arc is not None
        assert rt.development_state is not None
        assert len(rt.world_model_runtime.base_floor.entries) == 1
        assert rt.world_model_runtime.modulated.entries[0].value == 0.45
        assert len(rt.narrative_arc.arc_segments) == 1
        assert rt.development_state.transition_evidence == {}


class TestEmitIndividualTrace:
    """M11-C2 (DA-M11C2-1/2/4): the flag-on trace sink hook in _consume_result."""

    def test_emit_forwards_snapshot_belief_classes_and_tick(
        self,
        manual_clock: ManualClock,
        mock_cycle: Any,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """flag-on: the sink receives (snapshot, belief_classes, tick)."""
        from erre_sandbox.contracts.cognition_layers import (
            DevelopmentState,
            IndividualProfile,
        )

        captured: list[tuple[IndividualProfile, list[str] | None, int]] = []
        runtime = WorldRuntime(
            cycle=mock_cycle,  # type: ignore[arg-type]
            clock=manual_clock,
            individual_trace_sink=lambda p, bc, t: captured.append((p, bc, t)),
        )
        runtime.register_agent(
            make_agent_state(agent_id="a_rikyu_001", persona_id="rikyu"),
            make_persona_spec(persona_id="rikyu"),
        )
        rt = runtime._agents["a_rikyu_001"]
        rt.development_state = DevelopmentState(
            stage="S2_exploring", maturity_score=0.5
        )
        res = CycleResult(agent_state=rt.state, belief_classes=["trust", "wary"])

        runtime._emit_individual_trace(rt, res)

        assert len(captured) == 1
        profile, belief_classes, tick = captured[0]
        assert belief_classes == ["trust", "wary"]
        assert tick == rt.state.tick
        assert profile.individual_id == "a_rikyu_001"
        assert profile.development_state is not None
        assert profile.development_state.stage == "S2_exploring"

    def test_emit_noops_without_sink(
        self,
        manual_clock: ManualClock,
        mock_cycle: Any,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """flag-off (sink None): no snapshot, no error — the byte-invariant path."""
        runtime = WorldRuntime(cycle=mock_cycle, clock=manual_clock)  # type: ignore[arg-type]
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        res = CycleResult(agent_state=rt.state, belief_classes=["trust"])
        # Must not raise and must not require a sink.
        runtime._emit_individual_trace(rt, res)


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
