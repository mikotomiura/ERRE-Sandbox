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
from erre_sandbox.erre import SAMPLING_DELTA_BY_MODE
from erre_sandbox.schemas import (
    ERREModeName,
    SamplingDelta,
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


async def test_cycle_erre_policy_populates_sampling_overrides_from_table(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """FSM transition must also update sampling_overrides from the table.

    Without this wiring the FSM flips ``erre.name`` but leaves the
    ``SamplingDelta`` at its zero default, so ``compose_sampling`` keeps
    returning the persona's base values and mode changes become a
    no-op for LLM sampling — which defeats the whole M5
    sampling-override-live milestone.
    """
    policy = _RecordingFakePolicy(next_mode_return=ERREModeName.CHASHITSU)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()  # default ERREMode is DEEP_WORK with zero delta
    assert agent.erre.sampling_overrides == SamplingDelta()  # sanity
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
    expected = SAMPLING_DELTA_BY_MODE[ERREModeName.CHASHITSU]
    assert result.agent_state.erre.name == ERREModeName.CHASHITSU
    assert result.agent_state.erre.sampling_overrides == expected
    # Explicit drift check: the table must not have mutated to zero by
    # accident (would make the above equality trivially true).
    assert result.agent_state.erre.sampling_overrides != SamplingDelta()


async def test_cycle_erre_policy_noop_preserves_sampling_overrides(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """The FSM's no-op paths must not touch sampling_overrides either.

    Complement to ``_returning_current_is_treated_as_noop``: both the
    ``None`` return and the ``candidate == current`` guard must leave
    the full ERREMode instance (including ``sampling_overrides``)
    byte-identical to the pre-step value.
    """
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
    assert result.agent_state.erre.sampling_overrides == agent.erre.sampling_overrides


# ---------------------------------------------------------------------------
# erre_sampling_deltas DI slot — testing-only isolation of the FSM from the
# production sampling table (the rollback flag that originally motivated
# this slot was removed in m5-cleanup-rollback-flags; the slot itself is
# retained because tests benefit from per-case injection without
# monkey-patching :data:`SAMPLING_DELTA_BY_MODE`).
# ---------------------------------------------------------------------------


async def test_cycle_erre_sampling_deltas_zero_table_keeps_overrides_empty(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """Zero-delta injected table => FSM name flips but sampling_overrides stay empty.

    Exercises the testing-only DI slot: the FSM is still consulted (so mode
    name transitions are recorded) but the delta lookup hits the injected
    zero table, so ``compose_sampling`` sees no overrides and the LLM call
    uses the persona's base sampling only. Load-bearing because it proves
    ``CognitionCycle`` honours the injected mapping rather than the module
    constant, which is what lets other tests pin an FSM transition under a
    deterministic sampling regime.
    """
    zero_table = {mode: SamplingDelta() for mode in ERREModeName}
    policy = _RecordingFakePolicy(next_mode_return=ERREModeName.CHASHITSU)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    assert agent.erre.name == ERREModeName.DEEP_WORK  # sanity
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            erre_policy=policy,
            erre_sampling_deltas=zero_table,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    # FSM transition name change DID happen.
    assert result.agent_state.erre.name == ERREModeName.CHASHITSU
    # But sampling_overrides stayed at the zero default because our
    # injected table has SamplingDelta() for every mode.
    assert result.agent_state.erre.sampling_overrides == SamplingDelta()
    # Drift guard: the production table would have produced a non-zero delta.
    assert SAMPLING_DELTA_BY_MODE[ERREModeName.CHASHITSU] != SamplingDelta()


async def test_cycle_erre_sampling_deltas_default_uses_production_table(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """`erre_sampling_deltas=None` default preserves production behaviour."""
    policy = _RecordingFakePolicy(next_mode_return=ERREModeName.CHASHITSU)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            erre_policy=policy,
            erre_sampling_deltas=None,
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert (
        result.agent_state.erre.sampling_overrides
        == SAMPLING_DELTA_BY_MODE[ERREModeName.CHASHITSU]
    )
