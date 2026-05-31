"""Tests for the T14 WebSocket gateway.

Organised in two layers:

* **Layer A — pure/function level**: exercise :class:`Registry` and the parse
  / make helpers without a running server. Fast, deterministic.
* **Layer B — FastAPI TestClient**: exercise ``/health`` and
  ``/ws/observe`` end-to-end through the real Starlette WebSocket stack.
  Slower but covers the session state machine in :func:`ws_observe`.

The ``fast_timeouts`` fixture shrinks the protocol timing constants so idle
and handshake timeouts fire in under a second without compromising coverage.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from erre_sandbox.integration.gateway import (
    WS_TOKEN_HEADER,
    Registry,
    WSAuthConfig,
    _make_error,
    _make_server_handshake,
    _NullRuntime,
    _parse_envelope,
    make_app,
)
from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    ControlEnvelope,
    ErrorMsg,
    HandshakeMsg,
    SpeechMsg,
    WorldLayoutMsg,
    WorldTickMsg,
    Zone,
)

if TYPE_CHECKING:
    from .conftest import MockRuntime


# =============================================================================
# Layer A: pure helpers
# =============================================================================


class TestMakeServerHandshake:
    def test_peer_and_capabilities(self) -> None:
        hs = _make_server_handshake()
        assert hs.peer == "g-gear"
        assert hs.tick == 0
        assert hs.schema_version == SCHEMA_VERSION
        assert "handshake" in hs.capabilities
        assert "agent_update" in hs.capabilities
        # The full kind set mirrors ControlEnvelope discriminators (M4
        # foundation added dialog_*; M6 added reasoning_trace and
        # reflection_event; M7γ adds world_layout for the on-connect
        # snapshot).
        assert set(hs.capabilities) == {
            "handshake",
            "agent_update",
            "speech",
            "move",
            "animation",
            "world_tick",
            "error",
            "dialog_initiate",
            "dialog_turn",
            "dialog_close",
            "reasoning_trace",
            "reflection_event",
            "world_layout",
        }


class TestParseEnvelope:
    def test_valid_handshake_roundtrip(self) -> None:
        raw = HandshakeMsg(tick=0, peer="godot").model_dump_json()
        env = _parse_envelope(raw)
        assert isinstance(env, HandshakeMsg)

    def test_unknown_kind_rejected(self) -> None:
        raw = json.dumps(
            {
                "kind": "totally_made_up",
                "schema_version": SCHEMA_VERSION,
                "tick": 0,
            }
        )
        assert _parse_envelope(raw) is None

    def test_malformed_json_rejected(self) -> None:
        assert _parse_envelope("{not: 'json'") is None

    def test_oversize_frame_rejected(self) -> None:
        raw = json.dumps(
            {
                "kind": "speech",
                "tick": 0,
                "agent_id": "a",
                "utterance": "x" * 200_000,
                "zone": "peripatos",
            }
        )
        assert _parse_envelope(raw) is None

    def test_oversize_multibyte_frame_rejected(self) -> None:
        # F6 regression (codex review 2026-04-28): ``len(raw)`` counts
        # codepoints, not UTF-8 bytes. A payload with chars ≤ limit but
        # encoded bytes > limit must still be rejected so the
        # _MAX_RAW_FRAME_BYTES name actually constrains bytes.
        from erre_sandbox.integration.gateway import _MAX_RAW_FRAME_BYTES

        char_count = (_MAX_RAW_FRAME_BYTES // 3) + 100
        utterance = "あ" * char_count
        raw = json.dumps(
            {
                "kind": "speech",
                "tick": 0,
                "agent_id": "a",
                "utterance": utterance,
                "zone": "peripatos",
            },
            ensure_ascii=False,
        )
        assert len(raw) <= _MAX_RAW_FRAME_BYTES
        assert len(raw.encode("utf-8")) > _MAX_RAW_FRAME_BYTES
        assert _parse_envelope(raw) is None

    def test_frame_exactly_at_byte_limit_is_accepted(self) -> None:
        # F6 boundary: a frame whose UTF-8 encoded size equals the limit
        # (not exceeds) must still parse. Guards against off-by-one regression
        # where the byte check turns into ``>=`` instead of ``>``.
        from erre_sandbox.integration.gateway import _MAX_RAW_FRAME_BYTES

        # Build the JSON envelope first, then pad ``utterance`` so the encoded
        # frame is exactly at the limit.
        scaffold = json.dumps(
            {
                "kind": "speech",
                "tick": 0,
                "agent_id": "a",
                "utterance": "",
                "zone": "peripatos",
            }
        )
        # Each ASCII char added to utterance adds exactly 1 byte to the JSON.
        padding = _MAX_RAW_FRAME_BYTES - len(scaffold.encode("utf-8"))
        raw = json.dumps(
            {
                "kind": "speech",
                "tick": 0,
                "agent_id": "a",
                "utterance": "x" * padding,
                "zone": "peripatos",
            }
        )
        assert len(raw.encode("utf-8")) == _MAX_RAW_FRAME_BYTES
        env = _parse_envelope(raw)
        assert env is not None
        assert isinstance(env, SpeechMsg)


class TestRegistry:
    def test_add_remove_len(self) -> None:
        reg = Registry()
        q: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=4)
        assert len(reg) == 0
        reg.add("s1", q)
        assert len(reg) == 1
        reg.remove("s1")
        assert len(reg) == 0
        # removing unknown id is a no-op (defensive)
        reg.remove("never-existed")

    def test_fan_out_pushes_to_every_queue(self) -> None:
        reg = Registry()
        q1: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=4)
        q2: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=4)
        reg.add("s1", q1)
        reg.add("s2", q2)
        env = WorldTickMsg(tick=1, active_agents=3)
        reg.fan_out(env)
        assert q1.get_nowait() is env
        assert q2.get_nowait() is env

    def test_fan_out_drops_oldest_and_enqueues_warning_when_full(self) -> None:
        reg = Registry()
        q: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=2)
        reg.add("s1", q)
        first = WorldTickMsg(tick=1, active_agents=1)
        second = WorldTickMsg(tick=2, active_agents=1)
        third = WorldTickMsg(tick=3, active_agents=1)
        reg.fan_out(first)
        reg.fan_out(second)
        # Queue is full; next fan_out should drop `first`, add warning, add third.
        reg.fan_out(third)
        drained: list[ControlEnvelope] = []
        while not q.empty():
            drained.append(q.get_nowait())
        kinds = [e.kind for e in drained]
        assert "error" in kinds
        assert drained[-1] is third
        errors = [e for e in drained if isinstance(e, ErrorMsg)]
        assert errors[0].code == "backlog_overflow"

    def test_debug_snapshot(self) -> None:
        reg = Registry()
        q: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=4)
        reg.add("s1", q)
        q.put_nowait(WorldTickMsg(tick=0, active_agents=0))
        snap = reg.debug_snapshot()
        assert len(snap) == 1
        assert snap[0]["queue_depth"] == 1


class TestMakeError:
    def test_fields(self) -> None:
        err = _make_error(code="handshake_timeout", detail="5s", tick=42)
        assert err.kind == "error"
        assert err.code == "handshake_timeout"
        assert err.tick == 42


# =============================================================================
# Layer B: TestClient integration
# =============================================================================


def _client_hs() -> str:
    return HandshakeMsg(tick=0, peer="godot").model_dump_json()


def _recv_envelope(ws: Any) -> ControlEnvelope:
    """Helper: TestClient.websocket_connect yields a WS proxy whose receive_text
    returns a string; parse it into a ControlEnvelope via the module adapter."""
    raw = ws.receive_text()
    env = _parse_envelope(raw)
    assert env is not None, f"server frame did not parse: {raw!r}"
    return env


def _promote_to_active(ws: Any) -> None:
    """Send the client handshake and consume the M7γ on-connect WorldLayoutMsg.

    The gateway pushes a single ``world_layout`` envelope between handshake
    validation and registry insertion, so any test that wants to assert
    further runtime-driven envelopes must drain it first. Tests that
    explicitly verify the layout shape should NOT use this helper —
    see ``test_world_layout_msg.py``.
    """
    ws.send_text(_client_hs())
    layout = _recv_envelope(ws)
    assert isinstance(layout, WorldLayoutMsg), (
        f"expected WorldLayoutMsg between handshake and ACTIVE, got {layout!r}"
    )


class TestHealthEndpoint:
    def test_health_returns_schema_and_status(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == SCHEMA_VERSION
        assert body["status"] == "ok"
        assert body["active_sessions"] == 0


class TestHandshakeSuccess:
    def test_server_handshake_then_client_handshake_promotes_to_active(
        self,
        client: TestClient,
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            server_hs = _recv_envelope(ws)
            assert isinstance(server_hs, HandshakeMsg)
            assert server_hs.peer == "g-gear"
            ws.send_text(_client_hs())
            # No immediate reply; the session is ACTIVE. Close cleanly.

    def test_forwards_runtime_envelope_to_client(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)  # server handshake
            _promote_to_active(ws)  # sends client hs + drains world_layout
            # TestClient runs the app on a separate thread via an anyio
            # BlockingPortal; use it to call the async mock_runtime.put.
            speech = SpeechMsg(
                tick=7,
                agent_id="a_kant_001",
                utterance="I shall take a walk",
                zone=Zone.PERIPATOS,
            )
            client.portal.call(mock_runtime.put, speech)
            got = _recv_envelope(ws)
            assert isinstance(got, SpeechMsg)
            assert got.utterance == "I shall take a walk"


class TestHandshakeErrors:
    def test_handshake_timeout_emits_error_and_closes(
        self,
        client: TestClient,
        fast_timeouts: None,  # noqa: ARG002 — used for its side effect
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)  # server handshake
            # Do NOT reply; wait for handshake_timeout.
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "handshake_timeout"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_schema_mismatch_emits_error_and_closes(
        self,
        client: TestClient,
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)
            bad_hs = json.dumps(
                {
                    "kind": "handshake",
                    "schema_version": "0.0.0-bogus",
                    "tick": 0,
                    "peer": "godot",
                    "capabilities": [],
                    "sent_at": "2026-04-19T00:00:00Z",
                }
            )
            ws.send_text(bad_hs)
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "schema_mismatch"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_first_frame_must_be_handshake(
        self,
        client: TestClient,
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)
            # Send a WorldTickMsg first — that's not a handshake.
            ws.send_text(WorldTickMsg(tick=0, active_agents=0).model_dump_json())
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "invalid_envelope"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()


class TestActivePhaseRobustness:
    def test_invalid_envelope_during_active_is_warned_not_fatal(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)
            _promote_to_active(ws)
            ws.send_text("{not valid json")
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "invalid_envelope"
            # Connection still works — inject a real envelope and confirm delivery.
            tick = WorldTickMsg(tick=9, active_agents=1)
            client.portal.call(mock_runtime.put, tick)
            got = _recv_envelope(ws)
            assert isinstance(got, WorldTickMsg)
            assert got.tick == 9

    def test_idle_disconnect_after_timeout(
        self,
        client: TestClient,
        fast_timeouts: None,  # noqa: ARG002
    ) -> None:
        with client.websocket_connect("/ws/observe") as ws:
            _ = _recv_envelope(ws)
            _promote_to_active(ws)
            # Stay silent for > IDLE_DISCONNECT_S (patched to 0.5s).
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "idle_disconnect"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_recv_loop_handles_clean_websocket_disconnect(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A clean peer-side close (Godot exit, MacBook reconnect) must log at
        DEBUG, not ERROR (live-fix D2).

        Before the fix, ``WebSocketDisconnect`` propagated out of
        ``_recv_loop`` into the surrounding ``TaskGroup`` as an
        ``ExceptionGroup``; the outer ``except Exception`` then surfaced it
        via ``logger.exception("session %s crashed", ...)`` at ERROR level.
        Live-fix D2 catches the exception inside ``_recv_loop`` and demotes
        it to DEBUG.
        """
        import logging

        with (
            caplog.at_level(logging.DEBUG, logger="erre_sandbox.integration.gateway"),
            client.websocket_connect("/ws/observe") as ws,
        ):
            _ = _recv_envelope(ws)
            _promote_to_active(ws)
            # Closing the TestClient WS context cleanly disconnects.

        # Allow the server task to finish logging.
        for _ in range(50):
            if any("peer disconnected" in r.message for r in caplog.records):
                break
            client.portal.call(asyncio.sleep, 0.01)

        # No "session X crashed" ERROR.
        crashed = [
            r
            for r in caplog.records
            if r.levelno >= logging.ERROR and "crashed" in r.message
        ]
        assert crashed == [], (
            f"clean peer close produced ERROR-level crash log: {crashed}"
        )

        # The DEBUG-level breadcrumb is present.
        debug_msgs = [
            r
            for r in caplog.records
            if r.levelno == logging.DEBUG and "peer disconnected" in r.message
        ]
        assert debug_msgs, (
            "expected a DEBUG 'peer disconnected' log from recv_loop on clean close"
        )


