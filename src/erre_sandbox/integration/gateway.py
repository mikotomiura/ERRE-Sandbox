"""FastAPI + WebSocket gateway that streams :class:`ControlEnvelope` to peers (T14).

Design choice (see ``.steering/20260419-gateway-fastapi-ws/design.md`` v2):

* **Session state machine ≡ the WS handler function**: :func:`ws_observe` is
  itself the state machine. The three phases (``AWAITING_HANDSHAKE`` →
  ``ACTIVE`` → ``CLOSING``) are expressed as try/except boundaries plus
  early ``return``; no ``Session`` class, no explicit enum at runtime.
* **Fan-out**: a single :func:`_broadcaster` task pulls envelopes from
  :class:`WorldRuntime` and calls :meth:`Registry.fan_out` to push into every
  per-client bounded queue (``maxsize=MAX_ENVELOPE_BACKLOG``).
* **Timeouts**: handshake and idle-disconnect are both implemented with
  ``asyncio.timeout()`` context managers (Python 3.11+). No separate watchdog
  task, no ``time.monotonic`` polling.

The module exposes :func:`make_app` as the ASGI factory, so ``uvicorn`` can
start it with ``--factory`` and tests can inject a ``MockRuntime``.

Layer dependency (extended from ``integration/`` contract layer —
see decisions.md D2): this file is allowed to import from
``erre_sandbox.world`` (for ``WorldRuntime``); ``ui`` remains forbidden.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import re
import secrets
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar, Final, Protocol

from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from erre_sandbox.integration import protocol
from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentUpdateMsg,
    AnimationMsg,
    ControlEnvelope,
    DialogInitiateMsg,
    DialogTurnMsg,
    ErrorMsg,
    HandshakeMsg,
    MoveMsg,
    SpeechMsg,
    WorldLayoutMsg,
    WorldTickMsg,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# =============================================================================
# Module-level constants & adapter
# =============================================================================

_ENVELOPE_ADAPTER: Final[TypeAdapter[ControlEnvelope]] = TypeAdapter(ControlEnvelope)
"""Cached TypeAdapter for discriminated-union parsing of client frames.

Instantiating a :class:`TypeAdapter` is non-trivial (introspects Pydantic
models), so it is created once at import time and reused.
"""

_MAX_RAW_FRAME_BYTES: Final[int] = 64 * 1024

_LAYOUT_SNAPSHOT_TIMEOUT_S: Final[float] = 2.0
"""Hard cap on ``layout_snapshot`` build time at handshake (M7δ R3 M5).

Two seconds is generous given the production snapshot is a pure read of
``ZONE_CENTERS`` / ``ZONE_PROPS`` (microseconds in practice). The bound
exists for the failure mode where a future runtime extension reaches into
the live world (DB, LLM cache warm-up, etc.) and stalls indefinitely;
the gateway then falls back to an empty ``WorldLayoutMsg`` so the WS
handshake still completes."""
"""Hard upper bound on a single WS text frame we try to parse.

