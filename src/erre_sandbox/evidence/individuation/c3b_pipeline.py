"""M11-C3b verdict assembly pipeline (sidecar-only, GPU-free wiring).

Glues the capture artifacts of a same-base rikyu pilot into a scored verdict
**without** re-reading the DuckDB metrics table (DA-M11C3b-exec-1): for each
``(seed, condition)`` capture it computes the multi-encoder centroid panel over
the published ``.duckdb``, reads Burrows from the existing ``*.individuation.json``
sidecar (DA-M11C3b-exec-3), reads throughput primitives from the
``*.capture.json`` sidecar, **derives** the preflight verdict from that machine-
readable evidence (B-2 — never a hand-set flag), and feeds the assembled
:class:`VerdictExperiment` to the pure scorer.

The preflight derivation is the ADR §10 hard stop made executable: a run that
lacks the same-base 3-individual launcher, a complete primary-encoder panel (mpnet
+ prefix-aware e5-large), or runtime-phase elapsed instrumentation is *invalid*
(discard / re-capture), not inconclusive — closing the "e5 absent looks like a
sample shortfall" escape hatch (ADR §5.2/§7.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from erre_sandbox.evidence.capture_sidecar import (
    expected_run_id,
    read_sidecar,
    sidecar_path_for,
)
from erre_sandbox.evidence.individuation.c3b_verdict import (
    PRIMARY_ENCODER_IDS,
    ConditionRun,
    VerdictExperiment,
    score_c3b_verdict,
)
from erre_sandbox.evidence.individuation.c3b_verdict_report import (
    C3bVerdictReport,
    from_verdict_report,
)
from erre_sandbox.evidence.individuation.centroid_panel import compute_centroid_panel
from erre_sandbox.evidence.individuation.centroid_panel_report import (
    build_centroid_panel_report,
    centroid_panel_sidecar_path_for,
    write_centroid_panel_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.policy import AggregationLevel
from erre_sandbox.evidence.individuation.report import (
    individuation_sidecar_path_for,
    read_individuation_sidecar,
)
from erre_sandbox.evidence.tier_b.vendi import model_needs_e5_prefix

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    from erre_sandbox.evidence.capture_sidecar import SidecarV1
    from erre_sandbox.evidence.individuation.layer1 import EmbeddingProvider
    from erre_sandbox.evidence.individuation.models import MetricResult

_CENTROID_METRIC = "semantic_centroid_distance"
_FLOOR_METRIC = "semantic_centroid_within_floor"
_BURROWS_METRIC = "burrows_base_retention"
_COMPLETE_STATUS = "complete"
_MIN_SAME_BASE_INDIVIDUALS = 3
"""ADR §10 P-1 / §3: the same-base launcher must register >= 3 individuals."""


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Whether a capture satisfies the ADR §10 P-1 preflight (machine-derived)."""

    ok: bool
    reason: str | None = None


def _homogeneous_condition(panel_rows: Sequence[MetricResult]) -> bool | None:
    """The single ``individual_layer_enabled`` of a capture's panel rows.

    Derived from each row's ``provenance.source_individual_layer_enabled`` (loaded
    from the DuckDB ``raw_dialog.individual_layer_enabled`` column), **never** from
    a caller-passed flag (B-2). Returns ``None`` when the rows disagree (a corrupt
    mixed-condition capture) or there are no rows.
    """
    vals = {r.provenance.source_individual_layer_enabled for r in panel_rows}
    if len(vals) != 1:
        return None
    return next(iter(vals))


