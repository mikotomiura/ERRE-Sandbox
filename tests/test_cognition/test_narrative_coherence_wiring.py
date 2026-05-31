"""Wiring + negative-control tests for M11-A coherence → reflection (diagnostic).

Exercises the cycle-level integration: ``CognitionCycle.step`` Step 9.5 distils a
``NarrativeArc`` and a coherence score against the *prompt-visible* SWM, and a
clearly-incoherent utterance adds one reflection-deepening signal — and nothing
else. The negative-control test pins ``diagnostic ⊥ control``: a high- vs
low-coherence run differs only in the diagnostic arc/coherence and the reflection
signal, never in stage / sampling / drift / world-model state.

See ``.steering/20260527-m11-a-narrative-arc-coherence/decisions.md``.
"""

from __future__ import annotations

import json
from random import Random
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from erre_sandbox.cognition import CognitionCycle, CycleResult
from erre_sandbox.cognition.reflection import ReflectionPolicy
from erre_sandbox.contracts.cognition_layers import IndividualLayerConfig
from erre_sandbox.memory import EmbeddingClient, EmbeddingUnavailableError
from erre_sandbox.schemas import (
    PerceptionEvent,
    ReflectionEventMsg,
    SemanticMemoryRecord,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

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


def _unit_vec(sign: float) -> list[float]:
    """A full-dim unit vector along the first axis (so the store accepts it)."""
    return [sign, *([0.0] * (_DIM - 1))]


def _coherence_embedding(*, swm_sign: float) -> EmbeddingClient:
    """Embedding client whose SWM render embeds (anti)parallel to the utterance.

    The utterance (and any episodic text) embeds to ``+e0``; the rendered SWM —
    detected by its ``value=``/``tick=`` shape — embeds to ``swm_sign·e0``. So
    ``swm_sign=+1`` → cosine 1.0 (coherent), ``swm_sign=-1`` → cosine -1.0
    (clearly incoherent, below ``LOW_COHERENCE_THRESHOLD``).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content).get("input") or []
        out = []
        for text in inputs:
            is_swm = "value=" in text and "tick=" in text
            out.append(_unit_vec(swm_sign if is_swm else 1.0))
        return httpx.Response(httpx.codes.OK, json={"embeddings": out})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url=EmbeddingClient.DEFAULT_ENDPOINT,
        transport=transport,
    )
    return EmbeddingClient(client=client)


async def _seed_dyads(store: MemoryStore) -> None:
    for other, kind, conf in (("nietzsche", "clash", 0.8), ("rikyu", "trust", 0.7)):
        await store.upsert_semantic(
            SemanticMemoryRecord(
                id=f"belief_a_kant_001__{other}",
                agent_id="a_kant_001",
                summary=f"belief about {other}",
                belief_kind=kind,  # type: ignore[arg-type]
                confidence=conf,
            ),
        )


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


# --------------------------------------------------------------------------
# ReflectionPolicy: the 4th (diagnostic) OR condition
# --------------------------------------------------------------------------


def test_should_fire_low_coherence_is_fourth_or_condition() -> None:
    policy = ReflectionPolicy()
    base = {"ticks_since_last": 0, "importance_sum": 0.0, "zone_entered": False}
    assert policy.should_fire(**base) is False  # all base conditions quiet
    assert policy.should_fire(**base, low_coherence=True) is True


def test_should_fire_default_low_coherence_preserves_behaviour() -> None:
    """Omitting low_coherence keeps the original three-condition result."""
    policy = ReflectionPolicy()
    assert (
        policy.should_fire(ticks_since_last=0, importance_sum=0.0, zone_entered=False)
        is False
    )


# --------------------------------------------------------------------------
# Cycle Step 9.5 wiring
# --------------------------------------------------------------------------


async def _run_step(
    *,
    make_agent_state: Any,
    make_persona_spec: Any,
    store: MemoryStore,
    retriever: Retriever,
    embedding: EmbeddingClient,
    llm: OllamaChatClient,
    flag_on: bool,
) -> CycleResult:
    perception = _perception()
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
        [
            perception,
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


async def test_flag_on_high_coherence_builds_arc_without_extra_reflection(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    embedding = _coherence_embedding(swm_sign=1.0)
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

    assert result.narrative_arc is not None
    assert result.narrative_arc.coherence_score == pytest.approx(1.0)
    assert len(result.narrative_arc.arc_segments) >= 1
    # High coherence + quiet base conditions ⇒ no reflection deepening.
    assert result.reflection_triggered is False
    assert result.reflection_event is None


async def test_flag_on_low_coherence_triggers_reflection(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    embedding = _coherence_embedding(swm_sign=-1.0)
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

    assert result.narrative_arc is not None
    assert result.narrative_arc.coherence_score == pytest.approx(-1.0)
    assert result.reflection_triggered is True
    assert result.reflection_event is not None
    assert any(isinstance(e, ReflectionEventMsg) for e in result.envelopes)


async def test_silent_utterance_skips_arc(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    silent = {**_PLAN_WITH_UTTERANCE, "utterance": None}
    embedding = _coherence_embedding(swm_sign=-1.0)
    llm = make_chat_client(content=json.dumps(silent))
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

    assert result.narrative_arc is None
    assert result.reflection_triggered is False  # no arc ⇒ no coherence trigger


async def test_embedding_outage_skips_arc_without_raising(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)

    def boom(request: httpx.Request) -> httpx.Response:
        del request
        raise EmbeddingUnavailableError("down")

    embedding = EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(boom),
        ),
    )
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

    assert isinstance(result, CycleResult)  # did not raise
    assert result.narrative_arc is None
    assert result.reflection_triggered is False


async def test_flag_off_never_synthesises_arc(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    await _seed_dyads(cognition_store)
    embedding = _coherence_embedding(swm_sign=-1.0)
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

    assert result.narrative_arc is None
    assert result.world_model_runtime is None  # whole individual layer inert
    assert result.reflection_triggered is False


# --------------------------------------------------------------------------
# ★ negative-control: diagnostic ⊥ control
# --------------------------------------------------------------------------


async def test_coherence_does_not_drive_control(
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """High vs low coherence: only diagnostic arc/coherence + reflection differ.

    Everything on the *control surface* — ERRE stage/mode, sampling-bearing
    cognitive state, physical state, and the carried world model — must be
    byte-identical between the two runs. coherence is measured but never
    optimised against (the continuity-bias guard's twin self-restraint).
    """

    async def run(swm_sign: float) -> CycleResult:
        await _seed_dyads(cognition_store)
        embedding = _coherence_embedding(swm_sign=swm_sign)
        llm = make_chat_client(content=json.dumps(_PLAN_WITH_UTTERANCE))
        try:
            return await _run_step(
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

    coherent = await run(1.0)
    incoherent = await run(-1.0)

    # --- control surface: IDENTICAL ---
    assert coherent.agent_state.erre == incoherent.agent_state.erre
    assert coherent.agent_state.cognitive == incoherent.agent_state.cognitive
    assert coherent.agent_state.physical == incoherent.agent_state.physical
    assert coherent.agent_state.position == incoherent.agent_state.position
    assert coherent.world_model_runtime is not None
    assert incoherent.world_model_runtime is not None
    assert (
        coherent.world_model_runtime.modulated
        == incoherent.world_model_runtime.modulated
    )
    # Non-reflection envelopes match in shape (reflection adds one in the low
    # run); timestamps are volatile so compare the control-bearing projection.
    assert _control_envelopes(coherent.envelopes) == _control_envelopes(
        incoherent.envelopes
    )

    # --- diagnostic + reflection signal: MAY differ (and here, do) ---
    assert coherent.narrative_arc is not None
    assert incoherent.narrative_arc is not None
    assert (
        coherent.narrative_arc.coherence_score
        != incoherent.narrative_arc.coherence_score
    )
    assert coherent.reflection_triggered is False
    assert incoherent.reflection_triggered is True


def _control_envelopes(envelopes: Sequence[Any]) -> list[tuple[str, str | None]]:
    """Control-bearing projection of the envelope stream (timestamp-free).

    The diagnostic-only :class:`ReflectionEventMsg` is dropped (it is the one
    permitted difference); each remaining envelope is reduced to its ``kind`` and
    its speech utterance (``None`` for non-speech) — the volatile ``sent_at`` /
    ``wall_clock`` fields are deliberately excluded so the comparison reflects
    control content, not wall-clock noise.
    """
    return [
        (e.kind, getattr(e, "utterance", None))
        for e in envelopes
        if not isinstance(e, ReflectionEventMsg)
    ]
