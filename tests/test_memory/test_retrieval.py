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


# ---------------------------------------------------------------------------
# B-3: total order established BEFORE truncation (determinism hardening)
# ---------------------------------------------------------------------------
#
# The tie construction: a *fixed* ``now`` in the past plus ``created_at`` values
# that are all in the *future* means ``_age_days`` clamps every age to ``0.0``
# (``max(delta_s, 0)``), so the decay factor is exactly ``1.0`` for every entry.
# With a uniform embedding (cosine_sim identical) and equal importance /
# recall_count, every entry's ``strength`` is therefore bit-identical — a true
# equal-strength tie whose only differentiators are ``created_at`` and ``id``.

_FIXED_NOW = datetime(2020, 1, 1, tzinfo=UTC)
_UNIFORM_VEC = [0.1] * 768


def _tied_entry(
    make_entry: Callable[..., MemoryEntry],
    *,
    entry_id: str,
    agent_id: str,
    kind: MemoryKind,
    created_at: datetime,
) -> MemoryEntry:
    """A memory whose strength ties with every other ``_tied_entry``.

    ``created_at`` is in the future relative to ``_FIXED_NOW`` so the age clamps
    to 0 (equal decay); ``importance`` / ``recall_count`` are held constant.
    """
    e = make_entry(
        agent_id=agent_id,
        kind=kind,
        content=entry_id,
        importance=0.5,
        recall_count=0,
        created_at=created_at,
    )
    return e.model_copy(update={"id": entry_id})


