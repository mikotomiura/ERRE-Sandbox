"""S_WALKING scenario — Layer B1 via MockRuntime + TestClient.

Each step of :data:`erre_sandbox.integration.SCENARIO_WALKING` is exercised
by injecting the envelope a real pipeline would emit and asserting the
gateway delivers it to the connected peer with the right kind and fields.

The tests do **not** drive a real ``WorldRuntime`` / ``CognitionCycle`` —
see ``.steering/20260419-m2-integration-e2e-execution/decisions.md`` D2 for
why the contract-level Layer B1 is the right scope for CI, with the full
live stack reserved for the G-GEAR smoke run.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from erre_sandbox.schemas import (
    AgentUpdateMsg,
    AnimationMsg,
    ERREModeName,
    MoveMsg,
    WorldTickMsg,
    Zone,
)
from tests.test_integration._ws_helpers import client_handshake, recv_envelope

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from erre_sandbox.integration import Scenario
    from tests.conftest import MakeAgentState

    from .conftest import M2Logger, MockRuntime


def test_s_walking_step0_world_registers_kant_in_peripatos(
    walking_scenario: Scenario,
    client: TestClient,
    mock_runtime: MockRuntime,
    make_agent_state: MakeAgentState,
    m2_logger: M2Logger,
) -> None:
    """Step 0 — ``AgentUpdateMsg(erre=SHALLOW, zone=PERIPATOS)`` reaches the peer."""
    step = walking_scenario.steps[0]
    assert step.actor == "world"

    state = make_agent_state(
        tick=0,
        position={"zone": "peripatos"},
        erre={"name": "shallow", "entered_at_tick": 0},
    )
    env = AgentUpdateMsg(tick=0, agent_state=state)

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)  # server handshake
        ws.send_text(client_handshake())

        t0 = time.perf_counter()
        client.portal.call(mock_runtime.put, env)
        got = recv_envelope(ws)
        latency_ms = (time.perf_counter() - t0) * 1000.0

    assert isinstance(got, AgentUpdateMsg)
    assert got.agent_state.erre.name is ERREModeName.SHALLOW
    assert got.agent_state.position.zone is Zone.PERIPATOS
    m2_logger.log(
        scenario="S_WALKING", step=0, kind="agent_update", latency_ms=latency_ms
    )


def test_s_walking_step1_gateway_heartbeat(
    walking_scenario: Scenario,
    client: TestClient,
    mock_runtime: MockRuntime,
) -> None:
    """Step 1 — ``WorldTickMsg`` heartbeat reaches the peer."""
    step = walking_scenario.steps[1]
    assert step.actor == "gateway"

    tick_env = WorldTickMsg(tick=1, active_agents=1)

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        ws.send_text(client_handshake())
        client.portal.call(mock_runtime.put, tick_env)
        got = recv_envelope(ws)

    assert isinstance(got, WorldTickMsg)
    assert got.tick == 1
    assert got.active_agents == 1


def test_s_walking_step2_cognition_emits_move(
    walking_scenario: Scenario,
    client: TestClient,
    mock_runtime: MockRuntime,
    make_agent_state: MakeAgentState,
) -> None:
    """Step 2 — ``MoveMsg(speed>0)`` then ERRE-mode transition to PERIPATETIC."""
    step = walking_scenario.steps[2]
    assert step.actor == "cognition"

    move = MoveMsg(
        tick=10,
        agent_id="a_kant_001",
        target={"x": 1.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        speed=1.3,
    )
    peripatetic_state = make_agent_state(
        tick=10,
        position={"zone": "peripatos"},
        erre={"name": "peripatetic", "entered_at_tick": 10},
    )
    mode_shift = AgentUpdateMsg(tick=10, agent_state=peripatetic_state)

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        ws.send_text(client_handshake())

        client.portal.call(mock_runtime.put, move)
        got_move = recv_envelope(ws)
        client.portal.call(mock_runtime.put, mode_shift)
        got_shift = recv_envelope(ws)

    assert isinstance(got_move, MoveMsg)
    assert got_move.speed > 0.0
    assert isinstance(got_shift, AgentUpdateMsg)
    assert got_shift.agent_state.erre.name is ERREModeName.PERIPATETIC


def test_s_walking_step3_godot_avatar_moves(
    walking_scenario: Scenario,
    client: TestClient,
    mock_runtime: MockRuntime,
) -> None:
    """Step 3 — ``AnimationMsg(animation_name='walk')`` reaches the peer."""
    step = walking_scenario.steps[3]
    assert step.actor == "godot"

    anim = AnimationMsg(
        tick=11,
        agent_id="a_kant_001",
        animation_name="walk",
        loop=True,
    )

    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        ws.send_text(client_handshake())
        client.portal.call(mock_runtime.put, anim)
        got = recv_envelope(ws)

    assert isinstance(got, AnimationMsg)
    assert got.animation_name == "walk"
    assert got.loop is True
