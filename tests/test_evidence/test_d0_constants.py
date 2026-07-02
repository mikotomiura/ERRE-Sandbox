"""Pin the M13-SUB1 D0 structural-track frozen constants verbatim.

Two provenance classes (module docstring of
``erre_sandbox.evidence.d0_substrate.constants``):

* inherited constants — pinned `is`/value-equal to their source module
  (forking-paths guard, mirrors ``test_es1_spdm_constants.py`` /
  ``test_es3_constants.py``);
* the four defer constants this Plan-mode session froze by principle
  (``.steering/20260702-m13-sub1-d0-structural/decisions.md`` DA-D0S-1) —
  pinned to their literal value here.

The verdict value is never pinned (circular re-baking guard).
"""

from __future__ import annotations

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.es3_locomotion import constants as _es3
from erre_sandbox.evidence.spdm import constants as _spdm


def test_inherited_from_spdm_is_identity() -> None:
    assert _c.LANDSCAPE_JACCARD_FLOOR is _spdm.DEGENERATE_NULL_FLOOR
    assert _c.R_MIN is _spdm.R_MIN
    assert _c.NULL_NOISE_FACTOR is _spdm.NULL_NOISE_FACTOR
    assert _c.SPATIAL_GAMMA is _spdm.SPATIAL_GAMMA
    assert _c.SPATIAL_COORD_REF is _spdm.SPATIAL_COORD_REF
    assert _c.K_RETRIEVE is _spdm.K_RETRIEVE
    assert _c.M_MEMORIES is _spdm.M_MEMORIES
    assert _c.Q_BATTERY_MIN is _spdm.Q_BATTERY_MIN


def test_inherited_from_es3_is_identity() -> None:
    assert _c.CLOSURE_AMP_FLOOR is _es3.AMP_FLOOR
    assert _c.ZERO_TOL is _es3.ZERO_TOL
    assert _c.CI_ALPHA is _es3.CI_ALPHA
    assert _c.N_RESAMPLES is _es3.N_RESAMPLES
    assert _c.B is _es3.B
    assert _c.MIN_VALID_SEEDS is _es3.MIN_WALK_SEEDS


def test_residual_floor_value_equal_but_separate_constant() -> None:
    """Codex HIGH-1: value-equal to LANDSCAPE_JACCARD_FLOOR but its own name."""
    assert _c.RESIDUAL_JACCARD_FLOOR == _c.LANDSCAPE_JACCARD_FLOOR
    assert _c.RESIDUAL_JACCARD_FLOOR == 0.10


def test_structural_ready_threshold_is_r1() -> None:
    assert _c.STRUCTURAL_READY_MIN_RUNG == 1


def test_defer_constants_frozen_by_principle_da_d0s_1() -> None:
    """The four ADR-deferred R2 constants, frozen by principle (DA-D0S-1)."""
    assert _c.CONE_APERTURE_DEG == 120.0
    assert _c.CONE_RANGE_M == _c.WORLD_SIZE_M / 3.0
    assert _c.PROP_FIXTURE_MIN == 2
    assert _c.MIN_PROP_ZONES == 2


def test_verbatim_numeric_table() -> None:
    assert _c.LANDSCAPE_JACCARD_FLOOR == 0.10
    assert _c.CLOSURE_AMP_FLOOR == 0.02
    assert _c.R_MIN == 2.0
    assert _c.ZERO_TOL == 1e-9
    assert _c.CI_ALPHA == 0.10
    assert _c.N_RESAMPLES == 10000
    assert _c.B == 64
    assert _c.MIN_VALID_SEEDS == 32
    assert _c.NULL_NOISE_FACTOR == 1.5
    assert _c.M_MEMORIES == 20
    assert _c.AFFORDANCE_RADIUS_M == 2.0


def test_current_zone_props_fixture_fails_prop_gate() -> None:
    """Honest default prediction (DA-D0S-1): the MVP fixture does NOT clear
    R2's prop-fixture-minimum gate. This test documents the *fixture*, not
    the ladder's gating logic — it must never be "fixed" by adding props.
    """
    qualifying = [
        zone
        for zone, props in _c.ZONE_PROPS.items()
        if len(props) >= _c.PROP_FIXTURE_MIN
    ]
    assert len(qualifying) < _c.MIN_PROP_ZONES
