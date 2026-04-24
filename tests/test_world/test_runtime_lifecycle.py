"""FSM tests for ``WorldRuntime`` run-level epoch transitions (M8, L6-D3).

Covers the allowed transition path ``autonomous → q_and_a → evaluation`` and
the disallowed paths (direct skip, reverse, re-transition). Construction
reuses the ``world_harness`` fixture so the runtime is in its default post-
``__init__`` state (``EpochPhase.AUTONOMOUS``) without running any tick.
"""

from __future__ import annotations

import pytest

from erre_sandbox.schemas import EpochPhase, RunLifecycleState

from .conftest import RuntimeHarness


class TestWorldRuntimeLifecycleDefaults:
    def test_defaults_to_autonomous_phase(
        self, world_harness: RuntimeHarness
    ) -> None:
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
    def test_autonomous_to_q_and_a(
        self, world_harness: RuntimeHarness
    ) -> None:
        result = world_harness.runtime.transition_to_q_and_a()
        assert result.epoch_phase is EpochPhase.Q_AND_A
        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.Q_AND_A

    def test_q_and_a_to_evaluation(
        self, world_harness: RuntimeHarness
    ) -> None:
        world_harness.runtime.transition_to_q_and_a()
        result = world_harness.runtime.transition_to_evaluation()
        assert result.epoch_phase is EpochPhase.EVALUATION
        assert (
            world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.EVALUATION
        )

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
        assert (
            world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.AUTONOMOUS
        )

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
