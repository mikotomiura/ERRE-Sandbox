"""sqlite-vec backed memory store with kind-specific content tables.

See ``.steering/20260418-memory-store/design.md`` §3.1. The wire type
``schemas.MemoryEntry`` is pure domain and does **not** carry an embedding;
this module attaches the embedding in a shared ``vec0`` virtual table keyed
by ``memory_id``.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import struct
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Final

import sqlite_vec

from erre_sandbox.schemas import (
    DialogTurnMsg,
    MemoryEntry,
    MemoryKind,
    SemanticMemoryRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from pathlib import Path

DEFAULT_EMBED_DIM: Final[int] = 768
"""Default embedding dimension (nomic-embed-text-v1.5 produces 768-d vectors)."""

_KIND_TO_TABLE: Final[dict[MemoryKind, str]] = {
    MemoryKind.EPISODIC: "episodic_memory",
    MemoryKind.SEMANTIC: "semantic_memory",
    MemoryKind.PROCEDURAL: "procedural_memory",
    MemoryKind.RELATIONAL: "relational_memory",
}

_SHARED_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "agent_id",
    "content",
    "importance",
    "created_at",
    "last_recalled_at",
    "recall_count",
    "tags",
)


class MemoryStore:
    """Persistence layer for the 4-faculty memory model.

    The 4 memory kinds (``EPISODIC`` / ``SEMANTIC`` / ``PROCEDURAL`` /
    ``RELATIONAL``) live in their own tables with a minimal kind-specific
    schema; a single ``vec_embeddings`` virtual table stores 768-dim
    vectors keyed by ``memory_id`` and is joined at retrieval time.

    All write operations are asynchronous (``asyncio.to_thread`` wraps the
    blocking sqlite3 calls) so this store can be used inside an asyncio
    event loop without starving other coroutines.
    """

    VEC_TABLE: ClassVar[str] = "vec_embeddings"

    def __init__(
        self,
        db_path: Path | str = ":memory:",
        *,
        embed_dim: int = DEFAULT_EMBED_DIM,
    ) -> None:
        self._db_path = str(db_path)
        self._embed_dim = embed_dim
        self._conn: sqlite3.Connection | None = None
        # The stdlib ``sqlite3`` module ships with ``threadsafety=1``: the
        # module is safe to import from many threads, but a single connection
        # object is NOT safe to use concurrently. Earlier sessions relied on
        # "callers await before re-entering" to serialise access, which does
        # not hold when :meth:`erre_sandbox.world.WorldRuntime._on_cognition_tick`
        # dispatches N agent steps via ``asyncio.gather`` — each step lands on
        # a different thread-pool worker via :func:`asyncio.to_thread` and
        # races at ``conn.__enter__``, producing
        # ``SystemError: error return without exception set`` (observed
        # 2026-04-22 during M6-A-2b live verification with 3 agents).
        #
        # An :class:`RLock` (not :class:`Lock`) is required because
        # :meth:`_recall_semantic_sync` calls :meth:`_get_embedding_sync` while
        # already holding the lock.
        self._conn_lock: threading.RLock = threading.RLock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            # ``check_same_thread=False`` is required because ``asyncio.to_thread``
            # dispatches sync DB calls onto a worker pool; callers MUST hold
            # ``self._conn_lock`` before touching the returned connection, which
            # every ``_*_sync`` method in this class does. The async layer does
            # NOT serialise for us — ``asyncio.gather`` dispatches N agent steps
            # onto N threads concurrently.
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.enable_load_extension(True)  # noqa: FBT003 — sqlite3 stdlib API
            sqlite_vec.load(conn)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def create_schema(self) -> None:
        """Create the 4 content tables and the shared ``vec0`` table.

        Idempotent via ``IF NOT EXISTS``; safe to call on each startup.
        """
        with self._conn_lock:
            conn = self._ensure_conn()
            with conn:
                # Episodic: observations / perceptions — has source_observation_id.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS episodic_memory (
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
                # Semantic: beliefs / themes (distilled by reflection in M4).
                # ``origin_reflection_id`` (added in m4-memory-semantic-layer) links a
                # row back to the ``ReflectionEvent`` that produced it, enabling
                # audit queries and future reflection-deduplication logic. Existing
                # DBs get the column via the ``_migrate_semantic_schema`` call below.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS semantic_memory (
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
                self._migrate_semantic_schema(conn)
                # Procedural: zone/ritual-keyed skills (rich logic deferred to M5).
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS procedural_memory (
                        id TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        zone TEXT,
                        procedure_name TEXT,
                        content TEXT NOT NULL,
                        importance REAL NOT NULL,
                        created_at TEXT NOT NULL,
                        last_recalled_at TEXT,
                        recall_count INTEGER NOT NULL DEFAULT 0,
                        tags TEXT NOT NULL DEFAULT '[]'
                    )
                    """,
                )
                # Relational: interaction episodes (AgentState.relationships is
                # the dynamic source of truth; this table archives the history).
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS relational_memory (
                        id TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        other_agent_id TEXT,
                        content TEXT NOT NULL,
                        importance REAL NOT NULL,
                        created_at TEXT NOT NULL,
                        last_recalled_at TEXT,
                        recall_count INTEGER NOT NULL DEFAULT 0,
                        tags TEXT NOT NULL DEFAULT '[]'
                    )
                    """,
                )
                # Shared vec0 virtual table.
                conn.execute(
                    f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {self.VEC_TABLE}
                    USING vec0(
                        memory_id TEXT PRIMARY KEY,
                        embedding float[{self._embed_dim}]
                    )
                    """,
                )
                # Dialog turns (M8 L6-D1 precondition): complete per-turn log for
                # tracking ≥1000 turns/persona prerequisite of the M9 LoRA
                # training milestone. ``persona_id`` is resolved at sink time
                # from the bootstrap agent registry (see decisions D2) so the
                # wire schema stays untouched. Idempotency via UNIQUE(dialog_id,
                # turn_index) lets the sink re-fire safely on restart.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dialog_turns (
                        id TEXT PRIMARY KEY,
                        dialog_id TEXT NOT NULL,
                        tick INTEGER NOT NULL,
                        turn_index INTEGER NOT NULL,
                        speaker_agent_id TEXT NOT NULL,
                        speaker_persona_id TEXT NOT NULL,
                        addressee_agent_id TEXT NOT NULL,
                        addressee_persona_id TEXT NOT NULL,
                        utterance TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(dialog_id, turn_index)
                    )
                    """,
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ix_dialog_turns_persona
                    ON dialog_turns(speaker_persona_id, created_at)
                    """,
                )

    @staticmethod
    def _migrate_semantic_schema(conn: sqlite3.Connection) -> None:
        """Idempotently ensure ``semantic_memory.origin_reflection_id`` exists.

        Added by m4-memory-semantic-layer. New DBs receive the column via
        ``CREATE TABLE``; existing DBs (e.g. a ``var/kant.db`` carried over
        from the M2 milestone) reach here without the column, so we apply
        ``ALTER TABLE`` on demand. Idempotent: re-running ``create_schema()``
        is a no-op once the column is present.
        """
        existing = {
            row["name"] for row in conn.execute("PRAGMA table_info(semantic_memory)")
        }
        if "origin_reflection_id" not in existing:
            conn.execute(
                "ALTER TABLE semantic_memory ADD COLUMN origin_reflection_id TEXT",
            )

    async def close(self) -> None:
        if self._conn is not None:
            conn = self._conn
            self._conn = None
            await asyncio.to_thread(conn.close)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add(
        self,
        entry: MemoryEntry,
        embedding: list[float] | None = None,
    ) -> str:
        """Insert ``entry`` into its kind-specific table.

        If ``embedding`` is provided, also insert into ``vec_embeddings``.
        Returns the entry id (passthrough for convenience).
        """
        if embedding is not None and len(embedding) != self._embed_dim:
            raise ValueError(
                f"Embedding dim {len(embedding)} != store dim {self._embed_dim}",
            )
        return await asyncio.to_thread(self._add_sync, entry, embedding)

    def _add_sync(
        self,
        entry: MemoryEntry,
        embedding: list[float] | None,
    ) -> str:
        with self._conn_lock:
            conn = self._ensure_conn()
            with conn:
                if entry.kind is MemoryKind.EPISODIC:
                    conn.execute(
                        "INSERT INTO episodic_memory("
                        "id, agent_id, content, importance, created_at, "
                        "last_recalled_at, recall_count, source_observation_id, tags"
                        ") VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            entry.id,
                            entry.agent_id,
                            entry.content,
                            entry.importance,
                            _dt_to_text(entry.created_at),
                            _dt_to_text_opt(entry.last_recalled_at),
                            entry.recall_count,
                            entry.source_observation_id,
                            json.dumps(entry.tags, ensure_ascii=False),
                        ),
                    )
                elif entry.kind is MemoryKind.SEMANTIC:
                    # Legacy MemoryEntry path: ``origin_reflection_id`` is NULL
                    # by default. The M4 reflection cycle writes via the dedicated
                    # ``upsert_semantic`` method so this path stays around for
                    # non-reflection SEMANTIC writes (e.g. manual seed data in
                    # tests). Rows inserted here coexist safely with reflection
                    # rows — ``_semantic_row_to_record`` maps NULL → None.
                    conn.execute(
                        "INSERT INTO semantic_memory("
                        "id, agent_id, content, importance, created_at, "
                        "last_recalled_at, recall_count, tags"
                        ") VALUES (?,?,?,?,?,?,?,?)",
                        (
                            entry.id,
                            entry.agent_id,
                            entry.content,
                            entry.importance,
                            _dt_to_text(entry.created_at),
                            _dt_to_text_opt(entry.last_recalled_at),
                            entry.recall_count,
                            json.dumps(entry.tags, ensure_ascii=False),
                        ),
                    )
                elif entry.kind is MemoryKind.PROCEDURAL:
                    conn.execute(
                        "INSERT INTO procedural_memory("
                        "id, agent_id, content, importance, created_at, "
                        "last_recalled_at, recall_count, tags"
                        ") VALUES (?,?,?,?,?,?,?,?)",
                        (
                            entry.id,
                            entry.agent_id,
                            entry.content,
                            entry.importance,
                            _dt_to_text(entry.created_at),
                            _dt_to_text_opt(entry.last_recalled_at),
                            entry.recall_count,
                            json.dumps(entry.tags, ensure_ascii=False),
                        ),
                    )
                elif entry.kind is MemoryKind.RELATIONAL:
                    conn.execute(
                        "INSERT INTO relational_memory("
                        "id, agent_id, content, importance, created_at, "
                        "last_recalled_at, recall_count, tags"
                        ") VALUES (?,?,?,?,?,?,?,?)",
                        (
                            entry.id,
                            entry.agent_id,
                            entry.content,
                            entry.importance,
                            _dt_to_text(entry.created_at),
                            _dt_to_text_opt(entry.last_recalled_at),
                            entry.recall_count,
                            json.dumps(entry.tags, ensure_ascii=False),
                        ),
                    )
                else:  # pragma: no cover — exhaustive via MemoryKind enum
                    raise ValueError(f"Unknown kind: {entry.kind}")

                if embedding is not None:
                    conn.execute(
                        f"INSERT INTO {self.VEC_TABLE}"  # noqa: S608
                        "(memory_id, embedding) VALUES (?, ?)",
                        (entry.id, json.dumps(embedding)),
                    )
            return entry.id

    async def mark_recalled(self, memory_ids: Sequence[str]) -> None:
        """Increment ``recall_count`` and set ``last_recalled_at`` = now."""
        if not memory_ids:
            return
        await asyncio.to_thread(self._mark_recalled_sync, list(memory_ids))

    def _mark_recalled_sync(self, memory_ids: list[str]) -> None:
        with self._conn_lock:
            conn = self._ensure_conn()
            now = _dt_to_text(datetime.now(tz=UTC))
            placeholders = ",".join("?" * len(memory_ids))
            with conn:
                for table in _KIND_TO_TABLE.values():
                    conn.execute(
                        f"UPDATE {table} "  # noqa: S608 — table from fixed map
                        "SET recall_count = recall_count + 1, "
                        "    last_recalled_at = ? "
                        f"WHERE id IN ({placeholders})",
                        (now, *memory_ids),
                    )

    async def evict_episodic_before(
        self,
        agent_id: str,
        created_before: datetime,
    ) -> list[MemoryEntry]:
        """Remove and return episodic entries created before ``created_before``.

        Used by the M4 reflection loop (evict → LLM extract → Semantic).
        Evicting removes rows from both ``episodic_memory`` and the shared
        ``vec_embeddings`` table atomically.
        """
        return await asyncio.to_thread(
            self._evict_episodic_sync,
            agent_id,
            created_before,
        )

    def _evict_episodic_sync(
        self,
        agent_id: str,
        created_before: datetime,
    ) -> list[MemoryEntry]:
        with self._conn_lock:
            conn = self._ensure_conn()
            cutoff = _dt_to_text(created_before)
            with conn:
                rows = conn.execute(
                    "SELECT * FROM episodic_memory "
                    "WHERE agent_id = ? AND created_at < ? "
                    "ORDER BY created_at ASC",
                    (agent_id, cutoff),
                ).fetchall()
                if not rows:
                    return []
                ids = [r["id"] for r in rows]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"DELETE FROM episodic_memory WHERE id IN ({placeholders})",  # noqa: S608
                    ids,
                )
                conn.execute(
                    f"DELETE FROM {self.VEC_TABLE} WHERE memory_id IN ({placeholders})",  # noqa: S608
                    ids,
                )
            return [_row_to_memory_entry(r, MemoryKind.EPISODIC) for r in rows]

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        return await asyncio.to_thread(self._get_by_id_sync, memory_id)

    def _get_by_id_sync(self, memory_id: str) -> MemoryEntry | None:
        with self._conn_lock:
            conn = self._ensure_conn()
            for kind, table in _KIND_TO_TABLE.items():
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE id = ?",  # noqa: S608
                    (memory_id,),
                ).fetchone()
                if row is not None:
                    return _row_to_memory_entry(row, kind)
            return None

    async def list_by_agent(
        self,
        agent_id: str,
        kind: MemoryKind,
        *,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        return await asyncio.to_thread(self._list_by_agent_sync, agent_id, kind, limit)

    def _list_by_agent_sync(
        self,
        agent_id: str,
        kind: MemoryKind,
        limit: int,
    ) -> list[MemoryEntry]:
        with self._conn_lock:
            conn = self._ensure_conn()
            table = _KIND_TO_TABLE[kind]
            rows = conn.execute(
                f"SELECT * FROM {table} "  # noqa: S608 — table from fixed map
                "WHERE agent_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
            return [_row_to_memory_entry(r, kind) for r in rows]

    async def list_world_scope(
        self,
        exclude_agent_id: str,
        kind: MemoryKind,
        *,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Return memories from *other* agents (for world-scope retrieval)."""
        return await asyncio.to_thread(
            self._list_world_scope_sync,
            exclude_agent_id,
            kind,
            limit,
        )

    def _list_world_scope_sync(
        self,
        exclude_agent_id: str,
        kind: MemoryKind,
        limit: int,
    ) -> list[MemoryEntry]:
        with self._conn_lock:
            conn = self._ensure_conn()
            table = _KIND_TO_TABLE[kind]
            rows = conn.execute(
                f"SELECT * FROM {table} "  # noqa: S608 — table from fixed map
                "WHERE agent_id != ? "
                "ORDER BY created_at DESC LIMIT ?",
                (exclude_agent_id, limit),
            ).fetchall()
            return [_row_to_memory_entry(r, kind) for r in rows]

    async def get_embedding(self, memory_id: str) -> list[float] | None:
        """Return the stored embedding for ``memory_id`` or ``None``."""
        return await asyncio.to_thread(self._get_embedding_sync, memory_id)

    def _get_embedding_sync(self, memory_id: str) -> list[float] | None:
        with self._conn_lock:
            conn = self._ensure_conn()
            row = conn.execute(
                f"SELECT embedding FROM {self.VEC_TABLE} WHERE memory_id = ?",  # noqa: S608
                (memory_id,),
            ).fetchone()
            if row is None:
                return None
            raw = row["embedding"]
            if isinstance(raw, bytes):
                # sqlite-vec stores float32 little-endian; decode with struct.
                count = len(raw) // 4
                return list(struct.unpack(f"<{count}f", raw))
            if isinstance(raw, str):
                return [float(x) for x in json.loads(raw)]
            raise TypeError(f"Unexpected embedding payload type: {type(raw)!r}")

    async def knn_ids(
        self,
        query_embedding: list[float],
        *,
        k: int,
        candidate_ids: Iterable[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Return ``(memory_id, distance)`` pairs sorted by ascending distance.

        If ``candidate_ids`` is given, restrict the KNN scan to that id set.
        ``distance`` is the L2 distance from ``vec_distance_l2`` (lower =
        more similar). ``k`` is capped at the candidate pool size.
        """
        if len(query_embedding) != self._embed_dim:
            raise ValueError(
                f"Query dim {len(query_embedding)} != store dim {self._embed_dim}",
            )
        restrict = list(candidate_ids) if candidate_ids is not None else None
        return await asyncio.to_thread(
            self._knn_ids_sync,
            query_embedding,
            k,
            restrict,
        )

    def _knn_ids_sync(
        self,
        query_embedding: list[float],
        k: int,
        restrict: list[str] | None,
    ) -> list[tuple[str, float]]:
        with self._conn_lock:
            conn = self._ensure_conn()
            q_json = json.dumps(query_embedding)
            if restrict is None:
                rows = conn.execute(
                    f"SELECT memory_id, distance FROM {self.VEC_TABLE} "  # noqa: S608
                    "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                    (q_json, k),
                ).fetchall()
            elif not restrict:
                return []
            else:
                placeholders = ",".join("?" * len(restrict))
                rows = conn.execute(
                    f"SELECT memory_id, distance FROM {self.VEC_TABLE} "  # noqa: S608
                    "WHERE embedding MATCH ? AND k = ? "
                    f"AND memory_id IN ({placeholders}) "
                    "ORDER BY distance",
                    (q_json, k, *restrict),
                ).fetchall()
            return [(r["memory_id"], float(r["distance"])) for r in rows]

    # ------------------------------------------------------------------
    # Semantic-layer API (m4-memory-semantic-layer)
    # ------------------------------------------------------------------

    async def upsert_semantic(self, record: SemanticMemoryRecord) -> str:
        """Insert or replace a :class:`SemanticMemoryRecord`.

        The row's ``origin_reflection_id`` is preserved in the dedicated
        column. ``embedding`` is inserted into ``vec_embeddings`` only when
        non-empty — empty embeddings are permitted by the M4 foundation
        contract (e.g. fixture payloads, pre-embedding records) and simply
        make the row unrecallable via semantic search.

        Upsert semantics: same ``id`` replaces the prior row in both
        ``semantic_memory`` and ``vec_embeddings``. Internal bookkeeping
        fields (``importance`` / ``recall_count`` / ``tags``) that do not
        exist on the wire type receive defensible defaults on write; they
        are hidden on read.
        """
        if record.embedding and len(record.embedding) != self._embed_dim:
            raise ValueError(
                f"Embedding dim {len(record.embedding)} != store dim {self._embed_dim}",
            )
        return await asyncio.to_thread(self._upsert_semantic_sync, record)

    def _upsert_semantic_sync(self, record: SemanticMemoryRecord) -> str:
        with self._conn_lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO semantic_memory("
                    "id, agent_id, content, importance, created_at, "
                    "last_recalled_at, recall_count, tags, origin_reflection_id"
                    ") VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        record.id,
                        record.agent_id,
                        record.summary,
                        1.0,
                        _dt_to_text(record.created_at),
                        None,
                        0,
                        "[]",
                        record.origin_reflection_id,
                    ),
                )
                # The ``vec0`` virtual table does not support INSERT OR REPLACE
                # on its PRIMARY KEY (UNIQUE constraint fires before the replace
                # branch is taken), so we always clear the prior row for this
                # id before inserting the new embedding. Wrapping both statements
                # in the outer ``with conn:`` block keeps the upsert atomic.
                conn.execute(
                    f"DELETE FROM {self.VEC_TABLE} WHERE memory_id = ?",  # noqa: S608
                    (record.id,),
                )
                if record.embedding:
                    conn.execute(
                        f"INSERT INTO {self.VEC_TABLE}"  # noqa: S608
                        "(memory_id, embedding) VALUES (?, ?)",
                        (record.id, json.dumps(record.embedding)),
                    )
            return record.id

    async def recall_semantic(
        self,
        agent_id: str,
        query_embedding: list[float],
        *,
        k: int,
    ) -> list[tuple[SemanticMemoryRecord, float]]:
        """Return the agent's top-k semantic memories by vector distance.

        Returns a list of ``(record, distance)`` pairs sorted by ascending
        distance (``vec_distance_l2``; lower = more similar). Rows without
        a stored embedding are invisible to this query by construction
        (``upsert_semantic`` skips the vec table when ``embedding`` is
        empty). The result length is ``min(k, #rows-with-embedding)``.
        """
        if len(query_embedding) != self._embed_dim:
            raise ValueError(
                f"Query dim {len(query_embedding)} != store dim {self._embed_dim}",
            )
        return await asyncio.to_thread(
            self._recall_semantic_sync,
            agent_id,
            query_embedding,
            k,
        )

    def _recall_semantic_sync(
        self,
        agent_id: str,
        query_embedding: list[float],
        k: int,
    ) -> list[tuple[SemanticMemoryRecord, float]]:
        with self._conn_lock:
            conn = self._ensure_conn()
            candidate_rows = conn.execute(
                "SELECT id FROM semantic_memory WHERE agent_id = ?",
                (agent_id,),
            ).fetchall()
            candidate_ids = [r["id"] for r in candidate_rows]
            if not candidate_ids:
                return []
            q_json = json.dumps(query_embedding)
            placeholders = ",".join("?" * len(candidate_ids))
            hit_rows = conn.execute(
                f"SELECT memory_id, distance FROM {self.VEC_TABLE} "  # noqa: S608
                f"WHERE embedding MATCH ? AND k = ? AND memory_id IN ({placeholders}) "
                "ORDER BY distance",
                (q_json, k, *candidate_ids),
            ).fetchall()
            if not hit_rows:
                return []

            # Single batch fetch of the semantic rows keyed by memory_id. The
            # embedding is looked up per hit below because ``vec_distance_l2``
            # does not return the stored vector; ``k`` is small (≤ a few dozen)
            # so the per-hit lookup is acceptable. Rewrite to a single JOIN if k
            # ever grows to hundreds.
            hit_ids = [r["memory_id"] for r in hit_rows]
            id_placeholders = ",".join("?" * len(hit_ids))
            row_by_id = {
                r["id"]: r
                for r in conn.execute(
                    f"SELECT * FROM semantic_memory WHERE id IN ({id_placeholders})",  # noqa: S608
                    hit_ids,
                ).fetchall()
            }
            results: list[tuple[SemanticMemoryRecord, float]] = []
            for hit in hit_rows:
                mid = hit["memory_id"]
                row = row_by_id.get(mid)
                if row is None:
                    # Defensive: the row was deleted between the candidate_ids
                    # query and the knn join. Skip rather than raise.
                    continue
                # ``_get_embedding_sync`` re-acquires the same RLock — the
                # re-entrant lock class means this nested call does not
                # deadlock, just increments the recursion counter.
                embedding = self._get_embedding_sync(mid) or []
                results.append(
                    (
                        _semantic_row_to_record(row, embedding),
                        float(hit["distance"]),
                    ),
                )
            return results

    # ------------------------------------------------------------------
    # Dialog turns (M8 L6-D1 precondition)
    # ------------------------------------------------------------------

    def add_dialog_turn_sync(
        self,
        turn: DialogTurnMsg,
        *,
        speaker_persona_id: str,
        addressee_persona_id: str,
    ) -> str:
        """Persist ``turn`` into the ``dialog_turns`` table synchronously.

        Intended for the :class:`InMemoryDialogScheduler` sink which runs on
        the event-loop thread after each :meth:`record_turn` call and must
        not await. ``persona_id`` for speaker / addressee is resolved at the
        call site from the bootstrap agent registry (see decisions D2).

        Idempotent via ``INSERT OR IGNORE`` on the ``UNIQUE(dialog_id,
        turn_index)`` constraint — re-emitting the same turn after a restart
        is a no-op rather than a row duplication.

        Returns the row id (new UUID when the row was inserted, or the
        existing id when the INSERT was ignored).
        """
        row_id = f"dt_{turn.dialog_id}_{turn.turn_index:04d}"
        with self._conn_lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "INSERT OR IGNORE INTO dialog_turns("
                    "id, dialog_id, tick, turn_index, "
                    "speaker_agent_id, speaker_persona_id, "
                    "addressee_agent_id, addressee_persona_id, "
                    "utterance, created_at"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        row_id,
                        turn.dialog_id,
                        turn.tick,
                        turn.turn_index,
                        turn.speaker_id,
                        speaker_persona_id,
                        turn.addressee_id,
                        addressee_persona_id,
                        turn.utterance,
                        _dt_to_text(datetime.now(tz=UTC)),
                    ),
                )
        return row_id

    async def add_dialog_turn(
        self,
        turn: DialogTurnMsg,
        *,
        speaker_persona_id: str,
        addressee_persona_id: str,
    ) -> str:
        """Async wrapper over :meth:`add_dialog_turn_sync` via ``to_thread``.

        Non-scheduler callers (CLI, tests, future async sinks) should prefer
        this variant so the event loop is not blocked on sqlite I/O.
        """
        return await asyncio.to_thread(
            self.add_dialog_turn_sync,
            turn,
            speaker_persona_id=speaker_persona_id,
            addressee_persona_id=addressee_persona_id,
        )

    def iter_dialog_turns(
        self,
        *,
        persona: str | None = None,
        since: datetime | None = None,
    ) -> Iterator[dict[str, object]]:
        """Yield dialog turn rows as plain dicts, oldest first.

        ``persona`` filters by ``speaker_persona_id`` (addressee is not
        matched — export is speaker-scoped for LoRA training-data semantics).
        ``since`` filters by ``created_at >= since``.

        Returns plain dicts (not :class:`DialogTurnMsg`) so the export CLI
        can emit rows that include the resolved ``speaker_persona_id`` /
        ``addressee_persona_id`` without having to re-join at export time.
        """
        with self._conn_lock:
            conn = self._ensure_conn()
            clauses: list[str] = []
            params: list[object] = []
            if persona is not None:
                clauses.append("speaker_persona_id = ?")
                params.append(persona)
            if since is not None:
                clauses.append("created_at >= ?")
                params.append(_dt_to_text(since))
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = (
                "SELECT id, dialog_id, tick, turn_index, "
                "speaker_agent_id, speaker_persona_id, "
                "addressee_agent_id, addressee_persona_id, "
                "utterance, created_at "
                f"FROM dialog_turns {where} "
                "ORDER BY created_at ASC, turn_index ASC"
            )
            rows = conn.execute(sql, params).fetchall()
        for row in rows:
            yield dict(row)


