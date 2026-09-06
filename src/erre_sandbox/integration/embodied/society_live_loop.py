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

Later issues (I3+) extend this module with the closure root proper
(``build_society_live_world`` / ``run_society_live_loop`` /
``supervise_society_live_loop`` / ``society_wiring_reachability_summary``,
design-final.md §4) — out of scope here.

**Honest framing (binding, design-final.md §2)**: this is *wiring* /
*construction*, never aha / emergence / effect. Neither piece below imports
``evidence`` / ``spdm`` / ``runningness`` machinery, and neither
computes/emits a floor / landscape / verdict / divergence / magnitude /
detectability / aha-proxy statistic. "N 体が live で相互作用した" would be a
**boolean wiring-reachability claim**, never a social-emergence claim — this
issue does not even reach that witness (I4); it only builds the plumbing a
later witness will read.

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

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, cast

from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
)
from erre_sandbox.integration.inbound import (
    InboundSink,
    world_perturbation_to_perception,
)
from erre_sandbox.schemas import WorldPerturbationMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from erre_sandbox.schemas import Observation, PerceptionEvent

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
    """

    agent_tick: int
    correlation_id: str
    msg: WorldPerturbationMsg
    observation: PerceptionEvent


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


__all__ = [
    "DEFAULT_MAX_DRAIN_PER_TICK",
    "RECORD_MODE_WALL_CLOCK",
    "SocietyInboundLedger",
    "SocietyInboundRouter",
    "SocietyInjectedPerturbation",
    "society_live_loop_perturbation_plan",
]
