"""Report + sidecar coverage (M10-0 individuation PR-2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    INDIVIDUATION_SCHEMA_VERSION,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.report import (
    INDIVIDUATION_SIDECAR_SUFFIX,
    build_report,
    individuation_sidecar_path_for,
    write_individuation_error_sidecar,
    write_individuation_sidecar_atomic,
)

_NOW = datetime(2026, 5, 26, tzinfo=UTC)


def _result(
    status: MetricStatus, value: float | None, reason: str | None
) -> MetricResult:
    return MetricResult(
        run_id="run0",
        individual_id="a_kant_001",
        base_persona_id="kant",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name="zone_behavior_consistency",
        channel=MetricChannel.BEHAVIORAL,
        status=status,
        value=value,
        reason=reason,
        provenance=Provenance(
            metric_schema_version=INDIVIDUATION_SCHEMA_VERSION,
            source_table="raw_dialog.dialog",
            source_run_id="run0",
            source_epoch_phase="autonomous",
            source_individual_layer_enabled=False,
            source_filter_hash="deadbeef",
        ),
        computed_at=_NOW,
    )


def test_build_report_tallies() -> None:
    results = [
        _result(MetricStatus.VALID, 0.5, None),
        _result(MetricStatus.DEGENERATE, None, "x"),
        _result(MetricStatus.DEGENERATE, None, "y"),
    ]
    report = build_report("run0", results, computed_at=_NOW)
    assert report.schema_version == INDIVIDUATION_SCHEMA_VERSION
    assert report.counts_by_status == {"valid": 1, "degenerate": 2}
    assert report.counts_by_metric == {"zone_behavior_consistency": 3}
    assert len(report.results) == 3


def test_sidecar_path() -> None:
    p = individuation_sidecar_path_for(Path("data") / "kant_natural_run0.duckdb")
    assert p.name == "kant_natural_run0.duckdb" + INDIVIDUATION_SIDECAR_SUFFIX


def test_sidecar_roundtrip_provenance_nested(tmp_path: Path) -> None:
    report = build_report(
        "run0", [_result(MetricStatus.VALID, 0.5, None)], computed_at=_NOW
    )
    sidecar = individuation_sidecar_path_for(tmp_path / "out.duckdb")
    write_individuation_sidecar_atomic(sidecar, report)
    assert sidecar.exists()
    loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "run0"
    assert loaded["counts_by_status"] == {"valid": 1}
    # provenance stays nested inside each result
    assert loaded["results"][0]["provenance"]["source_table"] == "raw_dialog.dialog"


def test_error_sidecar(tmp_path: Path) -> None:
    sidecar = individuation_sidecar_path_for(tmp_path / "out.duckdb")
    write_individuation_error_sidecar(
        sidecar,
        run_id="run0",
        error_type="RuntimeError",
        error_summary="boom",
        computed_at=_NOW,
    )
    loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    assert loaded["status"] == "error"
    assert loaded["error_type"] == "RuntimeError"
    assert loaded["run_id"] == "run0"
