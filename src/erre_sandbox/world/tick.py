"""Single-coroutine heapq scheduler that drives the world tick loop (T13).

The runtime owns three periodic handlers:

* **physics** — 30 Hz: advance each agent's :class:`Kinematics`, emit
  :class:`ZoneTransitionEvent` when a zone boundary is crossed.
* **cognition** — 0.1 Hz (every 10 s): fan out to
  :meth:`CognitionCycle.step` for every registered agent via
  :func:`asyncio.gather` (``return_exceptions=True``) so one agent's LLM
  failure does not cancel the sibling tasks.
* **heartbeat** — 1 Hz: push a :class:`WorldTickMsg` into the envelope
  queue for observability.

All three live on a single :class:`asyncio.Task` via a min-heap of absolute
``due_at`` timestamps, which removes cross-task data races (no lock is taken
on ``_agents`` / ``_envelopes``) and lets a :class:`ManualClock` reproduce
any desired interleaving in tests.

See ``.steering/20260419-world-tick-zones/design.md`` for the v2 design
rationale (single coroutine, Voronoi zones, unbounded queue, anti-drift).
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, ClassVar

from erre_sandbox.schemas import (
    AgentState,
    ControlEnvelope,
    MoveMsg,
    Observation,
    PersonaSpec,
    WorldTickMsg,
    ZoneTransitionEvent,
)
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from erre_sandbox.cognition import CognitionCycle, CycleResult

logger = logging.getLogger(__name__)


# =============================================================================
# Clock abstraction
# =============================================================================


class Clock(ABC):
    """Minimal clock used by :class:`WorldRuntime` for absolute scheduling."""

    @abstractmethod
    def monotonic(self) -> float:
        """Return the current monotonic time in seconds."""

    @abstractmethod
    async def sleep_until(self, due_at: float) -> None:
        """Sleep until :meth:`monotonic` would return at least ``due_at``."""


class RealClock(Clock):
    """Production clock backed by :func:`time.monotonic` / :func:`asyncio.sleep`."""

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep_until(self, due_at: float) -> None:
        delta = due_at - time.monotonic()
        if delta > 0.0:
            await asyncio.sleep(delta)


class ManualClock(Clock):
    """Deterministic clock for tests.

    ``advance(dt)`` moves the clock forward by ``dt`` seconds and resolves any
    :meth:`sleep_until` waiters whose ``due_at`` has been reached. Waiters
    with identical ``due_at`` are woken in insertion order.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now: float = start
        self._waiters: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq: int = 0

    def monotonic(self) -> float:
        return self._now

    async def sleep_until(self, due_at: float) -> None:
        if due_at <= self._now:
            await asyncio.sleep(0)
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._seq += 1
        heapq.heappush(self._waiters, (due_at, self._seq, fut))
        await fut

    def advance(self, dt: float) -> None:
        """Advance time and wake any sleepers whose ``due_at <= new now``.

        The method is synchronous on purpose: callers usually issue it as
        ``manual_clock.advance(...)`` and then ``await asyncio.sleep(0)`` to
        let the event loop run the woken coroutines.
        """
        if dt < 0.0:
            msg = "ManualClock cannot run backward"
            raise ValueError(msg)
        self._now += dt
        while self._waiters and self._waiters[0][0] <= self._now:
            _, _, fut = heapq.heappop(self._waiters)
            if not fut.done():
                fut.set_result(None)


# =============================================================================
# Scheduled events
# =============================================================================


@dataclass(order=True)
class ScheduledEvent:
    """A single entry on the runtime's min-heap.

    ``order=True`` plus the ``seq`` tie-breaker gives stable FIFO ordering
    when two events share the same ``due_at``, which matters because the three
    handlers (physics, cognition, heartbeat) are all seeded at ``t = 0``.
    """

    due_at: float
    seq: int
    period: float = field(compare=False)
    handler: Callable[[], Awaitable[None]] = field(compare=False)
    name: str = field(compare=False, default="")


# =============================================================================
# Agent runtime bookkeeping
# =============================================================================


