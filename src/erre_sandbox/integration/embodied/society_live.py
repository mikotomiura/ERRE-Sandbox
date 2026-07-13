"""M4 society run enrichment — society-scope live-capture harness (Issue 001).

Design-final.md (``.steering/20260712-m13-m4-society-enrichment/design-final.md``
§A/§F, FROZEN) mirror table 1:1: this module is the society-scope peer of
``integration/embodied/live.py``'s N=1 live-capture apparatus. Where ``live.py``
wraps one ``inner_chat`` and drives ``loop.run_ecl_loop``, this module wraps one
``inner_chat`` **per agent** and drives
:func:`~erre_sandbox.integration.embodied.society.run_society_loop` — **imported
and called, never modified** (it already accepts an
``llms: Mapping[str, RecordReplayChatClient]`` mapping, an ``agent_states``
sequence, a ``personas`` mapping and per-agent ``observation_factories``, so no
society-side change is needed to drive N agents).

Three pieces this module owns, mirroring ``live.py``'s three (none of which the
existing seam owns):

* :func:`run_society_live_capture` — dependency-injects one ``inner_chat`` per
  agent (real ``OllamaChatClient`` in Issue 004, a mock in this module's tests),
  wraps each in :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient`
  (imported **verbatim** from ``live.py`` — agent-count independent, forces
  ``think=False`` on every call regardless of what the caller passed) then in a
  record-mode :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`,
  and hands the resulting ``llms`` mapping plus every other argument to
  ``run_society_loop`` unmodified.
* :func:`build_society_live_env_pins` — the society-scope
  ``build_live_env_pins`` peer: qwen3 digest / Ollama version / VRAM / uv.lock
  hash / ``think:false`` / resolved sampling, **plus** (Codex HIGH-4/M2/M5) a
  canonical JSON fingerprint of the fixed agent_states/personas/
  observation_factory constructors this module defines below, so a ``--verify``
  caller (Issue 002) can assert the committed manifest's env_pins against a
  freshly-recomputed fingerprint and fail loudly on drift.
* :data:`SOCIETY_LIVE_OBSERVABLES` / :func:`attach_society_live_observables` —
  the society-scope observables overlay: drops ``live.py``'s single-agent
  O5 (memory-centroid) and adds two **annotation-only** boolean/count
  identifiers, ``O4_distinct_zones`` (trace-wide distinct-zone count) and
  ``O_multi_agent_speech`` (per-agent >=1 speech/animation), neither of which
  is a gate, divergence, or floor statistic (Codex HIGH-6, §L3: both live
  under manifest key ``"annotations"``, never ``verdict``/``passed``/
  ``score``/``floor``).

Scope guard (design-final.md §F, binding, verbatim-mirrors ``live.py``'s
docstring). This is a *construction* apparatus, **NOT a measurement
line — final judgement は holding**. It imports no ``evidence`` / ``spdm`` /
``runningness`` machinery and computes/emits no floor / landscape / final
judgement statistic. The observables this module pre-registers are
annotation text/count only; the actual per-tick counting (if ever computed)
is a non-gate boolean count, never a measurement-line statistic (§事前登録).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.society import SocietyRunResult, run_society_loop
from erre_sandbox.schemas import (
    AgentState,
    CognitiveHabit,
    HabitFlag,
    PerceptionEvent,
    PersonalityTraits,
    PersonaSpec,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import Observation

# --------------------------------------------------------------------------- #
# Pre-registered protocol constant (sealed-run-before fixed, §事前登録)
# --------------------------------------------------------------------------- #

SOCIETY_LIVE_N_COGNITION_TICKS: Final[int] = 12
"""Sealed society live-run horizon: 12 cognition ticks, longer than the 4-tick
synthetic ``m2_society_golden`` fixture (design-final.md §C) so the sealed run
gives real qwen3:8b more opportunity to genuinely choose a distinct
destination zone. Fixed before the sealed run (Issue 004); run-after tuning is
a Stop condition (§事前登録 tune-to-pass closure, decisions.md 判断1)."""

SOCIETY_LIVE_RUN_ID: Final[str] = "m4-society-live-golden"
"""Pinned ``run_id`` for the sealed society live-capture (§事前登録)."""

_SEALED_WALL_CLOCK: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed UTC timestamp for every ``wall_clock`` field this module's fixed
constructors emit (``AgentState.wall_clock`` / ``PerceptionEvent.wall_clock``,
both ``Field(default_factory=_utc_now)`` in ``schemas.py``). A sealed
reproducible run's fixed constructors must be fully deterministic in every
field: leaving ``wall_clock`` to ``now()`` makes
``fixed_constructor_fingerprint`` non-reproducible across processes (two
back-to-back constructions in the *same* interpreter already disagree at
microsecond resolution on Linux/WSL, and CI runs on Linux) — a byte-identical
sealed-run contract violation this module must not reintroduce. All agents
share this single fixed value (a *legitimate nudge* is zone distribution
only, §C — there is no reason for wall-clock to vary between agents or
across constructions)."""

