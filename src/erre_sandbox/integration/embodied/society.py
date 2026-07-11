"""M2 Layer1 — N-agent record-mode sequential sorted scheduler (Issue 002).

A **construction, not measurement** driver (design-final.md §M0/§M1, binding):
this module registers N agents on one :class:`~erre_sandbox.world.WorldRuntime`
and drives their cognition **sequentially, in ``sorted(order_slot)`` order**,
per cognition window — the N-agent generalisation of ``run_ecl_loop``'s
single-agent direct drive (``integration/embodied/loop.py``, **unmodified,
never imported as a driver** — only its Plane 2 / checksum primitives are
reused: :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`,
:class:`~erre_sandbox.integration.embodied.loop.EclTraceRow`,
:class:`~erre_sandbox.integration.embodied.loop.EclDecisionRecord`,
:func:`~erre_sandbox.integration.embodied.loop.ecl_trace_checksum`).

**Record-mode sequential scheduler (§M4.1, binding)**: within one cognition
window this driver steps each agent **one at a time**, in
``sorted(agent_id)`` order — the ``order_slot`` used throughout — via the new
:meth:`~erre_sandbox.world.tick.WorldRuntime.step_cognition_once` public seam.
``asyncio.gather`` is never used to fan out cognition here (that lives only in
the live wall-clock phase-wheel, ``WorldRuntime._on_cognition_tick``, which
this driver never calls). This removes the shared-store write interleave that
concurrent stepping would otherwise introduce (design §論点/§M4.3 point 4).

**Plane 2 is per-agent keyed (§M6)**: :class:`WorldRuntime` drives exactly one
shared :class:`~erre_sandbox.cognition.CognitionCycle` for every registered
agent (the world seam's existing single-cycle wiring, unchanged here); since
that cycle's LLM client is a single object, :class:`_AgentKeyedChatClient`
routes each ``chat()`` call to the ``RecordReplayChatClient`` "activated" for
the tick currently being stepped. Sequential-only stepping (never two agents
mid-flight at once) makes "the active agent" always unambiguous.

**construction ≠ measurement (§M1/§M8, binding)**: this module computes no
floor / verdict / scorer / divergence and performs no zone/bin/category
aggregation. ``ecl_trace_checksum`` proves reproducibility, not a metric.
``cognition_step_order`` is causal-wiring provenance (which agent stepped
when), not an emergent-behaviour measurement.

Out of scope for this issue (deferred to later I-slices, §M11): the
versioned event/decision-log-wide checksum (I3, geometry checksum here is
the whole of it), the ``self_other_observation_input`` slot (I3), per-pair
named RNG substreams + pair-interaction determinism (I4), handoff N-agent
schema bump (I5), spend AST guard (I6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, Any, cast

from erre_sandbox.cognition import BiasFiredEvent, CognitionCycle, parse_llm_plan
from erre_sandbox.cognition.embodiment import K_ECL, EclRecordMode
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    GOLDEN_COGNITION_TICKS,
    EclDecisionRecord,
    EclReplayError,
    EclTraceRow,
    RecordedLlmCall,
    RecordReplayChatClient,
    ecl_trace_checksum,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import SCHEMA_VERSION, PerceptionEvent, Zone
from erre_sandbox.world import ManualClock, WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime

    from erre_sandbox.cognition import CycleResult
    from erre_sandbox.cognition.embodiment import EclDestination
    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec


# --------------------------------------------------------------------------- #
# Plane 2 — per-agent-keyed chat router (one shared CognitionCycle, N clients)
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _AgentKeyedChatClient:
    """Routes ``chat()`` to the "active" agent's :class:`RecordReplayChatClient`.

    ``WorldRuntime`` drives exactly one shared :class:`CognitionCycle` for
    every registered agent (existing world-seam wiring, unchanged by this
    module); :class:`CognitionCycle` in turn takes exactly one LLM client.
    Per-agent-keyed Plane 2 (§M6) is achieved here, one layer up: the driver
    calls :meth:`activate` immediately before stepping a given agent's
    cognition (:meth:`~erre_sandbox.world.tick.WorldRuntime.step_cognition_once`),
    and this router dispatches the resulting single ``chat()`` call to that
    agent's own :class:`RecordReplayChatClient`. The record-mode sequential
    scheduler (§M4.1) guarantees exactly one agent is ever "active" at a
    time — never two mid-flight concurrently — so there is no ambiguity.
    """

    clients: dict[str, RecordReplayChatClient]
    _active_agent_id: str | None = field(default=None, init=False, repr=False)

    @property
    def active_agent_id(self) -> str | None:
        """The agent_id currently activated, or ``None`` before the first step."""
        return self._active_agent_id

    def activate(self, agent_id: str) -> None:
        """Mark ``agent_id`` as the router's next ``chat()`` destination."""
        if agent_id not in self.clients:
            msg = f"no RecordReplayChatClient registered for agent_id {agent_id!r}"
            raise KeyError(msg)
        self._active_agent_id = agent_id

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        if self._active_agent_id is None:
            msg = "no agent activated on the per-agent chat router before chat()"
            raise EclReplayError(msg)
        client = self.clients[self._active_agent_id]
        return await client.chat(
            messages,
            sampling=sampling,
            model=model,
            options=options,
            think=think,
        )