Anything larger is rejected with :class:`ErrorMsg` ``invalid_envelope``
without even attempting to decode — a cheap DoS mitigation in line with the
same bound used by ``cognition.parse.MAX_RAW_PLAN_BYTES``.
"""

_SERVER_CAPABILITIES: Final[tuple[str, ...]] = (
    "handshake",
    "agent_update",
    "speech",
    "move",
    "animation",
    "world_tick",
    "error",
    # M4 foundation dialog variants — advertised so clients that opted into
    # 0.2.0-m4 can subscribe without a capability mismatch round-trip.
    "dialog_initiate",
    "dialog_turn",
    "dialog_close",
    # M6-A-3 / M6-A-4 xAI variants and the M7γ on-connect world layout
    # snapshot. Advertised so clients can drop the capability-probing
    # round-trip when they upgrade.
    "reasoning_trace",
    "reflection_event",
    "world_layout",
)


class _GracefulCloseError(Exception):
    """Raised by the recv / send coroutines to end the ACTIVE phase cleanly.

    The TaskGroup surrounding them catches this via ``except*`` so any
    voluntary exit (idle timeout already signalled, peer closed cleanly) is
    distinguished from genuine bugs which propagate upward.
    """


class _RuntimeLike(Protocol):
    """Minimal contract the gateway needs from a runtime source.

    Kept intentionally narrower than :class:`WorldRuntime` so tests can
    supply a ``MockRuntime`` without importing ``world``. Only
    :meth:`recv_envelope` is used on the broadcast path; M7γ adds
    :meth:`layout_snapshot` so the WS handler can push a per-session
    :class:`WorldLayoutMsg` immediately after handshake validation.
    """

    async def recv_envelope(self) -> ControlEnvelope: ...

    def layout_snapshot(self, *, tick: int = 0) -> WorldLayoutMsg: ...


def _envelope_target_agents(env: ControlEnvelope) -> frozenset[str] | None:
    """Extract the set of ``agent_id`` values an envelope is scoped to.

    Added by ``m4-gateway-multi-agent-stream`` to drive per-session
    subscription filtering. Returns ``None`` when the envelope is global
    (must reach every subscriber regardless of filter).

    Routing rules:

    * ``agent_update`` / ``speech`` / ``move`` / ``animation`` — the single
      ``agent_id`` field the envelope carries.
    * ``dialog_initiate`` — both the initiator and target.
    * ``dialog_turn`` — both the speaker and addressee.
    * ``handshake`` / ``world_tick`` / ``error`` / ``dialog_close`` —
      global: handshake is server-originated, world_tick and error are
      session-wide utilities, dialog_close is metadata-only (no
      participant fields on the wire type) so every subscriber needs it
      for UI cleanup.
    """
    if isinstance(env, AgentUpdateMsg):
        return frozenset({env.agent_state.agent_id})
    if isinstance(env, (SpeechMsg, MoveMsg, AnimationMsg)):
        return frozenset({env.agent_id})
    if isinstance(env, DialogInitiateMsg):
        return frozenset({env.initiator_agent_id, env.target_agent_id})
    if isinstance(env, DialogTurnMsg):
        return frozenset({env.speaker_id, env.addressee_id})
    return None


# =============================================================================
# Registry
# =============================================================================


class Registry:
    """Thin per-app lookup of session_id → outbound queue.

    Not a state machine: the session's state lives in the stack frame of
    :func:`ws_observe`. The registry exists only so that
    :func:`_broadcaster` can find every active outbound queue and
    ``/health`` can report ``active_sessions``.

    Per-session agent subscription (added by
    ``m4-gateway-multi-agent-stream``) is carried alongside the queue.
    A ``None`` subscription means the session receives every envelope
    (the M2 broadcast default); a frozenset restricts delivery to
    envelopes whose ``_envelope_target_agents`` intersects the set.
    Global envelopes (``world_tick`` / ``error`` / ``dialog_close`` /
    server handshake) bypass the filter unconditionally.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[ControlEnvelope]] = {}
        self._subscriptions: dict[str, frozenset[str] | None] = {}

    def __len__(self) -> int:
        return len(self._queues)

    def add(
        self,
        session_id: str,
        queue: asyncio.Queue[ControlEnvelope],
        *,
        subscribed_agents: frozenset[str] | None = None,
    ) -> None:
        self._queues[session_id] = queue
        self._subscriptions[session_id] = subscribed_agents

    def remove(self, session_id: str) -> None:
        self._queues.pop(session_id, None)
        self._subscriptions.pop(session_id, None)

    def fan_out(self, env: ControlEnvelope) -> None:
        """Push ``env`` to every registered queue whose subscription matches.

        If a queue is full we drop the **oldest** item, push a single
        :class:`ErrorMsg` ``backlog_overflow`` warning, then push ``env``.
        This preserves the "latest-wins" behaviour described in the
        integration-contract while keeping memory bounded.

        Subscription filtering: a session whose ``subscribed_agents`` is
        ``None`` receives every envelope. A non-None subscription receives
        an envelope only when ``_envelope_target_agents(env)`` is ``None``
        (global) or intersects the subscription.
        """
        targets = _envelope_target_agents(env)
        for session_id, queue in list(self._queues.items()):
            subscription = self._subscriptions.get(session_id)
            if (
                subscription is not None
                and targets is not None
                and subscription.isdisjoint(targets)
            ):
                # Session is subscribed to a specific agent set and this
                # envelope is scoped to a disjoint agent set — skip.
                continue
            # Guard against an unbounded (maxsize=0) queue: ``queue.full()``
            # returns False in that case, but the qsize() > maxsize - 2 loop
            # below would drain every queued item if we ever reached it.
            if queue.maxsize > 0 and queue.full():
                # We need room for two items (warning + env), so drop enough
                # oldest entries to bring the queue size to maxsize - 2.
                while queue.qsize() > max(queue.maxsize - 2, 0):
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover — defensive
                        break
                warning = _make_error(
                    code="backlog_overflow",
                    detail=(
                        f"session {session_id} queue full (maxsize="
                        f"{queue.maxsize}); dropped oldest"
                    ),
                )
                try:
                    queue.put_nowait(warning)
                except asyncio.QueueFull:
                    # maxsize < 2: warning cannot fit, env takes priority.
                    logger.debug(
                        "session %s dropped backlog_overflow warning",
                        session_id,
                    )
            try:
                queue.put_nowait(env)
            except asyncio.QueueFull:  # pragma: no cover — we just made room
                logger.warning("session %s dropped envelope", session_id)

    def debug_snapshot(self) -> list[dict[str, int]]:
        """Observation of current queue depths — used by ``/health`` and logs."""
        return [
            {
                "session_id_suffix_hash": abs(hash(sid)) % 10_000,
                "queue_depth": q.qsize(),
            }
            for sid, q in self._queues.items()
        ]


