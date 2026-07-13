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

Issue 003 (I3) additions: the **versioned event/decision-log-wide checksum**
(:func:`event_log_checksum`, §M4.4 — geometry checksum, i.e.
:func:`ecl_trace_checksum`, is composed as *part of* it, not replaced by it)
and the ``self_other_observation_input`` Layer2 seam slot (§M5.1, always
``None`` here).

Issue 004 (I4) additions: **per-pair named RNG substreams** (:class:`_PairRngCache`,
§M4.2, ``pair_key`` = canonical JSON array, Codex MEDIUM-7 collision guard) and
a **record-mode dialog channel** (:class:`_DeterministicDialogTurnGenerator`):
this driver now attaches an
:class:`~erre_sandbox.integration.dialog.InMemoryDialogScheduler` to the
:class:`WorldRuntime` it constructs and, once per cognition window,
calls the world's existing (unmodified) ``_run_dialog_tick``/``_drive_dialog_turns``
hooks so that co-located agents can deterministically dialog — the auto-fire
draw is keyed by the pair's own named RNG substream, not the shared instance
``InMemoryDialogScheduler`` otherwise defaults to. Dialog turns are recorded
into ``dialog_events`` from a non-LLM, deterministically-templated generator
(construction provenance, not persona cognition — §M8 spend guard: no new LLM
call). **Dialog and affinity are Layer1 social dynamics** (§M4.2/§M4.4), not
Layer2 mirror-sim (§M5) — self-other simulation is a distinct, later concern.
Affinity mutation (``WorldRuntime.apply_affinity_delta``) remains unwired here:
its sole producer in the codebase is ``bootstrap.py`` application wiring
(outside this issue's Allowed Files), so ``affinity_deltas`` stays honestly
empty. Out of scope for this issue (deferred to later I-slices, §M11): handoff
N-agent schema bump (I5), spend AST guard (I6).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from random import Random
from typing import TYPE_CHECKING, Any, Final, cast

from erre_sandbox.cognition import BiasFiredEvent, CognitionCycle, parse_llm_plan
from erre_sandbox.cognition.embodiment import K_ECL, EclRecordMode
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.integration.embodied.handoff import _quantize_embedded_json
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
from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    DialogTurnMsg,
    PerceptionEvent,
    ProximityEvent,
    Zone,
)
from erre_sandbox.world import ManualClock, WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime

    from erre_sandbox.cognition import CycleResult, LLMPlan
    from erre_sandbox.cognition.embodiment import EclDestination
    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec


# --------------------------------------------------------------------------- #
# Per-pair named RNG substream (§M4.2, I4)
# --------------------------------------------------------------------------- #


def _pair_key(a_id: str, b_id: str) -> str:
    """Canonical, collision-free pair identity (§M4.2, Codex MEDIUM-7).

    ``"-".join(sorted([a_id, b_id]))`` collides when an ``agent_id`` itself
    contains ``"-"`` (``["a-b", "c"]`` and ``["a", "b-c"]`` both join to the
    string ``"a-b-c"``). A canonical JSON array of the two sorted ids has no
    such collision: each element is individually quoted/escaped by
    ``json.dumps``, so the array's structural comma-between-two-quoted-strings
    delimiter cannot be produced by any character sequence *inside* either id.
    ``sorted(...)`` first makes the key order-agnostic (``_pair_key(a, b) ==
    _pair_key(b, a)``); ``ensure_ascii=True`` and compact ``separators`` keep
    the material a single canonical, 7-bit-stable string per pair.
    """
    return json.dumps(sorted([a_id, b_id]), separators=(",", ":"), ensure_ascii=True)


@dataclass(slots=True)
class _PairRngCache:
    """Per-pair named RNG substream: ``ecl-{run_id}-{pair_key}-{stream}`` (§M4.2).

    Mirrors :meth:`~erre_sandbox.cognition.embodiment.EclRecordMode.substream`'s
    memoize-on-first-call idiom one level up (per unordered *pair* instead of
    per-agent): the first :meth:`get` for a given pair seeds
    ``random.Random(f"ecl-{run_id}-{pair_key}-{stream}")`` (:func:`_pair_key`
    makes this order-agnostic); every later call for the *same* pair returns
    that same handle, so its draws form one run-sequence rather than
    restarting from the seed each tick — a byte-identical re-run with the same
    ``run_id`` reproduces a byte-identical draw sequence. **No new Python
    non-determinism source** (§M4.2): this is a named-substream regularity
    extension of the existing per-agent idiom, not a new randomness primitive.
    """

    run_id: str
    stream: str
    _cache: dict[str, Random] = field(default_factory=dict, init=False, repr=False)

    def get(self, a_id: str, b_id: str) -> Random:
        """Return (creating on first call) the named substream for ``{a_id, b_id}``."""
        key = _pair_key(a_id, b_id)
        rng = self._cache.get(key)
        if rng is None:
            rng = Random(f"ecl-{self.run_id}-{key}-{self.stream}")  # noqa: S311 — determinism seed, not cryptographic
            self._cache[key] = rng
        return rng


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
# Issue 003 (I3) — versioned event/decision-log-wide checksum + self-other seam
# --------------------------------------------------------------------------- #

