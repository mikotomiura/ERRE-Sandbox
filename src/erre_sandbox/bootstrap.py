"""Composition root for the ERRE-Sandbox 1-Kant walker orchestrator.

This module is the sole wiring point between the contract-level gateway
(``integration.gateway``) and the real ``WorldRuntime`` + cognition +
memory + inference stack. It closes GAP-1 (`_NullRuntime` dependency) so
that MASTER-PLAN §4.4 MVP functional criteria can be PASS'd.

Design rationale: see ``.steering/20260419-m2-functional-closure/design.md``.
The hybrid approach keeps composition in a single module (testable via
:func:`bootstrap`) while the CLI shell lives in ``__main__.py``.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

import uvicorn
import yaml

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.integration.gateway import make_app
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import (
    AgentState,
    ERREMode,
    ERREModeName,
    PersonaSpec,
    Position,
    Zone,
)
from erre_sandbox.world import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BootConfig:
    """Immutable orchestrator configuration.

    Instantiated once by ``__main__.cli`` from argparse, then passed into
    :func:`bootstrap`. Kept frozen so tests cannot mutate it across awaits.
    """

    host: str = "0.0.0.0"  # noqa: S104 — LAN only by design
    port: int = 8000
    db_path: str = "var/kant.db"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    ollama_url: str = "http://127.0.0.1:11434"
    check_ollama: bool = True
    log_level: str = "info"
    personas_dir: Path = field(default_factory=lambda: Path("personas"))


def _load_kant_persona(cfg: BootConfig) -> PersonaSpec:
    """Read ``personas/kant.yaml`` and validate into :class:`PersonaSpec`.

    Raises ``FileNotFoundError`` with a friendly message when the file is
    absent — orchestrator startup fails loudly rather than surfacing an
    opaque stack trace several levels deep.
    """
    path = cfg.personas_dir / "kant.yaml"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Kant persona YAML not found at {path!s}. "
            "Check cwd or pass --personas-dir pointing at the repository's "
            "personas/ directory.",
        ) from exc
    data = yaml.safe_load(raw)
    return PersonaSpec.model_validate(data)


def _build_kant_initial_state() -> AgentState:
    """Kant starts at peripatos centre in PERIPATETIC ERRE mode.

    Destination is set on the first cognition tick (10s after launch); until
    then the avatar stands still. This is acceptable for MVP — MASTER-PLAN
    §4.4 #4 requires 30Hz rendering, and WorldTickMsg heartbeats emit at 1Hz
    while physics ticks update ``position`` at 30Hz once the agent has a plan.
    """
    return AgentState(
        agent_id="a_kant_001",
        persona_id="kant",
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.PERIPATOS),
        erre=ERREMode(name=ERREModeName.PERIPATETIC, entered_at_tick=0),
    )


async def bootstrap(cfg: BootConfig) -> None:
    """Construct the full stack and supervise runtime + uvicorn.

    Resource lifecycle is structured via :class:`AsyncExitStack` so any
    exception during construction (or later during ``TaskGroup``) still
    invokes every ``close`` in LIFO order. OS signals (SIGINT / SIGTERM) are
    caught explicitly; without this the ``uvicorn.Server`` default handler
    intercepts Ctrl-C but the ``WorldRuntime`` task keeps running, which is
    the class of silent failure that T19 spent hours debugging.
    """
    logging.basicConfig(
        level=cfg.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        # force=True なので、既に handler が登録済 (e.g. pytest caplog) でも
        # bootstrap 呼び出しで root ロガー設定を上書きする。
        force=True,
    )

    async with AsyncExitStack() as stack:
        memory = MemoryStore(db_path=cfg.db_path)
        stack.push_async_callback(memory.close)

        embedding = EmbeddingClient(model=cfg.embed_model, endpoint=cfg.ollama_url)
        stack.push_async_callback(embedding.close)

        inference = OllamaChatClient(model=cfg.chat_model, endpoint=cfg.ollama_url)
        stack.push_async_callback(inference.close)

        if cfg.check_ollama:
            logger.info(
                "[bootstrap] health_check %s (model=%s)",
                cfg.ollama_url,
                cfg.chat_model,
            )
            await inference.health_check()

        retriever = Retriever(memory, embedding)
        cycle = CognitionCycle(
            retriever=retriever,
            store=memory,
            embedding=embedding,
            llm=inference,
        )
        runtime = WorldRuntime(cycle=cycle)
        runtime.register_agent(_build_kant_initial_state(), _load_kant_persona(cfg))

        app = make_app(runtime=runtime)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=cfg.host,
                port=cfg.port,
                log_level=cfg.log_level,
                lifespan="on",
            ),
        )
        # Disable uvicorn's own signal handler — we handle SIGINT/SIGTERM below.
        # Depends on uvicorn's private contract; verified against the version
        # pinned in pyproject.toml (>=0.30,<1). Re-verify on any uvicorn bump.
        cast("object", server).install_signal_handlers = lambda: None  # type: ignore[attr-defined]

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop_event.set)

        logger.info(
            "[bootstrap] starting (host=%s port=%s db=%s)",
            cfg.host,
            cfg.port,
            cfg.db_path,
        )
        await _supervise(runtime, server, stop_event)
        logger.info("[bootstrap] shutdown complete")


async def _supervise(
    runtime: WorldRuntime,
    server: uvicorn.Server,
    stop_event: asyncio.Event,
) -> None:
    """Run runtime + server concurrently; stop both when any signals done.

    Uses ``asyncio.wait(FIRST_COMPLETED)`` rather than ``TaskGroup`` so that
    a runtime exception propagates after graceful uvicorn shutdown instead
    of being wrapped in ``ExceptionGroup`` (which is noisier at the CLI).
    """
    runtime_task = asyncio.create_task(runtime.run(), name="world-runtime")
    server_task = asyncio.create_task(server.serve(), name="uvicorn")
    stop_task = asyncio.create_task(stop_event.wait(), name="signal-wait")

    done, pending = await asyncio.wait(
        {runtime_task, server_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Trigger graceful shutdown of both tasks regardless of who finished first.
    server.should_exit = True
    runtime.stop()

    # The stop_task is a pure ``stop_event.wait()`` — if we didn't exit via
    # signal, it will never complete, so cancel it explicitly before awaiting.
    if not stop_task.done():
        stop_task.cancel()

    awaitables: list[Awaitable[object]] = list(pending)
    for task in awaitables:
        try:
            await task
        except asyncio.CancelledError:
            # Expected: we cancelled runtime_task via runtime.stop() above,
            # or stop_task via the explicit cancel() just above.
            pass
        except Exception:
            # Unexpected: log so operators can debug instead of swallowing
            # the failure silently (T19 ghost session class of bugs).
            logger.exception(
                "pending task %s raised during shutdown",
                getattr(task, "get_name", lambda: "?")(),
            )

    # Re-raise the first task exception (if any) so the CLI exits non-zero.
    for task in done:
        if task is stop_task:
            continue
        exc = task.exception()
        if exc is not None:
            raise exc


__all__ = ["BootConfig", "bootstrap"]