# =============================================================================
# Pure helpers (no I/O)
# =============================================================================


def _make_server_handshake() -> HandshakeMsg:
    return HandshakeMsg(
        tick=0,
        peer="g-gear",
        capabilities=list(_SERVER_CAPABILITIES),
    )


def _make_error(*, code: str, detail: str, tick: int = 0) -> ErrorMsg:
    return ErrorMsg(tick=tick, code=code, detail=detail)


class _InvalidSubscribeError(ValueError):
    """Raised when ``?subscribe=`` violates a limit.

    Kept as a dedicated subclass so ``ws_observe`` can distinguish
    subscription errors from other client-side faults and surface a
    specific error code without catching bare ``ValueError`` (which would
    also catch downstream bugs).
    """


_SUBSCRIBE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"\A[A-Za-z0-9_-]+\Z")
"""Allowed character class for a single ``?subscribe=`` item.

Matches the kebab-case / snake-case slug shape of ``PersonaSpec.persona_id``
and rejects control characters, whitespace, path separators, and any
Unicode that could be abused for log injection or impersonation.
"""


def _parse_subscribe_param(raw: str | None) -> frozenset[str] | None:
    """Translate the ``?subscribe=`` URL param into a subscription set.

    Returns ``None`` (broadcast) when:

    * the param is absent, empty, or exactly ``*``.

    Returns a ``frozenset`` of persona ids when the param is a comma-
    separated list of non-empty slugs. Raises :class:`_InvalidSubscribeError`
    if any limit is violated — the caller surfaces this as an
    ``invalid_subscribe`` :class:`ErrorMsg` and closes the handshake.
    """
    if raw is None or raw in {"", "*"}:
        return None
    # O(1) byte-length pre-check before ``split``. Defends against a
    # permissive reverse proxy passing through multi-MB query strings
    # that would otherwise allocate a long list of short strings.
    if len(raw) > protocol.MAX_SUBSCRIBE_RAW_LENGTH:
        raise _InvalidSubscribeError(
            f"subscribe param is {len(raw)} chars, max is "
            f"{protocol.MAX_SUBSCRIBE_RAW_LENGTH}",
        )
    items = [x.strip() for x in raw.split(protocol.SUBSCRIBE_DELIMITER) if x.strip()]
    if not items:
        return None
    if len(items) > protocol.MAX_SUBSCRIBE_ITEMS:
        raise _InvalidSubscribeError(
            f"subscribe has {len(items)} items, max is {protocol.MAX_SUBSCRIBE_ITEMS}",
        )
    for item in items:
        if len(item) > protocol.MAX_SUBSCRIBE_ID_LENGTH:
            raise _InvalidSubscribeError(
                f"subscribe item {item[:20]!r}… exceeds "
                f"{protocol.MAX_SUBSCRIBE_ID_LENGTH} chars",
            )
        if not _SUBSCRIBE_ID_PATTERN.match(item):
            # Reject control chars / whitespace / unicode / path separators
            # before they reach the log pipeline. persona_id is a slug
            # (PersonaSpec) so any non-matching item is also a routing miss.
            raise _InvalidSubscribeError(
                f"subscribe item {item[:20]!r}… must match "
                f"[A-Za-z0-9_-]+ (persona_id slug)",
            )
    return frozenset(items)


