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

**Issue 005 (this module's fourth addition)** lands the mirror witness
(design-final.md §6 W-N2), again pure boolean/count with ``verdict`` an
explicit ``None``:

* :func:`self_other_segment_contract` / :func:`self_other_segment_marker` —
  the segment's render contract, **re-derived by calling ``society.py``'s own
  public :func:`~erre_sandbox.integration.embodied.society.
  build_self_other_context`** on a synthetic probe rather than copying a
  literal. The mirror's SSOT stays in ``society.py``: the live root builds no
  self-other context of its own, it only reads what the committed record holds
  (ADR 案 B の主根拠).
* :func:`extract_self_other_segment` / :func:`committed_self_other_segments` /
  :class:`CommittedSelfOtherSegment` — the committed-``RecordedLlmCall``
  readers.
* :func:`society_mirror_wiring_summary` — presence per ``(agent, window)``,
  observer attribution, the ``n_agents x windows`` call-budget pin (Codex
  **M-4**: the segment rides in the existing cognition call, it never adds a
  new one), and a disjointness check **scoped to the observation-derived
  memory field** (Codex **L-2**) with the LLM's own echo of the marker
  reported separately as a plain count, never as a violation.

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

import ast
import asyncio
import contextlib
import inspect
import json
from collections import Counter
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.integration.embodied.handoff import (
    canonical_dumps,
    recorded_calls_from_jsonl,
    render_society_golden,
)
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.society import (
    SelfOtherPriorRecord,
    build_self_other_context,
    run_society_loop,
)
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    society_live_agent_states,
    society_live_personas,
)
from erre_sandbox.integration.embodied.traversal_live import (
    EmbeddingRecordReplayClient,
    RecordedEmbeddingCall,
)
from erre_sandbox.integration.embodied.two_phase_live import two_phase_firing_summary
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
    from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import RecordedLlmCall
    from erre_sandbox.integration.embodied.society import (
        SelfOtherObservationInput,
        SocietyRunResult,
    )
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
        # sorted(): a frozenset's iteration order is hash-seeded, so building
        # the bucket map from it directly would give this dict a per-process
        # key order. Nothing iterates ``_buckets`` today (every access is by
        # key), so this is order-neutral -- but the live root keeps the
        # invariant its own determinism guard states rather than relying on
        # "no one iterates it yet" (design-final.md §5).
        self._buckets: dict[str, list[WorldPerturbationMsg]] = {
            agent_id: [] for agent_id in sorted(self._registered_agent_ids)
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
    # sorted(): the live root iterates no mapping view in arrival order (the
    # determinism guard's ``unsorted_iteration`` rule, design-final.md §5).
    for agent_id in sorted(run.result.decisions):
        for record in run.result.decisions[agent_id]:
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

    per_correlation_rows: list[tuple[str, dict[str, bool]]] = []
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
        per_correlation_rows.append((injected.correlation_id, seams))

    per_correlation_id = dict(per_correlation_rows)
    # Folded over the ordered ledger-derived list, never over a mapping view:
    # the live root iterates no dict view in arrival order (determinism guard).
    all_reach = (
        all(
            seams["all_seams_reached"]
            for _correlation_id, seams in per_correlation_rows
        )
        if per_correlation_rows
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


# --------------------------------------------------------------------------- #
# Issue 005 — mirror (prompt-level self-other context) wiring witness
# (design-final.md §6 W-N2; Codex L-1 vocabulary / L-2 disjointness scoping /
# M-4 call-count + attribution pins)
# --------------------------------------------------------------------------- #

_SEGMENT_PROBE_OBSERVER: Final[str] = "\x00probe-observer"
_SEGMENT_PROBE_OTHER: Final[str] = "\x00probe-other"
_SEGMENT_PROBE_ZONE: Final[str] = "\x00probe-zone"
"""Probe identifiers used only to re-derive the self-other segment's render
contract from ``society.py``'s own public builder.

They start with ``\\x00`` so they can never collide with a real ``agent_id`` /
``Zone`` value, which keeps the derivation unambiguous no matter what roster a
caller runs."""


def self_other_segment_contract() -> tuple[str, str]:
    """Return ``(marker, bullet_prefix)`` derived from society's public builder.

    The mirror's SSOT is ``society.py`` (design-final.md §1, ADR 案 B): this
    module **re-implements nothing**. To read a committed prompt it still needs
    two facts about the rendered segment — the line it starts with, and the
    prefix each observed-other line starts with — so both are obtained by
    calling the public
    :func:`~erre_sandbox.integration.embodied.society.build_self_other_context`
    on a synthetic one-other probe and reading its own ``rendered`` output back.
    No literal is copied here, so a change to society's render moves this
    contract with it instead of silently desynchronising a hard-coded copy.

    ``marker`` is the segment's first (framing) line, quoted verbatim from
    society's render — that module's wording, used here purely as a detection
    needle, never restated as this module's own vocabulary (Codex L-1).
    ``bullet_prefix`` is whatever precedes an observed agent's id on its line
    (``"- "`` in the current render), used for line-anchored membership tests.
    """
    probe = build_self_other_context(
        observer_id=_SEGMENT_PROBE_OBSERVER,
        window_index=1,
        prior_records=(
            SelfOtherPriorRecord(
                agent_id=_SEGMENT_PROBE_OTHER,
                window=0,
                zone=_SEGMENT_PROBE_ZONE,
            ),
        ),
    )
    marker, bullet_line = probe.rendered.split("\n", 1)
    bullet_prefix = bullet_line.split(_SEGMENT_PROBE_OTHER, 1)[0]
    return marker, bullet_prefix


def self_other_segment_marker() -> str:
    """The framing line a rendered self-other segment starts with (see above)."""
    return self_other_segment_contract()[0]


def extract_self_other_segment(user_prompt: str, *, marker: str) -> str:
    r"""Slice the self-other segment out of one committed ``user_prompt``.

    ``""`` when the prompt carries no segment (Layer2 off, or window 0 / an
    all-empty prior window). Otherwise the slice runs from ``marker`` to the
    first blank line after it: society's ``_render_self_other`` joins its lines
    with a single ``"\n"`` and the prompt builder appends ``"\n\n"`` after the
    block, so the first ``"\n\n"`` is exactly the segment's end. That boundary
    comes from the *render* contract, not from a copied prompt-template literal.
    """
    start = user_prompt.find(marker)
    if start < 0:
        return ""
    return user_prompt[start:].split("\n\n", 1)[0]


@dataclass(frozen=True, slots=True)
class CommittedSelfOtherSegment:
    """One committed cognition call's self-other segment (read-only projection).

    ``window`` is the call's ``EclDecisionRecord.agent_tick``; ``text`` is the
    exact slice that rode in that call's ``user_prompt``. Presence and observer
    attribution are the only things read off it — its **content is never graded,
    ranked or compared** (that would be measurement re-entry, Stop condition S4).
    """

    agent_id: str
    window: int
    text: str


def committed_self_other_segments(
    result: SocietyRunResult,
    *,
    marker: str | None = None,
) -> tuple[CommittedSelfOtherSegment, ...]:
    """Every non-empty self-other segment in ``result``'s committed calls.

    Reads ``result.decisions[*].call.user_prompt`` only — the committed
    ``RecordedLlmCall``, never a re-drive and never a live prompt rebuild.
    Ordered by ``(agent_id, window)``.
    """
    needle = self_other_segment_marker() if marker is None else marker
    segments: list[CommittedSelfOtherSegment] = []
    for agent_id in sorted(result.decisions):
        for record in result.decisions[agent_id]:
            text = extract_self_other_segment(record.call.user_prompt, marker=needle)
            if text:
                segments.append(
                    CommittedSelfOtherSegment(
                        agent_id=agent_id, window=record.agent_tick, text=text
                    )
                )
    return tuple(segments)


def _segment_named_roster_ids(
    segment: str,
    *,
    roster: Sequence[str],
    bullet_prefix: str,
) -> frozenset[str]:
    """Roster ids named on their own line in ``segment`` (structural, not graded).

    Line-anchored on ``bullet_prefix`` so an id echoed *inside* another agent's
    rendered ``said=…`` value cannot be mistaken for an observed-other line:
    society's render JSON-string-encodes every utterance, so an echoed utterance
    is always single-line and can never open a new bullet.
    """
    lines = segment.splitlines()[1:]
    return frozenset(
        agent_id
        for agent_id in roster
        if any(line.startswith(f"{bullet_prefix}{agent_id}") for line in lines)
    )


def _segment_leak_needles(
    segments: Sequence[CommittedSelfOtherSegment],
    *,
    marker: str,
) -> tuple[str, ...]:
    """Needles a memory row must not contain: the marker plus every bullet line.

    The marker alone would miss a *partial* leak (an observed-other line copied
    without its framing header), so each committed segment's own body lines are
    needles too. Deduplicated and sorted, so the search order is deterministic.
    """
    needles = {marker}
    for segment in segments:
        needles.update(line for line in segment.text.splitlines()[1:] if line)
    return tuple(sorted(needles))


def society_mirror_wiring_summary(result: SocietyRunResult) -> dict[str, Any]:
    """Pure boolean/count mirror-wiring witness (Issue 005, design-final.md §6 W-N2).

    Reads one committed
    :class:`~erre_sandbox.integration.embodied.society.SocietyRunResult` and
    nothing else — no re-drive, no live prompt rebuild, no store access. The
    mirror itself is **not re-implemented here**: the segment is built by
    ``run_society_loop(self_other_enabled=True)`` through ``society.py``'s own
    ``_build_window_self_other_contexts`` →
    :func:`~erre_sandbox.integration.embodied.society.build_self_other_context`,
    and this function only reads what that produced back out of the committed
    ``RecordedLlmCall.user_prompt`` (design-final.md §1: the SSOT stays in
    ``society.py``; the live root just reads the record).

    **What is read**

    * *presence* — which ``(agent_id, window)`` calls carried a non-empty
      segment (``segment_present_windows_per_agent`` /
      ``segment_present_count`` / ``any_agent_window_has_segment``), and that
      window 0 carried none (``window_zero_segment_absent``: window 0 has no
      prior window, the strict prefix filter's observable consequence in a
      committed run — the filter itself is pinned by ``society.py``'s own suite,
      ``test_self_other_no_future_or_self_leak``).
    * *observer attribution* — no segment names its own observer
      (``segment_never_names_observer``); every non-empty segment names at least
      one roster agent (``every_nonempty_segment_names_a_roster_agent``, the
      vacuity guard: were the render contract to drift, the naming checks would
      silently pass on an empty parse, and this boolean turns ``False``
      instead); and the ``(agent, window)`` → call map is a bijection over a
      complete window range (``agent_window_pairs_unique`` /
      ``agent_windows_complete``, Codex M-4).
    * *call budget* — the mirror adds **no new LLM call**:
      ``llm_call_count == n_agents * windows``
      (``llm_call_count_equals_agents_times_windows``, Codex M-4). The segment
      rides inside the existing cognition call's user prompt.
    * *disjointness, deliberately scoped (Codex L-2)* — the inspected sink is
      the **observation-derived memory field** only:
      ``SocietyRunResult.memory_mutations[*].content`` with ``kind='episodic'``,
      which ``cognition/cycle.py`` writes solely from pre-prompt observations
      (``_write_observations``; reflection is disabled in this driver's record
      mode, so no other memory table is ever written). A marker appearing in an
      LLM's **own raw response** — exactly what an echoing adversary mock
      produces — is an echo of the prompt: it is reported as the plain
      annotation ``llm_output_segment_echo_count`` and is explicitly **not** a
      disjointness violation.

    **What is NOT read (binding)**: the segment's *content* is never graded,
    ranked, scored or compared between runs (Stop condition S4 — a covert scorer
    would be measurement re-entry), and whether the segment changed any agent's
    behaviour is the frozen second link and is deliberately not computed.

    **Honest framing (design-final.md §2, Codex L-1)**: this is a witness of
    **construction wiring**. It is not a theory of mind, not an estimate of any
    agent's inner state, and not a measurement. ``verdict`` is an explicit
    ``None`` and no returned key — at any nesting level — names an effect,
    divergence, floor, score, detectability or aha claim.
    """
    marker, bullet_prefix = self_other_segment_contract()
    agent_ids = sorted(result.decisions)
    segments = committed_self_other_segments(result, marker=marker)

    windows_per_agent = {
        agent_id: len(result.decisions[agent_id]) for agent_id in agent_ids
    }
    llm_call_count = sum(windows_per_agent.values())
    distinct_window_counts = set(windows_per_agent.values())
    uniform_windows = (
        next(iter(distinct_window_counts)) if len(distinct_window_counts) == 1 else None
    )
    pairs = [
        (agent_id, record.agent_tick)
        for agent_id in agent_ids
        for record in result.decisions[agent_id]
    ]

    present: dict[str, list[int]] = {agent_id: [] for agent_id in agent_ids}
    names_observer = False
    names_a_roster_agent = True
    for segment in segments:
        present.setdefault(segment.agent_id, []).append(segment.window)
        named = _segment_named_roster_ids(
            segment.text, roster=agent_ids, bullet_prefix=bullet_prefix
        )
        names_observer = names_observer or segment.agent_id in named
        names_a_roster_agent = names_a_roster_agent and bool(named)

    needles = _segment_leak_needles(segments, marker=marker)
    memory_kinds: Counter[str] = Counter(row.kind for row in result.memory_mutations)
    carrying = sorted(
        row.memory_id
        for row in result.memory_mutations
        if any(needle in row.content for needle in needles)
    )
    echo_count = sum(
        1
        for agent_id in agent_ids
        for record in result.decisions[agent_id]
        if marker in record.call.raw_response
    )

    return {
        "segment_marker": marker,
        "agent_ids": list(agent_ids),
        "n_agents": len(agent_ids),
        "windows_per_agent": windows_per_agent,
        "llm_call_count": llm_call_count,
        "llm_call_count_equals_agents_times_windows": (
            uniform_windows is not None
            and llm_call_count == len(agent_ids) * uniform_windows
        ),
        "agent_window_pairs_unique": len(set(pairs)) == len(pairs),
        "agent_windows_complete": all(
            sorted(record.agent_tick for record in result.decisions[agent_id])
            == list(range(windows_per_agent[agent_id]))
            for agent_id in agent_ids
        ),
        "roster_ids_prefix_free": not any(
            one != other and other.startswith(one)
            for one in agent_ids
            for other in agent_ids
        ),
        "segment_present_windows_per_agent": {
            agent_id: sorted(present[agent_id]) for agent_id in sorted(present)
        },
        "segment_present_count": len(segments),
        "any_agent_window_has_segment": bool(segments),
        "window_zero_segment_absent": all(segment.window != 0 for segment in segments),
        "segment_never_names_observer": not names_observer,
        "every_nonempty_segment_names_a_roster_agent": names_a_roster_agent,
        "observation_memory_row_count": len(result.memory_mutations),
        "observation_memory_kinds": dict(memory_kinds),
        "observation_memory_rows_carrying_segment": carrying,
        "segment_absent_from_observation_memory": not carrying,
        "llm_output_segment_echo_count": echo_count,
        "verdict": None,
        "note": (
            "mirror wiring witness (construction wiring, non-gate annotations "
            "included): a boolean/count reading of the COMMITTED record only -- "
            "which (agent, window) cognition calls carried a non-empty "
            "prompt-level self-other context segment, whether any such segment "
            "reached the observation-derived memory field, and whether the call "
            "budget stayed at n_agents x windows with a unique per-agent "
            "attribution. This is CONSTRUCTION WIRING: it is not a theory of "
            "mind, it is not an estimate of any agent's inner state, and it is "
            "not a measurement -- whether the segment changed any behaviour is "
            "the frozen second link and is deliberately not computed. The "
            "segment's CONTENT is never graded, ranked or compared; only its "
            "presence, its observer attribution and its absence from the "
            "observation-derived memory field are read. Disjointness is "
            "deliberately scoped to that field alone "
            "(memory_mutations[*].content, kind='episodic', written solely "
            "from pre-prompt observations): a marker appearing in an LLM's own "
            "raw response is an echo of the prompt, is reported as the plain "
            "count llm_output_segment_echo_count, and is NOT a disjointness "
            "violation. segment_marker is quoted verbatim from society.py's "
            "own public builder render, so this module never restates that "
            "wording as a claim of its own. No floor, verdict or statistic is "
            "computed."
        ),
    }


# --------------------------------------------------------------------------- #
# Issue 006 — Plane G replay byte-parity + request conformance
# (design-final.md §5 "Plane G (regression guard)" / §6 W-N4; Codex H-4 / M-3)
#
# **Not a wall-clock real-time session (Codex M-3, binding)**: everything below
# is scoped to the *scripted in-process perturbation sequence* a capture
# committed. Real Godot frames, real WebSocket arrival times and real LLM
# latency are external non-determinism sources and are **outside** the replay
# set — byte-parity here is a statement about this module's scripted drive, not
# about a wall-clock live session. Nothing below measures an effect: every
# returned value is a boolean, a count, a checksum string or a request record.
# --------------------------------------------------------------------------- #


class _LedgerRow(Protocol):
    """The three fields a Plane G observation feed needs from one ledger row.

    Both :class:`SocietyInjectedPerturbation` (the in-process ledger the router
    produces, I2/I4) and :class:`SocietyLedgerEntry` (its serialised bundle
    form) satisfy this, so :func:`ledger_observation_factories` reads either one
    without a conversion step in between.
    """

    @property
    def agent_tick(self) -> int: ...

    @property
    def routed_agent_id(self) -> str: ...

    @property
    def msg(self) -> WorldPerturbationMsg: ...


@dataclass(frozen=True, slots=True)
class SocietyLedgerEntry:
    """Serialised form of one :class:`SocietyInjectedPerturbation`.

    Carries only what a replay needs to rebuild the observation feed — the
    derived :class:`~erre_sandbox.schemas.PerceptionEvent` is deliberately NOT
    stored, because a bundle that shipped the mapping's *output* alongside its
    *input* would let a drifted mapping replay green against its own stale
    output. The replay re-derives it from ``msg`` through the unmodified
    :func:`~erre_sandbox.integration.inbound.world_perturbation_to_perception`.
    """

    agent_tick: int
    correlation_id: str
    routed_agent_id: str
    msg: WorldPerturbationMsg


def society_ledger_entries(
    injected: Sequence[SocietyInjectedPerturbation],
) -> tuple[SocietyLedgerEntry, ...]:
    """Project the in-process injected ledger onto its serialisable form."""
    return tuple(
        SocietyLedgerEntry(
            agent_tick=row.agent_tick,
            correlation_id=row.correlation_id,
            routed_agent_id=row.routed_agent_id,
            msg=row.msg,
        )
        for row in injected
    )


def ledger_observation_factories(
    ledger: Sequence[_LedgerRow],
    *,
    agent_ids: Sequence[str],
) -> Mapping[str, Callable[[int], Sequence[Observation]]]:
    """Rebuild the per-agent observation feed from a committed inbound ledger.

    The N-agent generalisation of
    ``scripts.m13_live_loop_capture.ledger_observation_factory``: instead of one
    ``{tick: observations}`` table for a single agent, this keys on
    ``(agent, window)`` and returns the ``{agent_id: factory}`` mapping
    ``society.py::run_society_loop`` already takes on its public
    ``observation_factories`` kwarg — so a Plane G replay drives the
    **unmodified** driver.

    **Grouping is by ``routed_agent_id``, never ``observation.agent_id``
    (binding, ``decisions.md`` DA-SLC-8)**: ``world_perturbation_to_perception``
    copies ``msg.target_agent_id`` onto ``PerceptionEvent.agent_id``
    *unconditionally* (``inbound.py``, unmodified), so the observation's own
    ``agent_id`` says which agent the message was *aimed at*, not which agent's
    window it actually entered. ``routed_agent_id`` is the router's record of
    the bucket it really drew the message from — the single source of truth for
    "which window/bucket did this land in", and therefore the only correct key
    for reconstructing the same feed.

    **No mapping logic of its own**: the perturbation → perception step is the
    same unmodified pure function the router applied, and ``wall_clock`` is
    pinned to the same :data:`RECORD_MODE_WALL_CLOCK` the router pins
    (``schemas``' ``default_factory=_utc_now`` would otherwise stamp real time
    and break byte-parity). If either half drifted, this replay would stop
    reproducing the capture rather than silently agreeing with it.

    Each returned factory is **repeatable** (it reads a prebuilt table rather
    than draining a bucket, unlike :meth:`SocietyInboundRouter.observation_factories`
    whose factories clear their bucket): ``run_society_loop`` calls each exactly
    once per window, but a repeatable factory keeps this function a pure
    projection of the ledger rather than a stateful second driver.
    """
    by_agent_window: dict[tuple[str, int], list[PerceptionEvent]] = {}
    for row in ledger:
        observation = world_perturbation_to_perception(
            row.msg, tick=row.agent_tick
        ).model_copy(update={"wall_clock": RECORD_MODE_WALL_CLOCK})
        by_agent_window.setdefault((row.routed_agent_id, row.agent_tick), []).append(
            observation
        )

    def _make(agent_id: str) -> Callable[[int], Sequence[Observation]]:
        def factory(agent_tick: int) -> Sequence[Observation]:
            return tuple(by_agent_window.get((agent_id, agent_tick), ()))

        return factory

    return {agent_id: _make(agent_id) for agent_id in agent_ids}


# --------------------------------------------------------------------------- #
# Request conformance spies (Codex H-4 — the N-agent generalisation of
# ``scripts/m13_live_loop_capture.py``'s ``RequestConformance*`` pair)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyLlmRequest:
    """One cognition call's **request identity**, as recomposed at replay time.

    Exactly the four fields Codex H-4 binds as the conformance key —
    ``sampling`` is deliberately **not** a field here (see
    :data:`CONFORMANCE_EXCLUDED_FIELDS`): the spy that produces these records
    *does* observe the recomposed sampling, but it keeps it in a separate
    channel (:attr:`SocietyRequestConformanceChatClient.samplings`) precisely so
    a comparison of these records can never accidentally include it.
    """

    agent_id: str
    window: int
    system_prompt: str
    user_prompt: str


class SocietyRequestConformanceChatClient:
    """Per-agent replay-side spy pinning the *request* against the committed record.

    **Why a spy is required at all (Codex H-4, binding)**:
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` is
    **ordinal** — on replay it serves ``recorded[i]`` for the *i*-th call and
    appends *that committed record* to ``used``, without ever looking at what
    the caller actually asked. So comparing ``result.decisions[*].call`` against
    the committed record is **tautological**: it is the committed record, handed
    back. An apparatus drift that silently changed the prompt the cognition
    cycle composes would still replay to a green checksum, because the recorded
    answers would be re-served against questions nobody checked. This wrapper
    records the ``(system_prompt, user_prompt)`` the cycle *actually handed the
    client* on this replay — an independently produced string —
    so :func:`society_request_conformance` compares two genuinely different
    productions rather than one value against itself.

    ``window`` is the ordinal of this agent's own calls.
    ``society.py::_step_one_agent`` raises unless **exactly one** action-LLM
    call is served per ``(agent, window)`` (reflection is disabled in record
    mode), and the driver steps windows in strictly increasing order, so the
    *i*-th call this client sees is window *i* — the same identity the
    committed ``EclDecisionRecord.agent_tick`` carries.

    ``used`` / ``inner_invocations`` / ``is_replay`` delegate to the wrapped
    client, mirroring ``live_v1.SamplingSpyChatClient``'s drop-in contract, so
    ``society.py``'s driver (which reads ``client.used``) and the
    "touched no LLM" witness (``inner_invocations == 0``) both keep working
    through the wrapper unchanged.
    """

    def __init__(self, inner: RecordReplayChatClient, *, agent_id: str) -> None:
        self._inner = inner
        self._agent_id = agent_id
        self._requests: list[SocietyLlmRequest] = []
        self._samplings: list[ResolvedSampling] = []

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        system_prompt = next((m.content for m in messages if m.role == "system"), "")
        user_prompt = next((m.content for m in messages if m.role == "user"), "")
        self._requests.append(
            SocietyLlmRequest(
                agent_id=self._agent_id,
                window=len(self._requests),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )
        # Recorded, but kept OUT of SocietyLlmRequest on purpose (Codex H-4):
        # the firing annotation consumes it, the conformance check must not.
        self._samplings.append(sampling)
        return await self._inner.chat(
            messages,
            sampling=sampling,
            model=model,
            options=options,
            think=think,
        )

    @property
    def requests(self) -> tuple[SocietyLlmRequest, ...]:
        """``(agent_id, window, system_prompt, user_prompt)`` records, in call order."""
        return tuple(self._requests)

    @property
    def samplings(self) -> tuple[ResolvedSampling, ...]:
        """The per-window sampling the cycle **recomposed**, in call order.

        Deliberately a separate channel from :attr:`requests` — this is the
        knob-modulated value, which differs between a knob-on capture and a
        knob-off replay and therefore must never enter the conformance
        comparison (:data:`CONFORMANCE_SAMPLING_EXCLUSION_REASON`). Its
        legitimate consumer is the non-gate firing annotation
        (:func:`society_firing_annotation`).
        """
        return tuple(self._samplings)

    @property
    def used(self) -> tuple[Any, ...]:
        return self._inner.used

    @property
    def inner_invocations(self) -> int:
        return self._inner.inner_invocations

    @property
    def is_replay(self) -> bool:
        return self._inner.is_replay


class SocietyRequestConformanceEmbeddingClient:
    """The embedding-channel half of the same request-conformance pin (Codex H-4).

    :class:`~erre_sandbox.integration.embodied.traversal_live.EmbeddingRecordReplayClient`
    replays by position without comparing the requested ``(kind, text)``, so an
    observation-text drift would replay green against vectors recorded for
    different text. This wrapper records what was actually asked for; every
    method delegates — it changes no behaviour, it only observes. Duck-typed to
    the surface the wrapped client exposes (``memory.embedding.EmbeddingClient``
    is untouched).
    """

    def __init__(self, inner: EmbeddingRecordReplayClient) -> None:
        self._inner = inner
        self._requests: list[tuple[str, str]] = []

    @property
    def requests(self) -> tuple[tuple[str, str], ...]:
        """The ``(kind, text)`` pairs actually requested, in call order."""
        return tuple(self._requests)

    @property
    def used(self) -> tuple[RecordedEmbeddingCall, ...]:
        return self._inner.used

    @property
    def inner_invocations(self) -> int:
        return self._inner.inner_invocations

    async def close(self) -> None:
        await self._inner.close()

    async def embed(self, text: str) -> list[float]:
        self._requests.append(("embed", text))
        return await self._inner.embed(text)

    async def embed_query(self, text: str) -> list[float]:
        self._requests.append(("embed_query", text))
        return await self._inner.embed_query(text)

    async def embed_document(self, text: str) -> list[float]:
        self._requests.append(("embed_document", text))
        return await self._inner.embed_document(text)

    async def embed_many(self, texts: Sequence[str], *, kind: str) -> list[list[float]]:
        call_kind = "embed_query" if kind == "query" else "embed_document"
        self._requests.extend((call_kind, text) for text in texts)
        return await self._inner.embed_many(texts, kind=cast("Any", kind))


# --------------------------------------------------------------------------- #
# Plane G replay driver (UNMODIFIED ``run_society_loop``, knob-off)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyPlaneGReplay:
    """One Plane G replay's outcome (construction only, no ``verdict`` field)."""

    result: SocietyRunResult
    llm_requests: tuple[SocietyLlmRequest, ...]
    """Every recomposed request, ordered by ``(agent_id, window)``."""
    samplings_per_agent: Mapping[str, tuple[ResolvedSampling, ...]]
    """Per-agent recomposed sampling — the firing annotation's input, never the
    conformance comparison's (Codex H-4)."""
    embedding_requests: tuple[tuple[str, str], ...]
    embedding_used: tuple[RecordedEmbeddingCall, ...]
    llm_inner_invocations: Mapping[str, int]
    """Per-agent count of real inner-LLM calls — ``0`` for every agent on a
    genuine replay (nothing reached a backend)."""
    embedding_inner_invocations: int


def recorded_llm_from_capture(
    capture: SocietyRunResult,
) -> dict[str, tuple[RecordedLlmCall, ...]]:
    """The per-agent committed Plane 2 stream, in ``agent_tick`` order."""
    return {
        agent_id: tuple(d.call for d in capture.decisions[agent_id])
        for agent_id in sorted(capture.decisions)
    }


async def replay_society_plane_g(
    *,
    recorded_llm: Mapping[str, Sequence[RecordedLlmCall]],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    ledger: Sequence[_LedgerRow],
    store: MemoryStore,
    agent_states: Sequence[AgentState],
    personas: Mapping[str, PersonaSpec],
    run_id: str,
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    two_phase_knob: TwoPhaseKnob | None = None,
) -> SocietyPlaneGReplay:
    """Replay a committed society capture through the **unmodified** driver.

    Plane G (design-final.md §5): committed ledger →
    :func:`ledger_observation_factories` → **unmodified**
    ``society.py::run_society_loop`` with replay clients,
    ``self_other_enabled=True`` and ``two_phase_knob=None`` (knob-off) → the
    same ``ecl_trace_checksum`` / ``event_log_checksum`` the capture produced.

    **Why knob-off replays a knob-on capture byte-identically** (the ADR's §3
    key 5, restated here because it is the whole reason this function may pass
    ``two_phase_knob=None`` against a knob-on record): on replay,
    ``RecordReplayChatClient`` serves the **committed** call and appends that
    committed record to ``used`` — the driver's decision records, and therefore
    the plan, the resolved destination and the geometry, come from the record,
    not from anything the knob touches. A
    :class:`~erre_sandbox.erre.two_phase.TwoPhaseKnob` modulates only the
    *sampling* term the cognition cycle composes for its next call; it never
    reaches the trajectory. So knob-on and knob-off replays of the same
    committed decisions differ in exactly one observable — the recomposed
    sampling, which is why :func:`society_request_conformance` excludes it and
    :func:`society_firing_annotation` is the thing that reads it. Passing the
    knob here (``two_phase_knob=TwoPhaseKnob()``) is supported for exactly that
    annotation's knob-on arm.

    **Both channels run behind the conformance spies**, so this replay pins not
    only "the same answers reproduce the checksums" but also "the questions
    asked were the committed ones" (Codex H-4).

    ``store`` is the caller's (a fresh in-memory store per replay is the usual
    shape) — this function owns no store lifecycle. The embedding replay client
    is built internally from ``recorded_embedding`` and opens no connection.
    """
    agent_ids = tuple(state.agent_id for state in agent_states)
    spies = {
        agent_id: SocietyRequestConformanceChatClient(
            RecordReplayChatClient(recorded=tuple(recorded_llm[agent_id])),
            agent_id=agent_id,
        )
        for agent_id in agent_ids
    }
    embedding_spy = SocietyRequestConformanceEmbeddingClient(
        EmbeddingRecordReplayClient(recorded=recorded_embedding)
    )
    result = await run_society_loop(
        run_id=run_id,
        store=store,
        embedding=cast("EmbeddingClient", embedding_spy),
        llms=cast("Mapping[str, RecordReplayChatClient]", spies),
        agent_states=agent_states,
        personas=personas,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        k_ecl=k_ecl,
        reflector=reflector,
        observation_factories=ledger_observation_factories(ledger, agent_ids=agent_ids),
        self_other_enabled=True,
        two_phase_knob=two_phase_knob,
    )
    ordered_agent_ids = sorted(spies)
    return SocietyPlaneGReplay(
        result=result,
        llm_requests=tuple(
            request
            for agent_id in ordered_agent_ids
            for request in spies[agent_id].requests
        ),
        samplings_per_agent={
            agent_id: spies[agent_id].samplings for agent_id in ordered_agent_ids
        },
        embedding_requests=embedding_spy.requests,
        embedding_used=embedding_spy.used,
        llm_inner_invocations={
            agent_id: spies[agent_id].inner_invocations
            for agent_id in ordered_agent_ids
        },
        embedding_inner_invocations=embedding_spy.inner_invocations,
    )


# --------------------------------------------------------------------------- #
# Byte-parity witness + request conformance (boolean / count only)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyPlaneGPins:
    """The committed values a Plane G replay must reproduce.

    Extracted as its own bundle so the witness works identically for an
    in-process capture (:func:`society_plane_g_pins`) and for a committed
    on-disk bundle (a manifest's pinned checksums), without the witness itself
    depending on either source.
    """

    geometry_checksum: str
    event_log_checksum: str
    cognition_step_order: tuple[str, ...]
    self_other_observation_input: SelfOtherObservationInput


def society_plane_g_pins(capture: SocietyRunResult) -> SocietyPlaneGPins:
    """Read the Plane G pins off an in-process capture."""
    return SocietyPlaneGPins(
        geometry_checksum=capture.checksum,
        event_log_checksum=capture.event_log_checksum,
        cognition_step_order=tuple(capture.cognition_step_order),
        self_other_observation_input=capture.self_other_observation_input,
    )


def society_plane_g_parity(
    *,
    pins: SocietyPlaneGPins,
    replay: SocietyPlaneGReplay,
) -> dict[str, Any]:
    """Pure boolean witness of Plane G byte-parity (design-final.md §6 W-N4).

    Compares the committed pins against what the **unmodified** driver produced
    on replay. Every entry is a boolean or a checksum string; no magnitude,
    distance, floor, score or verdict is computed, and ``verdict`` is an
    explicit ``None``.

    ``replay_touched_no_llm`` folds both channels' ``inner_invocations`` — a
    replay that reached a real backend would be reproducing nothing.

    **Scope (Codex M-3, binding)**: the parity claimed here is over the
    *scripted in-process perturbation sequence* only. Real Godot frames, real
    WebSocket arrival times and real LLM latency are external non-determinism
    sources outside the replay set; this is not a wall-clock real-time session
    and this witness does not claim one.
    """
    llm_inner_total = sum(
        replay.llm_inner_invocations[agent_id]
        for agent_id in sorted(replay.llm_inner_invocations)
    )
    return {
        "geometry_checksum_committed": pins.geometry_checksum,
        "geometry_checksum_replayed": replay.result.checksum,
        "geometry_checksum_match": pins.geometry_checksum == replay.result.checksum,
        "event_log_checksum_committed": pins.event_log_checksum,
        "event_log_checksum_replayed": replay.result.event_log_checksum,
        "event_log_checksum_match": (
            pins.event_log_checksum == replay.result.event_log_checksum
        ),
        "cognition_step_order_match": (
            pins.cognition_step_order == tuple(replay.result.cognition_step_order)
        ),
        "self_other_slot_match": (
            pins.self_other_observation_input
            == replay.result.self_other_observation_input
        ),
        "self_other_slot_present": pins.self_other_observation_input is not None,
        "llm_inner_invocations": dict(sorted(replay.llm_inner_invocations.items())),
        "embedding_inner_invocations": replay.embedding_inner_invocations,
        "replay_touched_no_llm": (
            llm_inner_total == 0 and replay.embedding_inner_invocations == 0
        ),
        "verdict": None,
        "note": (
            "Plane G byte-parity witness (construction, non-gate annotation "
            "shape): booleans over committed-vs-replayed checksums, the "
            "cognition step order and the run-level self-other slot, plus the "
            "'no backend was touched' counters. Scoped to the SCRIPTED "
            "in-process perturbation sequence (Codex M-3): real Godot frames, "
            "real WebSocket arrival times and real LLM latency are external "
            "non-determinism sources outside the replay set -- this is not a "
            "wall-clock real-time session. No effect, divergence, floor, "
            "scorer or verdict is computed."
        ),
    }


CONFORMANCE_COMPARED_FIELDS: Final[tuple[str, ...]] = (
    "agent_id",
    "window",
    "system_prompt",
    "user_prompt",
)
"""The request identity :func:`society_request_conformance` compares (Codex H-4)."""

CONFORMANCE_EXCLUDED_FIELDS: Final[tuple[str, ...]] = ("sampling",)
"""Fields deliberately kept OUT of the conformance comparison (Codex H-4)."""

CONFORMANCE_SAMPLING_EXCLUSION_REASON: Final[str] = (
    "sampling is excluded from request conformance on purpose (Codex H-4): a "
    "knob-on capture is replayed through a knob-off unmodified run_society_loop, "
    "and a TwoPhaseKnob modulates exactly the sampling term the cognition cycle "
    "recomposes -- so the two sides legitimately differ there while every other "
    "part of the request must match. The knob-on sampling is pinned separately, "
    "as a NON-GATE annotation, by the unmodified two_phase_firing_summary's "
    "record_knob_on_pinned field."
)
"""Spelled out as a module constant so the exclusion is explicit in the
artifact, in the API surface and in the test that reads it — never an
undocumented omission."""


def committed_llm_requests(
    recorded_llm: Mapping[str, Sequence[RecordedLlmCall]],
) -> tuple[SocietyLlmRequest, ...]:
    """The committed request identities, ordered by ``(agent_id, window)``.

    ``window`` is the ordinal within that agent's own committed stream, which is
    ``agent_tick`` (``society.py`` commits exactly one call per agent per
    window, in increasing window order).
    """
    return tuple(
        SocietyLlmRequest(
            agent_id=agent_id,
            window=window,
            system_prompt=call.system_prompt,
            user_prompt=call.user_prompt,
        )
        for agent_id in sorted(recorded_llm)
        for window, call in enumerate(recorded_llm[agent_id])
    )


def _first_llm_drift(
    actual: Sequence[SocietyLlmRequest],
    expected: Sequence[SocietyLlmRequest],
) -> dict[str, Any] | None:
    """First differing request, as a locating record (``None`` when identical)."""
    for index in range(max(len(actual), len(expected))):
        if index >= len(actual):
            return {"index": index, "reason": "missing_on_replay_side"}
        if index >= len(expected):
            return {"index": index, "reason": "missing_in_committed_record"}
        got, want = actual[index], expected[index]
        if got == want:
            continue
        return {
            "index": index,
            "reason": "field_mismatch",
            "agent_id": want.agent_id,
            "window": want.window,
            "fields": [
                field
                for field in CONFORMANCE_COMPARED_FIELDS
                if getattr(got, field) != getattr(want, field)
            ],
        }
    return None


def _first_embedding_drift(
    actual: Sequence[tuple[str, str]],
    expected: Sequence[tuple[str, str]],
) -> dict[str, Any] | None:
    """First differing ``(kind, text)`` embedding request (``None`` when identical)."""
    for index in range(max(len(actual), len(expected))):
        if index >= len(actual):
            return {"index": index, "reason": "missing_on_replay_side"}
        if index >= len(expected):
            return {"index": index, "reason": "missing_in_committed_record"}
        if actual[index] != expected[index]:
            return {
                "index": index,
                "reason": "field_mismatch",
                "kind_matches": actual[index][0] == expected[index][0],
            }
    return None


def society_request_conformance(
    *,
    replay: SocietyPlaneGReplay,
    recorded_llm: Mapping[str, Sequence[RecordedLlmCall]],
    committed_embedding_requests: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """Compare the replay's **recomposed** requests against the committed record.

    The N-agent version of ``scripts/m13_live_loop_capture.py``'s
    ``_request_conformance_checks`` (Codex H-4): keyed on
    :data:`CONFORMANCE_COMPARED_FIELDS` — ``(agent_id, window, system_prompt,
    user_prompt)`` — with :data:`CONFORMANCE_EXCLUDED_FIELDS` (``sampling``)
    explicitly out, for the reason spelled out in
    :data:`CONFORMANCE_SAMPLING_EXCLUSION_REASON`.

    **Why this is not tautological**: the ``actual`` side comes from the
    replay-side spy (:class:`SocietyRequestConformanceChatClient`) — the prompts
    the cognition cycle *rebuilt* from persona, store, retrieval and this
    replay's observations — while the ``expected`` side is the committed
    ``RecordedLlmCall``. Comparing ``result.decisions[*].call`` instead would
    compare the committed record against itself, since an ordinal replay client
    re-serves and re-commits exactly what it was given. A drift on either side
    (a changed committed prompt, or a changed observation feed that makes the
    cycle recompose a different prompt) turns ``llm_requests_match`` ``False``
    while the ordinal replay still reproduces the geometry checksum — which is
    precisely the failure mode this check exists to catch.

    The self-other segment breakdown reads society's own render contract via
    :func:`self_other_segment_contract` (never a copied literal), so a change to
    ``society.py``'s mirror render moves this reader with it.

    Boolean / count / locating-record only; ``verdict`` is an explicit ``None``
    and nothing here is an effect, a score or a measurement.
    """
    expected = committed_llm_requests(recorded_llm)
    actual = replay.llm_requests
    marker = self_other_segment_marker()
    committed_segments = tuple(
        extract_self_other_segment(request.user_prompt, marker=marker)
        for request in expected
    )
    replayed_segments = tuple(
        extract_self_other_segment(request.user_prompt, marker=marker)
        for request in actual
    )
    return {
        "compared_fields": list(CONFORMANCE_COMPARED_FIELDS),
        "excluded_fields": list(CONFORMANCE_EXCLUDED_FIELDS),
        "excluded_fields_reason": CONFORMANCE_SAMPLING_EXCLUSION_REASON,
        "llm_request_count_replayed": len(actual),
        "llm_request_count_committed": len(expected),
        "llm_requests_match": list(actual) == list(expected),
        "llm_first_drift": _first_llm_drift(actual, expected),
        "self_other_segment_marker": marker,
        "self_other_segment_present_count_committed": sum(
            1 for segment in committed_segments if segment
        ),
        "self_other_segments_match": committed_segments == replayed_segments,
        "embedding_request_count_replayed": len(replay.embedding_requests),
        "embedding_request_count_committed": len(committed_embedding_requests),
        "embedding_requests_match": (
            list(replay.embedding_requests) == list(committed_embedding_requests)
        ),
        "embedding_first_drift": _first_embedding_drift(
            replay.embedding_requests, committed_embedding_requests
        ),
        "verdict": None,
        "note": (
            "request conformance witness (construction wiring, non-gate "
            "annotation shape): the replay-side spy's recomposed "
            "(agent_id, window, system_prompt, user_prompt) records and "
            "(kind, text) embedding requests compared against the committed "
            "record. sampling is EXCLUDED by design -- see "
            "excluded_fields_reason. This checks that the questions asked on "
            "replay were the committed ones; it is NOT a measurement of any "
            "effect, and a matching request set says nothing about behaviour, "
            "divergence or detectability."
        ),
    }


# --------------------------------------------------------------------------- #
# Determinism guard (design-final.md §5 table — AST-mechanical, negative-fixture
# testable; never a "return True" inspection)
# --------------------------------------------------------------------------- #

NONDETERMINISTIC_CALL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "choice",
        "choices",
        "getrandbits",
        "monotonic",
        "now",
        "perf_counter",
        "randint",
        "random",
        "sample",
        "shuffle",
        "time",
        "today",
        "uniform",
        "urandom",
        "utcnow",
        "uuid1",
        "uuid3",
        "uuid4",
        "uuid5",
    }
)
"""Callee names that would introduce a fresh non-determinism source.

Matched on the call's own name (``uuid.uuid4()`` and a bare ``uuid4()`` both
match ``uuid4``), which is what makes the scan import-style agnostic. The
``datetime(2026, 1, 1, tzinfo=UTC)`` *constructor* is deliberately absent: a
fixed literal timestamp is the pin, ``datetime.now()`` is the leak."""

UNSORTED_ITERATION_METHODS: Final[frozenset[str]] = frozenset(
    {"items", "keys", "values"}
)
"""Mapping views whose iteration order this module must not depend on."""

UNSORTED_ITERATION_BUILTINS: Final[frozenset[str]] = frozenset({"frozenset", "set"})
"""Builtins whose iteration order is hash-seeded, i.e. never a stable order."""

ORDERING_WRAPPERS: Final[frozenset[str]] = frozenset({"sorted"})
"""Calls that make the iteration they wrap deterministic."""


@dataclass(frozen=True, slots=True)
class NondeterminismFinding:
    """One flagged construct, with enough detail to locate and fix it."""

    kind: str
    """``"nondeterministic_call"`` or ``"unsorted_iteration"``."""
    name: str
    lineno: int


def _called_name(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _iteration_source(node: ast.AST) -> ast.expr | None:
    if isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
        return node.iter
    return None


def _unsorted_iteration_label(iter_node: ast.expr) -> str | None:
    if isinstance(iter_node, ast.Set):
        return "set-literal"
    if not isinstance(iter_node, ast.Call):
        return None
    func = iter_node.func
    if isinstance(func, ast.Attribute):
        return f".{func.attr}()" if func.attr in UNSORTED_ITERATION_METHODS else None
    if isinstance(func, ast.Name):
        if func.id in ORDERING_WRAPPERS:
            return None
        return f"{func.id}()" if func.id in UNSORTED_ITERATION_BUILTINS else None
    return None


def scan_nondeterminism_sources(source: str) -> tuple[NondeterminismFinding, ...]:
    """AST-scan ``source`` for the non-determinism sources §5 forbids in the live root.

    Mechanical, not a review checklist: it parses the source and flags
    (a) any call whose callee name is in :data:`NONDETERMINISTIC_CALL_NAMES`
    (``uuid4`` / ``datetime.now`` / ``time.time`` / ``random.*`` …), and (b) any
    ``for`` / ``async for`` / comprehension that iterates a mapping view
    (:data:`UNSORTED_ITERATION_METHODS`), a ``set()`` / ``frozenset()`` call or a
    set literal without a :data:`ORDERING_WRAPPERS` wrapper.

    Deliberately **syntactic**, with the two consequences named honestly: it
    cannot see a non-determinism source that arrives through an alias or a
    dynamic attribute (``getattr(datetime, "now")()``), and it flags an unsorted
    iteration whose result happens to be order-insensitive. The second is the
    safe direction — the live root simply sorts — and the first is why this
    guard is one instrument among the module's byte-parity checks, never the
    whole determinism argument.

    Returns findings sorted by ``(lineno, kind, name)`` so the output itself is
    deterministic. An empty tuple means "nothing flagged" — and the paired
    negative fixture in the test suite is what shows that an empty tuple is a
    result rather than the only thing this function can produce.
    """
    tree = ast.parse(source)
    findings: list[NondeterminismFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _called_name(node.func)
            if name in NONDETERMINISTIC_CALL_NAMES:
                findings.append(
                    NondeterminismFinding(
                        kind="nondeterministic_call", name=name, lineno=node.lineno
                    )
                )
        iter_node = _iteration_source(node)
        if iter_node is not None:
            label = _unsorted_iteration_label(iter_node)
            if label is not None:
                findings.append(
                    NondeterminismFinding(
                        kind="unsorted_iteration",
                        name=label,
                        lineno=iter_node.lineno,
                    )
                )
    return tuple(sorted(findings, key=lambda f: (f.lineno, f.kind, f.name)))


def live_root_source() -> str:
    """This module's own source text (the determinism guard's subject)."""
    return Path(__file__).read_text(encoding="utf-8")


def live_root_nondeterminism_findings() -> tuple[NondeterminismFinding, ...]:
    """Run :func:`scan_nondeterminism_sources` over the live root itself."""
    return scan_nondeterminism_sources(live_root_source())


# --------------------------------------------------------------------------- #
# Firing annotation (NON-GATE) — per-agent, unmodified ``two_phase_firing_summary``
# --------------------------------------------------------------------------- #


def society_firing_annotation(
    *,
    knob_on: SocietyPlaneGReplay,
    knob_off: SocietyPlaneGReplay,
    recorded_llm: Mapping[str, Sequence[RecordedLlmCall]],
) -> dict[str, Any]:
    """Per-agent firing annotation via the **unmodified** organ summary (non-gate).

    Pure function of two already-run replays of the SAME committed decisions —
    one with a :class:`~erre_sandbox.erre.two_phase.TwoPhaseKnob`, one without —
    whose per-agent recomposed sampling
    (:attr:`SocietyPlaneGReplay.samplings_per_agent`) is handed straight to
    :func:`~erre_sandbox.integration.embodied.two_phase_live.two_phase_firing_summary`
    **without modification**. The society path needs no new summary: exactly one
    action-LLM call is committed per ``(agent, window)`` and the driver steps
    agents sequentially in ``sorted(agent_id)`` order, so each agent's spied
    sampling sequence is unambiguously that agent's own per-window series — the
    single-agent summary applies per agent verbatim.

    **firing ≠ detectability (binding, design-final.md §2/§6)**: a fired sign
    inversion says the knob reached the sampling the cycle composed. It says
    nothing about whether any behaviour, zone, utterance or "aha" changed —
    that is the frozen second link and is deliberately not computed here.
    This annotation is therefore **not a gate**: ``hard_gate`` is ``False``,
    ``verdict`` is an explicit ``None``, and ``eligible`` / ``witness`` are
    plain counts with no threshold, rate or ratio attached. A run where no
    agent moved (λ stays 0, ``fail_mode="no_eligible_tick"``) is a legitimate
    outcome recorded as-is, never retried toward firing.
    """
    agent_ids = sorted(recorded_llm)
    per_agent: dict[str, dict[str, Any]] = {
        agent_id: two_phase_firing_summary(
            on_samplings=knob_on.samplings_per_agent[agent_id],
            off_samplings=knob_off.samplings_per_agent[agent_id],
            on_checksum=knob_on.result.checksum,
            off_checksum=knob_off.result.checksum,
            committed_call_samplings=[call.sampling for call in recorded_llm[agent_id]],
        )
        for agent_id in agent_ids
    }
    eligible_tick_count = sum(
        int(per_agent[agent_id]["eligible_tick_count"]) for agent_id in agent_ids
    )
    witness_tick_count = sum(
        int(per_agent[agent_id]["witness_tick_count"]) for agent_id in agent_ids
    )
    agents_with_witness_tick = sum(
        1 for agent_id in agent_ids if per_agent[agent_id]["witness_tick_count"] >= 1
    )
    return {
        "agent_ids": list(agent_ids),
        "n_agents": len(agent_ids),
        "per_agent": per_agent,
        "eligible_tick_count": eligible_tick_count,
        "witness_tick_count": witness_tick_count,
        "agents_with_witness_tick_count": agents_with_witness_tick,
        "hard_gate": False,
        "verdict": None,
        "note": (
            "per-agent firing annotation (NON-GATE, side annotation, outside "
            "every checksum/SHA/Done set): plain counts of the knob-on-vs-"
            "knob-off recomposed per-window sampling, produced by the "
            "UNMODIFIED two_phase_firing_summary applied per agent. firing != "
            "detectability -- a fired sign inversion means the knob reached "
            "the composed sampling, NOT that any behaviour, zone, utterance "
            "or 'aha' changed; that second link is frozen and is not computed. "
            "No threshold, rate, ratio, floor, scorer or verdict; a run with "
            "no eligible tick is recorded as-is, never retried toward firing."
        ),
    }


# --------------------------------------------------------------------------- #
# Plane G bundle projection (I7 hands this to disk; the re-quantisation of
# embedded serialised JSON happens HERE, at the projection boundary)
# --------------------------------------------------------------------------- #

PLANE_G_INBOUND_LEDGER_FILENAME: Final[str] = "inbound_ledger.jsonl"
PLANE_G_EMBEDDING_RECORD_FILENAME: Final[str] = "embedding_record.jsonl"


def society_injected_ledger_to_jsonl(ledger: Sequence[_LedgerRow]) -> str:
    """Serialise the injected inbound ledger as canonical JSONL.

    One line per perturbation actually **injected**, in injection order (which
    is drain order, which is push order). ``rejected`` (unknown target) and
    ``dropped`` (sink overflow) rows are deliberately absent: neither ever
    became an observation, so neither is part of the feed a replay must
    reconstruct (Codex M-2's population rule, carried into the artifact).

    ``routed_agent_id`` is committed alongside ``target_agent_id`` because the
    two are exactly what a mis-bucketing bug would make differ — dropping it
    would leave the bundle unable to express the distinction
    (``decisions.md`` DA-SLC-8).
    """
    return "".join(
        canonical_dumps(
            {
                "agent_tick": row.agent_tick,
                "correlation_id": row.msg.correlation_id,
                "routed_agent_id": row.routed_agent_id,
                "msg": row.msg.model_dump(mode="json"),
            }
        )
        + "\n"
        for row in ledger
    )


def society_injected_ledger_from_jsonl(text: str) -> tuple[SocietyLedgerEntry, ...]:
    """Reconstruct the injected ledger from its committed JSONL."""
    entries: list[SocietyLedgerEntry] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        entries.append(
            SocietyLedgerEntry(
                agent_tick=int(data["agent_tick"]),
                correlation_id=str(data["correlation_id"]),
                routed_agent_id=str(data["routed_agent_id"]),
                msg=WorldPerturbationMsg.model_validate(data["msg"]),
            )
        )
    return tuple(entries)


def society_embedding_record_to_jsonl(
    calls: Sequence[RecordedEmbeddingCall],
) -> str:
    """Serialise the embedding Plane 1 record as canonical JSONL."""
    return "".join(
        canonical_dumps(
            {"kind": call.kind, "text": call.text, "vector": list(call.vector)}
        )
        + "\n"
        for call in calls
    )


def society_embedding_record_from_jsonl(
    text: str,
) -> tuple[RecordedEmbeddingCall, ...]:
    """Reconstruct the embedding Plane 1 record from its committed JSONL."""
    calls: list[RecordedEmbeddingCall] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        calls.append(
            RecordedEmbeddingCall(
                kind=data["kind"],
                text=data["text"],
                vector=tuple(data["vector"]),
            )
        )
    return tuple(calls)


def society_recorded_llm_from_jsonl(
    decisions_jsonl: str,
) -> dict[str, tuple[RecordedLlmCall, ...]]:
    """Group a committed society ``decisions.jsonl`` into per-agent replay streams.

    ``handoff.society_decisions_to_jsonl`` writes rows already ordered by
    ``(order_slot, agent_tick)``, so each agent's physical line order IS its
    replay order. The per-row decode **delegates to the unmodified**
    :func:`~erre_sandbox.integration.embodied.handoff.recorded_calls_from_jsonl`
    (which parses the same flat ``decision_to_dict`` payload this wrapper
    unwraps), so a future ``RecordedLlmCall`` schema change has exactly one
    parser to keep in sync.
    """
    by_agent: dict[str, list[str]] = {}
    for line in decisions_jsonl.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_agent.setdefault(str(row["agent_id"]), []).append(
            json.dumps(row["decision"])
        )
    return {
        agent_id: tuple(recorded_calls_from_jsonl("\n".join(by_agent[agent_id])))
        for agent_id in sorted(by_agent)
    }


def society_plane_g_bundle(
    capture: SocietyRunResult,
    *,
    ledger: Sequence[_LedgerRow],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    run_config: dict[str, Any],
    env_pins: dict[str, Any],
) -> dict[str, str]:
    """Render the Plane G bundle: four handoff artifacts + two replay inputs.

    **Float re-quantisation happens here, at the projection boundary
    (``feedback_golden_crossplatform_float_drift``, PR #55/#76's轍)**: the four
    handoff artifacts are produced by the **unmodified**
    :func:`~erre_sandbox.integration.embodied.handoff.render_society_golden`,
    whose ``decisions.jsonl`` path routes every ``envelope_provenance`` entry
    through ``handoff``'s own ``_quantize_embedded_json`` — the helper that
    parses each *pre-serialised* ``ControlEnvelope.model_dump_json`` string,
    quantises the floats **inside** it and re-dumps. That step is not
    decoration: a raw ``model_dump_json`` string's floats are *text*, so the
    surrounding canonicaliser's blanket 6-decimal rule cannot see them, and a
    Windows-baked bundle would diverge from a Linux one on the drift-prone
    kinematic position while ``ecl_trace.jsonl`` agreed. This function
    deliberately does not re-implement that projection; it reuses it, so the
    bundle and ``event_log_checksum`` stay on the same serializer.

    The two extra files are this closure's own replay inputs — the injected
    inbound ledger and the embedding Plane 1 record — which the four-artifact
    handoff shape has no slot for.
    """
    rendered = dict(
        render_society_golden(capture, run_config=run_config, env_pins=env_pins)
    )
    rendered[PLANE_G_INBOUND_LEDGER_FILENAME] = society_injected_ledger_to_jsonl(ledger)
    rendered[PLANE_G_EMBEDDING_RECORD_FILENAME] = society_embedding_record_to_jsonl(
        recorded_embedding
    )
    return rendered


__all__ = [
    "COGNITION_ENVELOPE_KINDS",
    "CONFORMANCE_COMPARED_FIELDS",
    "CONFORMANCE_EXCLUDED_FIELDS",
    "CONFORMANCE_SAMPLING_EXCLUSION_REASON",
    "DEFAULT_MAX_DRAIN_PER_TICK",
    "DEFAULT_QUIESCE_MAX_ROUNDS",
    "DEFAULT_QUIESCE_STABLE_ROUNDS",
    "DIALOG_ENVELOPE_KINDS",
    "EXCLUDED_ENVELOPE_KINDS",
    "LIVE_ROOT_MODULE",
    "NONDETERMINISTIC_CALL_NAMES",
    "ORDERING_WRAPPERS",
    "PLANE_G_EMBEDDING_RECORD_FILENAME",
    "PLANE_G_INBOUND_LEDGER_FILENAME",
    "RECORD_MODE_WALL_CLOCK",
    "UNSORTED_ITERATION_BUILTINS",
    "UNSORTED_ITERATION_METHODS",
    "CommittedSelfOtherSegment",
    "NondeterminismFinding",
    "SocietyBroadcastLedger",
    "SocietyInboundLedger",
    "SocietyInboundRouter",
    "SocietyInjectedPerturbation",
    "SocietyLedgerEntry",
    "SocietyLiveRunResult",
    "SocietyLiveWorldInput",
    "SocietyLlmRequest",
    "SocietyPlaneGPins",
    "SocietyPlaneGReplay",
    "SocietyRequestConformanceChatClient",
    "SocietyRequestConformanceEmbeddingClient",
    "build_society_live_world",
    "committed_llm_requests",
    "committed_self_other_segments",
    "extract_self_other_segment",
    "ledger_observation_factories",
    "live_root_nondeterminism_findings",
    "live_root_source",
    "recorded_llm_from_capture",
    "replay_society_plane_g",
    "run_society_live_loop",
    "scan_nondeterminism_sources",
    "self_other_segment_contract",
    "self_other_segment_marker",
    "society_embedding_record_from_jsonl",
    "society_embedding_record_to_jsonl",
    "society_firing_annotation",
    "society_injected_ledger_from_jsonl",
    "society_injected_ledger_to_jsonl",
    "society_ledger_entries",
    "society_live_gateway_lifespan_serve",
    "society_live_loop_perturbation_plan",
    "society_mirror_wiring_summary",
    "society_plane_g_bundle",
    "society_plane_g_parity",
    "society_plane_g_pins",
    "society_recorded_llm_from_jsonl",
    "society_request_conformance",
    "society_wiring_reachability_summary",
    "spy_inject_envelope_callers",
    "supervise_society_live_loop",
]
