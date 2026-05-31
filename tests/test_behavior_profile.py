"""Tests for ``PersonaSpec.behavior_profile`` (M7ζ-3).

Validates the new ``BehaviorProfile`` sub-document — defaults preserve
backward compatibility for older yamls without a ``behavior_profile:``
block, range clamps reject out-of-bounds values, ``extra="forbid"``
rejects unknown fields, and the three real persona yamls round-trip
through ``PersonaSpec`` with the values declared for live divergence.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from erre_sandbox.schemas import BehaviorProfile, PersonaSpec

REPO_ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = REPO_ROOT / "personas"


def _load_yaml(name: str) -> PersonaSpec:
    with (PERSONAS_DIR / f"{name}.yaml").open(encoding="utf-8") as f:
        return PersonaSpec.model_validate(yaml.safe_load(f))


def test_default_factory_backward_compat(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    spec = make_persona_spec()  # no behavior_profile override
    bp = spec.behavior_profile
    assert bp.movement_speed_factor == 1.0
    assert bp.cognition_period_s == 10.0
    assert bp.dwell_time_s == 0.0
    assert bp.separation_radius_m == 1.5


def test_movement_speed_factor_clamped() -> None:
    with pytest.raises(ValidationError):
        BehaviorProfile(movement_speed_factor=3.0)
    with pytest.raises(ValidationError):
        BehaviorProfile(movement_speed_factor=0.2)


def test_cognition_period_s_clamped() -> None:
    with pytest.raises(ValidationError):
        BehaviorProfile(cognition_period_s=2.0)
    with pytest.raises(ValidationError):
        BehaviorProfile(cognition_period_s=121.0)


def test_dwell_time_s_clamped() -> None:
    with pytest.raises(ValidationError):
        BehaviorProfile(dwell_time_s=-1.0)
    with pytest.raises(ValidationError):
        BehaviorProfile(dwell_time_s=601.0)


def test_separation_radius_m_clamped() -> None:
    with pytest.raises(ValidationError):
        BehaviorProfile(separation_radius_m=-0.1)
    with pytest.raises(ValidationError):
        BehaviorProfile(separation_radius_m=5.1)


def test_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        BehaviorProfile.model_validate({"unknown_field": 1})


def test_kant_yaml_round_trip() -> None:
    bp = _load_yaml("kant").behavior_profile
    assert bp.movement_speed_factor == pytest.approx(0.85)
    assert bp.cognition_period_s == pytest.approx(14.0)
    assert bp.dwell_time_s == pytest.approx(30.0)
    assert bp.separation_radius_m == pytest.approx(1.5)


def test_nietzsche_yaml_round_trip() -> None:
    bp = _load_yaml("nietzsche").behavior_profile
    assert bp.movement_speed_factor == pytest.approx(1.25)
    assert bp.cognition_period_s == pytest.approx(7.0)
    assert bp.dwell_time_s == pytest.approx(5.0)
    assert bp.separation_radius_m == pytest.approx(1.5)


def test_rikyu_yaml_round_trip() -> None:
    bp = _load_yaml("rikyu").behavior_profile
    assert bp.movement_speed_factor == pytest.approx(0.70)
    assert bp.cognition_period_s == pytest.approx(18.0)
    assert bp.dwell_time_s == pytest.approx(90.0)
    assert bp.separation_radius_m == pytest.approx(1.2)


def test_three_personas_have_distinct_movement_speed_factors() -> None:
    factors = {
        name: _load_yaml(name).behavior_profile.movement_speed_factor
        for name in ("kant", "nietzsche", "rikyu")
    }
    assert len(set(factors.values())) == 3
