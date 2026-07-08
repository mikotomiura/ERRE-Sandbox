"""ECL B — competing-destination cue fixture + frozen-context provenance pass.

Issue 001 (``loop/20260708-m13-b-code-impl/issues/001-competing-cue-provenance.md``)
of the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md``
(§I1 lever / §I3 frozen schema / §I7 T3 materiality). Builds the **frozen
context generation side** of the 反復 (iterated) frozen-context bank: an
*enriched substrate* — structurally symmetric affordance / zone_transition
cues and content-mirrored memory across a competing-destination zone pair,
mounted on a neutral persona + frozen :class:`~erre_sandbox.schemas.AgentState`
snapshot — from which the untouched live organ renders one real ``(system_prompt,
user_prompt)`` pair via a single full-cycle **provenance pass**
(:func:`run_provenance_pass`, driven through
:func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop`, never modified).

§I1.1/§I1.2 (binding, non-reopenable — a fork here is a Stop condition,
superseding-ADR territory): the lever is the **zone-pick-visible prompt cue**,
not memory geometry. ``destination_zone`` is chosen by the LLM itself
(``cognition.parse.LLMPlan.destination_zone``); the resolver
(``cognition.embodiment.resolve_destination`` /
``strength_weighted_centroid``) only turns an already-chosen zone into
in-zone coordinates and cannot move ``H(zone|ctx)`` by construction. Memory
*geometry* (centroid/jitter/clamp) is therefore never touched by this fixture
— only prompt-visible *content* mirroring per zone.

Pieces this module owns:

* :data:`BANK_Z_COMP` / :data:`BANK_NEUTRAL_ZONE` / :data:`BANK_LAMBDA_CTX` —
  result-independent literal cue constants (forking-paths seal, §I1). Never
  imported from ``evidence.*``.
* :class:`CompetingCueSubstrate` — the frozen enriched-substrate bundle
  (neutral persona / frozen ``AgentState`` snapshot / symmetric observations /
  content-mirrored memories), built exclusively through
  :func:`build_competing_cue_substrate` via ``model_validate`` fixture edits
  (T3 materiality criterion 1, §I7) — never a hand-written prompt string.
* :class:`FrozenContext` — the byte-immutable frozen-context asset
  (``frozen_ctx_id`` / ``system_prompt`` / ``user_prompt`` / ``sampling_on`` /
  ``sampling_off``, §I3).
* :func:`run_provenance_pass` — the substrate-provenance graft (§I1.3/§I3.4):
  drives the enriched substrate through the untouched
  :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` for exactly one
  full cognition-cycle pass per condition (T_on / T_off), pinning
  ``ERRE_ZONE_BIAS_P=0`` (§I1.4, zone-bias/lever confound removal) and
  asserting ``bias_fired is None`` on both draws. The captured
  ``EclDecisionRecord.call.system_prompt`` / ``call.user_prompt`` are exactly
  what the canonical builders (``cognition.prompting.build_system_prompt`` /
  ``build_user_prompt``) rendered *inside* the live cycle — this module never
  calls them directly, it only supplies canonical inputs.

Scope guard (§I9, binding, mirrors ``live.py`` / ``live_v1.py`` / ``loop.py``).
This is a *construction* apparatus, **NOT a measurement line**. It computes
no ``H(zone|ctx)`` / count / diversity / divergence / floor / verdict, and
imports no ``evidence`` / ``spdm`` / ``runningness`` machinery. The bake-out
M-loop and ``BankLlmCallRecord`` (§I5) are Issue 002's scope, not this
module's; this module only builds the frozen-context generation side and
proves the provenance pass is wired through the canonical, unmodified organ.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from erre_sandbox.integration.embodied import live
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient, run_ecl_loop
from erre_sandbox.memory import RankedMemory
from erre_sandbox.schemas import (
    AffordanceEvent,
    AgentState,
    LocomotionState,
    MemoryEntry,
    MemoryKind,
    PersonalityTraits,
    PersonaSpec,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import Observation

# --------------------------------------------------------------------------- #
# Pre-registered cue constants (result-independent, forking-paths seal, §I1)
# --------------------------------------------------------------------------- #

BANK_Z_COMP: Final[tuple[Zone, Zone]] = (Zone.STUDY, Zone.GARDEN)
"""The competing-destination zone pair Z_comp (§I1.1). A **literal** pair —
never imported from ``evidence.*``. Fixed before any fixture was inspected for
its effect (forking-paths seal, §I1.5): the fixture is never re-cut after
observing a collapse."""

BANK_NEUTRAL_ZONE: Final[Zone] = Zone.AGORA
"""The frozen :class:`~erre_sandbox.schemas.AgentState` snapshot's spawn zone
(§I3.2) — the "third zone" outside :data:`BANK_Z_COMP`, so the agent's actual
position never pre-commits to either competing destination."""

BANK_LAMBDA_CTX: Final[tuple[float, ...]] = (0.4,)
"""Per-context frozen λ_ctx (§I3.3), literal and result-independent. Index 0
is this Issue's single frozen context (``bank-ctx-0``); the tuple shape is
pre-registered so Issue 002's K-context bank driver can extend it without a
superseding ADR. λ_ctx > 0 so T_on's :class:`~erre_sandbox.schemas.LocomotionState`
seeds a non-zero locomotion-sampling delta from tick 0 (the seed is a *direct*
state — no movement needs to be "earned" first, mirroring
``live_v1.locomotion_seeded_agent_state``'s λ₀ semantics). Never imported from
``evidence.*``; the ES-3 frozen gains themselves are read from
``erre_sandbox.erre.locomotion_sampling`` (the production defaults), not
duplicated here."""

BANK_PERSONA_ID: Final[str] = "bank-neutral"
"""Persona id of the fixture's neutral persona (§I3.1: empty preferred_zones,
no cognitive habits, personality left at library defaults)."""

BANK_AGENT_ID: Final[str] = "bank-agent-0"
"""Agent id of the fixture's frozen :class:`~erre_sandbox.schemas.AgentState`."""

