"""Typed cache-benchmark models: ``BenchCase`` (input) + ``BenchResult`` (row).

``BenchCase`` makes "the frozen shared prefix is intact at the head of the
system prompt" a construction-time invariant rather than a comment.
``BenchResult`` makes a malformed benchmark row unrepresentable (value
ranges, the TTFT non-negative/ordering invariant, tz-aware ``computed_at``,
non-empty natural-key fields). ``to_row`` derives its order from
:func:`.ddl.row_field_names`, asserted equal at import time.
"""

from __future__ import annotations

import math
from datetime import (
    UTC,
    datetime,  # used in a pydantic field annotation (runtime)
)
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from erre_sandbox.evidence.cache_benchmark.ddl import row_field_names
from erre_sandbox.evidence.cache_benchmark.policy import (
    KV_HIT_PROXY_MAX,
    KV_HIT_PROXY_MIN,
    TokenCountSource,
    TtftSource,
)

# Import-time lockstep with the DDL column order (same fail-fast discipline as
# individuation.models): a column added to ddl._BENCH_DDL_COLUMNS without a
# matching to_row entry (or vice versa) fails at import.
_TO_ROW_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "case_id",
    "run_id",
    "prefix_hash",
    "system_token_count",
    "user_token_count",
    "token_count_source",
    "kv_hit_proxy",
    "ttft_p50",
    "ttft_p95",
    "ttft_source",
    "computed_at",
)
if row_field_names() != _TO_ROW_FIELDS:
    msg = (
        "cache_benchmark BenchResult.to_row field order drifted from"
        f" ddl.row_field_names(): {_TO_ROW_FIELDS} != {row_field_names()}"
    )
    raise RuntimeError(msg)


class BenchCase(BaseModel):
    """One benchmark input: a prompt pair plus its declared shared prefix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    system_prompt: str
    user_prompt: str
    shared_prefix: str

    @model_validator(mode="after")
    def _check_non_empty(self) -> Self:
        if not self.case_id:
            msg = "case_id must be non-empty"
            raise ValueError(msg)
        if not self.shared_prefix:
            msg = (
                "shared_prefix must be non-empty (empty prefix is a meaningless proxy)"
            )
            raise ValueError(msg)
        if not self.system_prompt:
            msg = "system_prompt must be non-empty"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_prefix_intact(self) -> Self:
        if not self.system_prompt.startswith(self.shared_prefix):
            msg = (
                "system_prompt must start with shared_prefix"
                " (the shared prefix is load-bearing for KV cache reuse)"
            )
            raise ValueError(msg)
        return self


class BenchResult(BaseModel):
    """One benchmark trace row (flattens to the DDL column order)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    case_id: str
    run_id: str
    prefix_hash: str
    system_token_count: int = Field(ge=0)
    user_token_count: int = Field(ge=0)
    token_count_source: TokenCountSource
    kv_hit_proxy: float
    ttft_p50: float
    ttft_p95: float
    ttft_source: TtftSource
    computed_at: datetime

    @model_validator(mode="after")
    def _check_natural_key_non_empty(self) -> Self:
        if not self.run_id:
            msg = "run_id must be non-empty (natural key component)"
            raise ValueError(msg)
        if not self.case_id:
            msg = "case_id must be non-empty (natural key component)"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_kv_hit_proxy_range(self) -> Self:
        if not math.isfinite(self.kv_hit_proxy):
            msg = f"kv_hit_proxy must be finite, got {self.kv_hit_proxy!r}"
            raise ValueError(msg)
        if not (KV_HIT_PROXY_MIN <= self.kv_hit_proxy <= KV_HIT_PROXY_MAX):
            msg = (
                f"kv_hit_proxy must be in [{KV_HIT_PROXY_MIN}, {KV_HIT_PROXY_MAX}],"
                f" got {self.kv_hit_proxy!r}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_ttft(self) -> Self:
        for name, val in (("ttft_p50", self.ttft_p50), ("ttft_p95", self.ttft_p95)):
            if not math.isfinite(val):
                msg = f"{name} must be finite, got {val!r}"
                raise ValueError(msg)
            if val < 0.0:
                msg = f"{name} must be non-negative (a TTFT is a duration), got {val!r}"
                raise ValueError(msg)
        if self.ttft_p95 < self.ttft_p50:
            msg = f"ttft_p95 ({self.ttft_p95}) must be >= ttft_p50 ({self.ttft_p50})"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_computed_at_tz_aware(self) -> Self:
        if self.computed_at.tzinfo is None:
            msg = "computed_at must be timezone-aware (UTC)"
            raise ValueError(msg)
        return self

    def to_row(self) -> tuple[object, ...]:
        """Flatten to the DDL row tuple (column order from ddl)."""
        flat: dict[str, object] = {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "prefix_hash": self.prefix_hash,
            "system_token_count": self.system_token_count,
            "user_token_count": self.user_token_count,
            "token_count_source": self.token_count_source.value,
            "kv_hit_proxy": self.kv_hit_proxy,
            "ttft_p50": self.ttft_p50,
            "ttft_p95": self.ttft_p95,
            "ttft_source": self.ttft_source.value,
            # Stored as a naive UTC TIMESTAMP (see ddl: TIMESTAMPTZ→Python needs
            # pytz). Readers re-attach UTC; the instant is preserved.
            "computed_at": self.computed_at.astimezone(UTC).replace(tzinfo=None),
        }
        return tuple(flat[name] for name in _TO_ROW_FIELDS)


__all__ = [
    "BenchCase",
    "BenchResult",
]
