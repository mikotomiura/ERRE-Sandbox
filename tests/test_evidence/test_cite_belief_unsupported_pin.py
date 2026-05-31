"""Golden behavior pin for Layer 2 (Cite-Belief Discipline) — M10-0.

⚠ Claim boundary (A16): Layer 2 measures Cite-Belief Discipline only,
NOT Social-ToM; in M10-0 it is unsupported pin only. This test pins that
all three metrics return ``status='unsupported'`` 100% with their fixed
reasons and provenance (A12a/b/c). If a future change flips any of them to
active without adding a real input channel, this test fails loudly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.evidence.individuation.cite_belief import (
    UNSUPPORTED_PIN_SOURCE_TABLE,
    all_cite_belief_pins,
    cited_memory_id_source_distribution_pin,
    counterfactual_challenge_rejection_rate_pin,
    provisional_to_promoted_rate_pin,
)
from erre_sandbox.evidence.individuation.policy import (
    ALLOWED_METRIC_NAMES,
    UNSUPPORTED_PIN_FILTER_HASH,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

if TYPE_CHECKING:
    from erre_sandbox.evidence.individuation.models import MetricResult

_CTX = {
    "run_id": "run0",
    "individual_id": "kant_A",
    "base_persona_id": "kant",
    "source_epoch_phase": "phase_b",
    "source_individual_layer_enabled": False,
}

_EXPECTED = {
    "cite_belief_discipline.provisional_to_promoted_rate": (
        MetricChannel.BELIEF_SUBSTRATE,
        "belief promotion lifecycle field not present",
    ),
    "cite_belief_discipline.cited_memory_id_source_distribution": (
        MetricChannel.CITATION_SUBSTRATE,
        "cited_memory_ids schema pending M10-C",
    ),
    "cite_belief_discipline.counterfactual_challenge_rejection_rate": (
        MetricChannel.CITATION_SUBSTRATE,
        "requires perturbation protocol run, M11-C territory",
    ),
}


def _assert_unsupported_pin(result: MetricResult) -> None:
    assert result.status is MetricStatus.UNSUPPORTED
    assert result.value is None
    assert result.reason is not None
    assert result.reason != ""
    assert result.metric_name in ALLOWED_METRIC_NAMES
    assert result.metric_name in _EXPECTED
    expected_channel, expected_reason_fragment = _EXPECTED[result.metric_name]
    assert result.channel is expected_channel
    assert expected_reason_fragment in result.reason
    # provenance golden (LOW-1)
    assert result.provenance.source_filter_hash == UNSUPPORTED_PIN_FILTER_HASH
    assert result.provenance.source_table == UNSUPPORTED_PIN_SOURCE_TABLE
    assert result.provenance.source_epoch_phase == "phase_b"
    assert result.provenance.embedding_model_id is None
    assert result.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    assert result.tick == -1


def test_all_three_pins_are_unsupported() -> None:
    pins = all_cite_belief_pins(**_CTX)
    assert len(pins) == 3
    names = {p.metric_name for p in pins}
    assert names == set(_EXPECTED)
    for pin in pins:
        _assert_unsupported_pin(pin)


@pytest.mark.parametrize(
    "factory",
    [
        provisional_to_promoted_rate_pin,
        cited_memory_id_source_distribution_pin,
        counterfactual_challenge_rejection_rate_pin,
    ],
)
def test_each_pin_factory_is_unsupported(factory) -> None:
    _assert_unsupported_pin(factory(**_CTX))


def test_pin_is_deterministic_given_fixed_computed_at() -> None:
    fixed = datetime(2026, 5, 25, 0, 0, 0, tzinfo=UTC)
    a = provisional_to_promoted_rate_pin(**_CTX, computed_at=fixed)
    b = provisional_to_promoted_rate_pin(**_CTX, computed_at=fixed)
    assert a.to_row() == b.to_row()
