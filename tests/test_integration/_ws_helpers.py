"""Shared WebSocket helpers for Layer B scenario tests.

The ``TestClient.websocket_connect`` proxy exposes ``receive_text`` /
``send_text`` but leaves parsing to the caller. These two helpers are the
minimal glue reused by every scenario test so each file stays focused on
the step sequence itself rather than the transport mechanics.

Keeping the helpers here (not in ``conftest.py``) avoids the fixture
resolution overhead for callers that just want plain functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# TODO(T20): promote _parse_envelope to a public name when we tidy up
# integration/__init__.py; the second consumer (this module) means the
# underscore is now misleading. Kept private for now to avoid src/ churn
# outside the T19 execution-phase scope.
from erre_sandbox.integration.gateway import _parse_envelope
from erre_sandbox.schemas import HandshakeMsg

if TYPE_CHECKING:
    from erre_sandbox.schemas import ControlEnvelope


def client_handshake() -> str:
    """Return a godot-peer :class:`HandshakeMsg` encoded as JSON."""
    return HandshakeMsg(tick=0, peer="godot").model_dump_json()


def recv_envelope(ws: Any) -> ControlEnvelope:
    """Receive one frame from ``ws`` and parse it into a :class:`ControlEnvelope`.

    ``ws`` is the object yielded by
    :meth:`fastapi.testclient.TestClient.websocket_connect` — we accept
    ``Any`` because the class is private to starlette and typing against it
    would leak an implementation detail into every caller.
    """
    raw = ws.receive_text()
    env = _parse_envelope(raw)
    assert env is not None, f"server frame did not parse: {raw!r}"
    return env


__all__ = ["client_handshake", "recv_envelope"]
