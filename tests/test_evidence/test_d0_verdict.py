"""structural_status / R* branch logic (design-final.md §6), synthetic fixtures only.

Verdict *values* are never pinned elsewhere (circular re-baking guard) — this
file exhaustively covers the branch logic itself with hand-built
:class:`RungResult` / :class:`SmokeResult` fixtures, never a real generator
run.
"""

from __future__ import annotations

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import RungName, RungResult
from erre_sandbox.evidence.d0_substrate.smoke import SmokeResult
from erre_sandbox.evidence.d0_substrate.verdict_report import (
    evaluate_rung,
    render_structural_verdict,
)

_PASSING_SMOKE = SmokeResult(
    passed=True,
    monotone_gap_free=True,
    affordance_order_deterministic=True,
    position_round_trip_ok=True,
    move_msg_round_trip_ok=True,
    zone_transition_round_trip_ok=True,
    agent_update_schema_round_trip_ok=True,
    n_ticks=90,
    n_zone_transitions=1,
    n_affordance_events=0,
    reasons=(),
)

_FAILING_SMOKE = SmokeResult(
    passed=False,
    monotone_gap_free=False,
    affordance_order_deterministic=True,
    position_round_trip_ok=True,
    move_msg_round_trip_ok=True,
    zone_transition_round_trip_ok=True,
    agent_update_schema_round_trip_ok=True,
    n_ticks=90,
    n_zone_transitions=1,
    n_affordance_events=0,
    reasons=("physics tick delta not monotone/gap-free",),
)


def _rung_result(
    rung: RungName,
    *,
    n_valid_seeds: int = 64,
    median_estimand: float = 0.5,
    max_null: float = 0.0,
    ratio: float = 10.0,
    ci_lower: float = 0.3,
    null_ok: bool = True,
    control_ok: bool = True,
    control_value: float = 0.0,
    delta_median: float | None = 0.2,
    delta_ci_lower: float | None = 0.05,
    prop_fixture_valid: bool = True,
) -> RungResult:
    return RungResult(
        rung=rung,
        n_valid_seeds=n_valid_seeds,
        median_estimand=median_estimand,
        max_null=max_null,
        ratio=ratio,
        ci_lower=ci_lower,
        ci_upper=ci_lower + 0.1,
        null_ok=null_ok,
        control_ok=control_ok,
        control_value=control_value,
        delta_median=delta_median,
        delta_ci_lower=delta_ci_lower,
        prop_fixture_valid=prop_fixture_valid,
    )


def _passing_rung(rung: RungName) -> RungResult:
    return _rung_result(rung)


def _inconclusive_prop_gate_rung(rung: RungName) -> RungResult:
    return _rung_result(rung, prop_fixture_valid=False)


# --- evaluate_rung branch coverage ------------------------------------------


def test_evaluate_rung_pass_when_all_conditions_clear() -> None:
    verdict = evaluate_rung(_passing_rung("R1"))
    assert verdict.state == "PASS"
    assert verdict.reasons == ()


def test_evaluate_rung_inconclusive_prop_fixture_gate() -> None:
    verdict = evaluate_rung(_inconclusive_prop_gate_rung("R2"))
    assert verdict.state == "INCONCLUSIVE"


def test_evaluate_rung_inconclusive_too_few_valid_seeds() -> None:
    verdict = evaluate_rung(_rung_result("R0", n_valid_seeds=_c.MIN_VALID_SEEDS - 1))
    assert verdict.state == "INCONCLUSIVE"
    assert "valid seeds" in verdict.reasons[0]


def test_evaluate_rung_inconclusive_null_not_collapsed() -> None:
    verdict = evaluate_rung(_rung_result("R0", null_ok=False, max_null=0.9))
    assert verdict.state == "INCONCLUSIVE"
    assert "null" in verdict.reasons[0]


def test_evaluate_rung_inconclusive_control_not_collapsed() -> None:
    verdict = evaluate_rung(_rung_result("R1", control_ok=False, control_value=0.5))
    assert verdict.state == "INCONCLUSIVE"
    assert "control" in verdict.reasons[0]


def test_evaluate_rung_fail_below_floor() -> None:
    verdict = evaluate_rung(_rung_result("R0", median_estimand=0.01, ratio=0.2))
    assert verdict.state == "FAIL"
    assert any("floor" in r for r in verdict.reasons)


