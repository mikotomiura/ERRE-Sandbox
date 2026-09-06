"""M13 society live-closure composition root — Issue 002 (router部のみ, construction).

FROZEN ADR ``.steering/20260906-m13-society-live-closure/design-final.md``
(§4 Allowed Files / §5 決定論 / §2 honest framing) +
``.steering/20260906-m13-society-live-closure/decisions.md`` (Codex M-1/M-2).
This is the closure-only composition root for the N-agent (society) live
wiring — a sibling of ``integration/embodied/live_loop.py``'s single-agent
closure root, generalised to the fixed 3-agent roster
``society_live.SOCIETY_LIVE_AGENT_IDS``. Issue 002 lands only the two pieces
that do not depend on a running ``run_society_loop`` drive:

* :class:`SocietyInboundRouter` — the ``InboundSink`` -> per-agent
  ``observation_factories`` bridge ``society.py::run_society_loop`` accepts
  **unmodified** (``society.py`` is not touched by this issue at all: the
  router only produces the ``Mapping[str, Callable[[int], Sequence[
  Observation]]]`` shape that public kwarg already takes).
* :func:`society_live_loop_perturbation_plan` — the N-agent generalisation
  of ``scripts.m13_live_loop_capture.live_loop_perturbation_plan``.

**Issue 003 (this module's second addition)** lands the closure root proper:

* :class:`SocietyLiveWorldInput` / :func:`build_society_live_world` — a
  **frozen input bundle**, never a second :class:`~erre_sandbox.world.WorldRuntime`
  construction site (ADR §1, binding: "駆動ループを二本のままにせず一本にする").
  It reuses ``society_live.py``'s fixed constructors
  (:func:`~erre_sandbox.integration.embodied.society_live.society_live_agent_states`
  / :func:`~erre_sandbox.integration.embodied.society_live.society_live_personas`)
  and reproduces (never calls) ``run_society_live_capture``'s
  ``RecordReplayChatClient(inner=ThinkOffChatClient(...))`` wrapping, because
  that function does not forward the two new ``run_society_loop`` kwargs
  (``two_phase_knob`` / ``on_runtime_ready``, Issue 001) this closure root
  needs.
* :func:`run_society_live_loop` — drives ``run_society_loop`` directly
  (knob-on + ``self_other_enabled=True`` + the router's
  ``observation_factories``), returning a :class:`SocietyLiveRunResult` that
  bundles the run's
  :class:`~erre_sandbox.integration.embodied.society.SocietyRunResult`,
  the router's final :class:`SocietyInboundLedger`, and the **exact**
  :class:`~erre_sandbox.world.WorldRuntime` instance ``on_runtime_ready``
  received (never a second one).
* :func:`supervise_society_live_loop` — same-event-loop
  ``asyncio.TaskGroup`` supervision of gateway serve + drive, mirroring
  :func:`~erre_sandbox.integration.embodied.live_loop.supervise_live_loop`
  (module docstring below explains the one deliberate shape deviation this
  module's late runtime-discovery forces: ``gateway_serve`` takes the
  constructed :class:`~fastapi.FastAPI` app, it is not zero-arg).

**Issue 004 (this module's third addition)** lands the two construction
witnesses (design-final.md §6 W-N1 / W-N3), all boolean/count, ``verdict``
explicitly ``None``:

* :class:`SocietyBroadcastLedger` — the **consume-side** record of what the
  gateway actually fanned out (Codex **H-2**: a post-hoc
  ``WorldRuntime.drain_envelopes()`` observation races the gateway's own
  ``_broadcaster``, which consumes the very same queue via
  ``recv_envelope()``, so it must not be used). ``gateway.py`` stays
  **unmodified**: the ledger registers its own unbounded outbound queue
  through the public :meth:`~erre_sandbox.integration.gateway.Registry.
  reserve_slot` seam, so what it records is exactly what
  ``Registry.fan_out`` delivered.
* :func:`society_live_gateway_lifespan_serve` — a ``gateway_serve`` callable
  that actually runs the app's lifespan (hence its ``_broadcaster`` task),
  so the consume side is genuinely driven rather than simulated.
* :func:`spy_inject_envelope_callers` — the ``inject_envelope`` single-owner
  spy (design-final.md §6 W-N3 third bullet).
* :func:`society_wiring_reachability_summary` — the pure witness itself.

**Honest framing (binding, design-final.md §2)**: this is *wiring* /
*construction*, never aha / emergence / effect. Neither piece below imports
``evidence`` / ``spdm`` / ``runningness`` machinery, and neither
computes/emits a floor / landscape / verdict / divergence / magnitude /
detectability / aha-proxy statistic. "N 体が live で相互作用した" would be a
**boolean wiring-reachability claim**, never a social-emergence claim — this
issue does not even reach that witness (I4); it only builds the plumbing a
later witness will read.

**Not a wall-clock real-time session (design-final.md §5, binding)**:
:func:`run_society_live_loop` drives ``run_society_loop``, which internally
uses its own ``ManualClock(start=0.0)`` — this module never substitutes a
``RealClock``. A live-driven session built here replays a **scripted
in-process perturbation sequence** through that manual clock; it is not
listening for real WebSocket arrival times or real LLM latency. Byte-parity
(a later issue's Plane G) is scoped to that scripted sequence only.

**Codex M-1 (idempotent drain coordinator)**: ``run_society_loop`` calls
every registered agent's ``observation_factories[agent_id](cognition_tick)``
once per window, in ``sorted(agent_ids)`` order
(``society.py`` — ``for agent_id in sorted_agent_ids: for obs in
obs_factories[agent_id](cognition_tick): ...``). Whichever per-agent factory
happens to run first for a given window would, naively, be the one that
actually drains the shared ``InboundSink`` — a hidden ordering dependency.
:meth:`SocietyInboundRouter.begin_window` removes that dependency: it is
idempotent per ``tick`` (drains at most once no matter how many factories,
or how many times the same factory, call it for the same tick), so every
per-agent factory can safely call it unconditionally and then just read its
own bucket.

**Codex M-2 (5-way ledger)**: :attr:`SocietyInboundRouter.ledger` snapshots
the router's whole inbound lifecycle as five partitions — ``pushed`` /
``dropped`` / ``drained`` / ``injected`` / ``rejected`` — so a caller can
tell *where* every message that ever reached the sink ended up. The
reachability population for a later witness (I4) is **injected only**:
an unknown-target message is counted in ``rejected``, never ``injected``;
an overflow-evicted message is counted in ``dropped`` (via
``InboundSink.dropped``), never ``injected``.

**correlation-id / wall_clock (design-final.md §5 table)**:
``integration/inbound.py`` (**imported and used, never modified**) maps a
:class:`~erre_sandbox.schemas.WorldPerturbationMsg` to a
:class:`~erre_sandbox.schemas.PerceptionEvent` via a pure function whose
returned ``wall_clock`` defaults to ``_utc_now()`` — real, non-deterministic
wall-clock time. The router pins that field to
:data:`RECORD_MODE_WALL_CLOCK` immediately after calling the unmodified
mapping (never inside ``inbound.py`` itself), the same record-mode
convention every sibling live-closure driver already applies to its
in-process-synthesised fields (``live_loop_perturbation_plan``'s
``sent_at`` pin, ``society_live._SEALED_WALL_CLOCK``,
``handoff.GOLDEN_TS``).

Layer dependency (``architecture-rules`` skill): ``integration/`` may import
``schemas`` / ``contracts`` / ``inference`` / ``memory`` / ``cognition`` /
``world`` — this module only needs ``schemas`` plus two sibling
``integration.embodied`` / ``integration`` modules (same layer, import-only,
neither is modified).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from collections import Counter
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, cast

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.society import run_society_loop
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    society_live_agent_states,
    society_live_personas,
)
from erre_sandbox.integration.gateway import make_app
from erre_sandbox.integration.inbound import (
    InboundSink,
    world_perturbation_to_perception,
)
from erre_sandbox.schemas import ControlEnvelope, WorldPerturbationMsg, Zone
from erre_sandbox.world import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterator, Mapping, Sequence

    from fastapi import FastAPI

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.erre.two_phase import TwoPhaseKnob
    from erre_sandbox.integration.embodied.society import SocietyRunResult
    from erre_sandbox.integration.gateway import Registry
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import (
        AgentState,
        Observation,
        PerceptionEvent,
        PersonaSpec,
    )

# --------------------------------------------------------------------------- #
# Determinism pin (design-final.md §5, binding)
# --------------------------------------------------------------------------- #

RECORD_MODE_WALL_CLOCK: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed wall-clock value this module pins onto every inbound-sourced
``PerceptionEvent.wall_clock`` (:meth:`SocietyInboundRouter` factories) and
every perturbation-plan message's ``sent_at``
(:func:`society_live_loop_perturbation_plan`).

Same value as ``integration.embodied.society_live._SEALED_WALL_CLOCK``
(private, so not importable) and ``integration.embodied.handoff.GOLDEN_TS``
(design-final.md §5: "``handoff.GOLDEN_TS`` を import するか 本モジュール自身
の ``Final`` 定数として同値を定義し" — the either/or this module resolves by
defining its own constant, avoiding a real-code dependency on the
golden-rendering module for a single datetime literal).

Both pinned fields would otherwise be non-deterministic real time
(``PerceptionEvent.wall_clock`` is ``Field(default_factory=_utc_now)`` in
``schemas.py``; a perturbation plan built in-process — never received over
a wire — would otherwise stamp ``sent_at`` at build time). Pinning both to
this single frozen value keeps a society-scope live drive byte-parity
replayable, the same discipline every sibling live-closure driver already
applies (``live_loop_perturbation_plan``'s ``sent_at`` pin,
``scripts/m13_live_loop_capture.py``)."""

