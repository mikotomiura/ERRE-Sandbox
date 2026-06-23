"""Pin the M13-ES1 SPDM frozen §A pre-register to the ADR table verbatim.

The SPDM pre-registration freeze (``.steering/20260624-m13-es1-spdm/``, Codex
review REVISE → all 5 HIGH reflected before freeze) fixed every Gate 1 / Gate 2
threshold **before** any probe result was seen. This test is the forking-paths
guard's regression pin: a constant can only change by a deliberate edit that also
updates this expected table (which itself requires a superseding ADR). The verdict
thresholds are asserted to track the III-a ``live_carry`` frozen mirror (USE-only),
not independently tuned literals.
"""

from __future__ import annotations

from erre_sandbox.evidence.live_carry import constants as _iiia
from erre_sandbox.evidence.spdm import constants as _c


def test_frozen_estimand_geometry_verbatim() -> None:
    """A1 estimand geometry equals the pre-registered numbers."""
    assert _c.Q_BATTERY_MIN == 12
    assert _c.K_RETRIEVE == 8
    assert _c.M_MEMORIES == 20
    assert _c.N_SEED == 8
    assert _c.LANDSCAPE_KEY == "canonical_content_id"  # Codex HIGH-2
    assert _c.MARK_RECALLED_DURING_PROBE is False  # Codex HIGH-3


def test_frozen_verdict_thresholds_verbatim() -> None:
    """A3 verdict thresholds equal the pre-registered numbers."""
    assert _c.R_MIN == 2.0
    assert _c.DEGENERATE_NULL_FLOOR == 0.10
    assert _c.NULL_NOISE_FACTOR == 1.5
    assert _c.CI_ALPHA == 0.10
    assert _c.N_RESAMPLES == 2000
    assert _c.MIN_VALID_SEEDS == 5
    # Codex HIGH-1 / HIGH-4 additions:
    assert _c.VERDICT_NULL_KEYS == (
        "path_label_permutation",
        "same_terminal_same_query_w0",
    )
    assert _c.POSITIVE_CONTROL_RATIO_MIN == 2.0
    assert _c.NO_SPURIOUS_TOL_ABS == 0.05
    assert _c.SPREAD_STAT == "iqr"


def test_frozen_scorer_knobs_verbatim() -> None:
    """B3 spatial-term apparatus knobs equal the pre-registered numbers."""
    assert _c.SPATIAL_GAMMA == 0.5
    assert _c.SPATIAL_COORD_NORMALIZED is True
    assert _c.SPATIAL_COORD_REF == 1.0


def test_verdict_thresholds_inherit_iiia_freeze_use_only() -> None:
    """``R_MIN`` / ``DEGENERATE_NULL_FLOOR`` are USE-only views of the III-a freeze.

    The SPDM Gate-2 statistic is a Jaccard-distance separation, structurally the
    same readout the III-a cross-arm scorer gates; SPDM does not fork a second
    tunable copy of the scale-free ratio gate / practical-effect floor.
    """
    assert _c.R_MIN is _iiia.R_MIN
    assert _c.DEGENERATE_NULL_FLOOR is _iiia.DEGENERATE_NULL_FLOOR
    # ② positive control tracks the same inherited ratio.
    assert _c.POSITIVE_CONTROL_RATIO_MIN == _iiia.R_MIN
    # The noise factor tracks the III-a ON-noise factor value (local literal).
    assert _c.NULL_NOISE_FACTOR == _iiia.ON_NOISE_FACTOR


def test_excludes_signal_null_from_verdict_denominator() -> None:
    """Codex HIGH-1: ② (the signal) must not be a verdict-null key."""
    assert "same_content_different_location" not in _c.VERDICT_NULL_KEYS
    assert "same_location_different_content" not in _c.VERDICT_NULL_KEYS
    assert len(_c.VERDICT_NULL_KEYS) == 2