_BANK_CUE_PROP_KIND: Final[str] = "bank_cue_prop"
_BANK_CUE_DISTANCE_M: Final[float] = 3.0
_BANK_CUE_SALIENCE: Final[float] = 0.6
"""Shared affordance distance/salience across every Z_comp zone (§I1.1/§I3.1):
structural symmetry means the cue differs *only* in the zone-derived fields
(``prop_id`` / ``zone`` / ``to_zone``), never in distance or salience."""

_BANK_MEMORY_KIND: Final[MemoryKind] = MemoryKind.EPISODIC
_BANK_MEMORY_IMPORTANCE: Final[float] = 0.6
_BANK_MEMORY_STRENGTH: Final[float] = 0.7
_BANK_MEMORY_COSINE: Final[float] = 0.9
"""Shared content-mirrored memory parameters (§I1.3): every Z_comp zone gets
one :class:`~erre_sandbox.memory.RankedMemory` built directly (kind/strength/
content assigned, no retriever call, §I1.3), identical on every axis except
the zone-mirrored ``content`` string."""

BANK_MEMORY_CREATED_AT: Final[datetime] = datetime(2026, 7, 8, 0, 0, 0, tzinfo=UTC)
"""Fixed pin for every mirror memory's ``MemoryEntry.created_at`` (TASK-POST
/cross-review HIGH/H4, Codex).

Unpinned, ``MemoryEntry.created_at`` falls to ``schemas._utc_now``'s
``default_factory`` — a *dynamic* wall-clock read at fixture-construction
time, never a ``libm`` float (``feedback_golden_crossplatform_float_drift``'s
sub-ULP drift channel does not apply here). ``retrieval.py``'s
``_rank_scope`` totally orders same-scope candidates by ``(-strength,
created_at, id)`` (retrieval.py:250, untouched); every :data:`BANK_Z_COMP`
mirror memory shares the same ``strength``/``cosine_sim`` (§I1.3), so
``created_at`` is the live tie-break axis feeding ``retriever.retrieve`` →
``cognition.prompting.format_memories`` (which itself only stable-sorts by
``strength``, so a ``created_at``-order flip propagates straight into the
frozen prompt's memory-bullet order). Two mirror memories built microseconds
apart from an unpinned wall clock could tie (falling through to the ``id``
tie-break) on a coarse-resolution clock but *not* tie (true construction-order
wins) on a fine-resolution one — a clock-resolution-dependent cross-platform
flip the ``env.md`` "libm float 非在" analysis did not cover. Pinning to this
literal constant (offset per zone by :func:`build_competing_cue_substrate`'s
enumeration index) makes the tie-break axis itself a frozen, platform-
independent literal."""