# =============================================================================
# Row → MemoryEntry helpers
# =============================================================================


def _row_to_memory_entry(row: sqlite3.Row, kind: MemoryKind) -> MemoryEntry:
    return MemoryEntry(
        id=row["id"],
        agent_id=row["agent_id"],
        kind=kind,
        content=row["content"],
        importance=row["importance"],
        created_at=_text_to_dt(row["created_at"]),
        last_recalled_at=_text_to_dt_opt(row["last_recalled_at"]),
        recall_count=row["recall_count"],
        source_observation_id=(
            row["source_observation_id"] if kind is MemoryKind.EPISODIC else None
        ),
        tags=json.loads(row["tags"]) if row["tags"] else [],
    )


def _semantic_row_to_record(
    row: sqlite3.Row,
    embedding: list[float],
) -> SemanticMemoryRecord:
    """Reconstruct a :class:`SemanticMemoryRecord` from a storage row.

    Internal bookkeeping columns (``importance`` / ``recall_count`` /
    ``tags`` / ``last_recalled_at``) are intentionally not projected onto
    the wire type — they live only in storage so that future retention
    policies can tune them without breaking ``schemas.py``.
    """
    return SemanticMemoryRecord(
        id=row["id"],
        agent_id=row["agent_id"],
        embedding=embedding,
        summary=row["content"],
        origin_reflection_id=row["origin_reflection_id"],
        created_at=_text_to_dt(row["created_at"]),
    )


def _dt_to_text(dt: datetime) -> str:
    return dt.isoformat()


def _dt_to_text_opt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _text_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _text_to_dt_opt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


__all__ = [
    "DEFAULT_EMBED_DIM",
    "MemoryStore",
]
