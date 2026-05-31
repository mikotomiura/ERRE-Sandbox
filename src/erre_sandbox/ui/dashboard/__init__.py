"""Minimal observability dashboard for M2 (T18).

Public surface:

* :func:`create_app` — build a FastAPI app wired to its own
  :class:`DashboardState`.
* :class:`DashboardState` — server-side owner of the rolling window + alerts.
* :class:`MetricsAggregator` / :class:`ThresholdEvaluator` — the pure building
  blocks underneath.
* :class:`StubEnvelopeGenerator` — deterministic fixture cycler used until T14
  gateway lands.

Layer dependency (see ``architecture-rules`` skill + decisions.md D7):

* allowed: :mod:`erre_sandbox.schemas`, :mod:`erre_sandbox.integration`,
  ``fastapi``, ``uvicorn``, ``pydantic``
* forbidden: :mod:`erre_sandbox.cognition`, :mod:`erre_sandbox.memory`,
  :mod:`erre_sandbox.world`, :mod:`erre_sandbox.inference`
"""

from erre_sandbox.ui.dashboard.messages import (
    AlertMsg,
    AlertRecord,
    DeltaMsg,
    MetricsView,
    SnapshotMsg,
    UiMessage,
)
from erre_sandbox.ui.dashboard.server import create_app
from erre_sandbox.ui.dashboard.state import (
    WARMING_UP_COUNT,
    DashboardState,
    MetricsAggregator,
    ThresholdEvaluator,
)
from erre_sandbox.ui.dashboard.stub import StubEnvelopeGenerator

__all__ = [
    "WARMING_UP_COUNT",
    "AlertMsg",
    "AlertRecord",
    "DashboardState",
    "DeltaMsg",
    "MetricsAggregator",
    "MetricsView",
    "SnapshotMsg",
    "StubEnvelopeGenerator",
    "ThresholdEvaluator",
    "UiMessage",
    "create_app",
]