DEFAULT_MAX_DRAIN_PER_TICK: Final[int] = 8
"""Bounded per-window inbound drain (mirrors ``live_loop.py``'s
``DEFAULT_MAX_DRAIN_PER_TICK`` — same value, same rationale, declared
locally rather than imported so this module's construction surface stays
self-contained): at most this many queued ``WorldPerturbationMsg`` are
drained in a single :meth:`SocietyInboundRouter.begin_window` call, so one
abusive/burst inbound sender cannot make a single window's bucket-fill
unbounded. Excess messages simply wait in the sink for the next window's
drain (FIFO order preserved by ``InboundSink.drain``)."""


# --------------------------------------------------------------------------- #
# Ledger shapes (Codex M-2 — 5-way split; primary source for I4 / I6)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyInjectedPerturbation:
    """One inbound perturbation actually routed into one agent's observation window.

    Mirrors ``integration.embodied.live_loop.InjectedPerturbation``'s shape
    (``agent_tick`` / ``correlation_id`` / ``msg`` / ``observation``) for the
    N-agent router — a later reachability witness (I4) and Plane G's
    ``ledger_observation_factories`` replay (I6) both read this tuple as
    their one primary-source record of "which ``WorldPerturbationMsg``
    became which :class:`~erre_sandbox.schemas.PerceptionEvent`, injected
    into which agent's tick" — so its shape is fixed here rather than
    re-derived downstream.

    ``routed_agent_id`` (Issue 004) records **which agent's bucket the
    router actually pulled this message out of**, which is NOT recoverable
    from the other three fields: ``world_perturbation_to_perception`` sets
    ``PerceptionEvent.agent_id`` from ``msg.target_agent_id`` unconditionally
    (``inbound.py``, unmodified), so a router that mis-bucketed a message
    into the wrong agent's window would still produce an observation naming
    the *intended* agent. Without this field a "did it reach the agent it
    was aimed at" witness would compare a value against itself. With it,
    :func:`society_wiring_reachability_summary`'s ``target_agent_routing``
    seam is a genuine check of the N-agent routing step (AC1).
    """

    agent_tick: int
    correlation_id: str
    msg: WorldPerturbationMsg
    observation: PerceptionEvent
    routed_agent_id: str


@dataclass(frozen=True, slots=True)
class SocietyInboundLedger:
    """Snapshot of the router's 5-way inbound lifecycle split (Codex M-2).

    ``dropped`` / ``drained`` / ``injected`` / ``rejected`` are the four
    partitions the router itself can observe directly; ``pushed`` is a
    derived total (see its property docstring) — ``InboundSink`` exposes no
    raw push counter of its own (only ``.dropped``, the overflow-eviction
    count), so "how many messages entered the pipeline" has to be
    reconstructed from what this router can actually observe: what was
    evicted before ever being drained, plus what it itself drained.

    The reachability population for a later witness (I4, design-final.md
    §6 W-N1) is **``injected`` only** — ``dropped`` and ``rejected`` are
    explicitly excluded (Codex M-2): an overflow-evicted message never
    became an ``injected`` entry (it was gone before ``begin_window`` ever
    drained it), and an unknown-target message never became one either (it
    was routed to ``rejected`` instead of a bucket).
    """

    dropped: int
    drained: tuple[WorldPerturbationMsg, ...]
    injected: tuple[SocietyInjectedPerturbation, ...]
    rejected: tuple[WorldPerturbationMsg, ...]

    @property
    def pushed(self) -> int:
        """``dropped`` (evicted before draining) + ``len(drained)``.

        Exact whenever nothing pushed onto the sink remains queued
        unclaimed at snapshot time (true once every push this router has
        seen has been resolved one way or the other — evicted or drained);
        an honest lower bound otherwise (messages still queued, not yet
        drained, are not double-counted as "pushed" until they resolve).
        """
        return self.dropped + len(self.drained)

    @property
    def injected_correlation_ids(self) -> frozenset[str]:
        """The set of correlation-ids that reached ``injected``.

        A negative check (a dropped or rejected id must NOT appear here)
        reads this directly instead of scanning :attr:`injected` itself.
        """
        return frozenset(inj.correlation_id for inj in self.injected)


# --------------------------------------------------------------------------- #
# SocietyInboundRouter (Codex M-1 — idempotent-per-window drain coordinator)
# --------------------------------------------------------------------------- #


