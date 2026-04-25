"""Shared fixtures for ``tests/test_integration``.

This conftest serves three audiences:

* **T14 gateway tests** (``test_gateway.py``) — the ``MockRuntime``,
  ``app``, ``client``, and ``fast_timeouts`` fixtures below provide a
  lightweight harness for exercising the WebSocket gateway without pulling
  in the whole world-runtime stack.
* **T19 execution-phase scenario tests** (``test_scenario_*.py``) — now
  live (skip removed); the frozen :class:`Scenario` / :class:`Thresholds`
  fixtures are their one-line entry points, plus :class:`FakeEmbedder` and
  :func:`memory_store_with_fake_embedder` for the memory-write Layer B2
  path.
* **T20 acceptance observability** — :func:`m2_logger` writes structured
  jsonl records when env var ``M2_LOG_PATH`` is set (no-op otherwise,
  keeping CI output clean).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from erre_sandbox.integration import (
    M2_THRESHOLDS,
    SCENARIO_MEMORY_WRITE,
    SCENARIO_TICK_ROBUSTNESS,
    SCENARIO_WALKING,
    Scenario,
    Thresholds,
    make_app,
    protocol,
)
from erre_sandbox.memory import (
    DEFAULT_EMBED_DIM,
    DOC_PREFIX,
    QUERY_PREFIX,
    MemoryStore,
)
from erre_sandbox.schemas import PropLayout, WorldLayoutMsg, ZoneLayout

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from fastapi import FastAPI

    from erre_sandbox.schemas import ControlEnvelope


@pytest.fixture
def walking_scenario() -> Scenario:
    """Return the S_WALKING scenario (Kant × Peripatos baseline)."""
    return SCENARIO_WALKING


@pytest.fixture
def memory_write_scenario() -> Scenario:
    """Return the S_MEMORY_WRITE scenario."""
    return SCENARIO_MEMORY_WRITE


@pytest.fixture
def tick_robustness_scenario() -> Scenario:
    """Return the S_TICK_ROBUSTNESS scenario."""
    return SCENARIO_TICK_ROBUSTNESS


@pytest.fixture
def thresholds() -> Thresholds:
    """Return the frozen :class:`Thresholds` used in M2 acceptance."""
    return M2_THRESHOLDS


# =============================================================================
# T14 gateway fixtures
# =============================================================================


class MockRuntime:
    """Minimal :class:`RuntimeLike` for gateway tests.

    Tests drive the gateway by calling :meth:`put` which makes the next
    :meth:`recv_envelope` yield that envelope. Mirrors
    :meth:`WorldRuntime.recv_envelope` semantics (blocking FIFO) without
    pulling in the world layer.

    M7γ adds :meth:`layout_snapshot` so the gateway's on-connect emit
    has a stub to call. Tests that want to assert specific layout shapes
    can supply ``zones`` / ``props`` at construction time.
    """

    def __init__(
        self,
        *,
        layout_zones: list[ZoneLayout] | None = None,
        layout_props: list[PropLayout] | None = None,
    ) -> None:
        self._queue: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
        self._layout_zones = layout_zones if layout_zones is not None else []
        self._layout_props = layout_props if layout_props is not None else []

    async def recv_envelope(self) -> ControlEnvelope:
        return await self._queue.get()

    async def put(self, env: ControlEnvelope) -> None:
        await self._queue.put(env)

    def layout_snapshot(self, *, tick: int = 0) -> WorldLayoutMsg:
        return WorldLayoutMsg(
            tick=tick,
            zones=list(self._layout_zones),
            props=list(self._layout_props),
        )


@pytest.fixture
def mock_runtime() -> MockRuntime:
    return MockRuntime()


@pytest.fixture
def app(mock_runtime: MockRuntime) -> FastAPI:
    return make_app(runtime=mock_runtime)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Sync TestClient with lifespan-managed broadcaster task."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fast_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink session timing constants to keep tests sub-second.

    ``gateway.py`` reads these constants through the ``protocol`` module
    on every use, so patching the module attributes is sufficient.
    """
    monkeypatch.setattr(protocol, "HANDSHAKE_TIMEOUT_S", 0.3)
    monkeypatch.setattr(protocol, "IDLE_DISCONNECT_S", 0.5)
    monkeypatch.setattr(protocol, "MAX_ENVELOPE_BACKLOG", 4)