def derive_preflight(
    panel_rows: Sequence[MetricResult],
    capture: SidecarV1,
    *,
    used_encoder_ids: Sequence[str],
    primary_encoder_ids: Sequence[str] = PRIMARY_ENCODER_IDS,
    e5_prefix_id: str = PRIMARY_ENCODER_IDS[1],
    min_individuals: int = _MIN_SAME_BASE_INDIVIDUALS,
) -> PreflightResult:
    """Derive the ADR §10 P-1 preflight from machine-readable capture evidence.

    Each missing piece is an *invalid* protocol violation (not inconclusive):

    * same-base ``>= min_individuals`` distinct individuals (from the panel's
      per-individual floor rows, one ``base_persona_id``);
    * a homogeneous DB-derived condition;
    * both primary encoders present in the panel run, with the e5 primary being
      a prefix-aware id (``model_needs_e5_prefix``, ADR §5.1 / MED-2);
    * runtime-phase ``elapsed_seconds`` present and positive (P1a), and — for the
      flag-off throughput denominator — ``status == complete`` (§5.3).
    """
    if not panel_rows:
        return PreflightResult(ok=False, reason="panel produced no rows")

    floor_rows = [
        r
        for r in panel_rows
        if r.metric_name == _FLOOR_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    ]
    individuals = {r.individual_id for r in floor_rows}
    bases = {r.base_persona_id for r in floor_rows}
    condition = _homogeneous_condition(panel_rows)
    missing = [e for e in primary_encoder_ids if e not in set(used_encoder_ids)]
    no_elapsed = capture.elapsed_seconds is None or capture.elapsed_seconds <= 0

    # First failing check wins (kept as a table to stay within the return budget,
    # mirroring c3b_verdict._seed_invalid_reason).
    checks: list[tuple[bool, str]] = [
        (
            len(individuals) < min_individuals,
            f"only {len(individuals)} distinct individual(s); need"
            f" >= {min_individuals} same-base (launcher P-1)",
        ),
        (
            len(bases) != 1,
            f"individuals span multiple base personas {sorted(bases)}",
        ),
        (
            condition is None,
            "individual_layer condition not homogeneous across panel rows",
        ),
        (
            bool(missing),
            f"primary encoder(s) {missing} absent from panel"
            " (>= 2 primary vector encoders required, §5.1)",
        ),
        (
            not model_needs_e5_prefix(e5_prefix_id),
            f"e5 primary {e5_prefix_id!r} is not prefix-aware"
            " (model_needs_e5_prefix False)",
        ),
        (
            no_elapsed,
            "elapsed_seconds missing/non-positive (P1a instrumentation)",
        ),
        (
            condition is False and capture.status != _COMPLETE_STATUS,
            f"flag-off reference status={capture.status!r} (must be 'complete'"
            " for the throughput denominator, §5.3)",
        ),
    ]
    reason = next((r for failed, r in checks if failed), None)
    return PreflightResult(ok=reason is None, reason=reason)


def build_condition_run(
    *,
    panel_rows: Sequence[MetricResult],
    capture: SidecarV1,
    burrows_rows: Sequence[MetricResult],
    used_encoder_ids: Sequence[str],
) -> ConditionRun:
    """Assemble one :class:`ConditionRun` with a derived (never hand-set) preflight."""
    preflight = derive_preflight(panel_rows, capture, used_encoder_ids=used_encoder_ids)
    condition = _homogeneous_condition(panel_rows)
    return ConditionRun(
        seed=capture.run_idx,
        # Condition is DB-derived; if it could not be derived the run is already
        # preflight-invalid, so the placeholder never affects a scorable verdict.
        individual_layer_enabled=bool(condition) if condition is not None else False,
        preflight_ok=preflight.ok,
        capture_status=capture.status,
        focal_rows=capture.focal_observed,
        elapsed_seconds=capture.elapsed_seconds,
        panel_rows=tuple(panel_rows),
        burrows_rows=tuple(burrows_rows),
    )


def _burrows_rows(
    individuation_results: Sequence[MetricResult],
) -> tuple[MetricResult, ...]:
    return tuple(
        r
        for r in individuation_results
        if r.metric_name == _BURROWS_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    )


def run_c3b_verdict_pipeline(
    capture_paths: Sequence[Path],
    *,
    encoders: Sequence[EmbeddingProvider],
    run_id: str,
    computed_at: datetime,
    write_panel_sidecars: bool = True,
) -> C3bVerdictReport:
    """Assemble + score a C3b pilot from its capture artifacts (sidecar-only).

    For each ``.duckdb`` in *capture_paths*: compute the centroid panel with
    *encoders*, (optionally) persist a ``*.centroid_panel.json`` sidecar, read the
    sibling capture + individuation sidecars, and build a derived-preflight
    :class:`ConditionRun`. The assembled :class:`VerdictExperiment` is scored and
    converted to the durable :class:`C3bVerdictReport`. No DuckDB metrics write
    happens here, so the M10-0 ``write_individuation_rows`` hot path is untouched.
    """
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415  # cycle-safe lazy
        connect_analysis_view,
    )

    used_encoder_ids = tuple(p.embedding_model_id for p in encoders)
    runs: list[ConditionRun] = []
    for path in capture_paths:
        capture = read_sidecar(sidecar_path_for(path))
        individuation = read_individuation_sidecar(individuation_sidecar_path_for(path))
        view = connect_analysis_view(path)
        try:
            panel_rows = compute_centroid_panel(
                view, encoders=encoders, computed_at=computed_at, run_id=None
            )
        finally:
            view.close()
        if write_panel_sidecars:
            report = build_centroid_panel_report(
                expected_run_id(capture),
                panel_rows,
                used_encoder_ids,
                computed_at=computed_at,
            )
            write_centroid_panel_sidecar_atomic(
                centroid_panel_sidecar_path_for(path), report
            )
        runs.append(
            build_condition_run(
                panel_rows=panel_rows,
                capture=capture,
                burrows_rows=_burrows_rows(individuation.results),
                used_encoder_ids=used_encoder_ids,
            )
        )

    experiment = VerdictExperiment(run_id=run_id, runs=tuple(runs))
    verdict = score_c3b_verdict(experiment)
    return from_verdict_report(verdict, computed_at=computed_at)


__all__ = [
    "PreflightResult",
    "build_condition_run",
    "derive_preflight",
    "run_c3b_verdict_pipeline",
]
