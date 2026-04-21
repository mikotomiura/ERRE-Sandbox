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
    _build_initial_state,
    _load_persona_registry,
    _load_persona_yaml,
    _supervise,
)
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.inference.ollama_adapter import OllamaUnavailableError
from erre_sandbox.schemas import (
    AgentSpec,
    ERREModeName,
    PersonaSpec,
    Zone,
)

# ---------------------------------------------------------------------------
# _load_persona_yaml
# ---------------------------------------------------------------------------


def test_load_persona_yaml_reads_repo_kant() -> None:
    """The bundled ``personas/kant.yaml`` validates as :class:`PersonaSpec`."""
    persona = _load_persona_yaml(Path("personas"), "kant")
    assert isinstance(persona, PersonaSpec)
    assert persona.persona_id == "kant"


def test_load_persona_yaml_honours_custom_dir(tmp_path: Path) -> None:
    """Caller-supplied ``personas_dir`` is respected so tests can inject fixtures."""
    src = Path("personas/kant.yaml").read_text(encoding="utf-8")
    (tmp_path / "kant.yaml").write_text(src, encoding="utf-8")
    persona = _load_persona_yaml(tmp_path, "kant")
    assert persona.persona_id == "kant"


def test_load_persona_yaml_loads_nietzsche_and_rikyu() -> None:
    """M4 personas load without contract violations."""
    for pid in ("nietzsche", "rikyu"):
        persona = _load_persona_yaml(Path("personas"), pid)
        assert persona.persona_id == pid


@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "a/b", "a..b", "Kant", "_leading", ""],
)
def test_load_persona_yaml_rejects_unsafe_persona_id(
    hostile: str,
    tmp_path: Path,
) -> None:
    """The regex guard fires before any filesystem access."""
    with pytest.raises(ValueError, match="not a safe YAML filename"):
        _load_persona_yaml(tmp_path, hostile)


# ---------------------------------------------------------------------------
# _build_initial_state
# ---------------------------------------------------------------------------


def _load_kant_for_tests() -> PersonaSpec:
    return _load_persona_yaml(Path("personas"), "kant")


def test_build_initial_state_derives_agent_id_from_persona() -> None:
    spec = AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS)
    state = _build_initial_state(spec, _load_kant_for_tests())
    assert state.agent_id == "a_kant_001"
    assert state.persona_id == "kant"
    assert state.position.zone is Zone.PERIPATOS


def test_build_initial_state_picks_erre_mode_from_zone() -> None:
    spec = AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS)
    state = _build_initial_state(spec, _load_kant_for_tests())
    assert state.erre.name is ERREModeName.PERIPATETIC
    assert state.erre.entered_at_tick == 0


def test_build_initial_state_maps_chashitsu_to_chashitsu_mode() -> None:
    spec = AgentSpec(persona_id="kant", initial_zone=Zone.CHASHITSU)
    state = _build_initial_state(spec, _load_kant_for_tests())
    assert state.erre.name is ERREModeName.CHASHITSU


def test_build_initial_state_maps_study_to_deep_work() -> None:
    spec = AgentSpec(persona_id="kant", initial_zone=Zone.STUDY)
    state = _build_initial_state(spec, _load_kant_for_tests())
    assert state.erre.name is ERREModeName.DEEP_WORK


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


def test_bootconfig_default_fills_with_single_kant_spec() -> None:
    """Empty ``agents`` resolves to the M2 back-compat 1-Kant default.

    The original M4 #1 contract used an empty tuple to signal "fall back"; M4 #6
    materialises that fallback inside ``__post_init__`` so the orchestrator
    body can iterate over ``cfg.agents`` without branching on emptiness.
    """
    cfg = BootConfig()
    assert cfg.agents == (AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),)


def test_bootconfig_preserves_explicit_agents() -> None:
    specs = (
        AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),
        AgentSpec(persona_id="nietzsche", initial_zone=Zone.PERIPATOS),
        AgentSpec(persona_id="rikyu", initial_zone=Zone.CHASHITSU),
    )
    cfg = BootConfig(agents=specs)
    assert cfg.agents == specs


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


# ---------------------------------------------------------------------------
# _load_persona_registry — M5 orchestrator-integration
# ---------------------------------------------------------------------------


def test_load_persona_registry_builds_dict_for_each_agent() -> None:
    """Each unique persona_id in cfg.agents produces exactly one registry entry."""
    cfg = BootConfig(
        agents=(
            AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),
            AgentSpec(persona_id="nietzsche", initial_zone=Zone.PERIPATOS),
            AgentSpec(persona_id="rikyu", initial_zone=Zone.CHASHITSU),
        ),
    )
    registry = _load_persona_registry(cfg)
    assert set(registry.keys()) == {"kant", "nietzsche", "rikyu"}
    assert all(isinstance(p, PersonaSpec) for p in registry.values())
    assert registry["kant"].persona_id == "kant"


def test_load_persona_registry_deduplicates_repeated_persona_ids() -> None:
    """Same persona_id registered twice results in a single registry entry."""
    cfg = BootConfig(
        agents=(
            AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),
            AgentSpec(persona_id="kant", initial_zone=Zone.STUDY),
        ),
    )
    registry = _load_persona_registry(cfg)
    assert list(registry.keys()) == ["kant"]
