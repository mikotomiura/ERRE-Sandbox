"""M13 aha-substrate-embodiment traversal harness — Issue 001 (construction).

FROZEN ADR ``.steering/20260723-m13-aha-substrate-embodiment/design-final.md``
(Plan + ``/reimagine`` + Codex independent review, Verdict=Adopt-with-changes).
This is the **construction entry** for the situated-3D-substrate milestone: a
**deterministic traversal harness** that walks a single agent through a
frozen 5-leg itinerary — ``peripatos -> agora -> garden -> chashitsu -> study
-> peripatos`` (5 distinct zones / 5 cross-zone legs / 6 waypoint visits) —
so ``erre.locomotion_sampling.advance_lambda`` earns λ>0 from genuine
world-driven zone crossings rather than a seeded λ₀ (the Phase 4b limitation,
``two_phase_live.py``'s module docstring).

**organ 無改変 (Option A, binding)**: this module imports and drives
``two_phase_live.run_two_phase_capture`` — itself a sibling reconstruction of
``loop.run_ecl_loop`` that never touches ``loop.py`` / ``cycle.py`` /
``handoff.py`` / ``two_phase.py`` / ``embodiment.py`` / ``contracts/geometry.py``
— so this harness adds a **scripted-traversal chat client** + a waypoint
``observation_factory`` + a traversal-seeded ``AgentState`` on top of the
existing sibling driver. Nothing new is copied from the organ; only the
plan-source (chat client) and the seed/obs factories are new.

**Scope guard (design-final.md §Guard, binding, mirrors ``two_phase_live.py``).**
This is a *construction* apparatus, **NOT a measurement line — verdict は
holding**. It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery
and computes/emits **no** floor / landscape / verdict / divergence / magnitude
/ detectability / aha-proxy statistic. The only observable this module
produces is the exact-match physical **visit sequence** (:func:`extract_visit_sequence`)
against the frozen :data:`TRAVERSAL_EXPECTED_ROUTE` — a boolean/exact-match
witness (W1), never a threshold or effect size.

**Scripted planner, not emergent traversal (Codex HIGH-2, design-final.md
§採用アプローチ)**: :class:`ScriptedTraversalChatClient` does not represent an
LLM "genuinely deciding" to walk the itinerary — it is an Ollama-free scripted
responder that *consumes* the waypoint observation
:func:`traversal_observation_factory` injects each cognition tick (parsing the
``"proceed to <zone>"`` marker out of the rendered user prompt) and echoes the
matching ``destination_zone`` back as an ``LLMPlan``. This is explicitly a
*scripted-planner* traversal — organ non-modification is bought by routing the
itinerary through the same "world stimulus" channel (``inject_observation``)
a live LLM would read, never by hand-injecting ``destination_zone`` directly.
"Agent autonomously walks the itinerary" (emergent traversal) is out of scope
here and deferred (design-final.md §採用アプローチ, "別 ADR/別 spend").

Calibration finding (Issue 001 pre-registration, read-only, tune-to-pass
closed — the run itself was ephemeral and its log discarded, only the
following constants survive into this module). **Two distinct thresholds**
were calibrated along the same straight-line walk and must not be conflated
(post-review reconciliation note — an earlier draft of this docstring
conflated them):

* **Zone arrival** — the containing zone at the end of a cognition tick's
  physics window equals that leg's destination (the ``extract_visit_sequence``
  W1 route witness this module actually checks) — is the *looser* threshold.
  The frozen itinerary's five legs (``ZONE_CENTERS`` in
  ``contracts/geometry.py``, ``WORLD_SIZE_M=100``) span up to ~66.7 m
  (``garden<->chashitsu`` / ``chashitsu<->study``, the two legs whose centroids
  sit on opposite sides of the 100 m plane). At the golden persona's default
  walking speed (``CognitionCycle.DEFAULT_DESTINATION_SPEED=1.3`` m/s ×
  ``movement_speed_factor``) and 30 Hz physics, zone arrival for every leg —
  including that worst case — is reached well under 1000 physics ticks per
  cognition: empirically, 500 under-shoots (the agent has not yet crossed the
  destination zone's Voronoi boundary — the value
  ``test_traversal_undershoot_fails_route`` pins as a known-insufficient
  regression), while 1000 already reaches every leg's *zone*.
* **Full position-snap / trace byte-stability** — the agent's kinematics fully
  converges onto the *exact* resolved ECL target coordinate, so further
  physics ticks in the same cognition window become no-ops per
  ``world.physics.step_kinematics``'s ``dest is None`` early return and a
  re-run's raw 30 Hz trace stops changing — is the *stricter* threshold and a
  genuinely later milestone on the same walk: the agent crosses into the
  destination zone well before it converges on the exact interior point
  ``resolve_destination`` computed. Calibrated empirically at
  ``physics_ticks_per_cognition >= 1500`` (1000 has already reached the zone
  but has not yet fully snapped onto the target coordinate; 1500/2000/3000
  are byte-identical — confirmed snapped, further ticks no-op).
* :data:`TRAVERSAL_PHYSICS_TICKS_PER_COGNITION` pins **2000**, calibrated
  against the **stricter full-snap/byte-stability threshold** (1500's
  confirmed-sufficient minimum plus headroom) — *not* the looser zone-arrival
  one, which alone would tolerate a smaller value. The determinism discipline
  this module shares with ``two_phase_live.py`` (W4: a re-run's raw trace must
  not still be mid-flight, byte-stable for cross-platform replay) is the
  binding requirement, so the larger, stricter threshold is the honest pin —
  not a tuned-to-pass minimum against either threshold.
* With that pinned value, exactly one cognition tick fully completes one leg
  by **both** measures (zone arrival and full snap), so
  :data:`TRAVERSAL_HORIZON` **= 5** (one tick per leg, matching the itinerary
  length) — never re-derived from run-time success/failure.
* **Route-extraction source (why NOT the raw 30 Hz physics trace)**: the
  ``garden->chashitsu`` and ``chashitsu->study`` legs' straight-line paths
  pass close to the ``peripatos``/``garden``/``chashitsu`` (resp.
  ``peripatos``/``chashitsu``/``study``) Voronoi vertex (see
  ``contracts/geometry.ZONE_CENTERS`` — those three centroids are
  equidistant from a point on the straight line), so the *continuous*
  30 Hz ``EclTraceRow.zone`` trace transiently dips back into
  ``peripatos`` mid-leg before reaching the true destination. This is a
  geometric fact about the frozen world layout, not an insufficient-horizon
  failure — the two-crossings artefact is confirmed present at every
  ``physics_ticks_per_cognition`` tried. :func:`extract_visit_sequence`
  therefore samples the **end-of-cognition-tick** physical zone (the last
  physics row of each ``agent_tick`` window) rather than every physics row:
  a genuine embodiment witness against the **zone-arrival** threshold above
  (it fails if the physics simulation never actually crosses into the
  destination zone — see the 500-tick undershoot regression,
  ``test_traversal_undershoot_fails_route``) that is immune to the transient
  mid-leg Voronoi-vertex clip, which is a real but orthogonal continuous-path
  detail out of W1's exact-match scope.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from itertools import accumulate, pairwise
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from erre_sandbox.erre.locomotion_sampling import DEFAULT_LOCO_ALPHA, advance_lambda
from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.two_phase_live import (
    run_two_phase_capture,
    two_phase_firing_summary,
)
from erre_sandbox.schemas import (
    ERREMode,
    ERREModeName,
    LocomotionState,
    PerceptionEvent,
    Position,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime

    from erre_sandbox.inference.ollama_adapter import ChatMessage
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import (
        EclRunResult,
        RecordedLlmCall,
    )
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec

# --------------------------------------------------------------------------- #
# Frozen itinerary (design-final.md §採用アプローチ / §itinerary 表記, binding)
# --------------------------------------------------------------------------- #

TRAVERSAL_START_ZONE: Final[Zone] = Zone.PERIPATOS
"""The itinerary's origin/return zone (ADR: golden ``study`` seed overridden)."""

