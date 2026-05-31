"""Calibration tests for the M7δ semi-formula saturation regime.

The δ promotion thresholds (``BELIEF_THRESHOLD = 0.45`` /
``BELIEF_MIN_INTERACTIONS = 6``) were picked from a back-of-envelope
recurrence simulation: iterate ``next = prev*(1-decay) + impact*weight``
for the 3 production trait pairs (kant↔nietzsche / kant↔rikyu /
nietzsche↔rikyu), confirm that saturating dyads cross ``|affinity| >
0.45`` between turns 8 and 14, and that non-saturating dyads (e.g. an
empty-utterance scenario) never cross.

This file is the regression guard on that calibration. If a future
slice tunes the formula's tunables (decay/weight/impact coefficients
in ``cognition/relational.py``), this test will flag whether the
promotion threshold + min_interactions still pair sensibly with the
new dynamics — a much earlier signal than waiting for the live G-GEAR
acceptance run to fail.

No LLM, no I/O, no fixtures beyond Pydantic construction.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.belief import BELIEF_MIN_INTERACTIONS, BELIEF_THRESHOLD
from erre_sandbox.cognition.relational import compute_affinity_delta
from erre_sandbox.schemas import (
    CognitiveHabit,
    DialogTurnMsg,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    Zone,
)

# Production persona traits (kant.yaml / nietzsche.yaml / rikyu.yaml as
# of 2026-04-26). Pinned here so trait drift on the YAMLs surfaces as a
# calibration test failure rather than a silent simulation regression.
_KANT_TRAITS = {
    "openness": 0.85,
    "conscientiousness": 0.98,
    "extraversion": 0.35,
    "agreeableness": 0.50,
    "neuroticism": 0.20,
    "wabi": 0.25,
    "ma_sense": 0.70,
}
_NIETZSCHE_TRAITS = {
    "openness": 0.92,
    "conscientiousness": 0.40,
    "extraversion": 0.20,
    "agreeableness": 0.25,
    "neuroticism": 0.85,
    "wabi": 0.55,
    "ma_sense": 0.30,
}
_RIKYU_TRAITS = {
    "openness": 0.65,
    "conscientiousness": 0.95,
    "extraversion": 0.20,
    "agreeableness": 0.50,
    "neuroticism": 0.25,
    "wabi": 0.95,
    "ma_sense": 0.95,
}


def _make_persona(persona_id: str, traits: dict[str, float]) -> PersonaSpec:
    return PersonaSpec(
        persona_id=persona_id,
        display_name=persona_id.title(),
        era="—",
        personality=PersonalityTraits(**traits),
        cognitive_habits=[
            CognitiveHabit(
                description="placeholder",
                source="placeholder",
                flag=HabitFlag.FACT,
                mechanism="placeholder",
            ),
        ],
        preferred_zones=[Zone.PERIPATOS],
    )


def _make_turn(
    *,
    speaker_persona_id: str,
    addressee_persona_id: str,
    utterance: str = "A typical reply that exercises the structural impact term.",
) -> DialogTurnMsg:
    return DialogTurnMsg(
        tick=0,
        dialog_id="sim",
        speaker_id=f"a_{speaker_persona_id}_001",
        addressee_id=f"a_{addressee_persona_id}_001",
        utterance=utterance,
        turn_index=0,
    )


def _simulate(
    *,
    persona: PersonaSpec,
    addressee_persona: PersonaSpec,
    n_turns: int,
    utterance: str | None = None,
) -> list[float]:
    """Iterate the recurrence and return ``affinity`` after each turn."""
    turn = _make_turn(
        speaker_persona_id=persona.persona_id,
        addressee_persona_id=addressee_persona.persona_id,
        utterance=utterance
        if utterance is not None
        else "A typical reply that exercises the structural impact term.",
    )
    affinities: list[float] = []
    prev = 0.0
    for _ in range(n_turns):
        delta = compute_affinity_delta(
            turn,
            recent_transcript=(),
            persona=persona,
            prev=prev,
            addressee_persona=addressee_persona,
        )
        prev = max(-1.0, min(1.0, prev + delta))
        affinities.append(prev)
    return affinities


def _first_crossing(
    affinities: list[float],
    threshold: float,
) -> int | None:
    """Return the 1-based turn index where ``|affinity| >= threshold``."""
    for i, a in enumerate(affinities, start=1):
        if abs(a) >= threshold:
            return i
    return None


# ---------- Saturation crossings (calibration) ----------------------------


def test_kant_to_nietzsche_crosses_threshold_in_window() -> None:
    """Antagonism path: |affinity| crosses 0.45 within the calibration window."""
    kant = _make_persona("kant", _KANT_TRAITS)
    nietzsche = _make_persona("nietzsche", _NIETZSCHE_TRAITS)
    affinities = _simulate(persona=kant, addressee_persona=nietzsche, n_turns=20)
    crossing = _first_crossing(affinities, BELIEF_THRESHOLD)
    assert crossing is not None, (
        f"kant→nietzsche never crosses |affinity|>{BELIEF_THRESHOLD} in 20 "
        f"turns; final = {affinities[-1]:.3f}"
    )
    # Calibration window: belief promotion should fire within [N, 14].
    assert BELIEF_MIN_INTERACTIONS <= crossing <= 14, (
        f"kant→nietzsche crosses at turn {crossing}, expected "
        f"[{BELIEF_MIN_INTERACTIONS}, 14]; affinities={affinities}"
    )
    # Sign sanity: this pair must end up negative.
    assert affinities[-1] < 0.0


def test_kant_to_rikyu_positive_crosses_threshold_in_window() -> None:
    """Non-antagonistic pairing reaches the positive threshold in the window."""
    kant = _make_persona("kant", _KANT_TRAITS)
    rikyu = _make_persona("rikyu", _RIKYU_TRAITS)
    affinities = _simulate(persona=kant, addressee_persona=rikyu, n_turns=20)
    crossing = _first_crossing(affinities, BELIEF_THRESHOLD)
    assert crossing is not None
    assert BELIEF_MIN_INTERACTIONS <= crossing <= 14, (
        f"kant→rikyu crosses at turn {crossing}, expected "
        f"[{BELIEF_MIN_INTERACTIONS}, 14]; affinities={affinities}"
    )
    assert affinities[-1] > 0.0


def test_nietzsche_to_rikyu_positive_crosses_threshold_in_window() -> None:
    """Non-antagonistic pair (introvert speaker) still saturates by turn 14."""
    nietzsche = _make_persona("nietzsche", _NIETZSCHE_TRAITS)
    rikyu = _make_persona("rikyu", _RIKYU_TRAITS)
    affinities = _simulate(
        persona=nietzsche,
        addressee_persona=rikyu,
        n_turns=20,
    )
    crossing = _first_crossing(affinities, BELIEF_THRESHOLD)
    assert crossing is not None
    assert BELIEF_MIN_INTERACTIONS <= crossing <= 14, (
        f"nietzsche→rikyu crosses at turn {crossing}, expected "
        f"[{BELIEF_MIN_INTERACTIONS}, 14]; affinities={affinities}"
    )


def test_empty_utterances_never_cross_threshold() -> None:
    """Defensive: pure-decay scenarios never spuriously promote."""
    kant = _make_persona("kant", _KANT_TRAITS)
    rikyu = _make_persona("rikyu", _RIKYU_TRAITS)
    # Override utterance to "" + addressee_id is set but no length signal,
    # so structural impact = 0.6 only (addressee_match) → still produces
    # positive growth; substitute a turn that drives impact to zero by
    # also clearing the addressee.
    turn = DialogTurnMsg(
        tick=0,
        dialog_id="sim",
        speaker_id="a_kant_001",
        addressee_id="",
        utterance="",
        turn_index=0,
    )
    prev = 0.0
    for _ in range(20):
        delta = compute_affinity_delta(
            turn,
            recent_transcript=(),
            persona=kant,
            prev=prev,
            addressee_persona=rikyu,
        )
        prev = max(-1.0, min(1.0, prev + delta))
    assert abs(prev) < BELIEF_THRESHOLD, (
        f"empty-impact scenario reached {prev:.3f}; should stay below "
        f"{BELIEF_THRESHOLD}"
    )


def test_threshold_and_min_interactions_are_self_consistent() -> None:
    """Constants stay in their documented ranges (regression on tuning drift)."""
    assert 0.0 < BELIEF_THRESHOLD < 1.0
    assert BELIEF_MIN_INTERACTIONS >= 1
    # If a future slice raises threshold past 0.7 we lose the curious /
    # wary band entirely — flag that tuning change here.
    assert BELIEF_THRESHOLD <= 0.69


def test_simulation_saturation_is_bounded_in_legal_range() -> None:
    """Final-affinity must respect the [-1, 1] clamp for every pair."""
    pairs = [
        ("kant", _KANT_TRAITS, "nietzsche", _NIETZSCHE_TRAITS),
        ("kant", _KANT_TRAITS, "rikyu", _RIKYU_TRAITS),
        ("nietzsche", _NIETZSCHE_TRAITS, "rikyu", _RIKYU_TRAITS),
    ]
    for sp_id, sp_traits, ad_id, ad_traits in pairs:
        affinities = _simulate(
            persona=_make_persona(sp_id, sp_traits),
            addressee_persona=_make_persona(ad_id, ad_traits),
            n_turns=30,
        )
        assert -1.0 <= affinities[-1] <= 1.0, (
            f"{sp_id}→{ad_id} saturated at {affinities[-1]} outside [-1, 1]"
        )


@pytest.mark.parametrize(
    ("speaker_id", "speaker_traits", "addressee_id", "addressee_traits"),
    [
        ("kant", _KANT_TRAITS, "nietzsche", _NIETZSCHE_TRAITS),
        ("kant", _KANT_TRAITS, "rikyu", _RIKYU_TRAITS),
        ("nietzsche", _NIETZSCHE_TRAITS, "rikyu", _RIKYU_TRAITS),
        ("nietzsche", _NIETZSCHE_TRAITS, "kant", _KANT_TRAITS),
    ],
)
def test_first_turn_delta_is_within_documented_envelope(
    speaker_id: str,
    speaker_traits: dict[str, float],
    addressee_id: str,
    addressee_traits: dict[str, float],
) -> None:
    """A single turn from prev=0 yields a delta with magnitude in [0.0, 1.0].

    Regression guard against decay/weight/impact tuning blowing past the
    clamp on the first interaction. Catches "the formula is correct but
    the magnitude is wildly off" before live G-GEAR observes it.
    """
    speaker = _make_persona(speaker_id, speaker_traits)
    addressee = _make_persona(addressee_id, addressee_traits)
    turn = _make_turn(
        speaker_persona_id=speaker_id,
        addressee_persona_id=addressee_id,
    )
    delta = compute_affinity_delta(
        turn,
        recent_transcript=(),
        persona=speaker,
        prev=0.0,
        addressee_persona=addressee,
    )
    assert -1.0 <= delta <= 1.0
    assert delta != pytest.approx(0.0)