class TestFanOut:
    def test_two_clients_each_receive_the_same_envelope(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with (
            client.websocket_connect("/ws/observe") as ws1,
            client.websocket_connect("/ws/observe") as ws2,
        ):
            _ = _recv_envelope(ws1)
            _ = _recv_envelope(ws2)
            _promote_to_active(ws1)
            _promote_to_active(ws2)
            env = WorldTickMsg(tick=3, active_agents=0)
            client.portal.call(mock_runtime.put, env)
            got1 = _recv_envelope(ws1)
            got2 = _recv_envelope(ws2)
            assert isinstance(got1, WorldTickMsg)
            assert isinstance(got2, WorldTickMsg)
            assert got1.tick == 3 == got2.tick


# =============================================================================
# Layer B (SH-2): WebSocket connection-time auth gates
# =============================================================================


def _make_authed_client(
    mock_runtime: MockRuntime,
    auth_config: WSAuthConfig,
) -> TestClient:
    """Build a TestClient whose make_app() was wired with ``auth_config``.

    Each call returns a fresh TestClient so concurrent tests cannot leak
    registry state between cases. The caller is responsible for using the
    returned client as a context manager so the FastAPI lifespan starts
    the broadcaster task.
    """
    app = make_app(runtime=mock_runtime, auth_config=auth_config)
    return TestClient(app)


class TestWebSocketAuth:
    """SH-2 — Origin / token / session cap connection-time gates.

    All three gates default to disabled (see :class:`WSAuthConfig`). Each
    test below opts into exactly one gate so the failure mode is isolated.
    """

    # Shared literal so the S106 noqa only needs to live in one place.
    _TOKEN = "hunter2-shared"  # noqa: S105 — test fixture token literal

    def test_back_compat_no_token_required_by_default(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        """Default ``WSAuthConfig()`` accepts unauthenticated peers.

        Mirrors the Mac↔G-GEAR LAN workflow contract — bumping to the new
        gateway must not require token provisioning on existing setups.
        """
        with (
            _make_authed_client(mock_runtime, WSAuthConfig()) as client,
            client.websocket_connect("/ws/observe") as ws,
        ):
            server_hs = _recv_envelope(ws)
            assert isinstance(server_hs, HandshakeMsg)

    def test_token_missing_closes_with_1008(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        cfg = WSAuthConfig(token=self._TOKEN, require_token=True)
        with (
            _make_authed_client(mock_runtime, cfg) as client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/ws/observe"),
        ):
            pass
        assert exc_info.value.code == 1008

    def test_token_mismatch_closes_with_1008(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        cfg = WSAuthConfig(token=self._TOKEN, require_token=True)
        with (
            _make_authed_client(mock_runtime, cfg) as client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(
                "/ws/observe",
                headers={WS_TOKEN_HEADER: "wrong-token"},
            ),
        ):
            pass
        assert exc_info.value.code == 1008

    def test_token_match_continues_to_handshake(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        cfg = WSAuthConfig(token=self._TOKEN, require_token=True)
        with (
            _make_authed_client(mock_runtime, cfg) as client,
            client.websocket_connect(
                "/ws/observe",
                headers={WS_TOKEN_HEADER: self._TOKEN},
            ) as ws,
        ):
            server_hs = _recv_envelope(ws)
            assert isinstance(server_hs, HandshakeMsg)

    def test_origin_rejected_closes_with_1008(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        cfg = WSAuthConfig(
            allowed_origins=("http://mac.local", "http://g-gear.local"),
        )
        with (
            _make_authed_client(mock_runtime, cfg) as client,
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(
                "/ws/observe",
                headers={"origin": "http://evil.example"},
            ),
        ):
            pass
        assert exc_info.value.code == 1008

    def test_session_cap_exceeded_closes_with_1013(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        """Pre-accept cap pre-check closes the over-cap socket with 1013.

        ``max_sessions=2`` keeps the test cheap; the gate logic is the same
        at production ``max_sessions=8``. The third connection arrives while
        two sockets are already registered (in ACTIVE phase), so the
        pre-accept ``len(registry) >= cap`` branch fires.
        """
        cfg = WSAuthConfig(max_sessions=2)
        with (
            _make_authed_client(mock_runtime, cfg) as client,
            client.websocket_connect("/ws/observe") as ws1,
            client.websocket_connect("/ws/observe") as ws2,
        ):
            _ = _recv_envelope(ws1)  # server handshake
            _ = _recv_envelope(ws2)
            _promote_to_active(ws1)
            _promote_to_active(ws2)
            # Both sessions are now ACTIVE → registry holds 2 slots.
            with (
                pytest.raises(WebSocketDisconnect) as exc_info,
                client.websocket_connect("/ws/observe"),
            ):
                pass
            assert exc_info.value.code == 1013


# =============================================================================
# Null runtime sanity
# =============================================================================


class TestNullRuntime:
    async def test_recv_never_returns(self) -> None:
        """:class:`_NullRuntime` should block forever — the broadcaster relies on it."""
        rt = _NullRuntime()
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.1):
                await rt.recv_envelope()
