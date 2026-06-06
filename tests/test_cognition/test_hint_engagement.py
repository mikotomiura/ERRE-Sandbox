"""Faithfulness of the hint-engagement shadow classifier + carrier (ADR §2 / §7).

CPU-only. The core guarantee (ADR §2): the shadow ``classify_rejection_reason``
agrees with the authority ``apply_world_model_update_hint`` — ``classify == 'adopted'``
iff the authority adopts — and the four reject reasons fire in the authority's
predicate order. Pinned two ways:

* a **conformance property test** over a deterministic, fixed-seed Cartesian enumerator
  of ``(hint, exposed_citations, swm)`` under the domain precondition (the exposed map
  is built from the same SWM via ``visible_entry_citations``). No Hypothesis — a plain
  ``@pytest.mark.parametrize`` enumerator (補強 §2);
* per-gate unit scenarios incl. predicate-order ties.

Also covers ``adopted_signed_step`` being the **measured** delta (a near-zero ``weaken``
adopts with a sub-``VALUE_STEP`` step, 補強 §1) and the carrier builders' fixed shapes.
"""

from __future__ import annotations

import itertools

import pytest

from erre_sandbox.cognition.hint_engagement import (
    LLM_STATUS_UNAVAILABLE,
    LLM_STATUS_UNPARSEABLE,
    build_emitted_disposition,
    build_not_emitted_disposition,
    classify_rejection_reason,
    measure_adopted_signed_step,
)
from erre_sandbox.cognition.prompting import visible_entry_citations
from erre_sandbox.cognition.world_model import apply_world_model_update_hint
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelUpdateHint,
)


def _entry(
    axis: str, key: str, value: float, cited: tuple[str, ...]
) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,
        key=key,
        value=value,
        confidence=0.8,
        cited_memory_ids=cited,
        last_updated_tick=3,
    )


def _hint(
    axis: str, key: str, direction: str, cited: tuple[str, ...]
) -> WorldModelUpdateHint:
    return WorldModelUpdateHint(
        axis=axis, key=key, direction=direction, cited_memory_ids=cited
    )  # type: ignore[arg-type]


# --- per-gate scenarios (incl. predicate-order ties) --------------------------

# Each scenario: (entries, hint, expected_disposition). ``exposed`` is derived from
# ``entries`` via ``visible_entry_citations`` so the domain precondition holds.
_A = _entry("self", "adopt_pos", 0.5, ("m1", "m2"))
_F = _entry("self", "near_zero", 0.03, ("m1",))
_B = _entry("env", "zero", 0.0, ("m1",))
_C_POS = _entry("norm", "absbound", 1.0, ("m1",))
_C_NEG = _entry("norm", "absbound", -1.0, ("m1",))
_D = _entry("concept", "cite", 0.3, ("m1", "m2", "m9"))  # displayed = {m1, m2}
_E = _entry("temporal", "hidden", 0.4, ("m1",))

_SCENARIOS: list[tuple[list[WorldModelEntry], WorldModelUpdateHint, str]] = [
    ([_A], _hint("self", "adopt_pos", "strengthen", ("m1",)), "adopted"),
    ([_A], _hint("self", "adopt_pos", "weaken", ("m1",)), "adopted"),
    # 補強 §1: weaken clamps at 0, so a 0.03 entry adopts with a sub-VALUE_STEP step.
    ([_F], _hint("self", "near_zero", "weaken", ("m1",)), "adopted"),
    ([_B], _hint("env", "zero", "strengthen", ("m1",)), "rejected_no_effect"),
    ([_C_POS], _hint("norm", "absbound", "strengthen", ("m1",)), "rejected_no_effect"),
    ([_C_NEG], _hint("norm", "absbound", "strengthen", ("m1",)), "rejected_no_effect"),
    ([_A], _hint("self", "adopt_pos", "no_change", ("m1",)), "rejected_no_change"),
    ([_D], _hint("concept", "cite", "strengthen", ("m9",)), "rejected_citation"),
    # 5th entry is never displayed (top-4 only) -> not_displayed.
    (
        [_A, _F, _B, _D, _E],
        _hint("temporal", "hidden", "strengthen", ("m1",)),
        "rejected_not_displayed",
    ),
    ([_A], _hint("self", "ghost", "strengthen", ("m1",)), "rejected_not_displayed"),
    # Predicate-order ties: gate 1 (not_displayed) beats gate 3 (no_change)...
    ([_A], _hint("self", "ghost", "no_change", ("m1",)), "rejected_not_displayed"),
    # ...and gate 2 (citation) beats gate 3 (no_change).
    ([_D], _hint("concept", "cite", "no_change", ("m9",)), "rejected_citation"),
]


