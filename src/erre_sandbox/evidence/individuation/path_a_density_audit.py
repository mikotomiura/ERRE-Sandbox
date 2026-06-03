"""M10-A PR-S4c: path(a) density audit + decision/escalation (S4 pre-flight plumbing).

The S4 pre-flight ADR (``.steering/20260603-m10a-s4-preflight-design-adr/``) froze
the last piece of S4's GPU-smoke plumbing: a **density audit** that decides, after a
real corner run, whether the measured 3 same-base individuals carried enough
distinct-other dyads to power the H2 individuation gate, and — combined with the H2
verdict — which forward action (``GO`` / ``Y'_pivot`` / ``Y'_direct`` / ``ESCALATE``)
the program takes. This module is that plumbing. It does **not** run the GPU smoke,
S4, or S5 (all still BLOCK); it is the CPU-verifiable evaluator the smoke drives.

Three layers (ADR §6.0 / §6.1 / §6.2), all pure:

* **measured-3 resolution** (:func:`resolve_focal_measured`): the focal persona's
  ``base_groups`` group — exactly 3 individuals. PR-S4a makes the background
  cross-base / non-focal, so the focal base group isolates the measured trio cleanly
  (disposition §2.4); a legacy same-base run is the single group and resolves
  identically. We key on the focal **identity**, not ``count == 3``: with
  ``DEFAULT_PERSONAS`` = 3 personas a population whose ``world_size`` makes the
  per-base background counts equal 3 would make ``count == 3`` ambiguous (DA-S4C-2).
* **density audit** (:func:`per_owner_density`): per measured owner
  ``D_i = len({other_agent_id})`` (distinct-other, frozen ⑦ / PR-S4b HIGH-2 — a
  duplicated raw unit must not inflate power), then ``min(D_i)`` domination (S3.5a
  HIGH-1: the per-owner vector is kept, never median-compressed, so a skew vector
  ``(20, 20, 1)`` fails on the smallest owner instead of sneaking through a median of
  20). ``d_pass = min(D_i) >= D_TARGET_WEAK (20)``; ``D_TARGET_BONF (30)`` is the
  sensitivity floor. A measured owner with no captured evidence is degenerate, scored
  as an effective ``D_i = 0`` so the same ``min`` domination fails it.
* **decision + escalation** (:func:`decision` / :func:`escalation_feasible`): the
  ADR §6.1 complete table over ``(d_pass, H2 verdict)`` and the ADR §6.2 escalation
  feasibility — a **Šidák-corrected exact-min-of-3** Clopper-Pearson upper confidence
  limit ``rho_upper`` on the smallest owner's ``D_i``, ``feasible`` iff
  ``rho_upper >= D_TARGET / (N_esc - 1) = 20/30``. The frozen fast-fail cutoff is
  ``D_min <= 8`` (Codex round-3 independently re-derived the family-wise
  false-fast-fail rate as 0.0384 at ``<=8`` vs 0.1087 at ``<=9``).

Dependency boundary (PR-S4c plan-review condition ②): this module's **own numerical
code uses ``math`` / stdlib only** (no numpy, no scipy). The Clopper-Pearson upper
limit is computed from a self-contained regularised incomplete beta (Lentz continued
fraction) + a monotone bisection inverse, so the escalation test runs in the slim
default CI (scipy is an eval-extras-only dependency) and the frozen cutoff is pinned
in every environment (DA-S4C-3). It imports only :class:`H2Verdict` from the
``path_a_h2_gate`` leaf for the decision table (so the existing leaf's numpy is read
transitively, which is fine) and **nothing** from ``path_a_gate`` or the frozen §9
judgment path (``c3b_verdict`` / ``centroid_panel`` / ``layer1`` / ``c3b_pipeline``),
so the frozen sentinel stays ``exit=0``.

CPU only — no GPU / model. The audit reads the loader's already-persisted
``world_model_evidence`` (段B); it never re-runs inference.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.individuation.path_a_h2_gate import H2Verdict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.contracts.cognition_layers import PromotedEvidenceUnit
    from erre_sandbox.evidence.eval_store import AnalysisView

# --- frozen S4 pre-flight ADR constants (§6.0 / §6.2, do not re-negotiate) -----
D_TARGET_WEAK: Final[int] = 20
"""§6.0 primary density target: ``min(D_i) >= 20`` for ``d_pass`` (weak-conservative,
stage C). Effect-tier-variable / verdict-derived targets are deliberately NOT used
(continuity-bias guard)."""
D_TARGET_BONF: Final[int] = 30
"""§6.0 Bonferroni sensitivity floor (reported beside the primary, never the gate)."""
MEASURED_INDIVIDUAL_COUNT: Final[int] = 3
"""⑤ N=3 / stage C: the measured same-base trio. Defined locally so this module does
not import the scorer (:mod:`path_a_gate`)."""
N_CORNER: Final[int] = 21
"""§3.1 accept-risk corner world size (I=6 / N=21 operating point)."""
_N_CORNER_TRIALS: Final[int] = N_CORNER - 1
"""Binomial trials per owner: each ``D_i ~ Binomial(N_corner - 1 = 20, rho)`` (one
dyad per other agent, §4.1 yield model)."""
N_ESC: Final[int] = 31
"""§3.3 escalation world size (N_MAX=31). The escalation ceiling ratio is the density
target a robust yield must admit at this size."""
_ESC_CEILING_RATIO: Final[float] = D_TARGET_WEAK / (N_ESC - 1)
"""§6.2 escalation ceiling ``D_target / (N_esc - 1) = 20/30 ≈ 0.667``."""
ALPHA: Final[float] = 0.05
"""§6.2 family-wise false-fast-fail rate ceiling."""
ALPHA_OWNER: Final[float] = 1.0 - (1.0 - ALPHA) ** (1.0 / MEASURED_INDIVIDUAL_COUNT)
"""§6.2 Šidák per-owner level ``1 - (1 - 0.05)^(1/3) ≈ 0.016952`` so the min-of-3
family-wise false-fast-fail stays ``<= ALPHA`` (conservative alt = Bonferroni
``0.05/3 ≈ 0.0167``)."""

# Documented family-wise false-fast-fail rate at the frozen cutoff, for the test's
# math.comb cross-check (Codex round-3 independent re-derivation): at true
# rho = D_target/(N_esc-1) ≈ 0.667, P(min over 3 owners <= 8) ≈ 0.0384 <= ALPHA, while
# <= 9 jumps to ≈ 0.1087 — which is why the cutoff tightens to D_min <= 8.
_FROZEN_FAST_FAIL_CUTOFF: Final[int] = 8
"""§6.2 frozen fast-fail cutoff: ``D_min <= 8`` is escalation-hopeless (Y' direct)."""


class DensityAuditError(RuntimeError):
    """Raised when the measured-3 cannot be resolved or an input is malformed.

    The load-bearing cases are a ``base_groups`` with no focal group (or a focal
    group whose size is not the frozen :data:`MEASURED_INDIVIDUAL_COUNT`), and an
    out-of-domain Clopper-Pearson argument (``k`` / ``n`` / confidence). Both are
    protocol violations that must fail loud rather than silently mis-audit density.
    """


class DecisionAction(StrEnum):
    """The S4→S5 forward action (ADR §6.1 complete decision table)."""

    GO = "go"  # density sufficient ∧ H2 PASS → S5 gate (still a separate gate)
    Y_PIVOT = "y_pivot"  # sufficient density but non-separation → disposition §4.2
    Y_DIRECT = "y_direct"  # INVALID, or escalation-hopeless shortfall
    ESCALATE = "escalate"  # yield-driven shortfall, feasible long-run retry


@dataclass(frozen=True, slots=True)
class DensityAudit:
    """The measured trio's per-owner density audit (ADR §6.0).

    ``per_owner`` keeps the full ``(individual_id, D_i)`` vector (S3.5a HIGH-1: never
    median-compressed) — ``D_i`` is ``None`` for a degenerate owner with no captured
    evidence. ``min_d`` is the ``min(D_i)`` with a degenerate owner counted as an
    effective 0, so a skew vector fails on its smallest owner. ``d_pass`` is the
    primary gate (``min_d >= target``); ``d_pass_bonf`` the Bonferroni sensitivity.
    """

    per_owner: tuple[tuple[str, int | None], ...]
    min_d: int
    d_pass: bool
    d_pass_bonf: bool
    target: int = D_TARGET_WEAK
    degenerate_owners: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EscalationFeasibility:
    """ADR §6.2 escalation feasibility on the smallest owner's ``D_min``.

    ``rho_upper`` is the Šidák-corrected (per-owner ``alpha_owner``) Clopper-Pearson
    upper confidence limit on the per-owner yield; ``feasible`` iff
    ``rho_upper >= ceiling_ratio (20/30)`` (escalation could lift density to target at
    ``N_esc=31``). Otherwise the shortfall is structural (Y' direct).
    """

    d_min: int
    rho_upper: float
    feasible: bool
    alpha_owner: float = ALPHA_OWNER
    ceiling_ratio: float = _ESC_CEILING_RATIO


@dataclass(frozen=True, slots=True)
class DensityDecision:
    """The ADR §6.1 decision-table outcome for one (d_pass, H2 verdict) pair."""

    action: DecisionAction
    reason: str


# --- measured-3 resolution (DA-S4C-2) ----------------------------------------


def resolve_focal_measured(
    base_groups: Sequence[tuple[str, tuple[str, ...]]],
    focal_persona: str,
) -> tuple[str, ...]:
    """Resolve the focal persona's measured trio from the loader ``base_groups``.

    ``base_groups`` is the loader's
    :attr:`~erre_sandbox.evidence.individuation.loader.LoadedRun.base_groups`
    — ``(base_persona_id, sorted individual_ids)`` with one entry per base. The focal
    group must hold exactly :data:`MEASURED_INDIVIDUAL_COUNT` (3) individuals; PR-S4a's
    non-focal background guarantee makes that group the measured trio (DA-S4C-2). Keys
    on the focal **identity**, not a count, so a population whose per-base background
    counts also equal 3 cannot be mistaken for the measured set.

    Raises:
        DensityAuditError: ``focal_persona`` has no group (or, in a malformed
            ``base_groups``, more than one), or its group's size is not the frozen
            :data:`MEASURED_INDIVIDUAL_COUNT`.
    """
    matches = [members for base, members in base_groups if base == focal_persona]
    if len(matches) != 1:
        bases = sorted(base for base, _ in base_groups)
        kind = "is not a base group" if not matches else "appears more than once"
        msg = (
            f"focal persona {focal_persona!r} {kind} in this run"
            f" (bases present: {bases}); the measured trio cannot be resolved"
        )
        raise DensityAuditError(msg)
    members = matches[0]
    if len(members) != MEASURED_INDIVIDUAL_COUNT:
        msg = (
            f"focal base group {focal_persona!r} has {len(members)} individuals"
            f" {sorted(members)}, expected exactly {MEASURED_INDIVIDUAL_COUNT}"
            " (⑤ N=3 / stage C measured trio)"
        )
        raise DensityAuditError(msg)
    return tuple(members)


# --- density audit (DA-S4C-5 / DA-S4C-6) -------------------------------------


def per_owner_density(
    measured_ids: Sequence[str],
    evidence_by_id: Mapping[str, tuple[PromotedEvidenceUnit, ...] | None],
) -> DensityAudit:
    """Per-owner distinct-other density with ``min(D_i)`` domination (ADR §6.0).

    ``D_i = len({u.other_agent_id for u in evidence})`` per measured owner — the
    distinct-other dyad count, so a duplicated raw unit cannot inflate power (frozen
    ⑦ / PR-S4b HIGH-2). A missing / ``None`` evidence entry is a degenerate owner
    (no substrate captured), scored as an effective ``D_i = 0`` so the same
    ``min(D_i)`` domination fails the gate; it is also recorded in
    ``degenerate_owners``. ``d_pass = min(D_i) >= D_TARGET_WEAK`` — the target is the
    frozen weak-conservative 20 (§6.0), **not** a caller-tunable argument (Codex
    HIGH-1: an effect-tier / verdict-derived target is not admitted). The per-owner
    vector is preserved so a skew like ``(20, 20, 1)`` fails on its smallest owner
    (S3.5a HIGH-1, never median-compressed).

    Raises:
        DensityAuditError: ``measured_ids`` is not exactly
            :data:`MEASURED_INDIVIDUAL_COUNT` (3) owners (⑤ N=3, Codex MED-1) — the
            audit may not silently score a widened / shrunk measured set.
    """
    if len(measured_ids) != MEASURED_INDIVIDUAL_COUNT:
        msg = (
            f"per_owner_density requires exactly {MEASURED_INDIVIDUAL_COUNT} measured"
            f" owners (⑤ N=3 / stage C), got {len(measured_ids)}: {list(measured_ids)}"
        )
        raise DensityAuditError(msg)
    per_owner: list[tuple[str, int | None]] = []
    degenerate: list[str] = []
    effective: list[int] = []
    for owner_id in measured_ids:
        ev = evidence_by_id.get(owner_id)
        if ev is None:
            per_owner.append((owner_id, None))
            degenerate.append(owner_id)
            effective.append(0)
        else:
            d_i = len({u.other_agent_id for u in ev})
            per_owner.append((owner_id, d_i))
            effective.append(d_i)
    min_d = min(effective)
    return DensityAudit(
        per_owner=tuple(per_owner),
        min_d=min_d,
        d_pass=min_d >= D_TARGET_WEAK,
        d_pass_bonf=min_d >= D_TARGET_BONF,
        target=D_TARGET_WEAK,
        degenerate_owners=tuple(degenerate),
    )


# --- decision table (ADR §6.1, DA-S4C-9) -------------------------------------


def decision(
    h2_verdict: H2Verdict,
    *,
    d_pass: bool,
    escalation_feasible: bool,
) -> DensityDecision:
    """Map ``(d_pass, H2 verdict)`` to a forward action (ADR §6.1 complete table).

    ``h2_verdict`` is the **already-aggregated** experiment-level H2 verdict (the N=3
    seed-AND + most-severe precedence is the caller's job; this is a pure table).
    ``d_pass`` / ``escalation_feasible`` are keyword-only (boolean-trap guard);
    ``escalation_feasible`` is consulted only in the ``d_fail ∧ (PASS|INCONCLUSIVE)``
    branch (it is the :attr:`EscalationFeasibility.feasible` flag).

    Table (min(D_i) vs D_target=20 × H2 verdict):

    * ``d_pass ∧ PASS`` → ``GO`` (density sufficient ∧ separation; S5 = separate gate)
    * ``d_pass ∧ INCONCLUSIVE`` → ``Y_PIVOT`` (powered but non-separating = signal
      absent; more density cannot save it, stage-A INCONCLUSIVE→NO-GO not relaxed)
    * ``d_pass ∧ INVALID`` → ``Y_DIRECT`` (INVALID precedence)
    * ``d_fail ∧ (PASS|INCONCLUSIVE)`` → ``ESCALATE`` if feasible else ``Y_DIRECT``
    * ``d_fail ∧ INVALID`` → ``Y_DIRECT`` (INVALID precedence)
    """
    if d_pass:
        if h2_verdict is H2Verdict.PASS:
            return DensityDecision(
                DecisionAction.GO,
                "d_pass ∧ H2 PASS: density sufficient and separation demonstrated"
                " → GO (S5 gate is separate)",
            )
        if h2_verdict is H2Verdict.INCONCLUSIVE:
            return DensityDecision(
                DecisionAction.Y_PIVOT,
                "d_pass ∧ H2 INCONCLUSIVE: powered density but non-separation"
                " = individuation signal absent; escalation cannot save it → Y' pivot",
            )
        return DensityDecision(
            DecisionAction.Y_DIRECT,
            "d_pass ∧ H2 INVALID: measurer non-conformant on real emergent substrate"
            " (INVALID precedence) → Y' direct",
        )
    if h2_verdict is H2Verdict.INVALID:
        return DensityDecision(
            DecisionAction.Y_DIRECT,
            "d_fail ∧ H2 INVALID: INVALID precedence → Y' direct",
        )
    if escalation_feasible:
        return DensityDecision(
            DecisionAction.ESCALATE,
            "d_fail ∧ H2 (PASS|INCONCLUSIVE): density shortfall, yield could reach"
            " target at N_esc=31 (rho_upper >= 20/30) → ESCALATE (single long run)",
        )
    return DensityDecision(
        DecisionAction.Y_DIRECT,
        "d_fail ∧ H2 (PASS|INCONCLUSIVE): density shortfall is structural"
        " (rho_upper < 20/30, escalation hopeless) → Y' direct",
    )


# --- escalation feasibility (ADR §6.2, scipy-free Clopper-Pearson) -----------


def escalation_feasible(d_min: int) -> EscalationFeasibility:
    """Šidák-corrected Clopper-Pearson feasibility on ``D_min`` (ADR §6.2).

    ``rho_upper`` is the one-sided upper confidence limit on a single owner's yield at
    the per-owner level :data:`ALPHA_OWNER` (``1 - (1 - 0.05)^(1/3)``, so the min-of-3
    family-wise false-fast-fail stays ``<= ALPHA``). ``feasible`` iff
    ``rho_upper >= D_target/(N_esc-1) = 20/30``. The frozen fast-fail cutoff is
    ``D_min <= 8`` (escalation-hopeless → Y' direct).

    All inputs but ``d_min`` are **frozen constants**, not parameters: the trial count
    (:data:`_N_CORNER_TRIALS` = 20), ``ALPHA`` and ``ALPHA_OWNER`` are not
    caller-tunable, so the frozen cutoff cannot be re-negotiated through this API
    (Codex HIGH-2).
    """
    rho_upper = clopper_pearson_upper(d_min, _N_CORNER_TRIALS, 1.0 - ALPHA_OWNER)
    return EscalationFeasibility(
        d_min=d_min,
        rho_upper=rho_upper,
        feasible=rho_upper >= _ESC_CEILING_RATIO,
        alpha_owner=ALPHA_OWNER,
        ceiling_ratio=_ESC_CEILING_RATIO,
    )


def clopper_pearson_upper(k: int, n: int, conf: float) -> float:
    """One-sided Clopper-Pearson upper confidence limit (scipy-free, DA-S4C-4).

    ``rho_upper = BetaInv(conf; k + 1, n - k)`` (the Beta/Binomial duality), with the
    accident-prone boundaries handled explicitly:

    * invalid input (``n <= 0`` / ``k < 0`` / ``k > n`` / not ``0 < conf < 1``) →
      :class:`DensityAuditError`;
    * ``k == n`` → ``1.0`` (the ``Beta(k+1, 0)`` degenerate case — the upper limit on
      a fully-saturated owner is exactly 1, never passed to the bisection);
    * ``k == 0`` → the ordinary ``BetaInv(conf; 1, n)`` path (no special case needed;
      pinned by the test).
    """
    if n <= 0 or k < 0 or k > n:
        msg = f"clopper_pearson_upper requires 0 <= k <= n and n > 0, got k={k}, n={n}"
        raise DensityAuditError(msg)
    if not 0.0 < conf < 1.0:
        msg = f"clopper_pearson_upper requires 0 < conf < 1, got conf={conf}"
        raise DensityAuditError(msg)
    if k == n:
        return 1.0
    return _beta_ppf(conf, k + 1, n - k)


def _beta_ppf(p: float, a: float, b: float) -> float:
    """Inverse regularised incomplete beta (quantile) by monotone bisection.

    ``I_x(a, b)`` is strictly increasing in ``x`` on ``(0, 1)``, so a 200-step
    bisection on ``[0, 1]`` converges to far below double precision. Deterministic —
    no RNG, no scipy.
    """
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _reg_incomplete_beta(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _reg_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta ``I_x(a, b)`` (Lentz continued fraction, NR betai).

    Uses the symmetry ``I_x(a, b) = 1 - I_{1-x}(b, a)`` for ``x > (a+1)/(a+b+2)`` so
    the continued fraction is always evaluated in its fast-converging regime. ``math``
    only (no numpy / scipy).
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    ln_front = a * math.log(x) + b * math.log1p(-x) - ln_beta
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(ln_front) / a * _betacf(a, b, x)
    return 1.0 - math.exp(ln_front) / b * _betacf(b, a, 1.0 - x)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (modified Lentz, NR §6.4).

    Raises :class:`DensityAuditError` if the fraction does not converge within
    ``max_iter`` (a silent non-converged return is a numerical-accident hazard, Codex
    LOW-1; within the frozen domain it always converges in a handful of steps).
    """
    max_iter: Final[int] = 300
    eps: Final[float] = 3.0e-16
    fp_min: Final[float] = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fp_min:
        d = fp_min
    d = 1.0 / d
    h = d
    converged = False
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fp_min:
            d = fp_min
        c = 1.0 + aa / c
        if abs(c) < fp_min:
            c = fp_min
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fp_min:
            d = fp_min
        c = 1.0 + aa / c
        if abs(c) < fp_min:
            c = fp_min
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            converged = True
            break
    if not converged:
        msg = (
            f"incomplete-beta continued fraction did not converge in {max_iter}"
            f" iterations (a={a}, b={b}, x={x})"
        )
        raise DensityAuditError(msg)
    return h


# --- view-level wiring -------------------------------------------------------


def audit_density_from_view(
    view: AnalysisView,
    *,
    run_id: str,
    focal_persona: str,
) -> DensityAudit:
    """Audit the focal trio's density from an open analysis view (S4 plumbing).

    Resolves the measured trio from the raw_dialog ``base_groups`` and reads each
    owner's final-tick ``world_model_evidence`` (段B) from the trace, then runs
    :func:`per_owner_density`. A measured individual absent from the trace (flag-off /
    no SWM) maps to ``None`` evidence = degenerate. This does **not** run the gate or
    the GPU smoke — it is the density half of the S4 pre-flight plumbing.

    Raises:
        DensityAuditError: the run is absent, or the focal trio cannot be resolved.
    """
    from erre_sandbox.evidence.individuation.loader import (  # noqa: PLC0415  # cycle-safe lazy
        load_individual_state_windows,
        load_individual_windows,
    )

    loaded = next((run for run in load_individual_windows(view, run_id=run_id)), None)
    if loaded is None:
        msg = f"no run {run_id!r} present in the view"
        raise DensityAuditError(msg)
    measured_ids = resolve_focal_measured(loaded.base_groups, focal_persona)
    state_windows = load_individual_state_windows(view, run_id=run_id)
    evidence_by_id: dict[str, tuple[PromotedEvidenceUnit, ...] | None] = {
        owner_id: (
            state_windows[(run_id, owner_id)].world_model_evidence
            if (run_id, owner_id) in state_windows
            else None
        )
        for owner_id in measured_ids
    }
    return per_owner_density(measured_ids, evidence_by_id)


__all__ = [
    "ALPHA",
    "ALPHA_OWNER",
    "D_TARGET_BONF",
    "D_TARGET_WEAK",
    "MEASURED_INDIVIDUAL_COUNT",
    "N_CORNER",
    "N_ESC",
    "DecisionAction",
    "DensityAudit",
    "DensityAuditError",
    "DensityDecision",
    "EscalationFeasibility",
    "audit_density_from_view",
    "clopper_pearson_upper",
    "decision",
    "escalation_feasible",
    "per_owner_density",
    "resolve_focal_measured",
]
