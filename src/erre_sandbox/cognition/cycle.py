"""One-tick CoALA + ERRE cognition pipeline (T12, MVP M2).

The :class:`CognitionCycle` class orchestrates the 9 micro-steps that turn
``(AgentState, Observation[]) -> (AgentState', ControlEnvelope[])`` for a
single 10-second tick of a single agent. It deliberately keeps all numeric
math in :mod:`cognition.state`, all string building in
:mod:`cognition.prompting`, and all LLM-output decoding in
:mod:`cognition.parse` so this module reads as an integration recipe.

Scope boundary (see
``.steering/20260419-cognition-cycle-minimal/design.md`` §2.5):

* **In**: one agent, one tick, write observations as Episodic memory,
  CSDG Physical update, **ERRE mode FSM transition (M5)**, retrieve
  memories, call LLM, parse the plan, compose Cognitive update, emit
  ``AgentUpdate`` / ``Move`` / ``Speech`` / ``Animation`` envelopes.
* **Out**: PIANO parallelism (M4+), multi-agent ``asyncio.gather`` (T13),
  30Hz tick loop (T13), WebSocket transport (T14).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from random import Random
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from erre_sandbox.cognition.importance import estimate_importance
from erre_sandbox.cognition.parse import parse_llm_plan
from erre_sandbox.cognition.prompting import build_system_prompt, build_user_prompt
from erre_sandbox.cognition.reflection import Reflector
from erre_sandbox.cognition.state import (
    DEFAULT_CONFIG,
    StateUpdateConfig,
    advance_physical,
    apply_llm_delta,
)
from erre_sandbox.erre import SAMPLING_DELTA_BY_MODE
from erre_sandbox.inference import (
    ChatMessage,
    OllamaChatClient,
    OllamaUnavailableError,
    compose_sampling,
)
from erre_sandbox.memory import EmbeddingClient, EmbeddingUnavailableError
from erre_sandbox.schemas import (
    AffordanceEvent,
    AgentState,
    AgentUpdateMsg,
    AnimationMsg,
    BiorhythmEvent,
    Cognitive,
    ControlEnvelope,
    DialogTurnMsg,
    ERREMode,
    ERREModeShiftEvent,
    ERREModeTransitionPolicy,
    InternalEvent,
    MemoryEntry,
    MemoryKind,
    MoveMsg,
    Observation,
    Physical,
    ProximityEvent,
    ReasoningTrace,
    ReasoningTraceMsg,
    ReflectionEvent,
    ReflectionEventMsg,
    SpeechMsg,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from erre_sandbox.cognition.parse import LLMPlan
    from erre_sandbox.memory import MemoryStore, RankedMemory, Retriever
    from erre_sandbox.schemas import (
        ERREModeName,
        PersonaSpec,
        SamplingDelta,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BiasFiredEvent:
    """Structured record of one ``_bias_target_zone`` firing.

    Emitted by :func:`_bias_target_zone` via an optional sink when the helper
    actually replaces the LLM-chosen ``destination_zone`` with a persona
    preferred zone. Process-internal (not a wire envelope) — consumers are
    expected to persist or aggregate in-process (see bootstrap's
    ``_persist_bias_event`` closure for the canonical downstream).

    ``from_zone`` / ``to_zone`` carry the :class:`~erre_sandbox.schemas.Zone`
    enum values (``.value`` strings) so sinks can persist without re-importing
    the enum.
    """

    tick: int
    agent_id: str
    from_zone: str
    to_zone: str
    bias_p: float


_REFLECTION_ZONES: Final[frozenset[Zone]] = frozenset({Zone.PERIPATOS, Zone.CHASHITSU})

_PEER_TURNS_LIMIT: Final[int] = 3
"""Cap on peer-persona dialog turns surfaced to reflection (M7γ D1).

Three is the same shoulder used elsewhere in the prompt builder for
"recent X" sections — large enough to hint at conversational dynamics,
small enough that the prompt stays under the working-context budget.
"""

_TRACE_OBSERVED_OBJECTS_LIMIT: Final[int] = 3
"""Cap on :attr:`ReasoningTrace.observed_objects` (M7γ D3).

Top-3 by :attr:`AffordanceEvent.salience`; ties resolved by stable sort
order (insertion order from the observation stream)."""

_TRACE_NEARBY_AGENTS_LIMIT: Final[int] = 2
"""Cap on :attr:`ReasoningTrace.nearby_agents` (M7γ D3).

Two is the typical PIANO co-walking pair size; agents in larger crowds
will report the two who most recently entered proximity rather than a
saturated list."""

_TRACE_RETRIEVED_MEMORIES_LIMIT: Final[int] = 3
"""Cap on :attr:`ReasoningTrace.retrieved_memories` (M7γ D3).

Mirrors the retriever's typical top-k (per-agent + per-world) so the
xAI panel never exceeds three citation chips per tick."""


_BIORHYTHM_THRESHOLD: Final[float] = 0.5
"""Mid-level threshold for fatigue / hunger that drives
:class:`~erre_sandbox.schemas.BiorhythmEvent` emission (M6-A-2b).

