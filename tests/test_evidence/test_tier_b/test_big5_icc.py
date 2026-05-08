"""Tests for ``erre_sandbox.evidence.tier_b.big5_icc`` (M9-eval P4a).

Pin the dual-consumer split (M9-eval ME-11 / Codex P4a HIGH-2):

* ``ICC(C,k)`` consistency average drives ``me1_fallback_fire``.
* ``ICC(A,1)`` absolute agreement single is exposed for the DB9 drift gate.

Degenerate handling (Codex P4a MEDIUM-5 / LOW-2): identical-all-constant
windows return ``icc_*=1.0, degenerate=True`` deterministically, not via
``ANOVA 0/0``.
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.tier_b.big5_icc import (
    ME1_FALLBACK_LOWER_CI_THRESHOLD,
    ME1_FALLBACK_POINT_THRESHOLD,
    Big5ICCResult,
    compute_big5_icc,
)
from erre_sandbox.evidence.tier_b.ipip_neo import Big5Scores


def _scores(
    e: float,
    a: float,
    c: float,
    n: float,
    o: float,
    *,
    n_items: int = 50,
) -> Big5Scores:
    """Compact constructor for synthetic Big5Scores fixtures."""
    return Big5Scores(
        extraversion=e,
        agreeableness=a,
        conscientiousness=c,
        neuroticism=n,
        openness=o,
        n_items=n_items,
        version="ipip-50",
    )


def test_compute_big5_icc_identical_windows_degenerate_returns_one() -> None:
    """LOW-2 / MEDIUM-5: identical responses are a deliberate special case.

    The ANOVA decomposition would give 0/0; the helper short-circuits to
    ICC=1.0 with ``degenerate=True`` and ``me1_fallback_fire=False`` so the
    consumer can tell apart "perfect reliability" from "no variance to
    measure".
    """
    same = _scores(3.0, 3.0, 3.0, 3.0, 3.0)
    result = compute_big5_icc([same] * 25, n_resamples=200, seed=0)
    assert isinstance(result, Big5ICCResult)
    assert result.degenerate is True
    assert result.icc_consistency_average == pytest.approx(1.0)
    assert result.icc_consistency_single == pytest.approx(1.0)
    assert result.icc_agreement_single == pytest.approx(1.0)
    assert result.icc_agreement_average == pytest.approx(1.0)
    assert result.me1_fallback_fire is False
    assert result.formula_notation == "McGraw-Wong 1996"


def test_compute_big5_icc_consistency_vs_agreement_offset_sensitivity() -> None:
    """HIGH-2: systematic offset shrinks ICC(A,*) but not ICC(C,*).

    Build two batches of the same window pattern; the second batch has a
    systematic +1 Likert offset on every dimension. Consistency ICC stays
    the same (rank order preserved), agreement ICC drops because absolute
    levels diverge.
    """
    pattern = [
        _scores(1.5, 2.0, 4.0, 3.5, 4.5),
        _scores(2.0, 2.5, 4.5, 3.0, 4.0),
        _scores(1.0, 2.5, 3.5, 3.5, 4.5),
        _scores(2.5, 1.5, 4.0, 3.0, 4.0),
    ]
    offset = [
        _scores(
            s.extraversion + 1.0,
            s.agreeableness + 1.0,
            s.conscientiousness + 1.0,
            s.neuroticism + 1.0,
            s.openness + 1.0,
        )
        for s in pattern
    ]

    no_offset = compute_big5_icc(pattern * 4, n_resamples=200, seed=0)
    mixed = pattern + offset + pattern + offset
    with_offset = compute_big5_icc(mixed, n_resamples=200, seed=0)

    # Consistency tracks rank order, so the offset blend should NOT crush
    # the consistency ICC even though absolute levels move.
    cons_drop = no_offset.icc_consistency_average - with_offset.icc_consistency_average
    assert cons_drop <= 0.05
    # Absolute agreement should drop because the new windows live at a
    # different level. Allow a small tolerance for finite-sample noise.
    assert (with_offset.icc_agreement_single < no_offset.icc_agreement_single) or (
        with_offset.icc_agreement_single < 0.95
    )


def test_compute_big5_icc_me1_fallback_uses_consistency_only() -> None:
    """HIGH-2: fallback fire is driven by consistency thresholds, not agreement."""
    # Build windows with high agreement (no offsets) but uncorrelated dimension
    # pattern so consistency drops below 0.6.
    windows = [
        _scores(2.5, 2.5, 2.5, 2.5, 2.5),
        _scores(2.5, 2.5, 2.5, 2.5, 2.5),
    ] * 12 + [_scores(2.5, 2.5, 2.5, 2.5, 2.5)]
    # Make one window uncorrelated — extreme values on a different ordering.
    windows[0] = _scores(5.0, 1.0, 5.0, 1.0, 5.0)
    result = compute_big5_icc(windows, n_resamples=200, seed=0)
    # The fallback fire decision must reference consistency — assert by
    # construction: if the consistency point or lower CI is below the ME-1
    # thresholds, fire must be True; otherwise False.
    expected_fire = (
        result.icc_consistency_average < ME1_FALLBACK_POINT_THRESHOLD
        or result.icc_consistency_lower_ci < ME1_FALLBACK_LOWER_CI_THRESHOLD
    )
    assert result.me1_fallback_fire == expected_fire


def test_compute_big5_icc_db9_agreement_field_independent_of_me1_fire() -> None:
    """HIGH-2 / ME-11: agreement values are surfaced regardless of consistency fire."""
    pattern = [
        _scores(1.5, 2.0, 4.0, 3.5, 4.5),
        _scores(2.0, 2.5, 4.5, 3.0, 4.0),
        _scores(1.0, 2.5, 3.5, 3.5, 4.5),
        _scores(2.5, 1.5, 4.0, 3.0, 4.0),
    ]
    result = compute_big5_icc(pattern * 6, n_resamples=200, seed=0)
    # Both ICC variants must be populated regardless of fire flag.
    assert result.icc_agreement_single != 0.0
    assert result.icc_agreement_average != 0.0
    assert result.icc_consistency_average != 0.0


def test_compute_big5_icc_seed_stability() -> None:
    """ME-5 RNG seed: same seed → identical bootstrap CI."""
    pattern = [
        _scores(1.5, 2.0, 4.0, 3.5, 4.5),
        _scores(2.0, 2.5, 4.5, 3.0, 4.0),
        _scores(1.0, 2.5, 3.5, 3.5, 4.5),
        _scores(2.5, 1.5, 4.0, 3.0, 4.0),
    ] * 6
    a = compute_big5_icc(pattern, n_resamples=200, seed=123)
    b = compute_big5_icc(pattern, n_resamples=200, seed=123)
    assert a == b


def test_compute_big5_icc_rejects_too_few_windows() -> None:
    """Boundary: ICC needs >= 2 windows."""
    with pytest.raises(ValueError, match=">=2 windows"):
        compute_big5_icc([_scores(3, 3, 3, 3, 3)])
