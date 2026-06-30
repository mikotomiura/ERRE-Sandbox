"""M13-ES4 control battery (§2.3 / §2.4 / §3) on synthetic data.

AUC / stratified AUC / held-out entropy residual / TOST equivalence / pre-flight
sampling-hash equivalence — all pure numpy, pinned with constructed inputs.
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es4_actuator.battery import load_adversarial_labeled
from erre_sandbox.evidence.es4_actuator.controls import (
    adversarial_judge_auc,
    auc,
    held_out_residual,
    preflight_sampling_hash,
    stratified_min_auc,
    tost_equivalence,
)


def test_auc_perfect_reversed_and_ties() -> None:
    assert auc([0.1, 0.2, 0.9, 1.0], [0, 0, 1, 1]) == 1.0  # positives score high
    assert auc([0.1, 0.2, 0.9, 1.0], [1, 1, 0, 0]) == 0.0  # positives score low
    assert auc([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1]) == 0.5  # all tied


def test_stratified_min_auc_takes_worst_level() -> None:
    scores = [0.1, 0.9, 0.9, 0.1]  # level A separates, level B is reversed
    labels = [0, 1, 0, 1]
    strata = ["A", "A", "B", "B"]
    assert stratified_min_auc(scores, labels, strata) == 0.0


def test_adversarial_auc_with_oracle_judge() -> None:
    items = load_adversarial_labeled()
    # Key on (object, text): the same text can be appropriate for one object and an
    # object-mismatch for another, so the judge must see the object too.
    label_by_key = {(it.object, it.text): it.label for it in items}

    def oracle(obj: str, text: str) -> float:
        return 1.0 if label_by_key[(obj, text)] == "appropriate" else 0.0

    assert adversarial_judge_auc(items, oracle) == 1.0


def test_held_out_residual_survives_when_lambda_effect_beyond_entropy() -> None:
    n = 40
    hi = np.array([1, 0] * (n // 2))
    dq = np.where(hi == 1, 0.5, 0.0).astype(float)
    h = np.zeros(n)  # entropy carries no information here
    holdout = np.array([1, 1, 0, 0] * (n // 4))
    res = held_out_residual(dq.tolist(), h.tolist(), hi.tolist(), holdout.tolist())
    assert res.survives
    assert res.residual_ci_lower > 0.0


def test_held_out_residual_dies_when_dq_is_entropy() -> None:
    rng = np.random.default_rng(7)
    n = 60
    h = rng.uniform(0.0, 1.0, n)
    hi = np.array([1, 0] * (n // 2))  # λ indicator independent of the entropy proxy
    dq = 0.6 * h + rng.normal(0.0, 0.2, n)  # DQ carries entropy + λ-independent noise
    holdout = np.array([1, 1, 0, 0] * (n // 4))
    res = held_out_residual(dq.tolist(), h.tolist(), hi.tolist(), holdout.tolist())
    assert not res.survives  # after partialling H, no λ effect survives


def test_tost_equivalent_for_matched_and_not_for_separated() -> None:
    # N large enough that the difference CI is tighter than the 0.15-SD margin.
    rng = np.random.default_rng(0)
    a = rng.normal(0.5, 0.08, 800)
    matched = rng.normal(0.5, 0.08, 800)
    separated = rng.normal(0.9, 0.08, 800)
    assert tost_equivalence(a.tolist(), matched.tolist()).equivalent
    assert not tost_equivalence(a.tolist(), separated.tolist()).equivalent


def test_preflight_sampling_hash_passes() -> None:
    result = preflight_sampling_hash()
    assert result.loco_zero_equals_none
    assert result.m2_matches_a2_distribution
    assert result.ok
    assert result.max_abs_temp_diff <= 1e-9
