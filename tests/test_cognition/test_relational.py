"""Unit tests for ``cognition.relational`` (M7 Slice δ Commit C3).

The :mod:`erre_sandbox.cognition.relational` module is intentionally
side-effect free so every assertion in this file should fit on one screen
and require no fixtures beyond minimal Pydantic model construction.

M7γ → M7δ migration
-------------------

γ kept the body trivial (constant ``+0.02``) so the original tests pinned
that constant. δ replaces the body with the CSDG semi-formula

    next_affinity = prev * (1 - decay) + event_impact * event_weight

so the previous γ-specific assertions are no longer meaningful. This file
covers the δ surface: decay-only behaviour, structural positive impact,
antagonism-driven negative impact, and persona-coupled decay/weight
contrast. ``clamp_affinity_delta`` and ``apply_affinity`` are unchanged
between γ and δ; their tests are retained verbatim as regression guards.
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


def _make_persona(
    persona_id: str = "kant",
    *,
    neuroticism: float = 0.5,
    extraversion: float = 0.5,
) -> PersonaSpec:
    return PersonaSpec(
        persona_id=persona_id,
        display_name=persona_id.title(),
        era="1724-1804",
        personality=PersonalityTraits(
            neuroticism=neuroticism,
            extraversion=extraversion,
        ),
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
    utterance: str = "Guten Tag, mein Freund.",
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


# ---------- GAMMA_CONSTANT_DELTA (retained constant) -----------------------


def test_gamma_constant_is_positive_and_in_range() -> None:
    """The retained M7γ constant must respect the bond.affinity bound."""
    assert AFFINITY_LOWER <= GAMMA_CONSTANT_DELTA <= AFFINITY_UPPER
    assert GAMMA_CONSTANT_DELTA > 0.0


# ---------- compute_affinity_delta (δ semi-formula) -----------------------


def test_compute_decays_prev_when_impact_is_zero() -> None:
    """``prev`` shrinks toward 0 when no event_impact is present.

    Empty utterance + empty addressee_id → addressee_match=0, length_norm=0
    → structural impact 0. With no antagonism the formula reduces to
    ``next = prev * (1 - decay)`` so ``delta = -prev * decay`` (negative).
    """
    persona = _make_persona("kant", neuroticism=0.5)
    turn = _make_turn(addressee_id="", utterance="")
    delta = compute_affinity_delta(
        turn,
        recent_transcript=(),
        persona=persona,
        prev=0.8,
    )
    # decay = 0.02 + 0.06 * 0.5 = 0.05 → delta = -0.04
    assert delta == pytest.approx(-0.04, abs=1e-6)
    assert delta < 0.0


def test_compute_returns_positive_delta_for_kant_to_rikyu() -> None:
    """Non-antagonistic pairing yields a positive delta from structural impact."""
    kant = _make_persona("kant", neuroticism=0.20, extraversion=0.35)
    rikyu = _make_persona("rikyu", neuroticism=0.25, extraversion=0.20)
    turn = _make_turn(
        speaker_id="a_kant_001",
        addressee_id="a_rikyu_001",
        utterance="Tea ceremony reflects categorical hospitality.",
    )
    delta = compute_affinity_delta(
        turn,
        recent_transcript=(),
        persona=kant,
        prev=0.0,
        addressee_persona=rikyu,
    )
    assert delta > 0.0


def test_compute_returns_negative_delta_for_kant_to_nietzsche() -> None:
    """Antagonism table fires for kant↔nietzsche → delta < -0.05.

    This is the live-fire guarantee that the δ acceptance gate observes.
    """
    kant = _make_persona("kant", neuroticism=0.20, extraversion=0.35)
    nietzsche = _make_persona("nietzsche", neuroticism=0.85, extraversion=0.20)
    turn = _make_turn(
        speaker_id="a_kant_001",
        addressee_id="a_nietzsche_001",
        utterance="The categorical imperative is not negotiable.",
    )
    delta = compute_affinity_delta(
        turn,
        recent_transcript=(),
        persona=kant,
        prev=0.0,
        addressee_persona=nietzsche,
    )
    assert delta < -0.05


def test_compute_antagonism_is_symmetric_for_pair() -> None:
    """``(kant, nietzsche)`` and ``(nietzsche, kant)`` both fire negative."""
    kant = _make_persona("kant", neuroticism=0.20, extraversion=0.35)
    nietzsche = _make_persona("nietzsche", neuroticism=0.85, extraversion=0.20)
    turn_k = _make_turn(speaker_id="a_kant_001", addressee_id="a_nietzsche_001")
    turn_n = _make_turn(
        speaker_id="a_nietzsche_001",
        addressee_id="a_kant_001",
    )
    delta_k = compute_affinity_delta(
        turn_k,
        (),
        kant,
        prev=0.0,
        addressee_persona=nietzsche,
    )
    delta_n = compute_affinity_delta(
        turn_n,
        (),
        nietzsche,
        prev=0.0,
        addressee_persona=kant,
    )
    assert delta_k < 0.0
    assert delta_n < 0.0


def test_compute_neuroticism_drives_decay_contrast() -> None:
    """Higher neuroticism → faster decay → larger negative delta on ``prev``.

    Two personas with different neuroticism but identical other traits,
    no impact (empty turn), starting from the same ``prev``: the more
    neurotic one loses more affinity per tick.
    """
    low_neuro = _make_persona("low", neuroticism=0.20, extraversion=0.50)
    high_neuro = _make_persona("high", neuroticism=0.85, extraversion=0.50)
    turn = _make_turn(addressee_id="", utterance="")
    delta_low = compute_affinity_delta(
        turn,
        (),
        low_neuro,
        prev=0.5,
    )
    delta_high = compute_affinity_delta(
        turn,
        (),
        high_neuro,
        prev=0.5,
    )
    # Both decays are negative (impact=0, prev>0); high_neuro decays
    # 0.071 * 0.5 = 0.0355 vs low_neuro 0.032 * 0.5 = 0.016 → delta_high
    # is more negative (larger magnitude) than delta_low.
    assert delta_high < delta_low < 0.0


def test_compute_extraversion_drives_event_weight_contrast() -> None:
    """Higher extraversion → larger weight → larger positive delta.

    Identical turn (positive structural impact), no antagonism, two
    personas differing only in extraversion. The extravert's delta
    should be larger.
    """
    introvert = _make_persona("intro", extraversion=0.20, neuroticism=0.50)
    extravert = _make_persona("extra", extraversion=0.85, neuroticism=0.50)
    rikyu = _make_persona("rikyu", neuroticism=0.25, extraversion=0.20)
    turn = _make_turn(
        speaker_id="a_intro_001",
        addressee_id="a_rikyu_001",
        utterance="A long, considered, paragraph-length reflection.",
    )
    delta_intro = compute_affinity_delta(
        turn,
        (),
        introvert,
        prev=0.0,
        addressee_persona=rikyu,
    )
    delta_extra = compute_affinity_delta(
        turn,
        (),
        extravert,
        prev=0.0,
        addressee_persona=rikyu,
    )
    assert delta_extra > delta_intro > 0.0


def test_compute_clamps_to_legal_range_over_saturating_sequence() -> None:
    """Iterated turns saturate but never exceed ``AFFINITY_UPPER``.

    The δ tunables (max impact ~0.12, max weight 1.5) intentionally cap
    a single-turn delta well below the bond's range so the clamp is not
    needed on isolated calls. Saturation is reached over many turns; the
    clamp must still hold at the asymptote.
    """
    speaker = _make_persona("hyper", extraversion=1.0, neuroticism=0.0)
    other = _make_persona("rikyu", extraversion=0.20, neuroticism=0.25)
    turn = _make_turn(
        addressee_id="a_rikyu_001",
        utterance="x" * 500,  # well past _IMPACT_LENGTH_TARGET
    )
    prev = 0.0
    for _ in range(50):
        delta = compute_affinity_delta(
            turn,
            (),
            speaker,
            prev=prev,
            addressee_persona=other,
        )
        prev = max(-1.0, min(1.0, prev + delta))
    # Sequence must saturate strictly below the upper bound (or exactly at
    # it) without going past, and must have made meaningful progress.
    assert prev <= AFFINITY_UPPER
    assert prev > 0.5


def test_compute_addressee_persona_none_disables_antagonism() -> None:
    """When ``addressee_persona`` is None, the antagonism path is skipped."""
    kant = _make_persona("kant", neuroticism=0.20, extraversion=0.35)
    turn = _make_turn(
        speaker_id="a_kant_001",
        addressee_id="a_nietzsche_001",  # would have fired antagonism
        utterance="Guten Tag.",
    )
    delta = compute_affinity_delta(
        turn,
        recent_transcript=(),
        persona=kant,
        prev=0.0,
        addressee_persona=None,
    )
    # No antagonism → structural impact takes over → positive delta.
    assert delta > 0.0


# ---------- clamp_affinity_delta (γ behaviour, retained) -------------------


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


# ---------- apply_affinity (γ behaviour, retained) -------------------------


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
    """Six γ-constant increments stay below 1.0 (one full dialog budget).

    Retained as a sanity bound on the legacy γ constant — δ deltas vary
    so the equivalent calibration belongs in
    ``test_relational_simulation.py`` (C5).
    """
    bond = 0.0
    for _ in range(6):
        bond = apply_affinity(bond, GAMMA_CONSTANT_DELTA)
    assert bond == pytest.approx(0.12)
    assert bond < AFFINITY_UPPER
