"""Unit tests for ``cognition.belief.maybe_promote_belief`` (M7δ Commit C5).

These tests cover the pure-function gate: bond + persona pair → typed
:class:`SemanticMemoryRecord` (or ``None`` when either gate fails). The
storage write is exercised separately via ``test_relational_simulation``
(formula calibration) and the live G-GEAR run (C8 acceptance gate).
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.belief import (
    BELIEF_MIN_INTERACTIONS,
    BELIEF_THRESHOLD,
    maybe_promote_belief,
)
from erre_sandbox.schemas import (
    CognitiveHabit,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    RelationshipBond,
    Zone,
)


def _make_persona(persona_id: str = "kant") -> PersonaSpec:
    return PersonaSpec(
        persona_id=persona_id,
        display_name=persona_id.title(),
        era="—",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="x",
                source="x",
                flag=HabitFlag.FACT,
                mechanism="x",
            ),
        ],
        preferred_zones=[Zone.PERIPATOS],
    )


def _make_bond(
    *,
    affinity: float = 0.0,
    ichigo_ichie_count: int = 0,
    other_agent_id: str = "a_other_001",
) -> RelationshipBond:
    return RelationshipBond(
        other_agent_id=other_agent_id,
        affinity=affinity,
        ichigo_ichie_count=ichigo_ichie_count,
    )


# ---------- Gate behaviour -------------------------------------------------


def test_returns_none_when_below_threshold() -> None:
    """``|affinity|`` short of the threshold blocks promotion."""
    bond = _make_bond(affinity=0.30, ichigo_ichie_count=10)
    assert (
        maybe_promote_belief(
            bond,
            agent_id="a_kant_001",
            persona=_make_persona("kant"),
            addressee_persona=_make_persona("nietzsche"),
        )
        is None
    )


def test_returns_none_when_below_min_interactions() -> None:
    """Strong affinity with too few interactions blocks promotion."""
    bond = _make_bond(affinity=0.80, ichigo_ichie_count=2)
    assert (
        maybe_promote_belief(
            bond,
            agent_id="a_kant_001",
            persona=_make_persona("kant"),
            addressee_persona=_make_persona("nietzsche"),
        )
        is None
    )


def test_returns_record_when_both_gates_pass() -> None:
    """Both gates passed → typed SemanticMemoryRecord built."""
    bond = _make_bond(affinity=0.55, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    assert record is not None
    assert record.belief_kind in {"trust", "curious", "wary", "clash"}
    assert record.confidence > 0.0


def test_threshold_override_relaxes_gate() -> None:
    """Test-side override lets fixtures fire without touching the constant."""
    bond = _make_bond(affinity=0.20, ichigo_ichie_count=10)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
        threshold=0.10,
    )
    assert record is not None


def test_min_interactions_override_relaxes_gate() -> None:
    bond = _make_bond(affinity=0.80, ichigo_ichie_count=2)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
        min_interactions=2,
    )
    assert record is not None


# ---------- Classification -------------------------------------------------


@pytest.mark.parametrize(
    ("affinity", "expected_kind"),
    [
        (0.95, "trust"),
        (0.70, "trust"),  # R4 M4 — exact ``_TRUST_FLOOR`` boundary; ``>=`` is pass.
        (0.55, "curious"),
        (-0.55, "wary"),
        (-0.70, "clash"),  # R4 M4 — exact negative ``_TRUST_FLOOR`` boundary.
        (-0.95, "clash"),
    ],
)
def test_belief_kind_classification(affinity: float, expected_kind: str) -> None:
    bond = _make_bond(affinity=affinity, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("nietzsche"),
    )
    assert record is not None
    assert record.belief_kind == expected_kind


def test_confidence_scales_with_magnitude_and_interactions() -> None:
    """Higher ``|affinity|`` and more interactions → higher confidence (≤1.0)."""
    weak = _make_bond(affinity=0.50, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    strong = _make_bond(affinity=0.95, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS * 2)
    weak_record = maybe_promote_belief(
        weak,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    strong_record = maybe_promote_belief(
        strong,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    assert weak_record is not None
    assert strong_record is not None
    assert weak_record.confidence < strong_record.confidence
    assert strong_record.confidence == pytest.approx(1.0)


# ---------- Determinism + idempotence --------------------------------------


def test_record_id_is_deterministic_for_dyad() -> None:
    """Two promotions for the same dyad produce the same id (upsert target)."""
    bond_a = _make_bond(affinity=0.60, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    bond_b = _make_bond(affinity=0.80, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS + 5)
    record_a = maybe_promote_belief(
        bond_a,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    record_b = maybe_promote_belief(
        bond_b,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    assert record_a is not None
    assert record_b is not None
    assert record_a.id == record_b.id


def test_record_id_differs_per_dyad() -> None:
    bond = _make_bond(affinity=0.60, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    record_kant_to_rikyu = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    bond_other = _make_bond(
        affinity=0.60,
        ichigo_ichie_count=BELIEF_MIN_INTERACTIONS,
        other_agent_id="a_nietzsche_001",
    )
    record_kant_to_nietzsche = maybe_promote_belief(
        bond_other,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("nietzsche"),
    )
    assert record_kant_to_rikyu is not None
    assert record_kant_to_nietzsche is not None
    assert record_kant_to_rikyu.id != record_kant_to_nietzsche.id


def test_summary_carries_addressee_display_name() -> None:
    bond = _make_bond(affinity=0.60, ichigo_ichie_count=BELIEF_MIN_INTERACTIONS)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("rikyu"),
    )
    assert record is not None
    assert "Rikyu" in record.summary
    assert record.summary.startswith("belief: I ")


def test_threshold_constant_consistent_with_module_default() -> None:
    """Imported constant matches the function default — no drift."""
    bond = _make_bond(
        affinity=BELIEF_THRESHOLD - 0.01,
        ichigo_ichie_count=BELIEF_MIN_INTERACTIONS,
    )
    assert (
        maybe_promote_belief(
            bond,
            agent_id="a_kant_001",
            persona=_make_persona("kant"),
            addressee_persona=_make_persona("rikyu"),
        )
        is None
    )


# =============================================================================
# R4 M1 — gate boundary tests (strict-less-than semantics)
# =============================================================================


@pytest.mark.parametrize(
    ("affinity", "interactions", "should_promote"),
    [
        # Exactly at the threshold: ``abs(affinity) < threshold`` is False, so
        # the gate passes.
        (BELIEF_THRESHOLD, BELIEF_MIN_INTERACTIONS, True),
        # One ulp below the threshold: still blocked.
        (BELIEF_THRESHOLD - 0.001, BELIEF_MIN_INTERACTIONS, False),
        # Exact negative boundary: same strict-less-than semantics.
        (-BELIEF_THRESHOLD, BELIEF_MIN_INTERACTIONS, True),
        # Exactly at the min-interactions floor: ``ichigo_ichie_count <
        # min_interactions`` is False, so the gate passes.
        (BELIEF_THRESHOLD + 0.05, BELIEF_MIN_INTERACTIONS, True),
        # One short of the min-interactions floor: blocked.
        (BELIEF_THRESHOLD + 0.05, BELIEF_MIN_INTERACTIONS - 1, False),
    ],
)
def test_belief_promotion_at_exact_boundaries(
    affinity: float,
    interactions: int,
    should_promote: bool,  # noqa: FBT001 — parametrised truth target.
) -> None:
    """R4 M1 — pin strict-less-than semantics at the exact gate boundaries."""
    bond = _make_bond(affinity=affinity, ichigo_ichie_count=interactions)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("nietzsche"),
    )
    assert (record is not None) == should_promote


# =============================================================================
# R4 M6 — confidence clamp at 1.0
# =============================================================================


def test_confidence_clamps_at_one() -> None:
    """``min(1.0, ...)`` floor in ``_compute_confidence`` is enforced explicitly.

    R4 M6: ``test_confidence_scales_with_magnitude_and_interactions`` already
    exercises the clamp incidentally (``0.95 * 2.0 -> 1.0``), but doing so
    by name self-documents the contract: an arbitrarily large interaction
    multiplier must not produce ``confidence > 1.0``.
    """
    bond = _make_bond(affinity=1.0, ichigo_ichie_count=100)
    record = maybe_promote_belief(
        bond,
        agent_id="a_kant_001",
        persona=_make_persona("kant"),
        addressee_persona=_make_persona("nietzsche"),
    )
    assert record is not None
    assert record.confidence == pytest.approx(1.0)
