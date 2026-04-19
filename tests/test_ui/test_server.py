"""FastAPI TestClient tests for the dashboard server (HTTP + WS)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from erre_sandbox.ui.dashboard import create_app
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator


def test_get_dashboard_returns_html_200() -> None:
    app = create_app(enable_stub=False)
    with TestClient(app) as client:
        resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "ERRE-Sandbox Dashboard" in resp.text


def test_ws_initial_snapshot_is_sent_on_connect() -> None:
    app = create_app(enable_stub=False)
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        raw = ws.receive_text()
    msg = json.loads(raw)
    assert msg["kind"] == "snapshot"
    assert "metrics" in msg
    assert "envelope_tail" in msg
    assert "alerts" in msg


def test_ws_receives_delta_after_envelope_ingest() -> None:
    app = create_app(enable_stub=False)
    env, latency = StubEnvelopeGenerator(seed=0).next()
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        first = json.loads(ws.receive_text())
        assert first["kind"] == "snapshot"
        # Use the TestClient's portal to run the async coroutine on the
        # server's loop (avoids nested asyncio.run → event loop leak).
        client.portal.call(app.state.handle_envelope, env, latency)
        second = json.loads(ws.receive_text())
    assert second["kind"] == "delta"
    assert second["envelope"]["kind"] == env.kind


def test_ws_emits_alert_on_threshold_violation() -> None:
    app = create_app(enable_stub=False)
    gen = StubEnvelopeGenerator(seed=0)
    envs = [gen.next()[0] for _ in range(10)]
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        _ = ws.receive_text()  # discard snapshot
        # Saturate with 10 envelopes at 9000ms latency → past p50 100ms threshold.
        for env in envs:
            client.portal.call(app.state.handle_envelope, env, 9_000.0)

        kinds: list[str] = []
        for _ in range(30):  # 10 delta + at least 1 alert expected
            msg = json.loads(ws.receive_text())
            kinds.append(msg["kind"])
            if msg["kind"] == "alert":
                break
    assert "delta" in kinds
    assert "alert" in kinds


def test_create_app_with_stub_disabled_does_not_ingest() -> None:
    app = create_app(enable_stub=False, stub_interval_s=0.01)
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        snap = json.loads(ws.receive_text())
    assert snap["metrics"]["sample_count"] == 0
