"""M7ζ-3: ``MoveMsg.speed`` scales with ``movement_speed_factor``.

The factor is consumed in ``CognitionCycle._build_envelopes`` so that the
same cognition pipeline emits per-persona movement velocities — Nietzsche's
1.625 m/s burst, Kant's 1.105 m/s deliberate pace, Rikyū's 0.910 m/s slow
gait — without any branching on ``persona_id`` in cognition code.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.schemas import MoveMsg

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import PerceptionEvent


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


@pytest.mark.parametrize(
    ("factor", "label"),
    [
        (0.85, "kant"),
        (1.25, "nietzsche"),
        (0.70, "rikyu"),
        (1.0, "default"),  # default_factory backward compat
    ],
)
async def test_move_speed_uses_behavior_profile_factor(
    factor: float,
    label: str,
    make_agent_state: Any,
    make_persona_spec: Any,
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    persona = make_persona_spec(
        behavior_profile={"movement_speed_factor": factor},
    )
    embedding = make_embedding_client()
    llm = make_chat_client()  # default plan emits a MoveMsg
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        result = await cycle.step(
            make_agent_state(),
            persona,
            [perception_event],
        )
    finally:
        await embedding.close()
        await llm.close()

    move = next(e for e in result.envelopes if isinstance(e, MoveMsg))
    expected = CognitionCycle.DEFAULT_DESTINATION_SPEED * factor
    assert move.speed == pytest.approx(expected), label
