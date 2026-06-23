"""Unit tests for the frozen SPDM Gate-2 verdict branches (DA-SPDM-5).

Synthetic :class:`SeedResult` lists exercise each GO / NO_GO / INCONCLUSIVE path
without building the full retrieval apparatus (that round-trip is covered by
``test_spdm_probe.py``).
"""

from __future__ import annotations

from erre_sandbox.evidence.spdm.probe import SeedResult
from erre_sandbox.evidence.spdm.verdict_report import Gate1Result, evaluate_gate2


def _healthy_gate1() -> Gate1Result:
    return Gate1Result(
        single_query_distance=0.5,
        location_shuffle_null=0.05,
        ablation_w0_distance=0.0,
        zone_free_distance=0.5,
        zone_free_null=0.05,
    )


def _seeds(
    n: int,
    *,
    d_obs: float,
    d_perm: float = 0.03,
    d_w0: float = 0.0,
    d_sl_on: float = 0.30,
    d_sl_off: float = 0.30,
    valid: bool = True,
) -> list[SeedResult]:
    return [
        SeedResult(
            seed=i,
            d_obs=d_obs,
            d_null_permutation=d_perm,
            d_null_w0=d_w0,
            d_control_same_loc_on=d_sl_on,
            d_control_same_loc_off=d_sl_off,
            valid=valid,
        )
        for i in range(n)
    ]


def test_go_when_all_conditions_met() -> None:
    v = evaluate_gate2(_seeds(8, d_obs=0.45), _healthy_gate1(), n_queries=12)
    assert v.verdict == "GO"


def test_gate1_failure_is_inconclusive_not_no_go() -> None:
    bad_gate1 = Gate1Result(
        single_query_distance=0.05,  # ratio < R_MIN
        location_shuffle_null=0.05,
        ablation_w0_distance=0.0,
        zone_free_distance=0.05,
        zone_free_null=0.05,
    )
    v = evaluate_gate2(_seeds(8, d_obs=0.45), bad_gate1, n_queries=12)
    assert v.verdict == "INCONCLUSIVE"
    assert any("Gate 1" in r for r in v.reasons)


def test_low_query_count_is_inconclusive() -> None:
    v = evaluate_gate2(_seeds(8, d_obs=0.45), _healthy_gate1(), n_queries=11)
    assert v.verdict == "INCONCLUSIVE"
    assert any("query battery" in r for r in v.reasons)


def test_too_few_valid_seeds_is_inconclusive() -> None:
    v = evaluate_gate2(_seeds(4, d_obs=0.45), _healthy_gate1(), n_queries=12)
    assert v.verdict == "INCONCLUSIVE"
    assert any("valid seeds" in r for r in v.reasons)


def test_w0_non_collapse_is_apparatus_invalid_inconclusive() -> None:
    # ④ content-only floor did not collapse ⇒ canonical-id metric / fixture broken.
    v = evaluate_gate2(_seeds(8, d_obs=0.45, d_w0=0.5), _healthy_gate1(), n_queries=12)
    assert v.verdict == "INCONCLUSIVE"
    assert any("did not collapse" in r for r in v.reasons)


def test_noisy_observed_arm_is_inconclusive() -> None:
    # Large cross-seed swing in D_obs against a tight null ⇒ noise downgrade.
    seeds = [
        SeedResult(
            seed=i,
            d_obs=d,
            d_null_permutation=0.03,
            d_null_w0=0.02,
            d_control_same_loc_on=0.30,
            d_control_same_loc_off=0.30,
        )
        for i, d in enumerate([0.11, 0.95, 0.12, 0.93, 0.10, 0.99, 0.15, 0.90])
    ]
    v = evaluate_gate2(seeds, _healthy_gate1(), n_queries=12)
    assert v.verdict == "INCONCLUSIVE"
    assert any("too noisy" in r for r in v.reasons)


def test_thin_effect_is_no_go_not_go() -> None:
    # ratio passes (0.05 / 0.02 = 2.5) but median D_obs < practical floor (HIGH-5).
    v = evaluate_gate2(
        _seeds(8, d_obs=0.05, d_perm=0.02, d_w0=0.02),
        _healthy_gate1(),
        n_queries=12,
    )
    assert v.verdict == "NO_GO"
    assert any("practical floor" in r for r in v.reasons)


def test_insufficient_ratio_is_no_go() -> None:
    # median D_obs clears the floor but the null is nearly as large ⇒ ratio < R_MIN.
    v = evaluate_gate2(
        _seeds(8, d_obs=0.15, d_perm=0.12, d_w0=0.0),
        _healthy_gate1(),
        n_queries=12,
    )
    assert v.verdict == "NO_GO"
    assert any("ratio" in r for r in v.reasons)


def test_positive_control_failure_is_no_go() -> None:
    # Strong D_obs but the w0 floor is also high ⇒ ② location-driven control fails
    # (divergence not attributable to location). w0=0.09 stays under the collapse
    # gate (0.10) so this is a NO_GO, not apparatus-invalid.
    v = evaluate_gate2(
        _seeds(8, d_obs=0.16, d_perm=0.02, d_w0=0.09),
        _healthy_gate1(),
        n_queries=12,
    )
    assert v.verdict == "NO_GO"
    assert any("positive control" in r for r in v.reasons)


def test_no_spurious_control_failure_is_no_go() -> None:
    # ③ spatial term injects separation on co-located memories beyond tolerance.
    v = evaluate_gate2(
        _seeds(8, d_obs=0.45, d_sl_on=0.50, d_sl_off=0.30),
        _healthy_gate1(),
        n_queries=12,
    )
    assert v.verdict == "NO_GO"
    assert any("no-spurious" in r for r in v.reasons)


def test_verdict_carries_forensic_statistics() -> None:
    v = evaluate_gate2(_seeds(8, d_obs=0.45), _healthy_gate1(), n_queries=12)
    assert v.n_valid_seeds == 8
    assert v.n_queries == 12
    assert v.max_verdict_null >= 0.0
    assert v.ci_upper >= v.ci_lower
