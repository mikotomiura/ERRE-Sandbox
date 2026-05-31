"""Frozen-model validators for the WP6 cache benchmark (M10-0 A5).

``BenchCase`` makes the shared-prefix-intact invariant unrepresentable to
violate; ``BenchResult`` rejects out-of-range / non-finite / negative /
naive-timestamp / empty-natural-key rows. ``to_row`` order tracks the DDL.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from erre_sandbox.evidence.cache_benchmark.ddl import (
    BENCH_COLUMN_COUNT,
    row_field_names,
)
from erre_sandbox.evidence.cache_benchmark.models import (
    _TO_ROW_FIELDS,
    BenchCase,
    BenchResult,
)
from erre_sandbox.evidence.cache_benchmark.policy import (
    CACHE_BENCHMARK_SCHEMA_VERSION,
    TokenCountSource,
    TtftSource,
)

_NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)


def _result(**overrides: object) -> BenchResult:
    base: dict[str, object] = {
        "schema_version": CACHE_BENCHMARK_SCHEMA_VERSION,
        "case_id": "kant",
        "run_id": "baseline",
        "prefix_hash": "0" * 64,
        "system_token_count": 100,
        "user_token_count": 50,
        "token_count_source": TokenCountSource.PROXY_WHITESPACE_RE,
        "kv_hit_proxy": 0.3,
        "ttft_p50": 12.0,
        "ttft_p95": 19.0,
        "ttft_source": TtftSource.SYNTHETIC,
        "computed_at": _NOW,
    }
    base.update(overrides)
    return BenchResult(**base)  # type: ignore[arg-type]


# --- BenchCase --------------------------------------------------------------


def test_benchcase_accepts_prefix_intact() -> None:
    case = BenchCase(
        case_id="kant",
        system_prompt="PREFIX then the rest",
        user_prompt="u",
        shared_prefix="PREFIX",
    )
    assert case.shared_prefix == "PREFIX"


def test_benchcase_rejects_non_prefix() -> None:
    with pytest.raises(ValidationError, match="must start with shared_prefix"):
        BenchCase(
            case_id="kant",
            system_prompt="something else",
            user_prompt="u",
            shared_prefix="PREFIX",
        )


@pytest.mark.parametrize(
    ("case_id", "shared_prefix", "system_prompt"),
    [
        ("", "P", "P sys"),
        ("kant", "", "sys"),
        ("kant", "P", ""),
    ],
)
def test_benchcase_rejects_empty_fields(
    case_id: str, shared_prefix: str, system_prompt: str
) -> None:
    with pytest.raises(ValidationError):
        BenchCase(
            case_id=case_id,
            system_prompt=system_prompt,
            user_prompt="u",
            shared_prefix=shared_prefix,
        )


# --- BenchResult ------------------------------------------------------------


def test_benchresult_happy_path() -> None:
    r = _result()
    assert r.kv_hit_proxy == 0.3
    assert r.ttft_source is TtftSource.SYNTHETIC


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf")])
def test_benchresult_rejects_kv_hit_proxy_out_of_range(bad: float) -> None:
    with pytest.raises(ValidationError):
        _result(kv_hit_proxy=bad)


def test_benchresult_rejects_p95_below_p50() -> None:
    with pytest.raises(ValidationError, match="ttft_p95"):
        _result(ttft_p50=20.0, ttft_p95=10.0)


@pytest.mark.parametrize(("p50", "p95"), [(-1.0, 5.0), (1.0, -5.0)])
def test_benchresult_rejects_negative_ttft(p50: float, p95: float) -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        _result(ttft_p50=p50, ttft_p95=p95)


def test_benchresult_rejects_non_finite_ttft() -> None:
    with pytest.raises(ValidationError):
        _result(ttft_p95=float("inf"))


def test_benchresult_rejects_naive_computed_at() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _result(computed_at=datetime(2026, 5, 26, 12, 0, 0))  # noqa: DTZ001


@pytest.mark.parametrize("field", ["run_id", "case_id"])
def test_benchresult_rejects_empty_natural_key(field: str) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _result(**{field: ""})


@pytest.mark.parametrize("field", ["system_token_count", "user_token_count"])
def test_benchresult_rejects_negative_token_count(field: str) -> None:
    with pytest.raises(ValidationError):
        _result(**{field: -1})


def test_to_row_matches_ddl_order_and_count() -> None:
    r = _result()
    row = r.to_row()
    assert len(row) == BENCH_COLUMN_COUNT
    assert row_field_names() == _TO_ROW_FIELDS
    # enums flatten to their string value
    assert row[_TO_ROW_FIELDS.index("token_count_source")] == "proxy_whitespace_re"
    assert row[_TO_ROW_FIELDS.index("ttft_source")] == "synthetic"


def test_benchresult_is_frozen_and_forbids_extra() -> None:
    r = _result()
    with pytest.raises(ValidationError):
        BenchResult(**{**r.model_dump(), "surprise": 1})  # type: ignore[arg-type]