TRAVERSAL_ITINERARY: Final[tuple[Zone, ...]] = (
    Zone.AGORA,
    Zone.GARDEN,
    Zone.CHASHITSU,
    Zone.STUDY,
    Zone.PERIPATOS,
)
"""The 5 scripted ``destination_zone`` values, one per cognition tick (5 legs).

Frozen shape (ADR, tune-to-pass closed): ``peripatos -> agora -> garden ->
chashitsu -> study -> peripatos`` = 5 distinct zones / 5 cross-zone legs / 6
waypoint visits (peripatos revisited). This tuple is the itinerary *after*
:data:`TRAVERSAL_START_ZONE` — prepend the start to get the full 6-waypoint
visit sequence (:data:`TRAVERSAL_EXPECTED_ROUTE`).
"""

TRAVERSAL_EXPECTED_ROUTE: Final[tuple[Zone, ...]] = (
    TRAVERSAL_START_ZONE,
    *TRAVERSAL_ITINERARY,
)
"""The frozen 6-waypoint visit sequence — the W1 replay-fidelity witness value."""

TRAVERSAL_HORIZON: Final[int] = 5
"""Cognition ticks driven — one per leg (calibration finding, module docstring).

Never re-derived from a run's success/failure (tune-to-pass closed): fixed at
the itinerary's leg count because :data:`TRAVERSAL_PHYSICS_TICKS_PER_COGNITION`
was calibrated so one cognition tick's physics window always fully completes
one leg."""

TRAVERSAL_PHYSICS_TICKS_PER_COGNITION: Final[int] = 2000
"""Physics ticks (30 Hz) driven per cognition tick (calibration finding, module
docstring): empirically confirmed sufficient (1500) plus headroom for every
leg — including the ~66.7 m ``garden<->chashitsu`` / ``chashitsu<->study``
worst case — to fully snap onto the resolved ECL destination target within a
single cognition tick's physics window. Distinct from
``two_phase_live.py``'s / ``loop.py``'s ``DEFAULT_PHYSICS_TICKS_PER_COGNITION``
(=20, tuned for the ES-3 continuous-transit demonstration, not full-leg
arrival) — this harness's traversal semantics need genuine per-leg arrival,
so it pins its own, larger value."""


class TraversalScriptError(RuntimeError):
    """The scripted traversal plan-source could not serve the expected leg.

    Raised when the injected waypoint marker is missing/unparseable, or the
    observed waypoint disagrees with the frozen :data:`TRAVERSAL_ITINERARY`
    at that call index (drift guard — a scripted client silently diverging
    from the frozen itinerary would defeat the W1 exact-match witness).
    """


# --------------------------------------------------------------------------- #
# Seed factory — arm locomotion at the itinerary's origin zone
# --------------------------------------------------------------------------- #


def traversal_seed_agent_state() -> AgentState:
    """The golden agent, relocated to :data:`TRAVERSAL_START_ZONE`, loco armed.

    ``handoff.golden_agent_state()`` seeds at ``study`` (``x=0, y=0, z=0``,
    tagged ``zone="study"``); the traversal itinerary starts at ``peripatos``,
    whose centroid is *also* ``(0, 0, 0)`` (``contracts.geometry.ZONE_CENTERS``)
    — so only the ``zone`` tag changes, the coordinate stays geometrically
    consistent (``locate_zone(0, 0, 0) is Zone.PERIPATOS``). ``locomotion`` is
    armed at ``lam=0.0`` (honest rest, never a fabricated non-zero seed — the
    ``two_phase_live.TWO_PHASE_LOCO_LAM0`` idiom) so a later issue (I2) can
    reuse this seed to read the λ the itinerary's zone crossings earn. Every
    other field is byte-identical to the golden.
    """
    return handoff.golden_agent_state().model_copy(
        update={
            "position": Position(x=0.0, y=0.0, z=0.0, zone=TRAVERSAL_START_ZONE),
            "locomotion": LocomotionState(lam=0.0),
        },
    )


