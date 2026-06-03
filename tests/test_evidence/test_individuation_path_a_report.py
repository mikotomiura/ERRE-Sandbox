"""M10-A S3.5 / PR-S4b path(a) verdict sidecar roundtrip + conformance-marker coverage.

Pins that the durable sidecar (``*.path_a_verdict.json``) carries the five-state
verdict, the per-seed evidence, and — crucially — the live ``null_control_kind`` +
``null_control_conformance`` markers (PR-S4b: ``h2_owner_shuffle_resynth`` /
``conformant``) so the claim boundary lives on the artifact itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.path_a_gate import (
    NULL_CONTROL_CONFORMANCE,
    NULL_CONTROL_KIND,
    CriterionResult,
    PathAScoreReport,
    PathAVerdict,
    SeedScore,
)
from erre_sandbox.evidence.individuation.path_a_h2_gate import (
    H2NullControlResult,
    H2Verdict,
)
from erre_sandbox.evidence.individuation.path_a_report import (
    PATH_A_VERDICT_SIDECAR_SUFFIX,
    from_score_report,
    path_a_verdict_sidecar_path_for,
    read_path_a_verdict_sidecar,
    write_path_a_verdict_sidecar_atomic,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _score_report() -> PathAScoreReport:
    seed = SeedScore(
        run_idx=0,
        verdict=PathAVerdict.INVALID,
        reason="④null_control: null-control INVALID",
        belief_variance=CriterionResult(PathAVerdict.GO, "all valid"),
        belief_distribution=CriterionResult(PathAVerdict.GO, "distinct"),
        jaccard_separation=CriterionResult(PathAVerdict.GO, "median 0.2"),
        null_control=H2NullControlResult(
            H2Verdict.INVALID,
            "H2 INVALID: null_central 0.3000 >= d_obs 0.2000",
            d_obs=0.2,
            null_central=0.3,
            p_high=0.7,
            n_finite_null=1000,
            powered=None,
        ),
        jaccard_median=0.2,
        jaccard_valid_count=3,
        belief_distribution_summary=(
            ("a_rikyu_001", (("trust", 1), ("wary", 1))),
            ("a_rikyu_002", (("trust", 2), ("wary", 1))),
        ),
    )
    return PathAScoreReport(
        run_id="run0",
        verdict=PathAVerdict.INVALID,
        reason="most-severe across seeds = invalid",
        seeds=(seed,),
    )


def test_from_score_report_carries_conformance_markers() -> None:
    report = from_score_report(_score_report(), computed_at=_NOW)
    assert report.verdict == "invalid"
    assert report.null_control_kind == NULL_CONTROL_KIND
    assert report.null_control_conformance == NULL_CONTROL_CONFORMANCE
    assert report.computed_at == _NOW
    assert report.null_control_kind == "h2_owner_shuffle_resynth"
    assert report.null_control_conformance == "conformant"
    assert report.seeds[0].null_control is not None
    assert report.seeds[0].null_control.d_obs == 0.2
    assert report.seeds[0].null_control.null_central == 0.3


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    report = from_score_report(_score_report(), computed_at=_NOW)
    path = path_a_verdict_sidecar_path_for(tmp_path / "pilot.duckdb")
    assert path.name.endswith(PATH_A_VERDICT_SIDECAR_SUFFIX)
    write_path_a_verdict_sidecar_atomic(path, report)
    loaded = read_path_a_verdict_sidecar(path)
    assert loaded == report
    assert loaded.null_control_conformance == NULL_CONTROL_CONFORMANCE


def test_sidecar_path_suffix(tmp_path: Path) -> None:
    path = path_a_verdict_sidecar_path_for(tmp_path / "x.duckdb")
    assert path.name == "x.duckdb.path_a_verdict.json"


def test_legacy_shape_null_control_is_rejected() -> None:
    """MEDIUM-1: a legacy ``swm_key_shuffle_projection`` sidecar shape is rejected.

    The ④ evidence shape changed (central/p95/swm_*_count → d_obs/null_central/...).
    No real path_a sidecar exists yet — the gate was structurally GO-incapable before
    PR-S4b — so there is nothing to migrate; ``extra=forbid`` loudly rejects an old
    payload (a clear ValidationError) rather than silently misreading it, and the
    ``null_control_kind`` field discriminates the shape on the artifact itself.
    """
    import pytest
    from pydantic import ValidationError

    from erre_sandbox.evidence.individuation.path_a_report import NullControlReport

    legacy_payload = {
        "outcome": "invalid",
        "reason": "p95 0.25 <= 0.60",
        "central": 0.2,
        "p95": 0.25,
        "k": 1000,
        "swm_raw_key_count": 9,
        "swm_unique_key_count": 6,
    }
    with pytest.raises(ValidationError):
        NullControlReport.model_validate(legacy_payload)