class SocietyInboundRouter:
    """Bounded, idempotent-per-window ``InboundSink`` -> per-agent bucket router.

    Bridges the shared inbound face (one :class:`~erre_sandbox.integration.
    inbound.InboundSink` a gateway would push every parsed
    :class:`~erre_sandbox.schemas.WorldPerturbationMsg` into) to
    ``society.py::run_society_loop``'s existing public ``observation_factories``
    kwarg (``Mapping[str, Callable[[int], Sequence[Observation]]]``) — no
    change to ``society.py`` is needed because that kwarg already exists
    (Issue 001's superseding-ADR predecessor left it untouched; this router
    is simply a caller-supplied implementation of the shape it expects).

    Usage shape (a later issue wires this into the closure root):

    >>> router = SocietyInboundRouter(sink, agent_ids=SOCIETY_LIVE_AGENT_IDS)
    >>> factories = router.observation_factories(SOCIETY_LIVE_AGENT_IDS)
    >>> # factories handed straight to run_society_loop(observation_factories=...)

    **Idempotent drain (Codex M-1)**: :meth:`begin_window` may be called any
    number of times for the same ``tick`` — only the first call actually
    drains the sink; every subsequent call for that same ``tick`` is a
    no-op. This is what lets every per-agent factory call
    ``begin_window(tick)`` unconditionally at the top of its own body
    without caring whether it happens to be first or last in
    ``society.py``'s ``sorted_agent_ids`` iteration order for that window.

    **Registered vs. unregistered targets**: the set of agent ids passed to
    the constructor is this router's registry. A drained message whose
    ``target_agent_id`` is NOT in that registry is never bucketed — it is
    recorded onto :attr:`ledger`'s ``rejected`` partition and never becomes
    a :class:`SocietyInjectedPerturbation` (AC3).

    **FIFO (AC7)**: push order into the sink == drain order (``InboundSink.
    drain`` itself is FIFO) == the order messages land in a bucket == the
    order a factory call returns them, because every step here is a plain
    ordered append/iterate — no sorting or re-keying by anything other than
    arrival order.
    """

    def __init__(
        self,
        sink: InboundSink,
        *,
        agent_ids: Sequence[str],
        max_drain_per_tick: int = DEFAULT_MAX_DRAIN_PER_TICK,
    ) -> None:
        self._sink = sink
        self._registered_agent_ids: frozenset[str] = frozenset(agent_ids)
        self._max_drain_per_tick = max_drain_per_tick
        self._last_begun_tick: int | None = None
        self._buckets: dict[str, list[WorldPerturbationMsg]] = {
            agent_id: [] for agent_id in self._registered_agent_ids
        }
        self._drained: list[WorldPerturbationMsg] = []
        self._injected: list[SocietyInjectedPerturbation] = []
        self._rejected: list[WorldPerturbationMsg] = []

    def begin_window(self, tick: int) -> None:
        """Drain the sink for ``tick``, exactly once (Codex M-1, AC1).

        A second (or third, ...) call with the SAME ``tick`` is a no-op —
        this is what makes it safe for every per-agent
        ``observation_factories`` closure to call this unconditionally
        rather than relying on "whichever factory the driver happens to
        call first this window". The guard is a plain ``tick`` equality
        check against the last ``tick`` this method actually drained for —
        it assumes (as every existing sibling driver does) that a caller
        drives ``tick`` non-decreasingly across a single session; re-using
        an already-drained ``tick`` value out of order is outside this
        router's supported contract.

        Every drained message is appended to the cumulative ``drained``
        ledger (FIFO, AC7) and bucketed by ``target_agent_id`` — a
        registered target's bucket gets the message appended; an
        unregistered target's message goes straight to ``rejected`` instead
        (AC3) and is never bucketed.
        """
        if self._last_begun_tick == tick:
            return
        self._last_begun_tick = tick
        for msg in self._sink.drain(self._max_drain_per_tick):
            self._drained.append(msg)
            if msg.target_agent_id in self._registered_agent_ids:
                self._buckets.setdefault(msg.target_agent_id, []).append(msg)
            else:
                self._rejected.append(msg)

    def observation_factories(
        self,
        agent_ids: Sequence[str],
    ) -> Mapping[str, Callable[[int], Sequence[Observation]]]:
        """Build the ``{agent_id: factory}`` mapping ``run_society_loop`` wants.

        Each returned factory, when called with ``society.py``'s current
        ``cognition_tick``: calls :meth:`begin_window` (idempotent, so it
        never matters whether this is the first or last factory the driver
        calls this window), then reads and clears its OWN agent's bucket
        only (AC2 — a message aimed at some other agent is simply absent
        from this factory's return value; it was never appended to this
        agent's bucket in the first place).

        ``agent_ids`` need not equal the constructor's registered set
        exactly — an id absent from the registry simply gets a factory
        whose bucket is always empty (nothing is ever routed to it, since
        an unregistered target's messages go to ``rejected`` instead), a
        harmless no-op rather than an error.
        """
        return {agent_id: self._make_factory(agent_id) for agent_id in agent_ids}

    def _make_factory(
        self,
        agent_id: str,
    ) -> Callable[[int], Sequence[Observation]]:
        def factory(tick: int) -> Sequence[Observation]:
            self.begin_window(tick)
            bucket = self._buckets.get(agent_id, [])
            self._buckets[agent_id] = []
            observations: list[PerceptionEvent] = []
            for msg in bucket:
                # inbound.py's pure mapping is used unmodified; only the
                # returned wall_clock (real-time default_factory) is pinned
                # here, on the router side (design-final.md §5 table).
                observation = world_perturbation_to_perception(
                    msg, tick=tick
                ).model_copy(update={"wall_clock": RECORD_MODE_WALL_CLOCK})
                self._injected.append(
                    SocietyInjectedPerturbation(
                        agent_tick=tick,
                        correlation_id=msg.correlation_id,
                        msg=msg,
                        observation=observation,
                        # The bucket this factory owns -- i.e. the agent whose
                        # window actually receives the observation, which a
                        # mis-bucketing router would make differ from
                        # msg.target_agent_id (Issue 004 AC1).
                        routed_agent_id=agent_id,
                    )
                )
                observations.append(observation)
            return tuple(observations)

        return factory

    @property
    def ledger(self) -> SocietyInboundLedger:
        """A fresh, immutable snapshot of the router's 5-way lifecycle split.

        ``dropped`` is read live off ``InboundSink.dropped`` at snapshot
        time (the sink's own overflow-eviction counter); the other three
        partitions are copies of this router's own accumulated lists.
        """
        return SocietyInboundLedger(
            dropped=self._sink.dropped,
            drained=tuple(self._drained),
            injected=tuple(self._injected),
            rejected=tuple(self._rejected),
        )


# --------------------------------------------------------------------------- #
# Perturbation plan builder (pure function, N-agent generalisation)
# --------------------------------------------------------------------------- #

_PERTURBATION_ZONES: Final[tuple[Zone, ...]] = (
    Zone.STUDY,
    Zone.PERIPATOS,
    Zone.CHASHITSU,
    Zone.AGORA,
    Zone.GARDEN,
)
_PERTURBATION_MODALITY: Final[str] = "sight"
_PERTURBATION_INTENSITY: Final[float] = 0.4
_PERTURBATION_TEMPLATE: Final[str] = (
    "society live-loop stimulus window {window}: movement and light from "
    "the {zone}, aimed at {agent_id}"
)


