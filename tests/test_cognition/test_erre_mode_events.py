"""Tests for ERREModeShiftEvent emission from the cognition cycle (M6-A-1).

When the FSM returns a new mode, :meth:`CognitionCycle._maybe_apply_erre_fsm`
must now emit an :class:`~erre_sandbox.schemas.ERREModeShiftEvent` and have
:meth:`CognitionCycle.step` append it to the tick's observation stream so
Steps 4-10 (retrieve / prompt / reflection) see the mode-shift signal
alongside the inputs that caused it. This complements the existing tests in
``test_cycle_erre_fsm.py`` which cover the *state* transition; this file
covers the *observability* hook.

The tests use a ``captured`` list wired into the MockTransport-backed
:class:`OllamaChatClient` so we can inspect the exact user prompt emitted to
the LLM and confirm the shift event is rendered by
:func:`~erre_sandbox.cognition.prompting.build_user_prompt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.cycle import _infer_shift_reason
from erre_sandbox.schemas import (
    ERREModeName,
    InternalEvent,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import (
        Observation,
        PersonaSpec,
    )


# ---------- Fake policy (mirrors test_cycle_erre_fsm.py) ----------


@dataclass
class _FixedPolicy:
    """Policy that always returns ``next_mode_return`` when invoked."""

    next_mode_return: ERREModeName | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def next_mode(
        self,
        *,
        current: ERREModeName,
        zone: Zone,
        observations: Sequence[Observation],  # noqa: ARG002 — Protocol contract
        tick: int,
    ) -> ERREModeName | None:
        self.calls.append(
            {"current": current, "zone": zone, "tick": tick},
        )
        return self.next_mode_return


def _extract_user_prompt(captured: list[dict[str, Any]]) -> str:
    """Pull the user-role message content out of the first chat request.

    When a tick lands in a reflection zone (peripatos / chashitsu) the
    cycle issues two LLM calls — the main cognition step (Step 5) first,
    then the reflection distillation (Step 10). We want the main-cycle
    prompt, which is always ``captured[0]``.
    """
    assert captured, "no chat request captured"
    messages = captured[0]["messages"]
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert user_msgs, "expected a user-role message in the chat request"
    return user_msgs[-1]["content"]


# ---------- Tests: shift event flows into the LLM prompt ----------


async def test_zone_transition_emits_shift_event_into_prompt(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Zone transition → FSM picks new mode → shift event rendered in prompt."""
    policy = _FixedPolicy(next_mode_return=ERREModeName.PERIPATETIC)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()  # default mode DEEP_WORK
    assert agent.erre.name == ERREModeName.DEEP_WORK

    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)

    zone_event = ZoneTransitionEvent(
        tick=agent.tick,
        agent_id=agent.agent_id,
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )

    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            erre_policy=policy,
        )
        result = await cycle.step(agent, persona, [zone_event])
    finally:
        await embedding.close()
        await llm.close()

    # State is updated (already covered by test_cycle_erre_fsm.py, kept here
    # as a sanity check that we didn't regress while touching the signature).
    assert result.agent_state.erre.name == ERREModeName.PERIPATETIC

    # M6-A-1 core contract: the prompt sent to the LLM contains the shift
    # event line so the model can self-explain "why I am now peripatetic".
    prompt = _extract_user_prompt(captured)
    assert "erre_mode_shift" in prompt
    assert "deep_work" in prompt  # previous mode
    assert "peripatetic" in prompt  # new mode


async def test_no_transition_emits_no_shift_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Policy returns None → no shift event in the prompt (regression guard)."""
    policy = _FixedPolicy(next_mode_return=None)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
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
            erre_policy=policy,
        )
        await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    prompt = _extract_user_prompt(captured)
    assert "erre_mode_shift" not in prompt


async def test_policy_returning_current_mode_emits_no_shift_event(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Protocol-violating "return current" is treated as a no-op — no event."""
    policy = _FixedPolicy(next_mode_return=ERREModeName.DEEP_WORK)  # == default
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    assert agent.erre.name == ERREModeName.DEEP_WORK  # sanity

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
            erre_policy=policy,
        )
        await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    prompt = _extract_user_prompt(captured)
    assert "erre_mode_shift" not in prompt


async def test_shift_event_upstream_observations_not_mutated(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Caller's observations list is never mutated by the cycle's shift append.

    The caller (T13 orchestrator) typically buffers observations per tick;
    silently mutating it would break the one-tick-per-call contract.
    """
    policy = _FixedPolicy(next_mode_return=ERREModeName.CHASHITSU)
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()

    zone_event = ZoneTransitionEvent(
        tick=agent.tick,
        agent_id=agent.agent_id,
        from_zone=Zone.STUDY,
        to_zone=Zone.CHASHITSU,
    )
    caller_list: list[Observation] = [zone_event]
    snapshot_ids = [id(caller_list), len(caller_list)]

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
        )
        await cycle.step(agent, persona, caller_list)
    finally:
        await embedding.close()
        await llm.close()

    # The caller's list identity and length are preserved.
    assert [id(caller_list), len(caller_list)] == snapshot_ids


# ---------- Tests: _infer_shift_reason helper ----------


@pytest.mark.parametrize(
    ("observations", "expected"),
    [
        pytest.param(
            [
                ZoneTransitionEvent(
                    tick=1,
                    agent_id="a",
                    from_zone=Zone.STUDY,
                    to_zone=Zone.PERIPATOS,
                ),
            ],
            "zone",
            id="zone_transition",
        ),
        pytest.param(
            [
                InternalEvent(
                    tick=1,
                    agent_id="a",
                    content="fatigue:high",
                    importance_hint=0.8,
                ),
            ],
            "fatigue",
            id="internal_fatigue",
        ),
        pytest.param(
            [
                InternalEvent(
                    tick=1,
                    agent_id="a",
                    content="shuhari_promote:ha",
                    importance_hint=0.6,
                ),
            ],
            "scheduled",
            id="internal_shuhari",
        ),
        pytest.param(
            [],
            "external",
            id="empty_fallback",
        ),
        pytest.param(
            [
                InternalEvent(
                    tick=1,
                    agent_id="a",
                    content="fatigue:high",
                    importance_hint=0.8,
                ),
                ZoneTransitionEvent(
                    tick=1,
                    agent_id="a",
                    from_zone=Zone.STUDY,
                    to_zone=Zone.PERIPATOS,
                ),
            ],
            "zone",
            id="latest_wins_zone_over_fatigue",
        ),
    ],
)
def test_infer_shift_reason(
    observations: Sequence[Observation],
    expected: str,
) -> None:
    assert _infer_shift_reason(observations) == expected
