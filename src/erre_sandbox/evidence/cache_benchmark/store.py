"""Benchmark trace persistence — a **separate** DuckDB file / schema.

The trace is deliberately isolated from ``metrics.individuation`` (WP6 v2
Q12 observer-effect separation): a different file and the ``cache_bench``
schema, never the ``metrics`` schema. ``write_bench_rows`` mirrors
``eval_store.write_individuation_rows`` (full-run replace + in-batch
duplicate-natural-key guard) and additionally wraps the replace in a
transaction so a mid-insert failure cannot leave a run half-written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from erre_sandbox.evidence.cache_benchmark.ddl import bench_ddl_sql, row_field_names
from erre_sandbox.evidence.cache_benchmark.policy import (
    BENCH_SCHEMA_NAME,
    BENCH_TABLE_NAME,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from erre_sandbox.evidence.cache_benchmark.models import BenchResult

_NATURAL_KEY: tuple[str, ...] = ("run_id", "case_id")


def bootstrap_cache_benchmark_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create the ``cache_bench`` schema + trace table idempotently.

    *con* must be writable. All DDL is ``CREATE … IF NOT EXISTS`` so this is
    safe to call repeatedly. The qualified name is composed from
    :data:`BENCH_SCHEMA_NAME` (no ``metrics.`` literal).
    """
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {BENCH_SCHEMA_NAME}")
    con.execute(bench_ddl_sql(BENCH_SCHEMA_NAME))


def connect_cache_benchmark_db(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open a writable benchmark-trace connection and bootstrap its schema."""
    con = duckdb.connect(str(db_path))
    bootstrap_cache_benchmark_schema(con)
    return con


def write_bench_rows(
    con: duckdb.DuckDBPyConnection,
    results: Sequence[BenchResult],
) -> int:
    """Persist benchmark ``results`` into ``cache_bench.prefix_cache``.

    **Semantics — full-run replace**: every ``run_id`` present in *results*
    has its existing rows deleted before the batch is inserted, so callers
    must pass the complete case set per ``run_id``. Raises
    :class:`ValueError` if *results* contains a duplicate natural key
    ``(run_id, case_id)`` within the batch. The delete+insert runs inside a
    single transaction (rolled back on any failure) so a partial write can
    never leave a run with its old rows gone and only some new rows present.
    Returns the number of rows inserted.
    """
    if not results:
        return 0

    seen: set[tuple[str, str]] = set()
    for result in results:
        key = (result.run_id, result.case_id)
        if key in seen:
            msg = (
                "write_bench_rows: duplicate natural key in batch:"
                f" {dict(zip(_NATURAL_KEY, key, strict=True))}"
            )
            raise ValueError(msg)
        seen.add(key)

    run_ids = sorted({result.run_id for result in results})
    placeholders = ", ".join("?" for _ in run_ids)
    column_list = ", ".join(row_field_names())
    value_placeholders = ", ".join("?" for _ in row_field_names())

    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(
            f"DELETE FROM {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME}"  # noqa: S608  # identifiers are module-private constants
            f" WHERE run_id IN ({placeholders})",
            run_ids,
        )
        insert_sql = (
            f"INSERT INTO {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME}"  # noqa: S608  # identifiers are module-private constants
            f" ({column_list}) VALUES ({value_placeholders})"
        )
        for result in results:
            con.execute(insert_sql, list(result.to_row()))
    except Exception:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
    return len(results)


__all__ = [
    "bootstrap_cache_benchmark_schema",
    "connect_cache_benchmark_db",
    "write_bench_rows",
]
