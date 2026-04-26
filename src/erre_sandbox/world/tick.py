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
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from erre_sandbox.cognition.relational import apply_affinity
from erre_sandbox.schemas import (
    AffordanceEvent,
    AgentState,
    AgentView,
    ControlEnvelope,
    DialogScheduler,
    DialogTurnGenerator,
    DialogTurnMsg,
    EpochPhase,
    MoveMsg,
    Observation,
    PersonaSpec,
    PropLayout,
    ProximityEvent,
    RelationshipBond,
    RunLifecycleState,
    TemporalEvent,
    TimeOfDay,
    WorldLayoutMsg,
    WorldTickMsg,
    Zone,
    ZoneLayout,
    ZoneTransitionEvent,
)
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics
from erre_sandbox.world.zones import (
    ZONE_CENTERS,
    ZONE_PROPS,
    default_spawn,
    locate_zone,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Sequence

    from erre_sandbox.cognition import CognitionCycle, CycleResult

logger = logging.getLogger(__name__)


# =============================================================================
# Simulated time-of-day (M6-A-2b)
# =============================================================================

# Ordered ascending by phase. The period covering ``phase ∈ [phase, next_phase)``
# is the one returned by :func:`_time_of_day`. The six buckets map a
# continuous wall-time into the same vocabulary ``TimeOfDay`` uses so the
# FSM and LLM prompt can reason about "morning" without comparing floats.
# Boundaries skew toward daylight because research-session relevance peaks
# around noon / afternoon — night is the short tail.
_PERIOD_BOUNDARIES: tuple[tuple[float, TimeOfDay], ...] = (
    (0.00, TimeOfDay.DAWN),
    (0.10, TimeOfDay.MORNING),
    (0.40, TimeOfDay.NOON),
    (0.55, TimeOfDay.AFTERNOON),
    (0.80, TimeOfDay.DUSK),
    (0.90, TimeOfDay.NIGHT),
)


_PROXIMITY_THRESHOLD_M: Final[float] = 5.0
"""Distance at which an agent pair is considered "proximate" (M6-A-2b).

One :class:`ProximityEvent` is emitted per threshold crossing (``enter``
when the distance falls below, ``leave`` when it rises back above) so
co-walking agents do not spam the observation stream.  The value is
deliberately larger than a conversational radius so the FSM can react
**before** the dialog scheduler kicks in — five metres is the MASTER-PLAN
reading of "same room but not yet engaged".
"""


_AFFORDANCE_RADIUS_M: Final[float] = 2.0
"""Distance at which an agent is considered to notice a static world prop (M7 B1).

Mirrors the crossing-only semantics of :data:`_PROXIMITY_THRESHOLD_M`: a
single :class:`AffordanceEvent` is emitted when the agent's XZ distance to
a prop first falls below this radius. Until the agent has moved back out
of range and re-entered, no further event fires. The value is tighter than
proximity (5 m) because props are spot-like salience markers — a tea bowl
is noticed when the agent is *at* it, not merely in the same zone."""


_NEGATIVE_DELTA_TRIGGER: Final[float] = -0.05
"""M7δ threshold below which a negative affinity delta raises emotional_conflict.

Calibrated so the antagonism table's -0.10 magnitude (kant↔nietzsche)
fires the bump while transient negative noise from decay alone (decay
contribution at low ``prev`` is well above -0.05) does not. Value as of
the C5 retune; see ``.steering/20260426-m7-slice-delta/observation.md``
for the full calibration trajectory."""

_EMOTIONAL_CONFLICT_GAIN: Final[float] = 0.5
"""Coefficient applied to ``abs(delta)`` when raising emotional_conflict.

A -0.10 antagonism delta therefore raises emotional_conflict by 0.05
per turn, clamped at the upper bound of 1.0. The decay back to baseline
(``-0.02`` per tick) happens in
:func:`erre_sandbox.cognition.state.advance_physical`. Value as of the
C5 retune; see ``.steering/20260426-m7-slice-delta/observation.md``."""


def _time_of_day(elapsed: float, day_duration: float) -> TimeOfDay:
    """Map an elapsed-time scalar to the containing :class:`TimeOfDay` bucket.

    ``day_duration`` is the wall-clock length (seconds) of one simulated day
    — the runtime passes its configured value so tests can compress a day
    into milliseconds. The function is pure and cheap; called once per
    physics tick.
    """
    if day_duration <= 0.0:
        return TimeOfDay.DAWN  # degenerate — avoid divide-by-zero
    phase = (elapsed % day_duration) / day_duration
    current = _PERIOD_BOUNDARIES[0][1]
    for boundary, period in _PERIOD_BOUNDARIES:
        if phase >= boundary:
            current = period
    return current


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


@dataclass(slots=True)
class _PendingTurn:
    """One in-flight turn request staged by :meth:`WorldRuntime._drive_dialog_turns`.

    Staging the coroutine with its metadata lets the gather loop correlate
    each result with the dialog/speaker it belongs to for post-processing.
    """

    dialog_id: str
    speaker_id: str
    addressee_id: str
    turn_index: int
    coro: Coroutine[object, object, DialogTurnMsg | None]


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
    DEFAULT_DAY_DURATION_S: ClassVar[float] = 480.0
    """Wall-clock seconds per simulated day (M6-A-2b).

    Eight minutes is short enough that a live demo can traverse the full
    dawn → night cycle in one session while still giving the agent time
    to exhibit each :class:`TimeOfDay` phase. Tests pass a much smaller
    value via ``day_duration_s`` so crossing events can be forced quickly
    without advancing the :class:`ManualClock` for thousands of seconds.
    """

    def __init__(
        self,
        *,
        cycle: CognitionCycle,
        clock: Clock | None = None,
        physics_hz: float | None = None,
        cognition_period_s: float | None = None,
        heartbeat_period_s: float | None = None,
        day_duration_s: float | None = None,
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
        self._day_duration_s = (
            day_duration_s
            if day_duration_s is not None
            else self.DEFAULT_DAY_DURATION_S
        )
        # M6-A-2b: simulated time-of-day tracking. ``_time_start`` is
        # lazily initialised on the first physics tick so ``_current_period``
        # matches the clock the runtime was actually started with (not the
        # clock the constructor saw, which is usually still at t=0).
        self._time_start: float | None = None
        self._current_period: TimeOfDay = TimeOfDay.DAWN
        # M6-A-2b: ProximityEvent needs a prev-tick distance per agent pair
        # to detect threshold crossings. Key is ``frozenset({id_a, id_b})``
        # so each unordered pair gets exactly one entry regardless of which
        # side registered first. Stale entries (one side de-registered)
        # remain until the pair is observed again and overwrites itself;
        # WorldRuntime does not currently expose agent removal, so
        # purge-on-deregister is left to the caller that adds that hook.
        self._pair_distances: dict[frozenset[str], float] = {}
        # M7 B1: per-(agent_id, prop_id) last-seen XZ distance so
        # AffordanceEvent emits once per *entry* into a prop's salient radius,
        # not every tick the agent remains inside it. Populated lazily by
        # ``_fire_affordance_events``; entries are never purged (the table is
        # O(agents × props) and both bounds are small at MVP scale).
        self._agent_prop_distances: dict[tuple[str, str], float] = {}
        self._agents: dict[str, AgentRuntime] = {}
        self._events: list[ScheduledEvent] = []
        # TODO(T14): the unbounded queue is a deliberate MVP trade-off
        # (see decisions.md D7). When T14 wires a real WebSocket consumer,
        # switch to ``maxsize=10_000`` and add an oldest-drop / back-pressure
        # policy so a stalled client cannot grow memory without bound.
        self._envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
        self._dialog_scheduler: DialogScheduler | None = None
        # M5 orchestrator-integration: optional LLM-backed generator consulted
        # at the end of each cognition tick via ``_drive_dialog_turns``. When
        # ``None`` (e.g. unit tests that construct a bare runtime), open
        # dialogs are still admitted / timed out by the scheduler but no
        # utterances are generated — they close via the existing timeout path.
        self._dialog_generator: DialogTurnGenerator | None = None
        self._running: bool = False
        self._seq: int = 0
        # M8 L6-D3: run-level epoch state for the two-phase methodology.
        # Defaults to AUTONOMOUS so existing callers (run()) get today's
        # behaviour unchanged. Mutated only via transition_to_q_and_a() /
        # transition_to_evaluation() — direct assignment is not supported
        # (the field is addressed through a read-only property).
        self._run_lifecycle: RunLifecycleState = RunLifecycleState()

    # ----- Run lifecycle (M8) -----

    @property
    def run_lifecycle(self) -> RunLifecycleState:
        """Snapshot of the current run-level epoch state.

        Returns the live ``RunLifecycleState`` instance. Pydantic models are
        mutable by default, but callers **must not** mutate it — all state
        changes go through :meth:`transition_to_q_and_a` /
        :meth:`transition_to_evaluation` so the FSM invariants hold.
        """
        return self._run_lifecycle

    def transition_to_q_and_a(self) -> RunLifecycleState:
        """Advance the run from ``autonomous`` to ``q_and_a``.

        Raises :class:`ValueError` if the current phase is not
        :attr:`EpochPhase.AUTONOMOUS`. Replaces the lifecycle instance so
        observers that snapshotted the old value see a stable record.
        """
        current = self._run_lifecycle.epoch_phase
        if current is not EpochPhase.AUTONOMOUS:
            msg = (
                f"cannot transition to q_and_a from {current.value!r}; "
                "only autonomous → q_and_a is allowed"
            )
            raise ValueError(msg)
        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.Q_AND_A)
        return self._run_lifecycle

    def transition_to_evaluation(self) -> RunLifecycleState:
        """Advance the run from ``q_and_a`` to ``evaluation``.

        Raises :class:`ValueError` if the current phase is not
        :attr:`EpochPhase.Q_AND_A`. Direct ``autonomous → evaluation`` is
        disallowed to protect the autonomous-emergence claim (any Q&A
        interaction with the researcher must be recorded before the run
        enters offline scoring).
        """
        current = self._run_lifecycle.epoch_phase
        if current is not EpochPhase.Q_AND_A:
            msg = (
                f"cannot transition to evaluation from {current.value!r}; "
                "only q_and_a → evaluation is allowed"
            )
            raise ValueError(msg)
        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.EVALUATION)
        return self._run_lifecycle

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

    def agent_persona_id(self, agent_id: str) -> str | None:
        """Resolve ``agent_id`` to its ``persona_id``; ``None`` when unknown.

        Used by the M8 L6-D1 dialog-turn sink closure in bootstrap to stamp
        each persisted turn with both participants' persona ids (see
        ``.steering/20260425-m8-episodic-log-pipeline/decisions.md`` D2).
        Read-only — does not mutate the registry.
        """
        agent = self._agents.get(agent_id)
        return agent.state.persona_id if agent is not None else None

    def get_bond_affinity(
        self,
        agent_id: str,
        other_agent_id: str,
    ) -> float:
        """Return ``agent_id``'s current affinity toward ``other_agent_id``.

        ``0.0`` when ``agent_id`` is unknown or has no bond yet — matches
        :class:`RelationshipBond.affinity`'s default so the M7δ semi-formula's
        ``prev`` argument can be threaded through the bootstrap relational
        sink without a special "first interaction" branch. Read-only.
        """
        rt = self._agents.get(agent_id)
        if rt is None:
            return 0.0
        for bond in rt.state.relationships:
            if bond.other_agent_id == other_agent_id:
                return bond.affinity
        return 0.0

    def get_agent_zone(self, agent_id: str) -> Zone | None:
        """Return the zone of ``agent_id``'s current :class:`Position`.

        ``None`` when ``agent_id`` is unknown. Used by the M7δ bootstrap
        relational sink to stamp ``RelationshipBond.last_interaction_zone``
        with the zone the speaker spoke from. Read-only.
        """
        rt = self._agents.get(agent_id)
        if rt is None:
            return None
        return rt.state.position.zone

    def apply_affinity_delta(
        self,
        *,
        agent_id: str,
        other_agent_id: str,
        delta: float,
        tick: int,
        zone: Zone | None = None,
    ) -> None:
        """Apply an affinity ``delta`` to ``agent_id``'s bond with ``other_agent_id``.

        Mutates :attr:`AgentRuntime.state` in place via ``model_copy`` so the
        next ``AgentUpdateMsg`` snapshot picks up the new
        :class:`RelationshipBond`. When ``agent_id`` has no existing bond
        with ``other_agent_id`` a fresh bond is appended; otherwise the
        existing bond's :attr:`RelationshipBond.affinity` is updated (clamped
        through :func:`erre_sandbox.cognition.relational.apply_affinity`),
        :attr:`RelationshipBond.ichigo_ichie_count` is incremented, and
        :attr:`RelationshipBond.last_interaction_tick` is set to ``tick``.

        M7δ extensions:

        * ``zone`` — when supplied, written to
          :attr:`RelationshipBond.last_interaction_zone` so the Godot
          ``ReasoningPanel`` can render ``"<persona> affinity ±0.NN
          (N turns, last in <zone> @ tick T)"``. Default ``None`` keeps
          the field unset for callers that have not yet been migrated.
        * ``Physical.emotional_conflict`` write — negative ``delta`` past
          the M7δ trigger threshold (``< -0.05``) raises this field by
          ``abs(delta) * 0.5`` (clamped to ``[0, 1]``). Decay back to
          baseline lives in :func:`erre_sandbox.cognition.state.advance_physical`
          (per-tick ``-0.02``). Closes the dangling-read at
          ``cognition/state.py::sleep_penalty`` (R3 M4).

        Silent no-op when ``agent_id`` is not registered: the relational
        hook fires from the bootstrap turn-sink chain, which races a
        possible (M7γ-out-of-scope) deregistration. Future M9+ removal
        wiring should keep this fail-soft so a transient missing agent
        cannot crash the live runtime.
        """
        # SAFETY: single-writer assumption. The relational sink in
        # bootstrap is the sole producer of affinity-delta calls and runs
        # synchronously inside ``InMemoryDialogScheduler.record_turn``.
        # If M9 introduces parallel cognition cycles or external mutators
        # this method must guard ``rt.state.model_copy`` with an
        # ``asyncio.Lock`` to prevent lost updates (R3 H2).
        rt = self._agents.get(agent_id)
        if rt is None:
            return
        existing = list(rt.state.relationships)
        new_bonds: list[RelationshipBond] = []
        found = False
        for bond in existing:
            if bond.other_agent_id == other_agent_id:
                new_bonds.append(
                    bond.model_copy(
                        update={
                            "affinity": apply_affinity(bond.affinity, delta),
                            "ichigo_ichie_count": bond.ichigo_ichie_count + 1,
                            "last_interaction_tick": tick,
                            "last_interaction_zone": zone,
                        },
                    ),
                )
                found = True
            else:
                new_bonds.append(bond)
        if not found:
            new_bonds.append(
                RelationshipBond(
                    other_agent_id=other_agent_id,
                    affinity=apply_affinity(0.0, delta),
                    familiarity=0.0,
                    ichigo_ichie_count=1,
                    last_interaction_tick=tick,
                    last_interaction_zone=zone,
                ),
            )
        # M7δ: negative delta past the trigger threshold raises the
        # speaker / addressee's emotional_conflict so future cognition
        # cycles read the residue (sleep_penalty already consumes it).
        new_physical = rt.state.physical
        if delta < _NEGATIVE_DELTA_TRIGGER:
            bumped = min(
                1.0,
                rt.state.physical.emotional_conflict
                + abs(delta) * _EMOTIONAL_CONFLICT_GAIN,
            )
            new_physical = rt.state.physical.model_copy(
                update={"emotional_conflict": bumped},
            )
        rt.state = rt.state.model_copy(
            update={"relationships": new_bonds, "physical": new_physical},
        )

    def apply_belief_promotion(
        self,
        *,
        agent_id: str,
        other_agent_id: str,
        belief_kind: Literal["trust", "clash", "wary", "curious", "ambivalent"],
    ) -> None:
        """Stamp ``RelationshipBond.latest_belief_kind`` on a promoted dyad (M7ζ).

        Called from the bootstrap relational sink the moment
        :func:`erre_sandbox.cognition.belief.maybe_promote_belief` returns a
        non-None record, so the next ``AgentUpdateMsg`` snapshot carries the
        typed classification on the bond. Co-locating the write here (rather
        than at agent_state-export time via a semantic_memory lookup) avoids
        an extra DB read on every panel refresh; the bond IS the source of
        truth for what the Godot ``ReasoningPanel`` renders.

        Silent no-op when ``agent_id`` is not registered or the bond is
        absent: the relational sink is fire-and-forget, identical to
        :meth:`apply_affinity_delta`'s contract.

        SAFETY: same single-writer assumption as :meth:`apply_affinity_delta`
        — the bootstrap sink is the sole producer and runs synchronously.
        """
        rt = self._agents.get(agent_id)
        if rt is None:
            return
        existing = list(rt.state.relationships)
        new_bonds: list[RelationshipBond] = []
        found = False
        for bond in existing:
            if bond.other_agent_id == other_agent_id:
                new_bonds.append(
                    bond.model_copy(update={"latest_belief_kind": belief_kind}),
                )
                found = True
            else:
                new_bonds.append(bond)
        if not found:
            # Defensive: a promotion without a prior bond should never
            # happen (maybe_promote_belief reads bond fields), but if it
            # does the sink stays fail-soft rather than fabricating a bond.
            return
        rt.state = rt.state.model_copy(update={"relationships": new_bonds})

    def layout_snapshot(self, *, tick: int = 0) -> WorldLayoutMsg:
        """Construct a :class:`WorldLayoutMsg` from the static zone tables (M7γ).

        Pure read of :data:`erre_sandbox.world.zones.ZONE_CENTERS` and
        :data:`~erre_sandbox.world.zones.ZONE_PROPS` — no runtime state is
        consulted because in γ the world layout is immutable per run. The
        gateway emits this message exactly once per WS connection
        (see Slice γ Commit 3), immediately before completing the
        handshake-side ``registry.add(...)`` call.

        ``tick`` defaults to ``0`` to match the on-connect convention used
        by the ``world_layout.json`` fixture and asserted by
        ``tests/test_envelope_fixtures.py::test_shared_invariants_across_fixtures``.
        """
        zones = [
            ZoneLayout(zone=zone, x=x, y=y, z=z)
            for zone, (x, y, z) in ZONE_CENTERS.items()
        ]
        props: list[PropLayout] = [
            PropLayout(
                prop_id=spec.prop_id,
                prop_kind=spec.prop_kind,
                zone=zone,
                x=spec.x,
                y=spec.y,
                z=spec.z,
                salience=spec.salience,
            )
            for zone, prop_specs in ZONE_PROPS.items()
            for spec in prop_specs
        ]
        return WorldLayoutMsg(tick=tick, zones=zones, props=props)

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

    def inject_envelope(self, envelope: ControlEnvelope) -> None:
        """Append ``envelope`` to the fan-out queue from non-runtime code.

        Exposed for the dialog scheduler's envelope sink so it can interleave
        ``dialog_*`` messages with the cognition-generated stream without a
        second delivery path. Raw queue access stays private.
        """
        self._envelopes.put_nowait(envelope)

    def attach_dialog_scheduler(self, scheduler: DialogScheduler) -> None:
        """Install the scheduler consulted at the end of each cognition tick.

        Separated from ``__init__`` because the scheduler's envelope sink
        normally wants to call :meth:`inject_envelope` on this same runtime,
        which is awkward to arrange before the runtime exists.
        """
        self._dialog_scheduler = scheduler

    def attach_dialog_generator(self, generator: DialogTurnGenerator) -> None:
        """Install the LLM-backed :class:`DialogTurnGenerator` (M5).

        When attached, :meth:`_on_cognition_tick` walks every open dialog
        after the scheduler's proximity-auto-fire / timeout-close pass and
        either (a) closes the dialog with ``reason="exhausted"`` if the
        speaker's ``dialog_turn_budget`` is saturated, or (b) asks the
        generator for the next utterance and records/emits the resulting
        :class:`DialogTurnMsg`. ``None`` from the generator leaves the
        dialog untouched for the existing timeout path to reap.

        Last-writer-wins: re-attaching replaces the previously attached
        generator, mirroring :meth:`attach_dialog_scheduler`.
        """
        self._dialog_generator = generator

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
        # M6-A-2b: time-of-day cascade — emit a TemporalEvent for every
        # registered agent when the simulated clock crosses a period
        # boundary. No-agent ticks are hot-pathed so ``_time_start`` stays
        # None until at least one agent is registered; when agents appear
        # later their first tick sees elapsed near zero.
        if self._agents:
            self._fire_temporal_events()
        # M6-A-2b: agent-pair proximity crossings. Requires at least two
        # agents and the kinematic positions just advanced above, so this
        # runs AFTER the move loop in the same tick. Single-agent worlds
        # hot-path: no pairs, nothing to do.
        if len(self._agents) >= 2:  # noqa: PLR2004 — "pair" is inherently 2
            self._fire_proximity_events()
        # M7 B1: agent-prop affordance entries. Also needs the kinematic
        # positions just advanced above. Runs with any non-empty agent set —
        # a lone agent still notices props. Props are loaded from the static
        # ZONE_PROPS table so the loop cost is bounded by the MVP fixture
        # (two chashitsu tea bowls in the initial scope).
        if self._agents:
            self._fire_affordance_events()

    def _fire_proximity_events(self) -> None:
        """Detect agent-pair distance crossings of :data:`_PROXIMITY_THRESHOLD_M`.

        Distance is computed on the XZ plane to match
        :mod:`erre_sandbox.world.physics` (the Y axis carries avatar height,
        not a meaningful spatial separation). For each unordered pair:

        * First-time observation → cache distance, no event.
        * Crossed from ``>= threshold`` to ``< threshold`` → emit
          ``crossing="enter"`` to both agents.
        * Crossed from ``< threshold`` to ``>= threshold`` → emit
          ``crossing="leave"`` to both agents.
        * Stayed on the same side → cache update only, no event.

        Both sides of a crossing see the same ``distance_prev`` /
        ``distance_now`` values; only ``other_agent_id`` differs. This
        matches the observation stream's perspective-per-agent semantics
        (each agent gets its own view of what just happened to it).
        """
        for rt_a, rt_b in combinations(self._agents.values(), 2):
            dx = rt_a.state.position.x - rt_b.state.position.x
            dz = rt_a.state.position.z - rt_b.state.position.z
            distance = math.hypot(dx, dz)
            key = frozenset({rt_a.agent_id, rt_b.agent_id})
            prev = self._pair_distances.get(key)
            self._pair_distances[key] = distance
            if prev is None:
                # First observation: no prior tick to compare against.
                continue
            crossed_enter = (
                prev >= _PROXIMITY_THRESHOLD_M and distance < _PROXIMITY_THRESHOLD_M
            )
            crossed_leave = (
                prev < _PROXIMITY_THRESHOLD_M and distance >= _PROXIMITY_THRESHOLD_M
            )
            if not (crossed_enter or crossed_leave):
                continue
            crossing: Literal["enter", "leave"] = "enter" if crossed_enter else "leave"
            tick_a = rt_a.state.tick
            tick_b = rt_b.state.tick
            rt_a.pending.append(
                ProximityEvent(
                    tick=tick_a,
                    agent_id=rt_a.agent_id,
                    other_agent_id=rt_b.agent_id,
                    distance_prev=prev,
                    distance_now=distance,
                    crossing=crossing,
                ),
            )
            rt_b.pending.append(
                ProximityEvent(
                    tick=tick_b,
                    agent_id=rt_b.agent_id,
                    other_agent_id=rt_a.agent_id,
                    distance_prev=prev,
                    distance_now=distance,
                    crossing=crossing,
                ),
            )

    def _fire_affordance_events(self) -> None:
        """Emit :class:`AffordanceEvent` when an agent enters a prop's radius.

        Mirrors the crossing-only semantics of :meth:`_fire_proximity_events`:
        the event fires once when the XZ distance first falls below
        :data:`_AFFORDANCE_RADIUS_M`, then stays silent until the agent has
        moved back out of range and re-entered. This matches ProximityEvent's
        "edge, not level" design so chashitsu visitors do not flood the
        observation stream while sitting next to a tea bowl.

        Iterates every ``(agent, prop)`` pair in the static :data:`ZONE_PROPS`
        table. Bound at MVP scope: three agents × two chashitsu bowls = six
        distance checks per tick.
        """
        for zone, props in ZONE_PROPS.items():
            if not props:
                continue
            for rt in self._agents.values():
                ax = rt.state.position.x
                az = rt.state.position.z
                for prop in props:
                    dx = ax - prop.x
                    dz = az - prop.z
                    distance = math.hypot(dx, dz)
                    key = (rt.agent_id, prop.prop_id)
                    prev = self._agent_prop_distances.get(key)
                    self._agent_prop_distances[key] = distance
                    if prev is None:
                        # First observation: no prior tick to compare against.
                        # Do not fire on the very first frame the prop is seen,
                        # otherwise every spawn-inside-chashitsu triggers a
                        # spurious entry even when the agent never moved.
                        continue
                    crossed_enter = (
                        prev >= _AFFORDANCE_RADIUS_M and distance < _AFFORDANCE_RADIUS_M
                    )
                    if not crossed_enter:
                        continue
                    rt.pending.append(
                        AffordanceEvent(
                            tick=rt.state.tick,
                            agent_id=rt.agent_id,
                            prop_id=prop.prop_id,
                            prop_kind=prop.prop_kind,
                            zone=zone,
                            distance=distance,
                            salience=prop.salience,
                        ),
                    )

    def _fire_temporal_events(self) -> None:
        """Detect and emit TimeOfDay boundary crossings for all agents."""
        now = self._clock.monotonic()
        if self._time_start is None:
            self._time_start = now
            # Silently sync the initial period to the boot time — no event
            # on first ever tick because there is no prior period to cite.
            self._current_period = _time_of_day(0.0, self._day_duration_s)
            return
        elapsed = now - self._time_start
        new_period = _time_of_day(elapsed, self._day_duration_s)
        if new_period == self._current_period:
            return
        previous = self._current_period
        self._current_period = new_period
        for rt in self._agents.values():
            rt.pending.append(
                TemporalEvent(
                    tick=rt.state.tick,
                    agent_id=rt.agent_id,
                    period_prev=previous,
                    period_now=new_period,
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
        self._run_dialog_tick()
        if self._dialog_generator is not None and self._dialog_scheduler is not None:
            await self._drive_dialog_turns(self._current_world_tick())

    def _run_dialog_tick(self) -> None:
        """Evaluate the dialog scheduler after all per-agent cognition ran.

        The scheduler consumes a narrow projection (:class:`AgentView`) of
        each runtime so it cannot reach into kinematics or the pending
        observation buffer. Dialog envelopes are delivered through the
        scheduler's injected sink, which :func:`bootstrap` wires back to
        :meth:`inject_envelope`.
        """
        if self._dialog_scheduler is None:
            return
        views = self._agent_views()
        # The scheduler type is a Protocol frozen in schemas.py §7.5 —
        # ``tick`` is the concrete extension exposed by the default
        # :class:`InMemoryDialogScheduler`. Callers supplying a custom
        # scheduler should either subclass that class or accept that the
        # proximity auto-fire logic is skipped.
        tick_fn = getattr(self._dialog_scheduler, "tick", None)
        if tick_fn is None:
            return
        try:
            tick_fn(self._current_world_tick(), views)
        except Exception:
            # A misbehaving scheduler must not crash the cognition loop.
            logger.exception("dialog scheduler tick raised")

    def _current_world_tick(self) -> int:
        """Return the highest per-agent tick, or 0 when no agents are registered.

        Shared by ``_run_dialog_tick``, ``_drive_dialog_turns``, and
        ``_on_heartbeat_tick`` so the three consumers of "current world
        tick" always see the same value. Cheap enough to recompute each
        call (M4 target N ≤ 10 agents); if agent counts grow we could
        cache and invalidate inside ``_consume_result``.
        """
        return max((rt.state.tick for rt in self._agents.values()), default=0)

    def _agent_views(self) -> Sequence[AgentView]:
        return [
            AgentView(
                agent_id=rt.agent_id,
                zone=rt.state.position.zone,
                tick=rt.state.tick,
            )
            for rt in self._agents.values()
        ]

    async def _drive_dialog_turns(self, world_tick: int) -> None:
        """Walk every open dialog and either generate a turn or close at budget.

        Called only when both :attr:`_dialog_scheduler` and
        :attr:`_dialog_generator` are set. For each open dialog the method
        consults :meth:`InMemoryDialogScheduler.iter_open_dialogs` and:

        1. Picks the next speaker by strict alternation:
           ``turn_index % 2 == 0`` => initiator, else target. Derived from
           ``len(transcript)`` rather than a tracked counter so the scheduler
           remains the single source of truth.
        2. Closes the dialog with ``reason="exhausted"`` when
           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
        3. Otherwise dispatches the generator concurrently via
           :func:`asyncio.gather` with ``return_exceptions=True`` so one
           misbehaving pair cannot cancel the siblings. ``None`` return is a
           soft close — the existing timeout path will reap it later. An
           exception logs at ``WARNING`` and leaves the dialog untouched.
        4. On a fresh ``DialogTurnMsg`` it calls
           :meth:`InMemoryDialogScheduler.record_turn` (updates transcript and
           ``last_activity_tick``) and :meth:`inject_envelope` (fan-out to
           the WebSocket consumers). Scheduler ``record_turn`` does not emit
           on its own, so the explicit inject here is load-bearing.

        If a referenced speaker agent is not registered with this runtime
        the dialog is skipped and a warning logged — it means the runtime
        and scheduler have drifted, which is a bug in higher-layer wiring.
        """
        scheduler = self._dialog_scheduler
        generator = self._dialog_generator
        if scheduler is None or generator is None:
            return
        open_dialogs: list[tuple[str, str, str, Zone]] = list(
            scheduler.iter_open_dialogs(),
        )
        if not open_dialogs:
            return

        pending = self._stage_dialog_turns(
            scheduler=scheduler,
            generator=generator,
            open_dialogs=open_dialogs,
            world_tick=world_tick,
        )
        if not pending:
            return
        results = await asyncio.gather(
            *(p.coro for p in pending),
            return_exceptions=True,
        )
        for p, res in zip(pending, results, strict=True):
            if isinstance(res, BaseException):
                logger.warning(
                    "dialog turn generation failed for dialog %s speaker %s: %s",
                    p.dialog_id,
                    p.speaker_id,
                    res,
                )
                continue
            if res is None:
                # Soft close — leave for timeout reaper.
                continue
            if not isinstance(res, DialogTurnMsg):
                logger.warning(
                    "dialog turn generator returned unexpected type %s "
                    "for dialog %s — dropping",
                    type(res).__name__,
                    p.dialog_id,
                )
                continue
            try:
                scheduler.record_turn(res)
            except KeyError:
                # Dialog closed mid-gather (timeout / exhausted / external).
                logger.debug(
                    "dialog %s closed before turn %d could be recorded",
                    p.dialog_id,
                    p.turn_index,
                )
                continue
            self.inject_envelope(res)

    def _stage_dialog_turns(
        self,
        *,
        scheduler: DialogScheduler,
        generator: DialogTurnGenerator,
        open_dialogs: Sequence[tuple[str, str, str, Zone]],
        world_tick: int,
    ) -> list[_PendingTurn]:
        """Decide per-dialog what to do this tick: close, skip, or enqueue.

        Synchronous because every decision (budget / unknown agent / close)
        is local state. Returned pending turns are staged coroutines that
        :meth:`_drive_dialog_turns` then runs under ``asyncio.gather``.
        """
        pending: list[_PendingTurn] = []
        for did, init_id, target_id, _zone in open_dialogs:
            transcript = scheduler.transcript_of(did)
            turn_index = len(transcript)
            speaker_id = init_id if turn_index % 2 == 0 else target_id
            addressee_id = target_id if speaker_id == init_id else init_id
            speaker_rt = self._agents.get(speaker_id)
            addressee_rt = self._agents.get(addressee_id)
            if speaker_rt is None or addressee_rt is None:
                logger.warning(
                    "dialog %s references unregistered agent(s) "
                    "speaker=%s addressee=%s — skipping",
                    did,
                    speaker_id,
                    addressee_id,
                )
                continue
            budget = speaker_rt.state.cognitive.dialog_turn_budget
            if turn_index >= budget:
                try:
                    scheduler.close_dialog(did, reason="exhausted")
                except KeyError:
                    # Racy concurrent close (timeout already ran) — ignore.
                    logger.debug("dialog %s already closed before exhaust", did)
                continue
            pending.append(
                _PendingTurn(
                    dialog_id=did,
                    speaker_id=speaker_id,
                    addressee_id=addressee_id,
                    turn_index=turn_index,
                    coro=generator.generate_turn(
                        dialog_id=did,
                        speaker_state=speaker_rt.state,
                        speaker_persona=speaker_rt.persona,
                        addressee_state=addressee_rt.state,
                        transcript=transcript,
                        world_tick=world_tick,
                    ),
                ),
            )
        return pending

    async def _on_heartbeat_tick(self) -> None:
        await self._envelopes.put(
            WorldTickMsg(
                tick=self._current_world_tick(),
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
        # M6-A-2b: observations detected post-LLM (stress crossings) are
        # surfaced one tick late — append them to ``pending`` so the next
        # cognition tick sees the signal. Empty for agents whose stress
        # stayed on one side of the mid-band, which is the common case.
        if res.follow_up_observations:
            rt.pending.extend(res.follow_up_observations)
        for env in res.envelopes:
            if isinstance(env, MoveMsg):
                # Resolve a "zone-only" MoveMsg (coords unchanged from current
                # position, only zone field differs) to the target zone's spawn
                # point. CognitionCycle._build_envelopes emits this shape when
                # the LLM returns a destination_zone, relying on the world
                # layer to map semantic zone -> physical coordinates. Without
                # this resolution, step_kinematics would see dest == position,
                # mark "arrived immediately", and never cross a zone boundary
                # -> pending observations stay empty -> episodic_memory never
                # populates (GAP-1 blocker for MASTER-PLAN §4.4 #3).
                tgt = env.target
                if locate_zone(tgt.x, tgt.y, tgt.z) is not tgt.zone:
                    resolved = default_spawn(tgt.zone).model_copy(
                        update={"yaw": tgt.yaw, "pitch": tgt.pitch},
                    )
                    env = env.model_copy(update={"target": resolved})  # noqa: PLW2901 — intentional re-bind to propagate the zone-resolved target to both apply_move_command and the downstream queue
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