# --------------------------------------------------------------------------- #
# Waypoint observation injection — the "world stimulus" channel (design-final)
# --------------------------------------------------------------------------- #

_WAYPOINT_TEMPLATE: Final[str] = "traversal waypoint {tick}: proceed to {zone}"


def traversal_observation_factory(
    agent_id: str,
    *,
    itinerary: Sequence[Zone] = TRAVERSAL_ITINERARY,
) -> Callable[[int], Sequence[Observation]]:
    """One waypoint :class:`PerceptionEvent` per cognition tick (per leg).

    Mirrors ``loop._default_observation_factory``'s shape (one deterministic
    perception per tick), but the content carries a machine-parseable
    ``"proceed to <zone>"`` marker that :class:`ScriptedTraversalChatClient`
    parses out of the rendered user prompt (``cognition.prompting`` embeds
    ``obs.content`` verbatim as ``[perception] {content} (...)``) — the
    "scripted planner consumes waypoint observations" wiring (design-final.md
    §採用アプローチ). Ticks past the itinerary's length inject nothing (a
    caller driving past :data:`TRAVERSAL_HORIZON` gets no further waypoints,
    matching :class:`ScriptedTraversalChatClient`'s refusal to serve past the
    frozen itinerary).
    """

    def factory(agent_tick: int) -> Sequence[Observation]:
        if agent_tick >= len(itinerary):
            return []
        dest = itinerary[agent_tick]
        return [
            PerceptionEvent(
                tick=agent_tick,
                agent_id=agent_id,
                modality="sight",
                # ``source_zone`` is the schema's required "where did this
                # signal originate" tag (LOW-2 review note) — it is never the
                # movement *destination*, and this harness's route/leg logic
                # never reads it (inert field for W1). Pinned to the fixed
                # itinerary anchor rather than ``dest`` (which would read as
                # "the stimulus emanates from where the agent is headed",
                # backwards), mirroring ``loop._default_observation_factory``'s
                # convention of a fixed environmental ``source_zone``.
                source_zone=TRAVERSAL_START_ZONE,
                content=_WAYPOINT_TEMPLATE.format(tick=agent_tick, zone=dest.value),
                intensity=0.4,
            )
        ]

    return factory


# --------------------------------------------------------------------------- #
# Scripted-traversal chat client — Ollama-free plan source (organ 無改変)
# --------------------------------------------------------------------------- #

_WAYPOINT_RE: Final[re.Pattern[str]] = re.compile(r"proceed to (\w+)")
"""Matches the FIRST ``"proceed to <zone>"`` occurrence in the user prompt.

LOW-1 (review note): taking the first match is safe under two preconditions
this harness relies on but does not itself enforce:

1. ``world.tick.WorldRuntime._step_one`` drains ``rt.pending`` before every
   cognition step (``obs = rt.pending; rt.pending = []``), so a *previous*
   tick's injected :class:`~erre_sandbox.schemas.PerceptionEvent` never
   lingers into a *later* tick's ``observations`` list — each cognition tick
   sees exactly the one waypoint marker :func:`traversal_observation_factory`
   injected for it, never a stale one.
2. ``cognition.prompting.build_user_prompt`` renders the ``"Recent
   observations:"`` block *before* ``"Relevant memories:"`` — so even though
   this harness's own written episodic memories carry the identical
   ``"proceed to <zone>"`` text (:func:`~erre_sandbox.cognition.cycle.\
CognitionCycle._write_observations` stores ``obs.content`` verbatim), a
   retrieved *stale* memory from an earlier leg can only appear **after** the
   current tick's genuine marker in the rendered prompt, never before it.

If either precondition ever changes, :class:`ScriptedTraversalChatClient`
fails **closed**: a missing/unrecognised marker or an itinerary-order
mismatch raises :class:`TraversalScriptError` rather than silently walking
the wrong leg (see :meth:`ScriptedTraversalChatClient.chat` below) — that
fail-closed check is the backstop this precondition note does not replace.
"""


class ScriptedTraversalChatClient:
    """Ollama-free chat client that echoes the injected waypoint marker back.

    Duck-typed to the same ``chat`` keyword surface
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient.chat`
    exposes (matching :class:`~erre_sandbox.integration.embodied.live.\
ThinkOffChatClient` / :class:`~erre_sandbox.integration.embodied.loop.\
RecordReplayChatClient`'s ``inner`` contract), so it stands in for a live LLM
    without the organ importing this module.

    Each call parses the ``"proceed to <zone>"`` marker
    :func:`traversal_observation_factory` injected into the rendered user
    prompt (this is the "consumes waypoint observations" wiring, not a blind
    call-count index — design-final.md §採用アプローチ / Codex HIGH-2) and
    returns an ``LLMPlan``-shaped JSON response with that zone as
    ``destination_zone``. Raises :class:`TraversalScriptError` if the marker
    is missing/unparseable or disagrees with the frozen
    :data:`TRAVERSAL_ITINERARY` at that call index — a scripted-client
    integrity guard, not a construction-validity gate.
    """

    def __init__(self, *, itinerary: Sequence[Zone] = TRAVERSAL_ITINERARY) -> None:
        self._itinerary = tuple(itinerary)
        self._calls = 0

    @property
    def calls_served(self) -> int:
        """How many ``chat`` calls this client has served, in order."""
        return self._calls

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        del sampling, model, options, think  # scripted response ignores these
        user_prompt = next((m.content for m in messages if m.role == "user"), "")
        match = _WAYPOINT_RE.search(user_prompt)
        if match is None:
            msg = (
                "ScriptedTraversalChatClient: no 'proceed to <zone>' waypoint "
                "marker found in the rendered user prompt — "
                "traversal_observation_factory must inject the waypoint "
                "observation ahead of this cognition tick's chat call"
            )
            raise TraversalScriptError(msg)
        token = match.group(1)
        try:
            dest = Zone(token)
        except ValueError as exc:
            msg = f"ScriptedTraversalChatClient: unrecognised zone token {token!r}"
            raise TraversalScriptError(msg) from exc
        call_index = self._calls
        self._calls += 1
        if call_index >= len(self._itinerary):
            msg = (
                f"ScriptedTraversalChatClient: call {call_index} exceeds the "
                f"frozen itinerary length {len(self._itinerary)}"
            )
            raise TraversalScriptError(msg)
        expected = self._itinerary[call_index]
        if dest is not expected:
            msg = (
                f"ScriptedTraversalChatClient: tick {call_index} observed "
                f"waypoint {dest.value!r} but the frozen itinerary expects "
                f"{expected.value!r}"
            )
            raise TraversalScriptError(msg)
        content = json.dumps(
            {
                "thought": f"proceed to {dest.value}",
                "utterance": None,
                "destination_zone": dest.value,
                "animation": "walk",
            }
        )
        return ChatResponse(
            content=content,
            model="scripted-traversal",
            eval_count=0,
            prompt_eval_count=0,
            total_duration_ms=0.0,
        )


