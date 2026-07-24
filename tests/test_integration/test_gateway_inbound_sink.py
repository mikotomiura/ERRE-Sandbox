"""Issue 002 (M13 live-loop-closure): gateway ``inbound_sink`` opt-in wiring.

Covers ``.steering/20260724-m13-live-loop-closure/design-final.md`` Issue
002's four Acceptance Criteria:

* AC1 — ``inbound_sink=None`` (production ``bootstrap()`` shape) keeps
  ``_recv_loop`` **observationally identical** to the pre-Issue-002
  parse-and-ignore behaviour (MEDIUM-1: close code / response / log /
  timeout unchanged). A frame that happens to parse as
  :class:`WorldPerturbationMsg` is not special-cased — it fails
  :class:`ControlEnvelope` validation exactly like before and gets the
  existing ``invalid_envelope`` warning.
* AC2 — a non-``None`` :class:`InboundSink` receives every valid
  :class:`WorldPerturbationMsg` frame, FIFO-drainable, with a correlation-id
  assigned when the client left it blank.
* AC3 — even with a non-``None`` sink, a frame that fails inbound parsing
  (malformed JSON, or well-formed JSON that is invalid for *both*
  :data:`InboundEnvelope` and :class:`ControlEnvelope`) falls through to the
  existing ``invalid_envelope`` path and never touches the sink.
* AC4 — :class:`InboundSink`'s own FIFO / drop-oldest-overflow / monotonic
  ``correlation_id`` sequencing policy (LOW-1), exercised directly (no WS
  needed).

Reuses the ``mock_runtime`` fixture from ``tests/test_integration/conftest.py``
and follows the ``TestClient`` WS harness idioms established in
``test_gateway.py`` (``_recv_envelope`` / ``_promote_to_active`` /
``client.portal.call`` for touching asyncio state owned by the server-side
event loop).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from erre_sandbox.integration.gateway import _parse_envelope, make_app
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.schemas import (
    ControlEnvelope,
    ErrorMsg,
    HandshakeMsg,
    WorldLayoutMsg,
    WorldPerturbationMsg,
    WorldTickMsg,
    Zone,
)

if TYPE_CHECKING:
    from typing import Any

    from .conftest import MockRuntime

# _recv_envelope / _promote_to_active below are re-implemented locally rather
# than imported from test_gateway.py (test modules are not a shared-code
# surface) but are intentionally the same shape as its helpers so the two
# files stay easy to compare.


def _client_hs() -> str:
    return HandshakeMsg(tick=0, peer="godot").model_dump_json()


def _recv_envelope(ws: Any) -> ControlEnvelope:
    raw = ws.receive_text()
    env = _parse_envelope(raw)
    assert env is not None, f"server frame did not parse: {raw!r}"
    return env


def _promote_to_active(ws: Any) -> None:
    ws.send_text(_client_hs())
    layout = _recv_envelope(ws)
    assert isinstance(layout, WorldLayoutMsg), (
        f"expected WorldLayoutMsg between handshake and ACTIVE, got {layout!r}"
    )


def _perturbation(
    *, content: str = "a gust of wind crosses the path"
) -> WorldPerturbationMsg:
    return WorldPerturbationMsg(
        tick=0,
        target_agent_id="kant-01",
        modality="sight",
        source_zone=Zone.PERIPATOS,
        content=content,
        intensity=0.6,
    )


def _wait_for_drain(
    sink: InboundSink,
    client: TestClient,
    *,
    max_n: int,
    attempts: int = 50,
) -> list[WorldPerturbationMsg]:
    """Poll ``sink.drain`` until it yields something or ``attempts`` is exhausted.

    ``push`` happens asynchronously on the TestClient's own event-loop thread
    (triggered by the WS frame the test just sent), so a single immediate
    ``drain`` call from the test thread can race it. Mirrors the
    ``client.portal.call(asyncio.sleep, ...)`` convergence-wait idiom used by
    ``test_gateway.py::test_recv_loop_handles_clean_websocket_disconnect``.
    ``drain`` on an empty sink is side-effect free, so polling is safe.

    Cross-thread note (Opus TASK-POST LOW): this test-thread ``sink.drain``
    call and the server-side ``InboundSink.push`` it races both touch the
    same ``asyncio.Queue``-backed ``InboundSink`` without a lock — safe here
    only because ``asyncio.Queue``'s ``get_nowait``/``put_nowait`` are each
    individually GIL-atomic and this helper never mutates shared state beyond
    that queue; do not generalize this bare-poll pattern to a helper that
    needs multi-step cross-thread consistency.
    """
    for _ in range(attempts):
        drained = sink.drain(max_n)
        if drained:
            return drained
        client.portal.call(asyncio.sleep, 0.01)
    return []


class TestInboundSinkNoneObservationalIdentity:
    """AC1 — ``inbound_sink=None`` must not change existing behaviour."""

    def test_inbound_sink_none_observational_identity(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        app = make_app(runtime=mock_runtime)  # inbound_sink left at its None default
        with (
            TestClient(app) as client,
            client.websocket_connect("/ws/observe") as ws,
        ):
            server_hs = _recv_envelope(ws)
            assert isinstance(server_hs, HandshakeMsg)
            assert server_hs.peer == "g-gear"
            _promote_to_active(ws)

            # A frame that parses cleanly as WorldPerturbationMsg is *not*
            # a member of ControlEnvelope (kind="world_perturbation" is not
            # a discriminator there) — with inbound_sink=None it must get
            # exactly the pre-Issue-002 invalid_envelope warning, unchanged.
            ws.send_text(_perturbation().model_dump_json())
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "invalid_envelope"
            assert err.detail == "frame too large or failed ControlEnvelope validation"

            # Connection survives (identity of the existing non-fatal
            # invalid_envelope contract) — a real runtime envelope still
            # reaches the client afterwards.
            tick = WorldTickMsg(tick=9, active_agents=1)
            client.portal.call(mock_runtime.put, tick)
            got = _recv_envelope(ws)
            assert isinstance(got, WorldTickMsg)
            assert got.tick == 9


class TestInboundSinkEnqueues:
    """AC2 — a non-None sink receives valid WorldPerturbationMsg frames."""

    def test_inbound_sink_enqueues_perturbation(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        sink = InboundSink()
        app = make_app(runtime=mock_runtime, inbound_sink=sink)
        with (
            TestClient(app) as client,
            client.websocket_connect("/ws/observe") as ws,
        ):
            _ = _recv_envelope(ws)
            _promote_to_active(ws)

            perturbation = _perturbation(content="footsteps on the gravel path")
            ws.send_text(perturbation.model_dump_json())

            drained = _wait_for_drain(sink, client, max_n=10)
            assert len(drained) == 1
            got = drained[0]
            assert got.target_agent_id == "kant-01"
            assert got.content == "footsteps on the gravel path"
            # client left correlation_id blank -> sink assigned a monotonic id.
            assert got.correlation_id == "wp-0"

            # The gateway must not have also routed this frame through the
            # ControlEnvelope path (no invalid_envelope, no "ignored"
            # round-trip reply) — the connection stays quiescent until a
            # genuine runtime envelope arrives.
            tick = WorldTickMsg(tick=3, active_agents=1)
            client.portal.call(mock_runtime.put, tick)
            got_env = _recv_envelope(ws)
            assert isinstance(got_env, WorldTickMsg)
            assert got_env.tick == 3

    def test_inbound_sink_preserves_client_supplied_correlation_id(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        sink = InboundSink()
        app = make_app(runtime=mock_runtime, inbound_sink=sink)
        with (
            TestClient(app) as client,
            client.websocket_connect("/ws/observe") as ws,
        ):
            _ = _recv_envelope(ws)
            _promote_to_active(ws)

            perturbation = _perturbation().model_copy(
                update={"correlation_id": "godot-supplied-42"},
            )
            ws.send_text(perturbation.model_dump_json())

            drained = _wait_for_drain(sink, client, max_n=10)
            assert len(drained) == 1
            assert drained[0].correlation_id == "godot-supplied-42"


class TestInboundSinkInvalidFrameFallsThrough:
    """AC3 — invalid inbound frames fall through to invalid_envelope, sink untouched."""

    def test_inbound_sink_invalid_frame_falls_through(
        self,
        mock_runtime: MockRuntime,
    ) -> None:
        sink = InboundSink()
        app = make_app(runtime=mock_runtime, inbound_sink=sink)
        with (
            TestClient(app) as client,
            client.websocket_connect("/ws/observe") as ws,
        ):
            _ = _recv_envelope(ws)
            _promote_to_active(ws)

            # (a) malformed JSON — fails both InboundEnvelope and
            # ControlEnvelope parsing outright.
            ws.send_text("{not valid json")
            err = _recv_envelope(ws)
            assert isinstance(err, ErrorMsg)
            assert err.code == "invalid_envelope"

            # (b) well-formed JSON shaped like a WorldPerturbationMsg but
            # missing required fields: fails InboundEnvelope validation, and
            # "world_perturbation" is not a ControlEnvelope discriminator
            # either, so _parse_envelope also fails -> same invalid_envelope
            # path.
            broken = json.dumps({"kind": "world_perturbation", "tick": 0})
            ws.send_text(broken)
            err2 = _recv_envelope(ws)
            assert isinstance(err2, ErrorMsg)
            assert err2.code == "invalid_envelope"

            # Neither frame reached the sink.
            assert sink.drain(10) == []

            # Connection still healthy afterwards.
            tick = WorldTickMsg(tick=11, active_agents=1)
            client.portal.call(mock_runtime.put, tick)
            got = _recv_envelope(ws)
            assert isinstance(got, WorldTickMsg)
            assert got.tick == 11


class TestInboundSinkDrainPolicy:
    """AC4 — InboundSink's own FIFO / drop-oldest / monotonic-seq policy (LOW-1).

    Pure unit-level: exercises :class:`InboundSink` directly, no WS harness.
    """

    def test_fifo_order_and_drop_oldest_overflow(self) -> None:
        sink = InboundSink(maxsize=3)
        a = sink.push(_perturbation(content="a"))
        b = sink.push(_perturbation(content="b"))
        c = sink.push(_perturbation(content="c"))
        assert sink.dropped == 0

        # Queue is at maxsize=3; a 4th push evicts the oldest ("a").
        d = sink.push(_perturbation(content="d"))
        assert sink.dropped == 1

        drained = sink.drain(10)
        assert [m.content for m in drained] == ["b", "c", "d"]

        # Monotonic seq: correlation ids assigned in push order strictly increase,
        # independent of the drop-oldest eviction (seq is a push counter, not a
        # queue-position counter).
        assert (
            a.correlation_id,
            b.correlation_id,
            c.correlation_id,
            d.correlation_id,
        ) == (
            "wp-0",
            "wp-1",
            "wp-2",
            "wp-3",
        )

    def test_drain_caps_batch_size_and_stays_fifo_across_calls(self) -> None:
        sink = InboundSink(maxsize=10)
        for i in range(5):
            sink.push(_perturbation(content=str(i)))

        first_batch = sink.drain(2)
        assert [m.content for m in first_batch] == ["0", "1"]

        second_batch = sink.drain(10)
        assert [m.content for m in second_batch] == ["2", "3", "4"]

        # Draining an empty sink is a safe no-op.
        assert sink.drain(10) == []

    def test_drain_never_exceeds_max_n_even_when_more_is_queued(self) -> None:
        sink = InboundSink(maxsize=10)
        for i in range(5):
            sink.push(_perturbation(content=str(i)))

        batch = sink.drain(3)
        assert len(batch) == 3
        remaining = sink.drain(10)
        assert len(remaining) == 2
