"""Unit tests for :mod:`erre_sandbox.bootstrap`.

The full ``bootstrap()`` coroutine is exercised by e2e live verification
(G-GEAR side, see ``.steering/20260419-m2-functional-closure/evidence/``).
Here we cover the deterministic helper functions that can fail in
non-trivial ways: YAML loading, initial-state construction, and the new
Ollama ``health_check`` probe.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

import httpx
import pytest

from erre_sandbox.bootstrap import (
    BootConfig,
    _build_kant_initial_state,
    _load_kant_persona,
    _supervise,
)
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.inference.ollama_adapter import OllamaUnavailableError
from erre_sandbox.schemas import ERREModeName, PersonaSpec, Zone

# ---------------------------------------------------------------------------
# _load_kant_persona
# ---------------------------------------------------------------------------


def test_load_kant_persona_reads_repo_yaml() -> None:
    """The bundled ``personas/kant.yaml`` validates as :class:`PersonaSpec`."""
    cfg = BootConfig(personas_dir=Path("personas"))
    persona = _load_kant_persona(cfg)
    assert isinstance(persona, PersonaSpec)
    assert persona.persona_id == "kant"


def test_load_kant_persona_honours_personas_dir(tmp_path: Path) -> None:
    """``cfg.personas_dir`` is respected so tests can inject fixtures."""
    src = Path("personas/kant.yaml").read_text(encoding="utf-8")
    (tmp_path / "kant.yaml").write_text(src, encoding="utf-8")
    persona = _load_kant_persona(BootConfig(personas_dir=tmp_path))
    assert persona.persona_id == "kant"


# ---------------------------------------------------------------------------
# _build_kant_initial_state
# ---------------------------------------------------------------------------


def test_build_kant_initial_state_is_in_peripatos() -> None:
    state = _build_kant_initial_state()
    assert state.agent_id == "a_kant_001"
    assert state.persona_id == "kant"
    assert state.position.zone is Zone.PERIPATOS


def test_build_kant_initial_state_erre_mode_is_peripatetic() -> None:
    state = _build_kant_initial_state()
    assert state.erre.name is ERREModeName.PERIPATETIC
    assert state.erre.entered_at_tick == 0


# ---------------------------------------------------------------------------
# OllamaChatClient.health_check
# ---------------------------------------------------------------------------


async def _make_client_with(
    handler: httpx.MockTransport | None = None,
) -> OllamaChatClient:
    transport = handler or httpx.MockTransport(
        lambda _req: httpx.Response(200, json={"models": []}),
    )
    client = httpx.AsyncClient(
        base_url=OllamaChatClient.DEFAULT_ENDPOINT,
        transport=transport,
    )
    return OllamaChatClient(client=client)


async def test_health_check_passes_on_200() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.path)
        return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})

    async with await _make_client_with(httpx.MockTransport(handler)) as ollama:
        await ollama.health_check()
    assert captured == ["/api/tags"]


async def test_health_check_raises_on_500() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(500))
    async with await _make_client_with(transport) as ollama:
        with pytest.raises(OllamaUnavailableError, match="500"):
            await ollama.health_check()


async def test_health_check_raises_on_connect_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(handler)
    async with await _make_client_with(transport) as ollama:
        with pytest.raises(OllamaUnavailableError, match="unreachable"):
            await ollama.health_check()


# ---------------------------------------------------------------------------
# BootConfig
# ---------------------------------------------------------------------------


def test_bootconfig_is_frozen() -> None:
    cfg = BootConfig()
    with pytest.raises((AttributeError, TypeError)):
        cfg.port = 9000  # type: ignore[misc]


def test_bootconfig_defaults_match_mvp_requirements() -> None:
    cfg = BootConfig()
    assert cfg.port == 8000
    assert cfg.chat_model == "qwen3:8b"
    assert cfg.check_ollama is True
    assert cfg.ollama_url == "http://127.0.0.1:11434"


# ---------------------------------------------------------------------------
# _supervise
# ---------------------------------------------------------------------------


class _FakeRuntime:
    """Minimal WorldRuntime stand-in for supervision tests."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self.stop_called = False

    async def run(self) -> None:
        await self._stop_event.wait()

    def stop(self) -> None:
        self.stop_called = True
        self._stop_event.set()


class _FakeServer:
    """Minimal uvicorn.Server stand-in."""

    def __init__(self) -> None:
        self.should_exit = False
        self._exit_event = asyncio.Event()

    async def serve(self) -> None:
        # Poll ``should_exit`` via a short-lived waiter; _supervise sets it
        # directly (not via _exit_event) so we consult both.
        while not self.should_exit:
            with suppress(TimeoutError):
                await asyncio.wait_for(self._exit_event.wait(), timeout=0.02)


async def test_supervise_returns_cleanly_when_stop_event_fires() -> None:
    runtime = _FakeRuntime()
    server = _FakeServer()
    stop_event = asyncio.Event()

    async def _trip() -> None:
        await asyncio.sleep(0.05)
        stop_event.set()

    await asyncio.gather(
        _supervise(runtime, server, stop_event),  # type: ignore[arg-type]
        _trip(),
    )

    assert server.should_exit is True
    assert runtime.stop_called is True


async def test_supervise_reraises_runtime_exception() -> None:
    class _FailingRuntime(_FakeRuntime):
        async def run(self) -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError("boom")

    runtime = _FailingRuntime()
    server = _FakeServer()
    stop_event = asyncio.Event()

    with pytest.raises(RuntimeError, match="boom"):
        await _supervise(runtime, server, stop_event)  # type: ignore[arg-type]

    # Even after exception, both shutdown signals must have fired.
    assert server.should_exit is True
    assert runtime.stop_called is True
