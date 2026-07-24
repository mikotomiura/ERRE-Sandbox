"""M13 live-loop closure composition root — Issues 003/006 (construction).

FROZEN ADR ``.steering/20260724-m13-live-loop-closure/design-final.md``
(§3 DA-1 / DA-3, §4 Allowed Files). This module is the **closure-only**
composition root that connects the bounded inbound face
(``integration/inbound.py``'s :class:`~erre_sandbox.integration.inbound.InboundSink`
+ :func:`~erre_sandbox.integration.inbound.world_perturbation_to_perception`,
Issue 001/002) to a **knob-on** :class:`~erre_sandbox.cognition.CognitionCycle`
driven the same tick-synchronous way ``two_phase_live.run_two_phase_capture``
drives a knob-on cycle — except this driven loop's per-tick observations come
from the inbound sink instead of a fixed ``observation_factory``.

**Honest framing (binding, design-final.md §2)**: this is *wiring*, not
aha / emergence / effect. It imports no ``evidence`` / ``spdm`` /
``runningness`` machinery and computes/emits no floor / landscape / verdict /
divergence / magnitude / detectability / aha-proxy statistic. Production
``bootstrap.py`` is **untouched** — it never constructs a knob-on cycle and
never passes an ``inbound_sink`` to ``make_app``, so the production
observational identity (knob-less, inbound-ignoring) is unaffected by this
module's mere existence. This is a **live-loop root only**: a *separate*
process entry a developer would run deliberately to observe the knob fire in
a real-time session, never something ``bootstrap()`` reaches.

**organ / ``world/tick.py`` 無改変 (Option A)**: every organ symbol here is
imported and driven, never copied — including the two small closures
(:class:`~erre_sandbox.integration.embodied.loop._SinkContext`,
:func:`~erre_sandbox.integration.embodied.loop._build_decision`) that this
module imports directly from the sibling driver's module (``loop.py``)
rather than re-implementing; ``two_phase_live.run_two_phase_capture`` is the
one that actually copies them (its module docstring, Codex HIGH-3), and this
module reuses that already-audited copy by import. The knob
injection point is :class:`~erre_sandbox.cognition.CognitionCycle`'s
``two_phase_knob`` constructor keyword (``cycle.py:448``); the world seam is
:meth:`~erre_sandbox.world.WorldRuntime.step_cognition_once` (``tick.py:1706``),
the **public** seam that calls the same private ``_step_one`` /
``_consume_result`` pair the sibling driver calls directly — using the public
seam here (rather than reaching into the private pair, as the sibling driver
does) is a deliberate, behaviourally-identical substitution: ``step_cognition_once``
IS ``_step_one`` immediately followed by ``_consume_result``, nothing else, so
the fidelity contract below still holds byte-for-byte.

**Outbound is single-owner (HIGH-1, binding)**: :meth:`WorldRuntime.step_cognition_once`
already enqueues ``result.envelopes`` into ``WorldRuntime._envelopes`` via
``_consume_result`` (``tick.py:1807-1832``, ``_enqueue_with_drop_oldest``) —
the gateway's ``_broadcaster`` task drains that same queue
(:meth:`~erre_sandbox.world.WorldRuntime.drain_envelopes`) to fan out to
Godot. **This module never calls
:meth:`~erre_sandbox.world.WorldRuntime.inject_envelope`** — doing so would
re-enqueue the tick's envelopes a second time (double-send). The driven loop
below is read-only with respect to outbound: it drives cognition forward and
lets the existing enqueue path do its one and only job.

**correlation-id is a loop-owned trace ledger, not a widened schema (grill
G2)**: :class:`InjectedPerturbation` records which
:class:`~erre_sandbox.schemas.WorldPerturbationMsg` (and its
``correlation_id``) was injected into which cognition tick. Neither
:class:`~erre_sandbox.schemas.PerceptionEvent` nor
:class:`~erre_sandbox.schemas.MoveMsg` gains a new field — the reachability
bookkeeping lives entirely in this module's own capture ledger.

Scope guard (design-final.md §2/§7, binding, mirrors ``two_phase_live.py`` /
``traversal_live.py``). This is a **construction** apparatus, **NOT a
measurement line — verdict は holding**. The only observables this module
produces are: (a) the reproducibility checksum
(:func:`~erre_sandbox.integration.embodied.loop.ecl_trace_checksum`, proves
byte-identical re-drive, not a metric), (b) the plain injected-perturbation
/ move-envelope *counts* a caller's boolean acceptance check (Issue 003 AC2)
reads directly off :meth:`~erre_sandbox.world.WorldRuntime.drain_envelopes`,
and (c) :func:`wiring_reachability_summary` (Issue 006, W-live) — a pure
boolean/count **reachability** witness ("wiring reached each seam"), never
an effect / caused / aha / divergence / detectability claim.

**Issue 006 (W-live, HIGH-2/grill G2)**: :func:`run_live_loop_capture` now
also records a :class:`TickEnvelopeTrace` per driven tick (every tick, not
only ticks with an injected perturbation) directly off
``step_cognition_once``'s return value, plus a
:attr:`~LiveLoopCaptureResult.rejected` ledger of any drained
``WorldPerturbationMsg`` whose ``target_agent_id`` did not match the driven
agent (Codex TASK-POST MED-2: bounded, never injected).
:func:`wiring_reachability_summary` combines the tick ledger with a
**caller-supplied, already-computed** ``two_phase_live.two_phase_firing_summary``
(imported, never re-implemented — that summary needs a knob-on/knob-off
spied replay of the SAME committed decisions, a concern this module has no
reason to own; only its plain int/list keys are read, its full detail is
never re-embedded, Codex TASK-POST HIGH-1) to assert, per correlation-id,
whether it reached each of the five ADR seams (``perturbation`` →
``perception`` → ``capture`` → ``firing_summary`` →
``same_tick_envelope_observed``), plus a ``no_double_send`` boolean (HIGH-1,
generalized to every envelope kind, Codex TASK-POST MED-1) comparing this
ledger's own per-kind envelope multiset against the actual broadcast queue a
caller drains via ``drain_envelopes()``. **Seam granularity is not uniform**
(Codex TASK-POST HIGH-2): the first three seams are per-correlation, the
last two are tick-level co-occurrence only — correlation-id never reaches
the outbound wire protocol (grill G2), so this witness cannot and does not
claim per-correlation causation past the ``capture`` seam. Reachability is
not causation.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import Counter
from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Any, Final, cast

from erre_sandbox.cognition import BiasFiredEvent, CognitionCycle
from erre_sandbox.cognition.embodiment import K_ECL, EclRecordMode
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    EclReplayError,
    EclRunResult,
    EclTraceRow,
    RecordReplayChatClient,
    _build_decision,
    _SinkContext,
    ecl_trace_checksum,
)
from erre_sandbox.integration.inbound import (
    InboundSink,
    world_perturbation_to_perception,
)
from erre_sandbox.memory import Retriever
from erre_sandbox.world import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping, Sequence
    from datetime import datetime

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.erre.two_phase import TwoPhaseKnob
    from erre_sandbox.integration.embodied.loop import EclDecisionRecord
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import (
        AgentState,
        Observation,
        PerceptionEvent,
        PersonaSpec,
        WorldPerturbationMsg,
        Zone,
    )
    from erre_sandbox.world import Clock

DEFAULT_MAX_DRAIN_PER_TICK: Final[int] = 8
"""Bounded per-tick inbound drain (design-final.md DA-1 step 1, LOW-1 policy).

