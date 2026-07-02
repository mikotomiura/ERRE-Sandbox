"""D0b-runtime veto smoke: monotonicity, firing-order determinism, wire round-trips."""

from __future__ import annotations

from erre_sandbox.evidence.d0_substrate.smoke import (
    D0B_EPISODE_TICKS,
    D0B_SEED,
    D0B_TICK_HZ,
    run_smoke,
)


def test_smoke_passes_on_default_seed() -> None:
    result = run_smoke(D0B_SEED)
    assert result.passed is True
    assert result.reasons == ()


def test_smoke_monotone_gap_free() -> None:
    result = run_smoke(D0B_SEED)
    assert result.monotone_gap_free is True
    assert result.n_ticks == D0B_EPISODE_TICKS


def test_smoke_affordance_order_deterministic_across_reruns() -> None:
    result1 = run_smoke(D0B_SEED)
    result2 = run_smoke(D0B_SEED)
    assert result1.affordance_order_deterministic is True
    assert result2.affordance_order_deterministic is True
    assert result1.n_affordance_events == result2.n_affordance_events
    assert result1.n_zone_transitions == result2.n_zone_transitions


def test_smoke_wire_round_trips_pass() -> None:
    result = run_smoke(D0B_SEED)
    assert result.position_round_trip_ok is True
    assert result.move_msg_round_trip_ok is True
    assert result.zone_transition_round_trip_ok is True
    assert result.agent_update_schema_round_trip_ok is True


def test_smoke_reproducible_across_seeds() -> None:
    for seed in range(4):
        result_a = run_smoke(seed)
        result_b = run_smoke(seed)
        assert result_a == result_b


def test_smoke_tick_rate_pinned_to_production_physics_hz() -> None:
    assert D0B_TICK_HZ == 30.0


def test_smoke_zone_transition_actually_exercised() -> None:
    """TASK-POST LOW fix (Codex): a zero-transition episode makes
    ``zone_transition_round_trip_ok`` pass vacuously without exercising the
    schema at all. D0B_EPISODE_TICKS must give the fixed seed's own
    start/destination pair enough travel to actually cross a zone boundary.
    """
    result = run_smoke(D0B_SEED)
    assert result.n_zone_transitions >= 1