# --------------------------------------------------------------------------- #
# Driver — reuse two_phase_live.run_two_phase_capture verbatim (Option A)
# --------------------------------------------------------------------------- #


async def run_traversal_capture(
    *,
    run_id: str,
    store: MemoryStore,
    embedding: EmbeddingClient,
    retrieval_now: datetime,
    base_ts: datetime,
    agent_state: AgentState | None = None,
    persona: PersonaSpec | None = None,
    two_phase_knob: TwoPhaseKnob | None = None,
    seed: int = 0,
    n_cognition_ticks: int = TRAVERSAL_HORIZON,
    physics_ticks_per_cognition: int = TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
    inner_chat: Any | None = None,
) -> EclRunResult:
    """Drive the frozen itinerary through the untouched sibling driver.

    Wraps ``inner_chat`` (or, when omitted, a fresh
    :class:`ScriptedTraversalChatClient`) in the organ's own
    :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient`
    (``think=False``) then
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`
    (record mode), and hands everything to
    :func:`~erre_sandbox.integration.embodied.two_phase_live.\
run_two_phase_capture` **unmodified** — this function adds no organ copy of
    its own, only the plan-source + seed + observation-factory glue.
    ``two_phase_knob`` defaults to ``None`` (W3 knob algebra is I2 scope; I1
    only establishes the route with the knob off, per the ADR's
    ``knob=None ≡ run_ecl_loop`` fidelity discipline).

    ``inner_chat`` (I4, real-client injection point, minimal extension):
    ``None`` (every I1-I3 caller) reproduces the exact prior behaviour
    byte-for-byte — a fresh :class:`ScriptedTraversalChatClient` is built
    internally, unchanged. Supplying a duck-typed chat client instead (e.g. a
    real :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient`)
    lets a caller drive the **same** traversal seed / waypoint
    ``observation_factory`` / sibling-driver plumbing with a genuinely
    unscripted plan source — the I4 channel-exercise mode. **Honesty note
    (LOW-2 review)**: ``observation_factory`` is unconditionally
    :func:`traversal_observation_factory` regardless of ``inner_chat`` — a
    real backend receives the SAME pre-registered "proceed to ``<zone>``"
    waypoint stimulus a scripted run does. What is unscripted is the
    backend's *response* to that stimulus (whether it complies, ignores it,
    speaks instead, etc.), never the waypoint target itself — so "emergent
    traversal" would overclaim; "unscripted response to a pre-registered
    stimulus" is the accurate framing. This function performs **no** network
    I/O itself either way; whether ``inner_chat`` ever actually calls out is
    entirely the caller's choice.
    """
    state = agent_state if agent_state is not None else traversal_seed_agent_state()
    pn = persona if persona is not None else handoff.golden_persona()
    chat_source = (
        inner_chat if inner_chat is not None else ScriptedTraversalChatClient()
    )
    llm = RecordReplayChatClient(inner=ThinkOffChatClient(chat_source))
    return await run_two_phase_capture(
        run_id=run_id,
        store=store,
        embedding=embedding,
        llm=llm,
        agent_state=state,
        persona=pn,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        two_phase_knob=two_phase_knob,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        observation_factory=traversal_observation_factory(state.agent_id),
    )


# --------------------------------------------------------------------------- #
# Route extraction — the W1 exact-match witness (boolean/exact only)
# --------------------------------------------------------------------------- #


