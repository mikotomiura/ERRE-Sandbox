"""M10-A S3 E2b: active ``world_model_overlap_jaccard`` (SWM key-Jaccard).

The reactivate-ADR §3.A③ path(a) gate measures whether same-base individuals'
``SubjectiveWorldModel`` key-sets separate (median pairwise Jaccard ≤ 0.60). At
M10-0 this metric was a frozen ``layer1`` stub pinned ``unsupported`` (SWM not
captured). S1 (E2) persisted the final-tick ``(axis, key)`` set into
``metrics.individual_state_trace.world_model_keys_json``; this module turns that
substrate into the **active** metric.

**Case A architecture (DA-S3-1)**: the metric keeps the frozen name
``world_model_overlap_jaccard`` (the ADR names it) but the *active* implementation
lives here, outside the frozen ``layer1.py`` (terminate ADR §5.4 sentinel). The
runner calls this active fn only for **two distinct individuals whose SWM key-set
is present**; a self-pair (N=1, ``A|A``) or an absent SWM falls back to the frozen
``layer1`` stub (``unsupported``) — so a meaningless self-overlap of ``1.0`` is
never emitted and the never-VALID claim continues to hold when the input is absent.

Strict VALID conditions (DA-S3-3 / user C-2):

* ``None`` key-set → :class:`WorldModelOverlapMetricError` (defence in depth — the
  runner gates None to the stub fallback, so the active fn should never see it).
* both key-sets canonical set-ised (duplicate ``(axis, key)`` pairs removed) before
  the Jaccard, so a writer emitting a duplicate pair cannot inflate the union.
* empty union (both SWMs empty) → ``degenerate`` ("empty world-model union",
  Jaccard undefined) — never a fabricated ``0`` / ``1``.
* one side empty, the other non-empty → union non-empty → ``0.0`` valid (maximal
  separation).
* otherwise ``valid`` with ``value = |A∩B| / |A∪B| ∈ [0, 1]``.

Provenance is **not** assembled here: the runner stamps a trace-table source +
the world-model-specific ``source_filter_hash`` (DA-S3-2 / C-1) onto the
:class:`~erre_sandbox.evidence.individuation.layer1.MetricContext` before calling.
"""

from __future__ import annotations

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

WORLD_MODEL_OVERLAP_METRIC: Final[str] = "world_model_overlap_jaccard"
"""Active metric name — identical to the frozen layer1 stub (Case A, DA-S3-1)."""


class WorldModelOverlapMetricError(ValueError):
    """Raised when the active fn is called with a ``None`` SWM key-set.

    ``None`` is the runner's "SWM not captured" signal and must route to the frozen
    ``layer1`` stub (``unsupported``), never here. Receiving it means the runner's
    gating is broken, so we fail fast rather than fabricate a degenerate cell
    (mirrors ``individual_state_metrics.IndividualStateMetricError``'s stance).
    """


def _build(
    ctx: MetricContext,
    *,
    status: MetricStatus,
    value: float | None,
    reason: str | None,
    computed_at: datetime,
) -> MetricResult:
    """Stamp a :class:`MetricResult` (frozen ``layer1._build`` twin, kept local)."""
    return MetricResult(
        run_id=ctx.run_id,
        individual_id=ctx.individual_id,
        base_persona_id=ctx.base_persona_id,
        aggregation_level=ctx.aggregation_level,
        tick=ctx.tick,
        metric_name=WORLD_MODEL_OVERLAP_METRIC,
        channel=MetricChannel.WORLD_MODEL,
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


def world_model_overlap_jaccard_active(
    keys_a: tuple[tuple[str, str], ...] | None,
    keys_b: tuple[tuple[str, str], ...] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Active SWM key-Jaccard between two distinct same-base individuals.

    See the module docstring for the strict VALID/degenerate/fail-fast contract.
    The caller (runner) is responsible for only invoking this on two *distinct*
    individuals with *present* SWM key-sets; ``None`` here is a programming error.
    """
    if keys_a is None or keys_b is None:
        msg = (
            "world_model_overlap_jaccard_active received a None key-set;"
            " absent SWM must route to the layer1 stub fallback (unsupported)"
        )
        raise WorldModelOverlapMetricError(msg)
    set_a = frozenset(keys_a)
    set_b = frozenset(keys_b)
    union = set_a | set_b
    if not union:
        return _build(
            ctx,
            status=MetricStatus.DEGENERATE,
            value=None,
            reason="empty world-model union (both SWMs empty); Jaccard undefined",
            computed_at=computed_at,
        )
    jaccard = len(set_a & set_b) / len(union)
    return _build(
        ctx,
        status=MetricStatus.VALID,
        value=jaccard,
        reason=None,
        computed_at=computed_at,
    )


__all__ = [
    "WORLD_MODEL_OVERLAP_METRIC",
    "WorldModelOverlapMetricError",
    "world_model_overlap_jaccard_active",
]
