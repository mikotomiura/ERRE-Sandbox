"""M10-A S2 (E4): Burrows within-individual self-floor diagnostic.

Pins the calibration-only contract (Codex CX6): structured raw deltas + per
subsample sample sizes + the explicit ``no_ci`` / ``no_go_no_go`` /
``no_threshold_update`` discipline flags + the non-independence limitation. The
diagnostic only *reads* the frozen ``BURROWS_DELTA_MAX`` (4.0) for comparison and
never rewrites it (CX7). Determinism is asserted (no RNG).
"""

from __future__ import annotations

from erre_sandbox.evidence.individuation.burrows_self_floor import (
    BurrowsSelfFloorResult,
    compute_burrows_self_floor,
)
from erre_sandbox.evidence.individuation.c3b_verdict import BURROWS_DELTA_MAX


def _result() -> BurrowsSelfFloorResult:
    return compute_burrows_self_floor("rikyu", "ja")


def test_frozen_burrows_delta_max_is_4() -> None:
    """CX7: the frozen base-retention threshold stays 4.0 (read-only here)."""
    assert BURROWS_DELTA_MAX == 4.0


def test_self_floor_structure() -> None:
    r = _result()
    assert r.persona_id == "rikyu"
    assert r.language == "ja"
    assert r.corpus_poem_count == 5
    # split-half is exactly the even/odd pair; jackknife is one drop per poem.
    assert len(r.split_half) == 2
    assert len(r.jackknife) == r.corpus_poem_count
    assert {s.label for s in r.split_half} == {"even", "odd"}
    # the odd/even imbalance (3 vs 2 poems) is observable per CX6.
    even, odd = r.split_half
    assert {even.poem_count, odd.poem_count} == {3, 2}


def test_self_floor_reports_sample_sizes_and_fw_counts() -> None:
    """CX6: every subsample carries poem / char / token / present-fw counts."""
    r = _result()
    assert r.surviving_function_words > 0
    for s in (*r.split_half, *r.jackknife):
        assert s.poem_count >= 1
        assert s.char_count > 0
        assert s.token_count > 0
        assert 0 <= s.present_function_words <= r.surviving_function_words
        assert s.delta is None or s.delta >= 0.0


def test_self_floor_is_calibration_only_not_verdict() -> None:
    """CX6: explicit discipline flags + frozen value read, not rewritten."""
    r = _result()
    assert r.no_ci is True
    assert r.no_go_no_go is True
    assert r.no_threshold_update is True
    assert r.frozen_delta_self_max == BURROWS_DELTA_MAX  # read, not modified
    assert r.limitation  # non-empty non-independence caveat


def test_self_floor_aggregates_over_finite_deltas() -> None:
    r = _result()
    finite = [s.delta for s in (*r.split_half, *r.jackknife) if s.delta is not None]
    assert finite, "expected at least one finite self-delta"
    assert r.min_delta == min(finite)
    assert r.max_delta == max(finite)
    assert r.min_delta <= r.median_delta <= r.max_delta
    # within-band reflects whether 4.0 sits inside [min, max]
    assert r.delta_self_max_within_observed_band == (
        r.min_delta <= BURROWS_DELTA_MAX <= r.max_delta
    )


def test_self_floor_is_deterministic() -> None:
    """No RNG: two runs produce identical summaries."""
    assert _result().to_summary_dict() == _result().to_summary_dict()
