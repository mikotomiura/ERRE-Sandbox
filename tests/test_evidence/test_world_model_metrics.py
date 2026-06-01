"""M10-A S3 E2b — active ``world_model_overlap_jaccard`` (SWM key-Jaccard).

Pins the strict VALID conditions (DA-S3-3 / Codex/user C-2): canonical set-ised
``(axis, key)`` pairs, ``|A∩B| / |A∪B|``, empty union → degenerate, one-side
empty → ``0.0`` valid, and ``None`` input → fail-fast (defence in depth — the
runner gates None to the layer1 stub fallback, so the active function should never
see it). Self-pair gating lives in the runner, not here (the function only sees two
key-sets).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from erre_sandbox.evidence.individuation.layer1 import MetricContext
from erre_sandbox.evidence.individuation.policy import (
    METRIC_SPECS,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.world_model_metrics import (
    WORLD_MODEL_OVERLAP_METRIC,
    WorldModelOverlapMetricError,
    world_model_overlap_jaccard_active,
)

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _ctx() -> MetricContext:
    return MetricContext(
        run_id="run0",
        individual_id="a_rikyu_001|a_rikyu_002",
        base_persona_id="rikyu|rikyu",
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=-1,
        source_epoch_phase="evaluation",
        source_individual_layer_enabled=True,
        source_filter_hash="deadbeef",
        source_table="metrics.individual_state_trace",
    )


def test_metric_name_matches_frozen_stub_name() -> None:
    """Case A: the active metric keeps the frozen layer1 stub name (ADR §3.A③)."""
    assert WORLD_MODEL_OVERLAP_METRIC == "world_model_overlap_jaccard"


def test_full_overlap_is_one() -> None:
    keys = (("self", "relational_disposition"), ("env", "agora"))
    res = world_model_overlap_jaccard_active(keys, keys, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.metric_name == "world_model_overlap_jaccard"
    assert res.channel is MetricChannel.WORLD_MODEL
    assert res.value == pytest.approx(1.0)


def test_partial_overlap_jaccard() -> None:
    a = (("self", "relational_disposition"), ("env", "agora"), ("env", "study"))
    b = (("self", "relational_disposition"), ("env", "peripatos"))
    # ∩ = {self:relational_disposition} = 1 ; ∪ = 4 → 0.25
    res = world_model_overlap_jaccard_active(a, b, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.value == pytest.approx(0.25)


def test_disjoint_is_zero() -> None:
    a = (("env", "agora"),)
    b = (("env", "garden"),)
    res = world_model_overlap_jaccard_active(a, b, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.value == pytest.approx(0.0)


def test_canonical_set_dedups_duplicate_pairs() -> None:
    """Duplicate (axis,key) pairs are set-ised before Jaccard (C-2)."""
    a = (("env", "agora"), ("env", "agora"), ("self", "x"))
    b = (("env", "agora"),)
    # canonical A = {env:agora, self:x} (2), B = {env:agora} (1)
    # ∩ = 1, ∪ = 2 → 0.5
    res = world_model_overlap_jaccard_active(a, b, ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.VALID
    assert res.value == pytest.approx(0.5)


def test_one_side_empty_is_zero_valid() -> None:
    """One empty SWM with the other non-empty → union non-empty → 0.0 valid."""
    res = world_model_overlap_jaccard_active(
        (), (("env", "agora"),), ctx=_ctx(), computed_at=_NOW
    )
    assert res.status is MetricStatus.VALID
    assert res.value == pytest.approx(0.0)


def test_both_empty_is_degenerate() -> None:
    """Empty union → Jaccard undefined → degenerate (not a fabricated 0/1)."""
    res = world_model_overlap_jaccard_active((), (), ctx=_ctx(), computed_at=_NOW)
    assert res.status is MetricStatus.DEGENERATE
    assert res.value is None
    assert res.reason is not None


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (None, (("env", "agora"),)),
        ((("env", "agora"),), None),
        (None, None),
    ],
)
def test_none_input_fails_fast(
    a: tuple[tuple[str, str], ...] | None, b: tuple[tuple[str, str], ...] | None
) -> None:
    """None is the runner's stub-fallback signal; the active fn must never get it."""
    with pytest.raises(WorldModelOverlapMetricError):
        world_model_overlap_jaccard_active(a, b, ctx=_ctx(), computed_at=_NOW)


def test_symmetry_and_determinism() -> None:
    a = (("self", "x"), ("env", "agora"))
    b = (("env", "agora"), ("env", "study"))
    r1 = world_model_overlap_jaccard_active(a, b, ctx=_ctx(), computed_at=_NOW)
    r2 = world_model_overlap_jaccard_active(b, a, ctx=_ctx(), computed_at=_NOW)
    assert r1.value == pytest.approx(r2.value)
    assert r1.value == pytest.approx(1.0 / 3.0)  # ∩=1 (env:agora), ∪=3


def test_spec_is_now_valid_capable() -> None:
    """policy widened world_model_overlap_jaccard to allow VALID at M10-A (E2b)."""
    spec = METRIC_SPECS["world_model_overlap_jaccard"]
    assert MetricStatus.VALID in spec.allowed_statuses
    assert spec.allowed_statuses == frozenset(
        {MetricStatus.VALID, MetricStatus.DEGENERATE, MetricStatus.UNSUPPORTED}
    )
    assert spec.allowed_channels == frozenset({MetricChannel.WORLD_MODEL})
    assert spec.allowed_aggregation_levels == frozenset({AggregationLevel.PER_DYAD})
    # E2b is a gate metric, NOT diagnostic_only (it feeds the path(a) §3.A③ gate)
    assert spec.diagnostic_only is False
