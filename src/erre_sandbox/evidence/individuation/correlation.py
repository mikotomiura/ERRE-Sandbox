"""Cross-metric correlation for M10-0 individuation.

Computes the **Pearson correlation matrix between Layer 1 active metrics** to
surface *double measurement* — pairs whose ``|r|`` is high enough that the two
metrics are likely reading the same underlying signal through non-independent
channels (canonical §C.9 / acceptance A10). A pair with ``|r| >=``
:data:`DOUBLE_MEASUREMENT_THRESHOLD` is flagged.

What this is **not** (continuation-bias guard, design §0 / §11.4): the
correlation is a *descriptive* check on channel independence, **not** an
optimisation target. It does not (and must not) be used to select prompt
variants that jointly move Vendi and Burrows. The threshold is a
data-quality / validity signal only.

Scope (canonical §C.9): **Layer 1 × Layer 1, per_individual only**, aligned on
the ``(run_id, individual_id)`` observation unit. The per_dyad (centroid) and
population (Vendi) metrics carry a single metric each and a different
observation unit, so they cannot be correlated against the per_individual set
here; when present and valid they are recorded as
``ExcludedMetric(reason="wrong_observation_unit")`` rather than silently
dropped. **Layer 1 × Layer 2 / Layer 2 × Layer 2 cross-correlation is deferred
to M11-C** — at M10-0 the Layer 2 metrics are unsupported pins and never enter
the matrix (a behaviour pin test asserts their absence).

Honest degradation (no fabrication): the real M10-0 golden produces a valid
per_individual value only for ``zone_behavior_consistency`` (burrows is ja /
unsupported, the behavioural rate channels are degenerate, belief is
unsupported), so fewer than two metric columns clear the observation floor and
the report returns ``correlation_status="insufficient"``. That is the **normal**
outcome for the real golden, not a failure. A non-valid cell is treated as a
missing observation (``NaN``); it is never imputed with 0 or a column mean.

The status vocabulary is deliberately disjoint from
:class:`~.policy.MetricStatus` (valid / degenerate / unsupported): a
correlation outcome is a cross-metric aggregate, not a single extraction, so it
uses :class:`CorrelationStatus` (computed / insufficient) and the field is named
``correlation_status`` to keep the two from being confused.

This module imports only :mod:`.policy` (the leaf), the
:class:`~.report.IndividuationReport` type (for annotations), and ``numpy`` —
it never imports ``models`` / ``ddl`` / ``eval_store`` / ``loader`` at load
time, keeping the contamination surface tiny and the import graph acyclic. The
correlation result is an **independent sidecar artifact**; it is never written
into a :class:`~.models.MetricResult` or the ``metrics.individuation`` table
(it is not a metric in :data:`~.policy.METRIC_SPECS`, so the model validator
would reject it anyway).
"""

from __future__ import annotations