# --------------------------------------------------------------------------- #
# Fixed agent_states/personas constructors (decisions.md 判断2, HIGH-4)
# --------------------------------------------------------------------------- #

KANT_AGENT_ID: Final[str] = "a_kant"
NIETZSCHE_AGENT_ID: Final[str] = "a_nietzsche"
RIKYU_AGENT_ID: Final[str] = "a_rikyu"

SOCIETY_LIVE_AGENT_IDS: Final[tuple[str, ...]] = (
    KANT_AGENT_ID,
    NIETZSCHE_AGENT_ID,
    RIKYU_AGENT_ID,
)
"""Already ``sorted()`` (``a_kant`` < ``a_nietzsche`` < ``a_rikyu``) so
``order_slot`` (``sorted(agent_ids).index(agent_id)``, ``society.py``) is
stably 0/1/2 for kant/nietzsche/rikyu respectively — human-readable by
construction, no extra sort needed at the call site."""

_SOCIETY_LIVE_INITIAL_ZONE: Final[dict[str, Zone]] = {
    KANT_AGENT_ID: Zone.STUDY,
    NIETZSCHE_AGENT_ID: Zone.PERIPATOS,
    RIKYU_AGENT_ID: Zone.CHASHITSU,
}
"""Initial zone per agent (design-final.md §C table): a *legitimate nudge*
(distributed starting positions), never a scripted destination — the LLM's
``plan.destination_zone`` (the sole driver of movement,
``cognition/cycle.py``) is never touched by this module."""


def _society_live_agent_state(agent_id: str) -> AgentState:
    """Return a fresh, byte-identical ``AgentState`` for ``agent_id``.

    Mirrors ``handoff.golden_agent_state``'s fixed-constructor idiom (decisions.md
    判断2): a Ollama-free replay must reconstruct the exact same starting state
    the capture run started from, so this is an import-time-constant-shaped
    helper, never a ``personas/*.yaml`` read.
    """
    zone = _SOCIETY_LIVE_INITIAL_ZONE[agent_id]
    persona_id = agent_id.removeprefix("a_")
    return AgentState.model_validate(
        {
            "agent_id": agent_id,
            "persona_id": persona_id,
            "tick": 0,
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "zone": zone.value},
            "erre": {"name": "deep_work", "entered_at_tick": 0},
            "wall_clock": _SEALED_WALL_CLOCK,
        }
    )


def society_live_agent_states() -> list[AgentState]:
    """The sealed run's fixed 3-agent roster, fresh each call (no aliasing)."""
    return [_society_live_agent_state(agent_id) for agent_id in SOCIETY_LIVE_AGENT_IDS]


def _kant_persona() -> PersonaSpec:
    return PersonaSpec.model_validate(
        {
            "persona_id": "kant",
            "display_name": "Immanuel Kant",
            "era": "1724-1804",
            "primary_corpus_refs": ["kuehn2001"],
            "personality": PersonalityTraits(
                conscientiousness=0.95,
                openness=0.85,
            ).model_dump(),
            "cognitive_habits": [
                CognitiveHabit(
                    description="15:30 daily walk",
                    source="kuehn2001",
                    flag=HabitFlag.FACT,
                    mechanism="DMN activation via rhythmic locomotion",
                    trigger_zone=Zone.PERIPATOS,
                ).model_dump(mode="json"),
            ],
            "preferred_zones": ["study", "peripatos"],
        }
    )