M2_EVENTLOG_SCHEMA_VERSION: Final[str] = "m2-eventlog-1"
"""Versioned-additive schema tag for :func:`event_log_checksum`'s canonical
projection (§M4.4). Bump on any additive change to the categories folded into
the checksum (a schema-version-only change is expected to change the digest —
that is a *construction* schema pin, not a floor/verdict)."""

_EVENTLOG_FLOAT_DECIMALS: Final[int] = 6
"""6-decimal float quantisation, design-copied from
``loop._TRACE_FLOAT_DECIMALS`` / ``ecl_trace_checksum`` (not imported — that
name is module-private to ``loop.py``, mirroring this module's existing
design-copy convention for ``_default_observation_factory``). Absorbs the same
sub-ULP cross-platform ``libm`` drift ``ecl_trace_checksum`` documents, so the
event-log-wide checksum stays byte-identical across platforms too
(``feedback_golden_crossplatform_float_drift``)."""


def _q(value: float) -> float:
    """Quantise one float to :data:`_EVENTLOG_FLOAT_DECIMALS` decimals."""
    return round(value, _EVENTLOG_FLOAT_DECIMALS)


@dataclass(frozen=True, slots=True)
class PairEventRecord:
    """One canonical pair-interaction event (proximity crossing, §M4.4).

    Harvested read-only from ``WorldRuntime``'s per-agent pending-observation
    queue (:func:`_harvest_pair_events`) right after a cognition window's
    physics-tick block, before the next window's ``step_cognition_once`` call
    drains it (``world/tick.py`` ``_step_one``, unmodified). Only the
    canonical ``agent_id < other_agent_id`` side of each crossing is kept —
    ``_fire_proximity_events`` (already sorted-pair per §M4.3) appends the
    same crossing to *both* agents' queues with the ids swapped, so keeping
    one side avoids double-counting.

    Separation nudges (``_apply_separation_force``) apply no discrete
    ``Observation`` event — only a position mutation already reflected in the
    ``EclTraceRow`` geometry rows folded into ``geometry_checksum`` — so "pair
    events (proximity/separation)" (§M4.4) resolves to proximity-crossing
    records here; separation's effect is witnessed through geometry, not a
    second event stream.
    """

    tick: int
    sorted_pair: tuple[str, str]
    distance_prev: float
    distance_now: float
    crossing: str


@dataclass(frozen=True, slots=True)
class DialogEventRecord:
    """One recorded dialog turn (§M4.4) — Layer1 social dynamics, not Layer2 mirror-sim.

    Produced by this driver (I4): ``run_society_loop`` attaches an
    :class:`~erre_sandbox.integration.dialog.InMemoryDialogScheduler` and a
    non-LLM :class:`_DeterministicDialogTurnGenerator` to the
    :class:`WorldRuntime` it constructs, and calls the world's existing
    (unmodified) ``_run_dialog_tick``/``_drive_dialog_turns`` hooks once per
    cognition window (§M4.1's live phase-wheel, ``_on_cognition_tick``, is
    still never called — those two dialog-only hooks carry no due-time/dwell
    gating and are reused directly). Whether any dialog actually fires in a
    given run is scenario-dependent (co-location + the pair's own named RNG
    substream draw, §M4.2); an empty ``dialog_events`` tuple is a legitimate
    outcome, not a driver limitation. This is Layer1 pair-interaction
    provenance — self-other *simulation* (Layer2, §M5) is a distinct, later
    concern this record does not model.
    """

    dialog_id: str
    tick: int
    turn_index: int
    speaker_agent_id: str
    addressee_agent_id: str
    utterance: str