# --------------------------------------------------------------------------- #
# Default per-agent observation factory (design-copy of loop's private helper)
# --------------------------------------------------------------------------- #


def _default_observation_factory(
    agent_id: str,
) -> Callable[[int], Sequence[Observation]]:
    """One deterministic perception per tick, keyed by ``agent_id`` (§M4.4).

    Design-copy of ``loop._default_observation_factory`` (not imported — that
    name is module-private to ``loop.py``): each agent needs its own factory
    closure so N agents accumulate distinct located memories rather than
    aliasing one shared perception stream.
    """

    def factory(agent_tick: int) -> Sequence[Observation]:
        return [
            PerceptionEvent(
                tick=agent_tick,
                agent_id=agent_id,
                modality="sight",
                source_zone=Zone.STUDY,
                content=f"m2 society forage step {agent_tick}",
                intensity=0.4,
            )
        ]

    return factory


# --------------------------------------------------------------------------- #
# Per-window sink context (design-copy of loop._SinkContext, per-agent keyed)
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _SocietySinkContext:
    """Mutable per-agent, per-window context the trace-sink closure reads."""

    agent_tick: int = 0
    move: EclDestination | None = None


def _build_society_decision(
    *,
    agent_tick: int,
    call: RecordedLlmCall,
    result: CycleResult,
    bias_fired: BiasFiredEvent | None,
) -> EclDecisionRecord:
    """Assemble one agent-tick's Plane 2 record (design-copy of loop's helper)."""
    if call.outcome == "raised":
        plan = None
        llm_status = "raised"
    else:
        plan = parse_llm_plan(call.raw_response)
        llm_status = "ok" if not result.llm_fell_back else "fell_back"
        if plan is None:
            llm_status = "unparseable"
    envelope_provenance = tuple(env.model_dump_json() for env in result.envelopes)
    return EclDecisionRecord(
        agent_tick=agent_tick,
        call=call,
        plan=plan,
        plan_schema_version=SCHEMA_VERSION,
        llm_fell_back=result.llm_fell_back,
        llm_status=llm_status,
        bias_fired=bias_fired,
        move_decision=result.ecl_destination,
        envelope_provenance=envelope_provenance,
    )


