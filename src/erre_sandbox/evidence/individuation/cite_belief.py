"""Layer 2 (Cite-Belief Discipline) metrics — M10-0 unsupported pins.

⚠ **Claim boundary**: Layer 2 measures Cite-Belief Discipline only, **NOT
Social-ToM** (it is a process-trace prerequisite / proxy). In M10-0 all
three metrics are pinned to ``status='unsupported'`` 100% — there is no
active measurement (canonical §C.2, requirement §0, design.md §0):

* M-L2-1 ``provisional_to_promoted_rate`` — the live
  ``SemanticMemoryRecord.belief_kind`` is an *affinity* axis
  (``trust/clash/wary/curious/ambivalent``), not a provisional→promoted
  lifecycle, so the metric has no backing channel until a schema task.
* M-L2-2 ``cited_memory_id_source_distribution`` — ``cited_memory_ids``
  schema is M10-C territory.
* M-L2-3 ``counterfactual_challenge_rejection_rate`` — requires the
  perturbation protocol run, M11-C territory.

These functions read **no data**; they emit a deterministic unsupported
``MetricResult`` per individual. The ``status='unsupported'`` is enforced
both here and by :data:`~.policy.METRIC_SPECS` (the model rejects any
attempt to mark a ``cite_belief_discipline.*`` metric ``valid``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    CITE_BELIEF_CITED_MEMORY_SOURCE_DIST,
    CITE_BELIEF_COUNTERFACTUAL_REJECTION,
    CITE_BELIEF_PROVISIONAL_TO_PROMOTED,
    INDIVIDUATION_SCHEMA_VERSION,
    TICK_AGGREGATE_SENTINEL,
    UNSUPPORTED_PIN_FILTER_HASH,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

UNSUPPORTED_PIN_SOURCE_TABLE: Final[str] = "n/a:unsupported-pin"
"""``source_table`` for a pin that reads no data (honest non-source marker)."""

# Fixed reasons (verbatim from canonical design.md §C.2).
_REASON_PROVISIONAL_TO_PROMOTED: Final[str] = (
    "belief promotion lifecycle field not present in current"
    " SemanticMemoryRecord schema; metric requires schema extension or"
    " redefinition (deferred to M10-C / dedicated schema task)"
)
_REASON_CITED_MEMORY_SOURCE_DIST: Final[str] = "cited_memory_ids schema pending M10-C"
_REASON_COUNTERFACTUAL_REJECTION: Final[str] = (
    "requires perturbation protocol run, M11-C territory"
)


def _unsupported_pin(
    *,
    metric_name: str,
    channel: MetricChannel,
    reason: str,
    run_id: str,
    individual_id: str,
    base_persona_id: str,
    source_epoch_phase: str,
    source_individual_layer_enabled: bool,
    computed_at: datetime | None = None,
) -> MetricResult:
    """Build one per-individual unsupported pin for *metric_name*."""
    return MetricResult(
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=TICK_AGGREGATE_SENTINEL,
        metric_name=metric_name,
        channel=channel,
        status=MetricStatus.UNSUPPORTED,
        value=None,
        reason=reason,
        provenance=Provenance(
            metric_schema_version=INDIVIDUATION_SCHEMA_VERSION,
            source_table=UNSUPPORTED_PIN_SOURCE_TABLE,
            source_run_id=run_id,
            source_epoch_phase=source_epoch_phase,
            source_individual_layer_enabled=source_individual_layer_enabled,
            source_filter_hash=UNSUPPORTED_PIN_FILTER_HASH,
            embedding_model_id=None,
        ),
        computed_at=computed_at or datetime.now(UTC),
    )


def provisional_to_promoted_rate_pin(
    *,
    run_id: str,
    individual_id: str,
    base_persona_id: str,
    source_epoch_phase: str,
    source_individual_layer_enabled: bool,
    computed_at: datetime | None = None,
) -> MetricResult:
    """M-L2-1 pin (belief promotion lifecycle field absent)."""
    return _unsupported_pin(
        metric_name=CITE_BELIEF_PROVISIONAL_TO_PROMOTED,
        channel=MetricChannel.BELIEF_SUBSTRATE,
        reason=_REASON_PROVISIONAL_TO_PROMOTED,
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        source_epoch_phase=source_epoch_phase,
        source_individual_layer_enabled=source_individual_layer_enabled,
        computed_at=computed_at,
    )


def cited_memory_id_source_distribution_pin(
    *,
    run_id: str,
    individual_id: str,
    base_persona_id: str,
    source_epoch_phase: str,
    source_individual_layer_enabled: bool,
    computed_at: datetime | None = None,
) -> MetricResult:
    """M-L2-2 pin (cited_memory_ids schema pending M10-C)."""
    return _unsupported_pin(
        metric_name=CITE_BELIEF_CITED_MEMORY_SOURCE_DIST,
        channel=MetricChannel.CITATION_SUBSTRATE,
        reason=_REASON_CITED_MEMORY_SOURCE_DIST,
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        source_epoch_phase=source_epoch_phase,
        source_individual_layer_enabled=source_individual_layer_enabled,
        computed_at=computed_at,
    )


def counterfactual_challenge_rejection_rate_pin(
    *,
    run_id: str,
    individual_id: str,
    base_persona_id: str,
    source_epoch_phase: str,
    source_individual_layer_enabled: bool,
    computed_at: datetime | None = None,
) -> MetricResult:
    """M-L2-3 pin (requires perturbation protocol run, M11-C)."""
    return _unsupported_pin(
        metric_name=CITE_BELIEF_COUNTERFACTUAL_REJECTION,
        channel=MetricChannel.CITATION_SUBSTRATE,
        reason=_REASON_COUNTERFACTUAL_REJECTION,
        run_id=run_id,
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        source_epoch_phase=source_epoch_phase,
        source_individual_layer_enabled=source_individual_layer_enabled,
        computed_at=computed_at,
    )


def all_cite_belief_pins(
    *,
    run_id: str,
    individual_id: str,
    base_persona_id: str,
    source_epoch_phase: str,
    source_individual_layer_enabled: bool,
    computed_at: datetime | None = None,
) -> tuple[MetricResult, MetricResult, MetricResult]:
    """All three Layer 2 unsupported pins for one individual."""
    return (
        provisional_to_promoted_rate_pin(
            run_id=run_id,
            individual_id=individual_id,
            base_persona_id=base_persona_id,
            source_epoch_phase=source_epoch_phase,
            source_individual_layer_enabled=source_individual_layer_enabled,
            computed_at=computed_at,
        ),
        cited_memory_id_source_distribution_pin(
            run_id=run_id,
            individual_id=individual_id,
            base_persona_id=base_persona_id,
            source_epoch_phase=source_epoch_phase,
            source_individual_layer_enabled=source_individual_layer_enabled,
            computed_at=computed_at,
        ),
        counterfactual_challenge_rejection_rate_pin(
            run_id=run_id,
            individual_id=individual_id,
            base_persona_id=base_persona_id,
            source_epoch_phase=source_epoch_phase,
            source_individual_layer_enabled=source_individual_layer_enabled,
            computed_at=computed_at,
        ),
    )


__all__ = [
    "UNSUPPORTED_PIN_SOURCE_TABLE",
    "all_cite_belief_pins",
    "cited_memory_id_source_distribution_pin",
    "counterfactual_challenge_rejection_rate_pin",
    "provisional_to_promoted_rate_pin",
]
