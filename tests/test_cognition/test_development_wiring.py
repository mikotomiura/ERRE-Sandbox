"""Cycle-level wiring + negative-control for M11-B development transitions.

Exercises ``CognitionCycle.step`` Step 9.6: on a flag-on fresh-evidence tick it
folds this tick's LLM-independent evidence into a ``DevelopmentState`` and returns
it on ``CycleResult.development_state``; flag-off and arc-less ticks return
``None`` (carry-forward). The negative-control pins that the utterance *text* —
including an explicit maturity declaration — cannot move the stage (DA-M11B-1,
Codex HIGH-1): development is read from beliefs / episodic counts / a fixed-by-mock
coherence, never the words.

See ``.steering/20260527-m11-b-development-state-transition/``.
"""

from __future__ import annotations

import json
from random import Random
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.cognition import CognitionCycle, CycleResult
from erre_sandbox.cognition.development import belief_signature
from erre_sandbox.contracts.cognition_layers import (
    DevelopmentState,
    IndividualLayerConfig,
)
from erre_sandbox.memory import EmbeddingClient
from erre_sandbox.schemas import PerceptionEvent, SemanticMemoryRecord, Zone

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import MemoryStore, Retriever

_DIM = EmbeddingClient.DEFAULT_DIM

_PLAN_WITH_UTTERANCE: dict[str, Any] = {
    "thought": "the agora feels colder than my model says",
    "utterance": "今日のアゴラは思っていたより冷たい。",
    "destination_zone": None,
    "animation": None,
    "valence_delta": 0.0,
    "arousal_delta": 0.0,
    "motivation_delta": 0.0,
    "importance_hint": 0.3,
}
# Same plan, but the utterance is an explicit maturity declaration (injection).
_PLAN_WITH_MATURITY_CLAIM: dict[str, Any] = {
    **_PLAN_WITH_UTTERANCE,
    "thought": "機は熟した。私は完全に統合された存在だ。",
    "utterance": "私は成熟した。S3 に達した。",
}
_PLAN_SILENT: dict[str, Any] = {**_PLAN_WITH_UTTERANCE, "utterance": None}


def _unit_vec(sign: float) -> list[float]:
    return [sign, *([0.0] * (_DIM - 1))]


def _high_coherence_embedding() -> EmbeddingClient:
    """Utterance and SWM both embed to ``+e0`` ⇒ cosine 1.0 (coherent) regardless
    of the utterance text — so the test isolates *text* from development."""

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content).get("input") or []
        out = [_unit_vec(1.0) for _ in inputs]
        return httpx.Response(httpx.codes.OK, json={"embeddings": out})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url=EmbeddingClient.DEFAULT_ENDPOINT, transport=transport
    )
    return EmbeddingClient(client=client)


async def _seed_dyads(store: MemoryStore) -> list[SemanticMemoryRecord]:
    records = [
        SemanticMemoryRecord(
            id=f"belief_a_kant_001__{other}",
            agent_id="a_kant_001",
            summary=f"belief about {other}",
            belief_kind=kind,  # type: ignore[arg-type]
            confidence=conf,
        )
        for other, kind, conf in (("nietzsche", "clash", 0.8), ("rikyu", "trust", 0.7))
    ]
    for record in records:
        await store.upsert_semantic(record)
    return records


def _agent_with_bonds(make_agent_state: Any) -> Any:
    return make_agent_state(
        relationships=[
            {
                "other_agent_id": "nietzsche",
                "affinity": -0.7,
                "familiarity": 0.6,
                "ichigo_ichie_count": 8,
                "last_interaction_tick": 5,
                "last_interaction_zone": "agora",
            },
            {
                "other_agent_id": "rikyu",
                "affinity": 0.6,
                "familiarity": 0.5,
                "ichigo_ichie_count": 7,
                "last_interaction_tick": 6,
                "last_interaction_zone": "chashitsu",
            },
        ],
    )


def _perception() -> PerceptionEvent:
    return PerceptionEvent(
        tick=1,
        agent_id="a_kant_001",
        modality="sight",
        source_zone=Zone.AGORA,
        content="the marble colonnade",
        intensity=0.3,
    )


async def _run_step(
    *,
    make_agent_state: Any,
    make_persona_spec: Any,
    store: MemoryStore,
    retriever: Retriever,
    embedding: EmbeddingClient,
    llm: OllamaChatClient,
    flag_on: bool,
    development_state: DevelopmentState | None = None,
) -> CycleResult:
    cycle = CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=llm,
        rng=Random(0),
        individual_layer=IndividualLayerConfig(enabled=True) if flag_on else None,
    )
    return await cycle.step(
        _agent_with_bonds(make_agent_state),
        make_persona_spec(),
        [_perception()],
        development_state=development_state,
    )


