"""M13-ES4 Phase 0 / Phase 1 verdict logic (§4.1 / §8), synthetic fixtures.

Drives every one of the five vocabulary branches with constructed
Decomposition / control / battery / budget objects. Verdict *values* of a real run
are never baked here — this pins the decision logic, INCONCLUSIVE-first ordering
and over-claim scope.
"""

from __future__ import annotations

from erre_sandbox.evidence.es4_actuator.decomposition import Decomposition
from erre_sandbox.evidence.es4_actuator.verdict_report import (
    BatteryValidity,
    BudgetStatus,
    ScorerControls,
    evaluate_phase0,
    evaluate_phase1,
    required_clusters_for_mde,
)


def _decomp(**over: object) -> Decomposition:
    base = {
        "clusters": (),
        "n_clusters": 48,
        "delta_dq": 0.05,
        "delta_dq_std": 0.50,
        "delta_dq_ci_lower": 0.03,
        "delta_dq_ci_upper": 0.07,
        "delta_dq_std_ci_lower": 0.30,
        "monotone_supported": True,
        "monotone_min_increment_ci_lower": 0.01,
        "fluency_by_condition": {"A0": 3.0, "A1": 3.0, "A2": 3.0},
        "garbage_rate_by_condition": {"A0": 0.0, "A1": 0.0, "A2": 0.10},
        "empty_parse_rate_by_condition": {"A0": 0.0},
        "dispersion_by_condition": {"A0": 0.1},
        "cross_condition_valid_divergence": 0.0,
        "cross_condition_missing_divergence": 0.0,
    }
    base.update(over)
    return Decomposition(**base)  # type: ignore[arg-type]


def _scorer(**over: object) -> ScorerControls:
    base = {
        "a1_min_auc": 0.90,
        "a2_residual_survives": True,
        "a2_residual_ci_lower": 0.02,
        "adversarial_auc": 0.90,
    }
    base.update(over)
    return ScorerControls(**base)  # type: ignore[arg-type]


def _battery(**over: object) -> BatteryValidity:
    base = {
        "n_valid_aut": 16,
        "n_valid_rat": 12,
        "empty_parse_rate": 0.0,
        "cross_cond_valid_divergence": 0.0,
        "cross_cond_missing_divergence": 0.0,
        "persona_collapse": False,
        "rat_contamination": False,
    }
    base.update(over)
    return BatteryValidity(**base)  # type: ignore[arg-type]


_BUDGET_OK = BudgetStatus(projected_gpu_hours=5.0, cap_gpu_hours=8.0)


def test_required_clusters_within_available() -> None:
    req = required_clusters_for_mde()
    assert 0 < req <= 48


# --- Phase 0 ---


def test_phase0_pass() -> None:
    v = evaluate_phase0(_decomp(), _scorer(), _battery(), _BUDGET_OK)
    assert v.verdict == "PASS"


def test_phase0_invalid_scorer() -> None:
    v = evaluate_phase0(_decomp(), _scorer(a1_min_auc=0.5), _battery(), _BUDGET_OK)
    assert v.verdict == "INVALID_SCORER"


def test_phase0_invalid_battery() -> None:
    v = evaluate_phase0(_decomp(), _scorer(), _battery(n_valid_aut=10), _BUDGET_OK)
    assert v.verdict == "INVALID_TASK_BATTERY"


def test_phase0_no_go_strong_absence() -> None:
    v = evaluate_phase0(
        _decomp(delta_dq_ci_upper=0.01), _scorer(), _battery(), _BUDGET_OK
    )
    assert v.verdict == "NO_GO_EFFECT_ABSENT"


def test_phase0_inconclusive_underpowered_clusters() -> None:
    v = evaluate_phase0(_decomp(n_clusters=20), _scorer(), _battery(), _BUDGET_OK)
    assert v.verdict == "INCONCLUSIVE_UNDERPOWERED"


def test_phase0_inconclusive_over_budget() -> None:
    over = BudgetStatus(projected_gpu_hours=40.0, cap_gpu_hours=8.0)
    v = evaluate_phase0(_decomp(), _scorer(), _battery(), over)
    assert v.verdict == "INCONCLUSIVE_UNDERPOWERED"


# --- Phase 1 ---


def test_phase1_go() -> None:
    v = evaluate_phase1(_decomp(), _scorer(), _battery())
    assert v.verdict == "GO"


def test_phase1_invalid_scorer_residual() -> None:
    v = evaluate_phase1(
        _decomp(),
        _scorer(a2_residual_survives=False, a2_residual_ci_lower=-0.01),
        _battery(),
    )
    assert v.verdict == "INVALID_SCORER"


def test_phase1_invalid_battery_persona_collapse() -> None:
    v = evaluate_phase1(_decomp(), _scorer(), _battery(persona_collapse=True))
    assert v.verdict == "INVALID_TASK_BATTERY"


def test_phase1_inconclusive_underpowered() -> None:
    v = evaluate_phase1(_decomp(n_clusters=10), _scorer(), _battery())
    assert v.verdict == "INCONCLUSIVE_UNDERPOWERED"


def test_phase1_no_go_std_floor() -> None:
    v = evaluate_phase1(_decomp(delta_dq_std_ci_lower=0.10), _scorer(), _battery())
    assert v.verdict == "NO_GO_EFFECT_ABSENT"


def test_phase1_no_go_raw_floor() -> None:
    v = evaluate_phase1(_decomp(delta_dq=0.01), _scorer(), _battery())
    assert v.verdict == "NO_GO_EFFECT_ABSENT"


def test_phase1_no_go_non_monotone() -> None:
    v = evaluate_phase1(
        _decomp(monotone_supported=False, monotone_min_increment_ci_lower=-0.01),
        _scorer(),
        _battery(),
    )
    assert v.verdict == "NO_GO_EFFECT_ABSENT"


def test_phase1_no_go_garbage_rate() -> None:
    v = evaluate_phase1(
        _decomp(garbage_rate_by_condition={"A2": 0.5}), _scorer(), _battery()
    )
    assert v.verdict == "NO_GO_EFFECT_ABSENT"


def test_go_reason_states_actuator_sufficiency_scope() -> None:
    v = evaluate_phase1(_decomp(), _scorer(), _battery())
    reason = " ".join(v.reasons).lower()
    assert "actuator sufficiency" in reason
    assert "not walking" in reason or "not a re-proof" in reason or "not core" in reason
