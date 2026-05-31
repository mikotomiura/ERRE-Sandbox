"""MetricResult validator + to_row coverage (M10-0 individuation PR-1).

The validators encode the claim boundary as code (decisions DA-M10I-4 /
DA-M10I-9): these negative tests assert that ``cite_belief_discipline.*``,
``world_model_overlap_jaccard`` and ``intervention_recovery_rate`` can
never be constructed ``valid``, that the value/reason/status coupling and
finite-value rules hold, that ``tick >= -1`` and the aggregation-key
sentinel convention are enforced, and that ``to_row`` matches the DDL
column order.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from erre_sandbox.evidence.individuation.ddl import row_field_names
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    CITE_BELIEF_CITED_MEMORY_SOURCE_DIST,
    CITE_BELIEF_COUNTERFACTUAL_REJECTION,
    CITE_BELIEF_PROVISIONAL_TO_PROMOTED,
    RESERVED_POPULATION_ID,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)


def _provenance(**overrides: Any) -> Provenance:
    base: dict[str, Any] = {
        "metric_schema_version": "m10-0.1",
        "source_table": "raw_dialog.dialog",
        "source_run_id": "run0",
        "source_epoch_phase": "phase_b",
        "source_individual_layer_enabled": False,
        "source_filter_hash": "deadbeef",
        "embedding_model_id": None,
    }
    base.update(overrides)
    return Provenance(**base)


def _result(**overrides: Any) -> MetricResult:
    """A valid burrows_base_retention result; override fields per test."""
    prov_overrides = overrides.pop("provenance_overrides", {})
    base: dict[str, Any] = {
        "run_id": "run0",
        "individual_id": "kant_A",
        "base_persona_id": "kant",
        "aggregation_level": AggregationLevel.PER_INDIVIDUAL,
        "tick": 0,
        "metric_name": "burrows_base_retention",
        "channel": MetricChannel.UTTERANCE,
        "status": MetricStatus.VALID,
        "value": 0.5,
        "reason": None,
        "provenance": _provenance(**prov_overrides),
        "computed_at": datetime.now(UTC),
    }
    base.update(overrides)
    return MetricResult(**base)


def test_valid_result_constructs() -> None:
    result = _result()
    assert result.status is MetricStatus.VALID
    assert result.value == 0.5
    assert result.reason is None


def test_valid_requires_value_and_no_reason() -> None:
    with pytest.raises(ValidationError):
        _result(value=None)
    with pytest.raises(ValidationError):
        _result(reason="should not be set when valid")


def test_non_valid_requires_reason_and_no_value() -> None:
    # degenerate centroid: value None + reason set is OK
    ok = _result(
        metric_name="semantic_centroid_distance",
        aggregation_level=AggregationLevel.PER_DYAD,
        individual_id="A|B",
        status=MetricStatus.DEGENERATE,
        value=None,
        reason="requires N>=2",
        provenance_overrides={"embedding_model_id": "stub-encoder"},
    )
    assert ok.status is MetricStatus.DEGENERATE
    with pytest.raises(ValidationError):
        _result(status=MetricStatus.DEGENERATE, value=0.5, reason="bad")
    with pytest.raises(ValidationError):
        _result(status=MetricStatus.DEGENERATE, value=None, reason=None)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_valid_value_must_be_finite(bad: float) -> None:
    with pytest.raises(ValidationError):
        _result(value=bad)


def test_cite_belief_discipline_cannot_be_valid() -> None:
    # All three Layer 2 metrics: VALID is outside their spec.
    cases = (
        (CITE_BELIEF_PROVISIONAL_TO_PROMOTED, MetricChannel.BELIEF_SUBSTRATE),
        (CITE_BELIEF_CITED_MEMORY_SOURCE_DIST, MetricChannel.CITATION_SUBSTRATE),
        (CITE_BELIEF_COUNTERFACTUAL_REJECTION, MetricChannel.CITATION_SUBSTRATE),
    )
    for name, channel in cases:
        with pytest.raises(ValidationError):
            _result(
                metric_name=name,
                channel=channel,
                status=MetricStatus.VALID,
                value=0.5,
            )


def test_swm_jaccard_cannot_be_valid() -> None:
    with pytest.raises(ValidationError):
        _result(
            metric_name="world_model_overlap_jaccard",
            channel=MetricChannel.WORLD_MODEL,
            aggregation_level=AggregationLevel.PER_DYAD,
            individual_id="A|B",
            status=MetricStatus.VALID,
            value=0.5,
        )


def test_recovery_cannot_be_valid() -> None:
    with pytest.raises(ValidationError):
        _result(
            metric_name="intervention_recovery_rate",
            channel=MetricChannel.RECOVERY,
            status=MetricStatus.VALID,
            value=0.5,
        )


def test_unknown_metric_name_rejected() -> None:
    with pytest.raises(ValidationError):
        _result(metric_name="not_a_real_metric")


def test_channel_outside_spec_rejected() -> None:
    with pytest.raises(ValidationError):
        _result(channel=MetricChannel.BEHAVIORAL)  # burrows allows UTTERANCE only


def test_aggregation_level_outside_spec_rejected() -> None:
    with pytest.raises(ValidationError):
        # burrows allows per_individual only
        _result(
            aggregation_level=AggregationLevel.POPULATION,
            individual_id=RESERVED_POPULATION_ID,
        )


def test_embedding_required_valid_needs_model_id() -> None:
    # vendi_diversity is embedding_required: valid without an id is rejected
    with pytest.raises(ValidationError):
        _result(
            metric_name="vendi_diversity",
            aggregation_level=AggregationLevel.POPULATION,
            individual_id=RESERVED_POPULATION_ID,
            value=1.5,
        )
    ok = _result(
        metric_name="vendi_diversity",
        aggregation_level=AggregationLevel.POPULATION,
        individual_id=RESERVED_POPULATION_ID,
        value=1.5,
        provenance_overrides={"embedding_model_id": "stub-encoder"},
    )
    assert ok.provenance.embedding_model_id == "stub-encoder"


def test_tick_below_minus_one_rejected() -> None:
    with pytest.raises(ValidationError):
        _result(tick=-2)
    # -1 (aggregate sentinel) is allowed
    assert _result(tick=-1).tick == -1


def test_aggregation_key_sentinels() -> None:
    # per_individual must not be a reserved sentinel or contain the dyad sep
    with pytest.raises(ValidationError):
        _result(individual_id=RESERVED_POPULATION_ID)
    with pytest.raises(ValidationError):
        _result(individual_id="A|B")
    # per_dyad requires the separator
    with pytest.raises(ValidationError):
        _result(
            metric_name="semantic_centroid_distance",
            aggregation_level=AggregationLevel.PER_DYAD,
            individual_id="solo",
            status=MetricStatus.DEGENERATE,
            value=None,
            reason="N>=2",
            provenance_overrides={"embedding_model_id": "stub"},
        )
    # population requires the population sentinel
    with pytest.raises(ValidationError):
        _result(
            metric_name="vendi_diversity",
            aggregation_level=AggregationLevel.POPULATION,
            individual_id="not_sentinel",
            value=1.5,
            provenance_overrides={"embedding_model_id": "stub"},
        )


def test_computed_at_must_be_tz_aware() -> None:
    with pytest.raises(ValidationError):
        _result(computed_at=datetime(2026, 5, 25, 12, 0, 0))  # noqa: DTZ001 - naive on purpose
    aware = _result(computed_at=datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC))
    assert aware.computed_at.tzinfo is not None


def test_to_row_matches_ddl_column_order() -> None:
    result = _result()
    row = result.to_row()
    names = row_field_names()
    assert len(row) == len(names) == 18
    by_name = dict(zip(names, row, strict=True))
    assert by_name["run_id"] == "run0"
    assert by_name["aggregation_level"] == "per_individual"
    assert by_name["status"] == "valid"
    assert by_name["value"] == 0.5
    assert by_name["metric_schema_version"] == "m10-0.1"
    assert by_name["embedding_model_id"] is None


def test_frozen_and_extra_forbid() -> None:
    result = _result()
    with pytest.raises(ValidationError):
        result.value = 0.9  # type: ignore[misc]  # frozen
    with pytest.raises(ValidationError):
        _result(unexpected_field="x")


def test_to_sidecar_dict_keeps_provenance_nested() -> None:
    payload = _result().to_sidecar_dict()
    assert isinstance(payload["provenance"], dict)
    assert payload["provenance"]["metric_schema_version"] == "m10-0.1"
    assert payload["status"] == "valid"
