"""Control battery for the M13-ES4 verdict (§2.3 / §2.4 / §3, pre-registered).

The non-tautology + temperature-attribution + apparatus-integrity guards, all
pure numpy so they run LLM-free in Session 1:

* **pre-flight sampling-hash equivalence (hard abort)** — ``loco(λ=0)`` resolves
  bit-identically to the ``loco_delta=None`` path, and M2's resolved-temperature
  multiset equals A2's per ``(persona, item)`` (distribution-matched, §0 / §2.4).
  A break is a code defect, so the verdict aborts rather than spends a vocabulary.
* **(a1) temp-stratified discrimination** — within each temperature level the
  scorer+gate separates good vs garbage / on-task vs off-task at matched length,
  min AUC ≥ ``AUC_FLOOR``. Proves DQ is not riding temperature.
* **(a2) held-out residual** — after partialling out ``H_proxy`` (entropy proxy)
  on a holdout, the λ→DQ effect must survive (residual ΔDQ CI_lower > 0). Proves
  DQ is not an entropy re-encoding.
* **adversarial judge-AUC** — the appropriateness judge separates the frozen
  six-category labeled set's ``appropriate`` from ``inappropriate`` (AUC ≥
  ``AUC_FLOOR``), mitigating self-judge circularity (Codex M-4).
* **(b) temp-matched TOST** — A2 vs M2 equivalence (margin ``DELTA_EQUIV`` SD):
  the honest confirmation that the effect is attributable to the reached
  temperature distribution, not "locomotion magic" (§2.4; non-equivalence is a
  forensic flag, not a power claim).
* **falsifiability F (forensic)** — over-heat DQ / garbage turnover, recorded, not
  verdict-driving (§2.5).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.scenario import build_aut_requests

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.es4_actuator.battery import AdversarialItem
    from erre_sandbox.evidence.es4_actuator.scenario import Phase

ScoreFn = Callable[[str, str], float]
"""Continuous judge/scorer score for ``(object, text)`` (higher = more
appropriate). Production = the SGLang judge logit / probability; tests pass a
deterministic stub."""


# --- AUC ----------------------------------------------------------------------


def auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """ROC AUC via the Mann-Whitney U rank statistic.

    ``labels`` are ``1`` (positive) / ``0`` (negative). Returns 0.5 when either
    class is empty (uninformative).
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1, dtype=float)
    # average ranks for ties
    _assign_tie_ranks(s, ranks)
    rank_sum_pos = float(ranks[y == 1].sum())
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def _assign_tie_ranks(values: np.ndarray, ranks: np.ndarray) -> None:
    order = np.argsort(values, kind="mergesort")
    sorted_vals = values[order]
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            avg = (np.arange(i + 1, j + 2)).mean()
            ranks[order[i : j + 1]] = avg
        i = j + 1


