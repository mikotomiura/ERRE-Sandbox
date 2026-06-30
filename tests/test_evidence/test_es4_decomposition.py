"""M13-ES4 cluster-paired ΔDQ decomposition (§2.2 / §4.2), fixed-seed synthetic data.

Pins the paired δ_c contrast, the standardised ΔDQ_std, the cluster bootstrap CI
and the dose-monotonicity contrast on constructed scores (no LLM, no encoder).
"""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es4_actuator.decomposition import ScoredUnit, decompose
from erre_sandbox.evidence.es4_actuator.scoring import GenerationScore


def _score(
    dq: float, *, is_garbage: bool = False, empty: bool = False
) -> GenerationScore:
    n_valid = 0 if (is_garbage or empty) else 3
    return GenerationScore(
        n_parsed=0 if empty else 3,
        n_valid=n_valid,
        empty=empty,
        parse_fail=False,
        is_garbage=is_garbage,
        dq=dq,
        dispersion=0.0,
        h_proxy=1.0,
    )


def _units(
    cluster_means: dict[tuple[str, str], tuple[float, float, float]],
    n_seed: int = 5,
) -> list[ScoredUnit]:
    """One ScoredUnit per (cluster, condition, seed) at the given A0/A1/A2 mean."""
    units: list[ScoredUnit] = []
    for (persona, item), (m0, m1, m2) in cluster_means.items():
        for cond, mean in (("A0", m0), ("A1", m1), ("A2", m2)):
            units.extend(
                ScoredUnit(persona, item, cond, s, _score(mean)) for s in range(n_seed)
            )
    return units


def test_delta_dq_is_mean_paired_contrast() -> None:
    means = {
        ("kant", "brick"): (0.2, 0.4, 0.6),  # δ = 0.4
        ("kant", "key"): (0.2, 0.3, 0.4),  # δ = 0.2
    }
    decomp = decompose(_units(means), bootstrap_seed=0)
    assert decomp.n_clusters == 2
    assert decomp.delta_dq == 0.3  # mean(0.4, 0.2)
    assert {round(c.delta, 6) for c in decomp.clusters} == {0.4, 0.2}


def test_delta_dq_std_positive_when_deltas_vary() -> None:
    means = {
        ("p", "a"): (0.2, 0.4, 0.6),
        ("p", "b"): (0.1, 0.3, 0.5),
        ("p", "c"): (0.0, 0.4, 0.8),
    }
    decomp = decompose(_units(means), bootstrap_seed=1)
    sd = float(np.std([c.delta for c in decomp.clusters], ddof=1))
    assert decomp.delta_dq_std == decomp.delta_dq / sd
    assert decomp.delta_dq_std > 0.0


def test_monotone_supported_for_increasing_dose() -> None:
    means = {("p", f"i{k}"): (0.1, 0.3, 0.5) for k in range(6)}
    decomp = decompose(_units(means), bootstrap_seed=2)
    assert decomp.monotone_supported
    assert decomp.monotone_min_increment_ci_lower > 0.0


def test_monotone_not_supported_when_a1_below_a0() -> None:
    means = {("p", f"i{k}"): (0.5, 0.2, 0.6) for k in range(6)}  # A1 < A0
    decomp = decompose(_units(means), bootstrap_seed=3)
    assert not decomp.monotone_supported


def test_positive_effect_has_positive_ci_lower() -> None:
    means = {("p", f"i{k}"): (0.10, 0.30, 0.50) for k in range(8)}
    decomp = decompose(_units(means), bootstrap_seed=4)
    assert decomp.delta_dq_ci_lower > 0.0
    assert decomp.delta_dq_ci_lower <= decomp.delta_dq <= decomp.delta_dq_ci_upper


def test_garbage_and_divergence_aggregates() -> None:
    units = _units({("p", "a"): (0.2, 0.3, 0.4)}, n_seed=4)
    # make all A2 generations garbage
    units = [
        ScoredUnit(
            u.persona_id,
            u.item_id,
            u.condition,
            u.seed_idx,
            _score(0.0, is_garbage=True),
        )
        if u.condition == "A2"
        else u
        for u in units
    ]
    decomp = decompose(units)
    assert decomp.garbage_rate_by_condition["A2"] == 1.0
    assert decomp.garbage_rate_by_condition["A0"] == 0.0
    # A2 valid-rate collapses to 0 → cross-condition divergence is large
    assert decomp.cross_condition_valid_divergence >= 0.9