def society_live_loop_perturbation_plan(
    *,
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
    n_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    sent_at: datetime = RECORD_MODE_WALL_CLOCK,
) -> tuple[WorldPerturbationMsg, ...]:
    """Build the frozen bounded N-agent stimulus sequence (one per agent per window).

    The N-agent generalisation of
    ``scripts.m13_live_loop_capture.live_loop_perturbation_plan``: instead
    of one message per cognition tick for a single agent, this builds one
    message per ``(agent_id, window)`` pair, in window-major / agent-minor
    order — so ``len(plan) == len(agent_ids) * n_ticks``, the sealed
    default (``SOCIETY_LIVE_AGENT_IDS`` x ``SOCIETY_LIVE_N_COGNITION_TICKS``
    = 3 x 12 = 36 messages, design-final.md grill G1).

    A pure function of ``(agent_ids, n_ticks, sent_at)`` and this module's
    frozen zone/modality/intensity/template constants — never of a run
    outcome — so the plan is fixed before any sealed run and a re-bake
    reproduces it byte-for-byte (AC6). Each message is a *world stimulus*
    (design-final.md DA-2 semantics, inherited from the parent ADR): it
    carries no knob / mode / destination override, so it cannot bypass the
    cognition loop. ``source_zone`` cycles the five zones deterministically
    per ``(window, agent_index)``; ``modality`` / ``intensity`` are
    constant across every message, so the only things varying are the
    stimulus text, its origin zone, and its ``target_agent_id`` /
    ``correlation_id``.

    ``sent_at`` is pinned to :data:`RECORD_MODE_WALL_CLOCK` rather than
    left to ``_EnvelopeBase``'s ``default_factory=_utc_now`` — this plan is
    synthesised **in-process**, never received over a wire, so a real
    send-time would be pure non-determinism in a committed artifact
    (mirrors ``live_loop_perturbation_plan``'s own ``sent_at`` pin
    rationale). Nothing downstream reads it: ``sent_at`` is not one of the
    fields ``world_perturbation_to_perception`` copies onto the resulting
    ``PerceptionEvent``, so this pin only touches the ledger's bytes, never
    cognition or geometry.

    The stimulus is scripted; a model's *response* to it (a later issue's
    concern, out of scope here) would not be. That distinction is the
    honest one this plan's docstring inherits from its N=1 precedent: an
    unscripted response to a pre-registered stimulus is not an emergent or
    self-chosen behaviour.
    """
    plan: list[WorldPerturbationMsg] = []
    for window in range(n_ticks):
        for agent_index, agent_id in enumerate(agent_ids):
            zone = _PERTURBATION_ZONES[
                (window + agent_index) % len(_PERTURBATION_ZONES)
            ]
            plan.append(
                WorldPerturbationMsg(
                    tick=0,
                    sent_at=sent_at,
                    target_agent_id=agent_id,
                    modality=cast("Any", _PERTURBATION_MODALITY),
                    source_zone=zone,
                    content=_PERTURBATION_TEMPLATE.format(
                        window=window, zone=zone.value, agent_id=agent_id
                    ),
                    intensity=_PERTURBATION_INTENSITY,
                    correlation_id=f"wp-slc-{window:03d}-{agent_id}",
                )
            )
    return tuple(plan)


# --------------------------------------------------------------------------- #
# Issue 003 — closure root proper (construction, no second WorldRuntime)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyLiveWorldInput:
    """Frozen input bundle for a society live-closure drive (construction only).

    **NOT a second world/cycle construction site (ADR §1, binding)**: unlike
    :func:`~erre_sandbox.integration.embodied.live_loop.build_live_loop_world`
    (which builds a knob-on ``CognitionCycle`` + ``WorldRuntime`` itself), this
    bundle carries only the *inputs* :func:`run_society_live_loop` hands
    straight through to ``run_society_loop`` — the actual
    :class:`~erre_sandbox.world.WorldRuntime` /
    :class:`~erre_sandbox.cognition.CognitionCycle` construction stays
    exclusively inside ``run_society_loop`` itself (society.py:1330-1401),
    surfaced to a caller solely via ``on_runtime_ready`` (AC6: the runtime a
    caller ever sees is the ONE ``run_society_loop`` built, never a second
    instance this module constructs in parallel).

    ``router`` / ``inbound_sink`` are two views onto the SAME inbound face:
    ``router.observation_factories(...)`` is what reaches
    ``run_society_loop``'s ``observation_factories`` kwarg;
    ``inbound_sink`` is the identical object a gateway's ``make_app`` needs
    (:func:`supervise_society_live_loop`) so a WS client and the router drain
    the same queue — never two independently-fed sinks.
    """

    agent_states: tuple[AgentState, ...]
    personas: dict[str, PersonaSpec]
    store: MemoryStore
    embedding: EmbeddingClient
    llms: dict[str, RecordReplayChatClient]
    router: SocietyInboundRouter
    knob: TwoPhaseKnob | None
    inbound_sink: InboundSink


def build_society_live_world(
    *,
    inner_chats: Mapping[str, Any],
    store: MemoryStore,
    embedding: EmbeddingClient,
    inbound_sink: InboundSink,
    knob: TwoPhaseKnob | None = None,
    agent_states: Sequence[AgentState] | None = None,
    personas: Mapping[str, PersonaSpec] | None = None,
    max_drain_per_tick: int = DEFAULT_MAX_DRAIN_PER_TICK,
) -> SocietyLiveWorldInput:
    """Construct the frozen input bundle (never a ``WorldRuntime``, ADR §1).

    ``agent_states`` / ``personas`` default to ``society_live.py``'s fixed
    3-agent roster
    (:func:`~erre_sandbox.integration.embodied.society_live.society_live_agent_states`
    / :func:`~erre_sandbox.integration.embodied.society_live.society_live_personas`,
    **reused, ``society_live.py`` itself unmodified**) — the sealed N=3
    default (design-final.md grill G1) — but accept an override so a test can
    exercise a smaller roster.

    ``llms`` reproduces (never calls)
    :func:`~erre_sandbox.integration.embodied.society_live.run_society_live_capture`'s
    own ``RecordReplayChatClient(inner=ThinkOffChatClient(inner_chats[agent_id]))``
    wrapping field-for-field: that function cannot be called here because it
    does not forward ``two_phase_knob`` / ``on_runtime_ready`` (Issue 001) to
    ``run_society_loop`` — only the wrapping *shape* is reused, by explicit
    construction, not by import of that function.

    ``router`` is a fresh :class:`SocietyInboundRouter` bound to the SAME
    ``inbound_sink`` this bundle also carries verbatim, so
    :func:`supervise_society_live_loop` can hand that identical sink to
    ``make_app`` — one inbound face, never two independently-drained queues.
    """
    states = (
        tuple(agent_states)
        if agent_states is not None
        else tuple(society_live_agent_states())
    )
    persona_map = dict(personas) if personas is not None else society_live_personas()
    agent_ids = tuple(state.agent_id for state in states)
    llms: dict[str, RecordReplayChatClient] = {
        agent_id: RecordReplayChatClient(
            inner=ThinkOffChatClient(inner_chats[agent_id])
        )
        for agent_id in agent_ids
    }
    router = SocietyInboundRouter(
        inbound_sink, agent_ids=agent_ids, max_drain_per_tick=max_drain_per_tick
    )
    return SocietyLiveWorldInput(
        agent_states=states,
        personas=persona_map,
        store=store,
        embedding=embedding,
        llms=llms,
        router=router,
        knob=knob,
        inbound_sink=inbound_sink,
    )


@dataclass(frozen=True, slots=True)
class SocietyLiveRunResult:
    """One :func:`run_society_live_loop` drive's outcome.

    ``verdict`` is deliberately absent (design-final.md §2/§6): this is a
    construction result, not a measurement one. ``runtime`` is the **exact**
    :class:`~erre_sandbox.world.WorldRuntime` instance
    ``run_society_loop`` constructed and handed to ``on_runtime_ready`` — the
    same object a caller's gateway wiring received (AC6's single-instance
    witness reads this field directly against whatever a gateway app's
    ``.state.runtime`` holds).
    """

    result: SocietyRunResult
    ledger: SocietyInboundLedger
    runtime: WorldRuntime


