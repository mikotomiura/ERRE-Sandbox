"""Verdict logic tests: INCONCLUSIVE-first conjunctive branches (§4).

Exercises the decision logic over **synthetic** decomposition / control inputs so
each branch is pinned deterministically. The real run's verdict value is **never**
pinned (forking-paths guard); only the apparatus mechanics and the branch logic.
"""

from __future__ import annotations

from erre_sandbox.evidence.es3_locomotion import constants as _c
from erre_sandbox.evidence.es3_locomotion.controls import ControlResults
from erre_sandbox.evidence.es3_locomotion.decomposition import Decomposition
from erre_sandbox.evidence.es3_locomotion.verdict_report import evaluate_verdict


def _decomp(**overrides: object) -> Decomposition:
    """A baseline *valid, GO-capable* decomposition; override one field per test."""
    defaults: dict[str, object] = {
        "cells": (),
        "n_cells": 15,
        "n_headroom_valid": 15,
        "headroom_valid_fraction": 1.0,
        "n_n_valid": 15,
        "n_spread_valid": 15,
        "n_measurement_valid": 15,
        "d_loco": 0.05,
        "max_repeat_penalty_var": 0.0,
        "per_seed_d_loco": tuple([0.05] * 40),  # CI ≈ [0.05, 0.05] ≥ AMP_FLOOR
        "n_valid_walk_seeds": 40,
        "n_top_p_headroom_valid": 5,
        "median_top_p_amplitude": 0.01,
    }
    defaults.update(overrides)
    return Decomposition(**defaults)  # type: ignore[arg-type]


def _controls(**overrides: object) -> ControlResults:
    defaults: dict[str, object] = {
        "ablation_bit_equal": True,
        "ablation_max_abs_diff": 0.0,
        "zone_function_d_loco": 0.0,
        "n_hist_history_shuffle_d_loco": 0.05,
        "n_hist_lambda_shuffle_d_loco": 0.05,
    }
    defaults.update(overrides)
    return ControlResults(**defaults)  # type: ignore[arg-type]


def test_go_when_valid_and_ci_clears_floor() -> None:
    v = evaluate_verdict(_decomp(), _controls())
    assert v.verdict == "GO"
    assert v.ci_lower >= _c.AMP_FLOOR


def test_no_go_when_effective_modulation_below_floor() -> None:
    # Headroom sufficient, apparatus valid, but D_loco far below AMP_FLOOR.
    v = evaluate_verdict(
        _decomp(d_loco=0.005, per_seed_d_loco=tuple([0.005] * 40)),
        _controls(),
    )
    assert v.verdict == "NO_GO"
    assert v.ci_lower < _c.AMP_FLOOR


def test_inconclusive_few_walk_seeds() -> None:
    v = evaluate_verdict(
        _decomp(n_valid_walk_seeds=10, per_seed_d_loco=tuple([0.05] * 10)),
        _controls(),
    )
    assert v.verdict == "INCONCLUSIVE"
    assert "MIN_WALK_SEEDS" in v.reasons[0]


def test_inconclusive_few_headroom_valid_cells() -> None:
    v = evaluate_verdict(_decomp(n_headroom_valid=3), _controls())
    assert v.verdict == "INCONCLUSIVE"
    assert "headroom-valid cells" in v.reasons[0]


def test_inconclusive_low_lambda_spread() -> None:
    v = evaluate_verdict(_decomp(n_spread_valid=2), _controls())
    assert v.verdict == "INCONCLUSIVE"
    assert "spread" in v.reasons[0]


def test_inconclusive_headroom_saturated_fraction() -> None:
    v = evaluate_verdict(_decomp(headroom_valid_fraction=0.2), _controls())
    assert v.verdict == "INCONCLUSIVE"
    assert "HEADROOM_VALID_FRAC" in v.reasons[0]


def test_inconclusive_ablation_not_bit_equal() -> None:
    v = evaluate_verdict(
        _decomp(),
        _controls(ablation_bit_equal=False, ablation_max_abs_diff=0.1),
    )
    assert v.verdict == "INCONCLUSIVE"
    assert "ablation" in v.reasons[0]


def test_inconclusive_zone_function_control_nonzero() -> None:
    v = evaluate_verdict(_decomp(), _controls(zone_function_d_loco=0.04))
    assert v.verdict == "INCONCLUSIVE"
    assert "zone-function" in v.reasons[0]


def test_inconclusive_repeat_penalty_not_invariant() -> None:
    v = evaluate_verdict(_decomp(max_repeat_penalty_var=0.01), _controls())
    assert v.verdict == "INCONCLUSIVE"
    assert "repeat_penalty" in v.reasons[0]


def test_inconclusive_precedes_no_go() -> None:
    """An invalid apparatus with a low D_loco is INCONCLUSIVE, never NO_GO."""
    v = evaluate_verdict(
        _decomp(d_loco=0.005, per_seed_d_loco=tuple([0.005] * 40)),
        _controls(ablation_bit_equal=False, ablation_max_abs_diff=0.2),
    )
    assert v.verdict == "INCONCLUSIVE"


def test_full_apparatus_ablation_is_bit_equal() -> None:
    """End-to-end: the real control battery confirms the ablation identity."""
    from erre_sandbox.evidence.es3_locomotion.controls import ablation_identity
    from erre_sandbox.evidence.es3_locomotion.scenario import default_seed_bank

    bit_equal, max_diff = ablation_identity(default_seed_bank())
    assert bit_equal
    assert max_diff <= _c.ZERO_TOL