@dataclass(slots=True)
class _DeterministicDialogTurnGenerator:
    """Construction-only dialog-turn synthesis (I4, §M8 spend guard).

    Implements the :class:`~erre_sandbox.schemas.DialogTurnGenerator` Protocol
    duck-typed surface (``generate_turn``) with **no LLM call**: DG-6
    (``.steering/20260711-m13-m2-society-layer1-code/decisions.md``) requires
    this record-mode driver to close the I3 gap where dialog never fired,
    without adding a new LLM call (§M8 spend non-drift) or touching the live
    phase-wheel's LLM-backed dialog-turn generation (a distinct, later
    concern — this is not persona-authored dialog, it is construction
    provenance that a turn happened). The utterance is a fixed deterministic
    template keyed only by ``(dialog_id, turn_index, speaker/addressee
    agent_id)`` — no additional Python non-determinism source is introduced.
    Every produced turn is also appended to ``dialog_events`` via ``on_turn``
    so :func:`run_society_loop` can fold it into the versioned event log.
    """

    on_turn: Callable[[DialogEventRecord], None]

    async def generate_turn(
        self,
        *,
        dialog_id: str,
        speaker_state: AgentState,
        speaker_persona: PersonaSpec,
        addressee_state: AgentState,
        transcript: Sequence[DialogTurnMsg],
        world_tick: int,
    ) -> DialogTurnMsg | None:
        del speaker_persona  # construction-only synthesis, not persona-authored (§M8)
        turn_index = len(transcript)
        utterance = (
            f"m2-society-turn dialog={dialog_id} idx={turn_index} "
            f"speaker={speaker_state.agent_id}"
        )
        self.on_turn(
            DialogEventRecord(
                dialog_id=dialog_id,
                tick=world_tick,
                turn_index=turn_index,
                speaker_agent_id=speaker_state.agent_id,
                addressee_agent_id=addressee_state.agent_id,
                utterance=utterance,
            )
        )
        return DialogTurnMsg(
            tick=world_tick,
            dialog_id=dialog_id,
            speaker_id=speaker_state.agent_id,
            addressee_id=addressee_state.agent_id,
            utterance=utterance,
            turn_index=turn_index,
        )


@dataclass(frozen=True, slots=True)
class AffinityDeltaRecord:
    """Versioned-additive affinity-delta slot (§M4.4) — Layer1 social dynamics.

    Not produced by this driver (I4 checked, honest-empty per DG-6):
    ``run_society_loop`` never calls ``WorldRuntime.apply_affinity_delta`` —
    its sole producer in the codebase is ``bootstrap.py`` application wiring
    (outside this module's Allowed Files), not something that flows
    automatically out of a cognition step or the dialog channel this driver
    now wires (I4). Every :func:`run_society_loop` result therefore carries an
    empty ``affinity_deltas`` tuple; the type exists so the checksum schema is
    forward-compatible once a record-mode driver applies affinity mutations,
    without a schema break. Affinity is Layer1 relationship state, not Layer2
    mirror-sim (§M5) self-other simulation.
    """

    tick: int
    agent_id: str
    other_agent_id: str
    delta: float
    resulting_affinity: float


@dataclass(frozen=True, slots=True)
class MemoryMutationRecord:
    """One committed memory-store row (§M4.4), read-only after the run.

    Harvested from ``episodic_memory`` only (:func:`_collect_memory_mutations`)
    — reflection is disabled in this driver's ``EclRecordMode``
    (``reflection_disabled=True``), so semantic/procedural/relational rows are
    never written in Layer1 record mode.
    """

    memory_id: str
    agent_id: str
    kind: str
    content: str
    importance: float
    created_at: str
    tags: tuple[str, ...]


SelfOtherObservationInput = dict[str, Any] | None
"""Layer2 seam wire envelope (§M5.1, binding, versioned additive):
``None | {"schema_version": str, "payload": object}``. Layer1
(:func:`run_society_loop`) always passes ``None``. The concrete ``payload``
field composition is Layer2 scope (deferred to the mirror-sim impl-design ADR,
§M5.4) and is deliberately NOT modelled beyond this envelope shape here
(引っ張り禁止 — pulling that design forward is out of scope for this issue)."""


def _validate_self_other_slot(value: SelfOtherObservationInput) -> None:
    """Enforce the frozen minimal wire envelope (§M5.1) before hashing.

    ``None`` is always valid (the Layer1 case). A non-``None`` value must be
    exactly ``{"schema_version": str, "payload": object}`` — no more, no
    fewer keys — so a malformed envelope fails loudly here rather than being
    silently hashed as if it were valid Layer2 seam data.
    """
    if value is None:
        return
    if set(value) != {"schema_version", "payload"}:
        msg = (
            "self_other_observation_input must be None or exactly "
            f'{{"schema_version": str, "payload": object}}; got keys {sorted(value)}'
        )
        raise ValueError(msg)
    if not isinstance(value["schema_version"], str):
        msg = "self_other_observation_input['schema_version'] must be a str"
        raise TypeError(msg)


# --------------------------------------------------------------------------- #
# Layer2 (mirror-sim) — pure self-other context builder (§L3/§L7, J2)
#
# NOT a structural-floor verdict; verdict は holding (design-final.md §L4/§L13).
# This is a *construction* seam: a pure, deterministic function of the other
# agents' prior-window observed behaviour. It computes no floor / verdict /
# scorer / divergence / magnitude — it renders a SimToM prompt segment (a
# **functional analog** of taking another agent's perspective, NOT a neural
# mirror-neuron mechanism, §L1 規律 b) and a canonical float-free payload piece.
# --------------------------------------------------------------------------- #

