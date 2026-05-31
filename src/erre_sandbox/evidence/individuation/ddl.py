"""DDL for ``metrics.individuation`` (column-order single source of truth).

This module owns the **column order** for the table and the
``MetricResult`` row tuple: both ``row_field_names`` and
``MetricResult.to_row`` derive from :data:`_INDIVIDUATION_DDL_COLUMNS`, so
the two can never drift. ``eval_store.bootstrap_schema`` builds the table
from :func:`individuation_ddl_sql` and asserts at import time that the
created column set equals :func:`row_field_names` output.

Dependency rule: imports only :mod:`.policy` (the leaf), never
:mod:`.models` — keeping the package import graph acyclic.

This module contains **no** ``metrics.`` literal: :func:`individuation_ddl_sql`
takes the schema name as an argument so the qualified name is composed by
``eval_store`` from the ``METRICS_SCHEMA`` constant (CI eval-egress grep gate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricStatus,
)

if TYPE_CHECKING:
    from enum import StrEnum

TABLE_NAME: Final[str] = "individuation"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth. (name, SQL type) in physical
# order; row_field_names() and MetricResult.to_row() both derive from this.
_INDIVIDUATION_DDL_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("base_persona_id", "TEXT NOT NULL"),
    ("aggregation_level", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("metric_name", "TEXT NOT NULL"),
    ("channel", "TEXT NOT NULL"),
    ("status", "TEXT NOT NULL"),
    ("value", "DOUBLE"),
    ("reason", "TEXT"),
    ("metric_schema_version", "TEXT NOT NULL"),
    ("source_table", "TEXT NOT NULL"),
    ("source_run_id", "TEXT NOT NULL"),
    ("source_epoch_phase", "TEXT NOT NULL"),
    ("source_individual_layer_enabled", "BOOLEAN NOT NULL"),
    ("source_filter_hash", "TEXT NOT NULL"),
    ("embedding_model_id", "TEXT"),
    ("computed_at", "TIMESTAMP NOT NULL"),
)

INDIVIDUATION_COLUMN_COUNT: Final[int] = len(_INDIVIDUATION_DDL_COLUMNS)


def row_field_names() -> tuple[str, ...]:
    """Ordered column names — the order ``MetricResult.to_row`` must emit.

    Also the set the ``bootstrap_schema`` lockstep check compares the
    created table's columns against.
    """
    return tuple(name for name, _ in _INDIVIDUATION_DDL_COLUMNS)


def _sql_literal_set(enum_cls: type[StrEnum]) -> str:
    """Render an enum's members as a sorted SQL ``IN`` value list."""
    members = sorted(str(v) for v in enum_cls)
    return ", ".join(f"'{m}'" for m in members)


def individuation_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (``eval_store`` passes
    ``METRICS_SCHEMA``); this module never embeds a ``metrics.`` literal.
    The three table-level CHECKs encode the generic structural invariants
    (per-metric status policy stays model-level):

    * ``status`` ∈ the :class:`MetricStatus` enum,
    * ``aggregation_level`` ∈ the :class:`AggregationLevel` enum,
    * the value/reason ↔ status coupling,
    * ``tick >= -1`` (the aggregate sentinel floor).
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _INDIVIDUATION_DDL_COLUMNS
    )
    status_in = _sql_literal_set(MetricStatus)
    agg_in = _sql_literal_set(AggregationLevel)
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (status IN ({status_in})),\n"
        f"  CHECK (aggregation_level IN ({agg_in})),\n"
        f"  CHECK ((status = 'valid' AND value IS NOT NULL AND reason IS NULL)"
        f" OR (status <> 'valid' AND value IS NULL AND reason IS NOT NULL)),\n"
        f"  CHECK (tick >= -1)\n"
        f")"
    )


__all__ = [
    "INDIVIDUATION_COLUMN_COUNT",
    "TABLE_NAME",
    "individuation_ddl_sql",
    "row_field_names",
]
