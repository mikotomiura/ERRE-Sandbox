"""Typed metric result for M10-0 individuation (``MetricResult``).

The validators make the M10-0 claim boundary **unrepresentable to
violate** (decisions DA-M10I-4 / DA-M10I-9), not merely documented:

* ``metric_name`` must be in :data:`~.policy.METRIC_SPECS`; the spec then
  constrains ``status`` / ``channel`` / ``aggregation_level`` and whether
  a ``valid`` result must carry an ``embedding_model_id``. This is what
  rejects ``cite_belief_discipline.* = valid``, ``world_model_overlap_jaccard
  = valid`` and ``intervention_recovery_rate = valid``.
* the value/reason ↔ status coupling, finite ``value``,
  ``tick >= -1``, and the aggregation-key sentinel convention
  (HIGH-1) are all enforced here and, for the generic ones, again by the
  DuckDB ``CHECK`` clauses in :mod:`.ddl`.

``to_row`` derives its order from :func:`.ddl.row_field_names`, so the row
tuple can never drift from the table column order.
"""

from __future__ import annotations

import math
from datetime import (
    datetime,  # noqa: TC003  # used in a pydantic field annotation (must be importable at runtime)
)
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from erre_sandbox.evidence.individuation.ddl import row_field_names
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    METRIC_SPECS,
    RESERVED_POPULATION_ID,
    RESERVED_RUN_ID,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

# Import-time lockstep: the field set
# ``to_row`` flattens to is declared here independently and asserted equal
# to the DDL column order. A column added to ``ddl._INDIVIDUATION_DDL_COLUMNS``
# without a matching ``to_row`` mapping (or vice versa) fails at import,
# the same fail-fast discipline raw_dialog uses in ``eval_store``.
_TO_ROW_FIELDS: Final[tuple[str, ...]] = (
    "run_id",
    "individual_id",
    "base_persona_id",
    "aggregation_level",
    "tick",
    "metric_name",
    "channel",
    "status",
    "value",
    "reason",
    "metric_schema_version",
    "source_table",
    "source_run_id",
    "source_epoch_phase",
    "source_individual_layer_enabled",
    "source_filter_hash",
    "embedding_model_id",
    "computed_at",
)
if row_field_names() != _TO_ROW_FIELDS:
    msg = (
        "individuation MetricResult.to_row field order drifted from"
        f" ddl.row_field_names(): {_TO_ROW_FIELDS} != {row_field_names()}"
    )
    raise RuntimeError(msg)