def stratified_min_auc(
    scores: Sequence[float], labels: Sequence[int], strata: Sequence[object]
) -> float:
    """Minimum AUC across temperature strata (the (a1) statistic)."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    strata_arr = np.asarray(strata, dtype=object)
    aucs: list[float] = []
    for level in dict.fromkeys(strata_arr.tolist()):
        mask = strata_arr == level
        if mask.sum() == 0:
            continue
        aucs.append(auc(s[mask].tolist(), y[mask].tolist()))
    return min(aucs) if aucs else 0.5


def adversarial_judge_auc(items: Sequence[AdversarialItem], score_fn: ScoreFn) -> float:
    """AUC of ``score_fn`` over the frozen adversarial labeled set (appropriate=1)."""
    scores = [score_fn(it.object, it.text) for it in items]
    labels = [1 if it.label == "appropriate" else 0 for it in items]
    return auc(scores, labels)


# --- (a2) held-out residual ---------------------------------------------------


@dataclass(frozen=True)
class ResidualResult:
    """(a2) held-out entropy-residual gate."""

    residual_delta_dq: float
    residual_ci_lower: float
    survives: bool


def held_out_residual(
    dq: Sequence[float],
    h_proxy: Sequence[float],
    is_high_lambda: Sequence[int],
    holdout_mask: Sequence[int],
    *,
    bootstrap_seed: int = 0,
) -> ResidualResult:
    """Does λ→DQ survive partialling out ``H_proxy`` on a holdout fit? (§2.3 (a2)).

    Fit ``DQ ~ a + b·H`` on the holdout rows, residualise every row, then take the
    high-λ minus low-λ residual ΔDQ with a bootstrap CI. ``survives`` ⇔ CI_lower
    > 0 (entropy non-reducible).
    """
    dq_a = np.asarray(dq, dtype=float)
    h_a = np.asarray(h_proxy, dtype=float)
    hi = np.asarray(is_high_lambda, dtype=int)
    hold = np.asarray(holdout_mask, dtype=int).astype(bool)

    a, b = _fit_line(h_a[hold], dq_a[hold])
    residual = dq_a - (a + b * h_a)

    res_hi = residual[hi == 1]
    res_lo = residual[hi == 0]
    if res_hi.size == 0 or res_lo.size == 0:
        return ResidualResult(0.0, 0.0, survives=False)
    point = float(res_hi.mean() - res_lo.mean())
    ci_lo = _diff_ci_lower(res_hi, res_lo, bootstrap_seed)
    return ResidualResult(point, ci_lo, survives=ci_lo > 0.0)


def _fit_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 2 or float(np.var(x)) == 0.0:  # noqa: PLR2004 — a line needs ≥2 points
        return (float(y.mean()) if y.size else 0.0), 0.0
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def _diff_ci_lower(hi: np.ndarray, lo: np.ndarray, seed: int) -> float:
    rng = np.random.default_rng(seed)
    hi_idx = rng.integers(0, hi.size, size=(_c.N_RESAMPLES, hi.size))
    lo_idx = rng.integers(0, lo.size, size=(_c.N_RESAMPLES, lo.size))
    diffs = hi[hi_idx].mean(axis=1) - lo[lo_idx].mean(axis=1)
    return float(np.quantile(diffs, _c.CI_ALPHA / 2.0))


# --- (b) TOST -----------------------------------------------------------------


@dataclass(frozen=True)
class TostResult:
    """(b) two one-sided test equivalence of A2 vs M2 DQ."""

    mean_diff: float
    margin: float
    ci_lower: float
    ci_upper: float
    equivalent: bool


def tost_equivalence(
    a2_dq: Sequence[float], m2_dq: Sequence[float], *, bootstrap_seed: int = 0
) -> TostResult:
    """A2 vs M2 distribution-matched equivalence (margin ``DELTA_EQUIV`` SD).

    Equivalent ⇔ the ``(1 − 2α)`` percentile CI of the mean difference lies inside
    ``[−margin, +margin]`` (the bootstrap rendering of TOST).
    """
    a = np.asarray(a2_dq, dtype=float)
    m = np.asarray(m2_dq, dtype=float)
    if a.size == 0 or m.size == 0:
        return TostResult(0.0, 0.0, 0.0, 0.0, equivalent=False)
    pooled_sd = (
        float(np.std(np.concatenate([a, m]), ddof=1)) if a.size + m.size > 1 else 0.0
    )
    margin = _c.DELTA_EQUIV * pooled_sd
    rng = np.random.default_rng(bootstrap_seed)
    a_idx = rng.integers(0, a.size, size=(_c.N_RESAMPLES, a.size))
    m_idx = rng.integers(0, m.size, size=(_c.N_RESAMPLES, m.size))
    diffs = a[a_idx].mean(axis=1) - m[m_idx].mean(axis=1)
    ci_lo = float(np.quantile(diffs, _c.ALPHA_ONE_SIDED))
    ci_hi = float(np.quantile(diffs, 1.0 - _c.ALPHA_ONE_SIDED))
    equivalent = margin > 0.0 and ci_lo >= -margin and ci_hi <= margin
    return TostResult(
        float(a.mean() - m.mean()), margin, ci_lo, ci_hi, equivalent=equivalent
    )


# --- pre-flight sampling-hash equivalence (hard abort) ------------------------


@dataclass(frozen=True)
class PreflightResult:
    """Deterministic pre-flight asserts (§0). A False here is a code defect."""

    loco_zero_equals_none: bool
    m2_matches_a2_distribution: bool
    max_abs_temp_diff: float

    @property
    def ok(self) -> bool:
        return self.loco_zero_equals_none and self.m2_matches_a2_distribution


def _resolved_tuple(resolved: object) -> tuple[float, float, float]:
    return (
        round(resolved.temperature, 12),  # type: ignore[attr-defined]
        round(resolved.top_p, 12),  # type: ignore[attr-defined]
        round(resolved.repeat_penalty, 12),  # type: ignore[attr-defined]
    )


def preflight_sampling_hash(phase: Phase = "phase1") -> PreflightResult:
    """Check ``loco(λ=0)≡None`` and M2≡A2 distribution (a structural invariant).

    The ``phase`` argument is accepted for call-site symmetry, but the M2≡A2 check
    is always evaluated against the **phase-1** request set (M2 only exists in
    Phase 1); it is an apparatus property independent of which phase is running.
    """
    del phase  # M2≡A2 is phase-independent; always check the phase-1 request set.
    from erre_sandbox.evidence.es4_actuator.scenario import (  # noqa: PLC0415
        resolve_lambda_sampling,
    )
    from erre_sandbox.inference.sampling import compose_sampling  # noqa: PLC0415
    from erre_sandbox.schemas import SamplingDelta  # noqa: PLC0415

    # (1) loco(λ=0) ≡ loco_delta=None
    loco_zero_ok = True
    max_diff = 0.0
    for _persona_id, base in _c.PERSONA_ROSTER:
        none_path = compose_sampling(base, SamplingDelta())
        zero_path = resolve_lambda_sampling(base, _c.LAMBDA_A0)
        diff = abs(none_path.temperature - zero_path.temperature)
        max_diff = max(max_diff, diff)
        if _resolved_tuple(none_path) != _resolved_tuple(zero_path):
            loco_zero_ok = False

    # (2) M2 multiset ≡ A2 multiset per (persona, item)
    requests = build_aut_requests("phase1")
    a2: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
    m2: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
    for r in requests:
        key = (r.persona_id, r.item_id)
        if r.condition == "A2":
            a2.setdefault(key, []).append(_resolved_tuple(r.resolved))
        elif r.condition == "M2":
            m2.setdefault(key, []).append(_resolved_tuple(r.resolved))
    m2_ok = a2.keys() == m2.keys() and all(sorted(a2[k]) == sorted(m2[k]) for k in a2)
    return PreflightResult(loco_zero_ok, m2_ok, max_diff)


__all__ = [
    "PreflightResult",
    "ResidualResult",
    "ScoreFn",
    "TostResult",
    "adversarial_judge_auc",
    "auc",
    "held_out_residual",
    "preflight_sampling_hash",
    "stratified_min_auc",
    "tost_equivalence",
]