# --------------------------------------------------------------------------- #
# Run result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SocietyRunResult:
    """Outcome of one :func:`run_society_loop` drive.

    N-agent generalisation of ``loop.EclRunResult``.
    """

    run_id: str
    rows: tuple[EclTraceRow, ...]
    decisions: Mapping[str, tuple[EclDecisionRecord, ...]]
    checksum: str
    cognition_step_order: tuple[str, ...]
    """The exact agent_id sequence :meth:`~WorldRuntime.step_cognition_once` was
    called in, one entry per (window, agent) step — the causal-wiring witness
    for the record-mode sequential sorted(order_slot) scheduler (§M4.1, I2-G2).
    This is provenance of *when the driver stepped whom*, not a measurement of
    emergent behaviour (§M1 over-read guard)."""

    def replay_clients(self) -> dict[str, RecordReplayChatClient]:
        """Build one per-agent replay adapter from this run's recorded decisions."""
        return {
            agent_id: RecordReplayChatClient(recorded=tuple(d.call for d in decisions))
            for agent_id, decisions in self.decisions.items()
        }


def _validate_agents(
    agent_ids: list[str],
    llms: Mapping[str, RecordReplayChatClient],
    personas: Mapping[str, PersonaSpec],
) -> None:
    """Fail loudly at construction (not mid-run) on any agent-id mismatch."""
    if len(agent_ids) != len(set(agent_ids)):
        msg = f"duplicate agent_id in agent_states: {agent_ids}"
        raise ValueError(msg)
    missing_llm = sorted(set(agent_ids) - set(llms))
    if missing_llm:
        msg = f"missing RecordReplayChatClient for agent_id(s): {missing_llm}"
        raise ValueError(msg)
    missing_persona = sorted(set(agent_ids) - set(personas))
    if missing_persona:
        msg = f"missing PersonaSpec for agent_id(s): {missing_persona}"
        raise ValueError(msg)


async def _step_one_agent(
    *,
    world: WorldRuntime,
    llm_router: _AgentKeyedChatClient,
    llms: Mapping[str, RecordReplayChatClient],
    ctxs: dict[str, _SocietySinkContext],
    bias_slots: dict[str, list[BiasFiredEvent]],
    agent_id: str,
    cognition_tick: int,
) -> EclDecisionRecord:
    """Step one agent's cognition via the public seam and build its decision record.

    §M4.1: the caller invokes this once per agent per window, strictly in
    ``sorted(agent_id)`` order — never concurrently — so ``llm_router``'s
    "active agent" is always unambiguous.
    """
    llm_router.activate(agent_id)
    client = llms[agent_id]
    used_before = len(client.used)
    result = await world.step_cognition_once(agent_id)
    ctxs[agent_id].move = result.ecl_destination
    served = client.used[used_before:]
    if len(served) != 1:
        msg = (
            f"society cognition tick {cognition_tick} for agent "
            f"{agent_id!r} served {len(served)} action-LLM calls; "
            "expected exactly 1 (reflection disabled in record mode)"
        )
        raise EclReplayError(msg)
    return _build_society_decision(
        agent_tick=cognition_tick,
        call=served[0],
        result=result,
        bias_fired=bias_slots[agent_id][0] if bias_slots[agent_id] else None,
    )


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