Chosen as a single mid-band boundary rather than a multi-level
(low/mid/high) scheme so the LLM sees at most one biorhythm event per
signal per tick. Multi-level crossings would require dedup logic and
would pull agents out of their current mode on every small fluctuation,
which contradicts the ERRE "意図的非効率性" principle. If an agent's
personality demands a finer granularity, extend this to a per-persona
threshold via :class:`~erre_sandbox.schemas.PersonaSpec`.
"""


class CycleResult(BaseModel):
    """Outcome of one :meth:`CognitionCycle.step` call.

    ``llm_fell_back`` is the explicit flag the T14 gateway will surface as a
    metric — without it, callers would have to diff ``envelopes`` to infer
    whether the agent "decided to do nothing" vs "the LLM was unreachable".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_state: AgentState
    envelopes: list[ControlEnvelope] = Field(default_factory=list)
    new_memory_ids: list[str] = Field(default_factory=list)
    reflection_triggered: bool = False
    llm_fell_back: bool = False
    reflection_event: ReflectionEvent | None = None
    """Produced reflection, if any. ``None`` means the policy declined *or*
    the distillation path failed (LLM / embedding outage) — the
    ``reflection_triggered`` flag distinguishes the two."""
    follow_up_observations: list[Observation] = Field(default_factory=list)
    """Observations deferred to the next tick (M6-A-2b).

    Stress :class:`~erre_sandbox.schemas.BiorhythmEvent` crossings are the
    only current consumer: they are detected in Step 8 **after** the LLM's
    delta has already been applied, so there is no way to feed them into
    the current prompt. The caller (:meth:`WorldRuntime._consume_result`)
    appends this list to the agent's ``pending`` buffer so the next tick's
    observation stream surfaces the signal one tick late — the intended
    semantics for a post-LLM-derived readout."""


class CognitionError(RuntimeError):
    """Unexpected error inside the cycle that is NOT a recoverable outage.

    Raised (not caught) when the failure is bug-shaped — e.g. an
    ``AttributeError`` from a malformed ``Observation`` — so we don't
    silently fall back and hide the defect. See error-handling skill §ルール 5.
    """