def _parse_envelope(raw: str) -> ControlEnvelope | None:
    """Parse a client frame into a :class:`ControlEnvelope` or return ``None``.

    Returns ``None`` on:

    * frame size > :data:`_MAX_RAW_FRAME_BYTES`;
    * JSON or Pydantic validation failure.

    Callers are expected to follow a ``None`` with an
    :class:`ErrorMsg` ``invalid_envelope`` (one-shot warning, not a close).
    """
    # Cheap char-length upper bound first (UTF-8 bytes >= codepoint count).
    # The precise byte check only fires on near-limit frames, sparing us
    # the encode() copy on every typical frame.
    if len(raw) > _MAX_RAW_FRAME_BYTES:
        return None
    try:
        return _ENVELOPE_ADAPTER.validate_json(raw)
    except ValidationError:
        return None


# =============================================================================
# I/O helpers
# =============================================================================


async def _send(ws: WebSocket, env: ControlEnvelope) -> None:
    await ws.send_text(env.model_dump_json())


async def _send_error(ws: WebSocket, *, code: str, detail: str) -> None:
    try:
        await _send(ws, _make_error(code=code, detail=detail))
    except Exception:  # noqa: BLE001 — best-effort, the socket may already be gone
        logger.debug("could not surface ErrorMsg(%s) — socket likely closed", code)


# =============================================================================
# WS handler loops (called from ws_observe TaskGroup)
# =============================================================================


async def _recv_loop(ws: WebSocket) -> None:
    """Drain client → server frames and enforce idle-disconnect.

    The idle timer is expressed as a nested :func:`asyncio.timeout` around
    every :meth:`WebSocket.receive_text`; each successful receive resets it.
    On timeout we surface an :class:`ErrorMsg` and raise
    :class:`_GracefulCloseError` so the surrounding TaskGroup exits cleanly.

    For M2 clients may only meaningfully send :class:`HandshakeMsg` (already
    consumed before ACTIVE). Other parsed envelopes are logged as a
    warning but otherwise ignored; unparsable frames trigger a one-shot
    ``invalid_envelope`` warning without closing.
    """
    while True:
        try:
            async with asyncio.timeout(protocol.IDLE_DISCONNECT_S):
                raw = await ws.receive_text()
        except TimeoutError:
            await _send_error(
                ws,
                code="idle_disconnect",
                detail=f"no client frame for {protocol.IDLE_DISCONNECT_S}s",
            )
            raise _GracefulCloseError from None
        env = _parse_envelope(raw)
        if env is None:
            await _send_error(
                ws,
                code="invalid_envelope",
                detail="frame too large or failed ControlEnvelope validation",
            )
            continue
        if env.kind == "handshake":
            logger.debug("duplicate handshake after ACTIVE — ignored")
        else:
            logger.debug("client pushed %s envelope (ignored in M2)", env.kind)


async def _send_loop(
    ws: WebSocket,
    queue: asyncio.Queue[ControlEnvelope],
) -> None:
    """Drain the per-session outbound queue and write each envelope to the socket.

    We do not implement batching — envelope sizes are small (<1 KB) and
    Godot's client decodes one frame at a time, so the cost/benefit does not
    favour batching at this stage.
    """
    while True:
        env = await queue.get()
        try:
            await _send(ws, env)
        except WebSocketDisconnect:
            raise _GracefulCloseError from None
        except (OSError, RuntimeError) as exc:
            # Covers "WebSocket is not connected" and the lower-level OSErrors
            # Starlette can surface when the peer vanishes mid-write. Logging
            # here (rather than letting the TaskGroup surface an opaque
            # ExceptionGroup) makes the close reason observable.
            logger.debug("session send_loop terminating: %s", exc)
            raise _GracefulCloseError from exc


# =============================================================================
# Broadcaster task — started by the lifespan context manager
# =============================================================================


async def _broadcaster(runtime: _RuntimeLike, registry: Registry) -> None:
    """Forward every envelope produced by the runtime to all active sessions.

    The loop lives for the lifetime of the ASGI app (started by
    :func:`_lifespan`) and is cancelled on shutdown. Per-session back-pressure
    is handled by :meth:`Registry.fan_out`; exceptions raised here are
    intentionally surfaced so an operator notices a broken runtime source.
    """
    while True:
        env = await runtime.recv_envelope()
        registry.fan_out(env)


