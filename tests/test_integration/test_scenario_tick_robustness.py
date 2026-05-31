"""S_TICK_ROBUSTNESS scenario — Layer B1 via TestClient reconnect.

Covers the gateway's behaviour under tick drops and session restart.
Layer B1 scope: the client side's liveness alarm logic lives in Godot
(``godot_project/scripts/WebSocketClient.gd``) and is out of scope here —
what we *can* assert is that the gateway is stateless about tick numbers
and that a reconnected session produces a fresh ``HandshakeMsg`` with
``tick=0`` and the same ``SCHEMA_VERSION``.

Decisions.md D5 — we intentionally do **not** use ``ManualClock`` to
avoid spinning up the full ``WorldRuntime``; the essence of
disconnect/reconnect is the second handshake exchange, which
``TestClient.websocket_connect`` reproduces cleanly via two context blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentUpdateMsg,
    HandshakeMsg,
    WorldTickMsg,
)
from tests.test_integration._ws_helpers import promote_to_active, recv_envelope

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from erre_sandbox.integration import Scenario
    from tests.conftest import MakeAgentState

    from .conftest import MockRuntime

AGENT_ID = "a_kant_001"


def test_s_tick_robustness_initial_agent_update(
    tick_robustness_scenario: Scenario,
    client: TestClient,
    mock_runtime: MockRuntime,
    make_agent_state: MakeAgentState,
) -> None:
    """Step 0 — ``AgentUpdateMsg`` reaches the newly-active peer."""
    step = tick_robustness_scenario.steps[0]
    assert step.actor == "world"

    state = make_agent_state(agent_id=AGENT_ID, position={"zone": "peripatos"})
    env = AgentUpdateMsg(tick=0, agent_state=state)

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        promote_to_active(ws)
        client.portal.call(mock_runtime.put, env)
        got = recv_envelope(ws)

    assert isinstance(got, AgentUpdateMsg)
    assert got.agent_state.agent_id == AGENT_ID


def test_s_tick_robustness_tolerates_missed_heartbeat(
    client: TestClient,
    mock_runtime: MockRuntime,
) -> None:
    """Step 1 — a skipped tick does not surface as an ErrorMsg on the wire.

    The gateway is stateless about tick numbering — it forwards whatever
    the runtime produces. We verify that by omitting ``tick=2`` between
    ``tick=1`` and ``tick=3`` and confirming both observed frames are
    plain :class:`WorldTickMsg` with no intervening error.
    """
    tick1 = WorldTickMsg(tick=1, active_agents=1)
    tick3 = WorldTickMsg(tick=3, active_agents=1)

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        promote_to_active(ws)

        client.portal.call(mock_runtime.put, tick1)
        got1 = recv_envelope(ws)
        client.portal.call(mock_runtime.put, tick3)
        got3 = recv_envelope(ws)

    assert isinstance(got1, WorldTickMsg)
    assert isinstance(got3, WorldTickMsg)
    assert got1.tick == 1
    assert got3.tick == 3


def test_s_tick_robustness_survives_reconnect(
    client: TestClient,
) -> None:
    """Step 2 — second session produces a fresh ``HandshakeMsg`` with ``tick=0``.

    The first session completes handshake then closes cleanly. The second
    connection must begin a brand-new lifecycle (``HandshakeMsg.tick=0``,
    same ``SCHEMA_VERSION``) — this is the invariant Godot's reconnect
    flow depends on.
    """
    # First session: open, handshake, close.
    with client.websocket_connect("/ws/observe") as ws1:
        server_hs_1 = recv_envelope(ws1)
        assert isinstance(server_hs_1, HandshakeMsg)
        assert server_hs_1.tick == 0
        assert server_hs_1.schema_version == SCHEMA_VERSION
        promote_to_active(ws1)

    # Second session: fresh server handshake.
    with client.websocket_connect("/ws/observe") as ws2:
        server_hs_2 = recv_envelope(ws2)
        assert isinstance(server_hs_2, HandshakeMsg)
        assert server_hs_2.tick == 0
        assert server_hs_2.schema_version == SCHEMA_VERSION
        promote_to_active(ws2)


def test_s_tick_robustness_memory_continuity(
    client: TestClient,
    mock_runtime: MockRuntime,
    make_agent_state: MakeAgentState,
) -> None:
    """Step 3 — same ``agent_id`` is observed before and after reconnect.

    The runtime is the source of truth for agent identity; the gateway
    does not manufacture it. By injecting the same ``agent_id`` in both
    sessions we prove that a disconnect boundary does not fragment the
    agent's on-wire identity.
    """
    pre = AgentUpdateMsg(
        tick=5,
        agent_state=make_agent_state(
            agent_id=AGENT_ID,
            tick=5,
            position={"zone": "peripatos"},
        ),
    )
    post = AgentUpdateMsg(
        tick=20,
        agent_state=make_agent_state(
            agent_id=AGENT_ID,
            tick=20,
            position={"zone": "peripatos"},
        ),
    )

    with client.websocket_connect("/ws/observe") as ws1:
        _ = recv_envelope(ws1)
        promote_to_active(ws1)
        client.portal.call(mock_runtime.put, pre)
        got_pre = recv_envelope(ws1)

    with client.websocket_connect("/ws/observe") as ws2:
        _ = recv_envelope(ws2)
        promote_to_active(ws2)
        client.portal.call(mock_runtime.put, post)
        got_post = recv_envelope(ws2)

    assert isinstance(got_pre, AgentUpdateMsg)
    assert isinstance(got_post, AgentUpdateMsg)
    assert got_pre.agent_state.agent_id == got_post.agent_state.agent_id == AGENT_ID
    # Tick numbers move forward (monotonic) — no regression through the reconnect.
    assert got_post.agent_state.tick > got_pre.agent_state.tick