async def run_society_live_loop(
    world: SocietyLiveWorldInput,
    *,
    run_id: str,
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    on_runtime_ready: Callable[[WorldRuntime], Awaitable[None] | None] | None = None,
) -> SocietyLiveRunResult:
    """Drive ``world`` through ``run_society_loop`` unmodified (the ADR §1 core).

    Knob-on (``world.knob`` threaded straight through) + ``self_other_enabled=
    True`` (mirror wiring reaches live prompts, ADR §1) + the router's
    ``observation_factories`` (inbound reaches per-agent windows,
    ``society.py`` unmodified) — ``run_society_loop`` itself IS this drive's
    scheduler; this function adds no scheduling of its own.

    ``on_runtime_ready`` (optional, forwarded): this function ALWAYS installs
    its own internal hook (never leaves ``run_society_loop``'s hook slot
    empty) so it can capture the SAME ``WorldRuntime`` instance for its own
    return value (``SocietyLiveRunResult.runtime``, AC6) — a caller-supplied
    ``on_runtime_ready`` (e.g. :func:`supervise_society_live_loop`'s gateway
    wiring) is invoked from inside that internal hook, honouring the same
    sync-or-awaitable calling convention ``run_society_loop`` itself defines
    (``society.py``'s own ``_invoke_runtime_ready_hook``), so a caller cannot
    tell this function's own bookkeeping apart from a direct
    ``run_society_loop`` call from the hook's point of view.
    """
    agent_ids = tuple(state.agent_id for state in world.agent_states)
    runtime_box: list[WorldRuntime] = []

    async def _hook(runtime: WorldRuntime) -> None:
        # Construction exposure only (Codex M-5): read/capture, never mutate.
        runtime_box.append(runtime)
        if on_runtime_ready is None:
            return
        maybe_awaitable = on_runtime_ready(runtime)
        if isinstance(maybe_awaitable, Awaitable):
            await maybe_awaitable

    result = await run_society_loop(
        run_id=run_id,
        store=world.store,
        embedding=world.embedding,
        llms=world.llms,
        agent_states=world.agent_states,
        personas=world.personas,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        k_ecl=k_ecl,
        reflector=reflector,
        observation_factories=world.router.observation_factories(agent_ids),
        self_other_enabled=True,
        two_phase_knob=world.knob,
        on_runtime_ready=_hook,
    )
    if (
        not runtime_box
    ):  # pragma: no cover — defensive; run_society_loop always calls its hook
        msg = "run_society_loop returned without ever invoking on_runtime_ready"
        raise RuntimeError(msg)
    return SocietyLiveRunResult(
        result=result,
        ledger=world.router.ledger,
        runtime=runtime_box[0],
    )


# --------------------------------------------------------------------------- #
# Issue 004 — consume-side outbound ledger (Codex H-2: never a post-hoc
# ``WorldRuntime.drain_envelopes()`` observation, which races the gateway's
# own ``_broadcaster`` over the very same queue)
# --------------------------------------------------------------------------- #

COGNITION_ENVELOPE_KINDS: Final[frozenset[str]] = frozenset(
    {"agent_update", "animation", "move", "speech"}
)
"""The ONLY envelope kinds :func:`society_wiring_reachability_summary` gates on
(design-final.md §6 W-N3, Codex H-3).

These four are exactly the kinds ``WorldRuntime._consume_result`` enqueues from
a cognition step's ``CycleResult.envelopes`` — i.e. the ones whose *enqueue
side* can be reconstructed offline from
``SocietyRunResult.decisions[*].envelope_provenance`` with no re-drive."""

DIALOG_ENVELOPE_KINDS: Final[tuple[str, ...]] = (
    "dialog_initiate",
    "dialog_turn",
    "dialog_close",
)
"""Counted as a plain annotation, **never gated** (Codex H-3).

``run_society_loop`` wires ``InMemoryDialogScheduler(envelope_sink=world.
inject_envelope)`` internally (``society.py``), so the dialog stream is a
second, entirely legitimate producer on the same broadcast queue whose enqueue
side this module cannot reconstruct: wrapping that sink would need a third
additive ``run_society_loop`` kwarg, which the FROZEN ADR explicitly defers
(``decisions.md`` H-3 — the full version, ``dialog_envelope_sink``, is a
separate ADR). Gating on a multiset whose enqueue side is unobservable would
produce a witness that fails for a reason unrelated to the property it claims
to check, so these kinds are reported as counts and excluded from the gate."""

EXCLUDED_ENVELOPE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "handshake",
        "world_tick",
        "world_layout",
        "error",
        "reasoning_trace",
        "reflection_event",
        *DIALOG_ENVELOPE_KINDS,
    }
)
"""Every ``ControlEnvelope.kind`` deliberately outside the ``no_double_send``
gate, named explicitly rather than left implicit (Codex H-2's "``heartbeat`` /
``world_tick`` / ``error`` は除外集合として明記" requirement).

Reasons, kind by kind: ``handshake`` / ``world_layout`` are server-originated
per-session frames the gateway emits directly (never through the runtime's
broadcast queue); ``world_tick`` is the periodic liveness **heartbeat**
(``WorldRuntime._on_heartbeat_tick`` emits it onto the coalescing,
latest-wins heartbeat queue, so its multiset is deliberately lossy);
``error`` is a session-wide utility frame (``Registry.fan_out`` itself can
synthesise a ``backlog_overflow`` one); ``reasoning_trace`` /
``reflection_event`` are diagnostic streams no cognition step enqueues here;
``dialog_*`` is the Codex H-3 case documented on
:data:`DIALOG_ENVELOPE_KINDS`."""

DEFAULT_QUIESCE_STABLE_ROUNDS: Final[int] = 32
"""Consecutive no-growth event-loop yields :meth:`SocietyBroadcastLedger.quiesce`
requires before declaring the consume side settled.

One envelope costs the broadcaster several loop iterations (``recv_envelope``
creates two getter tasks and ``asyncio.wait``s on them), so a single yield is
not enough to conclude "nothing more is in flight". 32 is generous relative to
that cost and costs nothing measurable: an event-loop yield with no pending I/O
is a bare ``call_soon`` round-trip."""

DEFAULT_QUIESCE_MAX_ROUNDS: Final[int] = 100_000
"""Hard upper bound on :meth:`SocietyBroadcastLedger.quiesce` yields, so a
never-settling producer surfaces as a bounded return value instead of hanging
the supervisor forever."""


class _RecordingQueue(asyncio.Queue[ControlEnvelope]):
    """Unbounded outbound session queue that records every fan-out push.

    ``maxsize`` is deliberately 0 (unbounded): ``Registry.fan_out`` only takes
    its drop-oldest + synthetic ``backlog_overflow`` ``ErrorMsg`` branch when
    ``queue.maxsize > 0 and queue.full()``, so an unbounded queue keeps the
    record free of gateway-side eviction artifacts that were never produced by
    a cognition step. Nothing ever ``get``s from this queue — the record is
    taken at push time, which is precisely the moment
    :meth:`~erre_sandbox.integration.gateway.Registry.fan_out` delivers to a
    session — so it is sized for the bounded closure runs this module drives,
    not for an open-ended production session.
    """

    def __init__(self, records: list[ControlEnvelope]) -> None:
        super().__init__()
        self._records = records

    def put_nowait(self, item: ControlEnvelope) -> None:
        self._records.append(item)
        super().put_nowait(item)


