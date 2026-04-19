"""Tests for StubEnvelopeGenerator determinism and contract conformance."""

from __future__ import annotations

from pydantic import TypeAdapter

from erre_sandbox.schemas import ControlEnvelope
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator


def test_stub_is_deterministic_with_same_seed() -> None:
    g1 = StubEnvelopeGenerator(seed=7)
    g2 = StubEnvelopeGenerator(seed=7)
    for _ in range(14):
        e1, l1 = g1.next()
        e2, l2 = g2.next()
        assert e1.kind == e2.kind
        assert l1 == l2


def test_stub_differs_between_seeds() -> None:
    g1 = StubEnvelopeGenerator(seed=1)
    g2 = StubEnvelopeGenerator(seed=2)
    diverged = False
    for _ in range(14):
        _, l1 = g1.next()
        _, l2 = g2.next()
        if l1 != l2:
            diverged = True
            break
    assert diverged, "stub outputs with different seeds must diverge"


def test_stub_emits_control_envelope_pydantic() -> None:
    adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
    g = StubEnvelopeGenerator(seed=0)
    for _ in range(7):
        env, _ = g.next()
        # Round-trip via the union to prove fixture parses every cycle.
        round_tripped = adapter.validate_json(env.model_dump_json())
        assert round_tripped.kind == env.kind


def test_stub_latency_within_noise_band() -> None:
    g = StubEnvelopeGenerator(
        seed=0,
        base_latency_ms=50.0,
        noise_half_width_ms=10.0,
    )
    for _ in range(50):
        _, latency = g.next()
        assert 40.0 <= latency <= 60.0


def test_stub_cycles_through_seven_kinds() -> None:
    g = StubEnvelopeGenerator(seed=0)
    kinds = [g.next()[0].kind for _ in range(7)]
    assert set(kinds) == {
        "handshake",
        "agent_update",
        "world_tick",
        "move",
        "animation",
        "speech",
        "error",
    }