# =============================================================================
# T19 execution-phase fixtures (Layer B2 memory + observability)
# =============================================================================


class FakeEmbedder:
    """Deterministic embedder used by Layer B2 memory tests.

    Mirrors :class:`erre_sandbox.memory.EmbeddingClient` duck-typed methods
    (``embed_document`` / ``embed_query``) but produces stable 768-d vectors
    from a SHA-256 digest of the prefixed text. The exposed ``last_docs`` /
    ``last_queries`` lists let tests assert that the correct prefix was
    applied at the call site — the T10 D5 contract.

    Intentionally kept in ``tests/`` so the test-only fake never leaks into
    the production dependency graph (decisions.md D1).
    """

    def __init__(self) -> None:
        self.last_docs: list[str] = []
        self.last_queries: list[str] = []

    async def embed_document(self, text: str) -> list[float]:
        prefixed = f"{DOC_PREFIX}{text}"
        self.last_docs.append(prefixed)
        return self._vec(prefixed)

    async def embed_query(self, text: str) -> list[float]:
        prefixed = f"{QUERY_PREFIX}{text}"
        self.last_queries.append(prefixed)
        return self._vec(prefixed)

    @staticmethod
    def _vec(seed: str) -> list[float]:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        # 768 floats in [-1.0, 1.0], cycling the 32-byte digest deterministically.
        return [
            (digest[i % len(digest)] / 127.5) - 1.0 for i in range(DEFAULT_EMBED_DIM)
        ]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """Return a fresh :class:`FakeEmbedder` per test."""
    return FakeEmbedder()


@pytest_asyncio.fixture
async def memory_store_with_fake_embedder(
    fake_embedder: FakeEmbedder,
) -> AsyncIterator[tuple[MemoryStore, FakeEmbedder]]:
    """In-memory :class:`MemoryStore` paired with :class:`FakeEmbedder`.

    Schema is created eagerly; the store is closed on teardown to keep each
    test isolated (no cross-test sqlite state leak).
    """
    store = MemoryStore(":memory:")
    store.create_schema()
    try:
        yield store, fake_embedder
    finally:
        await store.close()


_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_ALLOWED_LOG_ROOT: Final[Path] = (_PROJECT_ROOT / "logs").resolve()


class M2LogPathError(ValueError):
    """Raised when ``M2_LOG_PATH`` resolves outside ``<project>/logs/``."""


class M2Logger:
    """Opt-in jsonl logger for T20 acceptance runs.

    When ``M2_LOG_PATH`` is unset, :meth:`log` is a no-op so CI stays clean.
    When set, the path must resolve inside ``<project>/logs/`` — any other
    location (absolute or traversal via ``..``) raises
    :class:`M2LogPathError` so an accidental or hostile env var cannot
    write to arbitrary filesystem locations.
    """

    def __init__(self, path: str | None) -> None:
        if not path:
            self._path: Path | None = None
            return
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(_ALLOWED_LOG_ROOT)
        except ValueError as exc:  # relative_to raises ValueError on mismatch
            raise M2LogPathError(
                f"M2_LOG_PATH must be inside {_ALLOWED_LOG_ROOT}; got {resolved}",
            ) from exc
        self._path = resolved
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, **fields: Any) -> None:
        if self._path is None:
            return
        record = {"ts": datetime.now(tz=UTC).isoformat(), **fields}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


@pytest.fixture
def m2_logger() -> M2Logger:
    """Return an :class:`M2Logger` honouring the ``M2_LOG_PATH`` env var."""
    return M2Logger(os.environ.get("M2_LOG_PATH"))
