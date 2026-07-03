"""Running-track freeze pins (design-final.md §5): result-independent constants.

The running track adds **exactly one** new frozen scalar and even that is a
structural identification with an inherited floor — pinned here so it can only
move if the inherited floor moves (a superseding ADR). No new tunable scalar
(design-final.md §5 全数値凍結表).
"""

from __future__ import annotations

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running import constants as _rc
from erre_sandbox.evidence.d0_substrate.smoke import D0B_TICK_HZ


def test_runningness_tv_floor_is_structural_identity_with_landscape_floor() -> None:
    # RUNNINGNESS_TV_FLOOR is not an independently chosen number: it IS the
    # inherited [0,1] practical-effect floor (design-final.md §3.2/§5).
    assert _rc.RUNNINGNESS_TV_FLOOR == _c.LANDSCAPE_JACCARD_FLOOR
    assert _rc.RUNNINGNESS_TV_FLOOR == 0.10


def test_no_new_tunable_scalar_beyond_the_inherited_identification() -> None:
    # The only running-track floor equals an inherited frozen floor; the other
    # policy knobs are read-only inherited from the frozen parent constants.
    assert _rc.RUNNINGNESS_TV_FLOOR == _c.LANDSCAPE_JACCARD_FLOOR
    assert _c.K_RETRIEVE == 8
    assert _c.M_MEMORIES == 20
    assert _c.CELL_MICRO_RADIUS_M == 10.0
    assert _c.B == 64


def test_policy_physics_constants_inherited() -> None:
    assert _rc.POLICY_SPEED_MPS == 1.3
    assert _rc.POLICY_TICK_HZ == D0B_TICK_HZ