def _nietzsche_persona() -> PersonaSpec:
    return PersonaSpec.model_validate(
        {
            "persona_id": "nietzsche",
            "display_name": "Friedrich Nietzsche",
            "era": "1844-1900",
            "primary_corpus_refs": ["safranski2002"],
            "personality": PersonalityTraits(
                openness=0.9,
                extraversion=0.4,
                neuroticism=0.7,
            ).model_dump(),
            "cognitive_habits": [
                CognitiveHabit(
                    description="long solitary mountain walks while composing thought",
                    source="safranski2002",
                    flag=HabitFlag.FACT,
                    mechanism="DMN activation via rhythmic locomotion",
                    trigger_zone=Zone.PERIPATOS,
                ).model_dump(mode="json"),
            ],
            "preferred_zones": ["peripatos", "agora"],
        }
    )


def _rikyu_persona() -> PersonaSpec:
    return PersonaSpec.model_validate(
        {
            "persona_id": "rikyu",
            "display_name": "Sen no Rikyu",
            "era": "1522-1591",
            "primary_corpus_refs": ["kumakura2009"],
            "personality": PersonalityTraits(
                conscientiousness=0.9,
                wabi=0.95,
                ma_sense=0.9,
            ).model_dump(),
            "cognitive_habits": [
                CognitiveHabit(
                    description="deliberate, unhurried tea-ceremony gesture sequence",
                    source="kumakura2009",
                    flag=HabitFlag.FACT,
                    mechanism="ritualised motor sequencing lowers cognitive load",
                    trigger_zone=Zone.CHASHITSU,
                ).model_dump(mode="json"),
            ],
            "preferred_zones": ["chashitsu", "garden"],
        }
    )


_SOCIETY_LIVE_PERSONA_FACTORY: Final[dict[str, Callable[[], PersonaSpec]]] = {
    KANT_AGENT_ID: _kant_persona,
    NIETZSCHE_AGENT_ID: _nietzsche_persona,
    RIKYU_AGENT_ID: _rikyu_persona,
}


def society_live_personas() -> dict[str, PersonaSpec]:
    """The sealed run's fixed 3-persona roster, fresh each call (no aliasing)."""
    return {
        agent_id: factory()
        for agent_id, factory in _SOCIETY_LIVE_PERSONA_FACTORY.items()
    }


# --------------------------------------------------------------------------- #
# Per-agent observation factories (legitimate nudge, §C — never destination_zone)
# --------------------------------------------------------------------------- #


def society_live_observation_factory(
    agent_id: str,
) -> Callable[[int], Sequence[Observation]]:
    """One deterministic perception per tick, keyed by ``agent_id``'s own zone.

    Per-agent version of ``society._default_observation_factory`` (that name is
    module-private to ``society.py``, so this is a design-copy, not an import):
    each agent perceives *from its own initial zone*
    (:data:`_SOCIETY_LIVE_INITIAL_ZONE`) rather than the hardcoded
    ``Zone.STUDY`` every agent shared in ``society.py``'s single-zone default —
    a *legitimate nudge* (design-final.md §C item 2) that lets each agent's
    resolver genuinely read agent-specific located memory geometry. It never
    touches ``plan.destination_zone``, the sole LLM-authored driver of
    movement (``cognition/cycle.py``).
    """
    source_zone = _SOCIETY_LIVE_INITIAL_ZONE.get(agent_id, Zone.STUDY)

    def factory(agent_tick: int) -> Sequence[Observation]:
        return [
            PerceptionEvent(
                tick=agent_tick,
                agent_id=agent_id,
                modality="sight",
                source_zone=source_zone,
                content=f"m4 society live forage step {agent_tick}",
                intensity=0.4,
                wall_clock=_SEALED_WALL_CLOCK,
            )
        ]

    return factory


