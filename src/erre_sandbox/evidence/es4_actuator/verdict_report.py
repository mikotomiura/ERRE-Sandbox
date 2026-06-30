"""Frozen five-vocabulary verdict for M13-ES4 (§4.1 Phase 0 / §8 Phase 1).

Pure decision logic over the cluster-paired :class:`~...decomposition.Decomposition`
and aggregated control / battery / budget evidence. Every threshold comes from
:mod:`constants`; this module holds no tunable literal of its own (the only derived
quantity is :func:`required_clusters_for_mde`, computed from the frozen
``MDE_CLUSTER_D`` / ``POWER`` / ``ALPHA_ONE_SIDED`` via standard-normal quantiles).

Structure mirrors ES-1/2/3: **INCONCLUSIVE-first conjunctive**. The two phases are
separate functions sharing one vocabulary (``design-final.md`` §0):

* Phase 0 (:func:`evaluate_phase0`) — feasibility/power binary gate. PASS = the
  frozen Phase 1 is licensed to run; the four non-PASS outcomes are terminal
  findings.
* Phase 1 (:func:`evaluate_phase1`) — the full ES-4 verdict. GO = *actuator
  sufficiency* (over-claim guard §9), never "walking → divergence" nor a re-proof
  of the core thesis.

The forking-paths seal (§5): a non-PASS / non-GO outcome is recorded as-is — the
floors / MDE / bands are never re-tuned to flip it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.es4_actuator import constants as _c

if TYPE_CHECKING:
    from erre_sandbox.evidence.es4_actuator.decomposition import Decomposition

Verdict = Literal[
    "INVALID_SCORER",
    "INVALID_TASK_BATTERY",
    "NO_GO_EFFECT_ABSENT",
    "INCONCLUSIVE_UNDERPOWERED",
    "PASS",
    "GO",
]

# Standard-normal one-sided quantiles (statistical constants, not §5 knobs).
_Z_ALPHA_05: float = 1.6448536269514722  # Φ⁻¹(0.95)
_Z_POWER_80: float = 0.8416212335729143  # Φ⁻¹(0.80)


def required_clusters_for_mde() -> int:
    """Clusters needed to detect ``MDE_CLUSTER_D`` at ``POWER`` / ``ALPHA_ONE_SIDED``.

    One-sample (paired) z approximation ``n = ((z_α + z_β) / d)²``. With the frozen
    d=0.40 / power 0.80 / α 0.05 this is ≈ 39, inside the available 48 clusters.
    """
    n = ((_Z_ALPHA_05 + _Z_POWER_80) / _c.MDE_CLUSTER_D) ** 2
    return math.ceil(n)


@dataclass(frozen=True)
class ScorerControls:
    """Aggregated scorer non-tautology controls (§2.3 / §3)."""

    a1_min_auc: float
    a2_residual_survives: bool
    a2_residual_ci_lower: float
    adversarial_auc: float

    @property
    def valid(self) -> bool:
        """(a1) ∨ (a2) ∨ adversarial all must hold (§4.1.1 / §8.1)."""
        return (
            self.a1_min_auc >= _c.AUC_FLOOR
            and self.a2_residual_survives
            and self.adversarial_auc >= _c.AUC_FLOOR
        )


@dataclass(frozen=True)
class BatteryValidity:
    """Aggregated item-level battery validity (§3 / §8.2)."""

    n_valid_aut: int
    n_valid_rat: int
    empty_parse_rate: float
    cross_cond_valid_divergence: float
    cross_cond_missing_divergence: float
    persona_collapse: bool
    rat_contamination: bool

    @property
    def valid(self) -> bool:
        return not self.failure_reason()

    def failure_reason(self) -> str | None:  # noqa: PLR0911 — pre-registered gate sequence (§3)
        if self.n_valid_aut < _c.MIN_VALID_AUT:
            return f"valid AUT {self.n_valid_aut} < MIN_VALID_AUT {_c.MIN_VALID_AUT}"
        if self.n_valid_rat < _c.MIN_VALID_RAT:
            return f"valid RAT {self.n_valid_rat} < MIN_VALID_RAT {_c.MIN_VALID_RAT}"
        if self.empty_parse_rate >= _c.EMPTY_PARSE_FAIL_CEILING:
            return (
                f"empty/parse-fail {self.empty_parse_rate:.3f} >= "
                f"{_c.EMPTY_PARSE_FAIL_CEILING}"
            )
        if self.cross_cond_valid_divergence > _c.CROSS_COND_DIVERGENCE_MAX:
            return (
                f"cross-condition valid divergence "
                f"{self.cross_cond_valid_divergence:.3f} > "
                f"{_c.CROSS_COND_DIVERGENCE_MAX} (selection bias)"
            )
        if self.cross_cond_missing_divergence > _c.CROSS_COND_DIVERGENCE_MAX:
            return (
                f"cross-condition missing divergence "
                f"{self.cross_cond_missing_divergence:.3f} > "
                f"{_c.CROSS_COND_DIVERGENCE_MAX}"
            )
        if self.persona_collapse:
            return "persona collapse (Burrows Δ separation absent)"
        if self.rat_contamination:
            return "RAT contamination (remaining valid RAT below floor after exclusion)"
        return None


@dataclass(frozen=True)
class BudgetStatus:
    """Total-inclusive GPU budget feasibility (§4.1, Codex M-7)."""

    projected_gpu_hours: float
    cap_gpu_hours: float

    @property
    def within_cap(self) -> bool:
        return self.projected_gpu_hours <= self.cap_gpu_hours


@dataclass(frozen=True)
class Es4Verdict:
    """The ES-4 verdict + the statistics that produced it."""

    phase: Literal["phase0", "phase1"]
    verdict: Verdict
    reasons: tuple[str, ...]
    n_clusters: int
    delta_dq: float
    delta_dq_ci_lower: float
    delta_dq_ci_upper: float
    delta_dq_std: float
    delta_dq_std_ci_lower: float
    monotone_supported: bool
    garbage_rate_a2: float
    a1_min_auc: float
    adversarial_auc: float
    a2_residual_ci_lower: float
    forensic: dict[str, float] = field(default_factory=dict)


def _garbage_a2(decomp: Decomposition) -> float:
    return decomp.garbage_rate_by_condition.get("A2", 0.0)


def _pack(
    phase: Literal["phase0", "phase1"],
    verdict: Verdict,
    reasons: tuple[str, ...],
    decomp: Decomposition,
    scorer: ScorerControls,
) -> Es4Verdict:
    return Es4Verdict(
        phase=phase,
        verdict=verdict,
        reasons=reasons,
        n_clusters=decomp.n_clusters,
        delta_dq=decomp.delta_dq,
        delta_dq_ci_lower=decomp.delta_dq_ci_lower,
        delta_dq_ci_upper=decomp.delta_dq_ci_upper,
        delta_dq_std=decomp.delta_dq_std,
        delta_dq_std_ci_lower=decomp.delta_dq_std_ci_lower,
        monotone_supported=decomp.monotone_supported,
        garbage_rate_a2=_garbage_a2(decomp),
        a1_min_auc=scorer.a1_min_auc,
        adversarial_auc=scorer.adversarial_auc,
        a2_residual_ci_lower=scorer.a2_residual_ci_lower,
    )


def evaluate_phase0(
    decomp: Decomposition,
    scorer: ScorerControls,
    battery: BatteryValidity,
    budget: BudgetStatus,
) -> Es4Verdict:
    """Phase 0 PASS-STOP (§4.1, INCONCLUSIVE-first conjunctive).

    PASS licenses the frozen Phase 1. Futility (NO_GO) requires the **strong**
    absence evidence ``pilot ΔDQ upper CI < DQ_FLOOR_RAW`` (Codex HIGH-6), never a
    point estimate ≤ 0.
    """
    if not scorer.valid:
        return _pack(
            "phase0", "INVALID_SCORER", (_scorer_reason(scorer),), decomp, scorer
        )
    battery_reason = battery.failure_reason()
    if battery_reason is not None:
        return _pack(
            "phase0", "INVALID_TASK_BATTERY", (battery_reason,), decomp, scorer
        )
    if decomp.delta_dq_ci_upper < _c.DQ_FLOOR_RAW:
        return _pack(
            "phase0",
            "NO_GO_EFFECT_ABSENT",
            (
                f"pilot ΔDQ upper CI {decomp.delta_dq_ci_upper:.4f} < DQ_FLOOR_RAW "
                f"{_c.DQ_FLOOR_RAW} (strong absence)",
            ),
            decomp,
            scorer,
        )
    required = required_clusters_for_mde()
    if decomp.n_clusters < required or not budget.within_cap:
        return _pack(
            "phase0",
            "INCONCLUSIVE_UNDERPOWERED",
            (
                f"effective clusters {decomp.n_clusters} < required {required} "
                f"for MDE_cluster_d {_c.MDE_CLUSTER_D}"
                if decomp.n_clusters < required
                else (
                    f"projected {budget.projected_gpu_hours:.1f} GPU-h > cap "
                    f"{budget.cap_gpu_hours} (total-inclusive)"
                ),
            ),
            decomp,
            scorer,
        )
    return _pack(
        "phase0",
        "PASS",
        (
            "apparatus valid ∧ scorer non-tautology ∧ battery valid ∧ feasible; "
            "frozen Phase 1 licensed",
        ),
        decomp,
        scorer,
    )


def evaluate_phase1(
    decomp: Decomposition,
    scorer: ScorerControls,
    battery: BatteryValidity,
) -> Es4Verdict:
    """Phase 1 verdict (§8, INCONCLUSIVE-first conjunctive).

    GO = actuator sufficiency only (over-claim guard §9).
    """
    if not scorer.valid:
        return _pack(
            "phase1", "INVALID_SCORER", (_scorer_reason(scorer),), decomp, scorer
        )
    battery_reason = battery.failure_reason()
    if battery_reason is not None:
        return _pack(
            "phase1", "INVALID_TASK_BATTERY", (battery_reason,), decomp, scorer
        )

    required = required_clusters_for_mde()
    if decomp.n_clusters < required:
        return _pack(
            "phase1",
            "INCONCLUSIVE_UNDERPOWERED",
            (
                f"effective clusters {decomp.n_clusters} < required {required} "
                f"for MDE_cluster_d {_c.MDE_CLUSTER_D}",
            ),
            decomp,
            scorer,
        )

    no_go = _no_go_reason(decomp)
    if no_go is not None:
        return _pack("phase1", "NO_GO_EFFECT_ABSENT", (no_go,), decomp, scorer)

    return _pack(
        "phase1",
        "GO",
        (
            "actuator sufficiency: apparatus valid ∧ ΔDQ_std CI_lower ≥ "
            f"{_c.DQ_FLOOR_STD_CI_LOWER} ∧ raw ΔDQ ≥ {_c.DQ_FLOOR_RAW} ∧ monotone "
            "dose. Scope = qwen3:8b frozen-decoding locomotion→temperature moves "
            "output into a divergent-favouring regime (NOT walking→divergence, NOT "
            "core-thesis re-proof)",
        ),
        decomp,
        scorer,
    )


def _no_go_reason(decomp: Decomposition) -> str | None:
    if decomp.delta_dq_std_ci_lower < _c.DQ_FLOOR_STD_CI_LOWER:
        return (
            f"ΔDQ_std CI_lower {decomp.delta_dq_std_ci_lower:.3f} < "
            f"{_c.DQ_FLOOR_STD_CI_LOWER}"
        )
    if decomp.delta_dq < _c.DQ_FLOOR_RAW:
        return f"raw ΔDQ {decomp.delta_dq:.4f} < {_c.DQ_FLOOR_RAW}"
    if not decomp.monotone_supported:
        return (
            f"dose non-monotone (min-increment CI_lower "
            f"{decomp.monotone_min_increment_ci_lower:.4f} ≤ 0)"
        )
    if _garbage_a2(decomp) > _c.GARBAGE_RATE_CEILING:
        return f"garbage_rate(A2) {_garbage_a2(decomp):.3f} > {_c.GARBAGE_RATE_CEILING}"
    return None


def _scorer_reason(scorer: ScorerControls) -> str:
    parts: list[str] = []
    if scorer.a1_min_auc < _c.AUC_FLOOR:
        parts.append(f"(a1) min AUC {scorer.a1_min_auc:.3f} < {_c.AUC_FLOOR}")
    if not scorer.a2_residual_survives:
        parts.append(
            f"(a2) held-out residual ΔDQ CI_lower {scorer.a2_residual_ci_lower:.4f} "
            "≤ 0 (entropy proxy)"
        )
    if scorer.adversarial_auc < _c.AUC_FLOOR:
        parts.append(
            f"adversarial judge AUC {scorer.adversarial_auc:.3f} < {_c.AUC_FLOOR}"
        )
    return "; ".join(parts) if parts else "scorer invalid"


__all__ = [
    "BatteryValidity",
    "BudgetStatus",
    "Es4Verdict",
    "ScorerControls",
    "Verdict",
    "evaluate_phase0",
    "evaluate_phase1",
    "required_clusters_for_mde",
]
