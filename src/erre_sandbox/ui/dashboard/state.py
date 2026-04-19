"""Server-side dashboard state — metrics aggregation + threshold evaluation.

See ``.steering/20260419-ui-dashboard-minimal/decisions.md`` D3 (server-side
aggregation) and D6 (warming-up skip of 5 samples).

The three building blocks are pure Python (``collections.deque``, ``statistics``)
so they're unit-testable without a :class:`fastapi.TestClient`.

* :class:`MetricsAggregator` — rolling-window of envelope latencies + tick
  inter-arrivals + envelope-kind tallies. Produces a :class:`MetricsView`.
* :class:`ThresholdEvaluator` — compares a :class:`MetricsView` against
  :data:`erre_sandbox.integration.M2_THRESHOLDS` and yields zero or more
  :class:`AlertRecord` objects. Skips the first
  :data:`WARMING_UP_COUNT` samples.
* :class:`DashboardState` — the owner that connects the two, plus a rolling
  window of envelopes and alerts for snapshots.
"""

from __future__ import annotations

import statistics
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from erre_sandbox.integration import M2_THRESHOLDS, Thresholds
from erre_sandbox.ui.dashboard.messages import AlertRecord, MetricsView

if TYPE_CHECKING:
    from collections.abc import Iterable

    from erre_sandbox.schemas import AgentState, ControlEnvelope

WARMING_UP_COUNT: Final[int] = 5
"""Number of initial envelopes to ingest before alerts are allowed to fire.

Rationale: p50 / p95 / σ on fewer than 5 samples are statistically meaningless
and produce false-positive alerts that make the UI noisy. See decisions.md D6.
"""

DEFAULT_WINDOW_SIZE: Final[int] = 50
"""Rolling window size for latency, inter-arrival, and envelope tail."""

ALERT_BUFFER_SIZE: Final[int] = 20
"""Number of past alerts retained for the Metrics Panel."""

_JITTER_MIN_SAMPLES: Final[int] = 2
"""Minimum tick intervals required to compute jitter (need at least 2)."""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


# =============================================================================
# MetricsAggregator
# =============================================================================


class MetricsAggregator:
    """Rolling-window metrics over the last :data:`DEFAULT_WINDOW_SIZE` envelopes."""

    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE) -> None:
        self._window_size = window_size
        self._latencies_ms: deque[float] = deque(maxlen=window_size)
        self._tick_intervals_s: deque[float] = deque(maxlen=window_size)
        self._last_tick_at: float | None = None
        self._kind_counts: Counter[str] = Counter()
        self._sample_count = 0

    @property
    def sample_count(self) -> int:
        return self._sample_count

    def ingest(
        self,
        *,
        envelope: ControlEnvelope,
        latency_ms: float,
        monotonic_now: float,
    ) -> None:
        """Record one envelope observation."""
        self._sample_count += 1
        self._latencies_ms.append(latency_ms)
        self._kind_counts[envelope.kind] += 1

        if envelope.kind == "world_tick":
            if self._last_tick_at is not None:
                self._tick_intervals_s.append(monotonic_now - self._last_tick_at)
            self._last_tick_at = monotonic_now

    def snapshot(self) -> MetricsView:
        """Render the current window into a :class:`MetricsView`."""
        if self._sample_count < WARMING_UP_COUNT:
            return MetricsView(
                sample_count=self._sample_count,
                latency_p50_ms=None,
                latency_p95_ms=None,
                tick_jitter_sigma=None,
                envelope_kind_counts=dict(self._kind_counts),
            )

        latencies = sorted(self._latencies_ms)
        p50 = _percentile(latencies, 50.0)
        p95 = _percentile(latencies, 95.0)

        jitter: float | None = None
        if len(self._tick_intervals_s) >= _JITTER_MIN_SAMPLES:
            mean = statistics.fmean(self._tick_intervals_s)
            if mean > 0.0:
                jitter = statistics.pstdev(self._tick_intervals_s) / mean

        return MetricsView(
            sample_count=self._sample_count,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            tick_jitter_sigma=jitter,
            envelope_kind_counts=dict(self._kind_counts),
        )


def _percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile for a pre-sorted list."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = max(0, min(n - 1, round((p / 100.0) * (n - 1))))
    return sorted_values[k]


# =============================================================================
# ThresholdEvaluator
# =============================================================================