ZONE_BIAS_ENV_VAR: Final[str] = "ERRE_ZONE_BIAS_P"
"""The env var ``cognition.cycle.CognitionCycle`` reads at construction for
the ``_bias_target_zone`` resample probability (default ``"0.2"``). Pinned to
``"0"`` for the duration of :func:`run_provenance_pass` (§I1.4, Codex
事実誤認 HIGH-1: removes the post-LLM zone-bias confound with the lever's
symmetric ``preferred_zones``)."""


# --------------------------------------------------------------------------- #
# Enriched substrate (canonical-inputs-only fixture, T3 materiality criterion 1)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CompetingCueSubstrate:
    """The frozen enriched substrate for one context (§I1.3/§I3.1).

    Every field is built through :func:`build_competing_cue_substrate` via
    ``model_validate`` fixture edits on canonical ``schemas`` types — never a
    hand-written prompt string (T3 materiality criterion 1, §I7). The live
    organ (``run_ecl_loop`` → ``CognitionCycle``) is the *only* thing that ever
    turns this substrate into an actual rendered prompt (§I1.3 provenance).
    """

    context_id: str
    persona: PersonaSpec
    agent_state: AgentState
    observations: tuple[Observation, ...]
    memories: tuple[RankedMemory, ...]


def build_competing_cue_substrate(
    *, context_id: str = "bank-ctx-0"
) -> CompetingCueSubstrate:
    """Build one frozen, symmetric competing-destination-cue substrate (§I1.1).

    Neutral persona (``preferred_zones=[]``, no habits) + a frozen
    :class:`~erre_sandbox.schemas.AgentState` snapshot spawned at
    :data:`BANK_NEUTRAL_ZONE` with a neutral ERRE mode/physical/cognitive
    state, plus — for each zone in :data:`BANK_Z_COMP` — one structurally
    identical :class:`~erre_sandbox.schemas.AffordanceEvent` +
    :class:`~erre_sandbox.schemas.ZoneTransitionEvent` pair (same salience,
    same distance, same event count; only the zone-derived fields differ) and
    one content-mirrored :class:`~erre_sandbox.memory.RankedMemory` (same
    kind/strength/cosine_sim; only the zone-referencing ``content`` string
    differs). This is the *designer-constructed* symmetric competition §I1.5
    is honest about — it licenses more than one zone in the substrate, it does
    not (and cannot) prove ``H(zone|ctx)`` is non-degenerate.
    """
    persona = PersonaSpec.model_validate(
        {
            "persona_id": BANK_PERSONA_ID,
            "display_name": "Bank Neutral Agent",
            "era": "n/a",
            "personality": PersonalityTraits().model_dump(),
            "cognitive_habits": [],
            "preferred_zones": [],
        }
    )
    agent_state = AgentState.model_validate(
        {
            "agent_id": BANK_AGENT_ID,
            "persona_id": BANK_PERSONA_ID,
            "tick": 0,
            "position": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "zone": BANK_NEUTRAL_ZONE.value,
            },
            "erre": {"name": "shallow", "entered_at_tick": 0},
        }
    )
    observations: list[Observation] = []
    memories: list[RankedMemory] = []
    for index, zone in enumerate(BANK_Z_COMP):
        observations.append(
            AffordanceEvent.model_validate(
                {
                    "tick": 0,
                    "agent_id": BANK_AGENT_ID,
                    "prop_id": f"bank-cue-{zone.value}",
                    "prop_kind": _BANK_CUE_PROP_KIND,
                    "zone": zone.value,
                    "distance": _BANK_CUE_DISTANCE_M,
                    "salience": _BANK_CUE_SALIENCE,
                }
            )
        )
        observations.append(
            ZoneTransitionEvent.model_validate(
                {
                    "tick": 0,
                    "agent_id": BANK_AGENT_ID,
                    "from_zone": BANK_NEUTRAL_ZONE.value,
                    "to_zone": zone.value,
                }
            )
        )
        entry = MemoryEntry.model_validate(
            {
                "id": f"bank-mem-{zone.value}",
                "agent_id": BANK_AGENT_ID,
                "kind": _BANK_MEMORY_KIND.value,
                "content": (
                    f"a vivid recollection formed while lingering near {zone.value}"
                ),
                "importance": _BANK_MEMORY_IMPORTANCE,
                # H4 pin (see BANK_MEMORY_CREATED_AT docstring): a per-zone
                # microsecond offset by construction-order index, never the
                # unpinned wall-clock default_factory.
                "created_at": BANK_MEMORY_CREATED_AT + timedelta(microseconds=index),
            }
        )
        memories.append(
            RankedMemory(
                entry=entry,
                strength=_BANK_MEMORY_STRENGTH,
                cosine_sim=_BANK_MEMORY_COSINE,
            )
        )
    return CompetingCueSubstrate(
        context_id=context_id,
        persona=persona,
        agent_state=agent_state,
        observations=tuple(observations),
        memories=tuple(memories),
    )


