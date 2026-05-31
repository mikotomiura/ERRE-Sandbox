"""Unit tests for the m4-memory-semantic-layer API on :class:`MemoryStore`.

Covers ``upsert_semantic`` + ``recall_semantic`` + the
``origin_reflection_id`` column migration. Existing 4-kind round-trip
tests in ``test_store.py`` are unchanged so M2 regression is preserved.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.memory.store import MemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from erre_sandbox.schemas import SemanticMemoryRecord


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------


def test_create_schema_adds_origin_reflection_id_column() -> None:
    """Fresh DB: ``origin_reflection_id`` is created directly by CREATE TABLE."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert "origin_reflection_id" in cols


def test_create_schema_is_idempotent_with_origin_reflection_id(
    tmp_path: Path,
) -> None:
    """Re-invoking ``create_schema`` does not fail on the migration path.

    Mimics the bootstrap flow where every startup calls ``create_schema()``
    against a persistent DB that may already have the column.
    """
    db = tmp_path / "m4_smoke.db"
    store = MemoryStore(db_path=db)
    store.create_schema()
    # Second invocation must not raise even though the ALTER TABLE path
    # would conflict if un-guarded.
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert "origin_reflection_id" in cols


def test_create_schema_migrates_pre_m4_db(
    tmp_path: Path,
) -> None:
    """Simulate an M2-era DB without the new column, then migrate it.

    The store must detect the missing column and ALTER TABLE without
    losing any data.
    """
    db = tmp_path / "pre_m4.db"
    # Build a pre-M4-shape semantic_memory table by hand.
    legacy = sqlite3.connect(str(db))
    try:
        legacy.execute(
            """
            CREATE TABLE semantic_memory (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL,
                created_at TEXT NOT NULL,
                last_recalled_at TEXT,
                recall_count INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]'
            )
            """,
        )
        legacy.execute(
            "INSERT INTO semantic_memory("
            "id, agent_id, content, importance, created_at, tags"
            ") VALUES (?,?,?,?,?,?)",
            ("legacy-1", "kant", "legacy row", 0.5, "2026-04-18T00:00:00+00:00", "[]"),
        )
        legacy.commit()
    finally:
        legacy.close()

    store = MemoryStore(db_path=db)
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert "origin_reflection_id" in cols
    row = conn.execute(
        "SELECT origin_reflection_id, content FROM semantic_memory WHERE id=?",
        ("legacy-1",),
    ).fetchone()
    assert row["content"] == "legacy row"
    assert row["origin_reflection_id"] is None


# ---------------------------------------------------------------------------
# Schema migration — M7δ (belief_kind + confidence)
# ---------------------------------------------------------------------------