@dataclass(slots=True)
class AgentRuntime:
    """Per-agent mutable state owned by :class:`WorldRuntime`.

    Kept deliberately separate from :class:`AgentState` so that transient
    bookkeeping (pending observations, kinematics) never leaks into the
    persisted snapshot.
    """

    agent_id: str
    state: AgentState
    persona: PersonaSpec
    kinematics: Kinematics
    pending: list[Observation] = field(default_factory=list)


# =============================================================================
# WorldRuntime
# =============================================================================


class WorldRuntime:
    """Drives physics + cognition + heartbeat for N agents on one asyncio task.

    Construction injects the :class:`CognitionCycle` (so the test double
    used in :mod:`tests.test_world` can be trivially swapped) and a
    :class:`Clock` (defaults to :class:`RealClock`; tests pass
    :class:`ManualClock` to drive time deterministically).
    """

    DEFAULT_PHYSICS_HZ: ClassVar[float] = 30.0
    DEFAULT_COGNITION_PERIOD_S: ClassVar[float] = 10.0
    DEFAULT_HEARTBEAT_PERIOD_S: ClassVar[float] = 1.0

    def __init__(
        self,
        *,
        cycle: CognitionCycle,
        clock: Clock | None = None,
        physics_hz: float | None = None,
        cognition_period_s: float | None = None,
        heartbeat_period_s: float | None = None,
    ) -> None:
        self._cycle = cycle
        self._clock: Clock = clock if clock is not None else RealClock()
        self._physics_dt = 1.0 / (physics_hz or self.DEFAULT_PHYSICS_HZ)
        self._cognition_period = (
            cognition_period_s
            if cognition_period_s is not None
            else self.DEFAULT_COGNITION_PERIOD_S
        )
        self._heartbeat_period = (
            heartbeat_period_s
            if heartbeat_period_s is not None
            else self.DEFAULT_HEARTBEAT_PERIOD_S
        )
        self._agents: dict[str, AgentRuntime] = {}
        self._events: list[ScheduledEvent] = []
        # TODO(T14): the unbounded queue is a deliberate MVP trade-off
        # (see decisions.md D7). When T14 wires a real WebSocket consumer,
        # switch to ``maxsize=10_000`` and add an oldest-drop / back-pressure
        # policy so a stalled client cannot grow memory without bound.
        self._envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
        self._running: bool = False
        self._seq: int = 0

    # ----- Registration -----

    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None:
        """Add an agent whose cognition cycle this runtime should drive.

        Must be called before :meth:`run` or from within a handler on the
        same event-loop task; the runtime uses a plain :class:`dict` for
        ``_agents`` and takes no lock, so concurrent mutation from a
        different task would race with the scheduler.
        """
        self._agents[state.agent_id] = AgentRuntime(
            agent_id=state.agent_id,
            state=state,
            persona=persona,
            kinematics=Kinematics(position=state.position),
        )

    def inject_observation(self, agent_id: str, obs: Observation) -> None:
        """Queue an externally sourced observation for ``agent_id``.

        The observation is consumed on the next cognition tick. Useful for
        tests and for T14 when external stimuli (e.g. user messages) need to
        reach an agent without going through the physics loop.
        """
        self._agents[agent_id].pending.append(obs)

    @property
    def agent_ids(self) -> list[str]:
        """Snapshot of currently registered agent ids (order = registration)."""
        return list(self._agents)

    # ----- Envelope consumers (T14 hooks) -----

    async def recv_envelope(self) -> ControlEnvelope:
        """Await and return the next envelope (FIFO).

        Blocking variant intended for T14's WebSocket producer.
        """
        return await self._envelopes.get()

    def drain_envelopes(self) -> list[ControlEnvelope]:
        """Non-blocking drain of all currently queued envelopes (FIFO)."""
        out: list[ControlEnvelope] = []
        while not self._envelopes.empty():
            out.append(self._envelopes.get_nowait())
        return out

    # ----- Lifecycle -----

    async def run(self) -> None:
        """Run the scheduler until :meth:`stop` is called.

        Uses a single min-heap of absolute ``due_at`` timestamps; on each
        iteration it pops the earliest event, awaits
        :meth:`Clock.sleep_until`, invokes the handler (with per-handler
        exception isolation so one bug cannot kill the loop), and reschedules
        the event at ``due_at + period`` (anti-drift: absolute time, not
        cumulative deltas).
        """
        now = self._clock.monotonic()
        self._schedule(
            now + self._physics_dt,
            self._physics_dt,
            self._on_physics_tick,
            name="physics",
        )
        self._schedule(
            now + self._cognition_period,
            self._cognition_period,
            self._on_cognition_tick,
            name="cognition",
        )
        self._schedule(
            now + self._heartbeat_period,
            self._heartbeat_period,
            self._on_heartbeat_tick,
            name="heartbeat",
        )

        self._running = True
        try:
            while self._running and self._events:
                ev = heapq.heappop(self._events)
                await self._clock.sleep_until(ev.due_at)
                if not self._running:
                    break
                try:
                    await ev.handler()
                except Exception:
                    logger.exception("world tick handler %s failed", ev.name)
                # Anti-drift: next due is previous due + period, not now + period.
                self._seq += 1
                next_due = ev.due_at + ev.period
                heapq.heappush(
                    self._events,
                    replace(ev, due_at=next_due, seq=self._seq),
                )
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal :meth:`run` to return at the next scheduling point."""
        self._running = False

    # ----- Handlers -----

    async def _on_physics_tick(self) -> None:
        dt = self._physics_dt
        for rt in self._agents.values():
            # Capture the zone BEFORE model_copy overwrites it; otherwise the
            # emitted ZoneTransitionEvent's from_zone would equal to_zone.
            prev_zone = rt.state.position.zone
            new_pos, zone_changed = step_kinematics(rt.kinematics, dt)
            if new_pos != rt.state.position:
                rt.state = rt.state.model_copy(update={"position": new_pos})
            if zone_changed is not None:
                rt.pending.append(
                    ZoneTransitionEvent(
                        tick=rt.state.tick,
                        agent_id=rt.agent_id,
                        from_zone=prev_zone,
                        to_zone=zone_changed,
                    ),
                )

    async def _on_cognition_tick(self) -> None:
        if not self._agents:
            return
        # Evaluate agents list once so that dict mutation during gather
        # (register_agent from inside a handler, if anyone ever does that)
        # cannot desynchronise the result / runtime pairing below.
        runtimes = list(self._agents.values())
        results = await asyncio.gather(
            *(self._step_one(rt) for rt in runtimes),
            return_exceptions=True,
        )
        for rt, res in zip(runtimes, results, strict=True):
            self._consume_result(rt, res)

    async def _on_heartbeat_tick(self) -> None:
        current_tick = max(
            (rt.state.tick for rt in self._agents.values()),
            default=0,
        )
        await self._envelopes.put(
            WorldTickMsg(
                tick=current_tick,
                active_agents=len(self._agents),
            ),
        )

    # ----- Cognition helpers -----

    async def _step_one(self, rt: AgentRuntime) -> CycleResult:
        # Exceptions raised by the cycle are NOT caught here; the caller is
        # ``asyncio.gather(..., return_exceptions=True)`` which turns them
        # into result-list entries so one agent's failure cannot cancel its
        # siblings. Adding a try/except here would duplicate that contract
        # and confuse future maintainers.
        obs: list[Observation] = rt.pending
        rt.pending = []
        return await self._cycle.step(
            rt.state,
            rt.persona,
            obs,
            tick_seconds=self._cognition_period,
        )

    def _consume_result(
        self,
        rt: AgentRuntime,
        res: CycleResult | BaseException,
    ) -> None:
        if isinstance(res, BaseException):
            logger.exception(
                "agent %s step raised",
                rt.agent_id,
                exc_info=res,
            )
            return
        rt.state = res.agent_state
        rt.kinematics.position = res.agent_state.position
        for env in res.envelopes:
            if isinstance(env, MoveMsg):
                apply_move_command(rt.kinematics, env)
            self._envelopes.put_nowait(env)

    # ----- Scheduling helper -----

    def _schedule(
        self,
        due_at: float,
        period: float,
        handler: Callable[[], Awaitable[None]],
        *,
        name: str,
    ) -> None:
        self._seq += 1
        heapq.heappush(
            self._events,
            ScheduledEvent(
                due_at=due_at,
                seq=self._seq,
                period=period,
                handler=handler,
                name=name,
            ),
        )
