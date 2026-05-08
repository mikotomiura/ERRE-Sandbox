"""Big5 stability ICC across runs/windows for Tier B DB9 quorum.

The intra-class correlation coefficient (ICC) over per-window Big5 score
vectors quantifies how stable the IPIP-50 self-report is across the 25
clusters of a typical run (5 runs × 5 per-100-turn windows).

DB9 sub-metric: ``big5_stability_icc``. Two consumers, two ICC variants
(M9-eval ME-11, Codex P4a HIGH-2):

* **ME-1 reliability fallback trigger**: ``ICC(C,k)`` consistency average
  is the primary value the trigger reads. Threshold ``point < 0.6 OR
  lower CI < 0.5`` in ≥2/3 personas fires the fallback (ME-1).
* **DB9 drift / adoption gate**: ``ICC(A,1)`` absolute agreement single
  rater is the primary value the gate reads. Level-shift sensitivity is
  intentional: a systematic Big5 offset is drift even if the rank order
  is preserved. ME-1 thresholds are *not* reused for ICC(A,1) — DB9
  cutoffs are calibrated separately on golden baseline data (P4b).

Notation: McGraw & Wong (1996). ``ICC(C,*)`` = consistency,
``ICC(A,*)`` = absolute agreement; ``*=1`` single rater, ``*=k`` k-rater
average. Mapping to Shrout & Fleiss (1979): ``ICC(2,k)`` ≈ ``ICC(C,k)``
or ``ICC(A,k)`` depending on whether absolute agreement was assumed.

Degenerate handling (Codex P4a MEDIUM-5): identical-all-constant response
matrices push BMS=0 and EMS=0 in the ANOVA decomposition. The function
returns ``icc_*=1.0, degenerate=True, me1_fallback_fire=False`` as an
explicit special case rather than an assumed limit. The
``test_compute_big5_icc_identical_windows_degenerate_returns_one`` test
pins this contract.

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report
only — no LIWC equivalence claim, no external-lexicon Big5 inference.
Tier A ``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10
Option D).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.bootstrap_ci import (
    DEFAULT_CI,
    DEFAULT_N_RESAMPLES,
    BootstrapResult,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from erre_sandbox.evidence.tier_b.ipip_neo import Big5Scores

ME1_FALLBACK_POINT_THRESHOLD: float = 0.6
"""ICC(C,k) point estimate threshold for ME-1 fallback fire (M9-eval ME-1)."""

ME1_FALLBACK_LOWER_CI_THRESHOLD: float = 0.5
"""ICC(C,k) 95% lower CI threshold for ME-1 fallback fire (M9-eval ME-1)."""

_DIMENSION_ORDER: tuple[str, ...] = ("E", "A", "C", "N", "O")
"""Big5 dimension order. Maps :class:`Big5Scores` fields to matrix rows."""

_FORMULA_NOTATION: str = "McGraw-Wong 1996"


@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    """Big5 stability ICC across windows.

    Two consumers (ME-11):

    * ME-1 (reliability fallback trigger) reads ``icc_consistency_average``
      and ``icc_consistency_lower_ci``; ``me1_fallback_fire`` summarises the
      0.6/0.5 threshold check.
    * DB9 (drift/adoption gate) reads ``icc_agreement_single`` and its CI.
      DB9 thresholds are *not* the ME-1 thresholds — see ME-11.

    ``degenerate`` is ``True`` for the all-identical-response special case
    (BMS=EMS=0 in the ANOVA); the ICC values are then deterministically
    set to 1.0 and the bootstrap intervals collapse to the same value.
    """

    # ME-1 consumer (reliability)
    icc_consistency_average: float
    icc_consistency_single: float
    icc_consistency_lower_ci: float
    icc_consistency_upper_ci: float
    me1_fallback_fire: bool

    # DB9 consumer (drift gate)
    icc_agreement_single: float
    icc_agreement_average: float
    icc_agreement_lower_ci: float
    icc_agreement_upper_ci: float

    # Diagnostic
    n_clusters: int  # number of Big5Scores windows fed in
    n_dimensions: int  # 5 (E/A/C/N/O)
    degenerate: bool
    formula_notation: str  # "McGraw-Wong 1996"


@dataclass(frozen=True, slots=True)
class TierBBootstrapPair:
    """Primary CI (cluster_only) + diagnostic CI (auto_block) pair.

    Per ME-14 (Codex P4a MEDIUM-1) the DB9 quorum code reads ``primary``
    only. ``diagnostic_auto_block`` is surfaced for variance-underestimation
    cross-checking and is not consumed by the gate. Pooled-persona CIs are
    forbidden unless an explicit ``is_exploratory`` flag is set elsewhere.
    """

    primary: BootstrapResult  # method="hierarchical-cluster-only"
    diagnostic_auto_block: BootstrapResult | None  # method="hierarchical-block"
    persona_id: str
    metric_name: str
    ess_disclosure: int  # cluster count, 25 typical (5 run × 5 window)


def _big5_matrix(big5_per_window: Sequence[Big5Scores]) -> np.ndarray:
    """Return ``(n_dimensions=5, n_windows)`` matrix of Big5 scores.

    Rows are dimensions in :data:`_DIMENSION_ORDER`, columns are windows in
    the input order. Used as the rating matrix for ICC computation.
    """
    n_windows = len(big5_per_window)
    matrix = np.empty((len(_DIMENSION_ORDER), n_windows), dtype=float)
    for j, scores in enumerate(big5_per_window):
        matrix[0, j] = scores.extraversion
        matrix[1, j] = scores.agreeableness
        matrix[2, j] = scores.conscientiousness
        matrix[3, j] = scores.neuroticism
        matrix[4, j] = scores.openness
    return matrix


def _icc_two_way_random(
    matrix: np.ndarray,
) -> tuple[float, float, float, float, bool]:
    """Compute ICC(C,1), ICC(C,k), ICC(A,1), ICC(A,k) and degenerate flag.

    Two-way random effects ANOVA (McGraw-Wong 1996 Table 4 cells for ICC2
    and ICC2k). ``matrix`` shape is ``(n_subjects, n_raters)``.

    Returns ``(icc_C1, icc_Ck, icc_A1, icc_Ak, degenerate)``. ``degenerate``
    is ``True`` when the ANOVA decomposition returns 0/0 (identical row or
    near-zero variance everywhere); ICC values are then 1.0.
    """
    n_subjects, n_raters = matrix.shape
    if n_subjects < 2 or n_raters < 2:  # noqa: PLR2004 — ICC needs ≥2 in each dim
        return 1.0, 1.0, 1.0, 1.0, True

    grand_mean = float(matrix.mean())
    subject_means = matrix.mean(axis=1)
    rater_means = matrix.mean(axis=0)

    # Sum-of-squares decomposition.
    ss_between_subjects = float(
        n_raters * np.sum((subject_means - grand_mean) ** 2),
    )
    ss_between_raters = float(
        n_subjects * np.sum((rater_means - grand_mean) ** 2),
    )
    ss_total = float(np.sum((matrix - grand_mean) ** 2))
    ss_residual = ss_total - ss_between_subjects - ss_between_raters

    df_subjects = n_subjects - 1
    df_raters = n_raters - 1
    df_residual = df_subjects * df_raters

    bms = ss_between_subjects / df_subjects if df_subjects > 0 else 0.0
    jms = ss_between_raters / df_raters if df_raters > 0 else 0.0
    ems = ss_residual / df_residual if df_residual > 0 else 0.0

    if math.isclose(bms, 0.0, abs_tol=1e-12) and math.isclose(
        ems,
        0.0,
        abs_tol=1e-12,
    ):
        return 1.0, 1.0, 1.0, 1.0, True

    icc_c1_denom = bms + (n_raters - 1) * ems
    icc_c1 = (bms - ems) / icc_c1_denom if icc_c1_denom > 0 else 0.0
    icc_ck = (bms - ems) / bms if bms > 0 else 0.0

    icc_a1_denom = bms + (n_raters - 1) * ems + n_raters * (jms - ems) / n_subjects
    icc_a1 = (bms - ems) / icc_a1_denom if icc_a1_denom > 0 else 0.0

    icc_ak_denom = bms + (jms - ems) / n_subjects
    icc_ak = (bms - ems) / icc_ak_denom if icc_ak_denom > 0 else 0.0

    return float(icc_c1), float(icc_ck), float(icc_a1), float(icc_ak), False


def _bootstrap_icc_cluster_only(
    matrix: np.ndarray,
    *,
    icc_index: int,
    seed: int,
    n_resamples: int,
    ci: float,
) -> tuple[float, float]:
    """Bootstrap CI for one of the four ICC variants.

    ``icc_index``: ``0=C1``, ``1=Ck``, ``2=A1``, ``3=Ak``. Resamples columns
    (raters/windows) with replacement; each column is a cluster in the
    cluster-only sense (M9-eval ME-14 / Codex P4a MEDIUM-1). Subjects are
    not resampled — the 5 Big5 dimensions are fixed by construction.
    """
    rng = np.random.default_rng(seed)
    n_raters = matrix.shape[1]
    replicate_iccs = np.empty(n_resamples, dtype=float)
    for r in range(n_resamples):
        cols = rng.integers(0, n_raters, size=n_raters)
        sampled = matrix[:, cols]
        replicate_iccs[r] = _icc_two_way_random(sampled)[icc_index]

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_iccs, alpha / 2.0))
    hi = float(np.quantile(replicate_iccs, 1.0 - alpha / 2.0))
    return lo, hi


def compute_big5_icc(
    big5_per_window: Sequence[Big5Scores],
    *,
    seed: int = 0,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
) -> Big5ICCResult:
    """Compute ICC(C,*) and ICC(A,*) over per-window Big5 scores.

    Args:
        big5_per_window: Sequence of :class:`Big5Scores`, one per window.
            Typically 25 entries (5 runs × 5 per-100-turn windows).
        seed: Deterministic bootstrap seed (M9-eval ME-5).
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.

    Returns:
        :class:`Big5ICCResult` with both consumers' values surfaced and
        ``me1_fallback_fire`` summarising the consistency-only threshold
        check (ME-1).

    Raises:
        ValueError: For empty input or fewer than 2 windows (ICC undefined).
    """
    n_windows = len(big5_per_window)
    if n_windows < 2:  # noqa: PLR2004 — ICC needs ≥2 raters
        raise ValueError(
            f"compute_big5_icc requires >=2 windows (got {n_windows})",
        )

    matrix = _big5_matrix(big5_per_window)
    icc_c1, icc_ck, icc_a1, icc_ak, degenerate = _icc_two_way_random(matrix)

    if degenerate:
        # Bootstrap collapses to the same value; surface 1.0 explicitly.
        cons_lo, cons_hi = 1.0, 1.0
        agr_lo, agr_hi = 1.0, 1.0
    else:
        cons_lo, cons_hi = _bootstrap_icc_cluster_only(
            matrix,
            icc_index=1,  # ICC(C,k)
            seed=seed,
            n_resamples=n_resamples,
            ci=ci,
        )
        agr_lo, agr_hi = _bootstrap_icc_cluster_only(
            matrix,
            icc_index=2,  # ICC(A,1)
            seed=seed,
            n_resamples=n_resamples,
            ci=ci,
        )

    me1_fallback_fire = not degenerate and (
        icc_ck < ME1_FALLBACK_POINT_THRESHOLD
        or cons_lo < ME1_FALLBACK_LOWER_CI_THRESHOLD
    )

    return Big5ICCResult(
        icc_consistency_average=icc_ck,
        icc_consistency_single=icc_c1,
        icc_consistency_lower_ci=cons_lo,
        icc_consistency_upper_ci=cons_hi,
        me1_fallback_fire=me1_fallback_fire,
        icc_agreement_single=icc_a1,
        icc_agreement_average=icc_ak,
        icc_agreement_lower_ci=agr_lo,
        icc_agreement_upper_ci=agr_hi,
        n_clusters=n_windows,
        n_dimensions=len(_DIMENSION_ORDER),
        degenerate=degenerate,
        formula_notation=_FORMULA_NOTATION,
    )


__all__ = [
    "ME1_FALLBACK_LOWER_CI_THRESHOLD",
    "ME1_FALLBACK_POINT_THRESHOLD",
    "Big5ICCResult",
    "TierBBootstrapPair",
    "compute_big5_icc",
]
