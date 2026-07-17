"""Unit tests for :mod:`erre_sandbox.erre.two_phase` (pure, no I/O).

Boolean causal-wiring construction (aha!/DMN-ECN Phase 4): asserts the two-phase
knob *fires* — off = the frozen ``locomotion_delta`` shape; on + generation =
divergence; on + evaluation = inverted-sign convergence — and that its constants
are pinned and its mode partition is exhaustive. It measures no effect size /
detectability / divergence / floor: those live behind the frozen measurement line
(door② UNMET). The cycle-level *live wiring* is covered separately in
``tests/test_cognition/test_cycle_two_phase.py``.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from erre_sandbox.erre import two_phase as tp
from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
    locomotion_delta,
)
from erre_sandbox.erre.two_phase import (
    EVALUATION_MODES,
    GENERATION_MODES,
    TWO_PHASE_GAIN_P,
    TWO_PHASE_GAIN_R,
    TWO_PHASE_GAIN_T,
    TwoPhase,
    TwoPhaseKnob,
    phase_of_mode,
    two_phase_delta,
)
from erre_sandbox.schemas import ERREModeName, LocomotionState, SamplingDelta

_GAINS = {
    "gain_t": TWO_PHASE_GAIN_T,
    "gain_p": TWO_PHASE_GAIN_P,
    "gain_r": TWO_PHASE_GAIN_R,
}


# --- ablation identity (inherited from locomotion_delta) ----------------------


def test_none_loco_yields_all_zero_delta() -> None:
    assert two_phase_delta(None, TwoPhase.GENERATION, **_GAINS) == SamplingDelta()
    assert two_phase_delta(None, TwoPhase.EVALUATION, **_GAINS) == SamplingDelta()


def test_lam_zero_yields_all_zero_delta() -> None:
    loco = LocomotionState(lam=0.0)
    assert two_phase_delta(loco, TwoPhase.GENERATION, **_GAINS) == SamplingDelta()
    assert two_phase_delta(loco, TwoPhase.EVALUATION, **_GAINS) == SamplingDelta()


def test_zero_gains_yield_all_zero_delta() -> None:
    loco = LocomotionState(lam=1.0)
    delta = two_phase_delta(
        loco, TwoPhase.EVALUATION, gain_t=0.0, gain_p=0.0, gain_r=0.0
    )
    assert delta == SamplingDelta()


# --- (2) generation phase = divergence bias -----------------------------------


@pytest.mark.parametrize("lam", [0.25, 0.5, 0.75, 1.0])
def test_generation_phase_is_divergence_bias(lam: float) -> None:
    delta = two_phase_delta(LocomotionState(lam=lam), TwoPhase.GENERATION, **_GAINS)
    assert delta.temperature > 0.0
    assert delta.top_p > 0.0
    assert delta.repeat_penalty == 0.0
    # Generation phase reproduces the frozen ES-3 locomotion_delta shape exactly.
    assert delta == locomotion_delta(
        LocomotionState(lam=lam), gain_t=TWO_PHASE_GAIN_T, gain_p=TWO_PHASE_GAIN_P
    )


# --- (3) evaluation phase = convergence bias (inverted sign) ------------------


@pytest.mark.parametrize("lam", [0.25, 0.5, 0.75, 1.0])
def test_evaluation_phase_is_convergence_bias(lam: float) -> None:
    delta = two_phase_delta(LocomotionState(lam=lam), TwoPhase.EVALUATION, **_GAINS)
    assert delta.temperature < 0.0
    assert delta.top_p < 0.0
    assert delta.repeat_penalty > 0.0


def test_phases_invert_temperature_and_top_p_sign() -> None:
    loco = LocomotionState(lam=0.8)
    gen = two_phase_delta(loco, TwoPhase.GENERATION, **_GAINS)
    ev = two_phase_delta(loco, TwoPhase.EVALUATION, **_GAINS)
    assert gen.temperature == pytest.approx(-ev.temperature)
    assert gen.top_p == pytest.approx(-ev.top_p)


def test_magnitude_scales_linearly_with_lam() -> None:
    for lam in (0.2, 0.5, 1.0):
        delta = two_phase_delta(LocomotionState(lam=lam), TwoPhase.EVALUATION, **_GAINS)
        assert delta.temperature == pytest.approx(-TWO_PHASE_GAIN_T * lam)
        assert delta.top_p == pytest.approx(-TWO_PHASE_GAIN_P * lam)
        assert delta.repeat_penalty == pytest.approx(TWO_PHASE_GAIN_R * lam)


# --- (4) phase_of_mode: exhaustive partition, fail-fast (Codex MED-2/3) --------


def test_phase_of_mode_generation_modes() -> None:
    for mode in (
        ERREModeName.PERIPATETIC,
        ERREModeName.RI_CREATE,
        ERREModeName.HA_DEVIATE,
    ):
        assert phase_of_mode(mode) is TwoPhase.GENERATION


def test_phase_of_mode_evaluation_and_neutral_modes() -> None:
    # Convergent + neutral (deep_work / shallow) → evaluation (frozen decision).
    for mode in (
        ERREModeName.ZAZEN,
        ERREModeName.CHASHITSU,
        ERREModeName.SHU_KATA,
        ERREModeName.DEEP_WORK,
        ERREModeName.SHALLOW,
    ):
        assert phase_of_mode(mode) is TwoPhase.EVALUATION


def test_phase_partition_covers_every_mode_exactly_once() -> None:
    assert GENERATION_MODES.isdisjoint(EVALUATION_MODES)
    assert set(ERREModeName) == GENERATION_MODES | EVALUATION_MODES
    for mode in ERREModeName:  # every mode resolves without raising
        assert phase_of_mode(mode) in (TwoPhase.GENERATION, TwoPhase.EVALUATION)


# --- (5) pinned constants + knob hygiene (tune-to-pass 封鎖, Codex HIGH-3/LOW-2)


def test_gains_are_pinned() -> None:
    assert TWO_PHASE_GAIN_T == DEFAULT_LOCO_GAIN_T == 0.3
    assert TWO_PHASE_GAIN_P == DEFAULT_LOCO_GAIN_P == 0.1
    assert TWO_PHASE_GAIN_R == 0.1


def test_knob_is_a_marker_with_no_tunable_gains() -> None:
    # Presence-only marker: the live modulation always uses the pinned module
    # constants, so a knob carries no per-injection gain override surface (Codex
    # TASK-POST HIGH). tune-to-pass / clamp-escape via the knob is impossible.
    knob = TwoPhaseKnob()
    for attr in ("gain_t", "gain_p", "gain_r"):
        assert not hasattr(knob, attr)


def test_knob_rejects_gain_arguments() -> None:
    # The exact attack: constructing with a gain kwarg must fail (no override channel).
    with pytest.raises(TypeError):
        TwoPhaseKnob(gain_r=999.0)  # type: ignore[call-arg]


def test_full_lam_stays_within_sampling_delta_bounds() -> None:
    for phase in TwoPhase:
        delta = two_phase_delta(LocomotionState(lam=1.0), phase, **_GAINS)
        for value in (delta.temperature, delta.top_p, delta.repeat_penalty):
            assert -1.0 <= value <= 1.0


# --- (C) measurement-zero guard (holding / over-read, Codex LOW-1) ------------


def test_module_imports_no_measurement_apparatus() -> None:
    """holding: two_phase must not import the frozen evidence/measurement layer."""
    tree = ast.parse(inspect.getsource(tp))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any("evidence" in name for name in imported)


def test_public_surface_has_no_measurement_names() -> None:
    """over-read: no effect / score / floor / divergence / aha proxy in the API."""
    forbidden = ("score", "floor", "divergence", "verdict", "aha", "effect", "detect")
    for name in tp.__all__:
        low = name.lower()
        assert not any(token in low for token in forbidden), name