M2_SELFOTHER_SCHEMA_VERSION: Final[str] = "m2-selfother-1"
"""Versioned-additive wire tag for the Layer2 ``self_other_observation_input``
slot payload (§L7). Distinct from :data:`M2_EVENTLOG_SCHEMA_VERSION` (the whole
event-log projection tag) — this versions the self-other payload shape only."""

_SELF_OTHER_FRAMING: Final[str] = (
    "Others you observed one step ago — simulate each one's likely inner state "
    "and let it inform your own next action. This is a functional analog of "
    "taking their perspective, not a claim about their true mind:"
)
"""SimToM prompt framing (§L3/§L7, prompt-level self-other simulation, 予算ゼロ
規律 c). Functional-analog vocabulary only (規律 b — no "mirror neuron / neural
mechanism / 神経機構再現"). Bounded and imperative so a think=False low-entropy
decode stays parseable (文献 §9-ii); the think=False parseability desk-audit
(§L11) is recorded in ``experiments/20260713-m13-m2-layer2/``."""


@dataclass(frozen=True, slots=True)
class SelfOtherPriorRecord:
    """One other agent's prior-window observed behaviour (builder input, §L7).

    A pure value object the driver (:func:`run_society_loop`, J3) assembles from
    the Layer1 event log it already records — ``zone``/``destination_zone`` from
    the geometry + resolved move, ``utterance`` from ``dialog_events``,
    ``was_proximate`` from ``pair_events`` (a plain bool — no distance float, so
    the payload stays float-free, §L7). Carries **only** already-recorded
    behaviour events — never an ``AppraisalState`` measurement field (規律 d): the
    observer *simulates* the other's inner state in the SimToM prompt, it is not
    stored as a measured value here.
    """

    agent_id: str
    window: int
    zone: str
    destination_zone: str | None = None
    utterance: str | None = None
    was_proximate: bool = False


@dataclass(frozen=True, slots=True)
class SelfOtherObservedRecord:
    """One observed other agent inside a :class:`SelfOtherContext` (§L7 ``observed``).

    Canonical, float-free projection: every scalar is ``{str, int, bool, None}``
    (the slot payload does not pass through :func:`_q`'s quantisation, so a float
    here would drift cross-platform — §L2/§L7, judgement 3 教訓)."""

    other_agent_id: str
    observed_zone: str
    observed_destination_zone: str | None
    observed_utterance: str | None
    was_proximate: bool

    def payload(self) -> dict[str, Any]:
        return {
            "other_agent_id": self.other_agent_id,
            "observed_zone": self.observed_zone,
            "observed_destination_zone": self.observed_destination_zone,
            "observed_utterance": self.observed_utterance,
            "was_proximate": self.was_proximate,
        }


@dataclass(frozen=True, slots=True)
class SelfOtherContext:
    """One observer's self-other injection at one cognition window (§L3/§L7).

    ``rendered`` is the deterministic SimToM text segment fed to
    :func:`~erre_sandbox.cognition.prompting.build_user_prompt`'s
    ``self_other_context`` kwarg (``""`` when no other agent was observed —
    window 0 or an all-empty prior window, §L4.3 → no slot contribution).
    :meth:`injection_payload` is the canonical, float-free payload piece the
    run-level slot aggregates (J3).
    """

    observer_agent_id: str
    window: int
    source_window: int
    observed: tuple[SelfOtherObservedRecord, ...]
    rendered: str

    @property
    def is_empty(self) -> bool:
        """``True`` when no other agent was observed (no slot contribution)."""
        return not self.observed

    def injection_payload(self) -> dict[str, Any]:
        """Canonical injection dict (§L7): ``observed`` already builder-sorted."""
        return {
            "window": self.window,
            "observer_agent_id": self.observer_agent_id,
            "source_window": self.source_window,
            "observed": [r.payload() for r in self.observed],
        }


def _render_self_other(observed: Sequence[SelfOtherObservedRecord]) -> str:
    """Deterministic SimToM segment render (pure function of ``observed``, §L7)."""
    lines = [_SELF_OTHER_FRAMING]
    for r in observed:
        parts = [f"zone={r.observed_zone}"]
        if r.observed_destination_zone is not None:
            parts.append(f"moved_toward={r.observed_destination_zone}")
        if r.observed_utterance is not None:
            parts.append(f'said="{r.observed_utterance}"')
        if r.was_proximate:
            parts.append("was_near_you")
        lines.append(f"- {r.other_agent_id}: {', '.join(parts)}")
    return "\n".join(lines)


