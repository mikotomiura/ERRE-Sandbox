"""ECL v0 integration determinism harness tests (M13, Issue 004).

The harness (``integration/embodied/loop.py``) drives the Issue 003 live seam
(``cognition/cycle.py`` + ``world/tick.py``, both unmodified) as a pure
record/replay apparatus. These tests pin the two-plane determinism contract
(design-final.md §論点3):

* **AC1** ``test_ecl_v0_replay_checksum_stable`` — a record run and two replay
  runs (same ``run_id`` + seed + recorded Plane 2) produce a byte-identical
  :func:`ecl_trace_checksum`.
* **AC2** ``test_ecl_v0_reflection_disabled_in_record_mode`` — the reflection LLM
  never fires end-to-end in record mode (``Reflector.maybe_reflect`` un-called).
* **AC3** ``test_ecl_v0_log_schema_forward_compat`` — every trace row carries
  ``agent_id`` / ``physics_tick_index`` / ``agent_tick`` / ``order_slot``, with
  ``order_slot`` a deterministic ``sorted(agent_id)`` function (0 for one agent)
  and the 30 Hz ``physics_tick_index`` axis distinct from the cognition
  ``agent_tick``.
* **AC4** ``test_ecl_v0_plane2_full_llm_record`` — each recorded decision carries
  the full :class:`LLMPlan` + fallback / parser / prompt / sampling, and replaying
  from the decisions alone reconstructs the state with **no** fresh LLM call.

A measurement-line non-re-entry guard (design §論点4) mirrors the Issue 002
embodiment guard: the harness imports no ``evidence`` / ``spdm`` / ``runningness``
machinery and defines no floor / landscape / verdict identifier.

LLM is mocked (recorded ``LLMPlan`` replay injection, no live Ollama); sqlite-vec
runs in ``:memory:``.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from erre_sandbox.cognition.reflection import Reflector
from erre_sandbox.inference.ollama_adapter import (
    ChatResponse,
    OllamaChatClient,
    OllamaUnavailableError,
)
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied import loop as ecl_loop
from erre_sandbox.integration.embodied.loop import (
    EclTraceRow,
    RecordedLlmCall,
    RecordReplayChatClient,
    ecl_trace_checksum,
    replay_client_from,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import SCHEMA_VERSION, Zone

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult
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


# --------------------------------------------------------------------------- #
# Self-contained mock inference clients (deterministic, no live Ollama)
# --------------------------------------------------------------------------- #


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


class _SpyReflector(Reflector):
    """Reflector that counts ``maybe_reflect`` calls (should stay 0 in record mode)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls = 0

    async def maybe_reflect(self, **kwargs: Any) -> None:  # type: ignore[override]  # noqa: ARG002
        self.calls += 1


class _ScriptedInner:
    """Duck-typed inner chat client that fails on chosen action-LLM ticks.

    Returns ``content`` verbatim, except on the 0-based call indices in
    ``raise_on`` where it raises ``OllamaUnavailableError`` — the record-side
    outage the harness must record as a ``raised`` call and reproduce on replay
    (α, B-2). Structurally matches the ``chat`` surface the harness calls.
    """

    def __init__(self, *, content: str, raise_on: frozenset[int] = frozenset()) -> None:
        self._content = content
        self._raise_on = raise_on
        self.calls = 0

    async def chat(self, messages, *, sampling, model=None, options=None, think=None):  # noqa: ARG002
        idx = self.calls
        self.calls += 1
        if idx in self._raise_on:
            raise OllamaUnavailableError("mock LLM outage (scripted)")
        return ChatResponse(
            content=self._content,
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )


async def _run(
    llm: RecordReplayChatClient,
    agent_state: AgentState,
    persona: PersonaSpec,
    *,
    run_id: str = "r0",
    seed: int = 0,
    reflector: Reflector | None = None,
    n_cognition_ticks: int = 8,
    physics_ticks_per_cognition: int = 20,
) -> EclRunResult:
    """One record/replay drive on a fresh in-memory store + embedder."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        return await run_ecl_loop(
            run_id=run_id,
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            seed=seed,
            reflector=reflector,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
    finally:
        await embedding.close()
        await store.close()


async def _record_run(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    *,
    run_id: str = "r0",
    seed: int = 0,
    reflector: Reflector | None = None,
) -> EclRunResult:
    inner = _chat_client(_PLAN_JSON)
    client = RecordReplayChatClient(inner=inner)
    try:
        return await _run(
            client,
            make_agent_state(),
            make_persona_spec(),
            run_id=run_id,
            seed=seed,
            reflector=reflector,
        )
    finally:
        await inner.close()


# --------------------------------------------------------------------------- #
# AC1 — replay checksum is byte-stable (record ≡ replay ≡ replay)
# --------------------------------------------------------------------------- #


async def test_ecl_v0_replay_checksum_stable(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    recorded = await _record_run(make_agent_state, make_persona_spec)
    assert recorded.rows, "record run produced no trace rows"

    replay1_client = replay_client_from(recorded)
    replay1 = await _run(replay1_client, make_agent_state(), make_persona_spec())

    replay2_client = replay_client_from(recorded)
    replay2 = await _run(replay2_client, make_agent_state(), make_persona_spec())

    # Same run_id + seed + recorded Plane 2 ⇒ byte-identical trace checksum.
    assert recorded.checksum == replay1.checksum == replay2.checksum
    # And the checksum is a pure function of the rows (recompute matches).
    assert ecl_trace_checksum(recorded.rows) == recorded.checksum
    # Replay never touched a live LLM.
    assert replay1_client.inner_invocations == 0
    assert replay2_client.inner_invocations == 0


# --------------------------------------------------------------------------- #
# AC2 — reflection LLM disabled in record mode
# --------------------------------------------------------------------------- #


async def test_ecl_v0_reflection_disabled_in_record_mode(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    inner = _chat_client(_PLAN_JSON)
    client = RecordReplayChatClient(inner=inner)
    embedding = _embed_client()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    spy = _SpyReflector(store=store, embedding=embedding, llm=inner)
    try:
        result = await run_ecl_loop(
            run_id="r0",
            store=store,
            embedding=embedding,
            llm=client,
            agent_state=make_agent_state(),
            persona=make_persona_spec(),
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            reflector=spy,
        )
    finally:
        await embedding.close()
        await store.close()
        await inner.close()

    # The reflection LLM (second non-determinism source) never fired.
    assert spy.calls == 0
    # Exactly one action-LLM call per cognition tick — no extra reflection calls.
    assert client.inner_invocations == len(result.decisions)


# --------------------------------------------------------------------------- #
# AC3 — trace-row log slots forward compatible + axis separation
# --------------------------------------------------------------------------- #


async def test_ecl_v0_log_schema_forward_compat(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    recorded = await _record_run(make_agent_state, make_persona_spec)
    rows = recorded.rows
    agent_id = make_agent_state().agent_id

    # Every row exposes the forward-compatible log slots.
    for row in rows:
        assert row.agent_id == agent_id
        assert isinstance(row.physics_tick_index, int)
        assert isinstance(row.agent_tick, int)
        # order_slot is a deterministic sorted(agent_id) function — 0 for one agent.
        assert row.order_slot == sorted([agent_id]).index(agent_id) == 0

    # agent_tick spans all cognition windows (0..7); physics_tick_index is the 30 Hz
    # counter, a distinct axis (it advances within and across windows).
    assert {row.agent_tick for row in rows} == set(range(8))
    assert max(row.physics_tick_index for row in rows) >= 8
    # The two axes are not the same counter: many physics indices share one
    # agent_tick (20 physics ticks per cognition window).
    window0 = [r.physics_tick_index for r in rows if r.agent_tick == 0]
    assert len(window0) == 20


# --------------------------------------------------------------------------- #
# AC4 — Plane 2 record completeness + replay-from-decisions reconstruction
# --------------------------------------------------------------------------- #


async def test_ecl_v0_plane2_full_llm_record(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    recorded = await _record_run(make_agent_state, make_persona_spec)

    assert len(recorded.decisions) == 8
    for i, decision in enumerate(recorded.decisions):
        # Full post-processed LLMPlan present and parsed.
        assert decision.plan is not None
        assert decision.plan.destination_zone is Zone.PERIPATOS
        # Parser / schema version.
        assert decision.plan_schema_version == SCHEMA_VERSION
        # Fallback status (the harness LLM always returns → no fallback).
        assert decision.llm_fell_back is False
        assert decision.llm_status == "ok"
        # Prompt + sampling captured.
        assert decision.call.system_prompt
        assert decision.call.user_prompt
        assert decision.call.sampling.temperature >= 0.0
        # Raw response is the exact replay-injection string.
        assert decision.call.raw_response == _PLAN_JSON
        # Move-decision provenance surfaced (history-dependent after tick 0).
        assert decision.move_decision is not None
        # Envelope provenance non-empty (at least the AgentUpdate + Move).
        assert decision.envelope_provenance
        assert decision.agent_tick == i

    # Replay from the recorded decisions ALONE reconstructs the run with no LLM.
    replay_client = replay_client_from(recorded)
    replayed = await _run(replay_client, make_agent_state(), make_persona_spec())
    assert replay_client.inner_invocations == 0
    assert replayed.checksum == recorded.checksum


# --------------------------------------------------------------------------- #
# Determinism plumbing — RecordReplayChatClient contract
# --------------------------------------------------------------------------- #


async def test_record_replay_client_exhaustion_raises(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """A replay stream shorter than the run's demand raises, never silently loops."""
    recorded = await _record_run(make_agent_state, make_persona_spec)
    short: Sequence[RecordedLlmCall] = recorded.replay_calls()[:2]
    client = RecordReplayChatClient(recorded=short)
    try:
        raised = False
        try:
            await _run(client, make_agent_state(), make_persona_spec())
        except ecl_loop.EclReplayError:
            raised = True
        assert raised, "exhausted replay stream did not raise EclReplayError"
    finally:
        assert client.inner_invocations == 0