def society_live_observation_factories(
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
) -> dict[str, Callable[[int], Sequence[Observation]]]:
    """Build the fixed per-agent observation-factory mapping for ``agent_ids``."""
    return {
        agent_id: society_live_observation_factory(agent_id) for agent_id in agent_ids
    }


# --------------------------------------------------------------------------- #
# Live-capture harness (record mode only; replay reuses SocietyRunResult.replay_clients)
# --------------------------------------------------------------------------- #


async def run_society_live_capture(
    *,
    inner_chats: Mapping[str, Any],
    store: MemoryStore,
    embedding: EmbeddingClient,
    run_id: str,
    agent_states: Sequence[AgentState],
    personas: Mapping[str, PersonaSpec],
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factories: Mapping[str, Callable[[int], Sequence[Observation]]]
    | None = None,
    self_other_enabled: bool = False,
) -> SocietyRunResult:
    """Drive one record-mode society run through per-agent ``inner_chats``.

    Wraps each ``inner_chats[agent_id]`` in
    :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient` (forces
    ``think=False``, imported verbatim — agent-count independent) then in a
    record-mode
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`,
    building the ``llms`` mapping
    :func:`~erre_sandbox.integration.embodied.society.run_society_loop`
    (**unmodified**) expects, and hands every other argument straight through.
    ``store`` / ``embedding`` are dependency-injected so this function never
    constructs its own Ollama or sqlite-vec connection — a live caller
    (Issue 004) wires real ``OllamaChatClient`` instances; this module's tests
    wire a mock per agent.

    ``self_other_enabled`` (M2 Layer2 mirror-sim, additive, default ``False``)
    is passed straight through to ``run_society_loop`` unchanged — this module
    adds no wiring of its own, it only threads the caller's choice down to the
    already-landed Layer2 seam (society.py, unmodified by this issue).
    """
    llms: dict[str, RecordReplayChatClient] = {
        state.agent_id: RecordReplayChatClient(
            inner=ThinkOffChatClient(inner_chats[state.agent_id])
        )
        for state in agent_states
    }
    return await run_society_loop(
        run_id=run_id,
        store=store,
        embedding=embedding,
        llms=llms,
        agent_states=agent_states,
        personas=personas,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        k_ecl=k_ecl,
        reflector=reflector,
        observation_factories=observation_factories,
        self_other_enabled=self_other_enabled,
    )


# --------------------------------------------------------------------------- #
# Fixed-constructor canonical fingerprint (Codex HIGH-4/M2/M5)
# --------------------------------------------------------------------------- #