def extract_visit_sequence(
    result: EclRunResult,
    *,
    start_zone: Zone = TRAVERSAL_START_ZONE,
) -> tuple[Zone, ...]:
    """The per-cognition-tick physical zone-visit sequence (module docstring).

    Samples the **last** physics row of each ``agent_tick`` window (the zone
    the agent's simulated kinematics actually settled in by the end of that
    cognition tick), prefixed by ``start_zone`` — never the raw 30 Hz
    continuous trace (module docstring: the ``garden<->chashitsu`` /
    ``chashitsu<->study`` legs' straight-line paths transiently clip a third
    zone's Voronoi cell near a triple-point, an orthogonal geometric detail
    the per-tick sampling is immune to). ``result.rows`` are already
    tick-ordered (``two_phase_live.run_two_phase_capture`` appends them in
    strictly increasing ``(agent_tick, physics_tick_index)`` order), so a
    single dict-overwrite pass keeps only the last row per tick.

    LOW-4 (review note): a cognition tick with **zero** physics rows (e.g. a
    misconfigured ``physics_ticks_per_cognition=0``, or a driver bug that
    skips a window) must never be silently dropped from the sequence — that
    would collapse a missing leg into an unremarkable shorter tuple instead of
    failing loudly. This function therefore requires every ``agent_tick`` in
    ``0 .. max(observed ticks)`` to have contributed at least one row and
    raises :class:`TraversalScriptError` naming the gap otherwise.
    """
    end_of_tick: dict[int, Zone] = {}
    for row in result.rows:
        end_of_tick[row.agent_tick] = row.zone
    if not end_of_tick:
        return (start_zone,)
    expected_ticks = range(max(end_of_tick) + 1)
    missing = [tick for tick in expected_ticks if tick not in end_of_tick]
    if missing:
        msg = (
            f"extract_visit_sequence: agent_tick(s) {missing} have zero "
            "physics rows in result.rows — a silently dropped leg would "
            "defeat the W1 exact-match witness. Check that "
            "physics_ticks_per_cognition > 0 and the driver's physics loop "
            "ran for every cognition tick."
        )
        raise TraversalScriptError(msg)
    return (start_zone, *(end_of_tick[tick] for tick in expected_ticks))


# --------------------------------------------------------------------------- #
# W2 — λ update-path (Issue 002, pure fold, tune-to-pass closed)
# --------------------------------------------------------------------------- #
#
# ``cognition.cycle.CognitionCycle._advance_locomotion`` (read-only, organ
# unchanged) updates λ via ``move_t = int(destination_zone is not None and
# destination_zone != current_zone)`` then ``advance_lambda(prev_lam, move_t,
# α)``. ``current_zone`` is ``agent_state.position.zone`` — the physical zone
# entering that cognition tick — so ``move_t`` at tick ``i`` is a pure
# function of :data:`TRAVERSAL_EXPECTED_ROUTE` (the physical zone entering
# tick ``i``) and :data:`TRAVERSAL_ITINERARY` (the destination requested at
# tick ``i``), computable without running anything. These are therefore
# **derived Final constants** — never re-derived from a run's success/failure
# (tune-to-pass closed) — that a run merely *confirms* (see
# ``test_traversal_lambda_update_path``'s spy cross-check).
#
# **Scope note (M-1 review, over-read guard, binding)**: W2 witnesses the
# λ→sampling **wiring** (which tick's *sampling call* sees λ>0) and the
# **tick-timing** of that wiring (tick 0 never fires, tick 1 is the earliest
# possible fire — the one-tick lag between a move and its λ becoming visible
# to sampling). It does **not** witness physical arrival — whether the agent's
# *kinematics* actually reached the destination zone is W1's job
# (:func:`extract_visit_sequence` + ``test_traversal_undershoot_fails_route``,
# which fails at an insufficient ``physics_ticks_per_cognition`` where W2's
# move_t/λ constants would be unchanged since they never read a physics row).
# Do not read a green W2 test as "the agent walked there" — only "the plan
# requested a move, and λ's sampling-visibility timing matches the fold".

TRAVERSAL_EXPECTED_MOVE_TICKS: Final[tuple[int, ...]] = tuple(
    i
    for i in range(len(TRAVERSAL_ITINERARY))
    if TRAVERSAL_ITINERARY[i] != TRAVERSAL_EXPECTED_ROUTE[i]
)
"""Tick indices where ``move_t=1`` for that tick's own plan decision (W2).

By the itinerary's frozen design (I1's pairwise-distinct consecutive-zone
check on :data:`TRAVERSAL_EXPECTED_ROUTE`), the destination requested at
every tick always differs from the zone the agent is physically in entering
that tick — so this evaluates to all 5 tick indices. Derived from the frozen
route/itinerary constants above, not hardcoded twice."""

TRAVERSAL_EXPECTED_INCOMING_LAMBDA: Final[tuple[float, ...]] = tuple(
    accumulate(
        (
            1 if i in TRAVERSAL_EXPECTED_MOVE_TICKS else 0
            for i in range(len(TRAVERSAL_ITINERARY) - 1)
        ),
        lambda lam, move_t: advance_lambda(lam, move_t, DEFAULT_LOCO_ALPHA),
        initial=0.0,
    )
)
"""The λ each cognition tick's **sampling call** actually reads (W2, pure fold).

``CognitionCycle._locomotion_delta_for`` (organ, read-only) reads
``agent_state.locomotion`` — the state **entering** the tick, before that
tick's own move updates it (``_advance_locomotion`` writes the new λ into
``new_state``, only visible to the *next* tick). So tick 0's sampling call
uses the traversal seed's ``lam=0.0`` (:func:`traversal_seed_agent_state`),
and tick ``i>0``'s sampling call uses λ folded via
``erre.locomotion_sampling.advance_lambda`` (organ import, not copied) through
ticks ``0..i-1``'s ``move_t``. Index ``i`` here is the incoming λ for tick
``i`` — length equals :data:`TRAVERSAL_HORIZON`.
"""

TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS: Final[tuple[int, ...]] = tuple(
    i for i, lam in enumerate(TRAVERSAL_EXPECTED_INCOMING_LAMBDA) if lam > 0.0
)
"""Tick indices whose **sampling call** sees λ>0 (W2 operational proxy).

Excludes tick 0 (its sampling uses the seed's ``lam=0.0``, so the two-phase
knob's delta is the all-zero ablation identity there — knob-on≡off trivially,
not a witness tick). This is the same population
``two_phase_live.two_phase_firing_summary``'s ``eligible_tick_count`` counts
operationally (knob-on sampling != knob-off sampling): see
``test_traversal_lambda_update_path``'s cross-check between this constant and
the spy's actual eligible ticks — the "computed value agrees with the
operational proxy" is a stronger W2 witness than either alone (Codex review
follow-up)."""


