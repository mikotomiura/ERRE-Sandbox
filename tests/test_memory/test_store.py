"""Unit tests for :mod:`erre_sandbox.memory.store`."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.schemas import MemoryKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.memory.store import MemoryStore
    from erre_sandbox.schemas import MemoryEntry


# ---------------------------------------------------------------------------
# Round-trip per kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(MemoryKind))
async def test_add_get_roundtrip_each_kind(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
    unit_embedding: list[float],
    kind: MemoryKind,
) -> None:
    entry = make_entry(
        kind=kind,
        content=f"content for {kind.value}",
        importance=0.4,
        tags=["alpha", "beta"],
        source_observation_id="obs-1" if kind is MemoryKind.EPISODIC else None,
    )

    returned_id = await store.add(entry, embedding=unit_embedding)
    assert returned_id == entry.id

    fetched = await store.get_by_id(entry.id)
    assert fetched is not None
    assert fetched.id == entry.id
    assert fetched.kind is kind
    assert fetched.agent_id == entry.agent_id
    assert fetched.content == entry.content
    assert fetched.importance == pytest.approx(entry.importance)
    assert fetched.recall_count == 0
    assert fetched.last_recalled_at is None
    assert fetched.tags == ["alpha", "beta"]
    if kind is MemoryKind.EPISODIC:
        assert fetched.source_observation_id == "obs-1"
    else:
        assert fetched.source_observation_id is None


async def test_add_without_embedding_does_not_insert_vec(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    entry = make_entry(kind=MemoryKind.EPISODIC)
    await store.add(entry, embedding=None)
    assert await store.get_embedding(entry.id) is None


async def test_add_rejects_wrong_dim(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    entry = make_entry()
    with pytest.raises(ValueError, match="Embedding dim"):
        await store.add(entry, embedding=[0.1] * 10)


# ---------------------------------------------------------------------------
# vec0 KNN
# ---------------------------------------------------------------------------


async def test_vec_knn_returns_closest_first(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    close = make_entry(kind=MemoryKind.EPISODIC, content="close")
    far = make_entry(kind=MemoryKind.EPISODIC, content="far")
    close_vec = [1.0] + [0.0] * 767
    far_vec = [0.0, 1.0] + [0.0] * 766
    query = [0.99, 0.01] + [0.0] * 766

    await store.add(close, embedding=close_vec)
    await store.add(far, embedding=far_vec)

    hits = await store.knn_ids(query, k=2)
    assert len(hits) == 2
    assert hits[0][0] == close.id
    assert hits[0][1] <= hits[1][1]


async def test_vec_knn_respects_candidate_restriction(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
    unit_embedding: list[float],
) -> None:
    e1 = make_entry(content="one")
    e2 = make_entry(content="two")
    await store.add(e1, embedding=unit_embedding)
    await store.add(e2, embedding=unit_embedding)

    hits = await store.knn_ids(unit_embedding, k=2, candidate_ids=[e1.id])
    assert [mid for mid, _ in hits] == [e1.id]


# ---------------------------------------------------------------------------
# List / mark_recalled / evict
# ---------------------------------------------------------------------------


async def test_list_by_agent_filters_and_orders(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    now = datetime.now(tz=UTC)
    old = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="old",
        created_at=now - timedelta(days=2),
    )
    new = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="new",
        created_at=now,
    )
    other = make_entry(
        agent_id="nietzsche",
        kind=MemoryKind.EPISODIC,
        content="other",
        created_at=now,
    )
    for e in (old, new, other):
        await store.add(e, embedding=None)

    results = await store.list_by_agent("kant", MemoryKind.EPISODIC)
    assert [r.content for r in results] == ["new", "old"]
    assert all(r.agent_id == "kant" for r in results)


async def test_list_world_scope_excludes_self(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    mine = make_entry(agent_id="kant", content="mine")
    theirs = make_entry(agent_id="nietzsche", content="theirs")
    await store.add(mine, embedding=None)
    await store.add(theirs, embedding=None)

    results = await store.list_world_scope("kant", MemoryKind.EPISODIC)
    assert [r.agent_id for r in results] == ["nietzsche"]


async def test_mark_recalled_updates_all_tables(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
) -> None:
    ep = make_entry(kind=MemoryKind.EPISODIC, content="ep")
    se = make_entry(kind=MemoryKind.SEMANTIC, content="se")
    await store.add(ep, embedding=None)
    await store.add(se, embedding=None)

    await store.mark_recalled([ep.id, se.id])

    ep_after = await store.get_by_id(ep.id)
    se_after = await store.get_by_id(se.id)
    assert ep_after is not None
    assert se_after is not None
    assert ep_after.recall_count == 1
    assert se_after.recall_count == 1
    assert ep_after.last_recalled_at is not None
    assert se_after.last_recalled_at is not None


async def test_mark_recalled_noop_on_empty(
    store: MemoryStore,
) -> None:
    # Should not raise.
    await store.mark_recalled([])


async def test_evict_episodic_before_returns_and_deletes(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
    unit_embedding: list[float],
) -> None:
    now = datetime.now(tz=UTC)
    old = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="old",
        created_at=now - timedelta(hours=2),
    )
    fresh = make_entry(
        agent_id="kant",
        kind=MemoryKind.EPISODIC,
        content="fresh",
        created_at=now,
    )
    semantic = make_entry(
        agent_id="kant",
        kind=MemoryKind.SEMANTIC,
        content="should not be evicted",
        created_at=now - timedelta(hours=3),
    )
    for e in (old, fresh, semantic):
        await store.add(e, embedding=unit_embedding)

    evicted = await store.evict_episodic_before(
        "kant",
        created_before=now - timedelta(hours=1),
    )
    assert [e.id for e in evicted] == [old.id]

    # ``old`` should be gone from both content and vec tables.
    assert await store.get_by_id(old.id) is None
    assert await store.get_embedding(old.id) is None
    # ``fresh`` (episodic, newer) and ``semantic`` must survive.
    assert await store.get_by_id(fresh.id) is not None
    assert await store.get_by_id(semantic.id) is not None


async def test_get_by_id_missing_returns_none(store: MemoryStore) -> None:
    assert await store.get_by_id("does-not-exist") is None


# ---------------------------------------------------------------------------
# Concurrent access regression (M6 live — 2026-04-22)
# ---------------------------------------------------------------------------


async def test_concurrent_add_does_not_raise_systemerror(
    store: MemoryStore,
    make_entry: Callable[..., MemoryEntry],
    unit_embedding: list[float],
) -> None:
    """Cognition ticks fan out via asyncio.gather → asyncio.to_thread.

    Before the M6 live verification patch, every sync DB method used the
    shared ``sqlite3.Connection`` without holding a lock, so two concurrent
    ``asyncio.to_thread(self._add_sync, ...)`` calls (3 agents per tick,
    multiple observations each) raced at ``conn.__enter__`` and raised
    ``SystemError: error return without exception set`` under Python 3.11
    with ``sqlite3.threadsafety == 1``.

    The regression guard launches 24 concurrent ``add`` calls (the count
    seen in live logs: 3 agents × 8 cognition ticks) and asserts no
    exception escapes. With the RLock in place every call returns the
    ``entry.id`` and every row becomes retrievable.
    """
    entries = [make_entry(content=f"concurrent-{i}") for i in range(24)]
    ids = await asyncio.gather(
        *(store.add(e, embedding=unit_embedding) for e in entries),
    )
    assert ids == [e.id for e in entries]
    # All rows landed — nothing was lost to a silent conn corruption.
    for e in entries:
        fetched = await store.get_by_id(e.id)
        assert fetched is not None
        assert fetched.content == e.content


# ---------------------------------------------------------------------------
# Dialog turn log (M8 L6-D1 precondition)
# ---------------------------------------------------------------------------


def _turn(
    *,
    dialog_id: str = "d_test_0001",
    turn_index: int = 0,
    speaker: str = "a_kant_001",
    addressee: str = "a_nietzsche_001",
    utterance: str = "guten Tag",
    tick: int = 10,
):  # type: ignore[no-untyped-def]
    from erre_sandbox.schemas import DialogTurnMsg

    return DialogTurnMsg(
        tick=tick,
        dialog_id=dialog_id,
        speaker_id=speaker,
        addressee_id=addressee,
        utterance=utterance,
        turn_index=turn_index,
    )


def test_add_dialog_turn_inserts_row(store: MemoryStore) -> None:
    turn = _turn()
    row_id = store.add_dialog_turn_sync(
        turn,
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    assert row_id == "dt_d_test_0001_0000"

    rows = list(store.iter_dialog_turns())
    assert len(rows) == 1
    row = rows[0]
    assert row["dialog_id"] == "d_test_0001"
    assert row["turn_index"] == 0
    assert row["speaker_persona_id"] == "kant"
    assert row["addressee_persona_id"] == "nietzsche"
    assert row["utterance"] == "guten Tag"


def test_add_dialog_turn_is_idempotent_on_duplicate(store: MemoryStore) -> None:
    """Re-inserting the same (dialog_id, turn_index) must be a no-op."""
    turn = _turn(utterance="first")
    store.add_dialog_turn_sync(
        turn,
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    # Second call with a different utterance — INSERT OR IGNORE keeps original.
    again = _turn(utterance="second")
    store.add_dialog_turn_sync(
        again,
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    rows = list(store.iter_dialog_turns())
    assert len(rows) == 1
    assert rows[0]["utterance"] == "first"


def test_iter_dialog_turns_filters_by_persona(store: MemoryStore) -> None:
    store.add_dialog_turn_sync(
        _turn(turn_index=0, speaker="a_kant_001"),
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    store.add_dialog_turn_sync(
        _turn(turn_index=1, speaker="a_rikyu_001"),
        speaker_persona_id="rikyu",
        addressee_persona_id="nietzsche",
    )
    store.add_dialog_turn_sync(
        _turn(turn_index=2, speaker="a_kant_001"),
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )

    kant_rows = list(store.iter_dialog_turns(persona="kant"))
    assert {r["turn_index"] for r in kant_rows} == {0, 2}

    rikyu_rows = list(store.iter_dialog_turns(persona="rikyu"))
    assert {r["turn_index"] for r in rikyu_rows} == {1}

    all_rows = list(store.iter_dialog_turns())
    assert len(all_rows) == 3


def test_iter_dialog_turns_filters_by_since(store: MemoryStore) -> None:
    """``since`` drops rows whose created_at is before the cutoff."""
    store.add_dialog_turn_sync(
        _turn(turn_index=0),
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    # Cutoff strictly in the future — everything should be dropped.
    future = datetime.now(tz=UTC) + timedelta(hours=1)
    assert list(store.iter_dialog_turns(since=future)) == []

    # Cutoff far in the past — everything should be kept.
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    rows = list(store.iter_dialog_turns(since=past))
    assert len(rows) == 1


def test_dialog_turn_count_by_persona_query(store: MemoryStore) -> None:
    """The canonical M9-readiness query returns per-persona turn counts."""
    for i, persona in enumerate(["kant", "kant", "rikyu", "nietzsche", "kant"]):
        store.add_dialog_turn_sync(
            _turn(turn_index=i, speaker=f"a_{persona}_001"),
            speaker_persona_id=persona,
            addressee_persona_id="rikyu",
        )

    # Execute the shipped SQL against the in-memory DB and assert the shape.
    conn = store._ensure_conn()  # noqa: SLF001 — test-only access is acceptable
    with store._conn_lock:  # noqa: SLF001
        rows = conn.execute(
            "SELECT speaker_persona_id, COUNT(*) AS turns "
            "FROM dialog_turns GROUP BY speaker_persona_id ORDER BY turns DESC",
        ).fetchall()
    counts = {r["speaker_persona_id"]: r["turns"] for r in rows}
    assert counts == {"kant": 3, "rikyu": 1, "nietzsche": 1}


# ---------------------------------------------------------------------------
# Bias fired events (M8 baseline-quality-metric)
# ---------------------------------------------------------------------------


def _seed_bias_event(
    store: MemoryStore,
    *,
    tick: int = 10,
    agent_id: str = "a_kant_001",
    persona_id: str = "kant",
    from_zone: str = "agora",
    to_zone: str = "peripatos",
    bias_p: float = 0.2,
) -> str:
    return store.add_bias_event_sync(
        tick=tick,
        agent_id=agent_id,
        persona_id=persona_id,
        from_zone=from_zone,
        to_zone=to_zone,
        bias_p=bias_p,
    )


def test_add_bias_event_inserts_row(store: MemoryStore) -> None:
    row_id = _seed_bias_event(store)
    assert row_id.startswith("be_")

    rows = list(store.iter_bias_events())
    assert len(rows) == 1
    row = rows[0]
    assert row["agent_id"] == "a_kant_001"
    assert row["persona_id"] == "kant"
    assert row["from_zone"] == "agora"
    assert row["to_zone"] == "peripatos"
    assert abs(float(row["bias_p"]) - 0.2) < 1e-9


def test_add_bias_event_allows_multiple_per_tick(store: MemoryStore) -> None:
    """No UNIQUE constraint — two firings on the same tick must both persist."""
    _seed_bias_event(store, tick=5, agent_id="a_kant_001")
    _seed_bias_event(store, tick=5, agent_id="a_kant_001")
    assert len(list(store.iter_bias_events())) == 2


def test_iter_bias_events_filters_by_persona(store: MemoryStore) -> None:
    _seed_bias_event(store, tick=1, persona_id="kant")
    _seed_bias_event(store, tick=2, persona_id="rikyu")
    _seed_bias_event(store, tick=3, persona_id="kant")

    kant_rows = list(store.iter_bias_events(persona="kant"))
    assert {r["tick"] for r in kant_rows} == {1, 3}

    rikyu_rows = list(store.iter_bias_events(persona="rikyu"))
    assert {r["tick"] for r in rikyu_rows} == {2}


def test_iter_bias_events_filters_by_since(store: MemoryStore) -> None:
    _seed_bias_event(store)
    future = datetime.now(tz=UTC) + timedelta(hours=1)
    assert list(store.iter_bias_events(since=future)) == []
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    assert len(list(store.iter_bias_events(since=past))) == 1
