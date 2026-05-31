"""WP6 cache benchmark framework (M10-0 acceptance A5).

Measures the prompt-ordering contract (``docs/m10-0/prompt-ordering-contract.md``)
along four axes — prompt prefix hash, system/user token split, a KV-hit
**proxy**, and TTFT p50/p95 — and persists a baseline. It is deliberately
**not** part of the frozen ``individuation`` claim-boundary contract: it
lives in its own package, writes to a separate DuckDB file under the
``cache_bench`` schema (observer-effect separation), and carries no
``metrics.`` literal.

The TTFT provenance is honest by construction: the synthetic path
(deterministic, CI) and the optional live path are separate functions, so
injected samples can never be stamped as ``live`` (see :mod:`.runner`).
"""

from __future__ import annotations

from erre_sandbox.evidence.cache_benchmark.compute import (
    count_proxy_tokens,
    kv_hit_proxy,
    prefix_hash,
    ttft_percentiles,
)
from erre_sandbox.evidence.cache_benchmark.ddl import (
    BENCH_COLUMN_COUNT,
    bench_ddl_sql,
    row_field_names,
)
from erre_sandbox.evidence.cache_benchmark.models import BenchCase, BenchResult
from erre_sandbox.evidence.cache_benchmark.policy import (
    BENCH_SCHEMA_NAME,
    BENCH_TABLE_NAME,
    CACHE_BENCHMARK_SCHEMA_VERSION,
    KV_HIT_PROXY_BASIS,
    KV_HIT_PROXY_MAX,
    KV_HIT_PROXY_MIN,
    TokenCountSource,
    TtftSource,
)
from erre_sandbox.evidence.cache_benchmark.runner import (
    run_case_synthetic,
    run_cases_synthetic,
    run_live_probe,
)
from erre_sandbox.evidence.cache_benchmark.store import (
    bootstrap_cache_benchmark_schema,
    connect_cache_benchmark_db,
    write_bench_rows,
)

__all__ = [
    "BENCH_COLUMN_COUNT",
    "BENCH_SCHEMA_NAME",
    "BENCH_TABLE_NAME",
    "CACHE_BENCHMARK_SCHEMA_VERSION",
    "KV_HIT_PROXY_BASIS",
    "KV_HIT_PROXY_MAX",
    "KV_HIT_PROXY_MIN",
    "BenchCase",
    "BenchResult",
    "TokenCountSource",
    "TtftSource",
    "bench_ddl_sql",
    "bootstrap_cache_benchmark_schema",
    "connect_cache_benchmark_db",
    "count_proxy_tokens",
    "kv_hit_proxy",
    "prefix_hash",
    "row_field_names",
    "run_case_synthetic",
    "run_cases_synthetic",
    "run_live_probe",
    "ttft_percentiles",
    "write_bench_rows",
]