def build_self_other_context(
    *,
    observer_id: str,
    window_index: int,
    prior_records: Sequence[SelfOtherPriorRecord],
) -> SelfOtherContext:
    """Build one observer's self-other context (pure, exact-oracle, §L3/§L7).

    NOT a structural-floor verdict; verdict は holding. A deterministic function
    of the other agents' prior-window behaviour: **strict prefix filter**
    (DA-L2-2, Codex HIGH-2) keeps only records where ``agent_id != observer_id``
    (never the observer's own action) **and** ``window == window_index - 1`` —
    the immediately-prior window ``source_window = t-1``, which is ``< window_index``
    by construction, so this-window / future-window records can never leak into
    the context (pinned by ``test_self_other_no_future_or_self_leak``). ``observed``
    is canonically sorted by ``other_agent_id`` (a total string order) so the
    payload/render are order-insensitive and float-free (``test_self_other_context_
    builder_purity``). ``window_index == 0`` → empty context (no prior window,
    honest). The build reads no store / memory / RNG / wall-clock — it is a pure
    seam boundary (§L6 disjointness: the observed input stream never touches the
    memory sink).
    """
    source_window = window_index - 1
    observed = tuple(
        SelfOtherObservedRecord(
            other_agent_id=r.agent_id,
            observed_zone=r.zone,
            observed_destination_zone=r.destination_zone,
            observed_utterance=r.utterance,
            was_proximate=r.was_proximate,
        )
        for r in sorted(
            (
                r
                for r in prior_records
                if r.agent_id != observer_id and r.window == source_window
            ),
            key=lambda r: r.agent_id,
        )
    )
    rendered = _render_self_other(observed) if observed else ""
    return SelfOtherContext(
        observer_agent_id=observer_id,
        window=window_index,
        source_window=source_window,
        observed=observed,
        rendered=rendered,
    )


def _pair_event_projection(e: PairEventRecord) -> dict[str, Any]:
    return {
        "tick": e.tick,
        "sorted_pair": list(e.sorted_pair),
        "distance_prev": _q(e.distance_prev),
        "distance_now": _q(e.distance_now),
        "crossing": e.crossing,
    }


def _dialog_event_projection(e: DialogEventRecord) -> dict[str, Any]:
    return {
        "dialog_id": e.dialog_id,
        "tick": e.tick,
        "turn_index": e.turn_index,
        "speaker_agent_id": e.speaker_agent_id,
        "addressee_agent_id": e.addressee_agent_id,
        "utterance": e.utterance,
    }


def _affinity_delta_projection(e: AffinityDeltaRecord) -> dict[str, Any]:
    return {
        "tick": e.tick,
        "agent_id": e.agent_id,
        "other_agent_id": e.other_agent_id,
        "delta": _q(e.delta),
        "resulting_affinity": _q(e.resulting_affinity),
    }


def _memory_mutation_projection(e: MemoryMutationRecord) -> dict[str, Any]:
    return {
        "memory_id": e.memory_id,
        "agent_id": e.agent_id,
        "kind": e.kind,
        "content": e.content,
        "importance": _q(e.importance),
        "created_at": e.created_at,
        "tags": list(e.tags),
    }


_PLAN_FLOAT_FIELDS: Final[tuple[str, ...]] = (
    "valence_delta",
    "arousal_delta",
    "motivation_delta",
    "importance_hint",
)
"""``LLMPlan``'s float fields (``cognition/parse.py``) — quantised the same
way every other float in the projection is (§M4.4's blanket 6-decimal rule),
even though these are parsed straight from decimal JSON text (deterministic,
no libm involved) rather than a computed trig value: uniform treatment keeps
the "every float in the projection is quantised" invariant simple to audit."""


def _quantized_plan_dump(plan: LLMPlan) -> dict[str, Any]:
    dumped = plan.model_dump(mode="json")
    for key in _PLAN_FLOAT_FIELDS:
        if key in dumped and dumped[key] is not None:
            dumped[key] = _q(dumped[key])
    return dumped


