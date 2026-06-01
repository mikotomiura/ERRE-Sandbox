"""§C.9 behaviour pin: Layer 1 × Layer 2 cross-correlation is NOT computed at M10-0.

The correlation matrix is Layer 1 (per_individual) × Layer 1 only. The Layer 2
cite_belief pins are unsupported, ``intervention_recovery_rate`` is never valid,
and ``world_model_overlap_jaccard`` — VALID-capable from M10-A S3 (E2b) — is a
per_dyad gate metric, never a per_individual correlation axis (DA-S3-6); so none
of them may enter the correlation matrix or its pairs. Layer 1 × Layer 2 /
Layer 2 × Layer 2 cross-correlation is deferred to M11-C.
"""

from __future__ import annotations

from datetime import UTC, datetime

from erre_sandbox.evidence.individuation.cite_belief import all_cite_belief_pins
from erre_sandbox.evidence.individuation.correlation import (
    CorrelationStatus,
    correlate_individuation,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.report import build_report

_NOW = datetime(2026, 5, 26, tzinfo=UTC)

_LAYER2_NAMES = {
    "cite_belief_discipline.provisional_to_promoted_rate",
    "cite_belief_discipline.cited_memory_id_source_distribution",
    "cite_belief_discipline.counterfactual_challenge_rejection_rate",
}
# Excluded from the correlation matrix: ``intervention_recovery_rate`` is still
# never-VALID (M11-C), and ``world_model_overlap_jaccard`` — VALID-capable since
# M10-A S3 (E2b) — is a per_dyad gate metric, never a per_individual correlation
# axis (DA-S3-6). Both must stay out of the matrix.
_EXCLUDED_FROM_CORRELATION = {
    "world_model_overlap_jaccard",
    "intervention_recovery_rate",
}


def _prov(run_id: str) -> Provenance:
    return Provenance(
        metric_schema_version="m10-0.1",
        source_table="raw_dialog.dialog",
        source_run_id=run_id,
        source_epoch_phase="autonomous",
        source_individual_layer_enabled=False,
        source_filter_hash="deadbeef",
    )


def _valid(
    name: str, channel: MetricChannel, run_id: str, ind: str, value: float
) -> MetricResult:
    return MetricResult(
        run_id=run_id,
        individual_id=ind,
        base_persona_id="kant",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name=name,
        channel=channel,
        status=MetricStatus.VALID,
        value=value,
        reason=None,
        provenance=_prov(run_id),
        computed_at=_NOW,
    )


def _reports_with_layer2() -> list[object]:
    """Two valid Layer 1 metrics + the three Layer 2 unsupported pins per run."""
    reports: list[object] = []
    for i in range(4):
        run_id = f"run{i}"
        ind = f"a_{i}"
        rows: list[MetricResult] = [
            _valid(
                "burrows_base_retention",
                MetricChannel.UTTERANCE,
                run_id,
                ind,
                0.1 + 0.2 * i,
            ),
            _valid(
                "zone_behavior_consistency",
                MetricChannel.BEHAVIORAL,
                run_id,
                ind,
                0.2 + 0.2 * i,
            ),
        ]
        rows.extend(
            all_cite_belief_pins(
                run_id=run_id,
                individual_id=ind,
                base_persona_id="kant",
                source_epoch_phase="autonomous",
                source_individual_layer_enabled=False,
                computed_at=_NOW,
            )
        )
        reports.append(build_report(run_id, rows, computed_at=_NOW))
    return reports


def test_layer2_pins_never_enter_matrix() -> None:
    report = correlate_individuation(_reports_with_layer2(), computed_at=_NOW)
    assert report.correlation_status is CorrelationStatus.COMPUTED
    # No Layer 2 / never-valid name appears in the matrix or any pair.
    forbidden = _LAYER2_NAMES | _EXCLUDED_FROM_CORRELATION
    assert forbidden.isdisjoint(report.metrics_in_matrix)
    for pair in report.pairs:
        assert pair.metric_a not in forbidden
        assert pair.metric_b not in forbidden


def test_no_cross_layer_pair_emitted() -> None:
    report = correlate_individuation(_reports_with_layer2(), computed_at=_NOW)
    # Only the single Layer 1 × Layer 1 pair (burrows, zone) is produced;
    # no Layer 1 × Layer 2 cross pair exists (cross is M11-C territory).
    assert len(report.pairs) == 1
    only = report.pairs[0]
    assert {only.metric_a, only.metric_b} == {
        "burrows_base_retention",
        "zone_behavior_consistency",
    }


def test_layer2_pins_not_recorded_as_excluded_metrics() -> None:
    # Layer 2 pins are unsupported (not valid), so they are simply absent — they
    # are not "excluded" (that reason space is for valid-but-unusable metrics).
    report = correlate_individuation(_reports_with_layer2(), computed_at=_NOW)
    excluded_names = {e.metric_name for e in report.excluded_metrics}
    assert _LAYER2_NAMES.isdisjoint(excluded_names)


# --- M10-A S2 (E3): diagnostic metrics excluded from correlation (DA-S2-4) ---


def test_diagnostic_metrics_not_in_candidate_set() -> None:
    """Codex CX5: narrative / development are valid-capable per_individual but
    excluded; the M10-0 candidate set is unchanged (pin churn zero)."""
    from erre_sandbox.evidence.individuation.correlation import _candidate_metrics

    candidates = set(_candidate_metrics())
    assert "narrative_coherence" not in candidates
    assert "development_stage_ordinal" not in candidates
    # the existing M10-0 candidate set still present (unchanged)
    assert {
        "burrows_base_retention",
        "zone_behavior_consistency",
        "belief_variance",
    } <= candidates


def test_diagnostic_metric_listed_excluded_not_in_matrix() -> None:
    """A valid diagnostic metric is reported excluded (reason diagnostic_only) and
    never enters the matrix / a pair (Codex CX5 transparency)."""
    reports: list[object] = []
    for i in range(4):
        run_id = f"run{i}"
        ind = f"a_{i}"
        rows: list[MetricResult] = [
            _valid(
                "burrows_base_retention",
                MetricChannel.UTTERANCE,
                run_id,
                ind,
                0.1 + 0.2 * i,
            ),
            _valid(
                "zone_behavior_consistency",
                MetricChannel.BEHAVIORAL,
                run_id,
                ind,
                0.2 + 0.2 * i,
            ),
            _valid(
                "narrative_coherence",
                MetricChannel.NARRATIVE,
                run_id,
                ind,
                0.3 + 0.1 * i,
            ),
        ]
        reports.append(build_report(run_id, rows, computed_at=_NOW))
    report = correlate_individuation(reports, computed_at=_NOW)
    assert "narrative_coherence" not in report.metrics_in_matrix
    for pair in report.pairs:
        assert "narrative_coherence" not in (pair.metric_a, pair.metric_b)
    excluded = {(e.metric_name, e.reason) for e in report.excluded_metrics}
    assert ("narrative_coherence", "diagnostic_only") in excluded
