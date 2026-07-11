"""M2 Layer1 society scheduler tests (Issues 002/003, design-final.md §M9.1 subset).

Covers the I2/I3-scoped acceptance criteria only (the full §M9.1 GATING suite —
permutation/checklist discovery guard, pair determinism, handoff manifest pins —
is deferred to later I-slices, §M11):

* **I2-G1** ``test_m2_society_n1_canonical_equivalent`` — society driver at
  N=1 is canonical-equivalent to ``run_ecl_loop`` (same underlying schema in
  this issue, so byte-identical checksum — a strictly stronger witness than
  the ADR's "canonical projection equivalence" floor, since I2 introduces no
  new schema).
* **I2-G2** ``test_m2_society_sequential_scheduler_order`` — N=3 agents step
  cognition strictly in ``sorted(order_slot)`` order, one at a time, and the
  driver source never calls ``asyncio.gather``.
* **I2-G3** ``test_m2_society_plane2_per_agent_replay`` — N=3 agents' Plane 2
  round-trips independently (record -> replay: ``inner_invocations == 0`` +
  per-agent byte-identical checksum).
* **I2-G4** ``test_m2_step_cognition_once_seam`` — the new
  ``WorldRuntime.step_cognition_once`` public seam steps one agent
  deterministically, bypassing the live phase-wheel.
* **I2-G5** — existing ECL v0/v1 legacy byte-invariant regression + I1 tick
  tests stay green is verified by the unmodified existing test suites, not
  duplicated here (``run_ecl_loop``/``loop.py`` are untouched by this issue).
* **I3-G1** ``test_m2_society_event_log_checksum_stable`` — the versioned
  event/decision-log-wide checksum (:func:`event_log_checksum`) is
  byte-identical across two runs of the same (seed, recorded Plane 2).
* **I3-G2** ``test_m2_log_carries_self_other_slot_forward_compat`` — the
  ``self_other_observation_input`` slot is versioned additive
  (``None | {schema_version, payload}``); Layer1's ``None`` is checksum-stable
  and a well-formed non-``None`` envelope changes the digest without raising.
* **I3-G3** ``test_m2_eventlog_covers_social_cognitive`` — the checksum is
  sensitive to each of dialog/affinity/memory-mutation/pair-event/decision
  category, not just geometry.
* **I3-G4** ``test_m2_eventlog_6digit_quantized`` — event-log floats are
  quantised to 6 decimals before hashing (cross-platform byte-identity
  precondition, ``feedback_golden_crossplatform_float_drift``).
* **I4-G1** ``test_m2_pair_interaction_deterministic`` — N=2, proximity/dialog
  RNG keyed by a per-pair named substream (``pair_key`` = canonical JSON
  array) is replay-stable through the real ``run_society_loop`` driver (not a
  vacuous module-level RNG check — DG-6); pair events serialize
  ``sorted_pair=(min_id,max_id)``.
* **I4-G2** ``test_m2_society_determinism_permutation`` — N=3, registering the
  same agent set in different orders yields the same ``event_log_checksum``.
* **I4-G3** ``test_m2_society_determinism_checklist`` — discovery guard
  (Codex MEDIUM-8): no wall-clock, checksum-path AST/text scan for bare
  non-sorted ``.values()``/``set(...)`` iteration, DB read ``ORDER BY``,
  canonical key sort, checksum input = final canonical projection only.
* **I4-G4** ``test_m2_pair_key_collision_free`` — ``pair_key`` (canonical JSON
  array) does not collide when an ``agent_id`` itself contains ``"-"``
  (Codex MEDIUM-7; the naive ``"-".join(sorted(...))`` alternative would).

NOT a structural-floor verdict; verdict は holding (design-final.md §M9,
binding anti-over-read guard). This module and its tests compute no
floor / verdict / scorer / divergence and perform no zone/bin/category
aggregation — ``ecl_trace_checksum`` / ``event_log_checksum`` prove
reproducibility, not a metric.

LLM is mocked (recorded ``LLMPlan`` replay injection, no live Ollama);
sqlite-vec runs in ``:memory:`` — gating is replay/mock only (§M8 LOW-9).
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from erre_sandbox.cognition import parse_llm_plan
from erre_sandbox.inference.ollama_adapter import ChatResponse, OllamaChatClient
from erre_sandbox.integration.embodied import loop as ecl_loop
from erre_sandbox.integration.embodied import society
from erre_sandbox.integration.embodied.loop import (
    RecordedLlmCall,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.integration.embodied.society import (
    AffinityDeltaRecord,
    DialogEventRecord,
    MemoryMutationRecord,
    PairEventRecord,
    SocietyRunResult,
    event_log_checksum,
    run_society_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import AgentState, PersonaSpec

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)
_PLAN_JSON = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)


def _chat_client(content: str) -> OllamaChatClient:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(
            httpx.codes.OK,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
            },
        )

    return OllamaChatClient(
        client=httpx.AsyncClient(
            base_url=OllamaChatClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


def _embed_client() -> EmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vec = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


class _ScriptedInner:
    """Duck-typed inner chat client returning a fixed content, call-counted."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls = 0

    async def chat(self, messages, *, sampling, model=None, options=None, think=None):  # noqa: ARG002
        self.calls += 1
        return ChatResponse(
            content=self._content,
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )


async def _run_society(
    agent_states: list[AgentState],
    personas: dict[str, PersonaSpec],
    *,
    run_id: str = "s0",
    seed: int = 0,
    n_cognition_ticks: int = 4,
    physics_ticks_per_cognition: int = 5,
) -> tuple[SocietyRunResult, dict[str, RecordReplayChatClient]]:
    """One record-mode society drive on a fresh in-memory store + embedder."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    inners = {s.agent_id: _ScriptedInner(_PLAN_JSON) for s in agent_states}
    clients = {
        agent_id: RecordReplayChatClient(inner=inner)
        for agent_id, inner in inners.items()
    }
    try:
        result = await run_society_loop(
            run_id=run_id,
            store=store,
            embedding=embedding,
            llms=clients,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
        return result, clients
    finally:
        await embedding.close()
        await store.close()


async def _replay_society(
    result: SocietyRunResult,
    agent_states: list[AgentState],
    personas: dict[str, PersonaSpec],
    *,
    run_id: str = "s0",
    seed: int = 0,
    n_cognition_ticks: int = 4,
    physics_ticks_per_cognition: int = 5,
) -> tuple[SocietyRunResult, dict[str, RecordReplayChatClient]]:
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    replay_clients = result.replay_clients()
    try:
        replayed = await run_society_loop(
            run_id=run_id,
            store=store,
            embedding=embedding,
            llms=replay_clients,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
        return replayed, replay_clients
    finally:
        await embedding.close()
        await store.close()


# --------------------------------------------------------------------------- #
# I2-G1 — N=1 society is canonical-equivalent to run_ecl_loop
# --------------------------------------------------------------------------- #


async def test_m2_society_n1_canonical_equivalent(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """society driver at N=1 must match run_ecl_loop's single-agent output.

    NOT a structural-floor verdict; verdict は holding. This is a causal-wiring
    / schema-equivalence check (single agent embedded in the society driver
    reduces to exactly the pre-existing single-agent path), not a measurement
    of emergent behaviour.
    """
    agent_state = make_agent_state()
    persona = make_persona_spec()

    # --- run_ecl_loop reference ---
    inner = _chat_client(_PLAN_JSON)
    ecl_client = RecordReplayChatClient(inner=inner)
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        ecl_result = await run_ecl_loop(
            run_id="s0",
            store=store,
            embedding=embedding,
            llm=ecl_client,
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            seed=0,
            n_cognition_ticks=4,
            physics_ticks_per_cognition=5,
            observation_factory=ecl_loop._default_observation_factory(
                agent_state.agent_id
            ),
        )
    finally:
        await embedding.close()
        await store.close()
        await inner.close()

    # --- society driver, N=1 ---
    society_result, _clients = await _run_society(
        [agent_state], {agent_state.agent_id: persona}
    )

    # Canonical projection equivalence: same rows -> same checksum (I2 keeps
    # the pre-existing single schema, so this is byte equality, a strictly
    # stronger witness than a cross-schema "semantic equivalence" claim).
    assert society_result.checksum == ecl_result.checksum
    assert len(society_result.rows) == len(ecl_result.rows)
    assert len(society_result.decisions[agent_state.agent_id]) == len(
        ecl_result.decisions
    )
    for got, want in zip(
        society_result.decisions[agent_state.agent_id],
        ecl_result.decisions,
        strict=True,
    ):
        assert got.plan == want.plan
        assert got.llm_status == want.llm_status
        assert got.move_decision == want.move_decision

    # Single-agent order_slot is 0, matching run_ecl_loop's convention.
    assert all(row.order_slot == 0 for row in society_result.rows)


# --------------------------------------------------------------------------- #
# I2-G2 — N=3 sequential sorted(order_slot) scheduler, no asyncio.gather
# --------------------------------------------------------------------------- #


async def test_m2_society_sequential_scheduler_order(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_states = [
        make_agent_state(agent_id="a_charlie", persona_id="kant"),
        make_agent_state(agent_id="a_alpha", persona_id="kant"),
        make_agent_state(agent_id="a_bravo", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}
    sorted_ids = sorted(s.agent_id for s in agent_states)

    result, _clients = await _run_society(agent_states, personas, n_cognition_ticks=3)

    # Causal-wiring witness: the driver stepped agents strictly in
    # sorted(agent_id) order, once per window, N_ticks*N_agents total steps.
    assert result.cognition_step_order == tuple(sorted_ids) * 3

    # order_slot assigned per the same sorted(agent_id) convention.
    for row in result.rows:
        assert row.order_slot == sorted_ids.index(row.agent_id)

    # Record-mode sequential scheduling never uses asyncio.gather to fan out
    # cognition (§M4.1) — inspect the driver source directly (construction
    # discovery guard, not a runtime measurement).
    source = inspect.getsource(society.run_society_loop)
    assert "asyncio.gather(" not in source, (
        "record-mode driver must not fan out cognition via asyncio.gather"
    )


# --------------------------------------------------------------------------- #
# I2-G3 — per-agent Plane2 record -> replay round trip (N=3)
# --------------------------------------------------------------------------- #


async def test_m2_society_plane2_per_agent_replay(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
        make_agent_state(agent_id="a_three", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}

    recorded, record_clients = await _run_society(
        agent_states, personas, n_cognition_ticks=3
    )
    assert recorded.rows, "record run produced no trace rows"
    for agent_id, client in record_clients.items():
        assert client.inner_invocations == len(recorded.decisions[agent_id])

    replayed, replay_clients = await _replay_society(
        recorded, agent_states, personas, n_cognition_ticks=3
    )

    # Replay never touched a live/inner LLM, for any agent.
    for agent_id, client in replay_clients.items():
        assert client.inner_invocations == 0
        # Per-agent LLMPlan byte-identical reconstruction.
        assert [d.plan for d in replayed.decisions[agent_id]] == [
            d.plan for d in recorded.decisions[agent_id]
        ]
        assert [d.call.raw_response for d in replayed.decisions[agent_id]] == [
            d.call.raw_response for d in recorded.decisions[agent_id]
        ]

    assert replayed.checksum == recorded.checksum


# --------------------------------------------------------------------------- #
# I2-G4 — WorldRuntime.step_cognition_once public seam
# --------------------------------------------------------------------------- #


async def test_m2_step_cognition_once_seam(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The new seam steps exactly one agent, bypassing the phase-wheel.

    Constructed directly against ``WorldRuntime`` (not via ``society.py``) so
    the seam's own contract is pinned independent of the driver.
    """
    from erre_sandbox.cognition import CognitionCycle
    from erre_sandbox.cognition.embodiment import EclRecordMode
    from erre_sandbox.memory import Retriever
    from erre_sandbox.world import ManualClock, WorldRuntime

    agent_state = make_agent_state()
    persona = make_persona_spec()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    inner = _ScriptedInner(_PLAN_JSON)
    llm = RecordReplayChatClient(inner=inner)
    try:
        retriever = Retriever(store, embedding, now_factory=_FIXED)
        ecl_mode = EclRecordMode(
            run_id="seam0",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            reflection_disabled=True,
        )
        cycle = CognitionCycle(
            retriever=retriever,
            store=store,
            embedding=embedding,
            llm=llm,  # type: ignore[arg-type]
            ecl_mode=ecl_mode,
        )
        clock = ManualClock(start=0.0)
        world = WorldRuntime(cycle=cycle, clock=clock, physics_hz=30.0)
        world.register_agent(agent_state, persona)

        # Never went through _on_cognition_tick's phase-wheel: next_cognition_due
        # defaults to 0.0 but that field is irrelevant here — step_cognition_once
        # ignores it entirely (no due-time / dwell gate).
        result = await world.step_cognition_once(agent_state.agent_id)
        assert result is not None
        assert result.agent_state.agent_id == agent_state.agent_id
        # The world's carried state reflects the step (mirrors _consume_result).
        assert world._agents[agent_state.agent_id].state.tick == result.agent_state.tick

        # Unregistered agent surfaces loudly (KeyError, not swallowed).
        with pytest.raises(KeyError):
            await world.step_cognition_once("does-not-exist")
    finally:
        await embedding.close()
        await store.close()