def _decision_projection(d: EclDecisionRecord) -> dict[str, Any]:
    """Canonical per-decision projection (per-agent LLMPlan replay, §M4.4).

    Excludes ``move_decision`` (``EclDestination``): its resolved fields are
    already the ``EclTraceRow.move_*`` columns folded into
    ``geometry_checksum`` (§M4.4, "geometry checksum is part of it"), so
    repeating it here would double-count the same provenance rather than add
    a new witness.

    ``envelope_provenance`` (superseding ADR, ``.steering/
    20260712-m13-m4-society-enrichment/decisions.md`` 判断3): each element is a
    *pre-serialised* ``ControlEnvelope.model_dump_json`` string, so its
    embedded floats (e.g. ``agent_state.cognitive.valence``/``mood_baseline``)
    are text and invisible to :func:`_q`'s blanket 6-decimal rule once the
    surrounding dict is canonicalised — the same gap
    :func:`~erre_sandbox.integration.embodied.handoff._quantize_embedded_json`
    closes for ``decisions.jsonl``. Reusing that exact helper here keeps the
    event-log checksum and the rendered ``decisions.jsonl`` on the *same*
    serializer for this field (Codex M-a/H1), makes ``event_log_checksum``'s
    witness semantic-normalized rather than raw-byte (Codex M-b), and repairs
    this module's own §M4.4 "every float in the projection is quantised"
    invariant, which this field silently violated before (the latent
    cross-platform drift the superseding ADR fixes).
    """
    return {
        "agent_tick": d.agent_tick,
        "call_outcome": d.call.outcome,
        "raw_response": d.call.raw_response,
        "plan": _quantized_plan_dump(d.plan) if d.plan is not None else None,
        "plan_schema_version": d.plan_schema_version,
        "llm_fell_back": d.llm_fell_back,
        "llm_status": d.llm_status,
        "bias_fired": (
            {**asdict(d.bias_fired), "bias_p": _q(d.bias_fired.bias_p)}
            if d.bias_fired is not None
            else None
        ),
        "envelope_provenance": [
            _quantize_embedded_json(env) for env in d.envelope_provenance
        ],
    }


def event_log_checksum(
    *,
    rows: Sequence[EclTraceRow],
    decisions: Mapping[str, Sequence[EclDecisionRecord]],
    pair_events: Sequence[PairEventRecord] = (),
    dialog_events: Sequence[DialogEventRecord] = (),
    affinity_deltas: Sequence[AffinityDeltaRecord] = (),
    memory_mutations: Sequence[MemoryMutationRecord] = (),
    self_other_observation_input: SelfOtherObservationInput = None,
) -> str:
    """SHA-256 over the **versioned event/decision log as a whole** (§M4.4).

    NOT a structural-floor verdict; verdict は holding (design-final.md §M9,
    binding anti-over-read guard). This proves *reproducibility* across the
    full construction event set — geometry (``EclTraceRow``, via
    :func:`ecl_trace_checksum`, composed as part of the whole, not replaced by
    it) + dialog events + affinity deltas + memory mutations + pair events +
    the ``self_other_observation_input`` slot (§M5.1, always ``None`` in
    Layer1) + per-agent ``LLMPlan`` replay (``EclDecisionRecord``) — not a
    metric, floor, or verdict.

    Every category is canonicalised the same way ``ecl_trace_checksum`` does:
    a stable JSON projection (``sort_keys=True`` + compact ``separators`` +
    ``ensure_ascii=False`` + ``allow_nan=False`` + 6-decimal float
    quantisation, :data:`_EVENTLOG_FLOAT_DECIMALS`) over an explicit
    full-order-key sort of each event list (§M4.1's
    ``(world_tick, order_slot, agent_tick, seq)`` family — here ``tick``
    (+ ``sorted_pair``/``dialog_id``/``agent_id`` tie-breaks) and
    ``memory_id`` (already deterministic, ``ecl-{agent_id}-{tick:04d}``) — so
    a byte-identical re-run under the same (seed, recorded Plane 2) yields a
    byte-identical digest, independent of collection order.

    cross-review MEDIUM-B (loop/20260711-m13-m2-society-layer1-code/cross-
    review-synthesis.md): the per-agent Plane 2 ``decisions`` mapping is also
    now **explicitly** sorted here — by ``agent_id`` (the same total order
    ``order_slot = sorted(agent_ids).index(agent_id)`` derives from) for the
    outer mapping key, then by ``agent_tick`` for each agent's own decision
    list — rather than resting on the driver's append discipline (§M4.1's
    strictly-increasing sequential-tick loop already produces this exact
    order, so ``run_society_loop``'s caller-observed digest is unchanged) or
    on ``json.dumps(sort_keys=True)`` alone (which only sorts the dict's own
    keys, not each agent's decision *list*). This turns the full-order-key
    contract above into a function-internal guarantee, independent of any
    future caller's collection order.
    """
    _validate_self_other_slot(self_other_observation_input)
    geometry_checksum = ecl_trace_checksum(rows)

    sorted_pair_events = sorted(
        pair_events,
        key=lambda e: (e.tick, e.sorted_pair[0], e.sorted_pair[1], e.crossing),
    )
    sorted_dialog_events = sorted(
        dialog_events,
        key=lambda e: (e.tick, e.dialog_id, e.turn_index),
    )
    sorted_affinity_deltas = sorted(
        affinity_deltas,
        key=lambda e: (e.tick, e.agent_id, e.other_agent_id),
    )
    sorted_memory_mutations = sorted(memory_mutations, key=lambda e: e.memory_id)

    canonical: dict[str, Any] = {
        "schema_version": M2_EVENTLOG_SCHEMA_VERSION,
        "geometry_checksum": geometry_checksum,
        "pair_events": [_pair_event_projection(e) for e in sorted_pair_events],
        "dialog_events": [_dialog_event_projection(e) for e in sorted_dialog_events],
        "affinity_deltas": [
            _affinity_delta_projection(e) for e in sorted_affinity_deltas
        ],
        "memory_mutations": [
            _memory_mutation_projection(e) for e in sorted_memory_mutations
        ],
        "self_other_observation_input": self_other_observation_input,
        "decisions": {
            agent_id: [
                _decision_projection(d)
                for d in sorted(decs, key=lambda d: d.agent_tick)
            ]
            for agent_id, decs in sorted(decisions.items())
        },
    }
    blob = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _harvest_pair_events(
    world: WorldRuntime,
    agent_ids: Sequence[str],
) -> list[PairEventRecord]:
    """Peek (non-destructively) at pending ``ProximityEvent`` observations.

    Called once per cognition window, right after the physics-tick block and
    before the next window's ``inject_observation``/``step_cognition_once``
    drains ``rt.pending`` (``world/tick.py`` ``_step_one``, unmodified). Only
    reads (``for obs in ...pending``, no ``.clear()``/reassignment) so the
    existing drain-on-next-step contract is untouched.
    """
    harvested: list[PairEventRecord] = []
    for agent_id in agent_ids:
        pending = world._agents[agent_id].pending  # noqa: SLF001 — read-only peek (record-mode driver, mirrors world._on_physics_tick() call pattern)
        harvested.extend(
            PairEventRecord(
                tick=obs.tick,
                sorted_pair=(agent_id, obs.other_agent_id),
                distance_prev=obs.distance_prev,
                distance_now=obs.distance_now,
                crossing=obs.crossing,
            )
            for obs in pending
            if isinstance(obs, ProximityEvent) and agent_id < obs.other_agent_id
        )
    return harvested