# --------------------------------------------------------------------------- #
# Frozen context schema (§I3, byte-immutable pin)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FrozenContext:
    """One frozen, byte-immutable context (§I3): the provenance-pass output.

    ``system_prompt`` / ``user_prompt`` are byte-identical across T_on/T_off
    (locomotion never renders into either canonical builder's output, §I3.3);
    ``sampling_on`` / ``sampling_off`` are the two resolved samplings the
    locomotion channel actually produced (λ_ctx-modulated vs. unmodulated).
    """

    frozen_ctx_id: str
    system_prompt: str
    user_prompt: str
    sampling_on: ResolvedSampling
    sampling_off: ResolvedSampling


# --------------------------------------------------------------------------- #
# Zone-bias pin (§I1.4, Codex 事実誤認 HIGH-1: removes the lever/bias confound)
# --------------------------------------------------------------------------- #


@contextmanager
def _pinned_zone_bias_off() -> Iterator[None]:
    """Pin :data:`ZONE_BIAS_ENV_VAR` to ``"0"`` for the wrapped scope (§I1.4).

    ``CognitionCycle`` reads the env var once at construction time (never
    per-tick), so this must be set *before* ``run_ecl_loop`` constructs its
    cycle. Restores the prior value (or absence) on exit so this module never
    leaks process-global state past one :func:`run_provenance_pass` call.
    """
    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "0"
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(ZONE_BIAS_ENV_VAR, None)
        else:
            os.environ[ZONE_BIAS_ENV_VAR] = prior


async def _preload_mirror_memories(
    store: MemoryStore,
    embedding: EmbeddingClient,
    substrate: CompetingCueSubstrate,
) -> None:
    """Pre-load *exactly* the substrate's mirror memories into ``store`` (§I1.1(d)).

    The lever's fourth dimension (§I1.1) is a memory whose *content* mirrors
    each Z_comp zone. For that content to reach the frozen prompt it must
    render through the organ's own canonical path (the cycle's
    ``retriever.retrieve`` → ``cognition.prompting.format_memories``), not be
    hand-written — so this loads the static, result-independent mirror set into
    the store and lets the untouched cycle surface it (§I3.1). "retriever 非
    呼出" (§I1/§I3.1) means "no result-dependent selection over a large
    corpus", not "bypass ``format_memories``": the store holds **strictly** the
    K_comp mirror rows, so the retrieval is a static pin (result-independent),
    consistent with the provenance pass's retrieve-count=1×K (§I2.2/§I6, the
    M-loop's retrieve-count=0 is a separate contract, Issue 002).

    Each row is embedded through the injected ``embedding`` client's canonical
    ``embed_document`` (the constant-vector mock in construction tests, D-10 —
    never real ``nomic-embed-text``), so every mirror row surfaces with an
    identical cosine and no zone is silently dropped (symmetric surfacing).
    """
    for memory in substrate.memories:
        doc_vec = await embedding.embed_document(memory.entry.content)
        await store.add(memory.entry, embedding=doc_vec)


def _substrate_observation_factory(
    substrate: CompetingCueSubstrate,
) -> Callable[[int], tuple[Observation, ...]]:
    """Build a per-tick observation factory for the provenance pass.

    Emits the substrate's symmetric cue on tick 0 only, nothing after (§I3.4:
    a single full-cycle provenance pass, not a multi-tick accumulation).
    """

    def factory(agent_tick: int) -> tuple[Observation, ...]:
        return substrate.observations if agent_tick == 0 else ()

    return factory


async def _run_condition(
    *,
    substrate: CompetingCueSubstrate,
    agent_state: AgentState,
    inner_chat: Any,
    store_factory: Callable[[], MemoryStore],
    embedding: EmbeddingClient,
    run_id: str,
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int,
) -> EclRunResult:
    """Drive one full-cycle provenance pass through the untouched organ.

    ``store_factory`` builds a **fresh** store per condition (T_on / T_off
    never share state) so the two rendered prompts cannot diverge from
    cross-condition memory contamination — the structural reason §I3.3's
    "prompt byte-identical across T_on/T_off" holds unconditionally, not just
    because locomotion happens to be prompt-invisible. The store is pre-loaded
    with **exactly** the substrate's mirror memories (§I1.1(d)) so the cycle's
    own retriever surfaces them into the frozen prompt; both conditions load the
    identical rows (memory is λ-independent), preserving §I3.3 byte-identity.
    """
    store = store_factory()
    store.create_schema()
    await _preload_mirror_memories(store, embedding, substrate)
    think_off = live.ThinkOffChatClient(inner_chat)
    llm = RecordReplayChatClient(inner=think_off)
    try:
        return await run_ecl_loop(
            run_id=run_id,
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=agent_state,
            persona=substrate.persona,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
            seed=seed,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=1,
            observation_factory=_substrate_observation_factory(substrate),
        )
    finally:
        await store.close()


