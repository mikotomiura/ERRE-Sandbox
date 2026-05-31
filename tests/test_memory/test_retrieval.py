"""Unit + integration tests for :mod:`erre_sandbox.memory.retrieval`.

Pure ``score`` invariants are TDD-mandatory (see ``test-standards`` §rule 7).
The :class:`Retriever` integration test uses an in-memory store and a
hand-crafted fake embedding client (no network).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import pytest

from erre_sandbox.memory.embedding import EmbeddingClient
from erre_sandbox.memory.retrieval import (
    DEFAULT_DECAY_LAMBDA,
    Retriever,
    cosine_similarity,
    score,
)
from erre_sandbox.schemas import MemoryKind

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.memory.store import MemoryStore
    from erre_sandbox.schemas import MemoryEntry


# ---------------------------------------------------------------------------
# score() pure-function invariants
# ---------------------------------------------------------------------------


def test_score_decays_over_time() -> None:
    fresh = score(importance=1.0, age_days=0.0, recall_count=0, cosine_sim=1.0)
    old = score(importance=1.0, age_days=30.0, recall_count=0, cosine_sim=1.0)
    assert fresh > old


def test_score_recall_count_boosts() -> None:
    no_recall = score(importance=1.0, age_days=1.0, recall_count=0, cosine_sim=1.0)
    recalled = score(importance=1.0, age_days=1.0, recall_count=5, cosine_sim=1.0)
    assert recalled > no_recall


def test_score_scales_linearly_with_importance() -> None:
    low = score(importance=0.2, age_days=0.0, recall_count=0, cosine_sim=1.0)
    high = score(importance=1.0, age_days=0.0, recall_count=0, cosine_sim=1.0)
    assert high == pytest.approx(low * 5.0)


def test_score_zero_cosine_zeros_out() -> None:
    assert score(importance=1.0, age_days=0.0, recall_count=99, cosine_sim=0.0) == 0.0


def test_score_half_life_approx_seven_days() -> None:
    # With lambda = 0.1, half-life = ln(2) / 0.1 ≈ 6.93 days.
    expected_halflife = math.log(2) / DEFAULT_DECAY_LAMBDA
    s_zero = score(importance=1.0, age_days=0.0, recall_count=0, cosine_sim=1.0)
    s_half = score(
        importance=1.0,
        age_days=expected_halflife,
        recall_count=0,
        cosine_sim=1.0,
    )
    assert s_half == pytest.approx(s_zero * 0.5, rel=1e-6)


def test_cosine_similarity_orthogonal_is_zero() -> None:
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)


def test_cosine_similarity_identical_is_one() -> None:
    assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector_returns_zero() -> None:
    assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


# ---------------------------------------------------------------------------
# Retriever integration
# ---------------------------------------------------------------------------


class _FakeEmbeddingClient(EmbeddingClient):
    """Deterministic stand-in for Ollama in retrieval tests."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        # Bypass the real __init__ (which would open an httpx client) — we
        # only need the QUERY_PREFIX / DOC_PREFIX-aware public methods below.
        self.model = "fake"
        self.endpoint = "http://fake"
        self.dim = len(vector)

    async def embed(self, _text: str) -> list[float]:
        return list(self._vector)

    async def embed_query(self, _text: str) -> list[float]:
        return list(self._vector)

    async def embed_document(self, _text: str) -> list[float]:
        return list(self._vector)

    async def embed_many(
        self,
        texts: Sequence[str],
        *,
        kind: Literal["query", "document"],  # noqa: ARG002
    ) -> list[list[float]]:
        return [list(self._vector) for _ in texts]

    async def close(self) -> None:
        pass


def _doc_vec(index: int) -> list[float]:
    v = [0.0] * 768
    v[index] = 1.0
    return v


async def test_retrieve_prefers_semantically_closer(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    now = datetime.now(tz=UTC)
    close = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="close",
        importance=0.5,
        created_at=now,
    )
    far = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="far",
        importance=0.5,
        created_at=now,
    )
    # close's doc-vec matches the query exactly; far's is orthogonal.
    await store.add(close, embedding=_doc_vec(0))
    await store.add(far, embedding=_doc_vec(1))

    retriever = Retriever(store, _FakeEmbeddingClient(_doc_vec(0)))
    ranked = await retriever.retrieve("kant", "anything", k_agent=2, k_world=0)

    assert [r.entry.content for r in ranked] == ["close", "far"]
    assert ranked[0].cosine_sim > ranked[1].cosine_sim


async def test_retrieve_splits_agent_and_world_scope(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    now = datetime.now(tz=UTC)
    mine_a = make_entry(agent_id="kant", content="mine_a", created_at=now)
    mine_b = make_entry(agent_id="kant", content="mine_b", created_at=now)
    theirs = make_entry(agent_id="nietzsche", content="theirs", created_at=now)
    for e in (mine_a, mine_b, theirs):
        await store.add(e, embedding=_doc_vec(0))

    retriever = Retriever(store, _FakeEmbeddingClient(_doc_vec(0)))
    ranked = await retriever.retrieve("kant", "q", k_agent=5, k_world=5)

    kant_hits = [r for r in ranked if r.entry.agent_id == "kant"]
    nietzsche_hits = [r for r in ranked if r.entry.agent_id == "nietzsche"]
    assert {r.entry.id for r in kant_hits} == {mine_a.id, mine_b.id}
    assert {r.entry.id for r in nietzsche_hits} == {theirs.id}


async def test_retrieve_bumps_recall_count(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    entry = make_entry(agent_id="kant", kind=MemoryKind.EPISODIC)
    await store.add(entry, embedding=_doc_vec(0))

    retriever = Retriever(store, _FakeEmbeddingClient(_doc_vec(0)))
    await retriever.retrieve("kant", "q", k_agent=1, k_world=0)

    after = await store.get_by_id(entry.id)
    assert after is not None
    assert after.recall_count == 1
    assert after.last_recalled_at is not None


async def test_retrieve_limits_respected(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    now = datetime.now(tz=UTC)
    for i in range(5):
        e = make_entry(
            agent_id="kant",
            content=f"memory_{i}",
            created_at=now - timedelta(minutes=i),
        )
        await store.add(e, embedding=_doc_vec(i % 3))

    retriever = Retriever(store, _FakeEmbeddingClient(_doc_vec(0)))
    ranked = await retriever.retrieve("kant", "q", k_agent=2, k_world=0)
    assert len(ranked) == 2
