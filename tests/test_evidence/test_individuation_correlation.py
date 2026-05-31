"""WP8 correlation unit coverage (M10-0 individuation PR-3).

Exercises the Pearson path on synthetic ``MetricResult`` rows (no live capture,
no embedding model): manual-value agreement, the ``|r| >= 0.85`` flag, the
honest ``insufficient`` degradation, NaN / constant / pairwise-n=2 safety, the
wrong-observation-unit exclusion of centroid / vendi, the deliberate
``CorrelationStatus`` vs ``MetricStatus`` vocabulary split, and the sidecar
writer (suffix / round-trip / atomic).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from erre_sandbox.evidence.individuation.correlation import (
    CORRELATION_SIDECAR_SUFFIX,
    CorrelationReport,
    CorrelationStatus,
    correlate_individuation,
    correlation_sidecar_path_for,
    write_correlation_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.report import build_report

_NOW = datetime(2026, 5, 26, tzinfo=UTC)

# per_individual candidate metrics and their (single) channel.
_BURROWS = ("burrows_base_retention", MetricChannel.UTTERANCE)
_ZONE = ("zone_behavior_consistency", MetricChannel.BEHAVIORAL)
_HABIT = ("cognitive_habit_recall_rate", MetricChannel.BEHAVIORAL)


def _provenance(run_id: str, *, embedding: str | None = None) -> Provenance:
    return Provenance(
        metric_schema_version="m10-0.1",
        source_table="raw_dialog.dialog",
        source_run_id=run_id,
        source_epoch_phase="autonomous",
        source_individual_layer_enabled=False,
        source_filter_hash="deadbeef",
        embedding_model_id=embedding,
    )


def _valid(
    metric: tuple[str, MetricChannel],
    run_id: str,
    individual_id: str,
    value: float,
) -> MetricResult:
    name, channel = metric
    return MetricResult(
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id="kant",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name=name,
        channel=channel,
        status=MetricStatus.VALID,
        value=value,
        reason=None,
        provenance=_provenance(run_id),
        computed_at=_NOW,
    )


def _degenerate(
    metric: tuple[str, MetricChannel], run_id: str, individual_id: str
) -> MetricResult:
    name, channel = metric
    return MetricResult(
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id="kant",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name=name,
        channel=channel,
        status=MetricStatus.DEGENERATE,
        value=None,
        reason="synthetic degenerate cell",
        provenance=_provenance(run_id),
        computed_at=_NOW,
    )


def _report(run_id: str, results: list[MetricResult]) -> object:
    return build_report(run_id, results, computed_at=_NOW)


def _one_individual_reports(
    burrows: list[float | None], zone: list[float | None]
) -> list[object]:
    """One report per run, each run one individual, with optional burrows/zone."""
    reports: list[object] = []
    for i, (b, z) in enumerate(zip(burrows, zone, strict=True)):
        run_id = f"run{i}"
        ind = f"a_{i}"
        rows: list[MetricResult] = []
        rows.append(
            _valid(_BURROWS, run_id, ind, b)
            if b is not None
            else _degenerate(_BURROWS, run_id, ind)
        )
        rows.append(
            _valid(_ZONE, run_id, ind, z)
            if z is not None
            else _degenerate(_ZONE, run_id, ind)
        )
        reports.append(_report(run_id, rows))
    return reports


def test_two_metrics_pearson_matches_numpy() -> None:
    burrows = [0.1, 0.5, 0.9, 0.3]
    zone = [0.2, 0.6, 1.0, 0.45]
    report = correlate_individuation(
        _one_individual_reports(burrows, zone), computed_at=_NOW
    )
    assert report.correlation_status is CorrelationStatus.COMPUTED
    assert len(report.pairs) == 1
    pair = report.pairs[0]
    assert pair.metric_a == "burrows_base_retention"  # b < z
    assert pair.metric_b == "zone_behavior_consistency"
    assert pair.channel_a == "utterance"
    assert pair.channel_b == "behavioral"
    assert pair.n_observations == 4
    expected = float(np.corrcoef(burrows, zone)[0, 1])
    assert pair.r == pytest.approx(expected)
    assert report.metrics_in_matrix == (
        "burrows_base_retention",
        "zone_behavior_consistency",
    )


def test_high_correlation_flagged_double_measurement() -> None:
    burrows = [0.1, 0.4, 0.7, 0.95]
    zone = [0.12, 0.41, 0.69, 0.97]  # near-perfectly correlated
    report = correlate_individuation(
        _one_individual_reports(burrows, zone), computed_at=_NOW
    )
    assert report.correlation_status is CorrelationStatus.COMPUTED
    assert report.pairs[0].is_double_measurement is True
    assert report.pairs[0].abs_r >= 0.85
    assert len(report.double_measurement_warnings) == 1


def test_low_correlation_not_flagged() -> None:
    burrows = [0.1, 0.9, 0.2, 0.8]
    zone = [0.5, 0.5001, 0.9, 0.1]  # weak/no monotone relationship
    report = correlate_individuation(
        _one_individual_reports(burrows, zone), computed_at=_NOW
    )
    assert report.correlation_status is CorrelationStatus.COMPUTED
    assert report.pairs[0].is_double_measurement is False
    assert report.double_measurement_warnings == ()


def test_single_valid_metric_insufficient_not_fabricated() -> None:
    # zone valid everywhere, burrows degenerate everywhere -> 1 metric column.
    report = correlate_individuation(
        _one_individual_reports([None, None, None, None], [0.2, 0.6, 1.0, 0.4]),
        computed_at=_NOW,
    )
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT
    assert report.pairs == ()
    assert report.double_measurement_warnings == ()
    assert report.insufficient_reason is not None
    reasons = {e.reason for e in report.excluded_metrics}
    assert "no_valid_values" in reasons  # burrows had no valid cell


def test_constant_column_excluded() -> None:
    # zone is constant (zero variance) -> excluded; only burrows survives.
    report = correlate_individuation(
        _one_individual_reports([0.1, 0.5, 0.9, 0.3], [0.5, 0.5, 0.5, 0.5]),
        computed_at=_NOW,
    )
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT
    excluded = {e.metric_name: e.reason for e in report.excluded_metrics}
    assert excluded.get("zone_behavior_consistency") == "constant_column"
    # No NaN leaked into a fabricated pair.
    assert report.pairs == ()


def test_too_few_observations_excluded() -> None:
    # burrows valid in only 2 units (< min_observations=3) -> excluded.
    report = correlate_individuation(
        _one_individual_reports([0.1, 0.5, None, None], [0.2, 0.6, 1.0, 0.4]),
        computed_at=_NOW,
    )
    excluded = {e.metric_name: e.reason for e in report.excluded_metrics}
    assert excluded.get("burrows_base_retention") == "too_few_observations"
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT


def test_nan_cell_pairwise_complete_counts() -> None:
    # burrows valid in all 4 units; zone valid in 3 (one degenerate).
    burrows = [0.1, 0.5, 0.9, 0.3]
    zone: list[float | None] = [0.2, 0.6, 1.0, None]
    report = correlate_individuation(
        _one_individual_reports(burrows, zone), computed_at=_NOW
    )
    assert report.correlation_status is CorrelationStatus.COMPUTED
    pair = report.pairs[0]
    assert pair.n_observations == 3  # pairwise-complete over the 3 shared units
    expected = float(np.corrcoef(burrows[:3], [0.2, 0.6, 1.0])[0, 1])
    assert pair.r == pytest.approx(expected)


def test_pairwise_n_equals_2_pair_skipped() -> None:
    # Both columns clear the column filter (>=3 valid each) but their pairwise
    # overlap is only 2 -> the pair is skipped (no spurious |r|=1).
    burrows: list[float | None] = [0.1, 0.4, 0.7, 0.9, None, None]
    zone: list[float | None] = [None, None, 0.3, 0.6, 0.8, 0.95]
    report = correlate_individuation(
        _one_individual_reports(burrows, zone), computed_at=_NOW
    )
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT
    assert report.pairs == ()
    assert "pairwise-complete" in (report.insufficient_reason or "")


def test_dyad_and_population_excluded_wrong_observation_unit() -> None:
    # Two per_individual metrics (valid pair) + a per_dyad centroid + a
    # population vendi: the latter two must be excluded, not correlated.
    reports: list[object] = []
    for i in range(3):
        run_id = f"run{i}"
        rows = [
            _valid(_BURROWS, run_id, f"a_{i}", 0.1 + 0.3 * i),
            _valid(_ZONE, run_id, f"a_{i}", 0.2 + 0.25 * i),
            MetricResult(
                run_id=run_id,
                individual_id=f"a_{i}|b_{i}",
                base_persona_id="kant|kant",
                aggregation_level=AggregationLevel.PER_DYAD,
                tick=-1,
                metric_name="semantic_centroid_distance",
                channel=MetricChannel.UTTERANCE,
                status=MetricStatus.VALID,
                value=0.3,
                reason=None,
                provenance=_provenance(run_id, embedding="stub:identity"),
                computed_at=_NOW,
            ),
            MetricResult(
                run_id=run_id,
                individual_id="__population__",
                base_persona_id="kant",
                aggregation_level=AggregationLevel.POPULATION,
                tick=-1,
                metric_name="vendi_diversity",
                channel=MetricChannel.UTTERANCE,
                status=MetricStatus.VALID,
                value=1.5,
                reason=None,
                provenance=_provenance(run_id, embedding="stub:identity"),
                computed_at=_NOW,
            ),
        ]
        reports.append(_report(run_id, rows))
    report = correlate_individuation(reports, computed_at=_NOW)
    assert report.correlation_status is CorrelationStatus.COMPUTED
    excluded = {e.metric_name: e.reason for e in report.excluded_metrics}
    assert excluded.get("semantic_centroid_distance") == "wrong_observation_unit"
    assert excluded.get("vendi_diversity") == "wrong_observation_unit"
    assert "semantic_centroid_distance" not in report.metrics_in_matrix
    assert "vendi_diversity" not in report.metrics_in_matrix


def test_conflicting_valid_value_raises() -> None:
    run_id = "run0"
    rows = [_valid(_BURROWS, run_id, "a_0", 0.1)]
    rows_conflict = [_valid(_BURROWS, run_id, "a_0", 0.9)]
    reports = [_report(run_id, rows), _report(run_id, rows_conflict)]
    with pytest.raises(ValueError, match="conflicting valid values"):
        correlate_individuation(reports, computed_at=_NOW)


def test_empty_reports_insufficient_not_raise() -> None:
    report = correlate_individuation([], computed_at=_NOW)
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT
    assert report.n_observation_units == 0
    assert report.run_ids == ()


def test_correlation_status_disjoint_from_metric_status() -> None:
    corr_values = {s.value for s in CorrelationStatus}
    metric_values = {s.value for s in MetricStatus}
    assert corr_values.isdisjoint(metric_values)
    assert "insufficient" not in metric_values


def test_three_metrics_emit_three_pairs() -> None:
    # burrows, zone, habit all valid & non-constant across 4 units -> C(3,2)=3.
    reports: list[object] = []
    vals = {
        _BURROWS: [0.1, 0.5, 0.9, 0.3],
        _ZONE: [0.2, 0.6, 1.0, 0.4],
        _HABIT: [0.9, 0.1, 0.4, 0.7],
    }
    for i in range(4):
        run_id = f"run{i}"
        rows = [_valid(m, run_id, f"a_{i}", vals[m][i]) for m in vals]
        reports.append(_report(run_id, rows))
    report = correlate_individuation(reports, computed_at=_NOW)
    assert report.correlation_status is CorrelationStatus.COMPUTED
    assert len(report.pairs) == 3
    assert report.metrics_in_matrix == (
        "burrows_base_retention",
        "cognitive_habit_recall_rate",
        "zone_behavior_consistency",
    )


# --- sidecar writer (user review #4) ---------------------------------------


def _computed_report() -> CorrelationReport:
    return correlate_individuation(
        _one_individual_reports([0.1, 0.5, 0.9, 0.3], [0.2, 0.6, 1.0, 0.45]),
        computed_at=_NOW,
    )


def test_sidecar_path_suffix() -> None:
    path = correlation_sidecar_path_for("data/run0.duckdb")
    assert path.name == "run0.duckdb" + CORRELATION_SIDECAR_SUFFIX
    assert path.name.endswith(".individuation.correlation.json")


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    report = _computed_report()
    out = tmp_path / "run0.duckdb.individuation.correlation.json"
    write_correlation_sidecar_atomic(out, report)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == report.to_sidecar_dict()
    # Re-validating the dict reconstructs an equal report.
    assert CorrelationReport.model_validate(loaded) == report


def test_sidecar_atomic_leaves_no_tmp(tmp_path: Path) -> None:
    report = _computed_report()
    out = tmp_path / "run0.duckdb.individuation.correlation.json"
    write_correlation_sidecar_atomic(out, report)
    assert out.exists()
    assert not (tmp_path / (out.name + ".tmp")).exists()
