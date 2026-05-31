"""Integration test for the M7γ on-connect WorldLayoutMsg push.

The gateway pushes exactly one ``world_layout`` envelope between handshake
validation and registry insertion so the Godot ``BoundaryLayer`` can hydrate
its zone / prop tables before any cognition-driven envelope arrives. This
file exercises the contract end-to-end through the FastAPI TestClient.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from erre_sandbox.integration.gateway import make_app
from erre_sandbox.schemas import (
    HandshakeMsg,
    PropLayout,
    WorldLayoutMsg,
    Zone,
    ZoneLayout,
)
from erre_sandbox.world.tick import WorldRuntime
from erre_sandbox.world.zones import ZONE_CENTERS, ZONE_PROPS
from tests.test_integration._ws_helpers import client_handshake, recv_envelope
from tests.test_integration.conftest import MockRuntime

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_FIXTURE = REPO_ROOT / "fixtures" / "control_envelope" / "world_layout.json"


class _StubCycle:
    """Minimal :class:`CognitionCycle` substitute for snapshot-only tests.

    The runtime never runs (no ``await runtime.run()``) so the cycle's
    ``step`` is intentionally not implemented — calls would surface as
    ``NotImplementedError`` rather than silently succeed.
    """

    async def step(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


@pytest.fixture
def runtime_with_layout() -> MockRuntime:
    """A :class:`MockRuntime` carrying a representative two-zone / one-prop layout."""
    zones = [
        ZoneLayout(zone=Zone.STUDY, x=-33.33, y=0.0, z=-33.33),
        ZoneLayout(zone=Zone.PERIPATOS, x=0.0, y=0.0, z=0.0),
    ]
    props = [
        PropLayout(
            prop_id="chawan_01",
            prop_kind="tea_bowl",
            zone=Zone.CHASHITSU,
            x=32.83,
            y=0.4,
            z=-32.83,
            salience=0.7,
        ),
    ]
    return MockRuntime(layout_zones=zones, layout_props=props)


@pytest.fixture
def app_with_layout(runtime_with_layout: MockRuntime) -> FastAPI:
    return make_app(runtime=runtime_with_layout)


@pytest.fixture
def client_with_layout(app_with_layout: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_with_layout) as c:
        yield c


def test_world_layout_arrives_after_handshake(client_with_layout: TestClient) -> None:
    """The gateway emits exactly one WorldLayoutMsg after client handshake.

    Order on the wire: server handshake → client handshake (sent by us) →
    WorldLayoutMsg → (any subsequent runtime-emitted envelopes).
    """
    with client_with_layout.websocket_connect("/ws/observe") as ws:
        server_hs = recv_envelope(ws)
        assert isinstance(server_hs, HandshakeMsg)
        ws.send_text(client_handshake())
        layout = recv_envelope(ws)
        assert isinstance(layout, WorldLayoutMsg)
        assert layout.tick == 0
        assert len(layout.zones) == 2
        assert layout.zones[0].zone is Zone.STUDY
        assert layout.zones[1].zone is Zone.PERIPATOS
        assert len(layout.props) == 1
        assert layout.props[0].prop_id == "chawan_01"
        assert layout.props[0].prop_kind == "tea_bowl"


def test_world_layout_capabilities_advertise_world_layout(
    client_with_layout: TestClient,
) -> None:
    """The server handshake's capability list announces ``world_layout``."""
    with client_with_layout.websocket_connect("/ws/observe") as ws:
        server_hs = recv_envelope(ws)
        assert isinstance(server_hs, HandshakeMsg)
        assert "world_layout" in server_hs.capabilities


def test_null_runtime_emits_empty_world_layout(client: TestClient) -> None:
    """The default :class:`MockRuntime` produces an empty (but valid) layout."""
    with client.websocket_connect("/ws/observe") as ws:
        _ = recv_envelope(ws)
        ws.send_text(client_handshake())
        layout = recv_envelope(ws)
        assert isinstance(layout, WorldLayoutMsg)
        assert layout.zones == []
        assert layout.props == []


def test_layout_envelope_matches_golden_fixture_shape() -> None:
    """The shipped fixture must validate cleanly against ``WorldLayoutMsg``."""
    raw = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    msg = WorldLayoutMsg.model_validate(raw)
    assert msg.kind == "world_layout"
    assert msg.tick == 0
    assert {z.zone for z in msg.zones} == set(Zone)
    # Two tea bowls in the chashitsu mirror ``world.zones.ZONE_PROPS``.
    tea_bowls = [p for p in msg.props if p.prop_kind == "tea_bowl"]
    assert len(tea_bowls) == 2


def test_runtime_layout_snapshot_matches_zones_module() -> None:
    """``WorldRuntime.layout_snapshot`` enumerates every Zone and prop spec."""
    runtime = WorldRuntime(cycle=_StubCycle())  # type: ignore[arg-type]
    snapshot = runtime.layout_snapshot()
    assert {z.zone for z in snapshot.zones} == set(ZONE_CENTERS)
    expected_prop_count = sum(len(specs) for specs in ZONE_PROPS.values())
    assert len(snapshot.props) == expected_prop_count
