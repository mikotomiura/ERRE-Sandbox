"""M10-A S2 diagnostic metrics: NarrativeArc / DevelopmentState (E3).

Two per-individual **diagnostic-only** metrics that surface the M11-A
``NarrativeArc`` and M11-B ``DevelopmentState`` substrate already persisted in
``metrics.individual_state_trace`` (M11-C2) — closing the reactivate-ADR §1.1
forensic gap that these axes were never defined in ``policy.METRIC_SPECS`` and
so were never measured.

These live **outside** the frozen ``layer1.py`` (terminate ADR §5.4 sentinel:
``c3b_verdict`` / ``centroid_panel`` / ``layer1`` / ``c3b_pipeline`` must stay
byte-identical), and they are ``diagnostic_only`` in the spec: never a verdict
or correlation axis (the frozen C3b verdict reads only centroid / floor /
burrows by name, and ``correlation`` excludes ``diagnostic_only`` candidates).

Honest-degrade contract (DA-S2-5, Codex CX4):

* ``None`` input → ``unsupported`` ("no substrate", mirrors ``belief_variance``'s
  ``None`` → unsupported path) — a flag-off tick, an un-synthesised arc, or an
  individual that never advanced a development stage.
* an **out-of-domain** value (coherence outside ``[-1, 1]`` / non-finite, an
  unknown development stage) is a **corrupt trace**, not a degenerate cell:
  :class:`IndividualStateMetricError` is raised (fail-fast) rather than silently
  degrading. Domain validation happens *before* any value is emitted.

Provenance: the runner stamps a **per-metric** ``source_filter_hash`` (one that
embeds this metric's own substrate field, not the belief payload — DA-S2-6 /
Codex CX3) via the loader's hash builders; this module only consumes the
already-built :class:`~erre_sandbox.evidence.individuation.layer1.MetricContext`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    INDIVIDUATION_SCHEMA_VERSION,
    MetricChannel,
    MetricStatus,
)

if TYPE_CHECKING:
    from datetime import datetime

    from erre_sandbox.evidence.individuation.layer1 import MetricContext

NARRATIVE_COHERENCE_METRIC: Final[str] = "narrative_coherence"
DEVELOPMENT_STAGE_METRIC: Final[str] = "development_stage_ordinal"

_COHERENCE_MIN: Final[float] = -1.0
_COHERENCE_MAX: Final[float] = 1.0

# Categorical ordinal code (0/1/2), NOT a continuous maturity score (the live
# DevelopmentState.maturity_score is a separate float — Codex CX2). The codes are
# never averaged / thresholded / correlated (diagnostic_only enforces this
# structurally); they exist so cross-individual divergence of the reached stage
# is observable in the individuation table.
STAGE_ORDINAL: Final[dict[str, float]] = {
    "S1_seed": 0.0,
    "S2_exploring": 1.0,
    "S3_consolidated": 2.0,
}


class IndividualStateMetricError(ValueError):
    """Raised on an out-of-domain (corrupt-trace) narrative / development value.

    Distinct from ``None`` (which is the honest "no substrate" → ``unsupported``
    path): a coherence outside ``[-1, 1]`` / non-finite, or a development stage
    not in :data:`STAGE_ORDINAL`, is a corrupted trace value — we fail fast
    rather than fabricate a degenerate cell (DA-S2-5, Codex CX4). Mirrors the
    loader's ``IndividualStateTraceSchemaError`` trusted-writer-corruption stance.
    """


def _build(
    ctx: MetricContext,
    *,
    metric_name: str,
    channel: MetricChannel,
    status: MetricStatus,
    value: float | None,
    reason: str | None,
    computed_at: datetime,
) -> MetricResult:
    """Stamp a :class:`MetricResult` from a context + outcome (layer1 ``_build`` twin).

    Kept local (not imported from frozen ``layer1``) so this module never couples
    to the frozen surface. ``embedding_model_id`` is always ``None`` — these
    metrics read the trace, never an encoder.
    """
    return MetricResult(
        run_id=ctx.run_id,
        individual_id=ctx.individual_id,
        base_persona_id=ctx.base_persona_id,
        aggregation_level=ctx.aggregation_level,
        tick=ctx.tick,
        metric_name=metric_name,
        channel=channel,
        status=status,
        value=value,
        reason=reason,
        provenance=Provenance(
            metric_schema_version=INDIVIDUATION_SCHEMA_VERSION,
            source_table=ctx.source_table,
            source_run_id=ctx.run_id,
            source_epoch_phase=ctx.source_epoch_phase,
            source_individual_layer_enabled=ctx.source_individual_layer_enabled,
            source_filter_hash=ctx.source_filter_hash,
            embedding_model_id=None,
        ),
        computed_at=computed_at,
    )


def narrative_coherence(
    coherence: float | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """NarrativeArc ``coherence_score`` as a per-individual diagnostic metric.

    ``None`` (no arc synthesised / no trace) → ``unsupported``. A finite value in
    ``[-1, 1]`` → ``valid`` with that value. Anything else (non-finite or
    out-of-range) is a corrupt trace → :class:`IndividualStateMetricError`.
    """
    name = NARRATIVE_COHERENCE_METRIC
    channel = MetricChannel.NARRATIVE
    if coherence is None:
        return _build(
            ctx,
            metric_name=name,
            channel=channel,
            status=MetricStatus.UNSUPPORTED,
            value=None,
            reason="no narrative arc synthesised (coherence_score absent)",
            computed_at=computed_at,
        )
    if not math.isfinite(coherence) or not (
        _COHERENCE_MIN <= coherence <= _COHERENCE_MAX
    ):
        msg = (
            f"coherence_score {coherence!r} is non-finite or outside"
            f" [{_COHERENCE_MIN}, {_COHERENCE_MAX}] — corrupt trace"
        )
        raise IndividualStateMetricError(msg)
    return _build(
        ctx,
        metric_name=name,
        channel=channel,
        status=MetricStatus.VALID,
        value=float(coherence),
        reason=None,
        computed_at=computed_at,
    )


def development_stage_ordinal(
    stage: str | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """DevelopmentState ``stage`` as a per-individual categorical ordinal code.

    ``None`` (no stage advanced / no trace) → ``unsupported``. A known stage →
    ``valid`` with its :data:`STAGE_ORDINAL` code (0/1/2 — a category code, not a
    continuous maturity, Codex CX2). An unknown stage string is a corrupt trace →
    :class:`IndividualStateMetricError`.
    """
    name = DEVELOPMENT_STAGE_METRIC
    channel = MetricChannel.DEVELOPMENT
    if stage is None:
        return _build(
            ctx,
            metric_name=name,
            channel=channel,
            status=MetricStatus.UNSUPPORTED,
            value=None,
            reason="no development stage advanced (development_stage absent)",
            computed_at=computed_at,
        )
    if stage not in STAGE_ORDINAL:
        msg = (
            f"development_stage {stage!r} not in {sorted(STAGE_ORDINAL)}"
            " — corrupt trace"
        )
        raise IndividualStateMetricError(msg)
    return _build(
        ctx,
        metric_name=name,
        channel=channel,
        status=MetricStatus.VALID,
        value=STAGE_ORDINAL[stage],
        reason=None,
        computed_at=computed_at,
    )


__all__ = [
    "DEVELOPMENT_STAGE_METRIC",
    "NARRATIVE_COHERENCE_METRIC",
    "STAGE_ORDINAL",
    "IndividualStateMetricError",
    "development_stage_ordinal",
    "narrative_coherence",
]