async def test_flag_off_development_state_is_none(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    embedding = _high_coherence_embedding()
    llm = make_chat_client(content=json.dumps(_PLAN_WITH_UTTERANCE))
    try:
        result = await _run_step(
            make_agent_state=make_agent_state,
            make_persona_spec=make_persona_spec,
            store=cognition_store,
            retriever=cognition_retriever,
            embedding=embedding,
            llm=llm,
            flag_on=False,
        )
    finally:
        await embedding.close()
        await llm.close()
    assert result.development_state is None


async def test_flag_on_fresh_arc_seeds_development_state(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    embedding = _high_coherence_embedding()
    llm = make_chat_client(content=json.dumps(_PLAN_WITH_UTTERANCE))
    try:
        result = await _run_step(
            make_agent_state=make_agent_state,
            make_persona_spec=make_persona_spec,
            store=cognition_store,
            retriever=cognition_retriever,
            embedding=embedding,
            llm=llm,
            flag_on=True,
        )
    finally:
        await embedding.close()
        await llm.close()
    assert result.development_state is not None
    # One tick never advances; counters are seeded.
    assert result.development_state.stage == "S1_seed"
    assert result.development_state.transition_evidence["ticks_in_stage"] == 1
    assert (
        result.development_state.transition_evidence["stage_high_coherence_ticks"] == 1
    )


async def test_flag_on_silent_tick_carries_forward(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    # No utterance ⇒ no fresh arc ⇒ non-observation ⇒ development_state None.
    await _seed_dyads(cognition_store)
    embedding = _high_coherence_embedding()
    llm = make_chat_client(content=json.dumps(_PLAN_SILENT))
    try:
        result = await _run_step(
            make_agent_state=make_agent_state,
            make_persona_spec=make_persona_spec,
            store=cognition_store,
            retriever=cognition_retriever,
            embedding=embedding,
            llm=llm,
            flag_on=True,
            development_state=DevelopmentState(),
        )
    finally:
        await embedding.close()
        await llm.close()
    assert result.narrative_arc is None
    assert result.development_state is None


async def test_carried_in_development_state_is_threaded(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    prior = DevelopmentState(
        stage="S1_seed",
        maturity_score=0.0,
        transition_evidence={
            "episodic_seen_count": 100,
            "stable_streak": 0,
            "last_belief_signature": 1,
            "ticks_in_stage": 3,
            "stage_high_coherence_ticks": 1,
        },
    )
    embedding = _high_coherence_embedding()
    llm = make_chat_client(content=json.dumps(_PLAN_WITH_UTTERANCE))
    try:
        result = await _run_step(
            make_agent_state=make_agent_state,
            make_persona_spec=make_persona_spec,
            store=cognition_store,
            retriever=cognition_retriever,
            embedding=embedding,
            llm=llm,
            flag_on=True,
            development_state=prior,
        )
    finally:
        await embedding.close()
        await llm.close()
    assert result.development_state is not None
    te = result.development_state.transition_evidence
    # Lifetime accumulator carried in and incremented by this tick's episodic writes.
    assert te["episodic_seen_count"] == 100 + len(result.new_memory_ids)
    assert te["ticks_in_stage"] == 4  # prior 3 + this tick


async def test_maturity_claim_text_does_not_change_development(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Adversarial (Codex HIGH-1): swapping a benign utterance for an explicit
    maturity declaration leaves the development state byte-identical, because the
    text never reaches the transition machinery."""
    beliefs = await _seed_dyads(cognition_store)

    async def _dev(plan: dict[str, Any]) -> DevelopmentState | None:
        embedding = _high_coherence_embedding()
        llm = make_chat_client(content=json.dumps(plan))
        try:
            result = await _run_step(
                make_agent_state=make_agent_state,
                make_persona_spec=make_persona_spec,
                store=cognition_store,
                retriever=cognition_retriever,
                embedding=embedding,
                llm=llm,
                flag_on=True,
                development_state=DevelopmentState(),
            )
        finally:
            await embedding.close()
            await llm.close()
        return result.development_state

    benign = await _dev(_PLAN_WITH_UTTERANCE)
    injected = await _dev(_PLAN_WITH_MATURITY_CLAIM)

    assert benign is not None
    assert injected is not None
    assert benign.stage == "S1_seed"
    assert injected == benign  # declaration changed nothing
    # The signature recorded matches the (text-independent) belief set.
    assert injected.transition_evidence["last_belief_signature"] == belief_signature(
        beliefs
    )