async def test_rank_scope_total_order_before_truncation(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    """β-G1: equal-strength ties are ordered ``(-strength, created_at, id)``
    across the whole candidate pool *before* ``[:k_agent]`` truncation, and the
    result is deterministic (identical across two runs).
    """
    # 10 tied agent memories. ``created_at`` is duplicated in pairs (i // 2) so
    # BOTH sort keys are exercised: distinct created_at orders across pairs, and
    # within a pair the ``id`` breaks the tie. ``id`` runs opposite to insertion
    # order so a naive stable/insertion-order sort would give a different result.
    n = 10
    entries: list[MemoryEntry] = []
    for i in range(n):
        e = _tied_entry(
            make_entry,
            entry_id=f"mem-{n - 1 - i:02d}",  # id order opposite to insertion
            agent_id="kant",
            kind=MemoryKind.EPISODIC,
            created_at=_FIXED_NOW + timedelta(seconds=i // 2),
        )
        entries.append(e)
        await store.add(e, embedding=list(_UNIFORM_VEC))

    retriever = Retriever(
        store,
        _FakeEmbeddingClient(list(_UNIFORM_VEC)),
        now_factory=_FIXED_NOW,
    )

    # The full pool ordering (no truncation) must be the total order.
    q_vec = list(_UNIFORM_VEC)
    full = await retriever._rank_scope(  # pinning the internal ordering contract
        q_vec=q_vec,
        now=_FIXED_NOW,
        kinds=(MemoryKind.EPISODIC,),
        agent_id="kant",
        world=False,
    )
    # All strengths are exactly equal (a real tie), so ordering is by
    # (created_at, id). created_at is strictly increasing in insertion order.
    strengths = {r.strength for r in full}
    assert len(strengths) == 1, "test setup must produce a genuine strength tie"
    expected_order = sorted(
        entries,
        key=lambda e: (e.created_at, e.id),
    )
    assert [r.entry.id for r in full] == [e.id for e in expected_order]

    # k_agent (3) < candidates (10): the tie spans the truncation boundary.
    # The returned top-k must be the deterministic prefix of the total order.
    run1 = await retriever.retrieve(
        "kant", "q", k_agent=3, k_world=0, mark_recalled=False
    )
    run2 = await retriever.retrieve(
        "kant", "q", k_agent=3, k_world=0, mark_recalled=False
    )
    ids1 = [r.entry.id for r in run1]
    ids2 = [r.entry.id for r in run2]
    assert ids1 == [e.id for e in expected_order[:3]]
    assert ids1 == ids2  # byte-identical across two runs (deterministic)


async def test_rank_scope_candidate_pool_boundary(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    """β-G2: with ``candidates > limit_candidates`` the total order applies only
    within the candidate pool, and the pool is *per (kind, scope)* (not a flat
    cap) — pool-external equal-strength older memories are not surfaced.
    """
    limit = 3
    # --- per (kind, scope) pool: 5 episodic + 5 semantic for the agent, plus
    # 5 episodic for a *world* peer. Each (kind, scope) fetch caps at ``limit``.
    ep_agent: list[MemoryEntry] = []
    for i in range(5):
        e = _tied_entry(
            make_entry,
            entry_id=f"ep-agent-{i:02d}",
            agent_id="kant",
            kind=MemoryKind.EPISODIC,
            created_at=_FIXED_NOW + timedelta(seconds=i),
        )
        ep_agent.append(e)
        await store.add(e, embedding=list(_UNIFORM_VEC))

    sem_agent: list[MemoryEntry] = []
    for i in range(5):
        e = _tied_entry(
            make_entry,
            entry_id=f"sem-agent-{i:02d}",
            agent_id="kant",
            kind=MemoryKind.SEMANTIC,
            created_at=_FIXED_NOW + timedelta(seconds=i),
        )
        sem_agent.append(e)
        await store.add(e, embedding=list(_UNIFORM_VEC))

    ep_world: list[MemoryEntry] = []
    for i in range(5):
        e = _tied_entry(
            make_entry,
            entry_id=f"ep-world-{i:02d}",
            agent_id="nietzsche",
            kind=MemoryKind.EPISODIC,
            created_at=_FIXED_NOW + timedelta(seconds=i),
        )
        ep_world.append(e)
        await store.add(e, embedding=list(_UNIFORM_VEC))

    retriever = Retriever(
        store,
        _FakeEmbeddingClient(list(_UNIFORM_VEC)),
        limit_candidates=limit,
        now_factory=_FIXED_NOW,
    )

    # The store fetches the most-recent ``limit`` per (kind, scope): the newest
    # 3 by created_at. Within each pool the total order is created_at ASC, so
    # the retrieved rows are the *oldest of the newest-3* — and the globally
    # oldest (index 0,1) are outside every pool (silent cap made explicit).
    agent_pool_ids = {e.id for e in ep_agent[2:]}  # newest 3 episodic-agent
    sem_pool_ids = {e.id for e in sem_agent[2:]}  # newest 3 semantic-agent
    world_pool_ids = {e.id for e in ep_world[2:]}  # newest 3 episodic-world
    pool_external = {e.id for e in (*ep_agent[:2], *sem_agent[:2], *ep_world[:2])}

    ranked = await retriever.retrieve(
        "kant", "q", k_agent=50, k_world=50, mark_recalled=False
    )
    got = {r.entry.id for r in ranked}

    # per (kind, scope) cap: agent pool = 3 episodic + 3 semantic = 6, NOT a
    # flat 3 across the whole agent scope.
    agent_hits = {r.entry.id for r in ranked if r.entry.agent_id == "kant"}
    assert agent_hits == agent_pool_ids | sem_pool_ids
    assert len(agent_hits) == 2 * limit  # proves per-kind (not flat) cap

    world_hits = {r.entry.id for r in ranked if r.entry.agent_id == "nietzsche"}
    assert world_hits == world_pool_ids

    # Pool-external older equal-strength memories are never surfaced.
    assert got.isdisjoint(pool_external)

    # Within the agent-episodic pool the ordering is the deterministic total
    # order (created_at ASC == id ASC here), confirming order acts on the pool.
    ep_agent_ranked = [
        r.entry.id
        for r in ranked
        if r.entry.agent_id == "kant" and r.entry.id.startswith("ep-agent-")
    ]
    assert ep_agent_ranked == sorted(agent_pool_ids)
