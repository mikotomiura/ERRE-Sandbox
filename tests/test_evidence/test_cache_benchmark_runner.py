"""Runner provenance for the WP6 cache benchmark.

The synthetic and live paths stamp their ``ttft_source`` internally, and
there is no generic entry that accepts a caller-chosen source — so injected
samples can never be passed off as live (Codex MF1).
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from erre_sandbox.evidence.cache_benchmark import runner
from erre_sandbox.evidence.cache_benchmark.models import BenchCase
from erre_sandbox.evidence.cache_benchmark.policy import TokenCountSource, TtftSource
from erre_sandbox.evidence.cache_benchmark.runner import (
    run_case_synthetic,
    run_live_probe,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_NOW = datetime(2026, 5, 26, tzinfo=UTC)
_CASE = BenchCase(
    case_id="kant",
    system_prompt="PREFIX then tail",
    user_prompt="user",
    shared_prefix="PREFIX",
)


def test_synthetic_path_stamps_synthetic() -> None:
    r = run_case_synthetic(
        _CASE, samples_ms=[10.0, 20.0], run_id="baseline", computed_at=_NOW
    )
    assert r.ttft_source is TtftSource.SYNTHETIC
    assert r.token_count_source is TokenCountSource.PROXY_WHITESPACE_RE
    assert r.case_id == "kant"
    assert r.system_token_count > 0


def test_live_probe_stamps_live() -> None:
    def fake_probe(_case: BenchCase) -> Sequence[float]:
        return [33.0, 41.0, 38.0]

    r = run_live_probe(_CASE, probe=fake_probe, run_id="live1", computed_at=_NOW)
    assert r.ttft_source is TtftSource.LIVE
    assert r.ttft_p50 > 0


def test_no_generic_run_case_with_ttft_source() -> None:
    # Structural guarantee (MF1): the public surface is synthetic/live-fixed.
    assert "run_case" not in runner.__all__
    assert not hasattr(runner, "run_case")
    # Neither fixed entry exposes a caller-settable ttft_source parameter.
    for fn in (run_case_synthetic, run_live_probe):
        assert "ttft_source" not in inspect.signature(fn).parameters


def test_run_cases_synthetic_one_row_per_case() -> None:
    case2 = BenchCase(
        case_id="rikyu",
        system_prompt="PREFIX wabi",
        user_prompt="u",
        shared_prefix="PREFIX",
    )
    results = runner.run_cases_synthetic(
        [_CASE, case2], samples_ms=[5.0, 9.0], run_id="baseline", computed_at=_NOW
    )
    assert [r.case_id for r in results] == ["kant", "rikyu"]
    assert all(r.ttft_source is TtftSource.SYNTHETIC for r in results)