# =============================================================================
# WebSocket endpoint — the session state machine
# =============================================================================


async def ws_observe(ws: WebSocket) -> None:  # noqa: PLR0915 — protocol state machine inherently long
    """Top-level WS handler. Also the session state machine.

    The three protocol phases map onto the function's linear control flow:

    * **AWAITING_HANDSHAKE** — from :meth:`accept` up to the point we have
      parsed the client :class:`HandshakeMsg` and its ``schema_version``
      matches. Timeouts and mismatches surface an ErrorMsg and ``return``
      before we ever touch the registry.
    * **ACTIVE** — the TaskGroup section. The session queue is created here,
      inserted into the registry, and removed in ``finally``.
    * **CLOSING** — the outer ``finally`` blocks; ``ws.close()`` is attempted
      best-effort so an already-closed socket does not raise.
    """
    # runtime lives on app.state for the broadcaster; the handler itself
    # does not need a direct reference, so we only look up the registry here.
    registry: Registry = ws.app.state.registry
    session_id = secrets.token_hex(8)

    # Parse the optional ``?subscribe=`` query parameter before accepting,
    # so a malformed subscription is rejected before we allocate resources
    # or notify the peer of a successful upgrade.
    try:
        subscribed_agents = _parse_subscribe_param(
            ws.query_params.get(protocol.SUBSCRIBE_QUERY_PARAM),
        )
    except _InvalidSubscribeError as exc:
        # WebSocket spec requires accept() before we can send any application
        # frame, so the ErrorMsg path mirrors the valid flow: upgrade first,
        # surface the error, then close. This intentionally gives the peer
        # no timing-based oracle between a valid and an invalid subscribe.
        await ws.accept(
            headers=[
                (
                    protocol.SCHEMA_VERSION_HEADER.lower().encode(),
                    SCHEMA_VERSION.encode(),
                ),
            ],
        )
        await _send_error(ws, code="invalid_subscribe", detail=str(exc))
        with contextlib.suppress(Exception):
            await ws.close()
        return

    await ws.accept(
        headers=[
            (
                protocol.SCHEMA_VERSION_HEADER.lower().encode(),
                SCHEMA_VERSION.encode(),
            ),
        ],
    )

    try:
        # ---------- Phase 1: AWAITING_HANDSHAKE ----------
        await _send(ws, _make_server_handshake())
        try:
            async with asyncio.timeout(protocol.HANDSHAKE_TIMEOUT_S):
                raw = await ws.receive_text()
        except TimeoutError:
            await _send_error(
                ws,
                code="handshake_timeout",
                detail=(
                    f"client HandshakeMsg not received within "
                    f"{protocol.HANDSHAKE_TIMEOUT_S}s"
                ),
            )
            return

        env = _parse_envelope(raw)
        if not isinstance(env, HandshakeMsg):
            await _send_error(
                ws,
                code="invalid_envelope",
                detail="first client frame must be HandshakeMsg",
            )
            return

        if env.schema_version != SCHEMA_VERSION:
            await _send_error(
                ws,
                code="schema_mismatch",
                detail=(
                    f"client schema_version={env.schema_version!r} != "
                    f"server {SCHEMA_VERSION!r}"
                ),
            )
            return

        # ---------- Phase 2: ACTIVE ----------
        # M7γ: push a single :class:`WorldLayoutMsg` snapshot immediately
        # after handshake validation, before the session joins the registry
        # fan-out. Sending pre-registry guarantees the layout always lands
        # *before* any cognition-driven envelope, so the Godot
        # :class:`BoundaryLayer` can hydrate ``zone_rects`` / ``prop_coords``
        # before the first agent tick paints over them.
        #
        # M7δ R3 M5: bound the snapshot build with ``asyncio.timeout(2.0)``
        # so a slow scan cannot stall the handshake. On timeout we fall back
        # to an empty :class:`WorldLayoutMsg` (the same shape ``_NullRuntime``
        # returns) and continue — Godot's BoundaryLayer treats an empty
        # ``zone_rects`` as "no overlay", which is degraded but live, not
        # frozen. Logged at WARNING so operators can see the regression.
        runtime: _RuntimeLike = ws.app.state.runtime
        try:
            async with asyncio.timeout(_LAYOUT_SNAPSHOT_TIMEOUT_S):
                layout_msg = await asyncio.to_thread(runtime.layout_snapshot)
        except TimeoutError:
            logger.warning(
                "[gateway] layout_snapshot exceeded %.1fs — sending empty "
                "fallback so handshake can complete (session=%s)",
                _LAYOUT_SNAPSHOT_TIMEOUT_S,
                session_id,
            )
            layout_msg = WorldLayoutMsg(tick=0)
        await _send(ws, layout_msg)

        out_queue: asyncio.Queue[ControlEnvelope] = asyncio.Queue(
            maxsize=protocol.MAX_ENVELOPE_BACKLOG,
        )
        registry.add(session_id, out_queue, subscribed_agents=subscribed_agents)
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_recv_loop(ws), name=f"recv-{session_id}")
                tg.create_task(
                    _send_loop(ws, out_queue),
                    name=f"send-{session_id}",
                )
        except* _GracefulCloseError:
            pass  # voluntary exit — send_error was already surfaced
        finally:
            registry.remove(session_id)

    except WebSocketDisconnect:
        # Peer closed the socket mid-flow; nothing actionable on our side.
        logger.debug("session %s disconnected by peer", session_id)
    except Exception:
        # Log full context server-side, but only surface a generic error to
        # the peer: internal exception types / file paths / DB identifiers
        # could otherwise leak to Godot or any future remote client.
        logger.exception("session %s crashed", session_id)
        await _send_error(
            ws,
            code="internal_error",
            detail="internal server error",
        )
    finally:
        with contextlib.suppress(Exception):
            await ws.close()


