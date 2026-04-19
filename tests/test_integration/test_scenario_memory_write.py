"""S_MEMORY_WRITE scenario — Layer B2 via MemoryStore + FakeEmbedder.

The walking path is not reached from the gateway: the scenario asserts
that the cognition cycle's *write pattern* (4 episodic + 1 semantic, with
``DOC_PREFIX`` applied at embed time) holds at the memory layer boundary.
The gateway passthrough is already covered by ``test_scenario_walking.py``
so replaying it here would be noise.

See ``.steering/20260419-m2-integration-e2e-execution/decisions.md`` D4
for the kind-distribution rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erre_sandbox.memory import DOC_PREFIX
from erre_sandbox.schemas import MemoryEntry, MemoryKind

if TYPE_CHECKING:
    from erre_sandbox.integration import Scenario
    from erre_sandbox.memory import MemoryStore

    from .conftest import FakeEmbedder, M2Logger

AGENT_ID = "a_kant_001"

# Decisions.md D4: the scenario's "4 episodic + 1 semantic" maps to this
# deterministic content list. Step order and text are fixed so the
# FakeEmbedder prefix check below has a stable expectation.
EPISODIC_CONTENT = (
    "雲が低く流れている",
    "風が右の頬に当たる",
    "Königsberg 大聖堂の鐘が鳴る",
    "すれ違った市民が軽く会釈した",
)
SEMANTIC_CONTENT = "Aesthetic judgment must be disinterested."


def test_s_memory_write_steps_are_three(memory_write_scenario: Scenario) -> None:
    """Sanity — scenario shape was not mutated between T19 design and execution."""
    assert len(memory_write_scenario.steps) == 3


@pytest.mark.asyncio
async def test_s_memory_write_writes_four_episodic_one_semantic(
    memory_store_with_fake_embedder: tuple[MemoryStore, FakeEmbedder],
    m2_logger: M2Logger,
) -> None:
    """Four ``EPISODIC`` + one ``SEMANTIC`` rows land in the store with embeddings."""
    store, embedder = memory_store_with_fake_embedder

    for i, content in enumerate(EPISODIC_CONTENT):
        embedding = await embedder.embed_document(content)
        entry = MemoryEntry(
            id=f"mem_ep_{i}",
            agent_id=AGENT_ID,
            kind=MemoryKind.EPISODIC,
            content=content,
            importance=0.5,
        )
        await store.add(entry, embedding=embedding)
        m2_logger.log(scenario="S_MEMORY_WRITE", kind="episodic", id=entry.id)

    sem_embedding = await embedder.embed_document(SEMANTIC_CONTENT)
    sem_entry = MemoryEntry(
        id="mem_sem_0",
        agent_id=AGENT_ID,
        kind=MemoryKind.SEMANTIC,
        content=SEMANTIC_CONTENT,
        importance=0.8,
    )
    await store.add(sem_entry, embedding=sem_embedding)
    m2_logger.log(scenario="S_MEMORY_WRITE", kind="semantic", id=sem_entry.id)

    episodic = await store.list_by_agent(AGENT_ID, MemoryKind.EPISODIC)
    semantic = await store.list_by_agent(AGENT_ID, MemoryKind.SEMANTIC)
    assert len(episodic) == 4
    assert len(semantic) == 1


@pytest.mark.asyncio
async def test_s_memory_write_embedding_prefix_applied(
    fake_embedder: FakeEmbedder,
) -> None:
    """Every stored document was embedded with :data:`DOC_PREFIX`.

    Mirrors the T10 D5 contract: the search_document / search_query
    asymmetry of nomic-embed-text-v1.5 is a correctness condition, not a
    hint — a silent regression would make prod retrieval useless.

    Uses only :class:`FakeEmbedder` (no store) — this test is purely
    about embed-time prefix behaviour, decoupled from persistence.
    """
    for content in EPISODIC_CONTENT:
        await fake_embedder.embed_document(content)
    await fake_embedder.embed_document(SEMANTIC_CONTENT)

    assert len(fake_embedder.last_docs) == 5
    for recorded in fake_embedder.last_docs:
        assert recorded.startswith(DOC_PREFIX), (
            f"document embed missing DOC_PREFIX: {recorded!r}"
        )
    # Queries never ran — ensure no accidental cross-wiring.
    assert fake_embedder.last_queries == []
