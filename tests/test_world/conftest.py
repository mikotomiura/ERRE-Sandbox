"""Shared fixtures for ``tests/test_world/`` (T13).

``MockCycle`` stands in for :class:`erre_sandbox.cognition.CognitionCycle` so
tick-loop tests can assert what the runtime does **with** cycle results
without involving the real cognition pipeline (which already has its own
coverage in ``tests/test_cognition``).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

import pytest

from erre_sandbox.cognition import CycleResult
from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    ControlEnvelope,
    Observation,
    PersonaSpec,
)
from erre_sandbox.world import ManualClock, WorldRuntime


@dataclass
class MockCycleCall:
    """Record of one :meth:`MockCycle.step` invocation."""

    agent_state: AgentState
    persona: PersonaSpec
    observations: list[Observation]
    tick_seconds: float


StepResponder = Callable[[MockCycleCall], Awaitable[object]]
"""Test-side hook: given the recorded call, return either a ``CycleResult`` or
raise. ``object`` keeps the type free of a CognitionCycle dependency here so
new response shapes (e.g. custom envelopes) need no fixture change."""


class MockCycle:
    """Duck-typed ``CognitionCycle`` replacement.

    The real class is not subclassed so tests cannot accidentally depend on
    private state; we only need :meth:`step` for the runtime contract.
    """

    def __init__(self, responder: StepResponder | None = None) -> None:
        self.calls: deque[MockCycleCall] = deque()
        self._responder: StepResponder | None = responder

    def set_responder(self, responder: StepResponder) -> None:
        self._responder = responder

    async def step(
        self,
        agent_state: AgentState,
        persona: PersonaSpec,
        observations: Sequence[Observation],
        *,
        tick_seconds: float,
    ) -> object:
        call = MockCycleCall(
            agent_state=agent_state,
            persona=persona,
            observations=list(observations),
            tick_seconds=tick_seconds,
        )
        self.calls.append(call)
        if self._responder is None:
            # Default: echo the incoming state unchanged, emit one AgentUpdate.
            return CycleResult(
                agent_state=agent_state,
                envelopes=[
                    AgentUpdateMsg(
                        tick=agent_state.tick,
                        agent_state=agent_state,
                    ),
                ],
            )
        return await self._responder(call)


@dataclass
class RuntimeHarness:
    """Bundle of runtime + its injected clock + mock cycle."""

    runtime: WorldRuntime
    clock: ManualClock
    cycle: MockCycle
    envelopes_seen: list[ControlEnvelope] = field(default_factory=list)


@pytest.fixture
def manual_clock() -> ManualClock:
    return ManualClock(start=0.0)


@pytest.fixture
def mock_cycle() -> MockCycle:
    return MockCycle()


@pytest.fixture
def world_harness(
    manual_clock: ManualClock,
    mock_cycle: MockCycle,
) -> RuntimeHarness:
    runtime = WorldRuntime(
        cycle=mock_cycle,  # type: ignore[arg-type]
        clock=manual_clock,
        physics_hz=30.0,
        cognition_period_s=10.0,
        heartbeat_period_s=1.0,
    )
    return RuntimeHarness(runtime=runtime, clock=manual_clock, cycle=mock_cycle)