async def run_society_loop(
    *,
    run_id: str,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llms: Mapping[str, RecordReplayChatClient],
    agent_states: Sequence[AgentState],
    personas: Mapping[str, PersonaSpec],
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = GOLDEN_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factories: Mapping[str, Callable[[int], Sequence[Observation]]]
    | None = None,
) -> SocietyRunResult:
    """Drive N agents' embodiment loop deterministically (Layer1, §M3/§M4).

    Registers every ``agent_states`` entry on one :class:`WorldRuntime` (this
    module's own driver, ``run_ecl_loop`` is **not** called or modified), then
    for each of ``n_cognition_ticks`` windows: injects each agent's pending
    observation, steps cognition for every agent **sequentially in
    ``sorted(agent_id)`` order** via
    :meth:`~erre_sandbox.world.tick.WorldRuntime.step_cognition_once` (no
    ``asyncio.gather`` fan-out — §M4.1), then advances
    ``physics_ticks_per_cognition`` 30 Hz physics ticks. ``order_slot`` is
    fixed per agent as ``sorted(agent_ids).index(agent_id)`` for the whole run.

    ``llms`` / ``personas`` must have an entry for every ``agent_states.agent_id``
    (missing entries raise ``ValueError`` at construction, not a KeyError mid-run).
    """
    agent_ids = [s.agent_id for s in agent_states]
    _validate_agents(agent_ids, llms, personas)

    order_slots = {agent_id: i for i, agent_id in enumerate(sorted(agent_ids))}

    ecl_mode = EclRecordMode(
        run_id=run_id,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        k_ecl=k_ecl,
        reflection_disabled=True,
    )
    retriever = Retriever(store, embedding, now_factory=retrieval_now)
    bias_slots: dict[str, list[BiasFiredEvent]] = {a: [] for a in agent_ids}
    llm_router = _AgentKeyedChatClient(clients=dict(llms))

    def bias_sink(evt: BiasFiredEvent) -> None:
        active = llm_router.active_agent_id
        if active is not None:
            bias_slots[active].append(evt)

    cycle = CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        # _AgentKeyedChatClient structurally matches the ``chat`` surface the
        # cycle calls (mirrors loop.py's RecordReplayChatClient duck-typing).
        llm=cast("Any", llm_router),
        rng=Random(seed),  # noqa: S311 — determinism seed, not cryptographic
        ecl_mode=ecl_mode,
        bias_sink=bias_sink,
        reflector=reflector,
    )
    clock = ManualClock(start=0.0)
    ctxs: dict[str, _SocietySinkContext] = {a: _SocietySinkContext() for a in agent_ids}
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
        ctx = ctxs[sink_agent_id]
        md = ctx.move
        rows.append(
            EclTraceRow(
                run_id=run_id,
                agent_id=sink_agent_id,
                physics_tick_index=physics_tick_index,
                agent_tick=ctx.agent_tick,
                order_slot=order_slots[sink_agent_id],
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

    world = WorldRuntime(cycle=cycle, clock=clock, physics_hz=30.0, ecl_trace_sink=sink)
    for state in agent_states:
        world.register_agent(state, personas[state.agent_id])

    obs_factories: dict[str, Callable[[int], Sequence[Observation]]] = dict(
        observation_factories
        if observation_factories is not None
        else {a: _default_observation_factory(a) for a in agent_ids}
    )

    decisions: dict[str, list[EclDecisionRecord]] = {a: [] for a in agent_ids}
    step_order: list[str] = []
    sorted_agent_ids = sorted(agent_ids)

    for cognition_tick in range(n_cognition_ticks):
        for agent_id in sorted_agent_ids:
            ctxs[agent_id].agent_tick = cognition_tick
            bias_slots[agent_id].clear()
            for obs in obs_factories[agent_id](cognition_tick):
                world.inject_observation(agent_id, obs)
        # §M4.1 record-mode sequential sorted(order_slot) scheduler — every
        # agent steps ONE AT A TIME in sorted(agent_id) order; no
        # asyncio.gather fan-out (that lives only in the live phase-wheel,
        # which this driver never calls).
        for agent_id in sorted_agent_ids:
            step_order.append(agent_id)
            decisions[agent_id].append(
                await _step_one_agent(
                    world=world,
                    llm_router=llm_router,
                    llms=llms,
                    ctxs=ctxs,
                    bias_slots=bias_slots,
                    agent_id=agent_id,
                    cognition_tick=cognition_tick,
                )
            )
        for _ in range(physics_ticks_per_cognition):
            await world._on_physics_tick()  # noqa: SLF001 — record-mode driver (society, mirrors run_ecl_loop precedent)

    frozen_rows = tuple(rows)
    return SocietyRunResult(
        run_id=run_id,
        rows=frozen_rows,
        decisions={a: tuple(decs) for a, decs in decisions.items()},
        checksum=ecl_trace_checksum(frozen_rows),
        cognition_step_order=tuple(step_order),
    )


__all__ = [
    "SocietyRunResult",
    "run_society_loop",
]
