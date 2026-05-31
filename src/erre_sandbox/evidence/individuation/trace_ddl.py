"""DDL + row builder for ``metrics.individual_state_trace`` (M11-C2 substrate).

Per-tick individual-state substrate captured **flag-on only** so that the
loader can recompute per-individual ``belief_variance`` (and report the
diagnostic development-stage / narrative-coherence series) without the live
``world`` loop ever importing ``memory`` (the source flows through
``CycleResult.belief_classes``; DA-M11C2-2).

Placement follows ``ddl.py``: this module owns the **column order** as the
single source of truth and never embeds a ``metrics.`` schema literal — the
qualified name is composed by the caller from the ``METRICS_SCHEMA`` constant
(CI eval-egress grep gate). The table is created **only when the individual
layer is enabled**: ``bootstrap_schema`` does not
touch it, so a flag-off run leaves the DuckDB byte-identical.

The table lives in the metrics schema (NOT ``raw_dialog``): it carries
individual-layer outputs, never the raw training-egress utterance stream, so
``ALLOWED_RAW_DIALOG_KEYS`` is untouched (DB byte ⊥ egress invariance).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import duckdb

    from erre_sandbox.contracts.cognition_layers import IndividualProfile

TABLE_NAME: Final[str] = "individual_state_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth: ``IndividualStateTraceRow.to_row``
# and ``column_names`` both derive from this. Nullable everywhere the snapshot
# field can be ``None`` (no fabrication — mirrors C1's Option B): a flag-on tick
# without a synthesised arc / advanced stage writes NULL, not a phantom value.
_INDIVIDUAL_STATE_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("development_stage", "TEXT"),
    ("coherence_score", "DOUBLE"),
    ("belief_classes_json", "TEXT"),
    ("arc_segment_count", "BIGINT NOT NULL"),
)

INDIVIDUAL_STATE_TRACE_COLUMN_COUNT: Final[int] = len(_INDIVIDUAL_STATE_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``IndividualStateTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _INDIVIDUAL_STATE_TRACE_COLUMNS)


def individual_state_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL
    is idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is
    safe to call repeatedly. ``tick >= 0`` is the only structural CHECK — trace
    rows are always real ticks (no aggregate sentinel, unlike ``individuation``).
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _INDIVIDUAL_STATE_TRACE_COLUMNS
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0)\n"
        f")"
    )


def bootstrap_individual_state_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap, DA-M11C2-1).

    Called **only** from the eval orchestrator's individual-layer-enabled branch
    — never from ``bootstrap_schema`` — so a flag-off run never issues this DDL
    and the DuckDB stays byte-identical.
    """
    con.execute(individual_state_trace_ddl_sql(schema, table))


@dataclass(frozen=True, slots=True)
class IndividualStateTraceRow:
    """One ``(run_id, individual_id, tick)`` individual-state trace row.

    Immutable; ``to_row`` emits values in ``_INDIVIDUAL_STATE_TRACE_COLUMNS``
    order so the INSERT bind stays in lockstep with the DDL.
    """

    run_id: str
    individual_id: str
    tick: int
    development_stage: str | None
    coherence_score: float | None
    belief_classes_json: str | None
    arc_segment_count: int

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.individual_id,
            self.tick,
            self.development_stage,
            self.coherence_score,
            self.belief_classes_json,
            self.arc_segment_count,
        )


def build_individual_state_trace_row(
    profile: IndividualProfile,
    belief_classes: list[str] | None,
    *,
    run_id: str,
    tick: int,
) -> IndividualStateTraceRow:
    """Project a C1 :class:`IndividualProfile` snapshot into a trace row (pure).

    None-safe throughout: ``development_state`` / ``narrative_arc`` are ``None``
    on a flag-on tick that advanced no stage / synthesised no arc, so the
    categorical / continuous fields stay NULL rather than fabricating a value
    (mirrors C1 Option B). ``arc_segment_count`` reads 0 when there is no arc
    (a count of zero observed segments, per the M11-C2 spec). *run_id* is bound
    by the orchestrator's sink closure — ``world`` never knows it (DA-M11C2-4).
    *belief_classes* comes off ``CycleResult`` so ``world`` never imports
    ``memory`` (DA-M11C2-2); ``None`` flag-off, a possibly-empty list flag-on.
    """
    dev = profile.development_state
    arc = profile.narrative_arc
    belief_classes_json = None if belief_classes is None else json.dumps(belief_classes)
    return IndividualStateTraceRow(
        run_id=run_id,
        individual_id=profile.individual_id,
        tick=tick,
        development_stage=None if dev is None else str(dev.stage),
        coherence_score=None if arc is None else arc.coherence_score,
        belief_classes_json=belief_classes_json,
        arc_segment_count=0 if arc is None else len(arc.arc_segments),
    )


__all__ = [
    "INDIVIDUAL_STATE_TRACE_COLUMN_COUNT",
    "TABLE_NAME",
    "IndividualStateTraceRow",
    "bootstrap_individual_state_trace_schema",
    "build_individual_state_trace_row",
    "column_names",
    "individual_state_trace_ddl_sql",
]
