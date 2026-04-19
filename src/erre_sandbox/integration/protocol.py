"""Session lifecycle constants and phase enum for the T14 gateway (WS).

This module augments :mod:`erre_sandbox.schemas` §7 ``ControlEnvelope`` with the
**operational parameters** that the wire-type definitions intentionally do not
encode:

* heartbeat cadence — how often the server must push :class:`WorldTickMsg`
* handshake / idle-disconnect timeouts — session lifecycle bounds
* ``SessionPhase`` — explicit enum of session states, consumed by the T14
  gateway implementation and the T19 skeleton scenario tests

The wire types themselves (``HandshakeMsg``, ``AgentUpdateMsg``, ...) are **not**
redefined here. They live in :mod:`erre_sandbox.schemas` and are imported by
consumers directly — this module only owns timing and state-machine rules.

See ``.steering/20260419-m2-integration-e2e/decisions.md`` D3 for why the
contract is split this way.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

# =============================================================================
# Session lifecycle constants
# =============================================================================

HEARTBEAT_INTERVAL_S: Final[float] = 1.0
"""Expected cadence of :class:`~erre_sandbox.schemas.WorldTickMsg` heartbeat.

Matches ``WorldRuntime._heartbeat_period`` default in :mod:`erre_sandbox.world.tick`.
Consumers (Godot client, monitor dashboards) may tolerate up to
``HEARTBEAT_INTERVAL_S * 3`` without raising a liveness alarm.
"""

HANDSHAKE_TIMEOUT_S: Final[float] = 5.0
"""Maximum time a peer has to send :class:`~erre_sandbox.schemas.HandshakeMsg`.

Measured from TCP accept / WS upgrade completion. Exceeding it causes the
gateway to close the socket with :class:`~erre_sandbox.schemas.ErrorMsg`
``code="handshake_timeout"``.
"""

IDLE_DISCONNECT_S: Final[float] = 60.0
"""Inactivity ceiling after which the gateway voluntarily closes a session.

Applies only once the session is :attr:`SessionPhase.ACTIVE`. During
``AWAITING_HANDSHAKE`` the stricter :data:`HANDSHAKE_TIMEOUT_S` governs.
"""

MAX_ENVELOPE_BACKLOG: Final[int] = 256
"""Maximum number of pending envelopes before the gateway drops the oldest.

The runtime queue (``WorldRuntime._envelopes``) is unbounded; the bound
applies per-client at the gateway layer so a slow Godot viewer cannot exhaust
server memory.
"""

SCHEMA_VERSION_HEADER: Final[str] = "X-Erre-Schema-Version"
"""HTTP header the gateway sets on the WS upgrade response.

Peers that don't send :class:`~erre_sandbox.schemas.HandshakeMsg` (e.g. debug
curl probes) can still discover the server's
:data:`~erre_sandbox.schemas.SCHEMA_VERSION` this way.
"""


# =============================================================================
# Session phase enum
# =============================================================================


class SessionPhase(StrEnum):
    """Explicit state-machine phases of a single WS session on the gateway.

    The T14 gateway implementation drives transitions strictly in this order:
    ``AWAITING_HANDSHAKE → ACTIVE → CLOSING``. No backwards transitions.

    Reconnection produces a fresh session (new ``SessionPhase`` instance).
    """

    AWAITING_HANDSHAKE = "awaiting_handshake"
    ACTIVE = "active"
    CLOSING = "closing"


__all__ = [
    "HANDSHAKE_TIMEOUT_S",
    "HEARTBEAT_INTERVAL_S",
    "IDLE_DISCONNECT_S",
    "MAX_ENVELOPE_BACKLOG",
    "SCHEMA_VERSION_HEADER",
    "SessionPhase",
]