class SocietyBroadcastLedger:
    """Consume-side record of what the gateway **actually fanned out** (Codex H-2).

    ``gateway.py`` is **unmodified** (design-final.md §4, binding). This ledger
    reaches the fan-out stream through the gateway's own public session seam:
    :meth:`~erre_sandbox.integration.gateway.Registry.reserve_slot` — the same
    call ``ws_observe`` makes for a real WebSocket peer — registering an
    unbounded :class:`_RecordingQueue` with ``subscribed_agents=None`` (the
    unfiltered, receives-every-envelope subscription). Everything
    ``Registry.fan_out`` delivers to that session is therefore recorded, in
    delivery order.

    **Why not ``WorldRuntime.drain_envelopes()`` after the run (Codex H-2)**:
    the gateway's ``_broadcaster`` task consumes that very queue via
    ``recv_envelope()`` for as long as the app's lifespan is running, so
    whatever a post-hoc drain returns depends on how far the broadcaster
    happened to get — a race, not a record. PR #89's
    ``_broadcast_envelope_kinds`` is exactly the rejected shape. Reading the
    consume side instead inverts the dependency: the more the broadcaster
    consumed, the *more* complete this record is.

    Lifecycle: :meth:`attach` (before any fan-out can happen),
    :meth:`quiesce` (after the drive, before the serve task is torn down),
    then read :attr:`envelope_kinds`. :func:`supervise_society_live_loop`
    performs all three when handed a ledger via its ``broadcast_ledger``
    kwarg.
    """

    def __init__(self, *, session_id: str = "society-live-broadcast-ledger") -> None:
        self._session_id = session_id
        self._records: list[ControlEnvelope] = []
        self._queue = _RecordingQueue(self._records)
        self._registry: Registry | None = None

    @property
    def session_id(self) -> str:
        """The registry key this ledger's session occupies."""
        return self._session_id

    def attach(self, app: FastAPI) -> None:
        """Register the recording session on ``app.state.registry``.

        Must happen before the app's ``_broadcaster`` can fan out anything —
        :func:`supervise_society_live_loop` calls this inside the readiness
        hook, i.e. before ``gateway_serve(app)`` is even scheduled.

        Counts against ``Registry``'s session cap exactly like a real peer
        would (``reserve_slot`` raises ``SessionCapExceededError`` past the
        cap); it is one session out of the default 8.
        """
        registry: Registry = app.state.registry
        registry.reserve_slot(self._session_id, self._queue, subscribed_agents=None)
        self._registry = registry

    def detach(self) -> None:
        """Release the session slot (idempotent; keeps the record intact)."""
        if self._registry is not None:
            self._registry.release_slot(self._session_id)
            self._registry = None

    async def quiesce(
        self,
        *,
        stable_rounds: int = DEFAULT_QUIESCE_STABLE_ROUNDS,
        max_rounds: int = DEFAULT_QUIESCE_MAX_ROUNDS,
    ) -> int:
        """Yield to the event loop until the record stops growing.

        The gateway's ``_broadcaster`` is a *separate task*: when the drive's
        own coroutine returns, the last window's envelopes are enqueued on the
        runtime but not yet fanned out. This waits for them by yielding
        (``await asyncio.sleep(0)``) until ``stable_rounds`` consecutive yields
        add nothing new, capped at ``max_rounds``.

        Deterministic despite being a settle-loop: this module drives a single
        event loop with no real I/O and a scripted in-process perturbation
        sequence (design-final.md §5 — **not** a wall-clock real-time
        session), so the yield schedule is a pure function of the program, not
        of timing. It never calls ``drain_envelopes()`` (Codex H-2).

        Returns the number of yields performed — a plain diagnostic count.
        """
        stable = 0
        rounds = 0
        last = len(self._records)
        while stable < stable_rounds and rounds < max_rounds:
            await asyncio.sleep(0)
            rounds += 1
            current = len(self._records)
            if current == last:
                stable += 1
            else:
                stable = 0
                last = current
        return rounds

    @property
    def envelopes(self) -> tuple[ControlEnvelope, ...]:
        """Every envelope fanned out to this session, in delivery order."""
        return tuple(self._records)

    @property
    def envelope_kinds(self) -> tuple[str, ...]:
        """``.kind`` of every fanned-out envelope, in delivery order."""
        return tuple(env.kind for env in self._records)


def society_live_gateway_lifespan_serve() -> Callable[
    [FastAPI], Coroutine[Any, Any, None]
]:
    """Build a ``gateway_serve`` that actually runs the app's lifespan.

    :func:`supervise_society_live_loop`'s ``gateway_serve`` is caller-supplied
    precisely so this module never depends on uvicorn. But the gateway's
    ``_broadcaster`` task — the thing that moves envelopes from the runtime to
    :meth:`~erre_sandbox.integration.gateway.Registry.fan_out`, and therefore
    the only thing that makes a consume-side ledger non-vacuous — is started by
    ``gateway.py``'s ``_lifespan`` context manager. This serve callable enters
    that same lifespan in-loop (``app.router.lifespan_context(app)``) and then
    parks until cancelled.

    In-loop on purpose: ``fastapi.testclient.TestClient`` would run the app on
    its own thread with its own event loop, which is incompatible with this
    module's same-event-loop supervision contract (and would put the
    broadcaster out of reach of :meth:`SocietyBroadcastLedger.quiesce`'s
    yields). ``gateway.py`` itself is untouched — this only *enters* the
    lifespan it already declares.

    This is still not a socket-level server: nothing binds a port, so it does
    not promise "a real client could connect" (``decisions.md`` DA-SLC-6 (b)).
    """

    async def serve(app: FastAPI) -> None:
        async with app.router.lifespan_context(app):
            await asyncio.Event().wait()

    return serve


LIVE_ROOT_MODULE: Final[str] = __name__
"""This module's own ``__name__`` — the caller identity
:func:`spy_inject_envelope_callers` checks for (design-final.md §6 W-N3:
"live root が ``inject_envelope`` を呼ばないことを spy で pin")."""


@contextlib.contextmanager
def spy_inject_envelope_callers() -> Iterator[list[str]]:
    """Record the calling module of every ``WorldRuntime.inject_envelope`` call.

    The outbound single-owner witness (design-final.md §6 W-N3, third bullet):
    on the society path there are two legitimate producers — cognition (via
    ``_consume_result``, which this closure root never invokes itself) and the
    dialog scheduler (``society.py`` wires ``envelope_sink=world.
    inject_envelope``). The property being pinned is narrower and exact: **the
    live root itself never calls it**, so it can never re-inject what cognition
    already emitted (the honest generalisation of PR #89 HIGH-1).

    Yields a list of caller ``__name__`` values, appended in call order, so a
    caller asserts both the negative (:data:`LIVE_ROOT_MODULE` never appears)
    and, for non-vacuity, that the spy does record real calls.

    Patches the class attribute (not an instance) because ``society.py``
    captures ``world.inject_envelope`` as a bound method when it attaches the
    dialog scheduler — a bound method resolved from whatever the class
    attribute is at attach time — so an instance-level patch installed after
    that attach would silently see nothing. Restored unconditionally on exit.
    A witness instrument only: no code path in this module's drive uses it.
    """
    callers: list[str] = []
    original = WorldRuntime.inject_envelope

    def _spy(runtime: WorldRuntime, envelope: ControlEnvelope) -> None:
        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        callers.append(
            caller.f_globals.get("__name__", "<unknown>")
            if caller is not None
            else "<unknown>"
        )
        original(runtime, envelope)

    WorldRuntime.inject_envelope = _spy  # type: ignore[assignment,method-assign]
    try:
        yield callers
    finally:
        WorldRuntime.inject_envelope = original  # type: ignore[method-assign]


# --------------------------------------------------------------------------- #
# Issue 004 — W-N1 / W-N3 wiring-reachability witness (boolean & count only)
# --------------------------------------------------------------------------- #


