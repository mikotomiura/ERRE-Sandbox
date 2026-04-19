"""Unit tests for MetricsAggregator, ThresholdEvaluator, and DashboardState."""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.integration import M2_THRESHOLDS
from erre_sandbox.ui.dashboard.messages import AlertRecord, MetricsView
from erre_sandbox.ui.dashboard.state import (
    WARMING_UP_COUNT,
    MetricsAggregator,
    ThresholdEvaluator,
)
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator

if TYPE_CHECKING:
    from erre_sandbox.ui.dashboard.state import DashboardState


# ----------------------------------------------------------------------
# MetricsAggregator
# ----------------------------------------------------------------------


def test_aggregator_returns_none_during_warming_up(
    stub: StubEnvelopeGenerator,
) -> None:
    agg = MetricsAggregator()
    env, latency = stub.next()
    agg.ingest(envelope=env, latency_ms=latency, monotonic_now=0.0)
    view = agg.snapshot()
    assert view.sample_count == 1
    assert view.latency_p50_ms is None
    assert view.latency_p95_ms is None
    assert view.tick_jitter_sigma is None


def test_aggregator_computes_percentiles_after_warming_up(
    stub: StubEnvelopeGenerator,
) -> None:
    agg = MetricsAggregator()
    for i in range(10):
        env, latency = stub.next()
        agg.ingest(envelope=env, latency_ms=latency, monotonic_now=float(i))
    view = agg.snapshot()
    assert view.sample_count == 10
    assert view.latency_p50_ms is not None
    assert view.latency_p95_ms is not None
    assert view.latency_p50_ms <= view.latency_p95_ms


def test_aggregator_tracks_envelope_kind_counts(
    stub: StubEnvelopeGenerator,
) -> None:
    agg = MetricsAggregator()
    for i in range(14):  # covers 2 full cycles of 7 fixtures
        env, latency = stub.next()
        agg.ingest(envelope=env, latency_ms=latency, monotonic_now=float(i))
    view = agg.snapshot()
    assert sum(view.envelope_kind_counts.values()) == 14
    # world_tick appears once per cycle of 7 → exactly 2 occurrences
    assert view.envelope_kind_counts.get("world_tick") == 2


# ----------------------------------------------------------------------
# ThresholdEvaluator
# ----------------------------------------------------------------------


def _view_with(latency_p50: float, sample_count: int = 10) -> MetricsView:
    return MetricsView(
        sample_count=sample_count,
        latency_p50_ms=latency_p50,
        latency_p95_ms=latency_p50 * 2.0,
        tick_jitter_sigma=0.05,
        envelope_kind_counts={},
    )


def test_threshold_evaluator_no_alert_within_limits() -> None:
    evaluator = ThresholdEvaluator(thresholds=M2_THRESHOLDS)
    view = _view_with(latency_p50=50.0)
    assert evaluator.evaluate(view) == ()


def test_threshold_evaluator_alerts_on_p50_violation() -> None:
    evaluator = ThresholdEvaluator(thresholds=M2_THRESHOLDS)
    view = _view_with(latency_p50=500.0)
    alerts = evaluator.evaluate(view)
    kinds = {a.which for a in alerts}
    assert "latency_p50_ms" in kinds
    assert "latency_p95_ms" in kinds


def test_threshold_evaluator_skips_warming_up() -> None:
    evaluator = ThresholdEvaluator(thresholds=M2_THRESHOLDS)
    view = _view_with(latency_p50=500.0, sample_count=WARMING_UP_COUNT - 1)
    assert evaluator.evaluate(view) == ()


def test_threshold_evaluator_boundary_equals_limit_no_alert() -> None:
    evaluator = ThresholdEvaluator(thresholds=M2_THRESHOLDS)
    view = _view_with(latency_p50=M2_THRESHOLDS.latency_p50_ms_max)
    kinds = {a.which for a in evaluator.evaluate(view)}
    # Equality is not strictly greater, so no p50 alert
    assert "latency_p50_ms" not in kinds


# ----------------------------------------------------------------------
# Dashboard-state integration
# ----------------------------------------------------------------------


def test_dashboard_state_ingest_updates_tail_and_metrics(
    state: DashboardState,
    stub: StubEnvelopeGenerator,
) -> None:
    for i in range(10):
        env, latency = stub.next()
        state.ingest(env, latency_ms=latency, monotonic_now=float(i))
    assert len(state.envelope_tail()) == 10
    assert state.metrics().sample_count == 10
    assert state.latest_agent_state() is not None  # one of the 10 was agent_update


def test_dashboard_state_snapshot_payload_shape(
    state: DashboardState,
    stub: StubEnvelopeGenerator,
) -> None:
    for i in range(6):
        env, latency = stub.next()
        state.ingest(env, latency_ms=latency, monotonic_now=float(i))
    agent, tail, metrics, alerts = state.to_snapshot_payload()
    assert metrics.sample_count == 6
    assert isinstance(tail, tuple)
    assert isinstance(alerts, tuple)
    assert agent is None or agent.persona_id == "kant"


def test_dashboard_state_records_alerts_on_violation(
    state: DashboardState,
) -> None:
    # Manually feed an envelope with absurd latency to trigger alert.
    s = StubEnvelopeGenerator(seed=0)
    for i in range(10):
        env, _ = s.next()
        state.ingest(env, latency_ms=10_000.0, monotonic_now=float(i))
    assert isinstance(state.alert_tail(), tuple)
    assert any(a.which == "latency_p50_ms" for a in state.alert_tail())
    assert all(isinstance(a, AlertRecord) for a in state.alert_tail())
