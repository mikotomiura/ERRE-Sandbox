"""Tests for the m4-gateway-multi-agent-stream routing feature.

Two layers mirroring ``test_gateway.py``:

* **Layer A — pure helpers**: ``_envelope_target_agents`` + the new
  subscription filter behaviour of :class:`Registry`, plus the
  ``?subscribe=`` query-string parser.
* **Layer B — FastAPI TestClient**: N parallel WS clients connecting with
  different ``?subscribe=`` values, asserting that envelope delivery
  obeys the routing contract.

Existing ``test_gateway.py`` covers the broadcast baseline (no subscribe
param == backward-compatible broadcast) so here we focus on the
subscription axis.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from starlette.websockets import WebSocketDisconnect

from erre_sandbox.integration.gateway import (
    Registry,
    _envelope_target_agents,
    _InvalidSubscribeError,
    _parse_envelope,
    _parse_subscribe_param,
)
from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    AnimationMsg,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    ERREMode,
    ERREModeName,
    ErrorMsg,
    HandshakeMsg,
    MoveMsg,
    Position,
    SpeechMsg,
    WorldTickMsg,
    Zone,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from erre_sandbox.schemas import ControlEnvelope

    from .conftest import MockRuntime


# =============================================================================
# Layer A: pure helpers
# =============================================================================


def _agent_state(agent_id: str) -> AgentState:
    return AgentState(
        agent_id=agent_id,
        persona_id=agent_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.PERIPATOS),
        erre=ERREMode(name=ERREModeName.PERIPATETIC, entered_at_tick=0),
    )


class TestParseSubscribeParam:
    def test_none_means_broadcast(self) -> None:
        assert _parse_subscribe_param(None) is None

    def test_empty_string_means_broadcast(self) -> None:
        assert _parse_subscribe_param("") is None

    def test_wildcard_means_broadcast(self) -> None:
        assert _parse_subscribe_param("*") is None

    def test_single_agent(self) -> None:
        assert _parse_subscribe_param("kant") == frozenset({"kant"})

    def test_multiple_agents_comma_separated(self) -> None:
        assert _parse_subscribe_param("kant,nietzsche,rikyu") == frozenset(
            {"kant", "nietzsche", "rikyu"},
        )

    def test_whitespace_tolerated(self) -> None:
        assert _parse_subscribe_param(" kant , nietzsche ") == frozenset(
            {"kant", "nietzsche"},
        )

    def test_all_empty_items_means_broadcast(self) -> None:
        assert _parse_subscribe_param(",,,") is None

    def test_rejects_too_many_items(self) -> None:
        raw = ",".join(f"a{i}" for i in range(100))
        with pytest.raises(_InvalidSubscribeError, match="max is"):
            _parse_subscribe_param(raw)

    def test_rejects_too_long_item(self) -> None:
        long_name = "a" * 100
        with pytest.raises(_InvalidSubscribeError, match="exceeds"):
            _parse_subscribe_param(long_name)

    def test_rejects_oversize_raw_before_split(self) -> None:
        """Pre-check rejects multi-MB inputs before allocating a list."""
        huge = "a" * (10 * 1024 * 1024)  # 10 MB
        with pytest.raises(_InvalidSubscribeError, match="max is"):
            _parse_subscribe_param(huge)

    @pytest.mark.parametrize(
        "bad_item",
        [
            "kant/nietzsche",  # path separator
            "kant\rnietzsche",  # control char (log injection attempt)
            "kant\nnietzsche",  # newline (log injection attempt)
            "kant nietzsche",  # whitespace
            "kant\u200bnietzsche",  # zero-width unicode
            "kant.nietzsche",  # dot
        ],
    )
    def test_rejects_non_slug_characters(self, bad_item: str) -> None:
        with pytest.raises(_InvalidSubscribeError, match="persona_id slug"):
            _parse_subscribe_param(bad_item)


class TestEnvelopeTargetAgents:
    def test_agent_update_targets_its_agent(self) -> None:
        env = AgentUpdateMsg(tick=1, agent_state=_agent_state("kant"))
        assert _envelope_target_agents(env) == frozenset({"kant"})

    def test_speech_targets_its_agent(self) -> None:
        env = SpeechMsg(
            tick=1,
            agent_id="kant",
            utterance="...",
            zone=Zone.PERIPATOS,
        )
        assert _envelope_target_agents(env) == frozenset({"kant"})

    def test_move_targets_its_agent(self) -> None:
        env = MoveMsg(
            tick=1,
            agent_id="rikyu",
            target=Position(x=1.0, y=0.0, z=0.0, zone=Zone.CHASHITSU),
            speed=0.4,
        )
        assert _envelope_target_agents(env) == frozenset({"rikyu"})

    def test_animation_targets_its_agent(self) -> None:
        env = AnimationMsg(tick=1, agent_id="nietzsche", animation_name="walk")
        assert _envelope_target_agents(env) == frozenset({"nietzsche"})

    def test_dialog_initiate_targets_initiator_and_target(self) -> None:
        env = DialogInitiateMsg(
            tick=1,
            initiator_agent_id="kant",
            target_agent_id="nietzsche",
            zone=Zone.PERIPATOS,
        )
        assert _envelope_target_agents(env) == frozenset({"kant", "nietzsche"})

    def test_dialog_turn_targets_speaker_and_addressee(self) -> None:
        env = DialogTurnMsg(
            tick=1,
            dialog_id="d1",
            speaker_id="kant",
            addressee_id="rikyu",
            utterance="...",
        )
        assert _envelope_target_agents(env) == frozenset({"kant", "rikyu"})

    def test_world_tick_is_global(self) -> None:
        env = WorldTickMsg(tick=1, active_agents=3)
        assert _envelope_target_agents(env) is None

    def test_error_is_global(self) -> None:
        env = ErrorMsg(tick=1, code="x", detail="y")
        assert _envelope_target_agents(env) is None

    def test_dialog_close_is_global(self) -> None:
        env = DialogCloseMsg(tick=1, dialog_id="d1", reason="completed")
        assert _envelope_target_agents(env) is None

    def test_handshake_is_global(self) -> None:
        env = HandshakeMsg(tick=0, peer="godot")
        assert _envelope_target_agents(env) is None

    def test_every_advertised_kind_has_explicit_routing(self) -> None:
        """Exhaustiveness guard: every kind in the capability set is covered.

        Without this, a newly-added envelope would silently fall through
        ``_envelope_target_agents`` to ``None`` (global broadcast) with no
        test failure. Enumerating the expected routing here forces the
        author of a new variant to update the map intentionally.
        """
        from erre_sandbox.integration.gateway import (  # noqa: PLC0415
            _SERVER_CAPABILITIES,
        )

        # kinds whose routing is intentionally global (None).
        expected_global = {
            "handshake",
            "world_tick",
            "error",
            "dialog_close",
        }
        # kinds that must return a non-None, non-empty routing set. The
        # specific members are covered by the individual tests above; here
        # we just enforce the per-agent vs global dichotomy.
        expected_per_agent = {
            "agent_update",
            "speech",
            "move",
            "animation",
            "dialog_initiate",
            "dialog_turn",
        }
        assert set(_SERVER_CAPABILITIES) == expected_global | expected_per_agent, (
            "capability list drifted from the routing-table invariant; "
            "update _envelope_target_agents and this test together"
        )


class TestRegistrySubscriptionFilter:
    def _make_session(
        self,
        reg: Registry,
        session_id: str,
        subscribed_agents: frozenset[str] | None = None,
    ) -> asyncio.Queue[ControlEnvelope]:
        q: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
        reg.add(session_id, q, subscribed_agents=subscribed_agents)
        return q

    def test_none_subscription_receives_everything(self) -> None:
        reg = Registry()
        q = self._make_session(reg, "s1", subscribed_agents=None)
        reg.fan_out(SpeechMsg(tick=1, agent_id="kant", utterance="", zone=Zone.STUDY))
        assert q.qsize() == 1

    def test_matching_subscription_delivers(self) -> None:
        reg = Registry()
        q = self._make_session(reg, "s1", subscribed_agents=frozenset({"kant"}))
        reg.fan_out(SpeechMsg(tick=1, agent_id="kant", utterance="", zone=Zone.STUDY))
        assert q.qsize() == 1

    def test_disjoint_subscription_skips(self) -> None:
        reg = Registry()
        q = self._make_session(reg, "s1", subscribed_agents=frozenset({"nietzsche"}))
        reg.fan_out(SpeechMsg(tick=1, agent_id="kant", utterance="", zone=Zone.STUDY))
        assert q.qsize() == 0

    def test_global_envelope_reaches_every_session(self) -> None:
        reg = Registry()
        q_filtered = self._make_session(
            reg, "s1", subscribed_agents=frozenset({"kant"})
        )
        q_disjoint = self._make_session(
            reg,
            "s2",
            subscribed_agents=frozenset({"rikyu"}),
        )
        q_broadcast = self._make_session(reg, "s3", subscribed_agents=None)
        reg.fan_out(WorldTickMsg(tick=1, active_agents=3))
        reg.fan_out(DialogCloseMsg(tick=1, dialog_id="d1", reason="completed"))
        assert q_filtered.qsize() == 2
        assert q_disjoint.qsize() == 2
        assert q_broadcast.qsize() == 2

    def test_dialog_turn_reaches_both_participants(self) -> None:
        reg = Registry()
        q_kant = self._make_session(reg, "s1", subscribed_agents=frozenset({"kant"}))
        q_nie = self._make_session(
            reg,
            "s2",
            subscribed_agents=frozenset({"nietzsche"}),
        )
        q_rikyu = self._make_session(reg, "s3", subscribed_agents=frozenset({"rikyu"}))
        reg.fan_out(
            DialogTurnMsg(
                tick=1,
                dialog_id="d1",
                speaker_id="kant",
                addressee_id="nietzsche",
                utterance="",
            ),
        )
        assert q_kant.qsize() == 1
        assert q_nie.qsize() == 1
        assert q_rikyu.qsize() == 0

    def test_remove_clears_subscription(self) -> None:
        reg = Registry()
        self._make_session(reg, "s1", subscribed_agents=frozenset({"kant"}))
        reg.remove("s1")
        # After remove, the fan_out target-list is empty so no raise + no delivery.
        reg.fan_out(SpeechMsg(tick=1, agent_id="kant", utterance="", zone=Zone.STUDY))
        assert len(reg) == 0


# =============================================================================
# Layer B: TestClient integration
# =============================================================================


def _client_hs() -> str:
    return HandshakeMsg(tick=0, peer="godot").model_dump_json()


def _recv_envelope(ws: Any) -> ControlEnvelope:
    raw = ws.receive_text()
    env = _parse_envelope(raw)
    assert env is not None, f"server frame did not parse: {raw!r}"
    return env


def _drain_after_ack(ws: Any) -> list[ControlEnvelope]:
    """Read 1 frame then return immediately — used to tidy server handshake.

    We consume the server HandshakeMsg so callers can focus on their
    scenario-specific envelopes afterwards.
    """
    return [_recv_envelope(ws)]


class TestSubscribeIntegration:
    """Client connects with ``?subscribe=`` and observes filtering."""

    def test_subscribe_single_agent_receives_only_that_agent(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with client.websocket_connect("/ws/observe?subscribe=kant") as ws:
            _drain_after_ack(ws)
            ws.send_text(_client_hs())

            # Push two speech envelopes — one for kant, one for nietzsche.
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=1,
                    agent_id="kant",
                    utterance="K1",
                    zone=Zone.PERIPATOS,
                ),
            )
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=2,
                    agent_id="nietzsche",
                    utterance="N1",
                    zone=Zone.PERIPATOS,
                ),
            )
            # Sandwich a global envelope to unblock receive_text if the
            # filter was applied correctly.
            client.portal.call(
                mock_runtime.put,
                WorldTickMsg(tick=3, active_agents=2),
            )

            env1 = _recv_envelope(ws)
            assert isinstance(env1, SpeechMsg)
            assert env1.agent_id == "kant"
            env2 = _recv_envelope(ws)
            assert isinstance(env2, WorldTickMsg)

    def test_subscribe_wildcard_equals_broadcast(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with client.websocket_connect("/ws/observe?subscribe=*") as ws:
            _drain_after_ack(ws)
            ws.send_text(_client_hs())
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=1,
                    agent_id="kant",
                    utterance="K1",
                    zone=Zone.PERIPATOS,
                ),
            )
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=2,
                    agent_id="nietzsche",
                    utterance="N1",
                    zone=Zone.PERIPATOS,
                ),
            )
            env1 = _recv_envelope(ws)
            env2 = _recv_envelope(ws)
            assert isinstance(env1, SpeechMsg)
            assert isinstance(env2, SpeechMsg)
            assert {env1.agent_id, env2.agent_id} == {"kant", "nietzsche"}

    def test_subscribe_multi_agent_receives_both(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with client.websocket_connect(
            "/ws/observe?subscribe=kant,nietzsche",
        ) as ws:
            _drain_after_ack(ws)
            ws.send_text(_client_hs())
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=1,
                    agent_id="kant",
                    utterance="K",
                    zone=Zone.PERIPATOS,
                ),
            )
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=2,
                    agent_id="rikyu",  # Not subscribed — should be filtered out.
                    utterance="R",
                    zone=Zone.CHASHITSU,
                ),
            )
            client.portal.call(
                mock_runtime.put,
                SpeechMsg(
                    tick=3,
                    agent_id="nietzsche",
                    utterance="N",
                    zone=Zone.PERIPATOS,
                ),
            )

            env1 = _recv_envelope(ws)
            env2 = _recv_envelope(ws)
            assert isinstance(env1, SpeechMsg)
            assert isinstance(env2, SpeechMsg)
            assert {env1.agent_id, env2.agent_id} == {"kant", "nietzsche"}

    def test_dialog_turn_reaches_participants_not_bystanders(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with (
            client.websocket_connect("/ws/observe?subscribe=kant") as ws_kant,
            client.websocket_connect(
                "/ws/observe?subscribe=nietzsche",
            ) as ws_nie,
            client.websocket_connect("/ws/observe?subscribe=rikyu") as ws_rikyu,
        ):
            for ws in (ws_kant, ws_nie, ws_rikyu):
                _drain_after_ack(ws)
                ws.send_text(_client_hs())

            client.portal.call(
                mock_runtime.put,
                DialogTurnMsg(
                    tick=5,
                    dialog_id="d_kant_nie_0001",
                    speaker_id="kant",
                    addressee_id="nietzsche",
                    utterance="Guten Tag",
                ),
            )
            # Global WorldTickMsg sentinel so every subscriber has something
            # to receive, including rikyu (who must NOT see the dialog_turn).
            client.portal.call(
                mock_runtime.put,
                WorldTickMsg(tick=6, active_agents=3),
            )

            # Kant and Nietzsche each see the dialog_turn first, then the tick.
            assert isinstance(_recv_envelope(ws_kant), DialogTurnMsg)
            assert isinstance(_recv_envelope(ws_kant), WorldTickMsg)
            assert isinstance(_recv_envelope(ws_nie), DialogTurnMsg)
            assert isinstance(_recv_envelope(ws_nie), WorldTickMsg)
            # Rikyu only sees the tick (the dialog_turn was filtered out).
            assert isinstance(_recv_envelope(ws_rikyu), WorldTickMsg)

    def test_dialog_close_reaches_every_subscriber(
        self,
        client: TestClient,
        mock_runtime: MockRuntime,
    ) -> None:
        with (
            client.websocket_connect("/ws/observe?subscribe=kant") as ws_kant,
            client.websocket_connect("/ws/observe?subscribe=rikyu") as ws_rikyu,
        ):
            for ws in (ws_kant, ws_rikyu):
                _drain_after_ack(ws)
                ws.send_text(_client_hs())
            client.portal.call(
                mock_runtime.put,
                DialogCloseMsg(
                    tick=9,
                    dialog_id="d_kant_nie_0001",
                    reason="completed",
                ),
            )
            env_k = _recv_envelope(ws_kant)
            env_r = _recv_envelope(ws_rikyu)
            assert isinstance(env_k, DialogCloseMsg)
            assert isinstance(env_r, DialogCloseMsg)

    def test_invalid_subscribe_closes_with_error(
        self,
        client: TestClient,
    ) -> None:
        long = ",".join(f"a{i}" for i in range(100))
        with client.websocket_connect(f"/ws/observe?subscribe={long}") as ws:
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "invalid_subscribe"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()
