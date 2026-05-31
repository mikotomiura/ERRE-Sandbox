"""Tests for the M6-A-3 ReasoningTrace pipeline.

The cognition cycle's LLM response now optionally carries three narrative
fields (``salient`` / ``decision`` / ``next_intent``) used by the Godot
xAI visualisation. This file covers two layers:

* **Parse layer** (``cognition.parse``) — the new fields are optional
  with sensible ``None`` defaults so stable-output-below-100% does not
  kill a tick.
* **Envelope layer** (``cognition.cycle._build_envelopes``) — a
  :class:`~erre_sandbox.schemas.ReasoningTraceMsg` is appended when the
  LLM filled at least one field, and omitted entirely otherwise (so
  downstream consumers can count "traces per N ticks" as a live metric
  of LLM output stability).
"""

from __future__ import annotations

import json
from random import Random
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.parse import LLMPlan, parse_llm_plan
from erre_sandbox.schemas import (
    AgentUpdateMsg,
    ReasoningTrace,
    ReasoningTraceMsg,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import ControlEnvelope, PersonaSpec


# ---------- Shared plan-JSON helper ----------


def _plan_json(**overrides: object) -> str:
    body: dict[str, object] = {
        "thought": "walk the peripatos",
        "utterance": None,
        "destination_zone": None,
        "animation": None,
        "valence_delta": 0.0,
        "arousal_delta": 0.0,
        "motivation_delta": 0.0,
        "importance_hint": 0.5,
    }
    body.update(overrides)
    return json.dumps(body)


# ---------- Parse layer ----------


def test_parse_plan_without_reasoning_fields_defaults_to_none() -> None:
    plan = parse_llm_plan(_plan_json())
    assert plan is not None
    assert plan.salient is None
    assert plan.decision is None
    assert plan.next_intent is None


def test_parse_plan_with_all_reasoning_fields() -> None:
    plan = parse_llm_plan(
        _plan_json(
            salient="鐘の音が午後の始まりを告げた",
            decision="散策を続けて批判書の構想を練る",
            next_intent="書斎に戻り第二章を書き継ぐ",
        ),
    )
    assert plan is not None
    assert plan.salient == "鐘の音が午後の始まりを告げた"
    assert plan.decision == "散策を続けて批判書の構想を練る"
    assert plan.next_intent == "書斎に戻り第二章を書き継ぐ"


def test_parse_plan_with_partial_reasoning_fields() -> None:
    """Only ``decision`` filled is valid — other two fall back to ``None``."""
    plan = parse_llm_plan(_plan_json(decision="沈黙する"))
    assert plan is not None
    assert plan.decision == "沈黙する"
    assert plan.salient is None
    assert plan.next_intent is None


def test_parse_plan_rejects_non_string_reasoning() -> None:
    # The fields are ``str | None`` — a raw number must fail validation.
    assert parse_llm_plan(_plan_json(salient=42)) is None


# ---------- Envelope layer (integration with CognitionCycle) ----------


def _reasoning_msgs(envelopes: list[ControlEnvelope]) -> list[ReasoningTraceMsg]:
    return [e for e in envelopes if isinstance(e, ReasoningTraceMsg)]


async def test_cycle_emits_reasoning_trace_envelope_when_fields_filled(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    llm_content = _plan_json(
        thought="walking reveals an intuition",
        utterance="今日は鐘の音が澄んで聞こえる。",
        salient="遠くの聖堂の鐘",
        decision="散策を続けて定言命法を言語化する",
        next_intent="戻って三批判書の第二章を書き継ぐ",
    )
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client(content=llm_content)

    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    msgs = _reasoning_msgs(result.envelopes)
    assert len(msgs) == 1
    trace: ReasoningTrace = msgs[0].trace
    assert trace.agent_id == result.agent_state.agent_id
    assert trace.persona_id == result.agent_state.persona_id  # M7ζ stamp
    assert trace.tick == result.agent_state.tick
    assert trace.mode == result.agent_state.erre.name
    assert trace.salient == "遠くの聖堂の鐘"
    assert trace.decision == "散策を続けて定言命法を言語化する"
    assert trace.next_intent == "戻って三批判書の第二章を書き継ぐ"


async def test_cycle_stamps_persona_id_for_non_default_persona(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """The persona_id stamp must follow ``AgentState.persona_id``, not a constant.

    M7ζ: the Godot ``ReasoningPanel`` uses ``trace.persona_id`` to look up
    display_name + 1-line summary in its static dict, so a wrong stamp would
    surface the wrong persona to the researcher.
    """
    llm_content = _plan_json(decision="silence is the answer")
    persona: PersonaSpec = make_persona_spec(
        persona_id="rikyu",
        display_name="Sen no Rikyū",
    )
    agent = make_agent_state(agent_id="a_rikyu_002", persona_id="rikyu")
    embedding = make_embedding_client()
    llm = make_chat_client(content=llm_content)

    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    msgs = _reasoning_msgs(result.envelopes)
    assert len(msgs) == 1
    assert msgs[0].trace.persona_id == "rikyu"


def test_reasoning_trace_persona_id_defaults_to_none() -> None:
    """Older M7ε wire payloads (no persona_id) deserialise as ``persona_id=None``.

    Backward-compat invariant — without this, the M7ζ schema bump would
    immediately break any cached fixtures captured pre-0.9.0-m7z.
    """
    trace = ReasoningTrace.model_validate(
        {
            "agent_id": "a_kant_001",
            "tick": 7,
            "mode": "deep_work",
            "salient": "an old payload",
        },
    )
    assert trace.persona_id is None
    # Round-trip preserves the explicit None.
    re_loaded = ReasoningTrace.model_validate_json(trace.model_dump_json())
    assert re_loaded.persona_id is None


async def test_cycle_omits_reasoning_trace_envelope_when_all_none(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Pre-M6 behaviour is preserved when the LLM omits all reasoning fields."""
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()  # DEFAULT_PLAN has no reasoning fields

    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    assert _reasoning_msgs(result.envelopes) == []
    # AgentUpdateMsg is still emitted — the trace is additive, not replacing.
    assert any(isinstance(e, AgentUpdateMsg) for e in result.envelopes)


async def test_cycle_emits_reasoning_trace_with_only_decision(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """A trace with only one non-null field still triggers the envelope.

    Observability rule: even a single line of rationale is load-bearing for
    the researcher, so we don't gate on "all three fields present".
    """
    llm_content = _plan_json(decision="沈黙して待つ")
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client(content=llm_content)

    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    msgs = _reasoning_msgs(result.envelopes)
    assert len(msgs) == 1
    assert msgs[0].trace.decision == "沈黙して待つ"
    assert msgs[0].trace.salient is None
    assert msgs[0].trace.next_intent is None


def test_llm_plan_model_accepts_null_reasoning_fields() -> None:
    """Explicit ``None`` is canonical; round-trip through ``LLMPlan``."""
    plan = LLMPlan.model_validate(
        json.loads(
            _plan_json(salient=None, decision=None, next_intent=None),
        ),
    )
    assert plan.salient is None
    assert plan.decision is None
    assert plan.next_intent is None