@pytest.mark.parametrize(("entries", "hint", "expected"), _SCENARIOS)
def test_classify_matches_authority_per_scenario(
    entries: list[WorldModelEntry],
    hint: WorldModelUpdateHint,
    expected: str,
) -> None:
    swm = SubjectiveWorldModel(entries=entries)
    exposed = visible_entry_citations(entries)

    assert classify_rejection_reason(hint, exposed, swm) == expected

    # Conformance: classify=='adopted' iff the authority adopts.
    nudged = apply_world_model_update_hint(swm, hint, exposed)
    assert (expected == "adopted") == (nudged is not None)


def test_near_zero_weaken_records_sub_step_delta() -> None:
    """補強 §1: weaken on 0.03 adopts with step -0.03 (< VALUE_STEP), not -0.05."""
    swm = SubjectiveWorldModel(entries=[_F])
    exposed = visible_entry_citations([_F])
    hint = _hint("self", "near_zero", "weaken", ("m1",))
    nudged = apply_world_model_update_hint(swm, hint, exposed)
    assert nudged is not None
    step = measure_adopted_signed_step(swm, nudged, axis="self", key="near_zero")
    assert step == pytest.approx(-0.03)


def test_full_step_deltas_are_signed() -> None:
    swm = SubjectiveWorldModel(entries=[_A])
    exposed = visible_entry_citations([_A])
    up = apply_world_model_update_hint(
        swm, _hint("self", "adopt_pos", "strengthen", ("m1",)), exposed
    )
    down = apply_world_model_update_hint(
        swm, _hint("self", "adopt_pos", "weaken", ("m1",)), exposed
    )
    assert up is not None
    assert down is not None
    assert measure_adopted_signed_step(
        swm, up, axis="self", key="adopt_pos"
    ) == pytest.approx(0.05)
    assert measure_adopted_signed_step(
        swm, down, axis="self", key="adopt_pos"
    ) == pytest.approx(-0.05)


# --- conformance property test (deterministic Cartesian enumerator, 補強 §2) ----

# A fixed SWM spanning every gate-relevant value shape; the exposed map is built from
# it so the domain precondition holds for every enumerated hint.
_PROP_ENTRIES = [
    _entry("self", "mid", 0.5, ("m1", "m2")),
    _entry("env", "zero", 0.0, ("m1", "m2")),
    _entry("norm", "pos_bound", 1.0, ("m1", "m2")),
    _entry("concept", "neg_bound", -1.0, ("m1", "m2")),
    _entry("temporal", "hidden5", 0.4, ("m1", "m2")),  # 5th -> never displayed
]
_PROP_SWM = SubjectiveWorldModel(entries=_PROP_ENTRIES)
_PROP_EXPOSED = visible_entry_citations(_PROP_ENTRIES)

# Targets: real displayed keys, the hidden 5th key, and a nonexistent key.
_PROP_TARGETS = [
    ("self", "mid"),
    ("env", "zero"),
    ("norm", "pos_bound"),
    ("concept", "neg_bound"),
    ("temporal", "hidden5"),
    ("self", "ghost"),
]
_PROP_DIRECTIONS = ["strengthen", "weaken", "no_change"]
# Citation choices: a displayed id (subset), a non-displayed id (not subset).
_PROP_CITED = [("m1",), ("m9",)]

