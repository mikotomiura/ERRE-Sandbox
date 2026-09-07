"""Tests for the §6 decision rule in scripts/paper01_external_audit.py (I-003).

design-final.md §6 is the single source of truth for the rule under test.
Every test here is **encoder-independent**: candidates are built directly as
:class:`~scripts.paper01_external_audit.CandidateExternalReport` instances
and pushed through :func:`~scripts.paper01_external_audit.decide_external`
-- no rarity computation, no adapter, no ``[eval]`` extras.

Per design-final.md §7 (Opus MEDIUM-11 "eliminate tautological ACs"), every
negative case here is run through :func:`decide_external` itself; no test
inspects a constructed dataclass's own fields as if that were a check on the
decision rule.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from scripts import paper01_external_audit as mod

from erre_sandbox.evidence.es4_actuator import constants as _c

if TYPE_CHECKING:
    import pytest

# --- shared fixtures --------------------------------------------------------

_OK_CLASS_SIZES = {"good": 40, "common": 2087}
_DEFICIENT_CLASS_SIZES = {"good": 10, "common": 2087}

_SURVIVOR_CI = (0.85, 0.95)  # both ends >= AUC_FLOOR (0.80)
_COLLAPSED_CI = (0.50, 0.79)  # both ends < AUC_FLOOR
_STRADDLE_CI = (0.70, 0.85)  # lower < AUC_FLOOR <= upper


def _report(
    key: str,
    *,
    family: str = "embedding",
    eligible: bool = True,
    engaged: bool = True,
    ci: tuple[float, float] = _SURVIVOR_CI,
    potency_median: float = 0.2,
    auc_full_median: float = 0.9,
    auc_lao_median: float = 0.9,
    drop_median: float = 0.0,
) -> mod.CandidateExternalReport:
    """Build one candidate report with a single-draw flag history.

    A single-element flags tuple is enough to drive
    :func:`~scripts.paper01_external_audit.aggregate_draws` (1/1 = 1.0 or
    0/1 = 0.0, both unambiguous against the 0.5 threshold); the draw-count
    dimension itself is covered by ``test_draw_aggregation_is_per_draw_not_
    marginal_median`` in ``test_preregistration.py``, not here.
    """
    ci_lower, ci_upper = ci
    collapsed_b = eligible and engaged and ci_upper < _c.AUC_FLOOR
    return mod.CandidateExternalReport(
        key=key,
        family=family,
        eligible_flags=(eligible,),
        engaged_flags=(engaged,),
        collapsed_flags=(collapsed_b,),
        auc_lao_ci_lower=ci_lower,
        auc_lao_ci_upper=ci_upper,
        potency_median=potency_median,
        auc_full_median=auc_full_median,
        auc_lao_median=auc_lao_median,
        drop_median=drop_median,
        audit_not_engaged=not engaged,
    )


# --- 003-1 -------------------------------------------------------------------


def test_decide_external_is_total() -> None:
    """Every combination of (eligible, engaged, collapsed) x class-deficiency,
    for 1-3 candidates, returns exactly one of the four §6 verdicts -- never
    an exception and never a value outside VERDICT_ENUM.
    """
    per_candidate_states = list(
        itertools.product((True, False), (True, False), (True, False))
    )
    candidate_keys = mod.EMBEDDING_FAMILY_EXT[:3]

    seen_verdicts: set[str] = set()
    for n_candidates in (1, 2, 3):
        for combo in itertools.product(per_candidate_states, repeat=n_candidates):
            for class_sizes in (_OK_CLASS_SIZES, _DEFICIENT_CLASS_SIZES):
                reports = [
                    _report(
                        candidate_keys[i],
                        eligible=elig,
                        engaged=eng,
                        ci=_COLLAPSED_CI if coll else _SURVIVOR_CI,
                    )
                    for i, (elig, eng, coll) in enumerate(combo)
                ]
                result = mod.decide_external(reports, class_sizes=class_sizes)
                assert result.verdict in mod.VERDICT_ENUM
                seen_verdicts.add(result.verdict)

    # Not a hard requirement of totality, but confirms the sweep actually
    # exercises real diversity rather than collapsing to one branch.
    assert len(seen_verdicts) >= 2


# --- 003-2 -------------------------------------------------------------------


def test_mixed_engaged_all_collapsed_is_no_valid_scorer() -> None:
    """engaged and not-engaged candidates coexist; every *engaged* one has
    collapsed -> NO_VALID_SCORER (the E2-restricted equality, not an E-wide
    one that a not-engaged candidate could permanently block).
    """
    reports = [
        _report("X0", eligible=True, engaged=True, ci=_COLLAPSED_CI),
        _report("X1", eligible=True, engaged=True, ci=_COLLAPSED_CI),
        _report("X2", eligible=True, engaged=False),  # potency = 0, not engaged
    ]
    result = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert result.verdict == "NO_VALID_SCORER"
    assert result.collapse_reproduced is True
    assert result.engaged == ("X0", "X1")
    assert result.collapsed == ("X0", "X1")
    assert "X2" not in result.engaged
    assert "X2" not in result.collapsed


# --- 003-3 -------------------------------------------------------------------


def test_ineligible_engaged_candidate_does_not_block_verdict() -> None:
    """The minimal reproduction of this issue's reason for existing: one
    eligible-but-potency=0 candidate sits alongside one truly-collapsed
    engaged candidate. NO_VALID_SCORER must still be reachable -- a naive
    ``collapsed == E`` rule would be permanently blocked by the potency=0
    candidate (it is eligible, never engaged, therefore never collapsed).
    """
    reports = [
        _report("X0", eligible=True, engaged=True, ci=_COLLAPSED_CI),
        _report("X1", eligible=True, engaged=False),  # the blocking candidate
    ]
    result = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert result.verdict == "NO_VALID_SCORER"
    assert result.eligible == ("X0", "X1")
    assert result.engaged == ("X0",)
    assert result.collapsed == ("X0",)


# --- 003-4 -------------------------------------------------------------------


def test_all_verdicts_are_reachable() -> None:
    """decide_external is not tautological: each of the four verdicts has a
    concrete, constructible input that reaches it.
    """
    pass_result = mod.decide_external(
        [_report("X0", ci=_SURVIVOR_CI)], class_sizes=_OK_CLASS_SIZES
    )
    no_valid_scorer_result = mod.decide_external(
        [_report("X0", ci=_COLLAPSED_CI)], class_sizes=_OK_CLASS_SIZES
    )
    invalid_battery_result = mod.decide_external(
        [_report("X0", ci=_SURVIVOR_CI)], class_sizes=_DEFICIENT_CLASS_SIZES
    )
    inconclusive_result = mod.decide_external(
        [_report("X0", ci=_STRADDLE_CI)], class_sizes=_OK_CLASS_SIZES
    )

    assert pass_result.verdict == "PASS"
    assert no_valid_scorer_result.verdict == "NO_VALID_SCORER"
    assert invalid_battery_result.verdict == "INVALID_TASK_BATTERY"
    assert inconclusive_result.verdict == "INCONCLUSIVE_UNDERPOWERED"

    reached = {
        pass_result.verdict,
        no_valid_scorer_result.verdict,
        invalid_battery_result.verdict,
        inconclusive_result.verdict,
    }
    assert reached == set(mod.VERDICT_ENUM)


# --- 003-5 -------------------------------------------------------------------


def test_ineligible_candidate_is_not_counted_as_collapse() -> None:
    """A not-eligible candidate whose CI would look collapsed if it were
    counted must never appear in `eligible`/`engaged`/`collapsed` -- only a
    genuinely eligible+engaged+survivor candidate should decide the verdict.
    """
    reports = [
        _report("X0", eligible=False, engaged=True, ci=_COLLAPSED_CI),
        _report("X1", eligible=True, engaged=True, ci=_SURVIVOR_CI),
    ]
    result = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert result.verdict == "PASS"
    assert "X0" not in result.eligible
    assert "X0" not in result.engaged
    assert "X0" not in result.collapsed
    assert result.survivors == ("X1",)


# --- 003-6 -------------------------------------------------------------------


def test_zero_potency_candidate_does_not_grant_pass() -> None:
    """A potency=0 candidate has auc_lao == auc_full >= floor identically,
    which a naive rule would read as a survivor. It must not grant PASS --
    the candidate is not engaged and therefore is excluded from E2 entirely.
    """
    reports = [
        _report(
            "X0",
            eligible=True,
            engaged=False,
            ci=_SURVIVOR_CI,  # identity: auc_lao == auc_full >= floor
            potency_median=0.0,
            auc_full_median=0.92,
            auc_lao_median=0.92,
            drop_median=0.0,
        ),
    ]
    result = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert result.verdict != "PASS"
    assert result.verdict == "INVALID_TASK_BATTERY"
    assert result.eligible == ("X0",)
    assert result.engaged == ()
    assert result.survivors == ()


# --- 003-7 -------------------------------------------------------------------


def test_invalid_task_battery_paths() -> None:
    """All three §6 INVALID_TASK_BATTERY entry paths independently fire:
    class-deficient gold, |E| == 0, and |E2| == 0.
    """
    class_deficient = mod.decide_external(
        [_report("X0", ci=_SURVIVOR_CI)], class_sizes=_DEFICIENT_CLASS_SIZES
    )
    empty_e = mod.decide_external([], class_sizes=_OK_CLASS_SIZES)
    empty_e2 = mod.decide_external(
        [
            _report("X0", eligible=True, engaged=False),
            _report("X1", eligible=True, engaged=False),
        ],
        class_sizes=_OK_CLASS_SIZES,
    )
    not_even_eligible = mod.decide_external(
        [_report("X0", eligible=False, engaged=False)], class_sizes=_OK_CLASS_SIZES
    )

    for result in (class_deficient, empty_e, empty_e2, not_even_eligible):
        assert result.verdict == "INVALID_TASK_BATTERY"
    assert empty_e.eligible == ()
    assert empty_e2.eligible == ("X0", "X1")
    assert empty_e2.engaged == ()


# --- 003-8 -------------------------------------------------------------------


def test_ci_crossing_floor_is_inconclusive() -> None:
    """An engaged candidate whose bootstrap CI straddles the floor (neither
    fully above -> survivor, nor fully below -> collapsed) yields
    INCONCLUSIVE_UNDERPOWERED, not one of the other three verdicts.
    """
    reports = [_report("X0", eligible=True, engaged=True, ci=_STRADDLE_CI)]
    result = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert result.verdict == "INCONCLUSIVE_UNDERPOWERED"
    assert result.survivors == ()
    assert result.collapsed == ()
    assert result.engaged == ("X0",)


# --- 003-9 -------------------------------------------------------------------


def test_lexical_candidate_does_not_drive_verdict() -> None:
    """X5/X6 (lexical) never enter EMBEDDING_FAMILY_EXT, so changing a
    lexical candidate's flags/CI in any way must leave the verdict (and
    every derived set) unchanged.
    """
    embedding_reports = [_report("X0", eligible=True, engaged=True, ci=_SURVIVOR_CI)]

    lexical_variant_a = _report(
        "X5", family="lexical", eligible=True, engaged=True, ci=_COLLAPSED_CI
    )
    lexical_variant_b = _report(
        "X6", family="lexical", eligible=False, engaged=False, ci=_STRADDLE_CI
    )

    result_a = mod.decide_external(
        [*embedding_reports, lexical_variant_a], class_sizes=_OK_CLASS_SIZES
    )
    result_b = mod.decide_external(
        [*embedding_reports, lexical_variant_b], class_sizes=_OK_CLASS_SIZES
    )

    assert result_a == result_b
    assert result_a.verdict == "PASS"
    assert "X5" not in result_a.eligible
    assert "X6" not in result_b.eligible


# --- 003-10 ------------------------------------------------------------------


def test_collapse_reproduced_matches_verdict() -> None:
    """`collapse_reproduced` tracks `verdict == "NO_VALID_SCORER"` exactly,
    across every reachable verdict (design-final.md §6, Opus MEDIUM-8: the
    §6 PASS/§8 PASS polarity does not line up, so this flag must be checked
    against the verdict directly rather than assumed).
    """
    scenarios = [
        mod.decide_external(
            [_report("X0", ci=_SURVIVOR_CI)], class_sizes=_OK_CLASS_SIZES
        ),
        mod.decide_external(
            [_report("X0", ci=_COLLAPSED_CI)], class_sizes=_OK_CLASS_SIZES
        ),
        mod.decide_external(
            [_report("X0", ci=_SURVIVOR_CI)], class_sizes=_DEFICIENT_CLASS_SIZES
        ),
        mod.decide_external(
            [_report("X0", ci=_STRADDLE_CI)], class_sizes=_OK_CLASS_SIZES
        ),
    ]
    for result in scenarios:
        assert result.collapse_reproduced == (result.verdict == "NO_VALID_SCORER")


# --- bonus: non-tautological floor read-through ------------------------------


def test_auc_floor_is_read_through_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUC_FLOOR is read from `_c.AUC_FLOOR` inside decide_external itself,
    never baked in at import time -- monkeypatching it before the call moves
    both the verdict and the reported `auc_floor` field.
    """
    reports = [_report("X0", eligible=True, engaged=True, ci=(0.5, 0.6))]

    before = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert before.verdict == "NO_VALID_SCORER"
    assert before.auc_floor == _c.AUC_FLOOR

    monkeypatch.setattr(_c, "AUC_FLOOR", 0.4)
    after = mod.decide_external(reports, class_sizes=_OK_CLASS_SIZES)
    assert after.verdict == "PASS"
    assert after.auc_floor == 0.4
