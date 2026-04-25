"""Unit tests for ``cognition.relational`` (M7 Slice γ Commit 2).

The :mod:`erre_sandbox.cognition.relational` module is intentionally
side-effect free so every assertion in this file should fit on one screen
and require no fixtures beyond minimal Pydantic model construction.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.relational import (
    AFFINITY_LOWER,
    AFFINITY_UPPER,
    GAMMA_CONSTANT_DELTA,
    apply_affinity,
    clamp_affinity_delta,
    compute_affinity_delta,
)
from erre_sandbox.schemas import (
    CognitiveHabit,
    DialogTurnMsg,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    Zone,
)


def _make_persona(persona_id: str = "kant") -> PersonaSpec:
    return PersonaSpec(
        persona_id=persona_id,
        display_name=persona_id.title(),
        era="1724-1804",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="15:30 walk",
                source="kuehn2001",
                flag=HabitFlag.FACT,
                mechanism="DMN",
            ),
        ],
        preferred_zones=[Zone.PERIPATOS],
    )


def _make_turn(
    *,
    dialog_id: str = "d1",
    speaker_id: str = "a_kant_001",
    addressee_id: str = "a_nietzsche_001",
    utterance: str = "Guten Tag.",
    turn_index: int = 0,
    tick: int = 1,
) -> DialogTurnMsg:
    return DialogTurnMsg(
        tick=tick,
        dialog_id=dialog_id,
        speaker_id=speaker_id,
        addressee_id=addressee_id,
        utterance=utterance,
        turn_index=turn_index,
    )


# ---------- compute_affinity_delta ------------------------------------------


def test_gamma_constant_is_positive_and_in_range() -> None:
    """The MVP constant must respect the ``RelationshipBond.affinity`` bound."""
    assert AFFINITY_LOWER <= GAMMA_CONSTANT_DELTA <= AFFINITY_UPPER
    assert GAMMA_CONSTANT_DELTA > 0.0


def test_compute_returns_constant_for_first_turn() -> None:
    """An initial turn with no transcript still yields the γ constant."""
    persona = _make_persona()
    turn = _make_turn()
    delta = compute_affinity_delta(turn, recent_transcript=(), persona=persona)
    assert delta == pytest.approx(GAMMA_CONSTANT_DELTA)


def test_compute_is_independent_of_transcript_size_in_gamma() -> None:
    """γ ignores the transcript: the same delta is returned regardless of length."""
    persona = _make_persona()
    turn = _make_turn(turn_index=5, tick=10)
    short_transcript = (_make_turn(turn_index=0),)
    long_transcript = tuple(_make_turn(turn_index=i) for i in range(20))
    short_delta = compute_affinity_delta(
        turn,
        recent_transcript=short_transcript,
        persona=persona,
    )
    long_delta = compute_affinity_delta(
        turn,
        recent_transcript=long_transcript,
        persona=persona,
    )
    assert short_delta == long_delta == pytest.approx(GAMMA_CONSTANT_DELTA)


def test_compute_is_independent_of_persona_in_gamma() -> None:
    """γ ignores ``persona`` — δ will revisit this."""
    turn = _make_turn()
    kant_delta = compute_affinity_delta(turn, (), _make_persona("kant"))
    rikyu_delta = compute_affinity_delta(turn, (), _make_persona("rikyu"))
    assert kant_delta == rikyu_delta == pytest.approx(GAMMA_CONSTANT_DELTA)


# ---------- clamp_affinity_delta --------------------------------------------


def test_clamp_at_upper_bound() -> None:
    assert clamp_affinity_delta(2.5) == AFFINITY_UPPER
    assert clamp_affinity_delta(AFFINITY_UPPER) == AFFINITY_UPPER


def test_clamp_at_lower_bound() -> None:
    assert clamp_affinity_delta(-3.0) == AFFINITY_LOWER
    assert clamp_affinity_delta(AFFINITY_LOWER) == AFFINITY_LOWER


@pytest.mark.parametrize(
    "value",
    [-0.5, -GAMMA_CONSTANT_DELTA, 0.0, GAMMA_CONSTANT_DELTA, 0.5],
)
def test_clamp_within_range_is_identity(value: float) -> None:
    assert clamp_affinity_delta(value) == pytest.approx(value)


# ---------- apply_affinity --------------------------------------------------


def test_apply_affinity_sums_and_clamps_high() -> None:
    """``current + delta`` exceeding ``+1.0`` snaps to the upper bound."""
    assert apply_affinity(0.95, 0.10) == AFFINITY_UPPER


def test_apply_affinity_sums_and_clamps_low() -> None:
    """``current + delta`` below ``-1.0`` snaps to the lower bound."""
    assert apply_affinity(-0.95, -0.10) == AFFINITY_LOWER


def test_apply_affinity_sums_within_range() -> None:
    """Values that stay within ``[-1.0, 1.0]`` add cleanly."""
    assert apply_affinity(0.10, 0.02) == pytest.approx(0.12)
    assert apply_affinity(-0.10, 0.02) == pytest.approx(-0.08)


def test_apply_affinity_six_steps_match_dialog_budget() -> None:
    """Six γ-constant increments stay below 1.0 (one full dialog budget)."""
    bond = 0.0
    for _ in range(6):
        bond = apply_affinity(bond, GAMMA_CONSTANT_DELTA)
    assert bond == pytest.approx(0.12)
    assert bond < AFFINITY_UPPER
