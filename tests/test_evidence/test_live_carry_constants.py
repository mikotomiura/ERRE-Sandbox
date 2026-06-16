"""Pin the III-a live §5.3 frozen §0 constants to the ADR table verbatim.

The GPU 前 threshold freeze ADR (``.steering/20260616-iiia-live-pregpu-freeze/``,
ACCEPTED, binding=user) pre-registered every value **before** any live-exec result
was seen. This test is the forking-paths guard's regression pin: a constant can only
change by a deliberate edit that also updates this expected table (which itself
requires a superseding ADR). The cap geometry is asserted to track the evidence-layer
frozen mirror (USE-only), not an independently tuned literal.
"""

from __future__ import annotations

from erre_sandbox.evidence.live_carry import constants as _c
from erre_sandbox.evidence.saturation.constants import MAX_TOTAL_MODULATION


def test_frozen_section0_table_verbatim() -> None:
    """Every §0 value equals the ADR-frozen number (no post-result tuning)."""
    assert _c.R_MIN == 2.0
    assert _c.DEGENERATE_NULL_FLOOR == 0.10
    assert _c.ON_NOISE_FACTOR == 1.5
    assert _c.M0_ENGAGEMENT_FLOOR == 5
    assert _c.COVERAGE_MIN == 0.50
    assert _c.MIN_TICK_PAIRS == 10
    assert _c.M2_COHERENCE_MARGIN == 0.10
    assert _c.M2_THROUGHPUT_RATIO == 0.90
    assert _c.REACH_NULL_MAX == 0.05
    assert _c.REACH_POS_MIN == 0.90
    assert _c.N_SEED == 3
    assert _c.RERUN_PER_ARM == 1


def test_cap_geometry_uses_frozen_mirror() -> None:
    """``M2_CAP`` / ``M2_TRANSIENT_TOL`` are USE-only views of the frozen cap."""
    # M2_CAP mirrors cognition.world_model.MAX_TOTAL_MODULATION (not a 2nd copy).
    assert _c.M2_CAP == MAX_TOTAL_MODULATION == 0.15
    assert _c.M2_TRANSIENT_TOL == 0.05  # mirrors cognition.world_model.VALUE_STEP
