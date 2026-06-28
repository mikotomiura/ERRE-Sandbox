"""Pin the M13-ES3 frozen §5 constants to the ADR table verbatim.

Every threshold was fixed **before** any verdict result was seen
(``.steering/20260629-m13-es3-adr/design-final.md`` §5, user-ratified
pre-registration commitment). This test is the forking-paths guard's regression
pin: a constant can only change by a deliberate edit that also updates this
expected table (which itself requires a superseding ADR). The verdict value is
**not** pinned here.
"""

from __future__ import annotations

from pathlib import Path

from erre_sandbox.bootstrap import _load_persona_yaml
from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_ALPHA,
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
)
from erre_sandbox.evidence.es3_locomotion import constants as _c

_PERSONAS_DIR = Path(__file__).resolve().parents[2] / "personas"


def test_ensemble_constants_verbatim() -> None:
    assert _c.B == 64
    assert _c.T == 200
    assert _c.ALPHA == 0.3


def test_gain_constants_verbatim() -> None:
    assert _c.LOCO_GAIN_T == 0.3
    assert _c.LOCO_GAIN_P == 0.1


def test_headroom_constants_verbatim() -> None:
    assert _c.TEMP_MAX == 2.0
    assert _c.HEADROOM_MIN == 0.3
    # HEADROOM_MIN is pinned equal to LOCO_GAIN_T by design (§5).
    assert _c.HEADROOM_MIN == _c.LOCO_GAIN_T


def test_validity_gate_constants_verbatim() -> None:
    assert _c.LOCO_SPREAD_MIN == 0.0025
    assert _c.MIN_CELLS == 8
    assert _c.MIN_CELL_N == 30
    assert _c.HEADROOM_VALID_FRAC == 0.5
    assert _c.MIN_WALK_SEEDS == 32


def test_verdict_threshold_constants_verbatim() -> None:
    assert _c.AMP_FLOOR == 0.02
    assert _c.CI_ALPHA == 0.10
    assert _c.N_RESAMPLES == 10000
    assert _c.ZERO_TOL == 1e-9


def test_live_defaults_pinned_equal_to_apparatus_constants() -> None:
    """The live cognition wiring reuses the apparatus scale; pin so they can't drift."""
    assert DEFAULT_LOCO_ALPHA == _c.ALPHA
    assert DEFAULT_LOCO_GAIN_T == _c.LOCO_GAIN_T
    assert DEFAULT_LOCO_GAIN_P == _c.LOCO_GAIN_P


def test_persona_roster_pinned_to_real_yaml() -> None:
    """The roster ``SamplingBase`` mirror equals the real YAML default_sampling."""
    assert [pid for pid, _ in _c.PERSONA_ROSTER] == ["kant", "nietzsche", "rikyu"]
    for persona_id, base in _c.PERSONA_ROSTER:
        spec = _load_persona_yaml(_PERSONAS_DIR, persona_id)
        assert base == spec.default_sampling, persona_id
