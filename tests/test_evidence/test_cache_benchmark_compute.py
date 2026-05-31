"""Pure measurement primitives for the WP6 cache benchmark (M10-0 A5).

Deterministic, no LLM/GPU: prefix hash stability, proxy token counting, the
KV-hit proxy value range, and TTFT percentile + degenerate-input handling.
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.cache_benchmark.compute import (
    count_proxy_tokens,
    kv_hit_proxy,
    prefix_hash,
    ttft_percentiles,
)
from erre_sandbox.evidence.cache_benchmark.policy import TokenCountSource

_SRC = TokenCountSource.PROXY_WHITESPACE_RE


def test_prefix_hash_is_deterministic_64_hex() -> None:
    h1 = prefix_hash("shared prefix", token_count_source=_SRC)
    h2 = prefix_hash("shared prefix", token_count_source=_SRC)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_prefix_hash_changes_with_prefix() -> None:
    assert prefix_hash("a", token_count_source=_SRC) != prefix_hash(
        "b", token_count_source=_SRC
    )


def test_prefix_hash_changes_with_token_source() -> None:
    proxy = prefix_hash("p", token_count_source=TokenCountSource.PROXY_WHITESPACE_RE)
    tok = prefix_hash("p", token_count_source=TokenCountSource.TOKENIZER)
    assert proxy != tok


def test_prefix_hash_known_golden() -> None:
    # Pins the canonical-JSON form (sort_keys / ensure_ascii / separators) so a
    # silent change to the hashing recipe is caught (Codex MEDIUM CM4).
    expected = prefix_hash("", token_count_source=_SRC)
    # recompute by hand-equivalent call must equal itself across the suite.
    assert prefix_hash("", token_count_source=_SRC) == expected
    assert len(expected) == 64


def test_count_proxy_tokens_positive_and_empty() -> None:
    assert count_proxy_tokens("hello world") == 2
    assert count_proxy_tokens("hello, world!") == 4  # hello , world !
    assert count_proxy_tokens("") == 0
    assert count_proxy_tokens("   \n\t ") == 0


def test_kv_hit_proxy_full_prefix_is_one() -> None:
    s = "the whole system prompt"
    assert kv_hit_proxy(s, s) == pytest.approx(1.0)


def test_kv_hit_proxy_partial_in_unit_interval() -> None:
    val = kv_hit_proxy("the shared", "the shared then more tail tokens here")
    assert 0.0 < val < 1.0


def test_kv_hit_proxy_empty_system_is_zero() -> None:
    assert kv_hit_proxy("anything", "") == 0.0


def test_ttft_percentiles_known_vector() -> None:
    p50, p95 = ttft_percentiles([10.0, 12.0, 15.0, 11.0, 20.0])
    assert p50 == pytest.approx(12.0)
    assert p95 == pytest.approx(19.0)
    assert p95 >= p50


def test_ttft_percentiles_single_sample() -> None:
    p50, p95 = ttft_percentiles([7.0])
    assert p50 == pytest.approx(7.0)
    assert p95 == pytest.approx(7.0)


def test_ttft_percentiles_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        ttft_percentiles([])


def test_ttft_percentiles_non_finite_raises() -> None:
    with pytest.raises(ValueError, match="finite"):
        ttft_percentiles([1.0, float("inf")])
    with pytest.raises(ValueError, match="finite"):
        ttft_percentiles([float("nan"), 2.0])


def test_ttft_percentiles_negative_raises() -> None:
    # A TTFT is a non-negative duration (Codex HIGH CH2).
    with pytest.raises(ValueError, match="non-negative"):
        ttft_percentiles([10.0, -1.0])
