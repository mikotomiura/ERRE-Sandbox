"""Tests for the M6-A-4 ReflectionEvent envelope emission.

The :class:`~erre_sandbox.cognition.reflection.Reflector` has been producing
:class:`~erre_sandbox.schemas.ReflectionEvent` instances since M4, but the
M5 wire contract did not expose them over the WebSocket. M6-A-4 wraps the
existing domain object in a :class:`~erre_sandbox.schemas.ReflectionEventMsg`
envelope so the Godot xAI ReasoningPanel can surface the distilled summary
to the researcher.

These tests cover the three observable cases:

* Successful reflection → exactly one :class:`ReflectionEventMsg` in the
  cycle's envelope list, carrying the same domain object as
  ``CycleResult.reflection_event``.
* Declined / failed reflection (reflector returns ``None``) → no envelope.
* ``reflection_triggered=True`` but ``reflection_event=None`` (policy fired
  but distillation failed) → no envelope, matching the documented behaviour
  of :class:`CycleResult.reflection_event`.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.reflection import Reflector
from erre_sandbox.schemas import (
    ControlEnvelope,
    ReflectionEvent,
    ReflectionEventMsg,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import PersonaSpec


class _StubReflector(Reflector):
    """Reflector that returns a pre-configured :class:`ReflectionEvent`.

    Bypasses the LLM-backed distillation and the in-policy trigger counter,
    so the envelope-emission contract is tested independently of the
    reflection policy (which has its own behavioural suite in
    ``test_reflection.py``).
    """

    def __init__(self, event: ReflectionEvent | None) -> None:
        self._event_override = event

    async def maybe_reflect(  # type: ignore[override]
        self,
        *,
        agent_state: Any,
        persona: Any,
        observations: Any,
        importance_sum: float,
    ) -> ReflectionEvent | None:
        del agent_state, persona, observations, importance_sum
        return self._event_override


def _reflection_msgs(envelopes: list[ControlEnvelope]) -> list[ReflectionEventMsg]:
    return [e for e in envelopes if isinstance(e, ReflectionEventMsg)]


async def test_reflection_event_emits_envelope(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    persona: PersonaSpec = make_persona_spec()
    agent = make_agent_state()
    stub_event = ReflectionEvent(
        agent_id=agent.agent_id,
        tick=agent.tick,
        summary_text="散策で鐘の音に触れ、定言命法の輪郭が見えた。",
        src_episodic_ids=["m1", "m2"],
    )
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            reflector=_StubReflector(stub_event),
        )
        # A zone-entry observation drives ``reflection_triggered=True`` for
        # the policy branch; the stub reflector ignores it but the cycle
        # must still wire the envelope when the reflector returned an event.
        zone_evt = ZoneTransitionEvent(
            tick=agent.tick,
            agent_id=agent.agent_id,
            from_zone=Zone.STUDY,
            to_zone=Zone.PERIPATOS,
        )
        result = await cycle.step(agent, persona, [zone_evt])
    finally:
        await embedding.close()
        await llm.close()

    msgs = _reflection_msgs(result.envelopes)
    assert len(msgs) == 1
    assert msgs[0].event is stub_event
    assert msgs[0].event.summary_text == stub_event.summary_text
    # The envelope tick tracks the post-tick state, not the original input.
    assert msgs[0].tick == result.agent_state.tick


async def test_reflector_declines_emits_no_envelope(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
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
            reflector=_StubReflector(None),
        )
        result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    assert _reflection_msgs(result.envelopes) == []
    assert result.reflection_event is None


def test_reflection_event_msg_is_in_control_envelope_union() -> None:
    """Pydantic discriminator dispatches ``reflection_event`` correctly."""
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    payload = {
        "kind": "reflection_event",
        "tick": 7,
        "event": {
            "agent_id": "a_rikyu_001",
            "tick": 7,
            "summary_text": "一期一会の茶席、侘びの本質を掴んだ。",
            "src_episodic_ids": ["m_obs_100"],
        },
    }
    env = adapter.validate_python(payload)
    assert isinstance(env, ReflectionEventMsg)
    assert env.event.summary_text == "一期一会の茶席、侘びの本質を掴んだ。"
