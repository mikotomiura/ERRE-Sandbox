"""Integration tests for :class:`CognitionCycle.step`."""

from __future__ import annotations

import json
from random import Random
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition import CognitionCycle, CycleResult
from erre_sandbox.contracts.cognition_layers import IndividualLayerConfig
from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    ERREModeName,
    MemoryKind,
    MoveMsg,
    SemanticMemoryRecord,
    SpeechMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import PerceptionEvent, PersonaSpec, ZoneTransitionEvent


def _build_cycle(
    *,
    retriever: Retriever,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llm: OllamaChatClient,
) -> CognitionCycle:
    return CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=llm,
        rng=Random(0),
    )


async def test_step_happy_path_emits_envelopes(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    persona: PersonaSpec = make_persona_spec()
    agent: AgentState = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()  # returns DEFAULT_PLAN
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    assert isinstance(result, CycleResult)
    assert not result.llm_fell_back
    kinds = [e.kind for e in result.envelopes]
    assert "agent_update" in kinds
    assert "speech" in kinds
    assert "move" in kinds
    assert "animation" in kinds

    # AgentUpdateMsg must always be present and tick bumped.
    agent_update = next(e for e in result.envelopes if isinstance(e, AgentUpdateMsg))
    assert agent_update.agent_state.tick == agent.tick + 1


async def test_step_writes_episodic_memory(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
        assert len(result.new_memory_ids) == 1
        stored = await cognition_store.list_by_agent(
            agent_id="a_kant_001",
            kind=MemoryKind.EPISODIC,
        )
        assert len(stored) == 1
    finally:
        await embedding.close()
        await llm.close()


async def test_step_falls_back_on_ollama_error(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    import httpx

    embedding = make_embedding_client()
    llm = make_chat_client(raise_exc=httpx.ConnectError("no route"))
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    assert result.llm_fell_back
    kinds = [e.kind for e in result.envelopes]
    assert kinds == ["agent_update"]


async def test_step_falls_back_on_malformed_llm_output(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    embedding = make_embedding_client()
    llm = make_chat_client(content="I cannot produce JSON right now.")
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    assert result.llm_fell_back
    assert len(result.envelopes) == 1
    assert isinstance(result.envelopes[0], AgentUpdateMsg)


async def test_step_applies_erre_sampling_override(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    embedding = make_embedding_client()
    captured: list[dict[str, Any]] = []
    llm = make_chat_client(captured=captured)
    persona: PersonaSpec = make_persona_spec(
        default_sampling={"temperature": 0.6, "top_p": 0.85, "repeat_penalty": 1.12},
    )
    agent: AgentState = make_agent_state(
        erre={
            "name": ERREModeName.PERIPATETIC.value,
            "entered_at_tick": 0,
            # peripatetic overrides per persona-erre §ルール 2.
            "sampling_overrides": {
                "temperature": 0.3,
                "top_p": 0.05,
                "repeat_penalty": -0.1,
            },
        },
        position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
    )
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    assert captured, "LLM was never invoked"
    options = captured[0]["options"]
    # 0.6 + 0.3 = 0.9 (within the clamp band).
    assert options["temperature"] == pytest.approx(0.9)
    assert options["top_p"] == pytest.approx(0.9)


async def test_step_detects_reflection_trigger_on_peripatos_entry(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    zone_entry_event: ZoneTransitionEvent,
) -> None:
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [zone_entry_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    assert result.reflection_triggered is True


async def test_step_advances_physical_even_on_fallback(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Physical decays with time even if the LLM call fails."""
    import httpx

    embedding = make_embedding_client()
    llm = make_chat_client(raise_exc=httpx.ConnectError("fail"))
    prev = make_agent_state(
        physical={"mood_baseline": 0.8},
    )
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(prev, make_persona_spec(), [])
    finally:
        await embedding.close()
        await llm.close()

    assert result.llm_fell_back
    assert result.agent_state.physical.mood_baseline < 0.8


async def test_move_msg_targets_destination_zone(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    embedding = make_embedding_client()
    # DEFAULT_PLAN destination_zone = "peripatos"
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    move = next(e for e in result.envelopes if isinstance(e, MoveMsg))
    assert move.target.zone is Zone.PERIPATOS
    assert move.speed == CognitionCycle.DEFAULT_DESTINATION_SPEED


async def test_speech_msg_carries_utterance(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    custom = {
        "thought": "quiet thought",
        "utterance": "こんにちは",
        "destination_zone": None,
        "animation": None,
        "valence_delta": 0.0,
        "arousal_delta": 0.0,
        "motivation_delta": 0.0,
        "importance_hint": 0.5,
    }
    embedding = make_embedding_client()
    llm = make_chat_client(content=json.dumps(custom))
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    speech = next(e for e in result.envelopes if isinstance(e, SpeechMsg))
    assert speech.utterance == "こんにちは"
    # No Move/Animation envelopes this time.
    assert not any(e.kind == "move" for e in result.envelopes)
    assert not any(e.kind == "animation" for e in result.envelopes)


async def test_step_continues_on_embedding_unavailable(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[..., EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """Embedding outage → memory is stored without a vector, cycle completes."""
    import httpx

    embedding = make_embedding_client(raise_exc=httpx.ConnectError("embed down"))
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            make_persona_spec(),
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    # Memory was still written (without a vector).
    assert len(result.new_memory_ids) == 1
    stored = await cognition_store.list_by_agent(
        agent_id="a_kant_001",
        kind=MemoryKind.EPISODIC,
    )
    assert len(stored) == 1
    # LLM path still ran — embedding failure is not a fallback trigger.
    assert not result.llm_fell_back


# ---------- M10-B individual layer wiring (DA-M10B-5/9) ------------------


def _user_message(captured: list[dict[str, Any]]) -> str:
    """Extract the user-role message content from a captured chat request."""
    body = captured[0]
    return next(m["content"] for m in body["messages"] if m["role"] == "user")


async def test_individual_layer_off_omits_world_model_section(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """Flag off (default): the USER prompt carries no held-world-model section."""
    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        await cycle.step(make_agent_state(), make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert "Held world-model entries" not in _user_message(captured)


async def test_individual_layer_on_injects_world_model_section(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """Flag on + promoted beliefs + bonds → the section is injected into USER."""
    # Two promoted dyads (distinct zones) so both env and self can rise.
    await cognition_store.upsert_semantic(
        SemanticMemoryRecord(
            id="belief_a_kant_001__nietzsche",
            agent_id="a_kant_001",
            summary="belief about nietzsche",
            belief_kind="clash",
            confidence=0.8,
        ),
    )
    await cognition_store.upsert_semantic(
        SemanticMemoryRecord(
            id="belief_a_kant_001__rikyu",
            agent_id="a_kant_001",
            summary="belief about rikyu",
            belief_kind="trust",
            confidence=0.7,
        ),
    )
    agent = make_agent_state(
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
    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        await cycle.step(agent, make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    user = _user_message(captured)
    assert "Held world-model entries:" in user
    # At least one env entry from the promoted dyads' zones is present.
    assert "[env/agora]" in user or "[env/chashitsu]" in user


# ---------- M10-C: hint apply + write-back through the cycle ----------------


async def _seed_two_dyads(store: MemoryStore) -> None:
    await store.upsert_semantic(
        SemanticMemoryRecord(
            id="belief_a_kant_001__nietzsche",
            agent_id="a_kant_001",
            summary="belief about nietzsche",
            belief_kind="clash",
            confidence=0.8,
        ),
    )
    await store.upsert_semantic(
        SemanticMemoryRecord(
            id="belief_a_kant_001__rikyu",
            agent_id="a_kant_001",
            summary="belief about rikyu",
            belief_kind="trust",
            confidence=0.7,
        ),
    )


def _agent_two_bonds(make_agent_state) -> AgentState:
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


_HINT_PLAN = {
    "thought": "agora clashes feel sharper than my model says",
    "utterance": None,
    "destination_zone": None,
    "animation": None,
    "valence_delta": 0.0,
    "arousal_delta": 0.0,
    "motivation_delta": 0.0,
    "importance_hint": 0.5,
    "world_model_update_hint": {
        "axis": "env",
        "key": "agora",
        "direction": "strengthen",
        "cited_memory_ids": ["belief_a_kant_001__nietzsche"],
    },
}


def _env_agora(result: CycleResult):
    runtime = result.world_model_runtime
    assert runtime is not None
    return next(
        e for e in runtime.modulated.entries if (e.axis, e.key) == ("env", "agora")
    )


async def test_flag_on_valid_hint_nudges_and_writes_back(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """A verified hint nudges its entry and the new SWM is carried on CycleResult."""
    await _seed_two_dyads(cognition_store)
    agent = _agent_two_bonds(make_agent_state)
    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(content=json.dumps(_HINT_PLAN), captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        result = await cycle.step(agent, make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    # The prompt actually exposed the entry + its belief citation + update schema.
    user = _user_message(captured)
    assert "[env/agora]" in user
    assert "cite=belief_a_kant_001__nietzsche" in user
    assert "world_model_update_hint" in user
    # floor value is -0.70; strengthen nudges magnitude by VALUE_STEP (0.05).
    assert _env_agora(result).value == pytest.approx(-0.75)


async def test_flag_on_saturation_snapshot_is_pre_nudge(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """world_model_saturation captures the reconciled SWM BEFORE the hint nudge.

    Saturation ADR section 2.1 (Codex LOW-2): the probe must observe the
    post-reconcile, **pre-nudge** value, never the post-hint carry-out (which can
    sit one step past the cap). On the first tick ``reconcile(None, floor) == floor``
    so env/agora reads the floor -0.70 in the snapshot, while the adopted hint nudges
    the carried-out runtime to -0.75 — the two must differ.
    """
    await _seed_two_dyads(cognition_store)
    agent = _agent_two_bonds(make_agent_state)
    embedding = make_embedding_client()
    llm = make_chat_client(content=json.dumps(_HINT_PLAN))
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        result = await cycle.step(agent, make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    # Post-hint carry-out is nudged to -0.75 (sibling test verifies this path).
    assert _env_agora(result).value == pytest.approx(-0.75)
    saturation = result.world_model_saturation
    assert saturation is not None
    sat_entry = next(
        e for e in saturation.modulated.entries if (e.axis, e.key) == ("env", "agora")
    )
    # The snapshot is the pre-nudge reconciled value (== floor on tick 1), NOT -0.75.
    assert sat_entry.value == pytest.approx(-0.70)
    assert sat_entry.value != pytest.approx(_env_agora(result).value)


async def test_flag_on_modulation_persists_across_ticks(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """The nudge survives a second tick whose LLM proposes no hint (evidence held)."""
    await _seed_two_dyads(cognition_store)
    agent = _agent_two_bonds(make_agent_state)
    embedding = make_embedding_client()
    llm_with_hint = make_chat_client(content=json.dumps(_HINT_PLAN))
    llm_no_hint = make_chat_client()  # DEFAULT_PLAN, no world_model_update_hint
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm_with_hint,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        first = await cycle.step(agent, make_persona_spec(), [perception_event])
        assert _env_agora(first).value == pytest.approx(-0.75)
        # Second tick: carry the runtime back in; no new hint this turn.
        cycle_no_hint = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm_no_hint,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        second = await cycle_no_hint.step(
            first.agent_state,
            make_persona_spec(),
            [perception_event],
            world_model_runtime=first.world_model_runtime,
        )
    finally:
        await embedding.close()
        await llm_with_hint.close()
        await llm_no_hint.close()
    # Evidence unchanged ⇒ the modulation is carried, not reset to the floor.
    assert _env_agora(second).value == pytest.approx(-0.75)


async def test_flag_on_fallback_preserves_world_model(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """A flag-on LLM outage returns the pre-LLM reconciled SWM, never None (MED-2)."""
    import httpx

    await _seed_two_dyads(cognition_store)
    agent = _agent_two_bonds(make_agent_state)
    embedding = make_embedding_client()
    llm = make_chat_client(raise_exc=httpx.ConnectError("llm down"))
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            individual_layer=IndividualLayerConfig(enabled=True),
        )
        result = await cycle.step(agent, make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.llm_fell_back is True
    assert result.world_model_runtime is not None
    # The reconciled floor is present (an env entry from the promoted dyads).
    keys = {(e.axis, e.key) for e in result.world_model_runtime.modulated.entries}
    assert ("env", "agora") in keys


async def test_flag_off_leaves_world_model_runtime_none(
    make_agent_state,
    make_persona_spec,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """Flag off: no world-model state is produced (the layer is inert)."""
    await _seed_two_dyads(cognition_store)
    agent = _agent_two_bonds(make_agent_state)
    embedding = make_embedding_client()
    llm = make_chat_client(content=json.dumps(_HINT_PLAN))
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(agent, make_persona_spec(), [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.world_model_runtime is None
