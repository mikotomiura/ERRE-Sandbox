"""Reachability positive-control regression (freeze ADR §4, M11-C3b §3.A④ lesson).

The freeze ADR's §4 throwaway CPU spike confirmed the M1 distance is *reachable* —
that the frozen ``world_model_overlap_jaccard_active`` body, driven through the
scorer's :func:`_separation`, actually distinguishes identical from disjoint floors
and degrades gracefully on an empty union. This test promotes that spike into a
permanent regression so a future refactor cannot silently break the distance wiring
(the "measurement cannot reach its target" failure mode the M11-C3b §3.A④ gate hit).

It exercises the **real** frozen distance body (no mock) via the scorer's own
``_separation`` — the same path M1 uses — so a break in either the active fn or the
``S = 1 - Jaccard`` adapter is caught.
"""

from __future__ import annotations

from erre_sandbox.evidence.live_carry import constants as _c
from erre_sandbox.evidence.live_carry.scorer import _separation


def test_reach_a_identical_floor_is_null_side_healthy() -> None:
    """(a) identical non-empty floor → S <= REACH_NULL_MAX (= 0.0 here)."""
    keys = (("self", "k1"), ("concept", "k2"))
    sep = _separation(keys, keys)
    assert sep is not None
    assert sep == 0.0
    assert sep <= _c.REACH_NULL_MAX


def test_reach_b_disjoint_floor_is_positive_side_healthy() -> None:
    """(b) key-disjoint non-empty floor → S >= REACH_POS_MIN (= 1.0 here)."""
    sep = _separation((("self", "a"),), (("self", "b"),))
    assert sep is not None
    assert sep == 1.0
    assert sep >= _c.REACH_POS_MIN


def test_reach_c_both_empty_is_degenerate_excluded() -> None:
    """(c) both floors empty → union empty → DEGENERATE → None (dropped from valid)."""
    assert _separation((), ()) is None


def test_partial_overlap_is_one_minus_jaccard() -> None:
    """A partial-overlap floor returns exactly ``1 - |A∩B| / |A∪B|`` (sanity)."""
    # A={x,y}, B={y,z} → ∩={y}, ∪={x,y,z} → Jaccard 1/3 → S = 2/3.
    sep = _separation((("self", "x"), ("self", "y")), (("self", "y"), ("self", "z")))
    assert sep is not None
    assert abs(sep - (2.0 / 3.0)) < 1e-12
