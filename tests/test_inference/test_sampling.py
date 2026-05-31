"""Unit tests for :mod:`erre_sandbox.inference.sampling` (pure, no I/O)."""

from __future__ import annotations

import pytest

from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.schemas import SamplingBase, SamplingDelta


def _base(**overrides: float) -> SamplingBase:
    defaults = {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.0}
    defaults.update(overrides)
    return SamplingBase(**defaults)


def _delta(**overrides: float) -> SamplingDelta:
    defaults = {"temperature": 0.0, "top_p": 0.0, "repeat_penalty": 0.0}
    defaults.update(overrides)
    return SamplingDelta(**defaults)


def test_compose_applies_additive_delta() -> None:
    resolved = compose_sampling(
        _base(temperature=0.6, top_p=0.85, repeat_penalty=1.1),
        _delta(temperature=0.3, top_p=0.05, repeat_penalty=-0.1),
    )
    assert isinstance(resolved, ResolvedSampling)
    assert resolved.temperature == pytest.approx(0.9)
    assert resolved.top_p == pytest.approx(0.9)
    assert resolved.repeat_penalty == pytest.approx(1.0)


def test_compose_clamps_temperature_upper() -> None:
    resolved = compose_sampling(_base(temperature=1.5), _delta(temperature=1.0))
    assert resolved.temperature == pytest.approx(2.0)


def test_compose_clamps_temperature_lower() -> None:
    resolved = compose_sampling(_base(temperature=0.0), _delta(temperature=-0.5))
    assert resolved.temperature == pytest.approx(0.01)


def test_compose_clamps_top_p_upper() -> None:
    resolved = compose_sampling(_base(top_p=0.95), _delta(top_p=0.1))
    assert resolved.top_p == pytest.approx(1.0)


def test_compose_clamps_top_p_lower() -> None:
    resolved = compose_sampling(_base(top_p=0.05), _delta(top_p=-0.5))
    assert resolved.top_p == pytest.approx(0.01)


def test_compose_clamps_repeat_penalty_upper() -> None:
    resolved = compose_sampling(_base(repeat_penalty=1.9), _delta(repeat_penalty=0.2))
    assert resolved.repeat_penalty == pytest.approx(2.0)


def test_compose_clamps_repeat_penalty_lower() -> None:
    resolved = compose_sampling(_base(repeat_penalty=0.6), _delta(repeat_penalty=-0.5))
    assert resolved.repeat_penalty == pytest.approx(0.5)


def test_compose_peripatetic_greater_than_zazen_temperature() -> None:
    """persona-erre §ルール 2 の peripatetic (+0.3) > zazen (-0.3) monotonicity."""
    base = _base(temperature=0.7)
    peripatetic = compose_sampling(base, _delta(temperature=0.3))
    zazen = compose_sampling(base, _delta(temperature=-0.3))
    assert peripatetic.temperature > zazen.temperature
    assert peripatetic.temperature == pytest.approx(1.0)
    assert zazen.temperature == pytest.approx(0.4)


def test_resolved_sampling_is_frozen() -> None:
    resolved = compose_sampling(_base(), _delta())
    with pytest.raises(ValueError, match="frozen"):
        resolved.temperature = 0.1  # type: ignore[misc]
