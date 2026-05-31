"""Tests for :mod:`erre_sandbox.evidence.capture_sidecar`.

Covers the sidecar v1 contract introduced by
``.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`` §1.4
(ME-9 ADR) and Codex 2026-05-06 review reflections:

* round-trip preserves payload exactly (atomic write + read validate).
* Literal violations on ``status`` / ``stop_reason`` raise
  :class:`pydantic.ValidationError` (Codex L2).
* ``model_config = ConfigDict(extra='allow')`` keeps unknown additive
  fields so a future ``event_log`` can be appended without bumping the
  major schema version (Codex Q2).
* :func:`expected_run_id` reconstructs the ``run_id`` the capture CLI
  persists into ``raw_dialog.dialog`` so audit can verify same-run
  integrity (Codex H1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from erre_sandbox.evidence.capture_sidecar import (
    SIDECAR_SCHEMA_VERSION,
    SIDECAR_SUFFIX,
    SidecarV1,
    expected_run_id,
    read_sidecar,
    sidecar_path_for,
    write_sidecar_atomic,
)


def _sample_payload(**overrides: object) -> SidecarV1:
    base: dict[str, object] = {
        "status": "complete",
        "stop_reason": "complete",
        "focal_target": 500,
        "focal_observed": 500,
        "total_rows": 1500,
        "wall_timeout_min": 360.0,
        "drain_completed": True,
        "runtime_drain_timeout": False,
        "git_sha": "deadbee",
        "captured_at": "2026-05-06T12:00:00Z",
        "persona": "kant",
        "condition": "natural",
        "run_idx": 0,
        "duckdb_path": "/tmp/kant_natural_run0.duckdb",  # noqa: S108
    }
    base.update(overrides)
    return SidecarV1.model_validate(base)


def test_atomic_round_trip_preserves_payload(tmp_path: Path) -> None:
    """Write then read returns equal payload field-for-field."""
    payload = _sample_payload()
    path = tmp_path / "kant_natural_run0.duckdb.capture.json"

    write_sidecar_atomic(path, payload)
    assert path.exists()
    # Temp sibling must not leak.
    assert not path.with_suffix(path.suffix + ".tmp").exists()

    loaded = read_sidecar(path)
    assert loaded.model_dump() == payload.model_dump()
    assert loaded.schema_version == SIDECAR_SCHEMA_VERSION


def test_invalid_literal_status_raises(tmp_path: Path) -> None:
    """``status`` outside the Literal set must reject at validation time."""
    bad = tmp_path / "bad.capture.json"
    bad.write_text(
        '{"schema_version":"1","status":"unknown","stop_reason":"complete",'
        '"focal_target":500,"focal_observed":500,"total_rows":1500,'
        '"wall_timeout_min":360.0,"drain_completed":true,'
        '"runtime_drain_timeout":false,"git_sha":"x","captured_at":"x",'
        '"persona":"kant","condition":"natural","run_idx":0,'
        '"duckdb_path":"x"}',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        read_sidecar(bad)


def test_extra_fields_allowed_for_forward_compat(tmp_path: Path) -> None:
    """Unknown additive fields survive validation (Codex Q2)."""
    payload_dict = _sample_payload().model_dump()
    payload_dict["event_log"] = [{"t": 1.0, "kind": "row_inserted"}]
    payload_dict["future_field"] = "ok"
    path = tmp_path / "future.capture.json"
    path.write_text(
        SidecarV1.model_validate(payload_dict).model_dump_json(),
        encoding="utf-8",
    )

    loaded = read_sidecar(path)
    # extra='allow' keeps the unknown keys round-trippable
    dumped = loaded.model_dump()
    assert dumped["event_log"] == [{"t": 1.0, "kind": "row_inserted"}]
    assert dumped["future_field"] == "ok"


def test_sidecar_path_helper_appends_suffix(tmp_path: Path) -> None:
    """``sidecar_path_for`` is the canonical naming rule."""
    duck = tmp_path / "kant_natural_run0.duckdb"
    side = sidecar_path_for(duck)
    assert side.name.endswith(SIDECAR_SUFFIX)
    assert side == tmp_path / f"kant_natural_run0.duckdb{SIDECAR_SUFFIX}"


def test_expected_run_id_round_trips_capture_naming() -> None:
    """``expected_run_id`` matches the capture CLI's ``run_id`` formula (Codex H1)."""
    payload = _sample_payload(persona="rikyu", condition="stimulus", run_idx=2)
    assert expected_run_id(payload) == "rikyu_stimulus_run2"
