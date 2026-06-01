"""M10-A S3.5 path(a) gate assembly (sidecar-only, GPU-free wiring).

Glues a same-base run's captured metrics into a :class:`PathARunInput` **without**
re-reading the DuckDB metrics table for the gate decision: it computes the
individuation rows via :func:`compute_individuation` (runner, editable layer) and
the final-tick belief / SWM substrate via :func:`load_individual_state_windows`
(loader, editable layer), then projects them into the scorer's identity-checked
input contract (CX-MED-2). It imports none of the frozen judgment path
(``c3b_verdict`` / ``centroid_panel`` / ``layer1`` / ``c3b_pipeline``), so the
frozen §9 sentinel stays ``exit=0``.

This is the wiring S4's GPU smoke (one cell) and S5's real N=3 run drive the gate
through; at S3.5 it is exercised on synthetic DuckDB fixtures (CPU, stub embedding
provider) — the scorer logic itself is unit-tested on hand-built dataclasses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.path_a_gate import (
    IndividualSubstrate,
    PathAExperiment,
    PathARunInput,
)
from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
)
from erre_sandbox.evidence.individuation.runner import compute_individuation

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from erre_sandbox.evidence.eval_store import AnalysisView
    from erre_sandbox.evidence.individuation.loader import IndividualStateWindow
    from erre_sandbox.evidence.individuation.models import MetricResult
    from erre_sandbox.evidence.individuation.runner import IndividuationContext

_BELIEF_VARIANCE_METRIC = "belief_variance"
_JACCARD_METRIC = "world_model_overlap_jaccard"


class PathAAssemblyError(RuntimeError):
    """Raised when a run cannot be projected into a :class:`PathARunInput`.

    The load-bearing case is a run whose per-individual ``belief_variance`` rows
    span more than one ``base_persona_id`` (not a same-base path(a) pilot): the
    ``base_persona_id`` needed for the null-control ``derive_seed`` is ambiguous, so
    we fail loud rather than pick one arbitrarily. A wrong *count* of individuals is
    left to the scorer's identity gate (→ INVALID), keeping the assembly thin.
    """


def assemble_path_a_run_from_view(
    view: AnalysisView,
    *,
    run_id: str,
    run_idx: int,
    ctx: IndividuationContext,
) -> PathARunInput:
    """Project one run's individuation rows + trace substrate into a seed input."""
    results = compute_individuation(view, run_id=run_id, ctx=ctx)
    trace_windows = load_state_windows(view, run_id=run_id)
    return _build_run_input(
        run_id=run_id,
        run_idx=run_idx,
        results=results,
        trace_windows=trace_windows,
    )


def assemble_path_a_run(
    path: Path | str,
    *,
    run_id: str,
    run_idx: int,
    ctx: IndividuationContext,
) -> PathARunInput:
    """Open a published ``.duckdb`` and assemble one seed's :class:`PathARunInput`."""
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415  # cycle-safe lazy
        connect_analysis_view,
    )

    view = connect_analysis_view(path)
    try:
        return assemble_path_a_run_from_view(
            view, run_id=run_id, run_idx=run_idx, ctx=ctx
        )
    finally:
        view.close()


def assemble_path_a_experiment(
    captures: Sequence[tuple[Path | str, str, int]],
    *,
    experiment_run_id: str,
    ctx: IndividuationContext,
) -> PathAExperiment:
    """Assemble the N=3 :class:`PathAExperiment` from ``(path, run_id, run_idx)``.

    The scorer (:func:`score_path_a_gate`) validates the seed matrix (exactly
    ``(0, 1, 2)``) and per-seed identity, so this stays a thin projector.
    """
    runs = tuple(
        assemble_path_a_run(path, run_id=run_id, run_idx=run_idx, ctx=ctx)
        for path, run_id, run_idx in captures
    )
    return PathAExperiment(run_id=experiment_run_id, runs=runs)


def load_state_windows(
    view: AnalysisView, *, run_id: str
) -> dict[tuple[str, str], IndividualStateWindow]:
    """Final-tick belief / SWM substrate per ``(run_id, individual_id)`` (loader)."""
    from erre_sandbox.evidence.individuation.loader import (  # noqa: PLC0415
        load_individual_state_windows,
    )

    return load_individual_state_windows(view, run_id=run_id)


def _build_run_input(
    *,
    run_id: str,
    run_idx: int,
    results: Sequence[MetricResult],
    trace_windows: dict[tuple[str, str], IndividualStateWindow],
) -> PathARunInput:
    belief_variance_rows = tuple(
        r
        for r in results
        if r.metric_name == _BELIEF_VARIANCE_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    )
    jaccard_rows = tuple(
        r
        for r in results
        if r.metric_name == _JACCARD_METRIC
        and r.aggregation_level is AggregationLevel.PER_DYAD
    )
    bases = {r.base_persona_id for r in belief_variance_rows}
    if len(bases) > 1:
        msg = (
            f"run {run_id!r} per-individual belief_variance rows span multiple base"
            f" personas {sorted(bases)}; path(a) is a same-base pilot"
        )
        raise PathAAssemblyError(msg)
    base_persona_id = next(iter(bases)) if bases else run_id
    individuals = tuple(
        IndividualSubstrate(
            individual_id=r.individual_id,
            belief_classes=(
                trace_windows[(run_id, r.individual_id)].belief_classes
                if (run_id, r.individual_id) in trace_windows
                else None
            ),
            world_model_keys=(
                trace_windows[(run_id, r.individual_id)].world_model_keys
                if (run_id, r.individual_id) in trace_windows
                else None
            ),
        )
        for r in sorted(belief_variance_rows, key=lambda r: r.individual_id)
    )
    return PathARunInput(
        run_idx=run_idx,
        run_id=run_id,
        base_persona_id=base_persona_id,
        individuals=individuals,
        belief_variance_rows=belief_variance_rows,
        jaccard_rows=jaccard_rows,
    )


__all__ = [
    "PathAAssemblyError",
    "assemble_path_a_experiment",
    "assemble_path_a_run",
    "assemble_path_a_run_from_view",
    "load_state_windows",
]