async def run_provenance_pass(
    *,
    substrate: CompetingCueSubstrate,
    inner_chat: Any,
    store_factory: Callable[[], MemoryStore],
    embedding: EmbeddingClient,
    run_id: str,
    retrieval_now: datetime,
    base_ts: datetime,
    lambda_ctx: float = BANK_LAMBDA_CTX[0],
    seed: int = 0,
) -> FrozenContext:
    """Render + freeze one context from the enriched substrate (§I1.3/§I3.4).

    Drives exactly two one-tick full-cycle passes through the untouched
    :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` — T_on
    (``locomotion=LocomotionState(lam=lambda_ctx)``) and T_off
    (``locomotion=None``) — with :data:`ZONE_BIAS_ENV_VAR` pinned to ``"0"``
    for both (§I1.4). Each pass yields exactly one
    :class:`~erre_sandbox.integration.embodied.loop.EclDecisionRecord`, whose
    ``call.system_prompt`` / ``call.user_prompt`` are exactly what
    ``cognition.prompting.build_system_prompt`` / ``build_user_prompt``
    rendered *inside* the cycle for this substrate — this function never calls
    either builder itself. Asserts ``bias_fired is None`` on both draws (the
    zone-bias/lever confound removal is a structural invariant, not just a
    pinned probability) and that the two rendered prompts are byte-identical
    (§I3.3: λ never enters either canonical builder's output).
    """
    agent_state_on = substrate.agent_state.model_copy(
        update={"locomotion": LocomotionState(lam=lambda_ctx)}
    )
    agent_state_off = substrate.agent_state.model_copy(update={"locomotion": None})

    with _pinned_zone_bias_off():
        result_on = await _run_condition(
            substrate=substrate,
            agent_state=agent_state_on,
            inner_chat=inner_chat,
            store_factory=store_factory,
            embedding=embedding,
            run_id=f"{run_id}-on",
            retrieval_now=retrieval_now,
            base_ts=base_ts,
            seed=seed,
        )
        result_off = await _run_condition(
            substrate=substrate,
            agent_state=agent_state_off,
            inner_chat=inner_chat,
            store_factory=store_factory,
            embedding=embedding,
            run_id=f"{run_id}-off",
            retrieval_now=retrieval_now,
            base_ts=base_ts,
            seed=seed,
        )

    decision_on = result_on.decisions[0]
    decision_off = result_off.decisions[0]
    if decision_on.bias_fired is not None or decision_off.bias_fired is not None:
        msg = (
            "run_provenance_pass: zone bias fired despite ERRE_ZONE_BIAS_P=0 pin "
            "(§I1.4 invariant violated)"
        )
        raise AssertionError(msg)
    if (
        decision_on.call.system_prompt != decision_off.call.system_prompt
        or decision_on.call.user_prompt != decision_off.call.user_prompt
    ):
        msg = (
            "run_provenance_pass: T_on/T_off rendered non-identical prompts "
            "(§I3.3 invariant violated — locomotion must never enter either "
            "canonical builder's output)"
        )
        raise AssertionError(msg)

    return FrozenContext(
        frozen_ctx_id=substrate.context_id,
        system_prompt=decision_on.call.system_prompt,
        user_prompt=decision_on.call.user_prompt,
        sampling_on=decision_on.call.sampling,
        sampling_off=decision_off.call.sampling,
    )


__all__ = [
    "BANK_AGENT_ID",
    "BANK_LAMBDA_CTX",
    "BANK_MEMORY_CREATED_AT",
    "BANK_NEUTRAL_ZONE",
    "BANK_PERSONA_ID",
    "BANK_Z_COMP",
    "ZONE_BIAS_ENV_VAR",
    "CompetingCueSubstrate",
    "FrozenContext",
    "build_competing_cue_substrate",
    "run_provenance_pass",
]
