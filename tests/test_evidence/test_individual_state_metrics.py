"""M10-A S2 E3 diagnostic metrics — narrative_coherence / development_stage_ordinal.

Covers the honest-degrade + fail-fast contract (DA-S2-5 / Codex CX4): ``None`` →
unsupported, a valid substrate value → valid, an out-of-domain value (corrupt
trace) → :class:`IndividualStateMetricError`. The ordinal encoding (0/1/2, not a
continuous maturity — Codex CX2) is pinned, and the spec is asserted
``diagnostic_only`` so the metric can never enter the verdict / correlation axes.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from erre_sandbox.evidence.individuation.individual_state_metrics import (
    DEVELOPMENT_STAGE_METRIC,
    NARRATIVE_COHERENCE_METRIC,
    STAGE_ORDINAL,
    IndividualStateMetricError,
    development_stage_ordinal,
    narrative_coherence,
)
from erre_sandbox.evidence.individuation.layer1 import MetricContext
from erre_sandbox.evidence.individuation.policy import (
    METRIC_SPECS,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _ctx() -> MetricContext:
    return MetricContext(
        run_id="run0",
        individual_id="a_rikyu_001",
        base_persona_id="rikyu",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        source_epoch_phase="evaluation",
        source_individual_layer_enabled=True,
        source_filter_hash="deadbeef",
        source_table="metrics.individual_state_trace",
    )


# --- narrative_coherence ----------------------------------------------------


def test_narrative_coherence_valid() -> None:
    res = narrative_coherence(0.42, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.metric_name == NARRATIVE_COHERENCE_METRIC
    assert res.channel is MetricChannel.NARRATIVE
    assert res.value == pytest.approx(0.42)
    assert res.reason is None


def test_narrative_coherence_none_is_unsupported() -> None:
    res = narrative_coherence(None, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.UNSUPPORTED
    assert res.value is None
    assert res.reason is not None


@pytest.mark.parametrize("bad", [1.5, -1.5, float("nan"), float("inf")])
def test_narrative_coherence_out_of_domain_fails_fast(bad: float) -> None:
    with pytest.raises(IndividualStateMetricError):
        narrative_coherence(bad, ctx=_ctx(), computed_at=_NOW)


@pytest.mark.parametrize("edge", [-1.0, 1.0, 0.0])
def test_narrative_coherence_boundary_values_valid(edge: float) -> None:
    res = narrative_coherence(edge, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.value == pytest.approx(edge)


# --- development_stage_ordinal ----------------------------------------------


@pytest.mark.parametrize(
    ("stage", "code"),
    [("S1_seed", 0.0), ("S2_exploring", 1.0), ("S3_consolidated", 2.0)],
)
def test_development_stage_ordinal_valid(stage: str, code: float) -> None:
    res = development_stage_ordinal(stage, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.metric_name == DEVELOPMENT_STAGE_METRIC
    assert res.channel is MetricChannel.DEVELOPMENT
    assert res.value == pytest.approx(code)


def test_development_stage_none_is_unsupported() -> None:
    res = development_stage_ordinal(None, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.UNSUPPORTED
    assert res.value is None
    assert res.reason is not None


def test_development_stage_unknown_fails_fast() -> None:
    with pytest.raises(IndividualStateMetricError):
        development_stage_ordinal("S9_unknown", ctx=_ctx(), computed_at=_NOW)


def test_stage_ordinal_is_categorical_code_not_maturity() -> None:
    """0/1/2 categorical codes (Codex CX2), not the [0,1] maturity_score range."""
    assert set(STAGE_ORDINAL.values()) == {0.0, 1.0, 2.0}
    # ordered S1 < S2 < S3
    assert (
        STAGE_ORDINAL["S1_seed"]
        < STAGE_ORDINAL["S2_exploring"]
        < STAGE_ORDINAL["S3_consolidated"]
    )


# --- spec / claim-boundary pins ---------------------------------------------


@pytest.mark.parametrize("name", [NARRATIVE_COHERENCE_METRIC, DEVELOPMENT_STAGE_METRIC])
def test_new_metrics_are_diagnostic_only(name: str) -> None:
    """Codex CX1: the spec marks them diagnostic_only (never a verdict axis)."""
    spec = METRIC_SPECS[name]
    assert spec.diagnostic_only is True
    assert spec.allowed_aggregation_levels == frozenset(
        {AggregationLevel.PER_INDIVIDUAL}
    )
    assert spec.allowed_statuses == frozenset(
        {MetricStatus.VALID, MetricStatus.UNSUPPORTED}
    )
    assert spec.embedding_required is False


def test_existing_specs_default_not_diagnostic_only() -> None:
    """The new flag defaults False so M10-0 specs are unchanged (Codex CX1)."""
    for name in ("burrows_base_retention", "belief_variance", "vendi_diversity"):
        assert METRIC_SPECS[name].diagnostic_only is False