@dataclass(frozen=True, slots=True)
class ThresholdEvaluator:
    """Compare a :class:`MetricsView` against :class:`Thresholds` → alerts."""

    thresholds: Thresholds = M2_THRESHOLDS

    def evaluate(self, metrics: MetricsView) -> tuple[AlertRecord, ...]:
        """Return zero or more alerts for threshold violations."""
        if metrics.sample_count < WARMING_UP_COUNT:
            return ()

        alerts: list[AlertRecord] = []
        now = _utc_now()

        if (
            metrics.latency_p50_ms is not None
            and metrics.latency_p50_ms > self.thresholds.latency_p50_ms_max
        ):
            alerts.append(
                AlertRecord(
                    at=now,
                    which="latency_p50_ms",
                    current=metrics.latency_p50_ms,
                    limit=self.thresholds.latency_p50_ms_max,
                )
            )
        if (
            metrics.latency_p95_ms is not None
            and metrics.latency_p95_ms > self.thresholds.latency_p95_ms_max
        ):
            alerts.append(
                AlertRecord(
                    at=now,
                    which="latency_p95_ms",
                    current=metrics.latency_p95_ms,
                    limit=self.thresholds.latency_p95_ms_max,
                )
            )
        if (
            metrics.tick_jitter_sigma is not None
            and metrics.tick_jitter_sigma > self.thresholds.tick_jitter_sigma_max
        ):
            alerts.append(
                AlertRecord(
                    at=now,
                    which="tick_jitter_sigma",
                    current=metrics.tick_jitter_sigma,
                    limit=self.thresholds.tick_jitter_sigma_max,
                )
            )
        return tuple(alerts)


# =============================================================================
# Dashboard-state owner class
# =============================================================================


@dataclass
class DashboardState:
    """Aggregate owner wrapping aggregator, evaluator, and rolling tails.

    The instance is created per app (shared across clients) so a late-joining
    browser sees the accumulated state via :meth:`to_snapshot`.
    """

    window_size: int = DEFAULT_WINDOW_SIZE
    evaluator: ThresholdEvaluator = field(default_factory=ThresholdEvaluator)
    _aggregator: MetricsAggregator = field(init=False)
    _envelope_tail: deque[ControlEnvelope] = field(init=False)
    _alert_tail: deque[AlertRecord] = field(init=False)
    _latest_agent_state: AgentState | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._aggregator = MetricsAggregator(window_size=self.window_size)
        self._envelope_tail = deque(maxlen=self.window_size)
        self._alert_tail = deque(maxlen=ALERT_BUFFER_SIZE)

    # ----- Ingest path --------------------------------------------------

    def ingest(
        self,
        envelope: ControlEnvelope,
        *,
        latency_ms: float,
        monotonic_now: float,
    ) -> tuple[MetricsView, tuple[AlertRecord, ...]]:
        """Consume one envelope, returning the new metrics and fresh alerts."""
        self._aggregator.ingest(
            envelope=envelope,
            latency_ms=latency_ms,
            monotonic_now=monotonic_now,
        )
        self._envelope_tail.append(envelope)

        if envelope.kind == "agent_update":
            self._latest_agent_state = envelope.agent_state

        metrics = self._aggregator.snapshot()
        alerts = self.evaluator.evaluate(metrics)
        for a in alerts:
            self._alert_tail.append(a)
        return metrics, alerts

    # ----- Export path --------------------------------------------------

    def latest_agent_state(self) -> AgentState | None:
        return self._latest_agent_state

    def envelope_tail(self) -> tuple[ControlEnvelope, ...]:
        return tuple(self._envelope_tail)

    def alert_tail(self) -> tuple[AlertRecord, ...]:
        return tuple(self._alert_tail)

    def metrics(self) -> MetricsView:
        return self._aggregator.snapshot()

    def to_snapshot_payload(
        self,
    ) -> tuple[
        AgentState | None,
        tuple[ControlEnvelope, ...],
        MetricsView,
        tuple[AlertRecord, ...],
    ]:
        """Return the 4-tuple SnapshotMsg needs."""
        return (
            self._latest_agent_state,
            tuple(self._envelope_tail),
            self._aggregator.snapshot(),
            tuple(self._alert_tail),
        )

    # ----- Diagnostics --------------------------------------------------

    def __len__(self) -> int:  # pragma: no cover - trivial
        return self._aggregator.sample_count


def ingest_many(
    state: DashboardState,
    envelopes: Iterable[ControlEnvelope],
    *,
    latencies_ms: Iterable[float],
    start_monotonic: float = 0.0,
    step_s: float = 1.0,
) -> None:
    """Test helper: ingest a batch with synthetic timings."""
    t = start_monotonic
    for env, latency in zip(envelopes, latencies_ms, strict=True):
        state.ingest(env, latency_ms=latency, monotonic_now=t)
        t += step_s


__all__ = [
    "ALERT_BUFFER_SIZE",
    "DEFAULT_WINDOW_SIZE",
    "WARMING_UP_COUNT",
    "DashboardState",
    "MetricsAggregator",
    "ThresholdEvaluator",
    "ingest_many",
]
