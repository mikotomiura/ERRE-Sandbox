"""Frozen conjunctive verdict for the M13-ES2 path-recombination replay (§9 / §10).

Pure decision logic over the per-scenario-seed readouts (:class:`SeedResult`).
Every threshold is read from :mod:`erre_sandbox.evidence.es2_replay.constants`;
this module holds **no** tunable literal of its own. The structure mirrors the
ES-1 ``spdm.verdict_report``: an INCONCLUSIVE gate is checked *first* (so an
under-powered or invalid measurement is never reported as a progressive NO_GO),
then the conjunctive GO conditions.

Verdict vocabulary (``design-final.md`` §0, kept distinct):

* **GO** — adequate power ∧ valid apparatus ∧ tight null, and the recombination
  generates de-novo, path-dependent novel seeds above the matched N-a null. Means
  *eligible to proceed to ES-3*, **not** the full hypothesis. The claim is then
  stratified by the N-b sensitivity (N-b pass → ordered content-location pairing;
  N-b fail → home-range / path-label only).
* **NO_GO** — adequate power ∧ valid apparatus ∧ tight null, yet path-dependence
  (N-a CI lower ≤ 0) or the novelty floor is not met. A **progressive finding**
  (recombination alone is insufficient → ES-3 / richer primitive), not a refutation.
* **INCONCLUSIVE** — low power, an invalid apparatus (no semantic competition, a
  temporal-replay control that did not fail, a degenerate trajectory), or a null
  too noisy to distinguish. Never conflated with NO_GO.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
from erre_sandbox.evidence.es2_replay import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

Verdict = Literal["GO", "NO_GO", "INCONCLUSIVE"]


@dataclass(frozen=True)
class SeedResult:
    """Per-scenario-seed readouts for one blind apparatus instantiation.

    All rates are over the **valid** replay seeds of that scenario seed. ``delta_a``
    / ``delta_b`` are ``D_obs - null_q`` for the N-a (primary) / N-b (sensitivity)
    nulls; the bootstrap CI is taken across these per-seed deltas (Codex H5).
    """

    seed: int
    valid: bool
    d_obs: float
    """A/B de-novo directed-transition Jensen-Shannon divergence (measurable ADR §2)."""
    null_q_a: float
    """N-a per-seed null quantile ``quantile(D_perm_a, PERM_NULL_QUANTILE)``."""
    delta_a: float
    """``d_obs - null_q_a`` (primary path-dependence statistic)."""
    null_q_b: float
    """N-b per-seed null quantile (within-agent pairing permutation)."""
    delta_b: float
    """``d_obs - null_q_b`` (sensitivity / claim stratifier)."""
    novel_transition_rate: float
    """Median over the two arms of the primary novel directed-transition rate."""
    exact_de_novo_rate: float
    """Median over the two arms of the secondary exact-de-novo rate (forensic)."""
    temporal_novel_rate: float
    """Novel-transition rate of the temporal-replay control (must be < floor)."""
    n_denovo_a: int
    n_denovo_b: int
    effective_zones_a: int
    effective_zones_b: int
    d_self: float
    """Within-agent split-half self-divergence (median of the two arms, JS)."""
    no_spurious_margin: float
    """③ semantic-isomorphic relabel transition-distribution JS margin (Codex M2)."""
    var_cosine: float
    """② ``var(pairwise cosine)`` over the synthetic embeddings (validity gate)."""


@dataclass(frozen=True)
class Es2Verdict:
    """The ES-2 verdict and the statistics that produced it."""

    verdict: Verdict
    reasons: tuple[str, ...]
    n_valid_seeds: int
    median_d_obs: float
    median_novel_transition_rate: float
    median_exact_de_novo_rate: float
    median_temporal_novel_rate: float
    ci_lower: float
    ci_upper: float
    n_b_ci_lower: float
    n_b_ci_upper: float
    min_denovo_seeds: int
    min_effective_zones: int
    median_d_self: float
    median_no_spurious_margin: float
    var_cosine: float


@dataclass(frozen=True)
class _Metrics:
    n_valid: int
    median_d_obs: float
    median_novel: float
    median_exact: float
    median_temporal: float
    ci_lower: float
    ci_upper: float
    nb_ci_lower: float
    nb_ci_upper: float
    min_denovo: int
    min_eff_zones: int
    median_d_self: float
    median_no_spurious: float
    var_cosine: float


def _median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0.0


def _compute_metrics(valid: list[SeedResult], bootstrap_seed: int) -> _Metrics:
    d_obs = [s.d_obs for s in valid]
    deltas_a = [s.delta_a for s in valid]
    deltas_b = [s.delta_b for s in valid]
    if deltas_a:
        ci_a = bootstrap_ci(
            deltas_a,
            n_resamples=_c.N_RESAMPLES,
            ci=1.0 - _c.CI_ALPHA,
            seed=bootstrap_seed,
            statistic="mean",
        )
        ci_b = bootstrap_ci(
            deltas_b,
            n_resamples=_c.N_RESAMPLES,
            ci=1.0 - _c.CI_ALPHA,
            seed=bootstrap_seed,
            statistic="mean",
        )
        ci_lower, ci_upper = ci_a.lo, ci_a.hi
        nb_lower, nb_upper = ci_b.lo, ci_b.hi
    else:
        ci_lower = ci_upper = nb_lower = nb_upper = 0.0

    return _Metrics(
        n_valid=len(valid),
        median_d_obs=_median(d_obs),
        median_novel=_median([s.novel_transition_rate for s in valid]),
        median_exact=_median([s.exact_de_novo_rate for s in valid]),
        median_temporal=_median([s.temporal_novel_rate for s in valid]),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        nb_ci_lower=nb_lower,
        nb_ci_upper=nb_upper,
        min_denovo=min((min(s.n_denovo_a, s.n_denovo_b) for s in valid), default=0),
        min_eff_zones=min(
            (min(s.effective_zones_a, s.effective_zones_b) for s in valid),
            default=0,
        ),
        median_d_self=_median([s.d_self for s in valid]),
        median_no_spurious=_median([s.no_spurious_margin for s in valid]),
        var_cosine=valid[0].var_cosine if valid else 0.0,
    )


def _inconclusive_reason(m: _Metrics) -> str | None:  # noqa: PLR0911 — guard sequence
    """First INCONCLUSIVE trigger (§9, calibration-free), else None.

    Checked before GO/NO_GO so an unreliable or invalid measurement is never
    reported as a (progressive) NO_GO finding.
    """
    if m.n_valid < _c.MIN_VALID_SEEDS:
        return f"valid seeds {m.n_valid} < MIN_VALID_SEEDS {_c.MIN_VALID_SEEDS}"
    if m.var_cosine < _c.COMPETITION_MIN_VAR:
        return (
            f"② competition absent: var(cosine) {m.var_cosine:.4f} < "
            f"COMPETITION_MIN_VAR {_c.COMPETITION_MIN_VAR}; apparatus invalid"
        )
    if m.min_denovo < _c.MIN_DENOVO_SEEDS:
        return (
            f"de-novo eligible seeds {m.min_denovo} < MIN_DENOVO_SEEDS "
            f"{_c.MIN_DENOVO_SEEDS} (sampling inadequate)"
        )
    if m.min_eff_zones < 2:  # noqa: PLR2004 — a non-degenerate trajectory needs ≥2 zones
        return f"effective zones {m.min_eff_zones} < 2 (degenerate trajectory)"
    if m.median_temporal >= _c.NOVELTY_FLOOR:
        return (
            f"temporal-replay control did not fail novelty (median "
            f"{m.median_temporal:.4f} >= NOVELTY_FLOOR {_c.NOVELTY_FLOOR}); "
            "apparatus invalid"
        )
    # Relative noise gate (self-calibrating, measurable ADR §4 / Codex H1): the
    # cross-agent JS must exceed the within-agent split-half JS noise. With
    # FLOOR_REL = 0.0 there is no absolute JS floor — the consistent JS estimator
    # makes D_self shrink with sample size, so the noise reference is D_self itself.
    noise_ref = max(m.median_d_self, _c.FLOOR_REL)
    if m.median_d_obs <= _c.NULL_NOISE_FACTOR * noise_ref:
        return (
            f"split-half noise gate: median(D_obs) {m.median_d_obs:.4f} <= "
            f"{_c.NULL_NOISE_FACTOR} * max(median(D_self) {m.median_d_self:.4f}, "
            f"FLOOR_REL {_c.FLOOR_REL})"
        )
    return None


def _go_failures(m: _Metrics) -> list[str]:
    """Unmet conjunctive GO conditions (§10); empty ⇒ GO."""
    failures: list[str] = []
    if m.median_novel < _c.NOVELTY_FLOOR:
        failures.append(
            f"median novel-transition rate {m.median_novel:.4f} < "
            f"NOVELTY_FLOOR {_c.NOVELTY_FLOOR}"
        )
    if m.ci_lower <= 0.0:
        failures.append(f"N-a bootstrap CI lower {m.ci_lower:.4f} <= 0 (90% CI)")
    if m.median_no_spurious > _c.NO_SPURIOUS_TOL:
        failures.append(
            f"③ no-spurious margin {m.median_no_spurious:.4f} > "
            f"NO_SPURIOUS_TOL {_c.NO_SPURIOUS_TOL}"
        )
    return failures


def _pack(verdict: Verdict, reasons: tuple[str, ...], m: _Metrics) -> Es2Verdict:
    return Es2Verdict(
        verdict=verdict,
        reasons=reasons,
        n_valid_seeds=m.n_valid,
        median_d_obs=m.median_d_obs,
        median_novel_transition_rate=m.median_novel,
        median_exact_de_novo_rate=m.median_exact,
        median_temporal_novel_rate=m.median_temporal,
        ci_lower=m.ci_lower,
        ci_upper=m.ci_upper,
        n_b_ci_lower=m.nb_ci_lower,
        n_b_ci_upper=m.nb_ci_upper,
        min_denovo_seeds=m.min_denovo,
        min_effective_zones=m.min_eff_zones,
        median_d_self=m.median_d_self,
        median_no_spurious_margin=m.median_no_spurious,
        var_cosine=m.var_cosine,
    )


def evaluate_verdict(
    seeds: Sequence[SeedResult],
    *,
    bootstrap_seed: int = 0,
) -> Es2Verdict:
    """Render the frozen ES-2 verdict from per-scenario-seed readouts.

    ``bootstrap_seed`` makes the CI reproducible (the resampling RNG seed). All
    thresholds come from :mod:`constants`; nothing here is tuned post-result.
    """
    valid = [s for s in seeds if s.valid]
    m = _compute_metrics(valid, bootstrap_seed)

    incon = _inconclusive_reason(m)
    if incon is not None:
        return _pack("INCONCLUSIVE", (incon,), m)

    failures = _go_failures(m)
    if not failures:
        return _pack(
            "GO",
            ("all GO conditions met; eligible to proceed to ES-3",),
            m,
        )
    return _pack("NO_GO", tuple(failures), m)


__all__ = ["Es2Verdict", "SeedResult", "Verdict", "evaluate_verdict"]
