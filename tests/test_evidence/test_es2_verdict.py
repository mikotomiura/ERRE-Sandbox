"""Verdict branch logic for the ES-2 apparatus (§9 INCONCLUSIVE gate + §10).

These tests drive :func:`evaluate_verdict` with **synthetic** ``SeedResult`` lists
to exercise each INCONCLUSIVE trigger and the GO / NO_GO / INCONCLUSIVE split.
They do **not** pin the apparatus's actual verdict value (that is produced once by
``scripts/es2_verdict_run.py`` and recorded in ``.steering/``); they pin only the
decision *logic* over pre-frozen thresholds. The Codex H5 bootstrap-unit property
(the CI is taken over per-seed deltas, never ``N_PERM``) is also pinned here.
"""

from __future__ import annotations

from erre_sandbox.evidence.es2_replay import constants as _c
from erre_sandbox.evidence.es2_replay.verdict_report import (
    SeedResult,
    evaluate_verdict,
)


def _seed(idx: int, **overrides: float | bool) -> SeedResult:
    """A baseline seed that satisfies every GO condition; override to perturb."""
    base: dict[str, float | int | bool] = {
        "seed": idx,
        "valid": True,
        "d_obs": 0.50,
        "null_q_a": 0.20,
        "delta_a": 0.30,
        "null_q_b": 0.20,
        "delta_b": 0.30,
        "novel_transition_rate": 0.90,
        "exact_de_novo_rate": 0.90,
        "temporal_novel_rate": 0.0,
        "n_denovo_a": 1000,
        "n_denovo_b": 1000,
        "effective_zones_a": 3,
        "effective_zones_b": 3,
        "d_self": 0.0,
        "no_spurious_margin": 0.0,
        "var_cosine": 0.06,
    }
    base.update(overrides)
    return SeedResult(**base)  # type: ignore[arg-type]


def _bank(n: int, **overrides: float | bool) -> list[SeedResult]:
    return [_seed(i, **overrides) for i in range(n)]


def test_all_conditions_met_is_go() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS))
    assert v.verdict == "GO"


def test_too_few_valid_seeds_is_inconclusive() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS - 1))
    assert v.verdict == "INCONCLUSIVE"
    assert "MIN_VALID_SEEDS" in v.reasons[0]


def test_absent_competition_is_inconclusive() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, var_cosine=0.0))
    assert v.verdict == "INCONCLUSIVE"
    assert "competition" in v.reasons[0]


def test_insufficient_denovo_seeds_is_inconclusive() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, n_denovo_a=10, n_denovo_b=10))
    assert v.verdict == "INCONCLUSIVE"
    assert "de-novo" in v.reasons[0]


def test_degenerate_trajectory_is_inconclusive() -> None:
    v = evaluate_verdict(
        _bank(_c.MIN_VALID_SEEDS, effective_zones_a=1, effective_zones_b=1)
    )
    assert v.verdict == "INCONCLUSIVE"
    assert "effective zones" in v.reasons[0]


def test_temporal_control_not_failing_is_inconclusive() -> None:
    # Temporal-replay control must fall below the novelty floor; if it does not, the
    # novelty test is vacuous ⇒ apparatus invalid ⇒ INCONCLUSIVE (Codex H3).
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, temporal_novel_rate=0.5))
    assert v.verdict == "INCONCLUSIVE"
    assert "temporal-replay" in v.reasons[0]


def test_split_half_noise_gate_is_inconclusive() -> None:
    # median(D_obs) <= 1.5 * max(median(D_self), FLOOR_REL) ⇒ cross-agent JS does not
    # exceed within-agent split-half sampling noise (self-calibrating, Codex H1/H6).
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, d_obs=0.50, d_self=0.50))
    assert v.verdict == "INCONCLUSIVE"
    assert "split-half noise gate" in v.reasons[0]


def test_negative_path_dependence_is_no_go() -> None:
    # Adequate power, valid apparatus, tight null, but N-a CI lower <= 0 ⇒ a
    # progressive NO_GO (not INCONCLUSIVE).
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, delta_a=-0.20, null_q_a=0.70))
    assert v.verdict == "NO_GO"
    assert any("CI lower" in r for r in v.reasons)


def test_novelty_floor_unmet_is_no_go() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, novel_transition_rate=0.05))
    assert v.verdict == "NO_GO"
    assert any("novel-transition" in r for r in v.reasons)


def test_no_spurious_margin_breach_is_no_go() -> None:
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, no_spurious_margin=0.20))
    assert v.verdict == "NO_GO"
    assert any("no-spurious" in r for r in v.reasons)


def test_bootstrap_unit_is_the_scenario_seed_not_n_perm() -> None:
    # Codex H5: the CI is bootstrapped over the per-seed deltas only. With a constant
    # delta across the seed bank the CI collapses to that delta (no spurious width
    # from a permutation-count sample size — N_PERM is not even an input here).
    v = evaluate_verdict(_bank(_c.MIN_VALID_SEEDS, delta_a=0.30))
    assert abs(v.ci_lower - 0.30) < 1e-9
    assert abs(v.ci_upper - 0.30) < 1e-9