def expected_lambda_sequence_checksum() -> str:
    """6-decimal-quantised checksum of :data:`TRAVERSAL_EXPECTED_INCOMING_LAMBDA`.

    An alternative, single-string W2 witness to the exact-tuple pin above (the
    ADR's "quantized λ sequence checksum" option) — never an effect-size or
    threshold, just a stable digest of the same pure fold.
    """
    quantised = [round(lam, 6) for lam in TRAVERSAL_EXPECTED_INCOMING_LAMBDA]
    blob = json.dumps(quantised, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------------------- #
# W3 — knob algebra on the earned-λ traversal (Issue 002)
# --------------------------------------------------------------------------- #


def traversal_generation_seed_agent_state() -> AgentState:
    """The traversal seed forced into a GENERATION-phase mode (peripatetic).

    Mirrors ``two_phase_live.generation_seeded_agent_state`` (read-only
    reuse of the *idiom*, not the function — that one is golden/study-seeded,
    this one is the peripatos traversal seed): overrides ``erre`` to
    ``peripatetic`` (∈ ``GENERATION_MODES``) so ``phase_of_mode`` = GENERATION,
    where ``two_phase_delta`` equals the frozen ES-3 ``locomotion_delta``
    (knob-on ≡ knob-off) — the phase-conditional control proving the bias
    fires *only* in the evaluation phase.
    """
    return traversal_seed_agent_state().model_copy(
        update={"erre": ERREMode(name=ERREModeName.PERIPATETIC, entered_at_tick=0)},
    )


async def run_traversal_replay_spy(
    *,
    recorded: Sequence[RecordedLlmCall],
    agent_state: AgentState,
    two_phase_knob: TwoPhaseKnob | None,
    store: MemoryStore,
    embedding: EmbeddingClient,
    retrieval_now: datetime,
    base_ts: datetime,
) -> tuple[tuple[ResolvedSampling, ...], str]:
    """Ollama-free knob-gated replay of committed traversal decisions (W3 helper).

    Mirrors ``scripts/aha_phase4b_two_phase_live_capture.py``'s
    ``_spied_replay``: wraps a replay-mode
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` in
    :class:`~erre_sandbox.integration.embodied.live_v1.SamplingSpyChatClient`
    (organ read-only reuse) so the **recomposed** per-tick sampling is visible
    — the replay client's own ``call.sampling`` is knob-invariant (it re-serves
    the recorded value regardless), so comparing it directly would silently
    mask the knob's effect. Uses the same
    :func:`traversal_observation_factory` the record run used, so a replay's
    memory-write locations match the record's (I1 discipline, though W3 does
    not depend on this for the sampling/λ witness itself).

    **Golden-path only (LOW-2 review note)**: ``persona`` is hardcoded to
    :func:`~erre_sandbox.integration.embodied.handoff.golden_persona` and the
    tick/physics counts to :data:`TRAVERSAL_HORIZON` /
    :data:`TRAVERSAL_PHYSICS_TICKS_PER_COGNITION` — this helper replays only
    the traversal's own committed decisions. Feeding it ``recorded`` decisions
    that were captured under a *different* persona or horizon does not raise;
    it silently replays against the wrong parameters and the resulting
    sampling comparison is meaningless (no cross-validation against the
    record's own provenance is performed here).
    """
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded))
    result = await run_two_phase_capture(
        run_id="traversal-w3-replay",
        store=store,
        embedding=embedding,
        llm=cast("RecordReplayChatClient", spy),
        agent_state=agent_state,
        persona=handoff.golden_persona(),
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        two_phase_knob=two_phase_knob,
        n_cognition_ticks=TRAVERSAL_HORIZON,
        physics_ticks_per_cognition=TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
        observation_factory=traversal_observation_factory(agent_state.agent_id),
    )
    return spy.sampled, result.checksum


async def traversal_firing_summary(
    *,
    store_factory: Callable[[], MemoryStore],
    embedding_factory: Callable[[], EmbeddingClient],
    retrieval_now: datetime,
    base_ts: datetime,
) -> dict[str, Any]:
    """W3 knob-algebra firing witness for the **earned** (not seeded) λ traversal.

    Sign-confirmation only (Codex LOW-3, honest framing): this is **not** a
    claim that "aha" or any generation-quality/effect occurred — only that the
    evaluation-phase sampling recomposition inverts sign vs knob-off on >=1
    λ>0 tick the traversal *itself earned* by walking the itinerary (Phase 4b
    needed a seeded λ₀; this run's λ comes from I1's zone crossings alone).

    Three Ollama-free in-memory runs, each on its **own** fresh store/embedding
    (``store_factory``/``embedding_factory`` — DI, this module constructs no
    mock itself, mirroring ``run_two_phase_capture``'s existing store/embedding
    injection contract):

    1. **Record** — one knob-on traversal run from
       :func:`traversal_seed_agent_state` (``deep_work`` ∈ ``EVALUATION_MODES``
       already, no override needed) — the committed decisions.
    2. **Replay knob-on** — :func:`run_traversal_replay_spy` on those same
       committed decisions, same evaluation seed, ``TwoPhaseKnob()``.
    3. **Replay knob-off** — the same, ``two_phase_knob=None``.

    Reduces the two spied sampling sequences via the **untouched**
    ``two_phase_live.two_phase_firing_summary`` (organ re-use, zero copy) —
    the returned dict is exactly that function's boolean/count contract
    (``verdict=None``, ``hard_gate=False``, no effect/divergence/floor/aha
    proxy field — see its own docstring).
    """
    seed = traversal_seed_agent_state()

    record_store = store_factory()
    record_store.create_schema()
    record_embedding = embedding_factory()
    try:
        record_result = await run_traversal_capture(
            run_id="traversal-w3-record",
            store=record_store,
            embedding=record_embedding,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
            agent_state=seed,
            two_phase_knob=TwoPhaseKnob(),
        )
    finally:
        await record_embedding.close()
        await record_store.close()
    recorded = record_result.replay_calls()

    on_store = store_factory()
    on_store.create_schema()
    on_embedding = embedding_factory()
    try:
        on_sampling, on_checksum = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=seed,
            two_phase_knob=TwoPhaseKnob(),
            store=on_store,
            embedding=on_embedding,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
        )
    finally:
        await on_embedding.close()
        await on_store.close()

    off_store = store_factory()
    off_store.create_schema()
    off_embedding = embedding_factory()
    try:
        off_sampling, off_checksum = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=seed,
            two_phase_knob=None,
            store=off_store,
            embedding=off_embedding,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
        )
    finally:
        await off_embedding.close()
        await off_store.close()

    return two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_checksum,
        off_checksum=off_checksum,
        committed_call_samplings=[c.sampling for c in recorded],
    )