def _collect_memory_mutations(
    store: MemoryStore,
    agent_ids: Sequence[str],
) -> tuple[MemoryMutationRecord, ...]:
    """Read committed ``episodic_memory`` rows for this run's agents (§M4.4).

    Read-only, canonical-key-sorted (``ORDER BY id ASC`` — the discovery-guard
    rule "DB/SQLite read は ORDER BY 必須", §M4.3, extended to this query). ECL
    record mode's memory ids are deterministic
    (``ecl-{agent_id}-{tick:04d}``, ``cognition/cycle.py``), so this ordering
    reproduces byte-identically across identical (seed, Plane 2) runs.
    Semantic/procedural/relational tables are not queried: reflection is
    disabled in this driver's ``EclRecordMode`` (``reflection_disabled=True``),
    so no rows are ever written there in Layer1 record mode.
    """
    if not agent_ids:
        return ()
    conn = store._ensure_conn()  # noqa: SLF001 — read-only, mirrors world._on_physics_tick() call pattern
    # placeholders is a fixed run of "?" chars keyed only by len(agent_ids) — no
    # external string is interpolated into the query; agent_ids' actual values
    # are bound via the parameterised tuple passed to conn.execute below.
    placeholders = ",".join("?" for _ in agent_ids)
    query = "SELECT id, agent_id, content, importance, created_at, tags "
    query += f"FROM episodic_memory WHERE agent_id IN ({placeholders}) ORDER BY id ASC"
    rows = conn.execute(query, tuple(agent_ids)).fetchall()
    return tuple(
        MemoryMutationRecord(
            memory_id=row["id"],
            agent_id=row["agent_id"],
            kind="episodic",
            content=row["content"],
            importance=row["importance"],
            created_at=row["created_at"],
            tags=tuple(json.loads(row["tags"])),
        )
        for row in rows
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
    """Geometry-only checksum (:func:`ecl_trace_checksum`), unchanged from I2."""
    cognition_step_order: tuple[str, ...]
    """The exact agent_id sequence :meth:`~WorldRuntime.step_cognition_once` was
    called in, one entry per (window, agent) step — the causal-wiring witness
    for the record-mode sequential sorted(order_slot) scheduler (§M4.1, I2-G2).
    This is provenance of *when the driver stepped whom*, not a measurement of
    emergent behaviour (§M1 over-read guard)."""
    pair_events: tuple[PairEventRecord, ...]
    """Canonical proximity-crossing events harvested during the run (§M4.4)."""
    memory_mutations: tuple[MemoryMutationRecord, ...]
    """Committed episodic-memory rows harvested after the run (§M4.4)."""
    dialog_events: tuple[DialogEventRecord, ...]
    """Dialog turns recorded during the run (§M4.4, wired in I4): a per-pair
    named-substream-seeded
    :class:`~erre_sandbox.integration.dialog.InMemoryDialogScheduler` plus a
    non-LLM :class:`_DeterministicDialogTurnGenerator` are attached to the
    driver's :class:`WorldRuntime`; whether this tuple is non-empty in a
    given run is scenario-dependent (co-location + the pair's RNG draw), an
    empty tuple is a legitimate scenario outcome, not a driver limitation."""
    affinity_deltas: tuple[AffinityDeltaRecord, ...]
    """Always empty in Layer1 (no affinity mutation wired, §M4.4). Versioned-
    additive slot for a later record-mode affinity driver."""
    self_other_observation_input: SelfOtherObservationInput
    """Always ``None`` in Layer1 (§M5.1). Layer2 seam slot."""
    event_log_checksum: str
    """SHA-256 over the versioned event/decision log as a whole (§M4.4) —
    :func:`event_log_checksum` applied to this result's own fields."""

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

    # §M4.2/DG-6 (I4): record-mode dialog channel. The scheduler's proximity
    # auto-fire draw is keyed by each co-located pair's own named RNG
    # substream (never the shared default); the generator is a non-LLM,
    # deterministic turn synthesiser (§M8 — no new LLM call). Both hooks
    # called below (``_run_dialog_tick`` / ``_drive_dialog_turns``) are
    # existing, unmodified ``WorldRuntime`` methods — no live phase-wheel
    # (``_on_cognition_tick``) due-time/dwell gating applies to either.
    dialog_events: list[DialogEventRecord] = []
    dialog_rng = _PairRngCache(run_id=run_id, stream="dialog")
    dialog_scheduler = InMemoryDialogScheduler(
        envelope_sink=world.inject_envelope,
        rng_for_pair=dialog_rng.get,
    )
    dialog_generator = _DeterministicDialogTurnGenerator(on_turn=dialog_events.append)
    world.attach_dialog_scheduler(dialog_scheduler)
    world.attach_dialog_generator(dialog_generator)

    obs_factories: dict[str, Callable[[int], Sequence[Observation]]] = dict(
        observation_factories
        if observation_factories is not None
        else {a: _default_observation_factory(a) for a in agent_ids}
    )

    decisions: dict[str, list[EclDecisionRecord]] = {a: [] for a in agent_ids}
    step_order: list[str] = []
    pair_events: list[PairEventRecord] = []
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
        # §M4.4: harvest this window's pair events before the NEXT window's
        # step_cognition_once drains rt.pending (world/tick.py _step_one).
        pair_events.extend(_harvest_pair_events(world, sorted_agent_ids))
        # §M4.2/DG-6 (I4): evaluate the dialog scheduler/generator once per
        # cognition window, after this window's post-physics zone state is
        # settled — the same two (unmodified) hooks the live phase-wheel's
        # ``_on_cognition_tick`` tail calls, invoked here sequentially by this
        # record-mode driver instead.
        world._run_dialog_tick()  # noqa: SLF001 — record-mode driver hook (unmodified WorldRuntime method)
        await world._drive_dialog_turns(  # noqa: SLF001 — record-mode driver hook (unmodified WorldRuntime method)
            world._current_world_tick()  # noqa: SLF001 — record-mode driver hook (unmodified WorldRuntime method)
        )

    frozen_rows = tuple(rows)
    frozen_decisions = {a: tuple(decs) for a, decs in decisions.items()}
    frozen_pair_events = tuple(pair_events)
    frozen_dialog_events = tuple(dialog_events)
    memory_mutations = _collect_memory_mutations(store, sorted_agent_ids)
    # §M5.1: Layer1 always passes None — the Layer2 seam slot is reserved but
    # never populated here (payload composition is Layer2 impl-design scope).
    self_other_observation_input: SelfOtherObservationInput = None
    return SocietyRunResult(
        run_id=run_id,
        rows=frozen_rows,
        decisions=frozen_decisions,
        checksum=ecl_trace_checksum(frozen_rows),
        cognition_step_order=tuple(step_order),
        pair_events=frozen_pair_events,
        memory_mutations=memory_mutations,
        dialog_events=frozen_dialog_events,
        affinity_deltas=(),
        self_other_observation_input=self_other_observation_input,
        event_log_checksum=event_log_checksum(
            rows=frozen_rows,
            decisions=frozen_decisions,
            pair_events=frozen_pair_events,
            dialog_events=frozen_dialog_events,
            affinity_deltas=(),
            memory_mutations=memory_mutations,
            self_other_observation_input=self_other_observation_input,
        ),
    )


__all__ = [
    "M2_EVENTLOG_SCHEMA_VERSION",
    "M2_SELFOTHER_SCHEMA_VERSION",
    "AffinityDeltaRecord",
    "DialogEventRecord",
    "MemoryMutationRecord",
    "PairEventRecord",
    "SelfOtherContext",
    "SelfOtherObservationInput",
    "SelfOtherObservedRecord",
    "SelfOtherPriorRecord",
    "SocietyRunResult",
    "build_self_other_context",
    "event_log_checksum",
    "run_society_loop",
]