class CognitionCycle:
    """Stateful orchestrator for a single agent's cognition loop.

    Hold one instance per agent in M4+ multi-agent runs. The store /
    embedding / llm / retriever dependencies are safe to share across
    instances (they carry their own clients or are stateless).
    """

    DEFAULT_DESTINATION_SPEED: ClassVar[float] = 1.3
    REFLECTION_IMPORTANCE_THRESHOLD: ClassVar[float] = 1.5
    """Sum-of-importances over the tick that triggers a reflection window.

    The 150 value quoted in ``docs/functional-design.md`` §2 applies to the
    long-horizon accumulator that M4 reflection will maintain. Per-tick we
    use a much smaller threshold (≈ 3 high-importance events) so the MVP
    can demonstrate the trigger path.
    """

    DEFAULT_TICK_SECONDS: ClassVar[float] = 10.0

    def __init__(
        self,
        *,
        retriever: Retriever,
        store: MemoryStore,
        embedding: EmbeddingClient,
        llm: OllamaChatClient,
        rng: Random | None = None,
        update_config: StateUpdateConfig | None = None,
        reflector: Reflector | None = None,
        erre_policy: ERREModeTransitionPolicy | None = None,
        erre_sampling_deltas: Mapping[ERREModeName, SamplingDelta] | None = None,
        bias_sink: Callable[[BiasFiredEvent], None] | None = None,
    ) -> None:
        self._retriever = retriever
        self._store = store
        self._embedding = embedding
        self._llm = llm
        self._rng = rng
        self._update_config = update_config or DEFAULT_CONFIG
        # Default reflector uses the same infra as the cycle. Injecting an
        # explicit instance is the supported extension point for tests and
        # for multi-agent orchestration (#6) that want to share a single
        # policy across all agents.
        self._reflector = reflector or Reflector(
            store=store,
            embedding=embedding,
            llm=llm,
        )
        # Optional ERRE mode FSM (M5 `m5-world-zone-triggers`). When None
        # (default) the cycle preserves pre-M5 behaviour: ``agent_state.erre``
        # is only set at boot and never changes thereafter. Wiring the
        # concrete :class:`~erre_sandbox.erre.DefaultERREModePolicy` is the
        # responsibility of ``m5-orchestrator-integration``.
        self._erre_policy = erre_policy
        # Override the per-mode sampling delta table. Defaults to the
        # production :data:`SAMPLING_DELTA_BY_MODE`. Tests may inject a
        # custom mapping (e.g. all-zero deltas) to isolate FSM-transition
        # behaviour from the production table without monkey-patching the
        # module constant. ``is not None`` rather than ``or`` so an
        # explicitly-empty mapping does not silently fall back to production.
        self._erre_sampling_deltas = (
            erre_sampling_deltas
            if erre_sampling_deltas is not None
            else SAMPLING_DELTA_BY_MODE
        )
        # Slice β: probability that a destination_zone landing outside the
        # persona's preferred_zones is resampled toward the preferred list.
        # Read once at construction — per-tick env reads would obscure the
        # experiment's knob and violate the "cognition has no env
        # dependencies" invariant the rest of this module relies on. Tune
        # via ``ERRE_ZONE_BIAS_P`` between runs; see
        # ``.steering/20260424-m7-differentiation-observability/design-final.md``.
        self._zone_bias_p = float(os.environ.get("ERRE_ZONE_BIAS_P", "0.2"))
        # Bias uses a persistent RNG (shared with ``self._rng`` when one is
        # injected, otherwise its own ``Random()`` so consecutive ticks draw
        # from a coherent sequence rather than fresh entropy per step).
        # Separate field from ``self._rng`` so the ``apply_llm_delta`` noise
        # contract ("no rng → deterministic") stays intact for callers that
        # deliberately pass ``None``.
        self._bias_rng = rng or Random()  # noqa: S311 — non-crypto bias nudge
        # M8 baseline-quality-metric: optional sink receiving one
        # :class:`BiasFiredEvent` per firing. None in unit tests and the
        # pre-M8 bootstrap; the production bootstrap wires it to a closure
        # that persists events via ``MemoryStore.add_bias_event_sync``
        # (see decisions D2/D5 in
        # ``.steering/20260425-m8-baseline-quality-metric/decisions.md``).
        self._bias_sink = bias_sink

    async def step(
        self,
        agent_state: AgentState,
        persona: PersonaSpec,
        observations: Sequence[Observation],
        *,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> CycleResult:
        """Run the 9-step cognition pipeline for one tick.

        ``tick_seconds`` is accepted for symmetry with T13 (which may pass a
        measured wall-clock delta) but is not yet consumed by the MVP math —
        :mod:`cognition.state` expects a fixed tick. It is deliberately left
        in the signature so T13 doesn't have to reshape the call.
        """
        _ = tick_seconds  # reserved for T13, intentionally unused here

        # Step 1: write observations as Episodic memories.
        new_memory_ids = await self._write_observations(
            observations,
            agent_id=agent_state.agent_id,
        )

        # Step 2: update Physical (pure, CSDG half-step).
        new_physical = advance_physical(
            agent_state.physical,
            observations,
            config=self._update_config,
            rng=self._rng,
        )

        # Step 2.25 (M6-A-2b): detect biorhythm threshold crossings. Emitted
        # BEFORE the FSM / retrieve / LLM so the mode policy can react to the
        # crossing and the LLM prompt can surface "I got tired" to the agent
        # narrating in first person. Stress crossings live in Cognitive and
        # are deferred — Cognitive is assembled post-LLM (Step 8), so stress
        # biorhythm would arrive a tick late and is not wired here.
        biorhythm_events = _detect_biorhythm_crossings(
            previous=agent_state.physical,
            current=new_physical,
            agent_id=agent_state.agent_id,
            tick=agent_state.tick,
        )
        if biorhythm_events:
            observations = [*observations, *biorhythm_events]

        # Step 2.5 (M5): ERRE mode FSM transition.
        #
        # Runs BEFORE retrieve / LLM so the sampling at Step 5 reflects the
        # newly-selected mode (zero-tick latency). When no policy is wired the
        # call is a no-op, preserving pre-M5 behaviour.
        #
        # M6-A-1: when a transition occurs, the emitted ERREModeShiftEvent is
        # appended to ``observations`` so Steps 4-10 (retrieve / prompt /
        # reflection) see the mode-shift signal alongside the inputs that
        # caused it. The upstream sequence is not mutated — we build a new
        # list and rebind the local.
        agent_state, shift_event = self._maybe_apply_erre_fsm(
            agent_state,
            observations,
        )
        if shift_event is not None:
            observations = [*observations, shift_event]

        # Step 3: reflection trigger detection (execution is M4+).
        importance_sum = sum(estimate_importance(o) for o in observations)
        entered_reflective = _detect_zone_entry(observations, _REFLECTION_ZONES)
        reflection_triggered = bool(
            importance_sum > self.REFLECTION_IMPORTANCE_THRESHOLD or entered_reflective,
        )
        if reflection_triggered:
            logger.info(
                "Reflection trigger for agent %s (sum=%.2f, zone_entry=%s)",
                agent_state.agent_id,
                importance_sum,
                entered_reflective,
            )

        # Step 4: retrieve memories (Unavailable → proceed with empty list).
        memories = await self._retrieve_safely(agent_state, observations)

        # Step 5-6: build prompts and call the LLM.
        sampling = compose_sampling(
            persona.default_sampling,
            agent_state.erre.sampling_overrides,
        )
        system_prompt = build_system_prompt(persona, agent_state)
        user_prompt = build_user_prompt(observations, memories)
        try:
            resp = await self._llm.chat(
                [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                sampling=sampling,
            )
        except OllamaUnavailableError as exc:
            logger.warning(
                "LLM unavailable for agent %s: %s — continuing current action",
                agent_state.agent_id,
                exc,
            )
            return self._fallback(
                agent_state,
                new_memory_ids=new_memory_ids,
                reflection_triggered=reflection_triggered,
                new_physical=new_physical,
            )

        # Step 7: parse the LLM plan (malformed → same fallback branch).
        plan = parse_llm_plan(resp.content)
        if plan is None:
            logger.warning(
                "LLM returned unparseable plan for agent %s (len=%d) — fallback",
                agent_state.agent_id,
                len(resp.content),
            )
            return self._fallback(
                agent_state,
                new_memory_ids=new_memory_ids,
                reflection_triggered=reflection_triggered,
                new_physical=new_physical,
            )

        # Slice β: nudge the LLM's destination toward persona preferred_zones
        # so three agents with different preferred lists produce three
        # different spatial trajectories. The helper is a no-op when the
        # destination is already preferred, when preferred_zones is empty,
        # or when the per-tick bias probability does not fire — so the
        # envelope-level contract is unchanged in the common case.
        plan = _bias_target_zone(
            plan,
            persona,
            self._bias_rng,
            self._zone_bias_p,
            agent_id=agent_state.agent_id,
            tick=agent_state.tick,
            bias_sink=self._bias_sink,
        )

        # Step 8: compose Cognitive via pure LLM delta.
        new_cognitive = apply_llm_delta(
            agent_state.cognitive,
            plan,
            config=self._update_config,
            rng=self._rng,
        )

        # Step 8.5 (M6-A-2b): detect stress threshold crossings. Unlike the
        # fatigue / hunger crossings in Step 2.25, stress lives in Cognitive
        # which is only known AFTER the LLM call, so the event arrives one
        # tick late by design. The runtime consumes
        # ``CycleResult.follow_up_observations`` and appends them to the
        # agent's pending buffer so the next tick's prompt sees the signal.
        stress_events = _detect_stress_crossing(
            previous=agent_state.cognitive,
            current=new_cognitive,
            agent_id=agent_state.agent_id,
            tick=agent_state.tick + 1,
        )

        # Step 9: assemble the post-tick state + envelopes.
        new_state = agent_state.model_copy(
            update={
                "tick": agent_state.tick + 1,
                "physical": new_physical,
                "cognitive": new_cognitive,
            },
        )
        envelopes = self._build_envelopes(
            new_state,
            plan,
            observations=observations,
            memories=memories,
        )

        # Step 10: reflection. Delegated to a collaborator so trigger policy
        # and LLM-distillation plumbing live outside this module. The
        # reflector never raises: outages resolve to ``reflection_event=None``.
        # M7γ D1: surface up to three recent peer-persona turns so the
        # distillation can react to what *others* just said. Fetched from
        # the dialog-turn log already populated by the bootstrap turn-sink
        # chain, so this stays a pure read against sqlite.
        recent_peer_turns = await self._fetch_recent_peer_turns(persona)
        reflection_event = await self._reflector.maybe_reflect(
            agent_state=new_state,
            persona=persona,
            observations=observations,
            importance_sum=importance_sum,
            recent_dialog_turns=recent_peer_turns,
        )
        # M6-A-4: wire the reflection over the envelope stream so the Godot
        # xAI ReasoningPanel can surface the distilled summary. Only emit
        # when the reflector actually produced an event — the ``None`` path
        # already has the ``reflection_triggered`` CycleResult flag for
        # observability.
        if reflection_event is not None:
            envelopes.append(
                ReflectionEventMsg(
                    tick=new_state.tick,
                    event=reflection_event,
                ),
            )

        return CycleResult(
            agent_state=new_state,
            envelopes=envelopes,
            new_memory_ids=new_memory_ids,
            reflection_triggered=reflection_triggered,
            llm_fell_back=False,
            reflection_event=reflection_event,
            follow_up_observations=list(stress_events),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _write_observations(
        self,
        observations: Sequence[Observation],
        *,
        agent_id: str,
    ) -> list[str]:
        new_ids: list[str] = []
        for obs in observations:
            content = _observation_content_for_embed(obs)
            try:
                vec = await self._embedding.embed_document(content)
            except EmbeddingUnavailableError as exc:
                logger.warning(
                    "Embedding unavailable for agent %s observation: %s — "
                    "storing memory without embedding",
                    agent_id,
                    exc,
                )
                vec = None
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                kind=MemoryKind.EPISODIC,
                content=content,
                importance=estimate_importance(obs),
                created_at=datetime.now(tz=UTC),
                source_observation_id=None,
            )
            mid = await self._store.add(entry, vec)
            new_ids.append(mid)
        return new_ids

    def _maybe_apply_erre_fsm(
        self,
        agent_state: AgentState,
        observations: Sequence[Observation],
    ) -> tuple[AgentState, ERREModeShiftEvent | None]:
        """Apply the optional ERRE mode FSM; return the (possibly) updated state.

        A ``None`` candidate from the policy signals "no transition this
        tick" and is the common case once an agent has settled into a mode;
        the returned tuple is ``(agent_state_unchanged, None)``. A concrete
        :class:`~erre_sandbox.schemas.ERREModeName` forces a fresh
        :class:`~erre_sandbox.schemas.ERREMode` with ``entered_at_tick``
        set to the tick the FSM observed and ``sampling_overrides`` pulled
        from :data:`~erre_sandbox.erre.SAMPLING_DELTA_BY_MODE` so Step 5's
        LLM call in the same tick uses the freshly-selected mode's delta
        via :func:`~erre_sandbox.inference.sampling.compose_sampling`. In
        that case an :class:`~erre_sandbox.schemas.ERREModeShiftEvent` is
        returned alongside the new state so Step 2.5 in :meth:`step` can
        append it to ``observations`` for downstream prompt / reflection.

        The FSM is consulted at Step 2.5, **before** ``new_physical`` is
        folded into ``agent_state``. Today ``advance_physical`` never
        changes ``position.zone`` (it only nudges CSDG half-step fields)
        so the FSM observes the correct zone; if a future milestone lets
        physical update change the zone, move this call after Step 9's
        ``agent_state.model_copy`` or refactor the physical update to
        happen before FSM.

        If the policy violates its Protocol contract and returns a value
        equal to ``current``, we treat it as a no-op (empty tuple tail):
        emitting a fresh :class:`~erre_sandbox.schemas.ERREMode` with a
        new ``entered_at_tick`` in that case would falsely mark a
        transition and confuse downstream dwell-time logic.

        The ``reason`` field on the emitted shift event is inferred from
        the most-recent mode-influencing observation (see
        :func:`_infer_shift_reason`). This approximation aligns with the
        FSM policy's "latest signal wins" semantics; a future milestone
        that needs byte-accurate attribution should extend the
        :class:`~erre_sandbox.schemas.ERREModeTransitionPolicy` Protocol
        to return ``(mode, reason)`` directly rather than reconstructing
        it here.
        """
        if self._erre_policy is None:
            return agent_state, None
        candidate = self._erre_policy.next_mode(
            current=agent_state.erre.name,
            zone=agent_state.position.zone,
            observations=observations,
            tick=agent_state.tick,
        )
        if candidate is None or candidate == agent_state.erre.name:
            return agent_state, None
        previous = agent_state.erre.name
        new_erre = ERREMode(
            name=candidate,
            entered_at_tick=agent_state.tick,
            sampling_overrides=self._erre_sampling_deltas[candidate],
        )
        logger.debug(
            "ERRE mode transition for agent %s: %s → %s (tick=%d)",
            agent_state.agent_id,
            previous,
            candidate,
            agent_state.tick,
        )
        shift_event = ERREModeShiftEvent(
            tick=agent_state.tick,
            agent_id=agent_state.agent_id,
            previous=previous,
            current=candidate,
            reason=_infer_shift_reason(observations),
        )
        return agent_state.model_copy(update={"erre": new_erre}), shift_event

    async def _retrieve_safely(
        self,
        agent_state: AgentState,
        observations: Sequence[Observation],
    ) -> list[RankedMemory]:
        query = _build_retrieval_query(observations, agent_state)
        if not query:
            return []
        try:
            return await self._retriever.retrieve(agent_state.agent_id, query)
        except (OllamaUnavailableError, EmbeddingUnavailableError) as exc:
            logger.warning(
                "Retrieve failed for agent %s: %s — continuing with no memories",
                agent_state.agent_id,
                exc,
            )
            return []

    def _fallback(
        self,
        agent_state: AgentState,
        *,
        new_memory_ids: list[str],
        reflection_triggered: bool,
        new_physical: Physical,
    ) -> CycleResult:
        """Continue-current-action path for recoverable failures.

        Physical is advanced (wall-clock time still passes), tick is bumped,
        Cognitive is carried over, no Speech/Move/Animation envelopes.
        """
        new_state = agent_state.model_copy(
            update={
                "tick": agent_state.tick + 1,
                "physical": new_physical,
            },
        )
        envelopes: list[ControlEnvelope] = [
            AgentUpdateMsg(tick=new_state.tick, agent_state=new_state),
        ]
        return CycleResult(
            agent_state=new_state,
            envelopes=envelopes,
            new_memory_ids=new_memory_ids,
            reflection_triggered=reflection_triggered,
            llm_fell_back=True,
        )

    def _build_envelopes(
        self,
        new_state: AgentState,
        plan: LLMPlan,
        *,
        observations: Sequence[Observation] = (),
        memories: Sequence[RankedMemory] = (),
    ) -> list[ControlEnvelope]:
        envelopes: list[ControlEnvelope] = [
            AgentUpdateMsg(tick=new_state.tick, agent_state=new_state),
        ]
        if plan.utterance:
            envelopes.append(
                SpeechMsg(
                    tick=new_state.tick,
                    agent_id=new_state.agent_id,
                    utterance=plan.utterance,
                    zone=new_state.position.zone,
                ),
            )
        if plan.destination_zone is not None:
            # Coordinates are carried over verbatim; the Godot side (T17)
            # performs spatial interpolation via Tween based on the Zone
            # boundary, so we only hand over the semantic destination.
            target = new_state.position.model_copy(
                update={"zone": plan.destination_zone},
            )
            envelopes.append(
                MoveMsg(
                    tick=new_state.tick,
                    agent_id=new_state.agent_id,
                    target=target,
                    speed=self.DEFAULT_DESTINATION_SPEED,
                ),
            )
        if plan.animation:
            envelopes.append(
                AnimationMsg(
                    tick=new_state.tick,
                    agent_id=new_state.agent_id,
                    animation_name=plan.animation,
                ),
            )
        # M7γ D3+D4: structured rationale carries the observation / memory
        # provenance and an affinity hint so the xAI panel can show *why*
        # the agent decided this way. Even when the LLM did not fill any
        # rationale field, the trace is emitted whenever at least one of
        # the M7γ provenance lists is non-empty *or* there is a recent
        # bond — otherwise downstream consumers would lose the affinity
        # signal entirely on quiet ticks.
        observed_objects = _trace_observed_objects(observations)
        nearby_agents = _trace_nearby_agents(observations)
        retrieved_memories = _trace_retrieved_memories(memories)
        decision = _decision_with_affinity(plan.decision, new_state)
        if (
            plan.salient is not None
            or decision is not None
            or plan.next_intent is not None
            or observed_objects
            or nearby_agents
            or retrieved_memories
        ):
            trace = ReasoningTrace(
                agent_id=new_state.agent_id,
                tick=new_state.tick,
                mode=new_state.erre.name,
                salient=plan.salient,
                decision=decision,
                next_intent=plan.next_intent,
                observed_objects=observed_objects,
                nearby_agents=nearby_agents,
                retrieved_memories=retrieved_memories,
            )
            envelopes.append(
                ReasoningTraceMsg(tick=new_state.tick, trace=trace),
            )
        return envelopes

    async def _fetch_recent_peer_turns(
        self,
        persona: PersonaSpec,
    ) -> list[DialogTurnMsg]:
        """Return up to three most-recent dialog turns from *other* personas.

        Reads ``dialog_turns`` rows synchronously off the event loop via
        :func:`asyncio.to_thread` so a slow sqlite scan cannot stall the
        cognition cycle. Returns ``[]`` on any failure — reflection D1 is
        an additive signal, not a blocking dependency.

        M7δ (R3 H3 SQL push): the WHERE / LIMIT push to SQLite via
        :meth:`MemoryStore.iter_dialog_turns(exclude_persona, limit)` so
        the previous full-table-scan-then-Python-filter pattern (which
        does not scale past a few thousand rows at the cycle's
        0.3 calls/s pace) is gone. ``iter_dialog_turns`` returns the most
        recent N rows in DESC order; we ``reversed(...)`` here to emit
        chronologically for the downstream reflection-prompt builder.

        Reconstructs :class:`DialogTurnMsg` from the export-flavoured row
        dicts produced by :meth:`MemoryStore.iter_dialog_turns`. The
        non-wire fields (``schema_version`` / ``sent_at``) take their
        default factories; only the fields the reflection prompt consumes
        are mapped.
        """
        try:
            rows = await asyncio.to_thread(
                lambda: list(
                    self._store.iter_dialog_turns(
                        exclude_persona=persona.persona_id,
                        limit=_PEER_TURNS_LIMIT,
                    ),
                ),
            )
        except sqlite3.OperationalError as exc:
            logger.warning(
                "iter_dialog_turns failed for peer turns (%s); skipping reflection D1",
                exc,
            )
            return []
        # SQL emits DESC (most recent first); reverse for chronological prompt.
        out: list[DialogTurnMsg] = []
        for row in reversed(rows):
            try:
                out.append(
                    DialogTurnMsg(
                        tick=int(row.get("tick", 0)),
                        dialog_id=str(row.get("dialog_id", "")),
                        speaker_id=str(row.get("speaker_agent_id", "")),
                        addressee_id=str(row.get("addressee_agent_id", "")),
                        utterance=str(row.get("utterance", "")),
                        turn_index=int(row.get("turn_index", 0)),
                    ),
                )
            except (ValidationError, ValueError, TypeError) as exc:
                logger.debug(
                    "skipping malformed dialog_turn row in peer fetch: %s",
                    exc,
                )
        return out


# ---------------------------------------------------------------------------
# Module-private helpers (pure)
# ---------------------------------------------------------------------------


def _bias_target_zone(
    plan: LLMPlan,
    persona: PersonaSpec,
    rng: Random,
    bias_p: float,
    *,
    agent_id: str,
    tick: int | None = None,
    bias_sink: Callable[[BiasFiredEvent], None] | None = None,
) -> LLMPlan:
    """Resample ``plan.destination_zone`` toward persona preferred zones.

    With probability ``bias_p``, if the LLM-chosen zone lies outside
    ``persona.preferred_zones``, pick a uniform replacement from that list
    and emit a ``bias.fired`` debug log so the researcher can confirm the
    bias is actually reshaping trajectories in a live run. The plan is
    returned unchanged in every other branch (empty preferred list,
    destination already preferred, destination is ``None``, or the
    probability did not fire), so normal LLM plans — including the
    intentional "stay put" signal — propagate unmodified.

    When ``bias_sink`` is provided (M8 baseline-quality-metric, decisions
    D2/D5), a :class:`BiasFiredEvent` is dispatched on every firing so
    callers can persist the event for post-hoc metric aggregation. The
    sink is called after the debug log so that a persistence failure
    (caught below) does not swallow the operator-visible signal. Sink
    exceptions are logged but never propagate — tearing down the live
    cognition cycle over observability bookkeeping would be worse than
    dropping a metric row.

    The "destination is ``None``" branch is deliberately a no-op in the
    first cut: we respect the LLM's choice to stay in place and let live
    G-GEAR data determine whether the helper should also synthesise a
    destination when the LLM leaves it empty. See Open Question #1 in
    ``.steering/20260424-m7-differentiation-observability/`` plan notes.
    """
    if not persona.preferred_zones:
        return plan
    if plan.destination_zone is None:
        return plan
    if plan.destination_zone in persona.preferred_zones:
        return plan
    if rng.random() >= bias_p:
        return plan
    new_dest = rng.choice(persona.preferred_zones)
    from_value = plan.destination_zone.value
    to_value = new_dest.value
    logger.debug(
        "bias.fired agent=%s from=%s to=%s bias_p=%.2f",
        agent_id,
        from_value,
        to_value,
        bias_p,
    )
    if bias_sink is not None and tick is not None:
        event = BiasFiredEvent(
            tick=tick,
            agent_id=agent_id,
            from_zone=from_value,
            to_zone=to_value,
            bias_p=bias_p,
        )
        try:
            bias_sink(event)
        except Exception:  # noqa: BLE001 — sink failures must not kill cycle
            logger.exception(
                "bias_sink raised for agent=%s tick=%s; dropping event",
                agent_id,
                tick,
            )
    return plan.model_copy(update={"destination_zone": new_dest})


def _observation_content_for_embed(obs: Observation) -> str:  # noqa: PLR0911 — discriminator dispatch
    """Render *obs* into a single string suitable for Episodic storage + embed."""
    if obs.event_type == "perception":
        return f"[perception] {obs.content}"
    if obs.event_type == "speech":
        return f"[speech] {obs.speaker_id}: {obs.utterance}"
    if obs.event_type == "zone_transition":
        return f"[zone_transition] {obs.from_zone.value} -> {obs.to_zone.value}"
    if obs.event_type == "erre_mode_shift":
        prev = obs.previous.value
        curr = obs.current.value
        return f"[erre_mode_shift] {prev} -> {curr} ({obs.reason})"
    if obs.event_type == "internal":
        return f"[internal] {obs.content}"
    if obs.event_type == "affordance":
        return (
            f"[affordance] {obs.prop_kind}#{obs.prop_id} in {obs.zone.value} "
            f"(distance={obs.distance:.1f}m, salience={obs.salience:.2f})"
        )
    if obs.event_type == "proximity":
        return (
            f"[proximity {obs.crossing}] other={obs.other_agent_id} "
            f"{obs.distance_prev:.1f}m -> {obs.distance_now:.1f}m"
        )
    if obs.event_type == "temporal":
        return f"[temporal] {obs.period_prev.value} -> {obs.period_now.value}"
    if obs.event_type == "biorhythm":
        return (
            f"[biorhythm {obs.signal}:{obs.threshold_crossed}] "
            f"{obs.level_prev:.2f} -> {obs.level_now:.2f}"
        )
    return "[unknown] (unformatted)"


def _build_retrieval_query(
    observations: Iterable[Observation],
    agent_state: AgentState,
) -> str:
    zone = agent_state.position.zone.value
    mode = agent_state.erre.name.value
    parts: list[str] = [f"agent at {zone} in {mode} mode"]
    parts.extend(_observation_content_for_embed(obs) for obs in observations)
    return " | ".join(parts)


def _detect_zone_entry(
    observations: Iterable[Observation],
    trigger_zones: frozenset[Zone],
) -> bool:
    for obs in observations:
        if obs.event_type == "zone_transition" and obs.to_zone in trigger_zones:
            return True
    return False


def _detect_biorhythm_crossings(
    *,
    previous: Physical,
    current: Physical,
    agent_id: str,
    tick: int,
) -> list[BiorhythmEvent]:
    """Emit a :class:`BiorhythmEvent` for every signal that crossed mid-band.

    Compares the agent's fatigue / hunger before and after the CSDG
    half-step advance. The mid-level threshold (:data:`_BIORHYTHM_THRESHOLD`)
    is the only boundary watched in M6-A-2b so we stay inside the "at most
    one biorhythm event per signal per tick" budget documented on the
    threshold constant.

    Returns an empty list when no signal crossed — a fast path that keeps
    the observation-stream allocation pressure off every physics tick.
    """
    events: list[BiorhythmEvent] = []
    for signal, prev_val, curr_val in (
        ("fatigue", previous.fatigue, current.fatigue),
        ("hunger", previous.hunger, current.hunger),
    ):
        crossed_up = prev_val < _BIORHYTHM_THRESHOLD <= curr_val
        crossed_down = curr_val < _BIORHYTHM_THRESHOLD <= prev_val
        if not (crossed_up or crossed_down):
            continue
        events.append(
            BiorhythmEvent(
                tick=tick,
                agent_id=agent_id,
                signal=signal,  # type: ignore[arg-type]
                level_prev=prev_val,
                level_now=curr_val,
                threshold_crossed="up" if crossed_up else "down",
            ),
        )
    return events


def _detect_stress_crossing(
    *,
    previous: Cognitive,
    current: Cognitive,
    agent_id: str,
    tick: int,
) -> list[BiorhythmEvent]:
    """Emit a stress :class:`BiorhythmEvent` if mid-band was crossed.

    Parallel to :func:`_detect_biorhythm_crossings` for the ``stress`` signal
    living on :class:`Cognitive`. Kept as a separate helper because:

    * The watched vector differs (``Cognitive`` vs ``Physical``), so the
      signatures would diverge if merged.
    * Stress crossings are detected *after* the LLM call (Step 8) so the
      emitted tick is ``agent_state.tick + 1`` — the tick the event will
      belong to when the runtime surfaces it via
      :attr:`CycleResult.follow_up_observations`. The fatigue/hunger helper
      uses ``agent_state.tick`` because those events are same-tick inputs.

    The returned list has at most one element (``stress`` is the only
    watched signal on :class:`Cognitive`).
    """
    prev_val = previous.stress
    curr_val = current.stress
    crossed_up = prev_val < _BIORHYTHM_THRESHOLD <= curr_val
    crossed_down = curr_val < _BIORHYTHM_THRESHOLD <= prev_val
    if not (crossed_up or crossed_down):
        return []
    return [
        BiorhythmEvent(
            tick=tick,
            agent_id=agent_id,
            signal="stress",
            level_prev=prev_val,
            level_now=curr_val,
            threshold_crossed="up" if crossed_up else "down",
        ),
    ]


def _infer_shift_reason(
    observations: Sequence[Observation],
) -> Literal["scheduled", "zone", "fatigue", "external", "reflection"]:
    """Heuristically attribute an ERRE mode transition to its trigger.

    The FSM policy (:class:`~erre_sandbox.erre.DefaultERREModePolicy`)
    uses "latest signal wins" semantics, so the most-recent
    mode-influencing observation is the best guess for what caused the
    transition. We scan in reverse and pick the first match.

    ``InternalEvent.content`` prefixes follow the convention established
    by the FSM policy's internal handler: ``"fatigue:*"`` signals a
    fatigue-driven transition, ``"shuhari_promote:*"`` (and any other
    internal hint) is treated as scheduled progression. A stray
    ``ERREModeShiftEvent`` in ``observations`` means an external source
    forced the transition.

    Falls back to ``"external"`` when no mode-influencing observation is
    found — this can happen when a future rule (dwell-time, tick-modulo)
    triggers without a corresponding event.
    """
    for ev in reversed(observations):
        if isinstance(ev, ZoneTransitionEvent):
            return "zone"
        if isinstance(ev, InternalEvent):
            if ev.content.startswith("fatigue:"):
                return "fatigue"
            return "scheduled"
        if isinstance(ev, ERREModeShiftEvent):
            return "external"
    return "external"


def _trace_observed_objects(observations: Sequence[Observation]) -> list[str]:
    """Top-3 ``AffordanceEvent.prop_id`` by salience (M7γ D3).

    Stable ordering: salience descending, then insertion order — so two
    props with equal salience surface in the order the observation stream
    delivered them. Empty input yields an empty list (the trace consumer
    should not need to special-case ``None`` vs ``[]``).
    """
    affordances = [o for o in observations if isinstance(o, AffordanceEvent)]
    affordances.sort(key=lambda o: o.salience, reverse=True)
    return [o.prop_id for o in affordances[:_TRACE_OBSERVED_OBJECTS_LIMIT]]


def _trace_nearby_agents(observations: Sequence[Observation]) -> list[str]:
    """Top-2 ``ProximityEvent.other_agent_id`` with ``crossing="enter"`` (M7γ D3).

    Only ``enter`` crossings are surfaced — a ``leave`` crossing is the
    *absence* of relevance, not a positive signal worth tracing. The cap
    matches typical PIANO co-walking pair sizes; agents in larger crowds
    will see the two who most recently entered proximity.
    """
    enters = [
        o
        for o in observations
        if isinstance(o, ProximityEvent) and o.crossing == "enter"
    ]
    return [o.other_agent_id for o in enters[:_TRACE_NEARBY_AGENTS_LIMIT]]


def _trace_retrieved_memories(memories: Sequence[RankedMemory]) -> list[str]:
    """Top-3 :attr:`MemoryEntry.id` from the ranked retrieval (M7γ D3).

    The retriever already returns memories sorted by combined score, so we
    take the prefix without re-ranking. Empty when retrieval produced no
    rows (LLM unavailable, embedding outage, or no match) — the trace
    field then degrades to ``[]`` rather than papering over the gap.
    """
    return [m.entry.id for m in memories[:_TRACE_RETRIEVED_MEMORIES_LIMIT]]


def _decision_with_affinity(
    decision: str | None,
    new_state: AgentState,
) -> str | None:
    """Append the most salient bond's affinity hint to ``decision`` (M7γ D4 + M7δ M2).

    M7γ ranked bonds by ``last_interaction_tick`` only — so a recently-
    touched but neutral bond would shadow a strongly-charged older one.
    M7δ tightens the rule: rank by ``(|affinity|, last_interaction_tick)``
    descending so the hint surfaces the bond that actually carries
    emotional weight. The Godot :class:`ReasoningPanel` already sorts the
    Relationships foldout by ``|affinity|`` first; this Python-side change
    aligns the LLM's decision-suffix hint with what the user sees on
    screen (R3 M2).

    When there is no bond at all the original decision passes through
    unchanged. When ``decision`` is None and there *is* a bond the hint
    becomes the entire decision — that is intentional, because the γ
    acceptance test asserts the substring ``"affinity"`` is present
    whenever bonds exist, regardless of LLM rationale completeness.

    Format: ``f" affinity={bond.affinity:+.2f} with {bond.other_agent_id}"``
    suffixed to the LLM's decision when present, or used standalone
    otherwise. The ``+.2f`` format matches the Godot ReasoningPanel
    rendering for the relationships foldout (Slice γ Commit 4).
    """
    if not new_state.relationships:
        return decision
    most_salient = max(
        new_state.relationships,
        key=lambda b: (
            abs(b.affinity),
            b.last_interaction_tick if b.last_interaction_tick is not None else -1,
        ),
    )
    hint = f"affinity={most_salient.affinity:+.2f} with {most_salient.other_agent_id}"
    if decision is None:
        return hint
    return f"{decision} ({hint})"


__all__ = [
    "BiasFiredEvent",
    "CognitionCycle",
    "CognitionError",
    "CycleResult",
]
