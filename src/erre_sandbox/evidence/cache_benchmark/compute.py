"""Pure measurement primitives for the cache benchmark (no I/O, no LLM).

All four functions are side-effect-free and deterministic for fixed input;
they take **strings**, never personas or adapters, so this module never
imports ``cognition`` / ``inference`` (the CLI adapter does that). numpy is
used only for the TTFT percentiles.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.cache_benchmark.policy import (
    CACHE_BENCHMARK_SCHEMA_VERSION,
    TokenCountSource,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# Word runs OR single punctuation chars; whitespace is the separator and is
# never a token. Unicode-aware so the German/Japanese spans in _COMMON_PREFIX
# and RESPONSE_SCHEMA_HINT count. A CJK run groups as one \w+ token — an
# over-merge flagged in the token_count_source provenance, acceptable for a
# *relative* section-size proxy (NOT a real BPE/SentencePiece tokenizer).
_TOKEN_RE: re.Pattern[str] = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def count_proxy_tokens(text: str) -> int:
    """Count deterministic proxy tokens (regex word/punct, not a real tokenizer)."""
    return len(_TOKEN_RE.findall(text))


def prefix_hash(shared_prefix: str, *, token_count_source: TokenCountSource) -> str:
    """SHA-256 over the canonical JSON of the shared prefix + its context.

    The payload binds the hash to ``(schema_version, tokenizer)`` so a hash
    value cannot be misread once either changes. The canonical
    form pins ``sort_keys`` / ``ensure_ascii`` / ``separators`` so the digest
    is byte-stable across environments.
    """
    payload = {
        "schema_version": CACHE_BENCHMARK_SCHEMA_VERSION,
        "shared_prefix": shared_prefix,
        "token_count_source": str(token_count_source),
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def kv_hit_proxy(shared_prefix: str, system_prompt: str) -> float:
    """Shared-prefix token fraction of the system prompt, in ``[0.0, 1.0]``.

    A **proxy**, not a measured GPU hit: the analytic upper bound on the
    cross-request KV reuse RadixAttention could achieve if prefix matching
    were token-exact (real hit ≤ this, after batching / eviction / tokenizer
    boundaries). See :data:`policy.KV_HIT_PROXY_BASIS`. Returns ``0.0`` for an
    empty system prompt (no division by zero).
    """
    system_tokens = count_proxy_tokens(system_prompt)
    if system_tokens == 0:
        return 0.0
    return count_proxy_tokens(shared_prefix) / system_tokens


def ttft_percentiles(samples_ms: Sequence[float]) -> tuple[float, float]:
    """Return ``(p50, p95)`` of time-to-first-token samples (milliseconds).

    Raises :class:`ValueError` on an empty input, a non-finite sample, or a
    negative sample — a TTFT is a non-negative duration, so a silent NaN/
    negative baseline would be meaningless.
    """
    if len(samples_ms) == 0:
        msg = "ttft_percentiles requires at least one sample"
        raise ValueError(msg)
    arr = np.asarray(samples_ms, dtype=float)
    if not bool(np.all(np.isfinite(arr))):
        msg = f"ttft samples must all be finite, got {list(samples_ms)!r}"
        raise ValueError(msg)
    if bool(np.any(arr < 0.0)):
        msg = f"ttft samples must be non-negative durations, got {list(samples_ms)!r}"
        raise ValueError(msg)
    p50 = float(np.percentile(arr, 50, method="linear"))
    p95 = float(np.percentile(arr, 95, method="linear"))
    # percentile is monotone in q so p95 >= p50, but guard against float fuzz.
    p95 = max(p95, p50)
    if not (math.isfinite(p50) and math.isfinite(p95)):  # pragma: no cover
        msg = "ttft percentiles produced a non-finite value"
        raise ValueError(msg)
    return p50, p95


__all__ = [
    "count_proxy_tokens",
    "kv_hit_proxy",
    "prefix_hash",
    "ttft_percentiles",
]
