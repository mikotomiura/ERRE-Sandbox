"""Type-level checks for the UiMessage discriminated union."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from erre_sandbox.ui.dashboard.messages import (
    AlertMsg,
    AlertRecord,
    DeltaMsg,
    MetricsView,
    SnapshotMsg,
    UiMessage,
)


def _view() -> MetricsView:
    return MetricsView(
        sample_count=0,
        latency_p50_ms=None,
        latency_p95_ms=None,
        tick_jitter_sigma=None,
        envelope_kind_counts={},
    )


def test_ui_message_adapter_parses_snapshot_kind() -> None:
    adapter: TypeAdapter[UiMessage] = TypeAdapter(UiMessage)
    msg = SnapshotMsg(
        agent_state=None,
        envelope_tail=(),
        metrics=_view(),
        alerts=(),
    )
    round_tripped = adapter.validate_json(msg.model_dump_json())
    assert isinstance(round_tripped, SnapshotMsg)


def test_ui_message_adapter_parses_alert_kind() -> None:
    adapter: TypeAdapter[UiMessage] = TypeAdapter(UiMessage)
    record = AlertRecord.model_validate(
        {
            "at": "2026-04-19T00:00:00Z",
            "which": "latency_p50_ms",
            "current": 200.0,
            "limit": 100.0,
        }
    )
    msg = AlertMsg(alert=record)
    round_tripped = adapter.validate_json(msg.model_dump_json())
    assert isinstance(round_tripped, AlertMsg)
    assert round_tripped.alert.which == "latency_p50_ms"


def test_ui_message_adapter_rejects_unknown_kind() -> None:
    adapter: TypeAdapter[UiMessage] = TypeAdapter(UiMessage)
    bogus = json.dumps({"kind": "mystery", "sent_at": "2026-04-19T00:00:00Z"})
    try:
        adapter.validate_json(bogus)
    except Exception:  # noqa: BLE001
        return
    raise AssertionError("unknown kind was not rejected")


def test_delta_and_snapshot_share_metrics_shape() -> None:
    delta = DeltaMsg.model_fields
    assert "envelope" in delta
    assert "metrics" in delta
    snap = SnapshotMsg.model_fields
    assert "agent_state" in snap
    assert "envelope_tail" in snap
    assert "metrics" in snap
    assert "alerts" in snap
