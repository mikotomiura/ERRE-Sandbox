"""M13-ES1 SPDM memory-layer tests: SpatialContext, location round-trip,
bit-identical scoring, and the additive ``location_json`` migration.

The non-negotiable invariant is **bit-identity**: with ``location=None`` or
``spatial_weight=0`` the score and ranking must reproduce the pre-SPDM behaviour
exactly (frozen non-breakage).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import pytest

from erre_sandbox.memory.embedding import EmbeddingClient
from erre_sandbox.memory.retrieval import Retriever, score, spatial_proximity
from erre_sandbox.memory.store import MemoryStore
from erre_sandbox.schemas import MemoryEntry, MemoryKind, Position, SpatialContext, Zone

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


# ---------------------------------------------------------------------------
# SpatialContext schema + score bit-identity
# ---------------------------------------------------------------------------


def test_spatial_context_roundtrips_json() -> None:
    sc = SpatialContext(zone=Zone.PERIPATOS, x=1.5, y=-2.0, z=3.25, source_count=4)
    assert SpatialContext.model_validate_json(sc.model_dump_json()) == sc


def test_spatial_context_source_count_optional() -> None:
    sc = SpatialContext(zone=Zone.STUDY, x=0.0, y=0.0, z=0.0)
    assert sc.source_count is None


def test_score_bit_identical_when_spatial_weight_zero() -> None:
    kwargs = {
        "importance": 0.7,
        "age_days": 3.0,
        "recall_count": 4,
        "cosine_sim": 0.55,
    }
    base = score(**kwargs)
    # Explicit weight=0 with any proximity must equal the pre-SPDM score.
    assert score(**kwargs, spatial_weight=0.0, proximity=0.9) == base
    assert score(**kwargs, spatial_weight=0.0, proximity=0.0) == base


def test_score_bit_identical_when_proximity_zero() -> None:
    kwargs = {
        "importance": 0.7,
        "age_days": 3.0,
        "recall_count": 4,
        "cosine_sim": 0.55,
    }
    # proximity 0 (no formation location) ⇒ factor 1 even with a positive weight.
    assert score(**kwargs, spatial_weight=2.0, proximity=0.0) == score(**kwargs)


def test_score_spatial_term_boosts_when_engaged() -> None:
    kwargs = {
        "importance": 0.7,
        "age_days": 3.0,
        "recall_count": 4,
        "cosine_sim": 0.55,
    }
    assert score(**kwargs, spatial_weight=1.0, proximity=1.0) == pytest.approx(
        score(**kwargs) * 2.0
    )


def test_spatial_proximity_none_is_neutral() -> None:
    here = SpatialContext(zone=Zone.STUDY, x=0.0, y=0.0, z=0.0)
    assert spatial_proximity(None, here) == 0.0
    assert spatial_proximity(here, None) == 0.0


def test_spatial_proximity_decays_with_distance() -> None:
    a = SpatialContext(zone=Zone.STUDY, x=0.0, y=0.0, z=0.0)
    same = SpatialContext(zone=Zone.STUDY, x=0.0, y=0.0, z=0.0)
    far = SpatialContext(zone=Zone.GARDEN, x=10.0, y=0.0, z=0.0)
    assert spatial_proximity(a, same) == pytest.approx(1.0)
    assert spatial_proximity(a, far) < spatial_proximity(a, same)


def test_spatial_proximity_accepts_position() -> None:
    pos = Position(x=1.0, y=0.0, z=0.0, zone=Zone.STUDY)
    formed = SpatialContext(zone=Zone.STUDY, x=1.0, y=0.0, z=0.0)
    assert spatial_proximity(pos, formed) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# store round-trip + migration
# ---------------------------------------------------------------------------


async def test_store_location_roundtrip_all_kinds() -> None:
    store = MemoryStore(":memory:")
    store.create_schema()
    loc = SpatialContext(zone=Zone.AGORA, x=2.0, y=1.0, z=0.0)
    for kind in (
        MemoryKind.EPISODIC,
        MemoryKind.SEMANTIC,
        MemoryKind.PROCEDURAL,
        MemoryKind.RELATIONAL,
    ):
        await store.add(
            MemoryEntry(
                id=f"{kind.value}-1",
                agent_id="a",
                kind=kind,
                content="c",
                importance=0.5,
                location=loc,
            ),
        )
        rows = await store.list_by_agent("a", kind)
        assert rows[0].location == loc
    await store.close()


async def test_store_location_none_roundtrip() -> None:
    store = MemoryStore(":memory:")
    store.create_schema()
    await store.add(
        MemoryEntry(
            id="e", agent_id="a", kind=MemoryKind.EPISODIC, content="c", importance=0.5
        ),
    )
    rows = await store.list_by_agent("a", MemoryKind.EPISODIC)
    assert rows[0].location is None
    await store.close()


def _old_schema_episodic_db(path: Path) -> None:
    """Create a pre-SPDM episodic_memory table (no ``location_json``) + one row."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE episodic_memory (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL NOT NULL,
            created_at TEXT NOT NULL,
            last_recalled_at TEXT,
            recall_count INTEGER NOT NULL DEFAULT 0,
            source_observation_id TEXT,
            tags TEXT NOT NULL DEFAULT '[]'
        )
        """,
    )
    conn.execute(
        "INSERT INTO episodic_memory"
        "(id, agent_id, content, importance, created_at, tags) "
        "VALUES (?,?,?,?,?,?)",
        ("legacy", "a", "old row", 0.5, datetime.now(tz=UTC).isoformat(), "[]"),
    )
    conn.commit()
    conn.close()


async def test_migration_backward_compatible(tmp_path: Path) -> None:
    """An existing pre-SPDM DB gains ``location_json`` via ALTER and legacy rows
    read back with ``location=None`` (no backfill)."""
    db = tmp_path / "legacy.db"
    _old_schema_episodic_db(db)

    store = MemoryStore(db)
    store.create_schema()  # runs _migrate_location_schema → ALTER ADD COLUMN
    rows = await store.list_by_agent("a", MemoryKind.EPISODIC)
    assert len(rows) == 1
    assert rows[0].id == "legacy"
    assert rows[0].location is None  # not backfilled

    # A fresh spatial write works on the migrated DB.
    await store.add(
        MemoryEntry(
            id="new",
            agent_id="a",
            kind=MemoryKind.EPISODIC,
            content="new row",
            importance=0.5,
            location=SpatialContext(zone=Zone.STUDY, x=1.0, y=0.0, z=0.0),
        ),
    )
    rows = await store.list_by_agent("a", MemoryKind.EPISODIC)
    by = {r.id: r for r in rows}
    assert by["new"].location is not None
    assert by["legacy"].location is None
    await store.close()


def test_migration_idempotent(tmp_path: Path) -> None:
    """Running create_schema twice does not error (ALTER guarded by PRAGMA check)."""
    db = tmp_path / "idem.db"
    store = MemoryStore(db)
    store.create_schema()
    store.create_schema()  # no-op second time


# ---------------------------------------------------------------------------
# Retriever bit-identity (default spatial_weight=0 must not change ranking)
# ---------------------------------------------------------------------------


class _FixedEmbedding(EmbeddingClient):
    def __init__(self, vec: list[float]) -> None:
        self.model = "fake"
        self.endpoint = "http://fake"
        self.dim = len(vec)
        self._vec = vec

    async def embed(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_query(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_document(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_many(
        self,
        texts: Sequence[str],
        *,
        kind: Literal["query", "document"],  # noqa: ARG002
    ) -> list[list[float]]:
        return [list(self._vec) for _ in texts]

    async def close(self) -> None:
        pass


async def test_retriever_default_ignores_location() -> None:
    """With the default spatial_weight=0, passing current_location must not change
    the ranking (bit-identical to pre-SPDM)."""
    store = MemoryStore(":memory:", embed_dim=4)
    store.create_schema()
    vec = [1.0, 0.0, 0.0, 0.0]
    now = datetime(2026, 1, 1, tzinfo=UTC)
    near = SpatialContext(zone=Zone.STUDY, x=0.0, y=0.0, z=0.0)
    far = SpatialContext(zone=Zone.GARDEN, x=50.0, y=0.0, z=0.0)
    await store.add(
        MemoryEntry(
            id="near",
            agent_id="a",
            kind=MemoryKind.EPISODIC,
            content="near",
            importance=0.5,
            created_at=now,
            location=far,
        ),
        embedding=vec,
    )
    await store.add(
        MemoryEntry(
            id="far",
            agent_id="a",
            kind=MemoryKind.EPISODIC,
            content="far",
            importance=0.5,
            created_at=now + timedelta(seconds=1),
            location=near,
        ),
        embedding=vec,
    )
    # Fixed now_factory so both calls share one clock (else wall-clock drift between
    # the two retrieves changes age_days → strength at the float level).
    retriever = Retriever(
        store, _FixedEmbedding(vec), now_factory=now + timedelta(days=1)
    )  # spatial_weight defaults to 0
    here = Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY)
    # mark_recalled=False on both so the only possible difference is current_location.
    ranked_loc = await retriever.retrieve(
        "a", "q", k_agent=2, k_world=0, current_location=here, mark_recalled=False
    )
    ranked_none = await retriever.retrieve(
        "a", "q", k_agent=2, k_world=0, mark_recalled=False
    )
    # Same strengths regardless of current_location, because weight=0.
    assert [r.strength for r in ranked_loc] == [r.strength for r in ranked_none]
    await store.close()