def test_create_schema_adds_belief_kind_and_confidence_columns() -> None:
    """Fresh DB: M7δ columns are created directly by CREATE TABLE."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert "belief_kind" in cols
    assert "confidence" in cols


def test_create_schema_migrates_pre_m7delta_db(tmp_path: Path) -> None:
    """Simulate an M4-era DB without belief_kind / confidence and migrate it.

    The store must detect the missing columns and ALTER TABLE without losing
    data, and pre-existing rows must read back with the documented defaults
    (belief_kind=NULL, confidence=1.0) so the contract in
    ``SemanticMemoryRecord`` (default 1.0) is honoured for legacy data.
    """
    db = tmp_path / "pre_m7d.db"
    legacy = sqlite3.connect(str(db))
    try:
        legacy.execute(
            """
            CREATE TABLE semantic_memory (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL,
                created_at TEXT NOT NULL,
                last_recalled_at TEXT,
                recall_count INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                origin_reflection_id TEXT
            )
            """,
        )
        legacy.execute(
            "INSERT INTO semantic_memory("
            "id, agent_id, content, importance, created_at, tags, "
            "origin_reflection_id"
            ") VALUES (?,?,?,?,?,?,?)",
            (
                "legacy-m4-1",
                "kant",
                "M4-era reflection",
                0.5,
                "2026-04-20T00:00:00+00:00",
                "[]",
                "rf_legacy",
            ),
        )
        legacy.commit()
    finally:
        legacy.close()

    store = MemoryStore(db_path=db)
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert "belief_kind" in cols
    assert "confidence" in cols
    row = conn.execute(
        "SELECT belief_kind, confidence, content FROM semantic_memory WHERE id=?",
        ("legacy-m4-1",),
    ).fetchone()
    assert row["content"] == "M4-era reflection"
    assert row["belief_kind"] is None
    assert row["confidence"] == 1.0


def test_create_schema_is_idempotent_with_belief_columns(tmp_path: Path) -> None:
    """Re-invoking ``create_schema`` does not fail on the M7δ migration path."""
    db = tmp_path / "m7d_smoke.db"
    store = MemoryStore(db_path=db)
    store.create_schema()
    store.create_schema()
    conn = store._ensure_conn()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")}
    assert {"belief_kind", "confidence", "origin_reflection_id"} <= cols


# ---------------------------------------------------------------------------
# upsert_semantic
# ---------------------------------------------------------------------------


async def test_upsert_semantic_round_trip(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    record = make_semantic_record(
        record_id="sm-1",
        embedding=unit_embedding,
        summary="peripatos → DMN activation becomes self-evident",
        origin_reflection_id="rf_042",
    )
    returned_id = await store.upsert_semantic(record)
    assert returned_id == "sm-1"
    hits = await store.recall_semantic("kant", unit_embedding, k=5)
    assert len(hits) == 1
    rec, distance = hits[0]
    assert rec.id == "sm-1"
    assert rec.summary == record.summary
    assert rec.origin_reflection_id == "rf_042"
    # sqlite-vec stores float32 so the round-trip introduces ~1e-8 rounding
    # even for exact decimals like 0.01. Compare element-wise with a tolerance.
    assert rec.embedding == pytest.approx(unit_embedding, abs=1e-6)
    assert distance == pytest.approx(0.0, abs=1e-5)


async def test_upsert_semantic_is_idempotent_on_id(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    first = make_semantic_record(
        record_id="sm-dup",
        embedding=unit_embedding,
        summary="first write",
        origin_reflection_id="rf_a",
    )
    await store.upsert_semantic(first)
    second = make_semantic_record(
        record_id="sm-dup",
        embedding=unit_embedding,
        summary="second write overrides",
        origin_reflection_id="rf_b",
    )
    await store.upsert_semantic(second)
    hits = await store.recall_semantic("kant", unit_embedding, k=5)
    # The KNN must still return exactly one row, and it must be the second
    # write's payload.
    assert len(hits) == 1
    rec, _ = hits[0]
    assert rec.summary == "second write overrides"
    assert rec.origin_reflection_id == "rf_b"


async def test_upsert_semantic_with_empty_embedding_skips_vec_table(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """Empty embedding is permitted by the M4 foundation contract."""
    record = make_semantic_record(
        record_id="sm-noembed",
        embedding=[],
        summary="record without a vector (pre-embedding)",
    )
    await store.upsert_semantic(record)
    # Row is in the semantic table but not recallable via KNN.
    assert await store.get_embedding("sm-noembed") is None
    hits = await store.recall_semantic("kant", unit_embedding, k=5)
    assert hits == []


async def test_upsert_semantic_replaces_stale_vector_when_embedding_cleared(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """Upsert without embedding must clear any prior vector for the same id."""
    first = make_semantic_record(
        record_id="sm-toggle",
        embedding=unit_embedding,
        summary="with embedding",
    )
    await store.upsert_semantic(first)
    assert await store.get_embedding("sm-toggle") is not None
    cleared = make_semantic_record(
        record_id="sm-toggle",
        embedding=[],
        summary="embedding removed",
    )
    await store.upsert_semantic(cleared)
    assert await store.get_embedding("sm-toggle") is None


async def test_upsert_semantic_rejects_wrong_dim(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
) -> None:
    record = make_semantic_record(embedding=[0.1] * 10)  # store dim is 768
    with pytest.raises(ValueError, match="Embedding dim"):
        await store.upsert_semantic(record)


async def test_upsert_semantic_round_trip_with_belief_kind_and_confidence(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """M7δ belief fields survive write → recall through sqlite + sqlite-vec."""
    record = make_semantic_record(
        record_id="sm-belief-1",
        embedding=unit_embedding,
        summary="belief: I clash with Friedrich Nietzsche",
        origin_reflection_id="rf_kant_007",
        belief_kind="clash",
        confidence=0.7,
    )
    await store.upsert_semantic(record)
    hits = await store.recall_semantic("kant", unit_embedding, k=3)
    assert len(hits) == 1
    rec, _distance = hits[0]
    assert rec.belief_kind == "clash"
    assert rec.confidence == pytest.approx(0.7)
    # Non-belief defaults still apply when fields are omitted.
    plain = make_semantic_record(
        record_id="sm-plain-1",
        embedding=unit_embedding,
        summary="non-belief reflection",
    )
    await store.upsert_semantic(plain)
    hits = await store.recall_semantic("kant", unit_embedding, k=3)
    by_id = {r.id: r for r, _d in hits}
    assert by_id["sm-plain-1"].belief_kind is None
    assert by_id["sm-plain-1"].confidence == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# recall_semantic
# ---------------------------------------------------------------------------


async def test_recall_semantic_rejects_wrong_query_dim(
    store: MemoryStore,
) -> None:
    with pytest.raises(ValueError, match="Query dim"):
        await store.recall_semantic("kant", [0.1] * 5, k=3)


async def test_recall_semantic_isolates_per_agent(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """recall_semantic scopes to the requested agent_id."""
    for agent in ("kant", "nietzsche", "rikyu"):
        await store.upsert_semantic(
            make_semantic_record(
                record_id=f"sm-{agent}",
                agent_id=agent,
                embedding=unit_embedding,
                summary=f"{agent} summary",
                origin_reflection_id=f"rf-{agent}",
            ),
        )
    hits = await store.recall_semantic("kant", unit_embedding, k=10)
    assert len(hits) == 1
    assert hits[0][0].agent_id == "kant"
    assert hits[0][0].summary == "kant summary"


async def test_recall_semantic_respects_k(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """K cap works and returns exactly K when enough candidates exist."""
    for i in range(5):
        # Slightly perturb the embedding so distances differ.
        embedding = list(unit_embedding)
        embedding[0] = 0.01 + i * 0.001
        await store.upsert_semantic(
            make_semantic_record(
                record_id=f"sm-{i}",
                embedding=embedding,
                summary=f"record {i}",
                origin_reflection_id=f"rf-{i}",
            ),
        )
    hits = await store.recall_semantic("kant", unit_embedding, k=3)
    assert len(hits) == 3
    # Results are distance-sorted ascending.
    distances = [d for _, d in hits]
    assert distances == sorted(distances)


async def test_recall_semantic_returns_empty_when_no_rows_for_agent(
    store: MemoryStore,
    unit_embedding: list[float],
) -> None:
    hits = await store.recall_semantic("ghost", unit_embedding, k=5)
    assert hits == []


async def test_recall_semantic_preserves_null_origin_reflection_id(
    store: MemoryStore,
    make_semantic_record: Callable[..., SemanticMemoryRecord],
    unit_embedding: list[float],
) -> None:
    """Records upserted without an origin_reflection_id round-trip as None."""
    record = make_semantic_record(
        record_id="sm-null-origin",
        embedding=unit_embedding,
        origin_reflection_id=None,
    )
    await store.upsert_semantic(record)
    hits = await store.recall_semantic("kant", unit_embedding, k=3)
    assert len(hits) == 1
    assert hits[0][0].origin_reflection_id is None
