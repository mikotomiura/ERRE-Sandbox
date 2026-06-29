"""Unit tests for :mod:`erre_sandbox.erre.locomotion_sampling` (pure, no I/O)."""

from __future__ import annotations

import pytest

from erre_sandbox.erre.locomotion_sampling import advance_lambda, locomotion_delta
from erre_sandbox.schemas import LocomotionState, SamplingDelta

_ALPHA = 0.3  # ES-3 frozen EMA α

_GAIN_T = 0.3  # ES-3 frozen LOCO_GAIN_T
_GAIN_P = 0.1  # ES-3 frozen LOCO_GAIN_P


def test_none_yields_all_zero_delta() -> None:
    assert locomotion_delta(None, gain_t=_GAIN_T, gain_p=_GAIN_P) == SamplingDelta()


def test_lam_zero_yields_all_zero_delta() -> None:
    delta = locomotion_delta(LocomotionState(lam=0.0), gain_t=_GAIN_T, gain_p=_GAIN_P)
    assert delta == SamplingDelta()


def test_zero_gain_yields_all_zero_delta() -> None:
    delta = locomotion_delta(LocomotionState(lam=1.0), gain_t=0.0, gain_p=0.0)
    assert delta == SamplingDelta()


@pytest.mark.parametrize("lam", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_temperature_and_top_p_scale_linearly_with_lam(lam: float) -> None:
    delta = locomotion_delta(LocomotionState(lam=lam), gain_t=_GAIN_T, gain_p=_GAIN_P)
    assert delta.temperature == pytest.approx(_GAIN_T * lam)
    assert delta.top_p == pytest.approx(_GAIN_P * lam)


def test_repeat_penalty_always_zero_divergence_specific() -> None:
    """Convergence parameter held at 0 for every λ (Oppezzo 2014, ADR §1.2)."""
    for lam in (0.0, 0.3, 0.6, 1.0):
        delta = locomotion_delta(
            LocomotionState(lam=lam), gain_t=_GAIN_T, gain_p=_GAIN_P
        )
        assert delta.repeat_penalty == 0.0


def test_full_lam_stays_within_sampling_delta_bounds() -> None:
    """λ=1 with the frozen gains stays inside SamplingDelta's [-1, 1] fields."""
    delta = locomotion_delta(LocomotionState(lam=1.0), gain_t=_GAIN_T, gain_p=_GAIN_P)
    assert delta.temperature == pytest.approx(0.3)
    assert delta.top_p == pytest.approx(0.1)


def test_gait_label_does_not_enter_sampling() -> None:
    """The optional gait descriptor never affects the delta."""
    walk = locomotion_delta(
        LocomotionState(lam=0.5, gait="walk"), gain_t=_GAIN_T, gain_p=_GAIN_P
    )
    plain = locomotion_delta(LocomotionState(lam=0.5), gain_t=_GAIN_T, gain_p=_GAIN_P)
    assert walk == plain


# --- advance_lambda EMA (ADR §1.1) --------------------------------------------


def test_advance_lambda_rises_on_move_decays_on_stay() -> None:
    assert advance_lambda(0.0, 1, _ALPHA) == pytest.approx(0.3)  # (1-α)·0 + α·1
    assert advance_lambda(1.0, 0, _ALPHA) == pytest.approx(0.7)  # (1-α)·1 + α·0


def test_advance_lambda_stays_in_unit_interval() -> None:
    """For prev∈[0,1], move∈{0,1}, α∈[0,1] the result stays in [0,1]."""
    for prev in (0.0, 0.5, 1.0):
        for move in (0, 1):
            lam = advance_lambda(prev, move, _ALPHA)
            assert 0.0 <= lam <= 1.0
            # The result must always be a valid LocomotionState λ.
            assert LocomotionState(lam=lam).lam == pytest.approx(lam)


def test_advance_lambda_walking_streak_converges_upward() -> None:
    """Repeated moves push λ monotonically toward 1."""
    lam = 0.0
    prev = -1.0
    for _ in range(20):
        lam = advance_lambda(lam, 1, _ALPHA)
        assert lam > prev
        prev = lam
    assert lam == pytest.approx(1.0, abs=1e-2)