_PROP_CASES = list(itertools.product(_PROP_TARGETS, _PROP_DIRECTIONS, _PROP_CITED))


@pytest.mark.parametrize(("target", "direction", "cited"), _PROP_CASES)
def test_classify_conforms_to_authority_over_enumerated_space(
    target: tuple[str, str],
    direction: str,
    cited: tuple[str, ...],
) -> None:
    axis, key = target
    hint = _hint(axis, key, direction, cited)
    disposition = classify_rejection_reason(hint, _PROP_EXPOSED, _PROP_SWM)
    nudged = apply_world_model_update_hint(_PROP_SWM, hint, _PROP_EXPOSED)

    # Core conformance: the shadow's 'adopted' verdict matches the authority exactly.
    assert (disposition == "adopted") == (nudged is not None)

    # When adopted, the measured step matches the authority's actual value move.
    if disposition == "adopted":
        assert nudged is not None
        step = measure_adopted_signed_step(_PROP_SWM, nudged, axis=axis, key=key)
        old = next(e.value for e in _PROP_SWM.entries if (e.axis, e.key) == target)
        new = next(e.value for e in nudged.entries if (e.axis, e.key) == target)
        assert step == pytest.approx(new - old)


def test_every_enumerated_disposition_is_in_the_closed_vocabulary() -> None:
    valid = {
        "adopted",
        "rejected_not_displayed",
        "rejected_citation",
        "rejected_no_change",
        "rejected_no_effect",
    }
    for target, direction, cited in _PROP_CASES:
        axis, key = target
        result = classify_rejection_reason(
            _hint(axis, key, direction, cited), _PROP_EXPOSED, _PROP_SWM
        )
        assert result in valid


# --- carrier builders ---------------------------------------------------------


def test_emitted_carrier_adopted_shape() -> None:
    swm = SubjectiveWorldModel(entries=[_A])
    exposed = visible_entry_citations([_A])
    hint = _hint("self", "adopt_pos", "strengthen", ("m1",))
    nudged = apply_world_model_update_hint(swm, hint, exposed)
    carrier = build_emitted_disposition(
        hint=hint,
        exposed_citations=exposed,
        swm=swm,
        nudged=nudged,
        exposed_entry_count=1,
    )
    assert carrier.llm_status == "ok"
    assert carrier.emitted is True
    assert carrier.disposition == "adopted"
    assert carrier.target_axis == "self"
    assert carrier.target_key == "adopt_pos"
    assert carrier.direction == "strengthen"
    assert carrier.adopted_signed_step == pytest.approx(0.05)
    assert carrier.exposed_entry_count == 1


def test_emitted_carrier_rejected_shape_has_zero_step() -> None:
    swm = SubjectiveWorldModel(entries=[_B])
    exposed = visible_entry_citations([_B])
    hint = _hint("env", "zero", "strengthen", ("m1",))
    carrier = build_emitted_disposition(
        hint=hint,
        exposed_citations=exposed,
        swm=swm,
        nudged=None,
        exposed_entry_count=1,
    )
    assert carrier.emitted is True
    assert carrier.disposition == "rejected_no_effect"
    assert carrier.adopted_signed_step == 0.0
    assert carrier.direction == "strengthen"


@pytest.mark.parametrize(
    "status", ["ok", LLM_STATUS_UNAVAILABLE, LLM_STATUS_UNPARSEABLE]
)
def test_not_emitted_carrier_fixed_shape(status: str) -> None:
    carrier = build_not_emitted_disposition(llm_status=status, exposed_entry_count=3)  # type: ignore[arg-type]
    assert carrier.llm_status == status
    assert carrier.emitted is False
    assert carrier.disposition == "not_emitted"
    assert carrier.target_axis is None
    assert carrier.target_key is None
    assert carrier.direction is None
    assert carrier.adopted_signed_step == 0.0
    assert carrier.exposed_entry_count == 3
