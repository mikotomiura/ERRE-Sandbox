"""Cluster-level paired ΔDQ estimand + bootstrap CI (§2.2 / §4.2, Codex HIGH-8).

The primary statistic is the **cluster-level paired** divergent-quality contrast,
where a cluster is ``(persona, item)`` and the seeds are **common** across A0/A2:

* per cluster ``c``: ``δ_c = mean_seed [DQ(A2; seed) − DQ(A0; seed)]`` (paired on
  the common seed — the seed cancels, halving variance);
* ``ΔDQ = mean_c δ_c`` (raw effect, in cosine-rarity units);
* ``ΔDQ_std = ΔDQ / SD_c(δ_c)`` (standardised across the **48** clusters — the
  effective N, *not* the seed count, which only sharpens each cluster mean).

The bootstrap resamples **clusters** (``hierarchical_bootstrap_ci`` discipline:
the effective sample size is the cluster count, so precision is not inflated by
seeds). Dose monotonicity (A0 ≤ A1 ≤ A2) is a **cluster bootstrap monotone
contrast** (§8.4, Codex M-6 — replaces Jonckheere). Supporting / forensic
quantities (fluency V, garbage rate, empty/parse rate, intra-list dispersion,
cross-condition selection-bias divergence) are aggregated here too but never enter
the primary CI. numpy / stdlib only; verdict-blind.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
from erre_sandbox.evidence.es4_actuator import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.es4_actuator.scoring import GenerationScore

_PRIMARY_CONDITIONS = ("A0", "A1", "A2")


@dataclass(frozen=True)
class ScoredUnit:
    """One scored AUT generation with its cell coordinates (decomposition input)."""

    persona_id: str
    item_id: str
    condition: str
    seed_idx: int
    score: GenerationScore


@dataclass(frozen=True)
class ClusterContrast:
    """Per ``(persona, item)`` cluster paired readout."""

    persona_id: str
    item_id: str
    n_paired: int
    delta: float
    """``δ_c`` = mean over common seeds of ``DQ(A2) − DQ(A0)``."""
    mean_dq_a0: float
    mean_dq_a1: float
    mean_dq_a2: float


@dataclass(frozen=True)
class Decomposition:
    """Cluster-paired estimand + supporting aggregates."""

    clusters: tuple[ClusterContrast, ...]
    n_clusters: int
    delta_dq: float
    delta_dq_std: float
    delta_dq_ci_lower: float
    delta_dq_ci_upper: float
    delta_dq_std_ci_lower: float
    monotone_supported: bool
    monotone_min_increment_ci_lower: float
    fluency_by_condition: dict[str, float]
    garbage_rate_by_condition: dict[str, float]
    empty_parse_rate_by_condition: dict[str, float]
    dispersion_by_condition: dict[str, float]
    cross_condition_valid_divergence: float
    cross_condition_missing_divergence: float


def _by_cell(
    units: Sequence[ScoredUnit],
) -> dict[tuple[str, str, str], dict[int, float]]:
    """``(persona, item, condition) → {seed_idx: dq}``."""
    out: dict[tuple[str, str, str], dict[int, float]] = defaultdict(dict)
    for u in units:
        out[(u.persona_id, u.item_id, u.condition)][u.seed_idx] = u.score.dq
    return out


def _cluster_contrasts(units: Sequence[ScoredUnit]) -> list[ClusterContrast]:
    cells = _by_cell(units)
    clusters: dict[tuple[str, str], None] = {}
    for persona_id, item_id, _condition in cells:
        clusters[(persona_id, item_id)] = None
    out: list[ClusterContrast] = []
    for persona_id, item_id in clusters:
        a0 = cells.get((persona_id, item_id, "A0"), {})
        a1 = cells.get((persona_id, item_id, "A1"), {})
        a2 = cells.get((persona_id, item_id, "A2"), {})
        common = sorted(set(a0) & set(a2))
        paired = [a2[s] - a0[s] for s in common]
        out.append(
            ClusterContrast(
                persona_id=persona_id,
                item_id=item_id,
                n_paired=len(paired),
                delta=float(np.mean(paired)) if paired else 0.0,
                mean_dq_a0=float(np.mean(list(a0.values()))) if a0 else 0.0,
                mean_dq_a1=float(np.mean(list(a1.values()))) if a1 else 0.0,
                mean_dq_a2=float(np.mean(list(a2.values()))) if a2 else 0.0,
            )
        )
    return out


def _std_ci_lower(deltas: np.ndarray, seed: int) -> float:
    """One-sided-relevant lower bound of ``ΔDQ_std`` over a cluster bootstrap."""
    n = deltas.size
    if n < 2:  # noqa: PLR2004 — SD needs ≥2 clusters
        return 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(_c.N_RESAMPLES, n))
    samples = deltas[idx]
    means = samples.mean(axis=1)
    sds = samples.std(axis=1, ddof=1)
    stds = np.divide(means, sds, out=np.zeros_like(means), where=sds > 0.0)
    return float(np.quantile(stds, _c.CI_ALPHA / 2.0))


def _monotone_ci_lower(clusters: Sequence[ClusterContrast], seed: int) -> float:
    """Lower CI of the **minimum** dose increment ``min(A1−A0, A2−A1)`` over clusters.

    ``> 0`` ⇒ the bootstrap supports a strictly monotone A0 ≤ A1 ≤ A2 dose
    response (Codex M-6 cluster monotone contrast).
    """
    inc = np.array(
        [
            min(c.mean_dq_a1 - c.mean_dq_a0, c.mean_dq_a2 - c.mean_dq_a1)
            for c in clusters
        ],
        dtype=float,
    )
    n = inc.size
    if n == 0:
        return 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(_c.N_RESAMPLES, n))
    means = inc[idx].mean(axis=1)
    return float(np.quantile(means, _c.CI_ALPHA / 2.0))


def _missing(score: GenerationScore) -> bool:
    """Effectively missing for DQ: empty / parse-fail / V < 2 (→ DQ floored to 0)."""
    return score.empty or score.parse_fail or score.n_valid < _c.MIN_VALID_IDEAS_FOR_DQ


def _condition_means(
    units: Sequence[ScoredUnit],
) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
]:
    by_cond: dict[str, list[ScoredUnit]] = defaultdict(list)
    for u in units:
        by_cond[u.condition].append(u)
    fluency: dict[str, float] = {}
    garbage: dict[str, float] = {}
    empty_parse: dict[str, float] = {}
    dispersion: dict[str, float] = {}
    valid_rate: dict[str, float] = {}
    for cond, us in by_cond.items():
        fluency[cond] = float(np.mean([u.score.n_valid for u in us]))
        garbage[cond] = float(np.mean([u.score.is_garbage for u in us]))
        empty_parse[cond] = float(
            np.mean([u.score.empty or u.score.parse_fail for u in us])
        )
        dispersion[cond] = float(np.mean([u.score.dispersion for u in us]))
        valid_rate[cond] = float(np.mean([not _missing(u.score) for u in us]))
    return fluency, garbage, empty_parse, dispersion, valid_rate


def _divergence(rates: dict[str, float]) -> float:
    primary = [rates[c] for c in _PRIMARY_CONDITIONS if c in rates]
    return (max(primary) - min(primary)) if primary else 0.0


def decompose(units: Sequence[ScoredUnit], *, bootstrap_seed: int = 0) -> Decomposition:
    """Full cluster-paired decomposition over the AUT scored units."""
    clusters = _cluster_contrasts(units)
    deltas = np.array([c.delta for c in clusters if c.n_paired > 0], dtype=float)

    if deltas.size > 0:
        delta_dq = float(np.mean(deltas))
        sd = float(np.std(deltas, ddof=1)) if deltas.size > 1 else 0.0
        delta_dq_std = delta_dq / sd if sd > 0.0 else 0.0
        ci = bootstrap_ci(
            deltas.tolist(),
            n_resamples=_c.N_RESAMPLES,
            ci=1.0 - _c.CI_ALPHA,
            seed=bootstrap_seed,
            statistic="mean",
        )
        ci_lo, ci_hi = ci.lo, ci.hi
        std_ci_lo = _std_ci_lower(deltas, bootstrap_seed + 1)
    else:
        delta_dq = delta_dq_std = ci_lo = ci_hi = std_ci_lo = 0.0

    mono_ci_lo = _monotone_ci_lower(clusters, bootstrap_seed + 2)
    fluency, garbage, empty_parse, dispersion, valid_rate = _condition_means(units)
    missing_rate = {c: 1.0 - r for c, r in valid_rate.items()}

    return Decomposition(
        clusters=tuple(clusters),
        n_clusters=sum(1 for c in clusters if c.n_paired > 0),
        delta_dq=delta_dq,
        delta_dq_std=delta_dq_std,
        delta_dq_ci_lower=ci_lo,
        delta_dq_ci_upper=ci_hi,
        delta_dq_std_ci_lower=std_ci_lo,
        monotone_supported=mono_ci_lo > 0.0,
        monotone_min_increment_ci_lower=mono_ci_lo,
        fluency_by_condition=fluency,
        garbage_rate_by_condition=garbage,
        empty_parse_rate_by_condition=empty_parse,
        dispersion_by_condition=dispersion,
        cross_condition_valid_divergence=_divergence(valid_rate),
        cross_condition_missing_divergence=_divergence(missing_rate),
    )


__all__ = [
    "ClusterContrast",
    "Decomposition",
    "ScoredUnit",
    "decompose",
]