def society_wiring_reachability_summary(
    run: SocietyLiveRunResult,
    *,
    broadcast_envelope_kinds: Sequence[str],
) -> dict[str, Any]:
    """Pure boolean/count wiring-reachability witness (Issue 004, W-N1 + W-N3).

    Operates only on ``run`` (this module's own ledger plus the drive's
    committed decision records) and the caller-supplied
    ``broadcast_envelope_kinds`` — the ``.kind`` sequence a
    :class:`SocietyBroadcastLedger` recorded from the **consume** side (Codex
    H-2). It re-drives nothing, measures nothing, and never touches
    ``WorldRuntime.drain_envelopes()``.

    **Population = ``injected`` only (Codex M-2)**: every per-correlation seam
    below is computed over ``run.ledger.injected``. A message whose
    ``target_agent_id`` was not registered went to ``rejected``, and a message
    evicted by sink overflow went to ``dropped`` — neither ever became an
    injected observation, so putting them in the reachability population would
    manufacture failures for messages that never entered the pipeline. Both
    appear instead as ``rejected_count`` / ``dropped_count`` plain counts.

    **Seam granularity is NOT uniform (design-final.md §6 W-N1, inherited from
    PR #89 HIGH-2)** — ``correlation_id`` is a
    :class:`~erre_sandbox.schemas.WorldPerturbationMsg` field that is never
    copied onto a :class:`~erre_sandbox.schemas.PerceptionEvent` or any
    outbound :class:`~erre_sandbox.schemas.ControlEnvelope`, so it simply does
    not reach the cognition/outbound seams. Three tiers, named as such:

    * **per-correlation** — traceable to THIS message:

      * ``perturbation`` — the ledger row's ``msg.correlation_id`` matches the
        row's own ``correlation_id`` (this row IS the drained message).
      * ``perception`` — re-applying the same unmodified pure mapping
        (:func:`~erre_sandbox.integration.inbound.world_perturbation_to_perception`)
        to ``(msg, agent_tick)`` reproduces the recorded observation exactly.
        ``wall_clock`` is excluded from the comparison: it is a per-call
        ``default_factory`` timestamp (``schemas._ObservationBase``) which the
        router pins to :data:`RECORD_MODE_WALL_CLOCK`, so two structurally
        identical events built microseconds apart would otherwise never
        compare equal (the ``exclude={"wall_clock"}`` precedent
        ``live_loop.wiring_reachability_summary`` already sets).
      * ``target_agent_routing`` — **the N-body seam** (AC1): the observation
        was injected into the window of the agent the message was aimed at.
        Deliberately a two-part check —
        ``msg.target_agent_id == observation.agent_id`` **and**
        ``msg.target_agent_id == routed_agent_id`` — because the first half
        alone is a tautology (``world_perturbation_to_perception`` copies
        ``target_agent_id`` straight onto ``agent_id``, so a mis-bucketed
        message still names the intended agent). The second half compares
        against the bucket the router actually drew the message from, which
        is the value a bucketing bug would change. With N=1 this is trivially
        true; with N=3 it is the whole point of the router.

    * **per (agent, window)** — ``capture``: the agent whose bucket actually
      produced the observation has a committed cognition decision at this
      ``agent_tick``, i.e. the window that received it actually became a
      committed step. Two perturbations routed to the same agent in the same
      window share this value; that is by construction, and the claim made is
      exactly "that agent's window was stepped", never "this message
      specifically produced that step".

    * **tick-level co-occurrence** — ``same_tick_cognition_stepped`` /
      ``same_tick_envelope_observed``: some agent stepped / some agent's step
      emitted at least one envelope on this message's injection tick. Every
      perturbation landing on the same tick reads the SAME value (AC7) — by
      construction, not an over-count: the honest claim is "the tick
      co-occurred", never "each perturbation individually produced it".

    **``no_double_send`` (W-N3)** compares two multisets restricted to
    :data:`COGNITION_ENVELOPE_KINDS`:

    * enqueue side — ``kind`` parsed out of every
      ``run.result.decisions[*].envelope_provenance`` entry (each entry is one
      emitted envelope's ``model_dump_json()``);
    * consume side — ``broadcast_envelope_kinds``, i.e. what
      ``Registry.fan_out`` actually delivered.

    Equality means the gateway delivered exactly the cognition envelopes the
    committed decisions account for: no envelope was re-injected by a second
    producer, and none was lost. ``dialog_*`` is a **plain count annotation
    only** (``dialog_envelope_counts``), never gated — see
    :data:`DIALOG_ENVELOPE_KINDS` for the Codex H-3 reason — and
    :data:`EXCLUDED_ENVELOPE_KINDS` names every other kind kept out of the
    gate.

    **Honest framing (binding, design-final.md §2)**: this is *wiring* /
    *construction*. Reachability is not causation. No floor / verdict /
    divergence / magnitude / detectability / scorer / aha-proxy is computed;
    ``verdict`` is an explicit ``None`` marker and no returned key names such
    a claim (AC6).
    """
    ledger = run.ledger
    stepped: set[tuple[str, int]] = set()
    ticks_stepped: set[int] = set()
    ticks_with_envelope: set[int] = set()
    enqueued_kinds: Counter[str] = Counter()
    for agent_id, records in run.result.decisions.items():
        for record in records:
            stepped.add((agent_id, record.agent_tick))
            ticks_stepped.add(record.agent_tick)
            if record.envelope_provenance:
                ticks_with_envelope.add(record.agent_tick)
            for envelope_json in record.envelope_provenance:
                kind = str(json.loads(envelope_json)["kind"])
                if kind in COGNITION_ENVELOPE_KINDS:
                    enqueued_kinds[kind] += 1

    consumed_kinds: Counter[str] = Counter(
        kind for kind in broadcast_envelope_kinds if kind in COGNITION_ENVELOPE_KINDS
    )
    consumed_all: Counter[str] = Counter(broadcast_envelope_kinds)

    per_correlation_id: dict[str, dict[str, bool]] = {}
    for injected in ledger.injected:
        rederived = world_perturbation_to_perception(
            injected.msg, tick=injected.agent_tick
        )
        seams = {
            "perturbation": injected.msg.correlation_id == injected.correlation_id,
            "perception": injected.observation.model_dump(exclude={"wall_clock"})
            == rederived.model_dump(exclude={"wall_clock"}),
            "target_agent_routing": (
                injected.msg.target_agent_id == injected.observation.agent_id
                and injected.msg.target_agent_id == injected.routed_agent_id
            ),
            "capture": (injected.routed_agent_id, injected.agent_tick) in stepped,
            "same_tick_cognition_stepped": injected.agent_tick in ticks_stepped,
            "same_tick_envelope_observed": injected.agent_tick in ticks_with_envelope,
        }
        seams["all_seams_reached"] = all(seams.values())
        per_correlation_id[injected.correlation_id] = seams

    all_reach = (
        all(seams["all_seams_reached"] for seams in per_correlation_id.values())
        if per_correlation_id
        else False
    )

    return {
        "per_correlation_id": per_correlation_id,
        "all_correlation_ids_reach_all_seams": all_reach,
        "injected_count": len(ledger.injected),
        "rejected_count": len(ledger.rejected),
        "dropped_count": ledger.dropped,
        "cognition_envelope_kinds_enqueued": dict(enqueued_kinds),
        "cognition_envelope_kinds_consumed": dict(consumed_kinds),
        "no_double_send": enqueued_kinds == consumed_kinds,
        "dialog_envelope_counts": {
            kind: consumed_all.get(kind, 0) for kind in DIALOG_ENVELOPE_KINDS
        },
        "verdict": None,
        "note": (
            "wiring reachability witness (non-gate, side annotation): boolean "
            "per-correlation-id seam reachability over the INJECTED "
            "population only -- 'wiring reached each seam' -- plus plain "
            "injected / rejected / dropped / envelope-kind counts. "
            "Reachability is not causation. Seam granularity is NOT uniform: "
            "'perturbation' / 'perception' / 'target_agent_routing' are "
            "per-correlation; 'capture' is per (agent, window), shared by "
            "several perturbations aimed at the same agent's same window; "
            "'same_tick_cognition_stepped' / 'same_tick_envelope_observed' "
            "are TICK-LEVEL co-occurrence, read identically by every "
            "perturbation on that tick -- by construction, not an "
            "over-count -- because correlation-id never reaches the "
            "cognition/outbound wire protocol. 'no_double_send' gates the "
            "cognition kinds only (agent_update / animation / move / speech); "
            "dialog_initiate / dialog_turn / dialog_close are a plain count "
            "annotation and are NOT gated, because run_society_loop fixes the "
            "dialog scheduler's envelope sink to world.inject_envelope "
            "internally and wrapping it would need a third additive kwarg "
            "the frozen ADR defers to a separate dialog_envelope_sink ADR "
            "(Codex H-3); handshake / world_tick (which also carries the "
            "periodic liveness heartbeat) / world_layout / error / "
            "reasoning_trace / reflection_event are excluded from both sides. "
            "This function computes no floor, magnitude, verdict or statistic "
            "beyond these booleans and counts."
        ),
    }


