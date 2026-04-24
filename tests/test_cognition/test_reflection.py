"""Unit tests for :class:`~erre_sandbox.cognition.reflection.Reflector`.

Covers the four responsibilities of the reflector in isolation:

* :class:`ReflectionPolicy` evaluation of the three trigger conditions
* per-agent counter bookkeeping (isolation + reset-after-fire)
* the full happy-path pipeline (episodic → LLM → embedding → upsert)
* graceful-degrade paths (LLM outage / embedding outage / empty window)

All paths use ``httpx.MockTransport``-backed clients and an in-memory
:class:`MemoryStore`, so the suite never touches a real Ollama server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CognitionCycle, ReflectionPolicy, Reflector
from erre_sandbox.cognition.reflection import build_reflection_messages
from erre_sandbox.inference import OllamaUnavailableError
from erre_sandbox.memory import EmbeddingUnavailableError
from erre_sandbox.schemas import (
    MemoryEntry,
    MemoryKind,
    ReflectionEvent,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore


# ---------------------------------------------------------------------------
# ReflectionPolicy — pure, no I/O
# ---------------------------------------------------------------------------


def test_policy_fires_when_counter_reaches_tick_interval() -> None:
    policy = ReflectionPolicy(tick_interval=3)
    assert not policy.should_fire(
        ticks_since_last=2,
        importance_sum=0.0,
        zone_entered=False,
    )
    assert policy.should_fire(
        ticks_since_last=3,
        importance_sum=0.0,
        zone_entered=False,
    )


def test_policy_fires_on_importance_threshold() -> None:
    policy = ReflectionPolicy(tick_interval=99, importance_threshold=1.5)
    assert policy.should_fire(
        ticks_since_last=1,
        importance_sum=1.51,
        zone_entered=False,
    )
    assert not policy.should_fire(
        ticks_since_last=1,
        importance_sum=1.5,
        zone_entered=False,
    )


def test_policy_fires_on_zone_entry() -> None:
    policy = ReflectionPolicy(tick_interval=99, importance_threshold=99.0)
    assert policy.should_fire(
        ticks_since_last=1,
        importance_sum=0.0,
        zone_entered=True,
    )


def test_policy_does_not_fire_when_all_triggers_inactive() -> None:
    policy = ReflectionPolicy(tick_interval=10)
    assert not policy.should_fire(
        ticks_since_last=1,
        importance_sum=0.0,
        zone_entered=False,
    )


# ---------------------------------------------------------------------------
# Reflector counters
# ---------------------------------------------------------------------------


def test_reflector_counter_isolates_per_agent(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
) -> None:
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        reflector = Reflector(store=cognition_store, embedding=embedding, llm=llm)
        reflector.record_tick("a")
        reflector.record_tick("a")
        assert reflector.record_tick("a") == 3
        assert reflector.record_tick("b") == 1
        reflector.reset_counter("a")
        assert reflector.record_tick("a") == 1
    finally:
        # No async work happened — we still need to close the httpx clients
        # but since the test is sync, rely on the module-level teardown
        # implicit in pytest-anyio. For determinism, leave them open; the
        # MockTransport has no real sockets.
        pass


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def _seed_episodic(
    store: MemoryStore,
    agent_id: str,
    *,
    count: int = 3,
) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        entry = MemoryEntry(
            id=f"e{i}",
            agent_id=agent_id,
            kind=MemoryKind.EPISODIC,
            content=f"episodic memory #{i}",
            importance=0.5,
            created_at=datetime.now(tz=UTC),
            source_observation_id=None,
        )
        await store.add(entry, None)
        ids.append(entry.id)
    return ids


async def test_reflector_persists_semantic_memory_on_success(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    ids = await _seed_episodic(cognition_store, agent.agent_id, count=2)
    embedding = make_embedding_client()
    llm = make_chat_client(content="今日は歩きながら批判哲学の萌芽を感じた。")
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert isinstance(event, ReflectionEvent)
    assert event.agent_id == agent.agent_id
    assert event.summary_text == "今日は歩きながら批判哲学の萌芽を感じた。"
    assert set(event.src_episodic_ids) == set(ids)


async def test_reflector_stored_record_is_recallable(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=2)
    embedding = make_embedding_client()
    llm = make_chat_client(content="summary paragraph")
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
        assert event is not None
        # The mock embedding returns [0.01]*768 for any input, so a query
        # with the same vector must surface the stored row at distance 0.
        q = [0.01] * 768
        hits = await cognition_store.recall_semantic(agent.agent_id, q, k=5)
    finally:
        await embedding.close()
        await llm.close()

    assert hits, "recall_semantic returned no rows for just-stored reflection"
    top_record, _distance = hits[0]
    assert top_record.summary == "summary paragraph"
    assert top_record.origin_reflection_id is not None


async def test_reflector_truncates_oversized_llm_output(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    """Security guard: the LLM may ignore the ≤200 char prompt contract."""
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    huge = "x" * 10_000
    embedding = make_embedding_client()
    llm = make_chat_client(content=huge)
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert event is not None
    # Truncated to the module-private cap; use 1000 as a safe upper bound.
    assert len(event.summary_text) <= 1000
    assert len(event.summary_text) < len(huge)


async def test_reflector_resets_counter_after_fire(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    embedding = make_embedding_client()
    llm = make_chat_client(content="ok")
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
        # After a successful fire the counter should be back at zero, so
        # the very next call with the same policy would still require one
        # more tick before firing again.
        assert reflector._ticks_since_last[agent.agent_id] == 0
    finally:
        await embedding.close()
        await llm.close()


# ---------------------------------------------------------------------------
# Failure / degrade paths
# ---------------------------------------------------------------------------


async def test_reflector_skips_when_no_episodic_memories(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    # deliberately NOT seeding any episodic rows
    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert event is None
    assert not captured, "LLM must not be called with an empty episodic window"


async def test_reflector_returns_none_on_ollama_unavailable(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    embedding = make_embedding_client()
    llm = make_chat_client(raise_exc=OllamaUnavailableError("down"))
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert event is None
    # Counter must NOT reset on failure — the next tick should still
    # exceed the interval and retry promptly.
    assert reflector._ticks_since_last[agent.agent_id] >= 1


async def test_reflector_stores_row_without_embedding_on_embed_outage(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    embedding = make_embedding_client(raise_exc=EmbeddingUnavailableError("down"))
    llm = make_chat_client(content="summary")
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert isinstance(event, ReflectionEvent)
    assert event.summary_text == "summary"
    # The row exists, but has no embedding, so it must not be returned by
    # recall_semantic (per #3 D7: empty-embedding rows are unrecallable).
    q = [0.01] * 768
    hits = await cognition_store.recall_semantic(agent.agent_id, q, k=5)
    assert hits == []


# ---------------------------------------------------------------------------
# Policy wiring via Observations
# ---------------------------------------------------------------------------


async def test_reflector_fires_on_zone_entry_observation(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    """The zone-entry observation path flows through ``should_fire``."""
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    zone_event = ZoneTransitionEvent(
        tick=agent.tick,
        agent_id=agent.agent_id,
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )
    embedding = make_embedding_client()
    llm = make_chat_client(content="zone-triggered reflection")
    try:
        # A policy that would never fire on tick / importance alone —
        # only the zone entry can get this off the ground.
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=999, importance_threshold=999.0),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[zone_event],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert isinstance(event, ReflectionEvent)
    assert event.summary_text == "zone-triggered reflection"


async def test_reflector_declines_when_policy_rejects(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()
    await _seed_episodic(cognition_store, agent.agent_id, count=1)
    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=999, importance_threshold=999.0),
        )
        event = await reflector.maybe_reflect(
            agent_state=agent,
            persona=persona,
            observations=[],
            importance_sum=0.0,
        )
    finally:
        await embedding.close()
        await llm.close()

    assert event is None
    assert not captured, "Policy-declined reflections must not call the LLM"


# ---------------------------------------------------------------------------
# CycleResult wiring — end-to-end via CognitionCycle
# ---------------------------------------------------------------------------


async def test_cycle_exposes_reflection_event_in_result(
    cognition_store: MemoryStore,
    cognition_retriever: Any,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
    perception_event: Any,
) -> None:
    """End-to-end: CognitionCycle.step must surface ReflectionEvent."""
    agent = make_agent_state()
    persona = make_persona_spec()
    embedding = make_embedding_client()
    # The default mock plan is valid JSON for the action step; the
    # reflection LLM call receives the same handler and just stores the
    # JSON string verbatim as its summary paragraph. (We never parse it.)
    llm = make_chat_client()
    try:
        reflector = Reflector(
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            policy=ReflectionPolicy(tick_interval=1),
        )
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            reflector=reflector,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    # Action LLM parsing succeeded, so fall-back flag is False AND the
    # reflector fired (tick_interval=1).
    assert not result.llm_fell_back
    assert result.reflection_event is not None
    assert result.reflection_event.agent_id == agent.agent_id


async def test_cycle_default_reflector_exists_and_fires(
    cognition_store: MemoryStore,
    cognition_retriever: Any,
    make_embedding_client: Callable[..., EmbeddingClient],
    make_chat_client: Callable[..., OllamaChatClient],
    make_agent_state: Any,
    make_persona_spec: Any,
    perception_event: Any,
) -> None:
    """No explicit reflector — the default one still works (interval=10)."""
    # default tick_interval=10 and no zone/importance, so no reflection fires
    agent = make_agent_state()
    persona = make_persona_spec()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    # Default policy requires 10 ticks; this is tick #1, so no reflection.
    assert result.reflection_event is None


# ---------------------------------------------------------------------------
# Language hint (M7 V) — reflection must speak Japanese, mirroring dialog_turn
# ---------------------------------------------------------------------------


def test_reflection_system_prompt_includes_japanese_hint_for_kant(
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    """Kant reflection must append the Japanese language hint.

    Mirrors the ``_DIALOG_LANG_HINT`` contract in ``integration/dialog_turn.py``
    (PR #68). Without this, LATEST REFLECTION appears in English on the
    researcher's screen despite speech/dialog being Japanese.
    """
    persona = make_persona_spec(persona_id="kant")
    agent = make_agent_state()
    messages = build_reflection_messages(persona, agent, episodic=[])
    system = messages[0].content
    assert "日本語" in system, (
        "reflection system prompt must contain Japanese instruction"
    )
    assert "記述せよ" in system, (
        "reflection hint uses 「記述せよ」 (written monologue), not 「応答せよ」"
    )


def test_reflection_system_prompt_hint_varies_by_persona(
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    """Each known persona gets a distinct lang hint (same pattern as dialog)."""
    agent = make_agent_state()
    kant_system = build_reflection_messages(
        make_persona_spec(persona_id="kant"),
        agent,
        episodic=[],
    )[0].content
    rikyu_system = build_reflection_messages(
        make_persona_spec(persona_id="rikyu"),
        agent,
        episodic=[],
    )[0].content
    nietzsche_system = build_reflection_messages(
        make_persona_spec(persona_id="nietzsche"),
        agent,
        episodic=[],
    )[0].content
    # Each persona's hint references a distinct vocabulary register.
    assert "学術的" in kant_system
    assert "侘び寂び" in rikyu_system
    assert "アフォリスティック" in nietzsche_system


def test_reflection_system_prompt_no_hint_for_unknown_persona(
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    """Unknown persona ids must not raise and must not inject a hint."""
    persona = make_persona_spec(persona_id="unknown-persona")
    agent = make_agent_state()
    messages = build_reflection_messages(persona, agent, episodic=[])
    system = messages[0].content
    # English-only base prompt, no Japanese hint appended.
    assert "日本語" not in system
    assert "記述せよ" not in system
