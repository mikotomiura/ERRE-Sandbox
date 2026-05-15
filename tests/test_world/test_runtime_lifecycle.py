"""FSM tests for ``WorldRuntime`` run-level epoch transitions (M8, L6-D3).

Covers the allowed transition path ``autonomous → q_and_a → evaluation`` and
the disallowed paths (direct skip, reverse, re-transition). Construction
reuses the ``world_harness`` fixture so the runtime is in its default post-
``__init__`` state (``EpochPhase.AUTONOMOUS``) without running any tick.

The trailing ``TestWorldRuntimeEnvelopeQueue`` class covers the SH-5 hardening
of the runtime envelope queue (2-queue split with bounded main +
coalescing heartbeat).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erre_sandbox.schemas import (
    EpochPhase,
    ErrorMsg,
    RunLifecycleState,
    WorldTickMsg,
)

if TYPE_CHECKING:
    from .conftest import RuntimeHarness


class TestWorldRuntimeLifecycleDefaults:
    def test_defaults_to_autonomous_phase(self, world_harness: RuntimeHarness) -> None:
        state = world_harness.runtime.run_lifecycle
        assert isinstance(state, RunLifecycleState)
        assert state.epoch_phase is EpochPhase.AUTONOMOUS

    def test_run_lifecycle_property_returns_live_instance(
        self, world_harness: RuntimeHarness
    ) -> None:
        """Property returns the current instance so observers can snapshot it."""
        first = world_harness.runtime.run_lifecycle
        second = world_harness.runtime.run_lifecycle
        assert first is second


class TestWorldRuntimeLifecycleAllowedTransitions:
    def test_autonomous_to_q_and_a(self, world_harness: RuntimeHarness) -> None:
        result = world_harness.runtime.transition_to_q_and_a()
        assert result.epoch_phase is EpochPhase.Q_AND_A
        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.Q_AND_A

    def test_q_and_a_to_evaluation(self, world_harness: RuntimeHarness) -> None:
        world_harness.runtime.transition_to_q_and_a()
        result = world_harness.runtime.transition_to_evaluation()
        assert result.epoch_phase is EpochPhase.EVALUATION
        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.EVALUATION

    def test_transition_replaces_lifecycle_instance(
        self, world_harness: RuntimeHarness
    ) -> None:
        """Transitions swap the instance so snapshotted refs stay stable."""
        before = world_harness.runtime.run_lifecycle
        world_harness.runtime.transition_to_q_and_a()
        after = world_harness.runtime.run_lifecycle
        assert before is not after
        # The old snapshot still carries the pre-transition phase; observers
        # that captured it before the swap retain a stable reading.
        assert before.epoch_phase is EpochPhase.AUTONOMOUS


class TestWorldRuntimeLifecycleRejectedTransitions:
    def test_autonomous_to_evaluation_is_rejected(
        self, world_harness: RuntimeHarness
    ) -> None:
        with pytest.raises(ValueError, match="q_and_a → evaluation"):
            world_harness.runtime.transition_to_evaluation()
        # Phase unchanged.
        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.AUTONOMOUS

    def test_q_and_a_to_autonomous_is_rejected(
        self, world_harness: RuntimeHarness
    ) -> None:
        world_harness.runtime.transition_to_q_and_a()
        with pytest.raises(ValueError, match="autonomous → q_and_a"):
            world_harness.runtime.transition_to_q_and_a()

    def test_evaluation_to_q_and_a_is_rejected(
        self, world_harness: RuntimeHarness
    ) -> None:
        world_harness.runtime.transition_to_q_and_a()
        world_harness.runtime.transition_to_evaluation()
        with pytest.raises(ValueError, match="autonomous → q_and_a"):
            world_harness.runtime.transition_to_q_and_a()

    def test_evaluation_to_evaluation_is_rejected(
        self, world_harness: RuntimeHarness
    ) -> None:
        world_harness.runtime.transition_to_q_and_a()
        world_harness.runtime.transition_to_evaluation()
        with pytest.raises(ValueError, match="q_and_a → evaluation"):
            world_harness.runtime.transition_to_evaluation()


class TestWorldRuntimeEnvelopeQueue:
    """SH-5: bounded main queue + coalescing heartbeat queue."""

    def test_envelope_queue_overflow_emits_warning_and_drops_oldest(
        self, world_harness: RuntimeHarness
    ) -> None:
        runtime = world_harness.runtime
        for i in range(1024):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        runtime.inject_envelope(WorldTickMsg(tick=9999, active_agents=0))
        drained = runtime.drain_envelopes()
        ticks = [e.tick for e in drained if isinstance(e, WorldTickMsg)]
        assert 9999 in ticks
        errors = [e for e in drained if isinstance(e, ErrorMsg)]
        assert len(errors) >= 1
        assert errors[0].code == "runtime_backlog_overflow"
        assert "drops=" in errors[0].detail
        # The very first envelope (tick=0) was dropped to make room.
        assert 0 not in ticks

    async def test_heartbeat_queue_coalesces_to_latest(
        self, world_harness: RuntimeHarness
    ) -> None:
        runtime = world_harness.runtime
        await runtime._on_heartbeat_tick()
        await runtime._on_heartbeat_tick()
        await runtime._on_heartbeat_tick()
        drained = runtime.drain_envelopes()
        heartbeats = [e for e in drained if isinstance(e, WorldTickMsg)]
        assert len(heartbeats) == 1

    async def test_recv_envelope_returns_main_and_preserves_heartbeat(
        self, world_harness: RuntimeHarness
    ) -> None:
        """SH-5 Codex 13th HIGH-1: heartbeat must not be silent-dropped when
        both queues are ready at the moment of ``recv_envelope``."""
        runtime = world_harness.runtime
        await runtime._on_heartbeat_tick()
        runtime.inject_envelope(WorldTickMsg(tick=42, active_agents=0))
        first = await runtime.recv_envelope()
        # Main is prioritised: the directly-injected envelope must come
        # back first.
        assert isinstance(first, WorldTickMsg)
        assert first.tick == 42
        # The heartbeat that raced alongside must remain observable on the
        # heartbeat queue.
        drained = runtime.drain_envelopes()
        heartbeats = [e for e in drained if isinstance(e, WorldTickMsg)]
        assert len(heartbeats) == 1
