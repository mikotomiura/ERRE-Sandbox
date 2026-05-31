"""DDL for the ``cache_bench.prefix_cache`` benchmark trace table.

Column order is the single source of truth here: both
:func:`row_field_names` and ``BenchResult.to_row`` derive from
:data:`_BENCH_DDL_COLUMNS`, and ``models.py`` asserts at import time that
the two agree (the same lockstep discipline as ``individuation.ddl``).

Dependency rule: imports only :mod:`.policy` (the leaf), never
:mod:`.models`. This module carries **no** ``metrics.`` literal — the
schema name is supplied by the caller from :data:`policy.BENCH_SCHEMA_NAME`
(``"cache_bench"``), so the benchmark trace never collides with the
``metrics.individuation`` egress (observer-effect separation, WP6 v2 Q12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.cache_benchmark.policy import (
    BENCH_TABLE_NAME,
    TokenCountSource,
    TtftSource,
)

if TYPE_CHECKING:
    from enum import StrEnum

# (name, SQL type) in physical column order. ``computed_at`` is a naive
# TIMESTAMP storing the **UTC** wall-clock: DuckDB's TIMESTAMPTZ→Python
# conversion hard-requires the optional ``pytz`` module (verified 2026-05-26:
# fetching a TIMESTAMPTZ raises "Required module 'pytz' failed to import"),
# and adding a dependency is forbidden here. So the model stays tz-aware (UTC),
# ``BenchResult.to_row`` normalises to naive UTC for storage, and readers
# re-attach UTC (store UTC, compare same instant — resolved
# without the dependency rather than via TIMESTAMPTZ).
_BENCH_DDL_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("schema_version", "TEXT NOT NULL"),
    ("case_id", "TEXT NOT NULL"),
    ("run_id", "TEXT NOT NULL"),
    ("prefix_hash", "TEXT NOT NULL"),
    ("system_token_count", "INTEGER NOT NULL"),
    ("user_token_count", "INTEGER NOT NULL"),
    ("token_count_source", "TEXT NOT NULL"),
    ("kv_hit_proxy", "DOUBLE NOT NULL"),
    ("ttft_p50", "DOUBLE NOT NULL"),
    ("ttft_p95", "DOUBLE NOT NULL"),
    ("ttft_source", "TEXT NOT NULL"),
    ("computed_at", "TIMESTAMP NOT NULL"),
)

BENCH_COLUMN_COUNT: Final[int] = len(_BENCH_DDL_COLUMNS)


def row_field_names() -> tuple[str, ...]:
    """Ordered column names — the order ``BenchResult.to_row`` must emit."""
    return tuple(name for name, _ in _BENCH_DDL_COLUMNS)


def _sql_literal_set(enum_cls: type[StrEnum]) -> str:
    """Render an enum's members as a sorted SQL ``IN`` value list."""
    members = sorted(str(v) for v in enum_cls)
    return ", ".join(f"'{m}'" for m in members)


def bench_ddl_sql(schema: str, table: str = BENCH_TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (``store`` passes
    :data:`policy.BENCH_SCHEMA_NAME`); this module never embeds a schema-dot
    literal. Table-level invariants (defence-in-depth with the pydantic
    validators):

    * ``kv_hit_proxy`` ∈ ``[0, 1]`` (the proxy is a fraction),
    * ``ttft_p95 >= ttft_p50`` and both ``>= 0`` (a TTFT is a non-negative
      duration),
    * token counts ``>= 0``,
    * ``token_count_source`` / ``ttft_source`` ∈ their enums,
    * ``UNIQUE (run_id, case_id)`` — the natural key, enforced at the DB and
      not only in the writer.
    """
    cols = ",\n  ".join(f"{name} {sqltype}" for name, sqltype in _BENCH_DDL_COLUMNS)
    token_src_in = _sql_literal_set(TokenCountSource)
    ttft_src_in = _sql_literal_set(TtftSource)
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (kv_hit_proxy >= 0.0 AND kv_hit_proxy <= 1.0),\n"
        f"  CHECK (ttft_p50 >= 0.0 AND ttft_p95 >= 0.0),\n"
        f"  CHECK (ttft_p95 >= ttft_p50),\n"
        f"  CHECK (system_token_count >= 0 AND user_token_count >= 0),\n"
        f"  CHECK (token_count_source IN ({token_src_in})),\n"
        f"  CHECK (ttft_source IN ({ttft_src_in})),\n"
        f"  UNIQUE (run_id, case_id)\n"
        f")"
    )


__all__ = [
    "BENCH_COLUMN_COUNT",
    "bench_ddl_sql",
    "row_field_names",
]
