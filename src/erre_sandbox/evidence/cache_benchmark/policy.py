"""Frozen contract for the WP6 cache benchmark (leaf module).

This module imports **nothing** from the rest of the ``cache_benchmark``
package — it is the dependency leaf (same discipline as
``individuation.policy``) so ``compute`` / ``ddl`` / ``models`` can all
import the enums and constants without any import cycle.

The cache benchmark is the M10-0 WP6 / acceptance A5 deliverable: it
measures the **prompt-ordering contract** (``docs/m10-0/prompt-ordering-contract.md``)
without touching ``metrics.individuation`` — its trace lives in a separate
DuckDB file under a separate schema (observer-effect separation), so this
module deliberately carries no ``metrics.`` literal.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

CACHE_BENCHMARK_SCHEMA_VERSION: Final[str] = "cache-bench-m10-0.1"
"""Pinned schema version stamped into every ``BenchResult`` and the baseline."""

BENCH_SCHEMA_NAME: Final[str] = "cache_bench"
"""DuckDB schema for the benchmark trace — NOT ``metrics`` (grep-gate safe)."""

BENCH_TABLE_NAME: Final[str] = "prefix_cache"
"""Bare benchmark trace table name inside :data:`BENCH_SCHEMA_NAME`."""

KV_HIT_PROXY_MIN: Final[float] = 0.0
KV_HIT_PROXY_MAX: Final[float] = 1.0

KV_HIT_PROXY_BASIS: Final[str] = "shared_prefix_tokens/system_prompt_tokens"
"""Provenance for :func:`compute.kv_hit_proxy`.

The proxy is the shared-prefix token fraction of the **system prompt only**;
it is an analytic *upper bound* on cross-request RadixAttention reuse, not a
measured GPU hit rate and not a whole-request (system+user) hit rate.
"""


class TokenCountSource(StrEnum):
    """How ``system_token_count`` / ``user_token_count`` were derived."""

    PROXY_WHITESPACE_RE = "proxy_whitespace_re"
    """Deterministic regex word/punct proxy — NOT a real model tokenizer."""
    TOKENIZER = "tokenizer"
    """A real model tokenizer (reserved for a future live row; unused in M10-0)."""


class TtftSource(StrEnum):
    """Provenance for the TTFT percentiles (synthetic must never claim live)."""

    SYNTHETIC = "synthetic"
    """Injected deterministic samples — no LLM/GPU/server contact (CI path)."""
    LIVE = "live"
    """Measured against a real Ollama/SGLang server (optional, never a CI gate)."""


__all__ = [
    "BENCH_SCHEMA_NAME",
    "BENCH_TABLE_NAME",
    "CACHE_BENCHMARK_SCHEMA_VERSION",
    "KV_HIT_PROXY_BASIS",
    "KV_HIT_PROXY_MAX",
    "KV_HIT_PROXY_MIN",
    "TokenCountSource",
    "TtftSource",
]