# --------------------------------------------------------------------------- #
# I4 — embedding record/replay (real-mode Plane 1 determinism, code-path only)
# --------------------------------------------------------------------------- #
#
# Real qwen3 (I4 channel exercise) pairs with a REAL embedding client
# (``memory.embedding.EmbeddingClient``, unmodified) instead of I1-I3's
# constant-vector mock. Unlike the mock (whose output is trivially
# deterministic — the same fixed vector for every input, on any machine), a
# real embedding call is a **second** Plane 1 source (alongside the retrieval
# clock / RNG substreams ``EclRecordMode`` already pins): replaying committed
# decisions Ollama-free must also replay the embedding vectors those
# decisions' retrieval/centroid math depended on, or the geometry checksum
# will not reproduce. This mirrors ``loop.RecordReplayChatClient`` for the
# embedding channel exactly (sequential in-order replay, never
# content-matched, ``inner_invocations``/``used``/``is_replay`` witnesses) —
# a new, minimal, traversal-scoped apparatus (no organ file provides this;
# ``memory/embedding.py`` stays read-only).


@dataclass(frozen=True, slots=True)
class RecordedEmbeddingCall:
    """One captured/replayed embedding call (I4 Plane 1 record unit).

    ``vector`` is 6-decimal quantised **at record time**
    (``feedback_golden_crossplatform_float_drift`` discipline, the same rule
    ``handoff.canonical_dumps`` / ``loop.ecl_trace_checksum`` apply elsewhere)
    so a committed replay artifact is cross-platform byte-stable even though
    the original real-Ollama vector may carry platform-specific float noise
    past the sixth decimal.
    """

    kind: Literal["embed", "embed_query", "embed_document"]
    text: str
    vector: tuple[float, ...]


class EmbeddingReplayError(RuntimeError):
    """The embedding replay stream is exhausted or a record client has no inner."""


class EmbeddingRecordReplayClient:
    """Record/replay wrapper for the embedding channel (I4, code-path only).

    Duck-typed to the ``embed`` / ``embed_query`` / ``embed_document`` surface
    :class:`~erre_sandbox.memory.retrieval.Retriever` and
    :meth:`~erre_sandbox.cognition.CognitionCycle._write_observations` call
    (``embed_query`` / ``embed_document`` respectively), so it stands in for
    :class:`~erre_sandbox.memory.embedding.EmbeddingClient` without either
    caller importing this module.

    * **Record** (``inner`` set, ``recorded=None``) — each call delegates to
      the real inner client once, quantises the result
      (:class:`RecordedEmbeddingCall`), and returns the **quantised** vector
      (not the raw one) so record and replay observe byte-identical
      downstream math — the same "quantise once, both paths read the
      quantised value" discipline as ``two_phase_live.quantise_sampling``.
    * **Replay** (``recorded`` set, ``inner=None``) — returns the next
      recorded vector in call order and **never touches a network
      connection** (``inner_invocations`` stays 0 — the AC4-equivalent
      witness for this channel).
    """

    def __init__(
        self,
        *,
        inner: Any | None = None,
        recorded: Sequence[RecordedEmbeddingCall] | None = None,
    ) -> None:
        self._inner = inner
        self._replay: list[RecordedEmbeddingCall] | None = (
            list(recorded) if recorded is not None else None
        )
        self._used: list[RecordedEmbeddingCall] = []
        self._replay_index = 0
        self._inner_invocations = 0

    @property
    def is_replay(self) -> bool:
        """``True`` in replay mode (recorded vectors injected, no network)."""
        return self._replay is not None

    @property
    def used(self) -> tuple[RecordedEmbeddingCall, ...]:
        """The calls actually served, in order (record or replay alike)."""
        return tuple(self._used)

    @property
    def inner_invocations(self) -> int:
        """How many times the real inner client was called — 0 in replay mode."""
        return self._inner_invocations

    async def close(self) -> None:
        """Delegate to the inner client's ``close`` when one exists (record mode)."""
        if self._inner is not None:
            await self._inner.close()

    async def embed(self, text: str) -> list[float]:
        return await self._call("embed", text)

    async def embed_query(self, text: str) -> list[float]:
        return await self._call("embed_query", text)

    async def embed_document(self, text: str) -> list[float]:
        return await self._call("embed_document", text)

    async def embed_many(
        self, texts: Sequence[str], *, kind: Literal["query", "document"]
    ) -> list[list[float]]:
        """Record/replay the batched embedding surface (M-1 review, forward-risk).

        ``memory.embedding.EmbeddingClient.embed_many`` is the one method of
        the real client's public surface the single-call ``embed`` /
        ``embed_query`` / ``embed_document`` trio above did not mirror —
        ``cognition/cycle.py``'s M11-A individual-layer coherence path calls
        it. The traversal driver never enables that layer
        (``run_two_phase_capture`` builds no individual-layer collaborator),
        so this was previously unreachable on this apparatus's own path — but
        silently so: a future caller that *did* enable it would hit an
        ``AttributeError`` deep inside a ratified real-spend session, past
        every mock-only CI check. Completing the surface now closes that gap
        while it is still free (mock-only) to test.

        Record mode issues **one** inner ``embed_many`` call for the whole
        batch (matching the real one-HTTP-round-trip shape —
        ``inner_invocations`` increments once, not once per text) but records
        **one** :class:`RecordedEmbeddingCall` per text, so replay consumes
        exactly as many stream slots as texts were requested — the same
        position-based sequencing :meth:`_call` uses for the single-text
        methods, applied per-element here (each replayed via :meth:`_call` so
        the replay-exhaustion / no-inner-in-record-mode error paths are
        shared, not duplicated).
        """
        call_kind: Literal["embed_query", "embed_document"] = (
            "embed_query" if kind == "query" else "embed_document"
        )
        if self._replay is not None:
            return [await self._call(call_kind, text) for text in texts]
        if self._inner is None:
            msg = (
                "record-mode EmbeddingRecordReplayClient needs an inner "
                "embedding client"
            )
            raise EmbeddingReplayError(msg)
        self._inner_invocations += 1
        raw_vectors = await self._inner.embed_many(texts, kind=kind)
        result: list[list[float]] = []
        for text, raw_vector in zip(texts, raw_vectors, strict=True):
            quantised = tuple(round(v, 6) for v in raw_vector)
            self._used.append(
                RecordedEmbeddingCall(kind=call_kind, text=text, vector=quantised)
            )
            result.append(list(quantised))
        return result

    async def _call(
        self, kind: Literal["embed", "embed_query", "embed_document"], text: str
    ) -> list[float]:
        if self._replay is not None:
            if self._replay_index >= len(self._replay):
                msg = (
                    f"embedding replay exhausted after {self._replay_index} calls; "
                    "the recorded Plane 1 embedding stream is shorter than the "
                    "replay run's demand"
                )
                raise EmbeddingReplayError(msg)
            call = self._replay[self._replay_index]
            self._replay_index += 1
            self._used.append(call)
            return list(call.vector)
        if self._inner is None:
            msg = (
                "record-mode EmbeddingRecordReplayClient needs an inner "
                "embedding client"
            )
            raise EmbeddingReplayError(msg)
        self._inner_invocations += 1
        method = getattr(self._inner, kind)
        raw_vector = await method(text)
        quantised = tuple(round(v, 6) for v in raw_vector)
        self._used.append(RecordedEmbeddingCall(kind=kind, text=text, vector=quantised))
        return list(quantised)


