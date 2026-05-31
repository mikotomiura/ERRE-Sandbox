"""Trace persistence for the WP6 cache benchmark.

Round-trip (incl tz-aware ``computed_at``), full-run-replace idempotency,
and the in-batch duplicate-natural-key guard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.evidence.cache_benchmark.models import BenchResult
from erre_sandbox.evidence.cache_benchmark.policy import (
    BENCH_SCHEMA_NAME,
    BENCH_TABLE_NAME,
    CACHE_BENCHMARK_SCHEMA_VERSION,
    TokenCountSource,
    TtftSource,
)
from erre_sandbox.evidence.cache_benchmark.store import (
    connect_cache_benchmark_db,
    write_bench_rows,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 5, 26, 12, 30, 45, tzinfo=UTC)


def _result(case_id: str = "kant", *, run_id: str = "baseline") -> BenchResult:
    return BenchResult(
        schema_version=CACHE_BENCHMARK_SCHEMA_VERSION,
        case_id=case_id,
        run_id=run_id,
        prefix_hash="0" * 64,
        system_token_count=100,
        user_token_count=50,
        token_count_source=TokenCountSource.PROXY_WHITESPACE_RE,
        kv_hit_proxy=0.3,
        ttft_p50=12.0,
        ttft_p95=19.0,
        ttft_source=TtftSource.SYNTHETIC,
        computed_at=_NOW,
    )


def _row_count(con: object) -> int:
    return con.execute(  # type: ignore[attr-defined]
        f"SELECT count(*) FROM {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME}"  # noqa: S608
    ).fetchone()[0]


def test_round_trip_preserves_fields_and_tz(tmp_path: Path) -> None:
    con = connect_cache_benchmark_db(tmp_path / "bench.duckdb")
    try:
        assert write_bench_rows(con, [_result()]) == 1
        row = con.execute(
            "SELECT case_id, kv_hit_proxy, ttft_p50, ttft_p95, ttft_source,"  # noqa: S608  # identifiers are module constants
            f" computed_at FROM {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME}"
        ).fetchone()
    finally:
        con.close()
    assert row[0] == "kant"
    assert row[1] == pytest.approx(0.3)
    assert row[2] == pytest.approx(12.0)
    assert row[3] == pytest.approx(19.0)
    assert row[4] == "synthetic"
    # Stored as naive UTC (TIMESTAMP; TIMESTAMPTZ→Python would need pytz). The
    # instant is preserved: re-attaching UTC recovers the written value
    # (Codex MF5/CM5 resolved without adding a dependency).
    assert row[5].tzinfo is None
    assert row[5].replace(tzinfo=UTC) == _NOW


def test_full_run_replace_is_idempotent(tmp_path: Path) -> None:
    con = connect_cache_benchmark_db(tmp_path / "bench.duckdb")
    try:
        results = [_result("kant"), _result("nietzsche"), _result("rikyu")]
        write_bench_rows(con, results)
        assert _row_count(con) == 3
        # Re-writing the same run replaces, never duplicates.
        write_bench_rows(con, results)
        assert _row_count(con) == 3
        dup = con.execute(
            "SELECT count(*) FROM ("  # noqa: S608  # identifiers are module constants
            "  SELECT run_id, case_id, count(*) c"
            f"  FROM {BENCH_SCHEMA_NAME}.{BENCH_TABLE_NAME}"
            "  GROUP BY run_id, case_id HAVING c > 1)"
        ).fetchone()[0]
        assert dup == 0
    finally:
        con.close()


def test_in_batch_duplicate_natural_key_raises(tmp_path: Path) -> None:
    con = connect_cache_benchmark_db(tmp_path / "bench.duckdb")
    try:
        with pytest.raises(ValueError, match="duplicate natural key"):
            write_bench_rows(con, [_result("kant"), _result("kant")])
    finally:
        con.close()


def test_empty_results_is_noop(tmp_path: Path) -> None:
    con = connect_cache_benchmark_db(tmp_path / "bench.duckdb")
    try:
        assert write_bench_rows(con, []) == 0
        assert _row_count(con) == 0
    finally:
        con.close()