import json
import math
from datetime import datetime  # noqa: TC003  # runtime use in a pydantic field
from enum import StrEnum
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import numpy as np
from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.individuation.policy import (
    METRIC_SPECS,
    AggregationLevel,
    MetricStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.individuation.report import IndividuationReport

CORRELATION_SCHEMA_VERSION: Final[str] = "m10-0.corr.1"
"""Pinned schema version stamped into every :class:`CorrelationReport`."""

DOUBLE_MEASUREMENT_THRESHOLD: Final[float] = 0.85
"""``|r|`` at or above which a metric pair is flagged double-measurement (A10)."""

MIN_CORRELATION_OBSERVATIONS: Final[int] = 3
"""Minimum *pairwise-complete* observations for a pair's ``r`` to be computed.

Pearson ``r`` over n=2 points is always ``±1`` by construction, so a 2-point
pair would spuriously trip the double-measurement flag; require ``>= 3``.
"""

CORRELATION_SIDECAR_SUFFIX: Final[str] = ".individuation.correlation.json"
"""Suffix for the standalone correlation sidecar (sibling of the ``.duckdb``)."""

_CORRELATION_METHOD: Final[str] = "pearson-numpy"
_OBSERVATION_UNIT: Final[str] = "(run_id, individual_id)"
_MIN_METRICS_FOR_MATRIX: Final[int] = 2
_ZERO_VARIANCE_ATOL: Final[float] = 1e-12


class CorrelationStatus(StrEnum):
    """Outcome of a correlation pass (disjoint from :class:`.policy.MetricStatus`)."""

    COMPUTED = "computed"
    INSUFFICIENT = "insufficient"


class CorrelationPair(BaseModel):
    """One off-diagonal cell of the Layer 1 correlation matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_a: str  # normalised so metric_a < metric_b (upper triangle)
    metric_b: str
    r: float  # finite Pearson r in [-1, 1]
    abs_r: float
    n_observations: int  # pairwise-complete observation count
    is_double_measurement: bool  # abs_r >= threshold
    channel_a: str  # descriptive: double-measurement == channel non-independence
    channel_b: str


class ExcludedMetric(BaseModel):
    """A metric kept out of the matrix, with the reason recorded (not silent)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str
    reason: str  # wrong_observation_unit | no_valid_values | too_few_observations
    #               | constant_column


class CorrelationReport(BaseModel):
    """Cross-metric correlation summary serialised to its own sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    computed_at: datetime
    method: str
    correlation_status: CorrelationStatus
    insufficient_reason: str | None
    observation_unit: str
    threshold: float
    min_observations: int
    run_ids: tuple[str, ...]
    metrics_in_matrix: tuple[str, ...]
    excluded_metrics: tuple[ExcludedMetric, ...]
    n_observation_units: int
    pairs: tuple[CorrelationPair, ...]
    double_measurement_warnings: tuple[CorrelationPair, ...]

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict (enums -> values, datetime -> ISO)."""
        return self.model_dump(mode="json")


def _candidate_metrics() -> tuple[str, ...]:
    """per_individual metric names that can be ``valid`` (derived from METRIC_SPECS).

    Recovery and the cite_belief pins are per_individual but never ``valid``, so
    they fall out naturally — the universe is not hard-coded. ``diagnostic_only``
    metrics (M10-A S2 narrative / development) are valid-capable per_individual but
    are **excluded** here so the descriptive Layer 1 channel-independence claim
    (canonical §C.9) is not silently widened to the M11 diagnostic layers
    (DA-S2-4 / Codex CX5); their inclusion is deferred to the S3 conformance ADR.
    """
    return tuple(
        sorted(
            name
            for name, spec in METRIC_SPECS.items()
            if AggregationLevel.PER_INDIVIDUAL in spec.allowed_aggregation_levels
            and MetricStatus.VALID in spec.allowed_statuses
            and not spec.diagnostic_only
        )
    )


def _diagnostic_only_excluded(
    reports: Sequence[IndividuationReport],
) -> tuple[ExcludedMetric, ...]:
    """``diagnostic_only`` metrics seen ``valid`` per_individual, as excluded rows.

    Codex CX5: a valid diagnostic metric is excluded from the matrix by
    :func:`_candidate_metrics`, but it must not *silently* vanish — the report
    lists it with reason ``"diagnostic_only"`` so a reader comparing the
    individuation table (which has the rows) to the correlation report sees an
    explicit policy exclusion, not an unexplained absence.
    """
    present: set[str] = set()
    for report in reports:
        for res in report.results:
            spec = METRIC_SPECS.get(res.metric_name)
            if (
                spec is not None
                and spec.diagnostic_only
                and res.status is MetricStatus.VALID
                and res.aggregation_level is AggregationLevel.PER_INDIVIDUAL
            ):
                present.add(res.metric_name)
    return tuple(
        ExcludedMetric(metric_name=name, reason="diagnostic_only")
        for name in sorted(present)
    )


def _pairwise_pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson ``r`` over two aligned 1-D arrays, or ``None`` if undefined.

    ``None`` for a constant column (zero variance) — ``r`` is 0/0 there. The
    result is clipped to ``[-1, 1]`` to absorb floating-point overshoot.
    """
    a_centered = a - a.mean()
    b_centered = b - b.mean()
    denom = math.sqrt(float(a_centered @ a_centered) * float(b_centered @ b_centered))
    if math.isclose(denom, 0.0, abs_tol=_ZERO_VARIANCE_ATOL):
        return None
    r = float(a_centered @ b_centered) / denom
    r = max(-1.0, min(1.0, r))
    return r if math.isfinite(r) else None


def _insufficient_report(
    *,
    computed_at: datetime,
    threshold: float,
    min_observations: int,
    run_ids: tuple[str, ...],
    excluded_metrics: tuple[ExcludedMetric, ...],
    n_observation_units: int,
    reason: str,
) -> CorrelationReport:
    return CorrelationReport(
        schema_version=CORRELATION_SCHEMA_VERSION,
        computed_at=computed_at,
        method=_CORRELATION_METHOD,
        correlation_status=CorrelationStatus.INSUFFICIENT,
        insufficient_reason=reason,
        observation_unit=_OBSERVATION_UNIT,
        threshold=threshold,
        min_observations=min_observations,
        run_ids=run_ids,
        metrics_in_matrix=(),
        excluded_metrics=excluded_metrics,
        n_observation_units=n_observation_units,
        pairs=(),
        double_measurement_warnings=(),
    )


def _collect_cells(
    reports: Sequence[IndividuationReport],
    candidate_names: frozenset[str],
) -> tuple[dict[tuple[str, str], dict[str, float]], dict[str, str], set[str]]:
    """Scan every result into per-unit valid cells + the wrong-scope metric set.

    per_individual valid -> a cell keyed by ``(run_id, individual_id)``; a valid
    result at another scope (centroid / vendi) -> ``wrong_scope``; everything
    else is left as a missing observation.

    Raises:
        ValueError: The same ``(unit, metric)`` carries two different valid
            values (would require a silent average).
    """
    cells: dict[tuple[str, str], dict[str, float]] = {}
    metric_channel: dict[str, str] = {}
    wrong_scope: set[str] = set()
    for report in reports:
        for res in report.results:
            if res.status is not MetricStatus.VALID:
                continue
            if (
                res.aggregation_level is AggregationLevel.PER_INDIVIDUAL
                and res.metric_name in candidate_names
            ):
                unit = (res.run_id, res.individual_id)
                row = cells.setdefault(unit, {})
                # A VALID MetricResult always carries a finite float (enforced by
                # the model validator); narrow float | None for mypy.
                value = float(cast("float", res.value))
                if res.metric_name in row and not math.isclose(
                    row[res.metric_name], value
                ):
                    msg = (
                        f"conflicting valid values for {res.metric_name!r} at"
                        f" observation unit {unit!r}: {row[res.metric_name]} vs {value}"
                    )
                    raise ValueError(msg)
                row[res.metric_name] = value
                metric_channel[res.metric_name] = res.channel.value
            elif res.aggregation_level is not AggregationLevel.PER_INDIVIDUAL:
                wrong_scope.add(res.metric_name)
    return cells, metric_channel, wrong_scope


def _materialise_matrix(
    cells: dict[tuple[str, str], dict[str, float]],
    units: list[tuple[str, str]],
    candidate_index: dict[str, int],
    n_candidates: int,
) -> np.ndarray:
    """``(n_units, n_candidates)`` matrix; absent (unit, metric) cells are NaN."""
    unit_index = {unit: i for i, unit in enumerate(units)}
    matrix = np.full((len(units), n_candidates), np.nan, dtype=float)
    for unit, row in cells.items():
        i = unit_index[unit]
        for name, value in row.items():
            matrix[i, candidate_index[name]] = value
    return matrix


def _filter_columns(
    matrix: np.ndarray,
    candidates: tuple[str, ...],
    candidate_index: dict[str, int],
    *,
    min_observations: int,
    wrong_scope: set[str],
) -> tuple[list[tuple[str, int]], tuple[ExcludedMetric, ...]]:
    """Split candidate columns into kept ``(name, col)`` and excluded-with-reason."""
    excluded: list[ExcludedMetric] = [
        ExcludedMetric(metric_name=name, reason="wrong_observation_unit")
        for name in wrong_scope
    ]
    kept: list[tuple[str, int]] = []
    for name in candidates:
        col = matrix[:, candidate_index[name]]
        valid = col[~np.isnan(col)]
        if valid.size == 0:
            excluded.append(ExcludedMetric(metric_name=name, reason="no_valid_values"))
        elif valid.size < min_observations:
            excluded.append(
                ExcludedMetric(metric_name=name, reason="too_few_observations")
            )
        elif math.isclose(float(valid.std()), 0.0, abs_tol=_ZERO_VARIANCE_ATOL):
            excluded.append(ExcludedMetric(metric_name=name, reason="constant_column"))
        else:
            kept.append((name, candidate_index[name]))
    excluded_sorted = tuple(sorted(excluded, key=lambda e: (e.metric_name, e.reason)))
    return kept, excluded_sorted


def _compute_pairs(
    matrix: np.ndarray,
    kept: list[tuple[str, int]],
    metric_channel: dict[str, str],
    *,
    threshold: float,
    min_observations: int,
) -> list[CorrelationPair]:
    """Upper-triangle pairwise-complete Pearson pairs (kept is in name order)."""
    pairs: list[CorrelationPair] = []
    for (name_a, col_a), (name_b, col_b) in combinations(kept, 2):
        vec_a = matrix[:, col_a]
        vec_b = matrix[:, col_b]
        mask = ~np.isnan(vec_a) & ~np.isnan(vec_b)
        n = int(mask.sum())
        if n < min_observations:
            continue
        r = _pairwise_pearson(vec_a[mask], vec_b[mask])
        if r is None:
            continue
        abs_r = abs(r)
        pairs.append(
            CorrelationPair(
                metric_a=name_a,  # kept is in sorted-name order -> a < b
                metric_b=name_b,
                r=r,
                abs_r=abs_r,
                n_observations=n,
                is_double_measurement=abs_r >= threshold,
                channel_a=metric_channel[name_a],
                channel_b=metric_channel[name_b],
            )
        )
    return pairs


def correlate_individuation(
    reports: Sequence[IndividuationReport],
    *,
    computed_at: datetime,
    threshold: float = DOUBLE_MEASUREMENT_THRESHOLD,
    min_observations: int = MIN_CORRELATION_OBSERVATIONS,
) -> CorrelationReport:
    """Correlate Layer 1 per_individual metrics across the given run reports.

    The observation unit is ``(run_id, individual_id)``; a non-valid metric is a
    missing observation (never imputed). When fewer than two metric columns
    clear the observation/variance floor the report degrades to
    ``correlation_status="insufficient"`` rather than fabricating a value — the
    expected outcome on the real M10-0 golden.

    Args:
        reports: Per-run individuation reports (``IndividuationReport``) whose
            ``results`` are scanned for valid per_individual metric rows.
        computed_at: Timezone-aware stamp for the report.
        threshold: ``|r|`` flag cut-off (default :data:`DOUBLE_MEASUREMENT_THRESHOLD`).
        min_observations: Minimum pairwise-complete observations per pair
            (default :data:`MIN_CORRELATION_OBSERVATIONS`).

    Raises:
        ValueError: The same ``(run_id, individual_id, metric_name)`` carries two
            different valid values (would require a silent average).
    """
    candidates = _candidate_metrics()
    candidate_index = {name: j for j, name in enumerate(candidates)}
    run_ids = tuple(sorted({report.run_id for report in reports}))

    cells, metric_channel, wrong_scope = _collect_cells(reports, frozenset(candidates))
    units = sorted(cells)
    n_units = len(units)
    matrix = _materialise_matrix(cells, units, candidate_index, len(candidates))

    kept, filtered_excluded = _filter_columns(
        matrix,
        candidates,
        candidate_index,
        min_observations=min_observations,
        wrong_scope=wrong_scope,
    )
    # Codex CX5: surface diagnostic_only metrics seen valid as explicit exclusions
    # (they never enter candidates, so _filter_columns cannot list them).
    excluded_sorted = tuple(
        sorted(
            [*filtered_excluded, *_diagnostic_only_excluded(reports)],
            key=lambda e: (e.metric_name, e.reason),
        )
    )
    if len(kept) < _MIN_METRICS_FOR_MATRIX:
        return _insufficient_report(
            computed_at=computed_at,
            threshold=threshold,
            min_observations=min_observations,
            run_ids=run_ids,
            excluded_metrics=excluded_sorted,
            n_observation_units=n_units,
            reason=(
                "fewer than 2 metrics have sufficient non-constant valid"
                " observations on the per_individual observation unit"
            ),
        )

    pairs = _compute_pairs(
        matrix,
        kept,
        metric_channel,
        threshold=threshold,
        min_observations=min_observations,
    )
    if not pairs:
        return _insufficient_report(
            computed_at=computed_at,
            threshold=threshold,
            min_observations=min_observations,
            run_ids=run_ids,
            excluded_metrics=excluded_sorted,
            n_observation_units=n_units,
            reason="no metric pair reached min_observations pairwise-complete",
        )

    metrics_in_matrix = tuple(
        sorted({m for pair in pairs for m in (pair.metric_a, pair.metric_b)})
    )
    warnings = tuple(pair for pair in pairs if pair.is_double_measurement)
    return CorrelationReport(
        schema_version=CORRELATION_SCHEMA_VERSION,
        computed_at=computed_at,
        method=_CORRELATION_METHOD,
        correlation_status=CorrelationStatus.COMPUTED,
        insufficient_reason=None,
        observation_unit=_OBSERVATION_UNIT,
        threshold=threshold,
        min_observations=min_observations,
        run_ids=run_ids,
        metrics_in_matrix=metrics_in_matrix,
        excluded_metrics=excluded_sorted,
        n_observation_units=n_units,
        pairs=tuple(pairs),
        double_measurement_warnings=warnings,
    )


def correlation_sidecar_path_for(duckdb_path: Path | str) -> Path:
    """Return the ``<duckdb>.individuation.correlation.json`` sibling path."""
    p = Path(duckdb_path)
    return p.with_name(p.name + CORRELATION_SIDECAR_SUFFIX)


def write_correlation_sidecar_atomic(
    path: Path | str, report: CorrelationReport
) -> None:
    """Atomically write the correlation sidecar JSON.

    Mirrors :func:`~.report.write_individuation_sidecar_atomic`: the heavy
    ``eval_store`` import is deferred so this module's load stays free of it
    (the sidecar is a plain JSON file and never touches the metrics schema).
    """
    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(
            report.to_sidecar_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ),
        encoding="utf-8",
    )
    atomic_temp_rename(tmp, path)


__all__ = [
    "CORRELATION_SCHEMA_VERSION",
    "CORRELATION_SIDECAR_SUFFIX",
    "DOUBLE_MEASUREMENT_THRESHOLD",
    "MIN_CORRELATION_OBSERVATIONS",
    "CorrelationPair",
    "CorrelationReport",
    "CorrelationStatus",
    "ExcludedMetric",
    "correlate_individuation",
    "correlation_sidecar_path_for",
    "write_correlation_sidecar_atomic",
]