A plain cap, not a rate/threshold: at most this many queued perturbations are
mapped and injected in a single cognition tick, so one abusive/burst inbound
sender cannot make a single tick's observation set unbounded. Excess messages
simply wait for the next tick's drain (FIFO order preserved by
:meth:`~erre_sandbox.integration.inbound.InboundSink.drain`)."""


# --------------------------------------------------------------------------- #
# DA-3 — knob-on cycle + WorldRuntime construction (organ imported, not copied)
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class LiveLoopWorld:
    """Handle bundling one knob-on :class:`WorldRuntime` + its capture state.

    Returned by :func:`build_live_loop_world`; passed to
    :func:`run_live_loop_capture` (once, or repeatedly to keep driving the
    same world forward) and — separately — ``world`` is the exact object a
    caller hands to
    ``erre_sandbox.integration.gateway.make_app(runtime=handle.world,
    inbound_sink=...)`` so the WebSocket broadcaster and the driven loop
    observe/drive the **same** runtime instance. That shared identity is the
    whole point of the closure: cognition-driven envelopes reach the gateway
    through the ordinary ``drain_envelopes`` path with no second channel.
    """

    world: WorldRuntime
    agent_id: str
    run_id: str
    llm: RecordReplayChatClient
    ctx: _SinkContext
    rows: list[EclTraceRow]
    bias_slot: list[BiasFiredEvent]


def build_live_loop_world(
    *,
    run_id: str,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llm: RecordReplayChatClient,
    agent_state: AgentState,
    persona: PersonaSpec,
    retrieval_now: datetime,
    base_ts: datetime,
    two_phase_knob: TwoPhaseKnob | None,
    seed: int = 0,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    physics_hz: float = 30.0,
    clock: Clock | None = None,
) -> LiveLoopWorld:
    """Construct the knob-on ``CognitionCycle`` + ``WorldRuntime`` (DA-3).

    Mirrors ``two_phase_live.run_two_phase_capture``'s cycle construction
    (``two_phase_live.py:207-217``) field-for-field, so a driven loop built
    here reproduces that sibling's cognition given the same inputs — the ONLY
    difference from that driver is *where each tick's observations come
    from* (an inbound-sink drain here vs. an ``observation_factory`` there;
    see :func:`run_live_loop_capture`). Passing ``two_phase_knob=None``
    reproduces the knob-less organ path exactly (the AC1 fidelity contract,
    Issue 003).

    ``clock`` defaults to ``None`` — :class:`WorldRuntime` then falls back to
    its own ``RealClock()`` default, the correct choice for a genuine
    real-time closure session. Tests that need byte-for-byte determinism
    against a record/replay reference pass an explicit
    ``erre_sandbox.world.ManualClock(start=0.0)`` (matching what
    ``run_two_phase_capture`` hardcodes internally).

    organ (``cognition/cycle.py``, ``world/tick.py``) is imported here, never
    modified — Option A. Single-agent v0 scope, matching every existing
    sibling driver (``run_ecl_loop`` / ``run_two_phase_capture`` /
    ``run_traversal_capture``).
    """
    agent_id = agent_state.agent_id
    ecl_mode = EclRecordMode(
        run_id=run_id,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        k_ecl=k_ecl,
        reflection_disabled=True,
    )
    retriever = Retriever(store, embedding, now_factory=retrieval_now)
    bias_slot: list[BiasFiredEvent] = []
    cycle = CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=cast("Any", llm),
        rng=Random(seed),  # noqa: S311 — determinism seed, not cryptographic
        ecl_mode=ecl_mode,
        bias_sink=bias_slot.append,
        reflector=reflector,
        two_phase_knob=two_phase_knob,
    )
    ctx = _SinkContext()
    order_slot = sorted([agent_id]).index(agent_id)
    rows: list[EclTraceRow] = []

    def sink(
        sink_agent_id: str,
        physics_tick_index: int,
        x: float,
        y: float,
        z: float,
        yaw: float,
        pitch: float,
        zone: Zone,
    ) -> None:
        md = ctx.move
        rows.append(
            EclTraceRow(
                run_id=run_id,
                agent_id=sink_agent_id,
                physics_tick_index=physics_tick_index,
                agent_tick=ctx.agent_tick,
                order_slot=order_slot,
                x=x,
                y=y,
                z=z,
                yaw=yaw,
                pitch=pitch,
                zone=zone,
                resolved_from=md.resolved_from if md is not None else None,
                move_centroid=md.centroid if md is not None else None,
                move_provenance=md.provenance if md is not None else None,
                move_jitter=md.jitter if md is not None else None,
                move_pre_clamp=md.pre_clamp if md is not None else None,
                move_post_clamp=md.post_clamp if md is not None else None,
                move_clamp_fired=md.clamp_fired if md is not None else None,
            )
        )

    world = WorldRuntime(
        cycle=cycle,
        clock=clock,
        physics_hz=physics_hz,
        ecl_trace_sink=sink,
    )
    world.register_agent(agent_state, persona)
    return LiveLoopWorld(
        world=world,
        agent_id=agent_id,
        run_id=run_id,
        llm=llm,
        ctx=ctx,
        rows=rows,
        bias_slot=bias_slot,
    )


# --------------------------------------------------------------------------- #
# DA-1 — driven tick loop (inbound drain -> PerceptionEvent -> step_cognition_once)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class InjectedPerturbation:
    """One inbound perturbation actually injected into one driven cognition tick.

    The loop-owned trace-ledger entry (grill G2): ``correlation_id`` traces a
    ``WorldPerturbationMsg`` to the ``agent_tick`` it was injected into and the
    exact :class:`~erre_sandbox.schemas.PerceptionEvent` the cognition cycle
    actually read — without adding a field to either schema.
    """

    agent_tick: int
    correlation_id: str
    msg: WorldPerturbationMsg
    observation: PerceptionEvent


@dataclass(frozen=True, slots=True)
class TickEnvelopeTrace:
    """One driven tick's emitted-envelope trace (Issue 006 ledger, seam5/HIGH-1).

    Recorded for **every** driven tick (not only ticks that had an injected
    perturbation) directly off ``step_cognition_once``'s return value — the
    SAME ``result.envelopes`` ``_consume_result`` already enqueues into the
    single-owner broadcast queue (module docstring HIGH-1 note). This ledger
    entry is read-only bookkeeping; recording it never touches the broadcast
    queue itself.

    ``envelope_kinds`` (Codex TASK-POST MED-1) stores each emitted envelope's
    ``.kind`` discriminator string, in emission order — a plain-string tuple,
    never the envelope payload itself, so :func:`wiring_reachability_summary`'s
    ``no_double_send`` check can compare a full per-kind multiset (move,
    speech, animation, dialog_turn, error, …) against the real broadcast
    queue instead of only counting ``MoveMsg``.
    """

    agent_tick: int
    envelope_kinds: tuple[str, ...]

    @property
    def envelope_count(self) -> int:
        """Total envelopes emitted this tick, regardless of kind."""
        return len(self.envelope_kinds)


@dataclass(frozen=True, slots=True)
class LiveLoopCaptureResult:
    """One driven-loop drive's outcome: the ECL run + its injected-perturbation ledger.

    ``ecl`` is byte-for-byte the same shape ``run_two_phase_capture`` /
    ``run_ecl_loop`` return (rows / decisions / checksum) — a later issue (I4)
    replays it through the untouched sibling driver via
    :meth:`observation_factory` to confirm the Plane-G regression golden.

    ``ticks`` (Issue 006): one :class:`TickEnvelopeTrace` per driven tick,
    the per-tick envelope-count ledger :func:`wiring_reachability_summary`
    reads for its seam5 / ``no_double_send`` checks.

    ``rejected`` (Codex TASK-POST MED-2, design-final.md DA-2 "bounded 検証
    の閉包"): every drained :class:`~erre_sandbox.schemas.WorldPerturbationMsg`
    whose ``target_agent_id`` did NOT match the driven agent — dropped
    before injection, never turned into a :class:`InjectedPerturbation` /
    :class:`~erre_sandbox.schemas.PerceptionEvent`. Bounded verification, not
    measurement: a plain ledger of what this single-agent v0 drive correctly
    refused to inject, observable as a plain count off
    :func:`wiring_reachability_summary`.
    """

    ecl: EclRunResult
    injected: tuple[InjectedPerturbation, ...]
    ticks: tuple[TickEnvelopeTrace, ...]
    rejected: tuple[WorldPerturbationMsg, ...] = ()

    @property
    def checksum(self) -> str:
        """Reproducibility checksum (proves byte-identical re-drive, not a metric)."""
        return self.ecl.checksum

    def observation_factory(self) -> Callable[[int], Sequence[Observation]]:
        """Rebuild a fixed per-tick observation factory from the injected ledger.

        The shape every existing record/replay driver in this package accepts
        (``run_ecl_loop`` / ``run_two_phase_capture``'s ``observation_factory``
        keyword) — so a later issue can replay this capture through the
        untouched sibling driver with no inbound sink involved at all.

        **I4 note**: this factory returns only the inbound-sourced
        ``PerceptionEvent``s captured in ``injected`` — it does NOT include
        observations the physics loop itself generates mid-run
        (``ZoneTransitionEvent`` / ``TemporalEvent`` / ``ProximityEvent``,
        appended to ``rt.pending`` by ``world/tick.py``, never by this
        module). A byte-parity replay must therefore drive the same
        ``run_two_phase_capture`` under the same ``physics_ticks_per_cognition`` /
        agent count / world conditions as the original capture so those
        physics-generated observations are regenerated identically on replay,
        not read back from this factory.
        """
        by_tick: dict[int, list[Observation]] = {}
        for inj in self.injected:
            by_tick.setdefault(inj.agent_tick, []).append(inj.observation)

        def factory(agent_tick: int) -> Sequence[Observation]:
            return tuple(by_tick.get(agent_tick, ()))

        return factory


async def run_live_loop_capture(
    handle: LiveLoopWorld,
    *,
    inbound_sink: InboundSink,
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    max_drain_per_tick: int = DEFAULT_MAX_DRAIN_PER_TICK,
) -> LiveLoopCaptureResult:
    """Drive ``handle`` for ``n_cognition_ticks`` (DA-1 driven tick loop).

    Per cognition tick:

    1. ``inbound_sink.drain(max_drain_per_tick)`` — bounded, FIFO (LOW-1).
    2. Each drained :class:`~erre_sandbox.schemas.WorldPerturbationMsg` whose
       ``target_agent_id`` matches ``handle.agent_id`` maps to a
       :class:`~erre_sandbox.schemas.PerceptionEvent` via
       :func:`~erre_sandbox.integration.inbound.world_perturbation_to_perception`
       and is injected via ``world.inject_observation`` — the exact "world
       stimulus" channel a live LLM already reads observations through. A
       mismatching ``target_agent_id`` (Codex TASK-POST MED-2, design-final.md
       DA-2 "bounded 検証の閉包") is dropped instead — never injected — and
       recorded onto :attr:`LiveLoopCaptureResult.rejected` so a caller can
       observe the drop as a plain count rather than have a stray
       :class:`~erre_sandbox.schemas.PerceptionEvent` silently land on the
       wrong agent's pending queue.
    3. ``await world.step_cognition_once(agent_id)`` — the **public** seam
       (``tick.py:1706``) that runs ``_step_one`` then ``_consume_result`` in
       one call. ``_consume_result`` already enqueues ``result.envelopes``
       into ``world._envelopes`` (``tick.py:1807-1832``) — **this function
       never calls ``world.inject_envelope``**, so outbound stays single-owner
       (HIGH-1: no re-injection, no double-send; Issue 003 AC2).
    4. The tick's served LLM call is read off ``handle.llm.used`` (record or
       replay alike) and folded into an ``EclDecisionRecord`` via the sibling
       driver's own ``_build_decision`` helper — reused, not re-implemented.
    5. ``physics_ticks_per_cognition`` physics ticks advance the world (the
       ``ecl_trace_sink`` installed by :func:`build_live_loop_world` appends
       one ``EclTraceRow`` per physics tick, exactly as in every sibling
       driver).

    Repeat calls on the same ``handle`` keep appending to ``handle.rows`` /
    the returned decisions start a fresh tick range from 0 each call — this
    function does not track a running tick offset across calls (Issue 003
    scope: single continuous drive per call, matching every existing sibling
    driver's contract). A caller that wants a longer session simply passes a
    larger ``n_cognition_ticks``.

    **Byte-parity replay note**: because ``agent_tick`` restarts at 0 on every
    call while ``handle.rows`` keeps accumulating, a *reused* ``handle`` across
    multiple calls produces a checksum over the whole accumulated row history,
    not a clean per-call one — ``agent_tick`` values would also collide
    between calls. Byte-parity replay (I4) is only guaranteed for a **single
    call on a freshly built ``handle``**; driving a handle across repeat
    calls is not a supported replay-parity shape.
    """
    world = handle.world
    agent_id = handle.agent_id
    llm = handle.llm
    decisions: list[EclDecisionRecord] = []
    injected: list[InjectedPerturbation] = []
    rejected: list[WorldPerturbationMsg] = []
    tick_traces: list[TickEnvelopeTrace] = []

    for agent_tick in range(n_cognition_ticks):
        handle.ctx.agent_tick = agent_tick
        handle.bias_slot.clear()

        drained = inbound_sink.drain(max_drain_per_tick)
        for msg in drained:
            # Codex TASK-POST MED-2 / DA-2 bounded verification: a
            # WorldPerturbationMsg aimed at some OTHER agent must never be
            # injected onto this single-agent v0 drive's pending queue.
            if msg.target_agent_id != agent_id:
                rejected.append(msg)
                continue
            obs = world_perturbation_to_perception(msg, tick=agent_tick)
            world.inject_observation(agent_id, obs)
            injected.append(
                InjectedPerturbation(
                    agent_tick=agent_tick,
                    correlation_id=msg.correlation_id,
                    msg=msg,
                    observation=obs,
                )
            )

        used_before = len(llm.used)
        # Public seam: _step_one (pending drain -> cognition) + _consume_result
        # (state write-back + outbound enqueue) in one call. Outbound is NOT
        # touched again below — see the module docstring's HIGH-1 note.
        result = await world.step_cognition_once(agent_id)
        handle.ctx.move = result.ecl_destination
        # Issue 006 seam5/HIGH-1 ledger: reads result.envelopes (the value
        # _consume_result already enqueued) — never re-touches the broadcast
        # queue itself. envelope_kinds (Codex TASK-POST MED-1) records every
        # emitted envelope's ``.kind``, not just MoveMsg, so
        # wiring_reachability_summary's no_double_send check can cover all
        # kinds.
        tick_traces.append(
            TickEnvelopeTrace(
                agent_tick=agent_tick,
                envelope_kinds=tuple(env.kind for env in result.envelopes),
            )
        )
        served = llm.used[used_before:]
        if len(served) != 1:
            msg_txt = (
                f"live-loop cognition tick {agent_tick} served {len(served)} "
                "action-LLM calls; expected exactly 1 (reflection disabled)"
            )
            raise EclReplayError(msg_txt)
        decisions.append(
            _build_decision(
                agent_tick=agent_tick,
                call=served[0],
                result=result,
                bias_fired=handle.bias_slot[0] if handle.bias_slot else None,
            )
        )
        for _ in range(physics_ticks_per_cognition):
            await world._on_physics_tick()  # noqa: SLF001 — same seam the sibling drivers use

    frozen_rows = tuple(handle.rows)
    ecl = EclRunResult(
        run_id=handle.run_id,
        rows=frozen_rows,
        decisions=tuple(decisions),
        checksum=ecl_trace_checksum(frozen_rows),
    )
    return LiveLoopCaptureResult(
        ecl=ecl,
        injected=tuple(injected),
        ticks=tuple(tick_traces),
        rejected=tuple(rejected),
    )


# --------------------------------------------------------------------------- #
# Issue 006 — W-live reachability witness (boolean/count only, HIGH-2/grill G2)
# --------------------------------------------------------------------------- #


def wiring_reachability_summary(
    capture: LiveLoopCaptureResult,
    *,
    firing_summary: Mapping[str, Any],
    broadcast_envelope_kinds: Sequence[str],
) -> dict[str, Any]:
    """Pure boolean/count wiring-reachability witness (Issue 006, W-live).

    Operates only on ``capture`` (this module's own per-tick trace ledger,
    Issue 003) plus two caller-supplied values — it never re-drives or
    re-measures anything itself:

    * ``firing_summary`` — an **already-computed**
      ``two_phase_live.two_phase_firing_summary`` result (imported, never
      re-implemented here: that summary needs a knob-on/knob-off spied
      replay of the SAME committed decisions, a concern this module has no
      reason to own). This function reads only the plain int/list keys it
      needs (``eligible_tick_count`` / ``witness_tick_count`` / ``per_tick``)
      — it no longer embeds the full result back into its own return value
      (Codex TASK-POST HIGH-1: the per-tick sampling-triple detail
      ``two_phase_firing_summary`` carries is measurement detail this witness
      has no business re-exposing under a reachability-only contract; a
      caller that wants that detail already has ``firing_summary`` in hand —
      it is the same object passed in).
    * ``broadcast_envelope_kinds`` (Codex TASK-POST MED-1) — the ``.kind`` of
      every envelope a caller drained off
      :meth:`~erre_sandbox.world.WorldRuntime.drain_envelopes` after the
      drive (the real broadcast queue), in any order. Comparing the
      *multiset* of these kinds against the ledger's own per-tick
      ``envelope_kinds`` reflection is what can catch a genuine re-injection
      bug (HIGH-1) across **every** envelope kind — not just ``MoveMsg`` —
      since the ledger alone only ever sees what ``step_cognition_once``
      returned, never what a (hypothetical) extra ``inject_envelope`` call
      would add.

    For each correlation-id actually injected
    (:attr:`LiveLoopCaptureResult.injected`), records whether it reached
    each of the five ADR seams (design-final.md DA-4/HIGH-2, Issue 006
    Scope) as a boolean — "wiring reached each seam", never an effect claim.
    **Seam granularity is not uniform (Codex TASK-POST HIGH-2, honest
    framing)**: ``correlation_id`` is a field this module's own
    :class:`~erre_sandbox.schemas.WorldPerturbationMsg` carries — it is never
    copied onto :class:`~erre_sandbox.schemas.PerceptionEvent` or any
    outbound :class:`~erre_sandbox.schemas.ControlEnvelope` member (grill G2:
    correlation-id does not reach the outbound wire protocol). Concretely:

    * ``perturbation`` / ``perception`` / ``capture`` — **per-correlation**:
      the ledger can trace THIS SPECIFIC correlation-id through these three
      seams because it owns the record of which ``msg`` produced which
      ``observation`` at which tick.
    * ``firing_summary`` / ``same_tick_envelope_observed`` — **tick-level
      co-occurrence, not per-correlation causation**: because correlation-id
      never reaches the cognition/outbound seams, all this witness can ever
      observe is that the correlation-id's *injection tick* also has a
      ``two_phase_firing_summary["per_tick"]`` entry / emitted at least one
      envelope — never that THIS correlation-id's stimulus specifically
      caused that entry / envelope (some other concurrent effect could
      equally explain it). If more than one perturbation lands on the same
      tick (``max_drain_per_tick`` > 1), every one of them reads the SAME
      tick-level booleans — this is by construction, not an over-count: the
      claim being made is honestly "the tick co-occurred", not "each
      perturbation individually caused it".

    Field-by-field:

    * ``perturbation`` — the ledger row's own ``msg.correlation_id`` matches
      the row's ``correlation_id`` (this row IS the drained
      :class:`~erre_sandbox.schemas.WorldPerturbationMsg`).
    * ``perception`` — re-applying the SAME pure mapping
      (:func:`~erre_sandbox.integration.inbound.world_perturbation_to_perception`)
      to ``(msg, agent_tick)`` reproduces the recorded observation exactly.
    * ``capture`` — the observation is reconstructable via
      :meth:`LiveLoopCaptureResult.observation_factory` at this tick (the
      exact capture-slot replay contract Issue 004 depends on).
    * ``firing_summary`` — this correlation-id's injection tick appears in
      the reused ``firing_summary["per_tick"]`` (a spied on/off replay
      actually covered this tick) — tick-level, see above.
    * ``same_tick_envelope_observed`` (Codex TASK-POST HIGH-2, renamed from
      ``emitted_envelope`` to name what it actually is) — ``step_cognition_once``
      emitted at least one envelope on this correlation-id's injection tick
      (:class:`TickEnvelopeTrace.envelope_count` > 0) — tick-level
      co-occurrence, see above.

    **Honest framing (binding, design-final.md §2)**: reachability is NOT
    causation. This function computes no floor / verdict / divergence /
    magnitude / detectability / aha-proxy statistic — ``verdict`` is an
    explicit ``None`` marker and no returned key names an effect/causal
    claim (Issue 006 AC4).
    """
    ledger_kind_counts = Counter(
        kind for t in capture.ticks for kind in t.envelope_kinds
    )
    broadcast_kind_counts = Counter(broadcast_envelope_kinds)
    no_double_send = ledger_kind_counts == broadcast_kind_counts

    tick_by_index = {t.agent_tick: t for t in capture.ticks}
    firing_ticks = {row["agent_tick"] for row in firing_summary["per_tick"]}
    factory = capture.observation_factory()

    per_correlation_id: dict[str, dict[str, bool]] = {}
    for inj in capture.injected:
        tick_trace = tick_by_index.get(inj.agent_tick)
        # wall_clock is a per-call default_factory(_utc_now) timestamp
        # (schemas.py _ObservationBase) -- excluded from the re-derivation
        # equality check below, else two structurally-identical
        # PerceptionEvents built microseconds apart would never compare
        # equal (mirrors test_two_phase_live.py's own
        # exclude={"locomotion", "wall_clock"} model_dump precedent).
        rederived = world_perturbation_to_perception(inj.msg, tick=inj.agent_tick)
        seams = {
            "perturbation": inj.msg.correlation_id == inj.correlation_id,
            "perception": inj.observation.model_dump(exclude={"wall_clock"})
            == rederived.model_dump(exclude={"wall_clock"}),
            "capture": inj.observation in factory(inj.agent_tick),
            "firing_summary": inj.agent_tick in firing_ticks,
            "same_tick_envelope_observed": (
                tick_trace is not None and tick_trace.envelope_count > 0
            ),
        }
        seams["all_seams_reached"] = all(seams.values())
        per_correlation_id[inj.correlation_id] = seams

    all_reach = (
        all(seams["all_seams_reached"] for seams in per_correlation_id.values())
        if per_correlation_id
        else False
    )

    return {
        "per_correlation_id": per_correlation_id,
        "all_correlation_ids_reach_all_seams": all_reach,
        "perturbation_count": len(capture.injected),
        "target_agent_mismatch_count": len(capture.rejected),
        "envelope_kind_counts": dict(ledger_kind_counts),
        "no_double_send": no_double_send,
        "eligible_tick_count": firing_summary["eligible_tick_count"],
        "sign_inversion_witness_tick_count": firing_summary["witness_tick_count"],
        "verdict": None,
        "note": (
            "wiring reachability witness (non-gate, side annotation): "
            "boolean per-correlation-id seam-reachability -- 'wiring reached "
            "each seam' -- plus a plain perturbation / envelope-kind / "
            "eligible-tick / target-agent-mismatch count. Reachability is "
            "not causation, and seams 'firing_summary' / "
            "'same_tick_envelope_observed' are TICK-LEVEL co-occurrence, not "
            "per-correlation causation (correlation-id never reaches the "
            "outbound wire protocol, grill G2). This function computes no "
            "floor, magnitude, or statistic beyond these booleans and "
            "counts."
        ),
    }


# --------------------------------------------------------------------------- #
# MEDIUM-2 — same-event-loop TaskGroup supervisor (gateway serve + driven loop)
# --------------------------------------------------------------------------- #


async def supervise_live_loop(
    *,
    handle: LiveLoopWorld,
    inbound_sink: InboundSink,
    gateway_serve: Callable[[], Coroutine[Any, Any, None]],
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    max_drain_per_tick: int = DEFAULT_MAX_DRAIN_PER_TICK,
    on_tasks_scheduled: Callable[[asyncio.Task[None], asyncio.Task[None]], None]
    | None = None,
) -> LiveLoopCaptureResult:
    """Supervise gateway serve + the driven loop in one ``TaskGroup`` (MEDIUM-2).

    ``gateway_serve`` is caller-injected — production wires
    ``functools.partial(uvicorn.Server(uvicorn.Config(make_app(runtime=
    handle.world, inbound_sink=inbound_sink), ...)).serve)``; tests pass a
    lightweight stub coroutine — so this composition root does not hard-code a
    running ASGI server into the construction path Issue 003 tests. Both the
    gateway-serve task and the driven-loop task are created via
    ``asyncio.TaskGroup.create_task`` from *inside the same*
    ``async with asyncio.TaskGroup()`` block, which by construction schedules
    both on ``asyncio.get_running_loop()`` at the point this coroutine is
    awaited — never a second event loop or a background thread. That
    single-loop guarantee is what MEDIUM-2 requires (design-final.md §3
    "同一 event loop の TaskGroup で supervise").

    ``on_tasks_scheduled`` (testing seam, optional): invoked once, immediately
    after both tasks are created, with ``(serve_task, driven_task)`` — lets a
    test assert ``serve_task.get_loop() is driven_task.get_loop()`` directly
    without threading/second-loop tricks (Issue 003 AC4). No production caller
    needs it.

    The driven loop is this supervisor's "work": once it finishes (returns its
    :class:`LiveLoopCaptureResult`), ``gateway_serve``'s task is cancelled —
    ``_serve_until_cancelled`` suppresses the resulting ``CancelledError`` so
    the ``TaskGroup`` exits cleanly instead of propagating a cancellation as a
    failure. A genuine exception from either task still propagates (wrapped in
    an ``ExceptionGroup`` per ``TaskGroup`` semantics) — this function adds no
    swallowing beyond the expected shutdown-cancellation path.
    """
    result_box: list[LiveLoopCaptureResult] = []

    async def _driven() -> None:
        result_box.append(
            await run_live_loop_capture(
                handle,
                inbound_sink=inbound_sink,
                n_cognition_ticks=n_cognition_ticks,
                physics_ticks_per_cognition=physics_ticks_per_cognition,
                max_drain_per_tick=max_drain_per_tick,
            )
        )

    async def _serve_until_cancelled() -> None:
        with contextlib.suppress(asyncio.CancelledError):
            await gateway_serve()

    async with asyncio.TaskGroup() as tg:
        serve_task = tg.create_task(
            _serve_until_cancelled(), name="live-loop-gateway-serve"
        )
        driven_task = tg.create_task(_driven(), name="live-loop-driven")
        if on_tasks_scheduled is not None:
            on_tasks_scheduled(serve_task, driven_task)
        await driven_task
        serve_task.cancel()

    return result_box[0]


__all__ = [
    "DEFAULT_MAX_DRAIN_PER_TICK",
    "InjectedPerturbation",
    "LiveLoopCaptureResult",
    "LiveLoopWorld",
    "TickEnvelopeTrace",
    "build_live_loop_world",
    "run_live_loop_capture",
    "supervise_live_loop",
    "wiring_reachability_summary",
]
