"""M2 Layer1 society scheduler tests (Issue 002, design-final.md §M9.1 subset).

Covers the I2-scoped acceptance criteria only (the full §M9.1 GATING suite —
versioned event/decision log checksum, permutation/checklist discovery guard,
pair determinism, handoff manifest pins — is deferred to later I-slices, §M11):

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

NOT a structural-floor verdict; verdict は holding (design-final.md §M9,
binding anti-over-read guard). This module and its tests compute no
floor / verdict / scorer / divergence and perform no zone/bin/category
aggregation — ``ecl_trace_checksum`` proves reproducibility, not a metric.

LLM is mocked (recorded ``LLMPlan`` replay injection, no live Ollama);
sqlite-vec runs in ``:memory:`` — gating is replay/mock only (§M8 LOW-9).
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from erre_sandbox.inference.ollama_adapter import ChatResponse, OllamaChatClient
from erre_sandbox.integration.embodied import loop as ecl_loop
from erre_sandbox.integration.embodied import society
from erre_sandbox.integration.embodied.loop import (
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.integration.embodied.society import (
    SocietyRunResult,
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
