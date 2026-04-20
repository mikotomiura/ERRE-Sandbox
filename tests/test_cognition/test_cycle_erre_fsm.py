"""Integration tests for the ERRE mode FSM hook in :class:`CognitionCycle`.

Covers the three observable behaviours of the optional ``erre_policy``
dependency injected into :class:`CognitionCycle` (M5 `m5-world-zone-triggers`):

* **No policy (default)**: ``agent_state.erre`` is unchanged across a tick
  — this preserves pre-M5 behaviour for boots that have not wired up FSM.
* **Policy returns a new mode**: ``result.agent_state.erre.name`` reflects
  the FSM's decision and the ``entered_at_tick`` is reset to the new tick.
* **Policy returns ``None``**: ``agent_state.erre`` is carried through
  unchanged (the FSM explicitly declined to transition).

A minimal in-test fake Policy is used rather than the full
:class:`DefaultERREModePolicy` so tests stay behaviour-focused and don't
duplicate ``tests/test_erre/test_fsm.py``'s coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.schemas import (
    ERREModeName,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import (
        Observation,
        PerceptionEvent,
        PersonaSpec,
    )


# ---------- Fake policy for test isolation ----------


@dataclass
class _RecordingFakePolicy:
    """Policy that returns a fixed next mode and records its inputs.

    ``next_mode_return`` None means "keep current"; anything else forces
    the FSM path to adopt that mode on every call.
    """

    next_mode_return: ERREModeName | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def next_mode(
        self,
        *,
        current: ERREModeName,
        zone: Zone,
        observations: Sequence[Observation],
        tick: int,
    ) -> ERREModeName | None:
        self.calls.append(
            {
                "current": current,
                "zone": zone,
                "observations": list(observations),
                "tick": tick,
            },
        )
        return self.next_mode_return


# ---------- Helpers ----------


def _build_cycle_with_policy(
    *,
    retriever: Retriever,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llm: OllamaChatClient,
    erre_policy: _RecordingFakePolicy | None,
) -> CognitionCycle:
    return CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=llm,
        rng=Random(0),
        erre_policy=erre_policy,
    )


# ---------- Tests ----------


async def test_cycle_without_erre_policy_keeps_mode_static(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle_with_policy(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            erre_policy=None,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.agent_state.erre.name == agent.erre.name
    assert result.agent_state.erre.entered_at_tick == agent.erre.entered_at_tick


async def test_cycle_erre_policy_updates_agent_state(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    policy = _RecordingFakePolicy(next_mode_return=ERREModeName.CHASHITSU)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()  # default ERREMode is DEEP_WORK
    assert agent.erre.name == ERREModeName.DEEP_WORK  # sanity
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle_with_policy(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            erre_policy=policy,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.agent_state.erre.name == ERREModeName.CHASHITSU
    # entered_at_tick should equal the tick the FSM observed (pre-step tick)
    assert result.agent_state.erre.entered_at_tick == agent.tick
    assert len(policy.calls) == 1
    recorded = policy.calls[0]
    assert recorded["current"] == ERREModeName.DEEP_WORK
    assert recorded["zone"] == agent.position.zone
    assert recorded["tick"] == agent.tick


async def test_cycle_erre_policy_none_return_leaves_mode_unchanged(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    policy = _RecordingFakePolicy(next_mode_return=None)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle_with_policy(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            erre_policy=policy,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.agent_state.erre.name == agent.erre.name
    assert result.agent_state.erre.entered_at_tick == agent.erre.entered_at_tick
    assert len(policy.calls) == 1  # policy is still consulted even if it returns None


async def test_cycle_erre_policy_returning_current_is_treated_as_noop(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    # A misbehaving policy that violates the "must differ from current"
    # Protocol contract by returning the current mode. The cycle must not
    # mark a fresh transition (no bumped entered_at_tick).
    policy = _RecordingFakePolicy(next_mode_return=ERREModeName.DEEP_WORK)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()  # default ERREMode is DEEP_WORK
    assert agent.erre.name == ERREModeName.DEEP_WORK
    original_entered_at = agent.erre.entered_at_tick
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle_with_policy(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            erre_policy=policy,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert result.agent_state.erre.name == ERREModeName.DEEP_WORK
    assert result.agent_state.erre.entered_at_tick == original_entered_at


async def test_cycle_erre_policy_receives_step_observations(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    # Record-only policy to verify the FSM sees the step's observations verbatim.
    policy = _RecordingFakePolicy(next_mode_return=None)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle_with_policy(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            erre_policy=policy,
        )
        await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert len(policy.calls) == 1
    assert policy.calls[0]["observations"] == [perception_event]