# --------------------------------------------------------------------------- #
# I4 — channel-exercise witness (honest count annotation, non-gate)
# --------------------------------------------------------------------------- #


def traversal_channel_exercise_summary(result: EclRunResult) -> dict[str, Any]:
    """Honest count annotation for a real-LLM traversal run (I4).

    **Not a gate** (Codex HIGH-2 defer, Phase 4b O5 idiom): no ``>=K``
    threshold, no "traversal succeeded" claim, no retry-until-it-moves. Reuses
    :func:`extract_visit_sequence` (itinerary-agnostic — it reads only
    ``result.rows``, never the frozen :data:`TRAVERSAL_ITINERARY`) to report
    the plain distinct-zone-visited count and the move-tick count a real run
    actually produced. **Honesty note (LOW-2 review)**: the real backend is
    given the SAME pre-registered waypoint stimulus a scripted run is
    (``run_traversal_capture``'s ``observation_factory`` is unconditional) —
    only its *response* to that stimulus is unscripted, so "emergent
    traversal" is not the right label for what this counts; it is a count of
    an unscripted backend's response to a pre-registered stimulus. A settled
    run (the agent never left its seed zone, λ stays 0 throughout, mirrors
    Phase 4b run1's ``no_eligible_tick``) is recorded exactly as such — a
    blank run is a legitimate, honestly-reported outcome, never silently
    retried or excluded.
    """
    visited = extract_visit_sequence(result)
    move_tick_count = sum(1 for prev, nxt in pairwise(visited) if prev != nxt)
    return {
        "n_ticks": len(result.decisions),
        "visited_zone_sequence": [z.value for z in visited],
        "distinct_zone_count": len(set(visited)),
        "move_tick_count": move_tick_count,
        "settled_no_movement": move_tick_count == 0,
        "hard_gate": False,
        "verdict": None,
        "note": (
            "channel-exercise count annotation (non-gate, side file, outside "
            "any checksum/SHA/Done set): honest distinct-zone / move-tick "
            "counts of a real-LLM's unscripted response to the SAME "
            "pre-registered waypoint stimulus a scripted run receives (not "
            "an emergent/self-chosen route — only the response to the "
            "stimulus is unscripted). No >=K threshold, no traversal-success "
            "claim, no toward-tuning — a settled/blank run (0 moves) is "
            "recorded as-is, not retried until it moves."
        ),
    }


__all__ = [
    "TRAVERSAL_EXPECTED_INCOMING_LAMBDA",
    "TRAVERSAL_EXPECTED_MOVE_TICKS",
    "TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS",
    "TRAVERSAL_EXPECTED_ROUTE",
    "TRAVERSAL_HORIZON",
    "TRAVERSAL_ITINERARY",
    "TRAVERSAL_PHYSICS_TICKS_PER_COGNITION",
    "TRAVERSAL_START_ZONE",
    "EmbeddingRecordReplayClient",
    "EmbeddingReplayError",
    "RecordedEmbeddingCall",
    "ScriptedTraversalChatClient",
    "TraversalScriptError",
    "expected_lambda_sequence_checksum",
    "extract_visit_sequence",
    "run_traversal_capture",
    "run_traversal_replay_spy",
    "traversal_channel_exercise_summary",
    "traversal_firing_summary",
    "traversal_generation_seed_agent_state",
    "traversal_observation_factory",
    "traversal_seed_agent_state",
]
