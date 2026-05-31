"""DDL + schema-isolation tests for the WP6 cache benchmark trace table.

Asserts the bootstrap/row-field lockstep, the DB-level CHECK + UNIQUE
constraints (defence-in-depth with the pydantic validators), and that the
package carries no quoted ``metrics.`` egress literal (the schema is the
isolated ``cache_bench``, never ``metrics``).
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.evidence.cache_benchmark.ddl import (
    bench_ddl_sql,
    row_field_names,
)
from erre_sandbox.evidence.cache_benchmark.policy import (
    BENCH_SCHEMA_NAME,
    BENCH_TABLE_NAME,
)
from erre_sandbox.evidence.cache_benchmark.store import (
    bootstrap_cache_benchmark_schema,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[2] / (
    "src/erre_sandbox/evidence/cache_benchmark"
)
_CLI_FILE = (
    Path(__file__).resolve().parents[2] / "src/erre_sandbox/cli/cache_benchmark.py"
)
# The CI eval-egress grep gate forbids a *quoted* schema-dot literal; backtick
# prose like ``metrics.individuation`` in a docstring is allowed (DA-M10I-22 #5).
_QUOTED_METRICS_LITERAL = re.compile(r"""["']metrics\.""")


def test_bootstrap_creates_table_with_lockstep_columns() -> None:
    con = duckdb.connect(":memory:")
    try:
        bootstrap_cache_benchmark_schema(con)
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ?"
            " ORDER BY ordinal_position",
            [BENCH_SCHEMA_NAME, BENCH_TABLE_NAME],
        ).fetchall()
    finally:
        con.close()
    created = tuple(r[0] for r in rows)
    assert created == row_field_names()


def test_bootstrap_is_idempotent() -> None:
    con = duckdb.connect(":memory:")
    try:
        bootstrap_cache_benchmark_schema(con)
        bootstrap_cache_benchmark_schema(con)  # must not raise
    finally:
        con.close()


def test_ddl_sql_has_no_quoted_metrics_literal() -> None:
    sql = bench_ddl_sql(BENCH_SCHEMA_NAME)
    assert not _QUOTED_METRICS_LITERAL.search(sql)
    assert "cache_bench" in sql


def test_ddl_has_check_and_unique_clauses() -> None:
    sql = bench_ddl_sql(BENCH_SCHEMA_NAME)
    assert "CHECK (kv_hit_proxy" in sql
    assert "CHECK (ttft_p50 >= 0.0 AND ttft_p95 >= 0.0)" in sql
    assert "CHECK (ttft_p95 >= ttft_p50)" in sql
    assert "UNIQUE (run_id, case_id)" in sql


def _insert_minimal(con: duckdb.DuckDBPyConnection, **overrides: object) -> None:
    row: dict[str, object] = {
        "schema_version": "cache-bench-m10-0.1",
        "case_id": "kant",
        "run_id": "baseline",
        "prefix_hash": "0" * 64,
        "system_token_count": 100,
        "user_token_count": 50,
        "token_count_source": "proxy_whitespace_re",
        "kv_hit_proxy": 0.3,
        "ttft_p50": 12.0,
        "ttft_p95": 19.0,
        "ttft_source": "synthetic",
        "computed_at": "2026-05-26 12:00:00",
    }
    row.update(overrides)
    cols = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    con.execute(
        f"INSERT INTO {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME} ({cols})"  # noqa: S608
        f" VALUES ({placeholders})",
        list(row.values()),
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"kv_hit_proxy": 2.0},
        {"ttft_p50": -1.0},
        {"ttft_p95": 5.0, "ttft_p50": 10.0},
        {"system_token_count": -1},
        {"token_count_source": "bogus"},
        {"ttft_source": "bogus"},
    ],
)
def test_db_check_rejects_bad_rows(overrides: dict[str, object]) -> None:
    con = duckdb.connect(":memory:")
    try:
        bootstrap_cache_benchmark_schema(con)
        with pytest.raises(duckdb.ConstraintException):
            _insert_minimal(con, **overrides)
    finally:
        con.close()


def test_db_unique_rejects_duplicate_natural_key() -> None:
    con = duckdb.connect(":memory:")
    try:
        bootstrap_cache_benchmark_schema(con)
        _insert_minimal(con)
        with pytest.raises(duckdb.ConstraintException):
            _insert_minimal(con)  # same (run_id, case_id)
    finally:
        con.close()


def test_package_has_no_quoted_metrics_literal() -> None:
    # Codex LOW CL2: catch a quoted egress literal copy-pasted anywhere in the
    # package or its CLI, not only in the DDL string.
    files = [*_PACKAGE_DIR.glob("*.py"), _CLI_FILE]
    offenders = [
        f.name for f in files if _QUOTED_METRICS_LITERAL.search(f.read_text("utf-8"))
    ]
    assert offenders == []