def test_evaluate_rung_fail_ci_straddles_zero() -> None:
    verdict = evaluate_rung(_rung_result("R0", ci_lower=-0.1))
    assert verdict.state == "FAIL"
    assert any("CI lower" in r for r in verdict.reasons)


def test_evaluate_rung_fail_anti_collapse_delta_below_floor() -> None:
    verdict = evaluate_rung(_rung_result("R1", delta_median=0.01, delta_ci_lower=0.001))
    assert verdict.state == "FAIL"
    assert any("Delta" in r for r in verdict.reasons)


def test_evaluate_rung_r0_ignores_delta_fields() -> None:
    """R0 has no anti-collapse gate; None deltas must not fail it."""
    verdict = evaluate_rung(_rung_result("R0", delta_median=None, delta_ci_lower=None))
    assert verdict.state == "PASS"


def test_evaluate_rung_r3_uses_closure_amp_floor() -> None:
    verdict = evaluate_rung(
        _rung_result("R3", median_estimand=_c.CLOSURE_AMP_FLOOR - 0.001)
    )
    assert verdict.state == "FAIL"


# --- render_structural_verdict branch coverage ------------------------------


def _all_pass(*, up_to: RungName = "R3") -> dict[RungName, RungResult]:
    order: tuple[RungName, ...] = ("R0", "R1", "R2", "R3")
    idx = order.index(up_to)
    results: dict[RungName, RungResult] = {}
    for i, rung in enumerate(order):
        if i <= idx:
            results[rung] = _passing_rung(rung)
        else:
            results[rung] = _rung_result(rung, median_estimand=0.0, ci_lower=-1.0)
    return results


def test_smoke_failure_forces_inconclusive_structural() -> None:
    verdict = render_structural_verdict(_all_pass(), _FAILING_SMOKE)
    assert verdict.structural_status == "INCONCLUSIVE_STRUCTURAL"
    assert verdict.r_star is None


def test_r0_apparatus_invalid_forces_inconclusive_structural() -> None:
    results = _all_pass()
    results["R0"] = _rung_result("R0", n_valid_seeds=1)
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "INCONCLUSIVE_STRUCTURAL"
    assert verdict.r_star is None


def test_r0_fail_gives_no_structural_floor_with_no_r_star() -> None:
    results = _all_pass()
    results["R0"] = _rung_result("R0", median_estimand=0.0, ci_lower=-1.0)
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "NO_STRUCTURAL_FLOOR"
    assert verdict.r_star is None


def test_r0_only_pass_gives_no_structural_floor() -> None:
    results = _all_pass(up_to="R0")
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "NO_STRUCTURAL_FLOOR"
    assert verdict.r_star == "R0"


def test_r1_pass_gives_structural_ready() -> None:
    results = _all_pass(up_to="R1")
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "STRUCTURAL_READY"
    assert verdict.r_star == "R1"


def test_r2_inconclusive_prop_gate_does_not_demote_structural_ready() -> None:
    """Honest default prediction (DA-D0S-1): R1 PASS + R2 prop-gate-blocked
    still yields STRUCTURAL_READY at R*=R1 (contiguity just stops there)."""
    results = _all_pass(up_to="R1")
    results["R2"] = _inconclusive_prop_gate_rung("R2")
    results["R3"] = _inconclusive_prop_gate_rung("R3")
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "STRUCTURAL_READY"
    assert verdict.r_star == "R1"


def test_full_ladder_pass_gives_r_star_r3() -> None:
    results = _all_pass(up_to="R3")
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.structural_status == "STRUCTURAL_READY"
    assert verdict.r_star == "R3"


def test_contiguity_break_at_r2_caps_r_star_at_r1_even_if_r3_would_pass() -> None:
    results = _all_pass(up_to="R1")
    results["R2"] = _rung_result("R2", median_estimand=0.0, ci_lower=-1.0)
    results["R3"] = _passing_rung("R3")  # would PASS on its own — must not count
    verdict = render_structural_verdict(results, _PASSING_SMOKE)
    assert verdict.r_star == "R1"
    assert verdict.structural_status == "STRUCTURAL_READY"


def test_claim_boundary_present_on_every_verdict() -> None:
    verdict = render_structural_verdict(_all_pass(), _PASSING_SMOKE)
    assert "G-GEAR runtime-ready" in verdict.claim_boundary
    assert "NOT Godot render-ready" in verdict.claim_boundary
