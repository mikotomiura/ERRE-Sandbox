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

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

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
    AgentState,
    AgentUpdateMsg,
    AnimationMsg,
    ControlEnvelope,
    ERREMode,
    ERREModeTransitionPolicy,
    MemoryEntry,
    MemoryKind,
    MoveMsg,
    Physical,
    ReflectionEvent,
    SpeechMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from random import Random

    from erre_sandbox.cognition.parse import LLMPlan
    from erre_sandbox.memory import MemoryStore, RankedMemory, Retriever
    from erre_sandbox.schemas import (
        ERREModeName,
        Observation,
        PersonaSpec,
        SamplingDelta,
    )

logger = logging.getLogger(__name__)

_REFLECTION_ZONES: Final[frozenset[Zone]] = frozenset({Zone.PERIPATOS, Zone.CHASHITSU})


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

        # Step 2.5 (M5): ERRE mode FSM transition.
        #
        # Runs BEFORE retrieve / LLM so the sampling at Step 5 reflects the
        # newly-selected mode (zero-tick latency). When no policy is wired the
        # call is a no-op, preserving pre-M5 behaviour.
        agent_state = self._maybe_apply_erre_fsm(agent_state, observations)

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

        # Step 8: compose Cognitive via pure LLM delta.
        new_cognitive = apply_llm_delta(
            agent_state.cognitive,
            plan,
            config=self._update_config,
            rng=self._rng,
        )

        # Step 9: assemble the post-tick state + envelopes.
        new_state = agent_state.model_copy(
            update={
                "tick": agent_state.tick + 1,
                "physical": new_physical,
                "cognitive": new_cognitive,
            },
        )
        envelopes = self._build_envelopes(new_state, plan)

        # Step 10: reflection. Delegated to a collaborator so trigger policy
        # and LLM-distillation plumbing live outside this module. The
        # reflector never raises: outages resolve to ``reflection_event=None``.
        reflection_event = await self._reflector.maybe_reflect(
            agent_state=new_state,
            persona=persona,
            observations=observations,
            importance_sum=importance_sum,
        )

        return CycleResult(
            agent_state=new_state,
            envelopes=envelopes,
            new_memory_ids=new_memory_ids,
            reflection_triggered=reflection_triggered,
            llm_fell_back=False,
            reflection_event=reflection_event,
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
    ) -> AgentState:
        """Apply the optional ERRE mode FSM; return the (possibly) updated state.

        A ``None`` return from the policy signals "no transition this tick"
        and is the common case once an agent has settled into a mode; it
        keeps ``agent_state`` byte-identical. A concrete
        :class:`~erre_sandbox.schemas.ERREModeName` forces a fresh
        :class:`~erre_sandbox.schemas.ERREMode` with ``entered_at_tick``
        set to the tick the FSM observed and ``sampling_overrides`` pulled
        from :data:`~erre_sandbox.erre.SAMPLING_DELTA_BY_MODE` so Step 5's
        LLM call in the same tick uses the freshly-selected mode's delta
        via :func:`~erre_sandbox.inference.sampling.compose_sampling`.

        The FSM is consulted at Step 2.5, **before** ``new_physical`` is
        folded into ``agent_state``. Today ``advance_physical`` never
        changes ``position.zone`` (it only nudges CSDG half-step fields)
        so the FSM observes the correct zone; if a future milestone lets
        physical update change the zone, move this call after Step 9's
        ``agent_state.model_copy`` or refactor the physical update to
        happen before FSM.

        If the policy violates its Protocol contract and returns a value
        equal to ``current``, we still treat it as a no-op: emitting a
        fresh :class:`~erre_sandbox.schemas.ERREMode` with a new
        ``entered_at_tick`` in that case would falsely mark a transition
        and confuse downstream dwell-time logic.

        The :class:`~erre_sandbox.schemas.ERREModeShiftEvent` is not
        emitted here: ``AgentUpdateMsg`` (Step 9) carries the new mode via
        ``agent_state.erre`` so Godot and memory can observe the change
        without a second event stream. If a future milestone requires an
        explicit shift event (e.g. for reflection scoring), emit it from
        here into either ``observations`` or the returned envelope list.
        """
        if self._erre_policy is None:
            return agent_state
        candidate = self._erre_policy.next_mode(
            current=agent_state.erre.name,
            zone=agent_state.position.zone,
            observations=observations,
            tick=agent_state.tick,
        )
        if candidate is None or candidate == agent_state.erre.name:
            return agent_state
        new_erre = ERREMode(
            name=candidate,
            entered_at_tick=agent_state.tick,
            sampling_overrides=self._erre_sampling_deltas[candidate],
        )
        logger.debug(
            "ERRE mode transition for agent %s: %s → %s (tick=%d)",
            agent_state.agent_id,
            agent_state.erre.name,
            candidate,
            agent_state.tick,
        )
        return agent_state.model_copy(update={"erre": new_erre})

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
        return envelopes


# ---------------------------------------------------------------------------
# Module-private helpers (pure)
# ---------------------------------------------------------------------------


def _observation_content_for_embed(obs: Observation) -> str:
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


__all__ = [
    "CognitionCycle",
    "CognitionError",
    "CycleResult",
]
