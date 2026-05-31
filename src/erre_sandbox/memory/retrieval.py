"""2-scope retriever with decay-weighted ranking.

The scoring function

    strength = importance * exp(-λ * age_days) * (1 + β * recall_count) * cosine_sim

matches ``docs/architecture.md §Memory Layer`` for the ``importance`` and
``recall_count`` factors; ``λ`` defaults to ``0.1`` (half-life ≈ 7 days).

``Retriever.retrieve`` is the authoritative retrieval entrypoint used by
``cognition/cycle.py`` (T12): it composes ``k_agent`` per-agent memories
with ``k_world`` cross-agent memories, ranks them by ``score()``, and
bumps ``recall_count`` as a deliberate side effect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.schemas import MemoryKind

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.memory.embedding import EmbeddingClient
    from erre_sandbox.memory.store import MemoryStore
    from erre_sandbox.schemas import MemoryEntry

_SECONDS_PER_DAY: Final[float] = 86_400.0
DEFAULT_DECAY_LAMBDA: Final[float] = 0.1  # half-life ≈ ln(2)/0.1 ≈ 6.93 days
DEFAULT_RECALL_BOOST: Final[float] = 0.2
DEFAULT_K_AGENT: Final[int] = 8
DEFAULT_K_WORLD: Final[int] = 3
DEFAULT_KINDS: Final[tuple[MemoryKind, ...]] = (
    MemoryKind.EPISODIC,
    MemoryKind.SEMANTIC,
)


def score(
    *,
    importance: float,
    age_days: float,
    recall_count: int,
    cosine_sim: float,
    decay_lambda: float = DEFAULT_DECAY_LAMBDA,
    recall_boost: float = DEFAULT_RECALL_BOOST,
) -> float:
    """Combine importance, recency, recall and semantic fit into one score.

    Pure function; see ``tests/test_memory/test_retrieval.py`` for the
    invariants this guarantees (monotone decay in ``age_days``, monotone
    boost in ``recall_count``, multiplicative in ``cosine_sim``).
    """
    decay = math.exp(-decay_lambda * max(age_days, 0.0))
    boost = 1.0 + recall_boost * max(recall_count, 0)
    return importance * decay * boost * cosine_sim


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity ∈ [-1, 1]. Returns 0.0 if either vector is zero."""
    av = np.asarray(a, dtype=np.float64)
    bv = np.asarray(b, dtype=np.float64)
    na = float(np.linalg.norm(av))
    nb = float(np.linalg.norm(bv))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(av, bv) / (na * nb))


@dataclass(frozen=True)
class RankedMemory:
    """A retrieval result paired with its computed strength."""

    entry: MemoryEntry
    strength: float
    cosine_sim: float


class Retriever:
    """Composes :class:`MemoryStore` and :class:`EmbeddingClient`.

    The retrieve pipeline is:

    1. Embed the query with :meth:`EmbeddingClient.embed_query`
       (``search_query:`` prefix).
    2. Pull up to ``limit_candidates`` per-agent entries (from ``kinds``)
       and ``limit_candidates`` world-scope entries.
    3. Compute ``cosine_sim`` for every candidate that has an embedding
       (candidates missing an embedding fall back to ``0.0``).
    4. Apply :func:`score` with the configured ``decay_lambda`` and
       ``recall_boost``.
    5. Take the top ``k_agent`` per-agent + top ``k_world`` world-scope.
    6. Bump ``recall_count`` for every returned memory.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding: EmbeddingClient,
        *,
        decay_lambda: float = DEFAULT_DECAY_LAMBDA,
        recall_boost: float = DEFAULT_RECALL_BOOST,
        limit_candidates: int = 50,
        now_factory: (datetime | None) = None,
    ) -> None:
        self._store = store
        self._embedding = embedding
        self._decay_lambda = decay_lambda
        self._recall_boost = recall_boost
        self._limit_candidates = limit_candidates
        # ``now_factory`` is optionally a fixed datetime for deterministic tests;
        # ``None`` means "use real wall clock" (see :meth:`_now`).
        self._fixed_now = now_factory

    def _now(self) -> datetime:
        return self._fixed_now if self._fixed_now is not None else datetime.now(tz=UTC)

    async def retrieve(
        self,
        agent_id: str,
        query: str,
        *,
        k_agent: int = DEFAULT_K_AGENT,
        k_world: int = DEFAULT_K_WORLD,
        kinds: Sequence[MemoryKind] = DEFAULT_KINDS,
    ) -> list[RankedMemory]:
        q_vec = await self._embedding.embed_query(query)
        now = self._now()

        agent_ranked = await self._rank_scope(
            q_vec=q_vec,
            now=now,
            kinds=kinds,
            agent_id=agent_id,
            world=False,
        )
        world_ranked = await self._rank_scope(
            q_vec=q_vec,
            now=now,
            kinds=kinds,
            agent_id=agent_id,
            world=True,
        )

        top_agent = agent_ranked[:k_agent]
        top_world = world_ranked[:k_world]
        combined = [*top_agent, *top_world]

        if combined:
            await self._store.mark_recalled([r.entry.id for r in combined])
        return combined

    async def _rank_scope(
        self,
        *,
        q_vec: list[float],
        now: datetime,
        kinds: Sequence[MemoryKind],
        agent_id: str,
        world: bool,
    ) -> list[RankedMemory]:
        candidates: list[MemoryEntry] = []
        for kind in kinds:
            batch = (
                await self._store.list_world_scope(
                    exclude_agent_id=agent_id,
                    kind=kind,
                    limit=self._limit_candidates,
                )
                if world
                else await self._store.list_by_agent(
                    agent_id=agent_id,
                    kind=kind,
                    limit=self._limit_candidates,
                )
            )
            candidates.extend(batch)
        if not candidates:
            return []
        scored: list[RankedMemory] = []
        for entry in candidates:
            vec = await self._store.get_embedding(entry.id)
            sim = cosine_similarity(vec, q_vec) if vec is not None else 0.0
            age = _age_days(entry.created_at, now)
            strength = score(
                importance=entry.importance,
                age_days=age,
                recall_count=entry.recall_count,
                cosine_sim=sim,
                decay_lambda=self._decay_lambda,
                recall_boost=self._recall_boost,
            )
            scored.append(RankedMemory(entry=entry, strength=strength, cosine_sim=sim))
        scored.sort(key=lambda r: r.strength, reverse=True)
        return scored


def _age_days(created_at: datetime, now: datetime) -> float:
    delta_s = (now - created_at).total_seconds()
    return max(delta_s / _SECONDS_PER_DAY, 0.0)


__all__ = [
    "DEFAULT_DECAY_LAMBDA",
    "DEFAULT_KINDS",
    "DEFAULT_K_AGENT",
    "DEFAULT_K_WORLD",
    "DEFAULT_RECALL_BOOST",
    "RankedMemory",
    "Retriever",
    "cosine_similarity",
    "score",
]
