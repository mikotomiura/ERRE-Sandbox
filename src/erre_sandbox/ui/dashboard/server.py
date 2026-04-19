"""FastAPI app + WebSocket handler for the dashboard (T18).

The app has two routes:

* ``GET /dashboard`` — returns :data:`HTML_TEMPLATE` as ``text/html``.
* ``GET /ws/dashboard`` — WebSocket that pushes a :class:`SnapshotMsg` on
  connect, then :class:`DeltaMsg` per ingested envelope and :class:`AlertMsg`
  on threshold violations.

The stub envelope stream runs as a single background task per app instance,
feeding the shared :class:`DashboardState`. Each client has its own queue of
outgoing UI messages so a slow viewer cannot block the rest.

See ``.steering/20260419-ui-dashboard-minimal/design.md`` §Implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from erre_sandbox.ui.dashboard.html import HTML_TEMPLATE
from erre_sandbox.ui.dashboard.messages import (
    AlertMsg,
    DeltaMsg,
    SnapshotMsg,
    UiMessage,
)
from erre_sandbox.ui.dashboard.state import DashboardState
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from erre_sandbox.schemas import ControlEnvelope

logger = logging.getLogger(__name__)

_SUBSCRIBER_QUEUE_MAX = 128


def create_app(  # noqa: C901, PLR0915  # factory wires 5 closures + lifespan
    *,
    stub_seed: int = 0,
    stub_interval_s: float = 1.0,
    enable_stub: bool = True,
) -> FastAPI:
    """Build a fresh FastAPI app wired to its own :class:`DashboardState`."""
    state = DashboardState()
    subscribers: set[asyncio.Queue[UiMessage]] = set()

    async def broadcast(msg: UiMessage) -> None:
        for q in list(subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning("dashboard subscriber queue full; dropping oldest")
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(msg)

    async def handle_envelope(
        envelope: ControlEnvelope,
        latency_ms: float,
    ) -> None:
        metrics, fresh_alerts = state.ingest(
            envelope,
            latency_ms=latency_ms,
            monotonic_now=time.monotonic(),
        )
        await broadcast(DeltaMsg(envelope=envelope, metrics=metrics))
        for alert in fresh_alerts:
            await broadcast(AlertMsg(alert=alert))

    async def ingest_loop() -> None:
        gen = StubEnvelopeGenerator(seed=stub_seed)
        async for envelope, latency_ms in gen.stream(interval_s=stub_interval_s):
            await handle_envelope(envelope, latency_ms)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if enable_stub:
            task = asyncio.create_task(ingest_loop())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="ERRE-Sandbox Dashboard", lifespan=lifespan)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def _get_dashboard() -> HTMLResponse:
        return HTMLResponse(HTML_TEMPLATE)

    @app.websocket("/ws/dashboard")
    async def _ws_dashboard(ws: WebSocket) -> None:
        await ws.accept()
        q: asyncio.Queue[UiMessage] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_MAX)
        subscribers.add(q)
        try:
            agent, tail, metrics, alerts = state.to_snapshot_payload()
            snapshot = SnapshotMsg(
                agent_state=agent,
                envelope_tail=tail,
                metrics=metrics,
                alerts=alerts,
            )
            await ws.send_text(snapshot.model_dump_json())
            while True:
                msg = await q.get()
                await ws.send_text(msg.model_dump_json())
        except WebSocketDisconnect:
            pass
        finally:
            subscribers.discard(q)

    app.state.dashboard_state = state
    app.state.broadcast = broadcast
    app.state.handle_envelope = handle_envelope
    return app


__all__ = ["create_app"]