def _fingerprint_agent_states(agent_states: Sequence[AgentState]) -> str:
    """SHA-256 over the canonical JSON of ``agent_states`` (order-preserving)."""
    payload = [state.model_dump(mode="json") for state in agent_states]
    blob = handoff.canonical_dumps(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _fingerprint_personas(personas: Mapping[str, PersonaSpec]) -> str:
    """SHA-256 over the canonical JSON of ``personas`` (key-sorted)."""
    payload = {
        agent_id: persona.model_dump(mode="json")
        for agent_id, persona in personas.items()
    }
    blob = handoff.canonical_dumps(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _fingerprint_observation_factories(
    agent_ids: Sequence[str],
) -> str:
    """SHA-256 over each agent's factory name/version + its tick-0 observation.

    The factory *closure* itself is not JSON-serialisable, so the fingerprint
    covers what actually varies the run's behaviour: the factory's identity
    (module-qualified name), a version tag, and the canonical JSON of the
    first (``agent_tick=0``) observation it produces for each agent — the
    same shape :func:`society_live_observation_factory` will keep producing
    for any given ``agent_id`` since it is a pure function of ``agent_id``.
    """
    factories = society_live_observation_factories(agent_ids)
    payload = {
        agent_id: {
            "factory": (
                f"{society_live_observation_factory.__module__}."
                f"{society_live_observation_factory.__qualname__}"
            ),
            "factory_version": 1,
            "tick0_observation": [
                obs.model_dump(mode="json") for obs in factories[agent_id](0)
            ],
        }
        for agent_id in agent_ids
    }
    blob = handoff.canonical_dumps(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def fixed_constructor_fingerprint(
    *,
    agent_states: Sequence[AgentState],
    personas: Mapping[str, PersonaSpec],
    agent_ids: Sequence[str] | None = None,
) -> dict[str, str]:
    """Canonical JSON fingerprint of the fixed constructors (HIGH-4/M2).

    Returns a small dict of SHA-256 hex digests (agent_states / personas /
    observation_factories) that :func:`build_society_live_env_pins` pins into
    the manifest's ``env_pins`` block, so a ``--verify`` caller (Issue 002) can
    recompute the same fingerprint from its own fresh constructor call and
    assert it matches the committed value — a capture/verify constructor drift
    (which would otherwise silently break byte-parity, Codex HIGH-4) fails
    loudly instead.
    """
    ids = agent_ids if agent_ids is not None else [s.agent_id for s in agent_states]
    return {
        "agent_states_sha256": _fingerprint_agent_states(agent_states),
        "personas_sha256": _fingerprint_personas(personas),
        "observation_factories_sha256": _fingerprint_observation_factories(ids),
    }


# --------------------------------------------------------------------------- #
# Manifest env-pin overlay (handoff.py untouched, overlay lives here)
# --------------------------------------------------------------------------- #


def build_society_live_env_pins(
    *,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    resolved_sampling: ResolvedSampling,
    agent_states: Sequence[AgentState],
    personas: Mapping[str, PersonaSpec],
    model: str = "qwen3:8b",
    run_id: str = SOCIETY_LIVE_RUN_ID,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    seed: int = 0,
    base_env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the society live-capture env pins onto ``handoff.capture_env_pins()``.

    Society-scope peer of ``live.build_live_env_pins``: pins the model tag,
    qwen3 digest, Ollama version, VRAM, uv.lock hash, forced ``think=False``,
    and the cycle's live-resolved sampling verbatim — plus (Codex HIGH-4/M2/M5)
    the sealed ``run_id``/``seed``/``n_cognition_ticks`` and the fixed-
    constructor canonical fingerprint (:func:`fixed_constructor_fingerprint`)
    so a ``--verify`` caller can assert the committed manifest's env_pins
    against a freshly-recomputed fingerprint. ``base_env_pins`` defaults to a
    fresh :func:`~erre_sandbox.integration.embodied.handoff.capture_env_pins`
    snapshot so a caller can also pass a frozen snapshot for reproducible tests.
    """
    pins: dict[str, Any] = dict(
        base_env_pins if base_env_pins is not None else handoff.capture_env_pins()
    )
    pins["model"] = model
    pins["qwen3_model_digest"] = qwen3_model_digest
    pins["ollama_version"] = ollama_version
    pins["vram_gb"] = vram_gb
    pins["uv_lock_sha256"] = uv_lock_sha256
    pins["think"] = False
    pins["resolved_sampling"] = resolved_sampling.model_dump(mode="json")
    pins["run_id"] = run_id
    pins["seed"] = seed
    pins["n_cognition_ticks"] = n_cognition_ticks
    pins["fixed_constructor_fingerprint"] = fixed_constructor_fingerprint(
        agent_states=agent_states, personas=personas
    )
    return pins


def apply_self_other_env_pin(
    env_pins: dict[str, Any], *, self_other_enabled: bool
) -> None:
    """Persist the M2 Layer2 self-other witness into ``env_pins`` (in place).

    Single seam (Codex MEDIUM, code-review) for the *write only when True*
    discipline shared by ``scripts/m4_society_live_capture.py``'s ``capture()``
    (live-Ollama path, CI-unreached) and its Ollama-free mock-bundle test
    renderer: when ``self_other_enabled`` is ``True`` the key
    ``"self_other_enabled"`` is set to ``True``; when ``False`` **any existing
    key is removed** so no ``self_other_enabled`` key survives — the existing M4
    Layer2-off golden's ``env_pins`` block (which never had the key) and
    therefore its byte-identity is untouched, and a re-used / stale dict cannot
    leave a lingering ``true``/``false`` that would weaken the *absence ==
    Layer2-off* invariant (Codex MEDIUM, cross-review). ``--verify`` auto-detects
    Layer2-on from this key's presence. This is a pure ``dict`` mutation
    helper, not a schema change to ``handoff.py``.
    """
    if self_other_enabled:
        env_pins["self_other_enabled"] = True
    else:
        env_pins.pop("self_other_enabled", None)


# --------------------------------------------------------------------------- #
# Observables overlay (annotation-only, never a gate — Codex HIGH-6/§L3)
# --------------------------------------------------------------------------- #

SOCIETY_LIVE_OBSERVABLES: Final[dict[str, Any]] = {
    "O1": (
        "N cognition ticks x M physics ticks completed for every agent against "
        "a live Ollama qwen3:8b with no exception (full completion)"
    ),
    "O2": (
        "replaying from the captured per-agent decisions alone reproduces a "
        "byte-identical replay_checksum/event_log_checksum with every "
        "replay client's inner_invocations==0"
    ),
    "O3a": (
        "the same committed decisions.jsonl replays to the same checksum "
        "with every replay client's inner_invocations==0 on both WSL Linux "
        "(glibc) and Windows (UCRT)"
    ),
    "O3b": (
        "the same raw Plane 2 re-renders the full artifact set to the same "
        "SHA-256 set on both platforms (6-decimal float quantisation absorbs "
        "libm drift)"
    ),
    "O4_distinct_zones": (
        "non-degeneracy: a pure count annotation (never a divergence/floor "
        "statistic) of how many distinct zones appear across the trace's "
        "agent+zone occupancy, whole-run — not a Done gate"
    ),
    "O_multi_agent_speech": (
        "a pure boolean-per-agent count annotation (never a divergence/floor "
        "statistic) of whether each agent produced at least one "
        "speech/animation stream entry in the envelope_stream — not a Done gate"
    ),
    "done_formula": "O1∧O2∧O3a∧O3b",
    "o5_min_ticks": None,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass
closure, mirrors ``live.LIVE_OBSERVABLES``): frozen at import time (not
derived from any run outcome), so a sealed run cannot retroactively redefine
what it is judged against. ``O4_distinct_zones``/``O_multi_agent_speech`` are
**annotation** identifiers only — count/boolean text, never a gate/verdict/
score/floor key (Codex HIGH-6, §L3)."""


def build_society_live_manifest_overlay() -> dict[str, Any]:
    """Return the sealed-run-before ``annotations`` overlay block (a fresh copy).

    §L3: the key is ``annotations`` (not ``observables``, unlike ``live.py``'s
    single-agent overlay) so the manifest never carries a
    ``verdict``/``passed``/``score``/``floor`` key at any nesting level.
    """
    return dict(SOCIETY_LIVE_OBSERVABLES)


def attach_society_live_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the ``annotations`` overlay attached (non-mutating).

    ``handoff.build_manifest``/``render_society_golden`` (untouched) have no
    ``annotations`` field; this function is the live-capture-side seam that
    adds it on top of the dict those functions return, so ``handoff.py`` never
    needs to know about the society live-capture pre-registration.
    """
    overlaid = dict(manifest)
    overlaid["annotations"] = build_society_live_manifest_overlay()
    return overlaid


__all__ = [
    "KANT_AGENT_ID",
    "NIETZSCHE_AGENT_ID",
    "RIKYU_AGENT_ID",
    "SOCIETY_LIVE_AGENT_IDS",
    "SOCIETY_LIVE_N_COGNITION_TICKS",
    "SOCIETY_LIVE_OBSERVABLES",
    "SOCIETY_LIVE_RUN_ID",
    "apply_self_other_env_pin",
    "attach_society_live_observables",
    "build_society_live_env_pins",
    "build_society_live_manifest_overlay",
    "fixed_constructor_fingerprint",
    "run_society_live_capture",
    "society_live_agent_states",
    "society_live_observation_factories",
    "society_live_observation_factory",
    "society_live_personas",
]