# --------------------------------------------------------------------------- #
# Spend/measurement non-re-entry guard (construction-scoped, §M1/§M8 spirit)
# --------------------------------------------------------------------------- #


def test_m2_society_module_imports_no_measurement_machinery() -> None:
    """society.py imports no evidence/spdm/runningness machinery (§M8 主 guard).

    Full AST allowlist guard + Counter/groupby/numpy/scipy/statistics denial is
    I6 scope; this is the minimal I2-scoped import check so the driver never
    quietly re-enters the measurement line.
    """
    src_path = society.__file__
    assert src_path is not None
    text = Path(src_path).read_text(encoding="utf-8")
    forbidden = ("evidence.", "runningness", "landscape_divergence", "spdm")
    for token in forbidden:
        assert token not in text, f"society.py must not reference {token!r}"


# --------------------------------------------------------------------------- #
# I3-G1 — versioned event/decision-log-wide checksum is stable
# --------------------------------------------------------------------------- #


async def test_m2_society_event_log_checksum_stable(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Two runs of the same (seed, recorded Plane 2) yield the same event-log checksum.

    NOT a structural-floor verdict; verdict は holding. This is a reproducibility
    witness (design-final.md §M4.4), not a metric/floor/verdict — the checksum
    covers geometry (via ``ecl_trace_checksum``, embedded as ``geometry_checksum``)
    + pair events + memory mutations + the (always-``None`` in Layer1) self-other
    slot + per-agent LLMPlan replay, not geometry alone.
    """
    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
        make_agent_state(agent_id="a_three", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}

    run1, _clients1 = await _run_society(agent_states, personas, n_cognition_ticks=3)
    run2, _clients2 = await _run_society(agent_states, personas, n_cognition_ticks=3)

    assert run1.event_log_checksum == run2.event_log_checksum

    # Recomputing directly from the result's own fields reproduces the stored
    # digest — ties the public function to what the driver actually returns.
    for run in (run1, run2):
        recomputed = event_log_checksum(
            rows=run.rows,
            decisions=run.decisions,
            pair_events=run.pair_events,
            dialog_events=run.dialog_events,
            affinity_deltas=run.affinity_deltas,
            memory_mutations=run.memory_mutations,
            self_other_observation_input=run.self_other_observation_input,
        )
        assert recomputed == run.event_log_checksum

    # Layer1 always reserves the slot as None (§M5.1). Affinity mutation is
    # never produced by this driver (§M4.4 — the sole producer in the
    # codebase is bootstrap.py application wiring, outside this issue).
    # Dialog IS now wired (I4, DG-6): whether this scenario actually admits
    # a dialog is co-location-dependent, but the two independent runs above
    # already proved run1/run2 event-log-checksum equality — i.e. whatever
    # dialog_events this scenario produces is itself replay-stable.
    assert run1.self_other_observation_input is None
    assert run1.dialog_events == run2.dialog_events
    assert run1.affinity_deltas == ()
    # Reflection is disabled in record mode, but every injected perception is
    # still committed as an episodic memory each cognition tick — a non-empty
    # witness that the memory-mutation category is genuinely exercised here.
    assert run1.memory_mutations, "expected at least one committed episodic row"

    # geometry_checksum is part of the whole, not a stand-in for it: mutating
    # only a geometry row (unrelated to any other category) changes
    # event_log_checksum too.
    mutated_first_row = dataclasses.replace(run1.rows[0], x=run1.rows[0].x + 1.0)
    mutated_rows = (mutated_first_row, *run1.rows[1:])
    assert (
        event_log_checksum(
            rows=mutated_rows,
            decisions=run1.decisions,
            pair_events=run1.pair_events,
            memory_mutations=run1.memory_mutations,
        )
        != run1.event_log_checksum
    )


# --------------------------------------------------------------------------- #
# I3-G2 — self_other_observation_input: versioned-additive Layer2 seam slot
# --------------------------------------------------------------------------- #


def test_m2_log_carries_self_other_slot_forward_compat() -> None:
    """The slot is ``None | {schema_version, payload}``; Layer1's None is byte-stable.

    NOT a structural-floor verdict; verdict は holding. Forward-compat means: a
    well-formed Layer2 envelope changes the digest (it is real checksum input)
    without raising / requiring a schema break; a malformed envelope is
    rejected loudly (§M5.1 minimal wire envelope, frozen).
    """
    base_kwargs = {
        "rows": (),
        "decisions": {},
        "pair_events": (),
        "dialog_events": (),
        "affinity_deltas": (),
        "memory_mutations": (),
    }

    none_a = event_log_checksum(**base_kwargs, self_other_observation_input=None)
    none_b = event_log_checksum(**base_kwargs, self_other_observation_input=None)
    assert none_a == none_b, "Layer1 None slot must be byte-invariant"

    populated = event_log_checksum(
        **base_kwargs,
        self_other_observation_input={
            "schema_version": "mirror-sim-0",
            "payload": {"observed_appraisal": "calm"},
        },
    )
    assert populated != none_a, (
        "a well-formed Layer2 envelope must change the digest (real input, "
        "not a decorative field)"
    )

    # A second, differently-valued well-formed envelope also changes the
    # digest relative to the first (payload content genuinely participates).
    populated_2 = event_log_checksum(
        **base_kwargs,
        self_other_observation_input={
            "schema_version": "mirror-sim-0",
            "payload": {"observed_appraisal": "distressed"},
        },
    )
    assert populated_2 != populated

    # Malformed envelopes (missing/extra keys, wrong schema_version type) are
    # rejected loudly rather than silently hashed.
    with pytest.raises(ValueError, match="schema_version"):
        event_log_checksum(
            **base_kwargs,
            self_other_observation_input={"payload": {}},
        )
    with pytest.raises(ValueError, match="schema_version"):
        event_log_checksum(
            **base_kwargs,
            self_other_observation_input={
                "schema_version": "mirror-sim-0",
                "payload": {},
                "extra": 1,
            },
        )
    with pytest.raises(TypeError, match="schema_version"):
        event_log_checksum(
            **base_kwargs,
            self_other_observation_input={"schema_version": 1, "payload": {}},
        )


# --------------------------------------------------------------------------- #
# I3-G3 — checksum covers social/cognitive events, not geometry alone
# --------------------------------------------------------------------------- #


def test_m2_eventlog_covers_social_cognitive() -> None:
    """Mutating any one event category (not just geometry) changes the checksum.

    NOT a structural-floor verdict; verdict は holding. Demonstrates the §M4.4
    sensitivity requirement directly against :func:`event_log_checksum` (a pure
    function of its inputs), independent of whether this driver's current
    wiring produces non-empty dialog/affinity data live.
    """

    def _decision(raw: str) -> society.EclDecisionRecord:
        call = RecordedLlmCall(
            system_prompt="s",
            user_prompt="u",
            sampling=None,  # type: ignore[arg-type]
            response=ChatResponse(
                content=raw, model="qwen3:8b", eval_count=1, total_duration_ms=0.0
            ),
            outcome="ok",
        )
        plan = parse_llm_plan(raw)
        return society.EclDecisionRecord(
            agent_tick=0,
            call=call,
            plan=plan,
            plan_schema_version="v1",
            llm_fell_back=False,
            llm_status="ok",
            bias_fired=None,
            move_decision=None,
            envelope_provenance=(),
        )

    base_decision = _decision(_PLAN_JSON)
    other_plan_json = json.dumps(
        {
            "thought": "different",
            "utterance": "違う",
            "destination_zone": "agora",
            "animation": "walk",
        }
    )
    mutated_decision = _decision(other_plan_json)

    base_pair = PairEventRecord(
        tick=1,
        sorted_pair=("a_one", "a_two"),
        distance_prev=6.0,
        distance_now=4.0,
        crossing="enter",
    )
    mutated_pair = PairEventRecord(
        tick=1,
        sorted_pair=("a_one", "a_two"),
        distance_prev=6.0,
        distance_now=4.5,
        crossing="enter",
    )

    base_dialog = DialogEventRecord(
        dialog_id="d0",
        tick=1,
        turn_index=0,
        speaker_agent_id="a_one",
        addressee_agent_id="a_two",
        utterance="ようこそ",
    )
    mutated_dialog = DialogEventRecord(
        dialog_id="d0",
        tick=1,
        turn_index=0,
        speaker_agent_id="a_one",
        addressee_agent_id="a_two",
        utterance="さようなら",
    )

    base_affinity = AffinityDeltaRecord(
        tick=1,
        agent_id="a_one",
        other_agent_id="a_two",
        delta=0.1,
        resulting_affinity=0.1,
    )
    mutated_affinity = AffinityDeltaRecord(
        tick=1,
        agent_id="a_one",
        other_agent_id="a_two",
        delta=0.2,
        resulting_affinity=0.2,
    )

    base_memory = MemoryMutationRecord(
        memory_id="ecl-a_one-0000",
        agent_id="a_one",
        kind="episodic",
        content="forage step 0",
        importance=0.4,
        created_at="2026-01-01T00:00:00+00:00",
        tags=(),
    )
    mutated_memory = MemoryMutationRecord(
        memory_id="ecl-a_one-0000",
        agent_id="a_one",
        kind="episodic",
        content="forage step 0 MUTATED",
        importance=0.4,
        created_at="2026-01-01T00:00:00+00:00",
        tags=(),
    )

    base = event_log_checksum(
        rows=(),
        decisions={"a_one": (base_decision,)},
        pair_events=(base_pair,),
        dialog_events=(base_dialog,),
        affinity_deltas=(base_affinity,),
        memory_mutations=(base_memory,),
    )

    variants = {
        "decision": event_log_checksum(
            rows=(),
            decisions={"a_one": (mutated_decision,)},
            pair_events=(base_pair,),
            dialog_events=(base_dialog,),
            affinity_deltas=(base_affinity,),
            memory_mutations=(base_memory,),
        ),
        "pair_event": event_log_checksum(
            rows=(),
            decisions={"a_one": (base_decision,)},
            pair_events=(mutated_pair,),
            dialog_events=(base_dialog,),
            affinity_deltas=(base_affinity,),
            memory_mutations=(base_memory,),
        ),
        "dialog_event": event_log_checksum(
            rows=(),
            decisions={"a_one": (base_decision,)},
            pair_events=(base_pair,),
            dialog_events=(mutated_dialog,),
            affinity_deltas=(base_affinity,),
            memory_mutations=(base_memory,),
        ),
        "affinity_delta": event_log_checksum(
            rows=(),
            decisions={"a_one": (base_decision,)},
            pair_events=(base_pair,),
            dialog_events=(base_dialog,),
            affinity_deltas=(mutated_affinity,),
            memory_mutations=(base_memory,),
        ),
        "memory_mutation": event_log_checksum(
            rows=(),
            decisions={"a_one": (base_decision,)},
            pair_events=(base_pair,),
            dialog_events=(base_dialog,),
            affinity_deltas=(base_affinity,),
            memory_mutations=(mutated_memory,),
        ),
    }

    for category, checksum in variants.items():
        assert checksum != base, (
            f"non-canonical {category!r} must change event_log_checksum "
            "(social/cognitive event coverage, §M4.4)"
        )
    # And every variant differs from every other (no accidental collision
    # masking one category's mutation with another's).
    values = [base, *variants.values()]
    assert len(set(values)) == len(values)


# --------------------------------------------------------------------------- #
# I3-G4 — event-log floats are 6-decimal quantised before hashing
# --------------------------------------------------------------------------- #


def test_m2_eventlog_6digit_quantized() -> None:
    """Sub-6th-decimal float differences collapse; 6th-decimal differences don't.

    Mirrors ``ecl_trace_checksum``'s cross-platform quantisation rule
    (``feedback_golden_crossplatform_float_drift``) applied to the event-log
    categories introduced in this issue (pair-event distances here).
    """

    def _pair(distance_now: float) -> PairEventRecord:
        return PairEventRecord(
            tick=0,
            sorted_pair=("a_one", "a_two"),
            distance_prev=5.0,
            distance_now=distance_now,
            crossing="enter",
        )

    kwargs = {"rows": (), "decisions": {}}

    sub_ulp_a = event_log_checksum(pair_events=(_pair(4.1234561),), **kwargs)
    sub_ulp_b = event_log_checksum(pair_events=(_pair(4.1234564),), **kwargs)
    assert sub_ulp_a == sub_ulp_b, (
        "differences beyond the 6th decimal must round away before hashing"
    )

    distinct_a = event_log_checksum(pair_events=(_pair(4.100001),), **kwargs)
    distinct_b = event_log_checksum(pair_events=(_pair(4.100002),), **kwargs)
    assert distinct_a != distinct_b, (
        "a genuine 6th-decimal difference must still change the digest"
    )


# --------------------------------------------------------------------------- #
# I4-G1 — per-pair named RNG substream, real driver, pair-interaction determinism
# --------------------------------------------------------------------------- #


async def test_m2_pair_interaction_deterministic(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """N=2, co-located from tick 0: proximity + dialog RNG replay-stable.

    NOT a structural-floor verdict; verdict は holding. Two co-located agents
    are placed in a reflective zone (``peripatos``) from tick 0 so the
    dialog scheduler's proximity auto-fire draw — keyed by this pair's own
    named RNG substream (§M4.2, ``pair_key`` = canonical JSON array) — gets
    a real chance to fire through the actual :func:`run_society_loop` driver
    (DG-6: not a vacuous module-level RNG check). Two independent runs of the
    same (seed, recorded Plane 2) must agree byte-for-byte, whatever the
    scenario's dialog outcome turns out to be.
    """
    agent_states = [
        make_agent_state(
            agent_id="a_one",
            position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        ),
        make_agent_state(
            agent_id="a_two",
            position={"x": 0.1, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        ),
    ]
    personas = {s.agent_id: make_persona_spec() for s in agent_states}

    run1, _c1 = await _run_society(
        agent_states, personas, run_id="i4-pair", n_cognition_ticks=8
    )
    run2, _c2 = await _run_society(
        agent_states, personas, run_id="i4-pair", n_cognition_ticks=8
    )

    assert run1.event_log_checksum == run2.event_log_checksum
    assert run1.dialog_events == run2.dialog_events
    assert run1.pair_events == run2.pair_events

    # The scenario is designed to actually exercise the dialog channel (DG-6)
    # — an empty result here would mean the fixture failed to provoke the
    # real driver path this test exists to pin, not a vacuous pass.
    assert run1.dialog_events, (
        "co-located N=2 scenario expected to admit at least one dialog turn "
        "through the real driver (DG-6 — not a vacuous RNG-only check)"
    )
    for evt in run1.dialog_events:
        assert {evt.speaker_agent_id, evt.addressee_agent_id} == {"a_one", "a_two"}

    # Pair events (proximity) always serialize the canonical sorted_pair
    # orientation (Codex HIGH-3), independent of registration order.
    for pe in run1.pair_events:
        assert pe.sorted_pair == tuple(sorted(pe.sorted_pair))

    # A different run_id changes the named substream material
    # (``ecl-{run_id}-{pair_key}-{stream}``) — the dialog channel is keyed by
    # run identity, not a fixed global sequence.
    run3, _c3 = await _run_society(
        agent_states, personas, run_id="i4-pair-other", n_cognition_ticks=8
    )
    assert run3.event_log_checksum != run1.event_log_checksum


# --------------------------------------------------------------------------- #
# I4-G2 — registration-order permutation invariance (N=3)
# --------------------------------------------------------------------------- #


async def test_m2_society_determinism_permutation(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Same N=3 agent set, different registration orders, same checksum.

    NOT a structural-floor verdict; verdict は holding. ``order_slot =
    sorted(agent_id)`` (§M2) plus the §M4.3 sorted-combinations discovery
    guard means dict-insertion/registration order must never leak into
    ``event_log_checksum`` — this is the causal-wiring witness for that
    claim (Codex MEDIUM-8's "既知集合限定 → 実装保証" permutation test).
    """
    ids = ["a_alpha", "a_bravo", "a_charlie"]
    agent_states_by_id = {aid: make_agent_state(agent_id=aid) for aid in ids}
    personas = {aid: make_persona_spec() for aid in ids}

    checksums: set[str] = set()
    for order in itertools.permutations(ids):
        ordered_states = [agent_states_by_id[aid] for aid in order]
        result, _clients = await _run_society(
            ordered_states, personas, run_id="i4-perm", n_cognition_ticks=3
        )
        checksums.add(result.event_log_checksum)

    assert len(checksums) == 1, (
        "registering the same N=3 agent set in different orders must yield "
        f"the same event_log_checksum; got {len(checksums)} distinct digests"
    )


# --------------------------------------------------------------------------- #
# I4-G3 — discovery guard: no bare non-sorted values()/set() in checksum path
# --------------------------------------------------------------------------- #

_CHECKSUM_PATH_FUNCS: tuple[str, ...] = (
    "event_log_checksum",
    "_pair_event_projection",
    "_dialog_event_projection",
    "_affinity_delta_projection",
    "_memory_mutation_projection",
    "_decision_projection",
    "_quantized_plan_dump",
    "_collect_memory_mutations",
    "_harvest_pair_events",
    "run_society_loop",
)


def test_m2_society_determinism_checklist() -> None:
    """AST/grep discovery guard extending the checklist to N agents (§M4.3, MEDIUM-8).

    NOT a structural-floor verdict; verdict は holding. Checks, against the
    module's own source (construction-provenance inspection, not a runtime
    measurement):

    1. no wall-clock read anywhere in the module.
    2. the checksum-path functions (:data:`_CHECKSUM_PATH_FUNCS`) contain no
       bare non-sorted ``.values()`` iteration, and every bare ``set(...)``
       call is immediately wrapped in ``sorted(...)`` (``sorted(set(...))``
       is the only allowed shape — canonicalisation, §M8 HIGH-4).
    3. DB/SQLite reads use ``ORDER BY``.
    4. the versioned event-log's per-category lists are explicitly sorted
       before projection (canonical key sort).
    """
    src_path = society.__file__
    assert src_path is not None
    full_source = Path(src_path).read_text(encoding="utf-8")

    # 1. no wall-clock.
    assert "time.time(" not in full_source
    assert "datetime.now(" not in full_source
    assert ".utcnow(" not in full_source

    # 2. checksum-path bare non-sorted values()/set() scan.
    combined = "\n".join(
        inspect.getsource(getattr(society, name)) for name in _CHECKSUM_PATH_FUNCS
    )
    assert ".values()" not in combined, (
        "checksum-path code must not iterate a bare (non-sorted) .values() "
        "— §M4.3 discovery guard"
    )
    for match in re.finditer(r"\bset\(", combined):
        preceding = combined[: match.start()].rstrip()
        assert preceding.endswith("sorted("), (
            "checksum-path code must not construct a bare set(...) — only "
            f"sorted(set(...)) canonicalisation is allowed (§M8 HIGH-4); "
            f"found unwrapped set( at offset {match.start()}"
        )

    # 3. DB read uses ORDER BY (the one SQL query on the checksum path,
    # _collect_memory_mutations).
    collect_source = inspect.getsource(society._collect_memory_mutations)
    assert "ORDER BY" in collect_source
    assert "SELECT" in collect_source

    # 4. canonical key sort: event_log_checksum explicitly sorts every
    # variable-order event category before projecting it (not just the
    # already-deterministic geometry/decisions inputs).
    checksum_source = inspect.getsource(society.event_log_checksum)
    for sorted_call in (
        "sorted(\n        pair_events,",
        "sorted(\n        dialog_events,",
        "sorted(\n        affinity_deltas,",
        "sorted(memory_mutations,",
    ):
        assert sorted_call in checksum_source, (
            "event_log_checksum must canonically sort before projecting: "
            f"{sorted_call!r}"
        )


# --------------------------------------------------------------------------- #
# I4-G4 — pair_key collision-free (agent_id containing "-")
# --------------------------------------------------------------------------- #


def test_m2_pair_key_collision_free() -> None:
    """``pair_key`` = canonical JSON array does not collide on ``"-"``-bearing ids.

    Codex MEDIUM-7: ``"-".join(sorted([a_id, b_id]))`` collides — both
    ``["a-b", "c"]`` and ``["a", "b-c"]`` join to the literal string
    ``"a-b-c"``. The canonical-JSON-array construction must not.
    """
    key_1 = society._pair_key("a-b", "c")
    key_2 = society._pair_key("a", "b-c")
    assert key_1 != key_2, "pair_key must not collide when an agent_id contains '-'"

    # Demonstrate the naive alternative *does* collide, so the regression this
    # guards against is not a strawman.
    naive_1 = "-".join(sorted(["a-b", "c"]))
    naive_2 = "-".join(sorted(["a", "b-c"]))
    assert naive_1 == naive_2 == "a-b-c"

    # Order-agnostic (unordered pair identity) and a genuine canonical-JSON
    # array shape (not just "any string that happens to differ").
    assert society._pair_key("a-b", "c") == society._pair_key("c", "a-b")
    assert key_1 == json.dumps(["a-b", "c"], separators=(",", ":"), ensure_ascii=True)
    assert key_2 == json.dumps(["a", "b-c"], separators=(",", ":"), ensure_ascii=True)
