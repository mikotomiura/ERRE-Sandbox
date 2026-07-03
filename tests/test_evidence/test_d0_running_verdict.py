"""Running verdict branch logic (design-final.md §6), synthetic fixtures only.

Verdict *values* of a real run are never pinned (circular re-baking guard) —
this file covers the INCONCLUSIVE-first branch logic + claim_scope decision
with hand-built fixtures, never a real generator run.
"""

from __future__ import annotations

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import RungName, RungResult
from erre_sandbox.evidence.d0_substrate.running.forensic import ForensicReport
from erre_sandbox.evidence.d0_substrate.running.runningness import RunningnessResult
from erre_sandbox.evidence.d0_substrate.running.verdict_running import (
    render_running_verdict,
)


def _rr(
    rung: RungName,
    *,
    median: float = 0.5,
    max_null: float = 0.0,
    ratio: float = 10.0,
    ci_lower: float = 0.3,
    null_ok: bool = True,
    control_ok: bool = True,
    control_value: float = 0.0,
    delta_median: float | None = 0.2,
    delta_ci_lower: float | None = 0.05,
    prop_fixture_valid: bool = True,
    n_valid: int = 64,
) -> RungResult:
    return RungResult(
        rung=rung,
        n_valid_seeds=n_valid,
        median_estimand=median,
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


def _rungs(r0: RungResult, r1: RungResult) -> dict[RungName, RungResult]:
    # R2/R3 are prop-fixture-gated INCONCLUSIVE on the frozen sparse fixture, so
    # contiguity stops at R1 (R* = R1 when R0 & R1 PASS).
    return {
        "R0": r0,
        "R1": r1,
        "R2": _rr("R2", prop_fixture_valid=False),
        "R3": _rr("R3", prop_fixture_valid=False),
    }


def _running(*, gate_pass: bool = True, tv_ci_lower: float = 0.3) -> RunningnessResult:
    return RunningnessResult(
        tv_ci_lower=tv_ci_lower,
        tv_median=tv_ci_lower,
        gate_pass=gate_pass,
        n_seeds=64,
        per_seed_tv=(),
        tv_ci_lower_indep_baseline=0.2,
        tv_ci_lower_other_cloud_baseline=0.2,
        n_forage_events=100,
    )


def _forensic(*, prop_free_zone_delta1: float = 0.2) -> ForensicReport:
    return ForensicReport(
        within_zone_geometry_present=True,
        within_zone_arm_distance_median=1.0,
        topk_zone_saturated=0.0,
        clamp_rate=0.1,
        per_zone_memory_count={},
        per_zone_delta1_contribution={},
        prop_free_zone_delta1=prop_free_zone_delta1,
        memoryless_r1_pass=True,
        memoryless_running_tv_ci_lower=0.0,
        spontaneous_r1_pass=False,
        spontaneous_median_delta1=0.0,
        spontaneous_terminal_zone_memory_count=4.0,
        no_reflect_r1_pass=True,
        uniform_centroid_r1_pass=True,
        top1_centroid_r1_pass=True,
    )


def _render(
    rungs: dict[RungName, RungResult],
    *,
    frozen_r_star: RungName | None = "R0",
    runningness: RunningnessResult | None = None,
    replay_ok: bool = True,
    max_d1: float = 0.5,
):
    return render_running_verdict(
        rungs,
        frozen_r_star=frozen_r_star,
        runningness=runningness or _running(),
        forensic=_forensic(),
        replay_checksum="deadbeef",
        replay_ok=replay_ok,
        max_d1=max_d1,
    )


def test_replay_mismatch_is_inconclusive() -> None:
    v = _render(_rungs(_rr("R0"), _rr("R1")), replay_ok=False)
    assert v.structural_status_running == "INCONCLUSIVE_RUNNING"
    assert v.running_r_star is None


def test_gate_fail_is_inconclusive() -> None:
    v = _render(_rungs(_rr("R0"), _rr("R1")), runningness=_running(gate_pass=False))
    assert v.structural_status_running == "INCONCLUSIVE_RUNNING"


def test_d1_degenerate_is_inconclusive() -> None:
    # Gate + replay OK but arms never diverge (max_d1 = 0) => degenerate readout,
    # distinct from NO_STRUCTURAL_FLOOR (design-final.md §2.3 failure-3).
    v = _render(_rungs(_rr("R0"), _rr("R1")), max_d1=0.0)
    assert v.structural_status_running == "INCONCLUSIVE_RUNNING"
    assert v.d1_degenerate is True


def test_r0_apparatus_invalid_is_inconclusive() -> None:
    v = _render(_rungs(_rr("R0", null_ok=False), _rr("R1")))
    assert v.structural_status_running == "INCONCLUSIVE_RUNNING"


def test_r0_floor_fail_is_no_structural_floor() -> None:
    v = _render(_rungs(_rr("R0", median=0.0, ratio=0.0), _rr("R1")))
    assert v.structural_status_running == "NO_STRUCTURAL_FLOOR_RUNNING"


def test_r1_fail_is_no_structural_floor() -> None:
    # R0 PASS but R1 fails its anti-collapse floor => R* = R0 < R1.
    v = _render(_rungs(_rr("R0"), _rr("R1", delta_median=0.0, delta_ci_lower=0.0)))
    assert v.structural_status_running == "NO_STRUCTURAL_FLOOR_RUNNING"
    assert v.running_r_star == "R0"


def test_r1_pass_with_paired_contrast_is_structural_ready() -> None:
    v = _render(_rungs(_rr("R0"), _rr("R1")), frozen_r_star="R0")
    assert v.structural_status_running == "STRUCTURAL_READY_RUNNING"
    assert v.running_r_star == "R1"


def test_paired_contrast_not_corroborated_is_no_structural_floor() -> None:
    # Same running R* = R1, but the frozen (blind) apparatus already reaches R1
    # => the advance is not attributable to running-ness (design-final.md §4.3).
    v = _render(_rungs(_rr("R0"), _rr("R1")), frozen_r_star="R1")
    assert v.structural_status_running == "NO_STRUCTURAL_FLOOR_RUNNING"


def test_frozen_r_star_none_is_not_corroborated() -> None:
    # Blind apparatus INCONCLUSIVE / R0-fail => frozen_r_star=None must NOT be
    # coerced to "R0" and falsely corroborate the paired contrast (Codex HIGH-2).
    v = _render(_rungs(_rr("R0"), _rr("R1")), frozen_r_star=None)
    assert v.structural_status_running == "NO_STRUCTURAL_FLOOR_RUNNING"


def test_short_seed_bank_is_inconclusive() -> None:
    # Explicit n_valid < MIN_VALID_SEEDS guard (code-reviewer HIGH-2).
    v = _render(_rungs(_rr("R0", n_valid=8), _rr("R1", n_valid=8)))
    assert v.structural_status_running == "INCONCLUSIVE_RUNNING"


def test_claim_scope_always_embeds_unconditional_caveat() -> None:
    v = _render(_rungs(_rr("R0"), _rr("R1")))
    assert "runningness_certified_separately_by_gate" in v.claim_scope
    assert "return_to_home_errand" in v.claim_scope


def test_claim_scope_narrows_to_chashitsu_when_prop_free_delta_below_floor() -> None:
    verdict_5zone = render_running_verdict(
        _rungs(_rr("R0"), _rr("R1")),
        frozen_r_star="R0",
        runningness=_running(),
        forensic=_forensic(prop_free_zone_delta1=_c.RESIDUAL_JACCARD_FLOOR),
        replay_checksum="x",
        replay_ok=True,
        max_d1=0.5,
    )
    verdict_chashitsu = render_running_verdict(
        _rungs(_rr("R0"), _rr("R1")),
        frozen_r_star="R0",
        runningness=_running(),
        forensic=_forensic(prop_free_zone_delta1=0.0),
        replay_checksum="x",
        replay_ok=True,
        max_d1=0.5,
    )
    assert "scope=5zone" in verdict_5zone.claim_scope
    assert "scope=chashitsu_prop_local_only" in verdict_chashitsu.claim_scope