# --------------------------------------------------------------------------- #
# α (B-2) — outcome-tagged Plane 2: raised / unparseable are recorded + replayed
# --------------------------------------------------------------------------- #


async def test_ecl_loop_raised_call_does_not_crash(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """An LLM outage on tick 3 does not crash the run (no positional IndexError)."""
    inner = _ScriptedInner(content=_PLAN_JSON, raise_on=frozenset({3}))
    client = RecordReplayChatClient(inner=inner)
    recorded = await _run(
        client, make_agent_state(), make_persona_spec(), n_cognition_ticks=6
    )

    # The run completed all 6 ticks and ``used`` stayed tick-aligned (len==ticks).
    assert len(recorded.decisions) == 6
    assert len(client.used) == 6

    # The raised tick recorded the outage as its own outcome (no parse attempted).
    raised = recorded.decisions[3]
    assert raised.call.outcome == "raised"
    assert raised.call.response is None
    assert raised.llm_status == "raised"
    assert raised.plan is None
    assert raised.llm_fell_back is True

    # The other ticks parsed normally.
    for i, decision in enumerate(recorded.decisions):
        if i == 3:
            continue
        assert decision.call.outcome == "ok"
        assert decision.llm_status == "ok"
        assert decision.plan is not None


async def test_ecl_loop_raised_replay_checksum_matches(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """A record run with a raised tick replays (decisions alone) to the same sum."""
    inner = _ScriptedInner(content=_PLAN_JSON, raise_on=frozenset({2}))
    record_client = RecordReplayChatClient(inner=inner)
    recorded = await _run(
        record_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=5
    )
    assert recorded.decisions[2].llm_status == "raised"

    replay_client = replay_client_from(recorded)
    replayed = await _run(
        replay_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=5
    )

    # Replay re-raised the recorded outage (no live LLM) and reproduced the fallback.
    assert replay_client.inner_invocations == 0
    assert replayed.checksum == recorded.checksum
    assert replayed.decisions[2].llm_status == "raised"
    assert replayed.decisions[2].plan is None


async def test_ecl_loop_unparseable_replay_checksum_matches(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Unparseable content → fallback on record and replay → identical checksum."""
    inner = _ScriptedInner(content="this is not a plan")
    record_client = RecordReplayChatClient(inner=inner)
    recorded = await _run(
        record_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=4
    )
    # Content is recorded as ``ok`` (a successful call); the fallback is derived by
    # re-parsing to ``None`` — so the replay reproduces it without a flag.
    assert all(d.call.outcome == "ok" for d in recorded.decisions)
    assert all(d.llm_status == "unparseable" for d in recorded.decisions)
    assert all(d.plan is None for d in recorded.decisions)

    replay_client = replay_client_from(recorded)
    replayed = await _run(
        replay_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=4
    )
    assert replay_client.inner_invocations == 0
    assert replayed.checksum == recorded.checksum
    assert all(d.llm_status == "unparseable" for d in replayed.decisions)


async def test_ecl_loop_success_then_raised_replay_matches(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """ok → raised → ok replays to a byte-identical checksum (Codex LOW/H-13).

    The raised tick's fallback advances position from the prior tick's in-flight
    ``Kinematics.destination``, so the whole sequence is deterministic only if the
    replay re-raises at exactly the recorded tick.
    """
    inner = _ScriptedInner(content=_PLAN_JSON, raise_on=frozenset({1}))
    record_client = RecordReplayChatClient(inner=inner)
    recorded = await _run(
        record_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=3
    )
    assert [d.llm_status for d in recorded.decisions] == ["ok", "raised", "ok"]

    replay_client = replay_client_from(recorded)
    replayed = await _run(
        replay_client, make_agent_state(), make_persona_spec(), n_cognition_ticks=3
    )
    assert replay_client.inner_invocations == 0
    assert replayed.checksum == recorded.checksum
    assert [d.llm_status for d in replayed.decisions] == ["ok", "raised", "ok"]


# --------------------------------------------------------------------------- #
# γ-G2 (C/B-4) — checksum canonicalisation is CANONICAL_JSON_RULES (drift-pin)
# --------------------------------------------------------------------------- #


def _trace_row(**overrides: Any) -> EclTraceRow:
    """A fully-populated ``EclTraceRow`` for the checksum canonicalisation pin."""
    fields: dict[str, Any] = {
        "run_id": "rün-canon",  # non-ASCII ⇒ ensure_ascii=False is observable
        "agent_id": "a0",
        "physics_tick_index": 3,
        "agent_tick": 1,
        "order_slot": 0,
        "x": 1.5,
        "y": 0.0,
        "z": -2.25,
        "yaw": 0.1,
        "pitch": 0.0,
        "zone": Zone.PERIPATOS,
        "resolved_from": "memory_centroid",
        "move_centroid": (1.0, 2.0),
        "move_provenance": ("m1", "m2"),
        "move_jitter": (0.1, 0.2),
        "move_pre_clamp": (1.1, 2.2),
        "move_post_clamp": (1.1, 2.2),
        "move_clamp_fired": False,
    }
    fields.update(overrides)
    return EclTraceRow(**fields)


def test_ecl_trace_checksum_canonical_rules() -> None:
    """``ecl_trace_checksum`` canonicalises identically to CANONICAL_JSON_RULES.

    C (B-4): the checksum's ``json.dumps`` must apply the same
    ``sort_keys`` + compact ``separators`` + ``ensure_ascii=False`` +
    ``allow_nan=False`` rules the manifest advertises, so a consumer recomputing
    the digest under the published rules gets identical bytes. A non-finite float
    raises rather than being silently hashed (Stop condition, design §論点3).
    """
    row = _trace_row()

    # Behavioural drift-pin: the digest equals sha256 over the *same* canonical
    # projection serialised with handoff.canonical_dumps (the CANONICAL_JSON_RULES
    # serialiser). The non-ASCII ``run_id`` pins ensure_ascii=False; the compact
    # separators / sort_keys are pinned because json's defaults would differ.
    expected_projection = [
        {
            "run_id": row.run_id,
            "agent_id": row.agent_id,
            "physics_tick_index": row.physics_tick_index,
            "agent_tick": row.agent_tick,
            "order_slot": row.order_slot,
            "x": row.x,
            "y": row.y,
            "z": row.z,
            "yaw": row.yaw,
            "pitch": row.pitch,
            "zone": row.zone.value,
            "resolved_from": row.resolved_from,
            "move_centroid": [1.0, 2.0],
            "move_provenance": ["m1", "m2"],
            "move_jitter": [0.1, 0.2],
            "move_pre_clamp": [1.1, 2.2],
            "move_post_clamp": [1.1, 2.2],
            "move_clamp_fired": False,
        }
    ]
    expected_digest = hashlib.sha256(
        handoff.canonical_dumps(expected_projection).encode("utf-8")
    ).hexdigest()
    assert ecl_trace_checksum([row]) == expected_digest

    # allow_nan=False: a non-finite float in the trace raises (not silently hashed).
    with pytest.raises(ValueError, match=r"[Nn]a[Nn]|[Ii]nf|not.*JSON"):
        ecl_trace_checksum([_trace_row(x=float("inf"))])
    with pytest.raises(ValueError, match=r"[Nn]a[Nn]|[Ii]nf|not.*JSON"):
        ecl_trace_checksum([_trace_row(y=float("nan"))])

    # Advertised-rules pin: the manifest rules the consumer reads match the four
    # levers the checksum inlines (drift between the two is the failure this guards).
    rules = handoff.CANONICAL_JSON_RULES
    assert rules["sort_keys"] is True
    assert rules["ensure_ascii"] is False
    assert rules["separators"] == [",", ":"]
    assert rules["allow_nan"] is False


# --------------------------------------------------------------------------- #
# Measurement-line non-re-entry (import / output guard, not a word ban)
# --------------------------------------------------------------------------- #


_LOOP_TREE = ast.parse(Path(ecl_loop.__file__).read_text(encoding="utf-8"))


def test_ecl_loop_no_measurement_imports() -> None:
    """The harness imports no measurement machinery (design §論点4)."""
    banned_prefix = ("erre_sandbox.evidence",)
    banned_sub = ("spdm", "runningness")
    for node in ast.walk(_LOOP_TREE):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(banned_prefix), node.module
            assert not any(s in node.module for s in banned_sub), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_prefix), alias.name
                assert not any(s in alias.name for s in banned_sub), alias.name


def test_ecl_loop_no_measurement_output_identifiers() -> None:
    """No floor / landscape / verdict output identifier is defined (docstrings may
    still name them). Identifier-level, mirroring the Issue 002 embodiment guard."""
    banned = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
    for node in ast.walk(_LOOP_TREE):
        names: list[str] = []
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        for name in names:
            low = name.lower()
            assert not any(tok in low for tok in banned), name