class Provenance(BaseModel):
    """Where a metric value came from (flattened into the DDL row)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_schema_version: str
    source_table: str
    source_run_id: str
    source_epoch_phase: str
    source_individual_layer_enabled: bool
    source_filter_hash: str
    embedding_model_id: str | None = None


class MetricResult(BaseModel):
    """One typed individuation metric result for one (metric, scope) row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    individual_id: str
    base_persona_id: str
    aggregation_level: AggregationLevel
    tick: int
    metric_name: str
    channel: MetricChannel
    status: MetricStatus
    value: float | None = None
    reason: str | None = None
    provenance: Provenance
    computed_at: datetime

    @model_validator(mode="after")
    def _check_metric_spec(self) -> Self:
        spec = METRIC_SPECS.get(self.metric_name)
        if spec is None:
            msg = (
                f"unknown metric_name {self.metric_name!r}"
                f" (not in METRIC_SPECS allow-list)"
            )
            raise ValueError(msg)
        if self.status not in spec.allowed_statuses:
            msg = (
                f"metric {self.metric_name!r}: status {self.status.value!r} not"
                f" allowed (allowed: {sorted(s.value for s in spec.allowed_statuses)})"
            )
            raise ValueError(msg)
        if self.channel not in spec.allowed_channels:
            msg = (
                f"metric {self.metric_name!r}: channel {self.channel.value!r} not"
                f" allowed (allowed: {sorted(c.value for c in spec.allowed_channels)})"
            )
            raise ValueError(msg)
        if self.aggregation_level not in spec.allowed_aggregation_levels:
            msg = (
                f"metric {self.metric_name!r}: aggregation_level"
                f" {self.aggregation_level.value!r} not allowed"
            )
            raise ValueError(msg)
        if (
            spec.embedding_required
            and self.status is MetricStatus.VALID
            and self.provenance.embedding_model_id is None
        ):
            msg = (
                f"metric {self.metric_name!r}: valid result requires"
                f" embedding_model_id (embedding_required spec)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_value_reason_coupling(self) -> Self:
        if self.status is MetricStatus.VALID:
            if self.value is None or self.reason is not None:
                msg = "status='valid' requires value set and reason None"
                raise ValueError(msg)
            if not math.isfinite(self.value):
                msg = f"status='valid' value must be finite, got {self.value!r}"
                raise ValueError(msg)
        elif self.value is not None or self.reason is None:
            msg = f"status={self.status.value!r} requires value None and reason set"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_tick_floor(self) -> Self:
        if self.tick < -1:
            msg = f"tick must be >= -1 (got {self.tick}); -1 is the aggregate sentinel"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_aggregation_key_sentinels(self) -> Self:
        ind = self.individual_id
        level = self.aggregation_level
        if level is AggregationLevel.PER_INDIVIDUAL:
            if ind in {RESERVED_POPULATION_ID, RESERVED_RUN_ID} or DYAD_SEP in ind:
                msg = (
                    f"per_individual individual_id {ind!r} must be a real id"
                    f" (no reserved sentinel, no {DYAD_SEP!r})"
                )
                raise ValueError(msg)
        elif level is AggregationLevel.PER_DYAD:
            if DYAD_SEP not in ind:
                msg = (
                    f"per_dyad individual_id {ind!r} must be a {DYAD_SEP!r}-joined pair"
                )
                raise ValueError(msg)
        elif level is AggregationLevel.POPULATION:
            if ind != RESERVED_POPULATION_ID:
                msg = f"population individual_id must be {RESERVED_POPULATION_ID!r}"
                raise ValueError(msg)
        elif (
            ind != RESERVED_RUN_ID or self.base_persona_id != RESERVED_RUN_ID
        ):  # AggregationLevel.RUN
            msg = (
                f"run row requires individual_id and base_persona_id"
                f" == {RESERVED_RUN_ID!r}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_computed_at_tz_aware(self) -> Self:
        if self.computed_at.tzinfo is None:
            msg = "computed_at must be timezone-aware (UTC)"
            raise ValueError(msg)
        return self

    def to_row(self) -> tuple[object, ...]:
        """Flatten to the 18-element DDL row tuple (column order from ddl)."""
        flat: dict[str, object] = {
            "run_id": self.run_id,
            "individual_id": self.individual_id,
            "base_persona_id": self.base_persona_id,
            "aggregation_level": self.aggregation_level.value,
            "tick": self.tick,
            "metric_name": self.metric_name,
            "channel": self.channel.value,
            "status": self.status.value,
            "value": self.value,
            "reason": self.reason,
            "metric_schema_version": self.provenance.metric_schema_version,
            "source_table": self.provenance.source_table,
            "source_run_id": self.provenance.source_run_id,
            "source_epoch_phase": self.provenance.source_epoch_phase,
            "source_individual_layer_enabled": (
                self.provenance.source_individual_layer_enabled
            ),
            "source_filter_hash": self.provenance.source_filter_hash,
            "embedding_model_id": self.provenance.embedding_model_id,
            "computed_at": self.computed_at,
        }
        return tuple(flat[name] for name in _TO_ROW_FIELDS)

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict with provenance kept nested (for the sidecar)."""
        return self.model_dump(mode="json")


__all__ = [
    "MetricResult",
    "Provenance",
]
