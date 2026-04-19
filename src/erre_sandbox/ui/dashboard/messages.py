"""UI-side WebSocket messages for the dashboard (T18).

Three discriminated kinds mirror the ``ControlEnvelope`` pattern in
:mod:`erre_sandbox.schemas`:

* :class:`SnapshotMsg` (``kind="snapshot"``) — full state, sent once on connect.
* :class:`DeltaMsg` (``kind="delta"``) — one envelope + updated metrics, sent
  each time an envelope arrives.
* :class:`AlertMsg` (``kind="alert"``) — threshold violation notification.

Consumers: :mod:`erre_sandbox.ui.dashboard.server` emits these, the browser
client parses the ``kind`` field to dispatch to panel renderers.

Design decision: see ``.steering/20260419-ui-dashboard-minimal/decisions.md`` D2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

# These imports must remain at runtime: Pydantic v2 resolves them when the
# dashboard ``BaseModel`` subclasses below are built.
from erre_sandbox.schemas import AgentState, ControlEnvelope  # noqa: TC001


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


# =============================================================================
# Panel payload types (shared by snapshot & delta)
# =============================================================================


class MetricsView(BaseModel):
    """Current metric readings rendered in the Metrics Panel."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(..., ge=0)
    latency_p50_ms: float | None = Field(
        None,
        description="p50 of envelope latency in ms; None while warming up.",
    )
    latency_p95_ms: float | None = Field(
        None,
        description="p95 of envelope latency in ms; None while warming up.",
    )
    tick_jitter_sigma: float | None = Field(
        None,
        description="σ/μ of WorldTickMsg inter-arrival; None while warming up.",
    )
    envelope_kind_counts: dict[str, int] = Field(default_factory=dict)


class AlertRecord(BaseModel):
    """One past threshold violation kept in the rolling buffer."""

    model_config = ConfigDict(extra="forbid")

    at: datetime
    which: str
    current: float
    limit: float


# =============================================================================
# WS message kinds
# =============================================================================


class _BaseMsg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sent_at: datetime = Field(default_factory=_utc_now)


class SnapshotMsg(_BaseMsg):
    """Complete dashboard state, pushed once on client connect."""

    kind: Literal["snapshot"] = "snapshot"
    agent_state: AgentState | None
    envelope_tail: tuple[ControlEnvelope, ...]
    metrics: MetricsView
    alerts: tuple[AlertRecord, ...]


class DeltaMsg(_BaseMsg):
    """One newly-observed envelope plus the updated metrics after ingesting it."""

    kind: Literal["delta"] = "delta"
    envelope: ControlEnvelope
    metrics: MetricsView


class AlertMsg(_BaseMsg):
    """A fresh threshold violation just detected."""

    kind: Literal["alert"] = "alert"
    alert: AlertRecord


UiMessage: TypeAlias = Annotated[
    SnapshotMsg | DeltaMsg | AlertMsg,
    Field(discriminator="kind"),
]
"""Discriminated union of all server → client messages."""


__all__ = [
    "AlertMsg",
    "AlertRecord",
    "DeltaMsg",
    "MetricsView",
    "SnapshotMsg",
    "UiMessage",
]