async def supervise_society_live_loop(
    *,
    world: SocietyLiveWorldInput,
    gateway_serve: Callable[[FastAPI], Coroutine[Any, Any, None]],
    run_id: str,
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    on_tasks_scheduled: Callable[[asyncio.Task[None], asyncio.Task[None]], None]
    | None = None,
    broadcast_ledger: SocietyBroadcastLedger | None = None,
) -> SocietyLiveRunResult:
    """Supervise gateway serve + the society drive in one ``TaskGroup``.

    Mirrors :func:`~erre_sandbox.integration.embodied.live_loop.supervise_live_loop`
    (same-event-loop ``asyncio.TaskGroup``, cancel-on-completion,
    ``on_tasks_scheduled`` testing seam, real-exception-propagates-as-
    ``ExceptionGroup``) with **one deliberate shape deviation**, forced by
    this module's construction constraint (ADR §1: no second ``WorldRuntime``):
    ``live_loop.build_live_loop_world`` constructs its ``WorldRuntime`` BEFORE
    ``supervise_live_loop`` is even called, so that sibling's ``gateway_serve``
    can be a plain zero-arg callable the caller pre-binds to a already-known
    runtime. Here, :func:`build_society_live_world` deliberately builds no
    runtime at all — the concrete ``WorldRuntime`` only exists once
    ``run_society_loop`` constructs it and hands it to ``on_runtime_ready``,
    which does not fire until AFTER this function has already started the
    drive. ``gateway_serve`` therefore takes the constructed
    :class:`~fastapi.FastAPI` app as its one argument — the app itself can
    only be built (``make_app(runtime=..., inbound_sink=...)``) once that
    runtime is known, i.e. **inside** the ``on_runtime_ready`` hook below,
    never before it (Codex H-1's readiness-ordering concern, generalised).

    **Readiness barrier (AC1, Codex H-1)**: the internal ``on_runtime_ready``
    hook (1) builds ``app = make_app(runtime=<the runtime run_society_loop
    just built>, inbound_sink=world.inbound_sink)`` (AC6: the SAME instance,
    no second channel), (2) schedules ``gateway_serve(app)`` as a task on
    THIS SAME ``TaskGroup`` (AC2 — same event loop by construction, since
    ``asyncio.TaskGroup.create_task`` always schedules onto
    ``asyncio.get_running_loop()`` at the point it is called), then (3)
    ``await asyncio.sleep(0)`` once before returning. Because
    ``tg.create_task(...)`` above already scheduled the new task's own first
    step via ``loop.call_soon()`` strictly BEFORE this function's own
    ``sleep(0)`` schedules its continuation the same way, asyncio's
    single-threaded FIFO-ready-queue guarantees the gateway task's
    synchronous prefix (everything up to ITS OWN first internal ``await``)
    has already run by the time this hook's ``await`` returns — and therefore
    before ``run_society_loop``'s first cognition window below (the hook is
    awaited, per Issue 001, before that window's first observation drain).
    This is a genuine scheduling-order guarantee, not a real socket-level
    "accepting connections" probe — honest for a construction-only closure
    root driving a caller-injected stub or uvicorn server alike.

    **``broadcast_ledger`` (Issue 004, optional, default ``None`` = every
    pre-Issue-004 call is unaffected)**: when supplied, this supervisor owns
    the two moments a consume-side outbound record needs and a caller cannot
    reach on its own —

    1. :meth:`SocietyBroadcastLedger.attach` is called on the freshly built
       ``app`` **inside** the readiness hook, i.e. strictly before
       ``gateway_serve(app)`` is even scheduled and therefore strictly before
       the app's ``_broadcaster`` can fan out its first envelope. Nothing can
       be missed by attaching late.
    2. :meth:`SocietyBroadcastLedger.quiesce` is awaited after the drive
       finishes but **before** the serve task is cancelled — the broadcaster
       is a separate task consuming ``runtime.recv_envelope()``, so the last
       window's envelopes are still in flight when the drive's own coroutine
       returns. Cancelling first would truncate the record; draining the
       runtime queue instead would be exactly the race Codex H-2 rejected.

    A genuine exception from either the drive or ``gateway_serve`` still
    propagates as an ``ExceptionGroup`` (``TaskGroup`` semantics unchanged);
    only ``asyncio.CancelledError`` from the deliberate shutdown-cancel below
    is suppressed.
    """
    result_box: list[SocietyLiveRunResult] = []
    serve_task_box: list[asyncio.Task[None]] = []
    driven_task_box: list[asyncio.Task[None]] = []

    async def _on_runtime_ready(runtime: WorldRuntime) -> None:
        # Construction exposure only (Codex M-5): make_app READS runtime (a
        # constructor keyword), it never calls a mutating method on it.
        app = make_app(runtime=runtime, inbound_sink=world.inbound_sink)
        if broadcast_ledger is not None:
            # Registered BEFORE the serve task exists, so no fan-out can
            # precede the record (Codex H-2 consume-side ledger).
            broadcast_ledger.attach(app)

        async def _serve_until_cancelled() -> None:
            with contextlib.suppress(asyncio.CancelledError):
                await gateway_serve(app)

        serve_task = tg.create_task(
            _serve_until_cancelled(), name="society-live-gateway-serve"
        )
        serve_task_box.append(serve_task)
        # See the readiness-barrier docstring paragraph above for why this
        # single sleep(0) is a deterministic ordering guarantee, not a poll.
        await asyncio.sleep(0)
        if on_tasks_scheduled is not None:
            on_tasks_scheduled(serve_task, driven_task_box[0])

    async def _driven() -> None:
        result_box.append(
            await run_society_live_loop(
                world,
                run_id=run_id,
                retrieval_now=retrieval_now,
                base_ts=base_ts,
                seed=seed,
                n_cognition_ticks=n_cognition_ticks,
                physics_ticks_per_cognition=physics_ticks_per_cognition,
                k_ecl=k_ecl,
                reflector=reflector,
                on_runtime_ready=_on_runtime_ready,
            )
        )

    async with asyncio.TaskGroup() as tg:
        driven_task = tg.create_task(_driven(), name="society-live-driven")
        driven_task_box.append(driven_task)
        await driven_task
        if broadcast_ledger is not None:
            # Let the still-running broadcaster finish fanning out the last
            # window's envelopes BEFORE the serve task (and with it the
            # lifespan's broadcaster) is torn down.
            await broadcast_ledger.quiesce()
        if serve_task_box:
            serve_task_box[0].cancel()

    return result_box[0]


__all__ = [
    "COGNITION_ENVELOPE_KINDS",
    "DEFAULT_MAX_DRAIN_PER_TICK",
    "DEFAULT_QUIESCE_MAX_ROUNDS",
    "DEFAULT_QUIESCE_STABLE_ROUNDS",
    "DIALOG_ENVELOPE_KINDS",
    "EXCLUDED_ENVELOPE_KINDS",
    "LIVE_ROOT_MODULE",
    "RECORD_MODE_WALL_CLOCK",
    "SocietyBroadcastLedger",
    "SocietyInboundLedger",
    "SocietyInboundRouter",
    "SocietyInjectedPerturbation",
    "SocietyLiveRunResult",
    "SocietyLiveWorldInput",
    "build_society_live_world",
    "run_society_live_loop",
    "society_live_gateway_lifespan_serve",
    "society_live_loop_perturbation_plan",
    "society_wiring_reachability_summary",
    "spy_inject_envelope_callers",
    "supervise_society_live_loop",
]
