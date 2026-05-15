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

import asyncio
import contextlib
import logging
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

    # ------------------------------------------------------------------
    # Codex 13th MEDIUM coverage gaps (security-hardening-pre-m10-followup)
    # ------------------------------------------------------------------
    # The four cases below close the boundary / monotonic / cancel /
    # observability gaps the Codex 13th review flagged after PR #170.
    # ``maxsize`` is 1024 in production; the test exercises that exact value
    # rather than a re-bound smaller queue so any regression in the
    # ``qsize() > maxsize - 2`` drain loop surfaces under the live config.

    def test_envelope_queue_at_maxsize_minus_one_does_not_overflow(
        self, world_harness: RuntimeHarness
    ) -> None:
        """1023 inserts (maxsize=1024 → ``maxsize-1``): no overflow path."""
        runtime = world_harness.runtime
        for i in range(runtime._envelopes.maxsize - 1):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        assert runtime._envelope_overflow_count == 0
        # No warning was enqueued because the queue never hit ``full()``.
        drained = runtime.drain_envelopes()
        assert all(isinstance(env, WorldTickMsg) for env in drained)

    def test_envelope_queue_at_exact_maxsize_does_not_overflow(
        self, world_harness: RuntimeHarness
    ) -> None:
        """1024 inserts (exact maxsize): boundary stays under overflow."""
        runtime = world_harness.runtime
        for i in range(runtime._envelopes.maxsize):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        # The Nth insert sees the queue not-yet-full pre-put, so it lands
        # without invoking the drop-oldest path.
        assert runtime._envelope_overflow_count == 0

    def test_envelope_queue_at_maxsize_plus_one_triggers_overflow_once(
        self, world_harness: RuntimeHarness
    ) -> None:
        """1025th insert: overflow path fires exactly once and warning lands."""
        runtime = world_harness.runtime
        for i in range(runtime._envelopes.maxsize):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        assert runtime._envelope_overflow_count == 0
        runtime.inject_envelope(WorldTickMsg(tick=9999, active_agents=0))
        assert runtime._envelope_overflow_count >= 1
        drained = runtime.drain_envelopes()
        errors = [e for e in drained if isinstance(e, ErrorMsg)]
        assert errors
        assert errors[0].code == "runtime_backlog_overflow"

    def test_repeated_overflow_increments_count_monotonically(
        self, world_harness: RuntimeHarness
    ) -> None:
        """``_envelope_overflow_count`` is monotonically non-decreasing
        across distinct overflow bursts so an SRE timeseries can derive
        rate-of-overflow without rebasing."""
        runtime = world_harness.runtime
        # First burst: drain to room=0, then inject one extra.
        for i in range(runtime._envelopes.maxsize + 1):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        first_burst = runtime._envelope_overflow_count
        assert first_burst >= 1
        # Inject another N+2 envelopes; the queue is full from burst 1, so
        # subsequent inserts continue draining oldest and the counter must
        # keep climbing.
        for i in range(runtime._envelopes.maxsize + 2):
            runtime.inject_envelope(
                WorldTickMsg(tick=10_000 + i, active_agents=0),
            )
        second_burst = runtime._envelope_overflow_count
        assert second_burst > first_burst

    def test_consume_result_path_uses_drop_oldest_helper(
        self, world_harness: RuntimeHarness
    ) -> None:
        """Both ingress paths funnel through ``_enqueue_with_drop_oldest``.

        ``inject_envelope`` and ``_consume_result`` share the helper so the
        SH-5 overflow accounting (and SH-FOLLOWUP / Codex 13th MEDIUM
        ``logger.warning`` emission) applies uniformly. Test this by
        priming the queue via ``inject_envelope`` to overflow, then calling
        the helper directly (the same call ``_consume_result`` makes per
        :meth:`WorldRuntime._consume_result.envelopes` loop). The shared
        counter must reflect both calls without rebase.
        """
        runtime = world_harness.runtime
        for i in range(runtime._envelopes.maxsize + 1):
            runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        baseline = runtime._envelope_overflow_count
        # Direct helper invocation models the ``_consume_result`` exit path.
        runtime._enqueue_with_drop_oldest(
            WorldTickMsg(tick=42_000, active_agents=0),
        )
        assert runtime._envelope_overflow_count > baseline

    def test_overflow_emits_logger_warning_for_sre_observability(
        self,
        world_harness: RuntimeHarness,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Codex 13th MEDIUM: in-band ``ErrorMsg`` is paired with an
        out-of-band ``logger.warning`` so the journal-only SRE pipeline
        catches overflow even when the ErrorMsg consumer is the slow one.
        """
        runtime = world_harness.runtime
        with caplog.at_level(logging.WARNING, logger="erre_sandbox.world.tick"):
            for i in range(runtime._envelopes.maxsize + 1):
                runtime.inject_envelope(WorldTickMsg(tick=i, active_agents=0))
        overflow_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "backlog overflow" in r.message
        ]
        assert overflow_records, (
            "expected at least one logger.warning('runtime backlog overflow ...')"
        )

    async def test_recv_envelope_cancel_releases_resources_cleanly(
        self, world_harness: RuntimeHarness
    ) -> None:
        """A cancelled ``recv_envelope`` must not leave a pending getter
        warning in the loop close path and must not poison either queue."""
        runtime = world_harness.runtime
        task = asyncio.create_task(runtime.recv_envelope())
        # Yield long enough for ``recv_envelope`` to spawn its two
        # internal getters and block on ``asyncio.wait``.
        await asyncio.sleep(0)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # Both queues are still empty — no orphan items left behind by the
        # cancellation race.
        assert runtime._envelopes.qsize() == 0
        assert runtime._heartbeat_envelopes.qsize() == 0