# =============================================================================
# Health endpoint
# =============================================================================


async def _health(app: FastAPI) -> dict[str, object]:
    registry: Registry = app.state.registry
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "active_sessions": len(registry),
    }


# =============================================================================
# Null runtime (used when an operator spawns the gateway standalone for debug)
# =============================================================================


class _NullRuntime:
    """Placeholder runtime that never emits envelopes.

    Allows ``uvicorn --factory`` runs to succeed without binding to a live
    :class:`WorldRuntime`. All production starts should inject a real
    runtime via :func:`make_app`.
    """

    DESCRIPTION: ClassVar[str] = "gateway started without a WorldRuntime"

    async def recv_envelope(self) -> ControlEnvelope:
        # Sleep forever — the broadcaster awaits this and simply never wakes.
        await asyncio.Event().wait()
        # Unreachable but type-level satisfying return.
        return WorldTickMsg(tick=0, active_agents=0)  # pragma: no cover

    def layout_snapshot(self, *, tick: int = 0) -> WorldLayoutMsg:
        """Return an empty layout snapshot.

        The ``_NullRuntime`` carries no zone or prop state, so the snapshot
        is intentionally empty. Real :class:`WorldRuntime` instances build
        the message from :data:`erre_sandbox.world.zones.ZONE_CENTERS` /
        :data:`~erre_sandbox.world.zones.ZONE_PROPS`.
        """
        return WorldLayoutMsg(tick=tick)


# =============================================================================
# App factory and lifespan
# =============================================================================


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime: _RuntimeLike = app.state.runtime
    registry: Registry = app.state.registry
    task = asyncio.create_task(_broadcaster(runtime, registry), name="broadcaster")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


def make_app(runtime: _RuntimeLike | None = None) -> FastAPI:
    """ASGI factory — the canonical entry point.

    The runtime dependency is injected so tests can swap a :class:`MockRuntime`
    via fixture. The default :class:`_NullRuntime` makes the app runnable
    standalone (useful for curl probes of ``/health``).
    """
    app = FastAPI(lifespan=_lifespan)
    app.state.runtime = runtime if runtime is not None else _NullRuntime()
    app.state.registry = Registry()

    async def health_endpoint() -> dict[str, object]:
        return await _health(app)

    app.add_api_route("/health", health_endpoint, methods=["GET"])
    app.add_api_websocket_route("/ws/observe", ws_observe)
    return app


# =============================================================================
# __main__
# =============================================================================


def _main() -> None:
    import uvicorn  # noqa: PLC0415 — only needed when run as __main__

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 — LAN only
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(
        "erre_sandbox.integration.gateway:make_app",
        factory=True,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    _main()
