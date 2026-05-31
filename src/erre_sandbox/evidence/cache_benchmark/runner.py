"""Assemble :class:`BenchResult` rows from cases + TTFT samples.

The synthetic and live paths are **separate functions** so the TTFT
provenance cannot be forged: ``run_case_synthetic`` interns
``ttft_source=SYNTHETIC`` and ``run_live_probe`` interns ``LIVE`` — there is
no generic ``run_case(..., ttft_source)`` entry that would let injected
samples be stamped as live. The core never starts a server; the live path
receives its samples from an injected *probe* callable (the CLI's optional
``--live`` mode / an eval-extra smoke test supplies a real one).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.evidence.cache_benchmark.compute import (
    count_proxy_tokens,
    kv_hit_proxy,
    prefix_hash,
    ttft_percentiles,
)
from erre_sandbox.evidence.cache_benchmark.models import BenchCase, BenchResult
from erre_sandbox.evidence.cache_benchmark.policy import (
    CACHE_BENCHMARK_SCHEMA_VERSION,
    TokenCountSource,
    TtftSource,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime

# M10-0 always uses the deterministic regex proxy for the token split; the
# TTFT provenance is the axis that varies between synthetic and live.
_TOKEN_SOURCE: TokenCountSource = TokenCountSource.PROXY_WHITESPACE_RE


def _build(
    case: BenchCase,
    *,
    samples_ms: Sequence[float],
    ttft_source: TtftSource,
    run_id: str,
    computed_at: datetime,
) -> BenchResult:
    p50, p95 = ttft_percentiles(samples_ms)
    return BenchResult(
        schema_version=CACHE_BENCHMARK_SCHEMA_VERSION,
        case_id=case.case_id,
        run_id=run_id,
        prefix_hash=prefix_hash(case.shared_prefix, token_count_source=_TOKEN_SOURCE),
        system_token_count=count_proxy_tokens(case.system_prompt),
        user_token_count=count_proxy_tokens(case.user_prompt),
        token_count_source=_TOKEN_SOURCE,
        kv_hit_proxy=kv_hit_proxy(case.shared_prefix, case.system_prompt),
        ttft_p50=p50,
        ttft_p95=p95,
        ttft_source=ttft_source,
        computed_at=computed_at,
    )


def run_case_synthetic(
    case: BenchCase,
    *,
    samples_ms: Sequence[float],
    run_id: str,
    computed_at: datetime,
) -> BenchResult:
    """Build a result from injected samples; ``ttft_source`` is fixed synthetic."""
    return _build(
        case,
        samples_ms=samples_ms,
        ttft_source=TtftSource.SYNTHETIC,
        run_id=run_id,
        computed_at=computed_at,
    )


def run_live_probe(
    case: BenchCase,
    *,
    probe: Callable[[BenchCase], Sequence[float]],
    run_id: str,
    computed_at: datetime,
) -> BenchResult:
    """Build a result from a real-server *probe*; ``ttft_source`` is fixed live.

    The *probe* performs the actual server round-trips and returns measured
    TTFT samples (ms). It is supplied by the optional live path only — the
    core does not import any inference adapter.
    """
    return _build(
        case,
        samples_ms=probe(case),
        ttft_source=TtftSource.LIVE,
        run_id=run_id,
        computed_at=computed_at,
    )


def run_cases_synthetic(
    cases: Sequence[BenchCase],
    *,
    samples_ms: Sequence[float],
    run_id: str,
    computed_at: datetime,
) -> list[BenchResult]:
    """Run every case through the synthetic path with the same sample vector."""
    return [
        run_case_synthetic(
            case, samples_ms=samples_ms, run_id=run_id, computed_at=computed_at
        )
        for case in cases
    ]


__all__ = [
    "run_case_synthetic",
    "run_cases_synthetic",
    "run_live_probe",
]
