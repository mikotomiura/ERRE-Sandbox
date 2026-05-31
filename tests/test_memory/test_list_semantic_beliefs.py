"""Tests for ``MemoryStore.list_semantic_beliefs`` (M10-B, DA-M10B-2).

This is the non-vector read path the world-model synthesis depends on: belief
promotions ship with an empty embedding and are therefore invisible to
``recall_semantic`` (a KNN over the vec table). ``list_semantic_beliefs`` must
return them anyway, scoped to the agent and sorted by id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.memory.store import MemoryStore
    from erre_sandbox.schemas import SemanticMemoryRecord


async def test_returns_only_belief_records(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
) -> None:
    """Belief rows are returned; plain reflection rows are excluded."""
    await store.upsert_semantic(
        make_semantic_record(record_id="belief_kant__x", belief_kind="trust"),
    )
    await store.upsert_semantic(
        make_semantic_record(record_id="reflection_1", belief_kind=None),
    )
    beliefs = await store.list_semantic_beliefs("kant")
    assert [b.id for b in beliefs] == ["belief_kant__x"]
    assert beliefs[0].belief_kind == "trust"


async def test_visible_without_embedding(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """A belief with an empty embedding is invisible to recall_semantic but
    visible here (the whole point of the method)."""
    await store.upsert_semantic(
        make_semantic_record(
            record_id="belief_kant__y",
            belief_kind="clash",
            embedding=[],
        ),
    )
    assert await store.recall_semantic("kant", unit_embedding, k=5) == []
    beliefs = await store.list_semantic_beliefs("kant")
    assert [b.id for b in beliefs] == ["belief_kant__y"]


async def test_excludes_foreign_agent(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
) -> None:
    await store.upsert_semantic(
        make_semantic_record(
            record_id="belief_kant__a",
            agent_id="kant",
            belief_kind="trust",
        ),
    )
    await store.upsert_semantic(
        make_semantic_record(
            record_id="belief_nietzsche__a",
            agent_id="nietzsche",
            belief_kind="clash",
        ),
    )
    kant = await store.list_semantic_beliefs("kant")
    assert [b.id for b in kant] == ["belief_kant__a"]


async def test_sorted_by_id(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
) -> None:
    for rid in ("belief_kant__c", "belief_kant__a", "belief_kant__b"):
        await store.upsert_semantic(
            make_semantic_record(record_id=rid, belief_kind="curious"),
        )
    beliefs = await store.list_semantic_beliefs("kant")
    assert [b.id for b in beliefs] == [
        "belief_kant__a",
        "belief_kant__b",
        "belief_kant__c",
    ]


async def test_empty_when_no_beliefs(store: MemoryStore) -> None:
    assert await store.list_semantic_beliefs("kant") == []
