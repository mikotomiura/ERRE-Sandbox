"""Shared fixtures for ``tests/test_integration``.

This conftest serves two audiences:

* **T14 gateway tests** (``test_gateway.py``) — the ``MockRuntime``,
  ``app``, ``client``, and ``fast_timeouts`` fixtures below provide a
  lightweight harness for exercising the WebSocket gateway without pulling
  in the whole world-runtime stack.
* **T19 E2E skeleton tests** (``test_scenario_*.py``) — currently marked
  ``@pytest.mark.skip`` pending the T19 execution phase; the frozen
  :class:`Scenario` / :class:`Thresholds` fixtures are kept here as their
  one-line entry points.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
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

if TYPE_CHECKING:
    from collections.abc import Iterator

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
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ControlEnvelope] = asyncio.Queue()

    async def recv_envelope(self) -> ControlEnvelope:
        return await self._queue.get()

    async def put(self, env: ControlEnvelope) -> None:
        await self._queue.put(env)


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
