"""Unit tests for :mod:`erre_sandbox.inference.sampling` (pure, no I/O)."""

from __future__ import annotations

import pytest

from erre_sandbox.erre import SAMPLING_DELTA_BY_MODE
from erre_sandbox.erre.locomotion_sampling import locomotion_delta
from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.schemas import LocomotionState, SamplingBase, SamplingDelta

# The three M13-ES3 roster personas' real default_sampling (personas/*.yaml).
# Used to pin the bit-identical backward-compatibility invariant over the exact
# (base, mode_delta) value space every compose_sampling call path feeds.
_ROSTER_BASES = {
    "kant": SamplingBase(temperature=0.60, top_p=0.85, repeat_penalty=1.12),
    "nietzsche": SamplingBase(temperature=0.85, top_p=0.80, repeat_penalty=0.95),
    "rikyu": SamplingBase(temperature=0.45, top_p=0.78, repeat_penalty=1.25),
}


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


# --- M13-ES3 bit-identical backward-compatibility invariant (Codex M4 / L2) ---
#
# Adding the third ``loco_delta`` argument must not perturb a single existing
# call path. Every live caller invokes ``compose_sampling(base, mode_delta)``
# (two args): cognition/cycle.py, inference/{ollama,sglang}_adapter.py,
# cognition/reflection.py, integration/dialog_turn.py, cli/eval_run_golden.py.
# All feed the same value space — a persona ``default_sampling`` base and one of
# the eight ``SAMPLING_DELTA_BY_MODE`` mode deltas (plus the bare
# ``SamplingDelta()`` warmup). These tests pin that the two-arg form, the
# explicit ``None`` form, and the explicit all-zero ``SamplingDelta()`` form are
# **field-for-field identical** across that exact space, so the call sites need
# no change and behave bit-identically.


@pytest.mark.parametrize("persona", sorted(_ROSTER_BASES))
@pytest.mark.parametrize("mode", sorted(SAMPLING_DELTA_BY_MODE, key=lambda m: m.value))
def test_loco_default_is_bit_identical_to_two_arg(persona: str, mode: object) -> None:
    """``compose(base, mode)`` == ``compose(base, mode, None)`` == ``…, zero``.

    Over the real roster bases × all eight ERRE mode deltas (the exact value
    space every call path feeds), the defaulted / explicit-None / explicit-zero
    loco argument all reproduce the pre-ES3 two-argument result exactly.
    """
    base = _ROSTER_BASES[persona]
    mode_delta = SAMPLING_DELTA_BY_MODE[mode]  # type: ignore[index]

    two_arg = compose_sampling(base, mode_delta)
    explicit_none = compose_sampling(base, mode_delta, None)
    explicit_zero = compose_sampling(base, mode_delta, SamplingDelta())

    assert explicit_none == two_arg
    assert explicit_zero == two_arg


def test_loco_delta_is_third_additive_term() -> None:
    """A non-zero ``loco_delta`` adds on top of base + mode, then clamps."""
    base = _base(temperature=0.6, top_p=0.85, repeat_penalty=1.1)
    mode_delta = _delta(temperature=0.1, top_p=0.0, repeat_penalty=-0.1)
    loco = _delta(temperature=0.3, top_p=0.1, repeat_penalty=0.0)

    resolved = compose_sampling(base, mode_delta, loco)
    assert resolved.temperature == pytest.approx(0.6 + 0.1 + 0.3)
    assert resolved.top_p == pytest.approx(0.85 + 0.0 + 0.1)
    assert resolved.repeat_penalty == pytest.approx(1.1 - 0.1 + 0.0)


def test_loco_delta_clamps_after_three_term_sum() -> None:
    """The clamp invariant still binds the full three-term sum."""
    resolved = compose_sampling(
        _base(temperature=1.8),
        _delta(temperature=0.3),
        _delta(temperature=0.5),
    )
    assert resolved.temperature == pytest.approx(2.0)


# --- locomotion_delta ablation identity (ADR §1.2): None path == gain=0 path ---


def test_loco_none_path_bit_identical_to_lam_zero_and_gain_zero() -> None:
    """``loco_delta=None`` ≡ a ``locomotion_delta`` of None / λ=0 / gain=0.

    The ablation is expressed as *bit equality between the* ``loco_delta=None``
    *path and a* ``gain=0`` *path* (Codex L2), not "difference from a full-gain
    run". All four compositions must be field-for-field identical.
    """
    base = _ROSTER_BASES["kant"]
    mode_delta = SAMPLING_DELTA_BY_MODE[next(iter(SAMPLING_DELTA_BY_MODE))]

    none_path = compose_sampling(base, mode_delta, None)
    loco_none = compose_sampling(
        base, mode_delta, locomotion_delta(None, gain_t=0.3, gain_p=0.1)
    )
    lam_zero = compose_sampling(
        base,
        mode_delta,
        locomotion_delta(LocomotionState(lam=0.0), gain_t=0.3, gain_p=0.1),
    )
    gain_zero = compose_sampling(
        base,
        mode_delta,
        locomotion_delta(LocomotionState(lam=1.0), gain_t=0.0, gain_p=0.0),
    )
    assert loco_none == none_path
    assert lam_zero == none_path
    assert gain_zero == none_path
