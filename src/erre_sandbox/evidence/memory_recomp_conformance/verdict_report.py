"""Frozen conjunctive verdict for the memory-recomposition seam (§4-4 / §5).

Pure decision logic over the per-scenario-seed readouts (:class:`SeedResult`).
Every threshold is read from :mod:`constants`; this module holds **no** tunable
literal of its own. The structure mirrors the ES-1 / ES-2 house style: the
INCONCLUSIVE gate is checked **first** (so an under-powered or ill-posed
measurement is never reported as a progressive NO_GO), then the conjunctive GO
condition (``CI_lower > 0``).

Verdict vocabulary (design-final.md §4-4, kept distinct):

* **GO** — adequate power ∧ a well-posed, non-degenerate channel, and the per-seed
  conformance ``{delta_s}`` bootstrap CI lower bound > 0: the recomposition channel
  gives an independent downstream discrete choice a non-circular causal bias. Means
  *the memory-recomposition seam is a necessary substrate* (ES-1 / ES-3 boundary),
  **not** proof of H4.
* **NO_GO** — adequate power ∧ valid channel, yet the conformance CI straddles or
  falls below 0. A **progressive** finding (this C→D pairing does not couple), not a
  refutation. A different pairing needs a fresh pre-register (design-final.md §6).
* **INCONCLUSIVE** — too few valid seeds, an ill-posed channel (argmax unstable), a
  degenerate channel (effective support collapsed), an underpowered apparatus
  (synthetic power gate), or a cost-ceiling abort. Never conflated with NO_GO.

Claim boundary is emitted as machine-readable first-class fields
(``claim_scope`` / ``live_agent_connected``, design-final.md §5 / Codex LOW-1) so
over-reading does not depend on prose alone.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from erre_sandbox.evidence.memory_recomp_conformance import constants as _c
from erre_sandbox.evidence.memory_recomp_conformance.conformance_stats import (
    deltas_ci,
    exact_permutation_null_quantile,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

RecompStatus = Literal["GO", "NO_GO", "INCONCLUSIVE"]
ClaimScope = Literal["synthetic_post_idle_walk_only"]


@dataclass(frozen=True)
class SeedResult:
    """Per-scenario-seed readouts for one blind apparatus instantiation.

    ``conform_row`` is the ``(Z,)`` per-zone entropy-reduction vector; ``delta_s`` is
    computed at aggregation time (it needs the *population* of ``target_zone``
    assignments for the pairing-destroying null), so it is not stored here.
    """

    seed: int
    valid: bool
    """``H(marginal) > 0`` and ``conform_row`` finite (non-degenerate walk)."""
    start_zone: int
    target_zone: int
    """The channel's ``zone_of_formation(to_content)`` — the D-walk bonus zone."""
    conform_row: tuple[float, ...]
    """``conform_s(z)`` for every zone ``z`` (paired scale-free entropy reduction)."""
    argmax_stability: float
    """Channel argmax bootstrap-resample recovery rate (ill-posed-channel guard)."""
    channel_effective_support: float
    """Channel transition distribution inverse-Simpson support (collapse guard)."""


@dataclass(frozen=True)
class RecompVerdict:
    """The memory-recomposition seam verdict and the statistics that produced it."""

    recomposition_channel_status: RecompStatus
    reasons: tuple[str, ...]
    n_valid_seeds: int
    median_conform: float
    ci_lower: float
    ci_upper: float
    median_argmax_stability: float
    median_channel_effective_support: float
    synthetic_power_pass_rate: float
    coupling_strength_used: float
    # --- machine-readable claim boundary (design-final.md §5 / Codex LOW-1) ---
    claim_scope: ClaimScope
    live_agent_connected: Literal[False]


def _median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0.0


def compute_deltas(valid_results: Sequence[SeedResult]) -> list[float]:
    """Per-seed ``delta_s = conform_s(target_zone_s) - null_q_s`` over valid seeds.

    The pairing-destroying null for seed ``s`` draws on the *other* valid seeds'
    ``target_zone`` assignments (design-final.md §2 / §4-4), computed exactly.
    """
    target_zones = np.array([r.target_zone for r in valid_results], dtype=np.int64)
    deltas: list[float] = []
    for s, r in enumerate(valid_results):
        row = np.asarray(r.conform_row, dtype=np.float64)
        null_q = exact_permutation_null_quantile(
            row, target_zones, s, _c.PERM_NULL_QUANTILE
        )
        deltas.append(float(row[r.target_zone] - null_q))
    return deltas


def _inconclusive_reason(
    *,
    cost_ceiling_exceeded: bool,
    n_valid: int,
    median_argmax: float,
    median_supp: float,
    synthetic_power_pass_rate: float,
) -> str | None:
    """First INCONCLUSIVE trigger (design §4-4), else None (checked before GO/NO_GO).

    Order matters: an ill-posed / degenerate / underpowered measurement must never be
    reported as a (progressive) NO_GO finding.
    """
    if cost_ceiling_exceeded:
        return "cost ceiling exceeded (90 min wall clock)"
    if n_valid < _c.MIN_VALID_SEEDS:
        return f"valid seeds {n_valid} < MIN_VALID_SEEDS {_c.MIN_VALID_SEEDS}"
    if median_argmax < _c.ARGMAX_STABILITY_MIN:
        return (
            f"channel ill-posed: median argmax stability {median_argmax:.4f} < "
            f"ARGMAX_STABILITY_MIN {_c.ARGMAX_STABILITY_MIN}"
        )
    if median_supp < _c.EFFECTIVE_SUPPORT_MIN:
        return (
            f"channel degenerate: median effective support {median_supp:.4f} < "
            f"EFFECTIVE_SUPPORT_MIN {_c.EFFECTIVE_SUPPORT_MIN}"
        )
    if synthetic_power_pass_rate < _c.SYNTHETIC_POWER_PASS_MIN:
        return (
            f"underpowered: synthetic power {synthetic_power_pass_rate:.4f} < "
            f"SYNTHETIC_POWER_PASS_MIN {_c.SYNTHETIC_POWER_PASS_MIN}"
        )
    return None


def evaluate_verdict(
    seeds: Sequence[SeedResult],
    *,
    synthetic_power_pass_rate: float,
    coupling_strength_used: float,
    cost_ceiling_exceeded: bool = False,
    bootstrap_seed: int = 0,
) -> RecompVerdict:
    """Render the frozen verdict from per-scenario-seed readouts.

    ``synthetic_power_pass_rate`` is the ``1.0 × POLYA_ALPHA`` rung of the synthetic
    power ladder; ``coupling_strength_used`` must equal ``POLYA_ALPHA`` (tune-to-pass
    audit — a mismatch is a wiring bug, not a soft failure). All thresholds come from
    :mod:`constants`; nothing here is tuned post-result.
    """
    if coupling_strength_used != _c.POLYA_ALPHA:
        msg = (
            "coupling_strength_used must equal the frozen POLYA_ALPHA "
            f"({_c.POLYA_ALPHA}); got {coupling_strength_used} — a new free effect "
            "parameter leaked into D (design-final.md §6)"
        )
        raise ValueError(msg)

    valid = [s for s in seeds if s.valid]
    n_valid = len(valid)
    median_argmax = _median([s.argmax_stability for s in valid])
    median_supp = _median([s.channel_effective_support for s in valid])

    deltas = compute_deltas(valid)
    finite_deltas = [d for d in deltas if math.isfinite(d)]  # drop NaN (invalid seed)
    if len(finite_deltas) >= 2:  # noqa: PLR2004 — need ≥2 to bootstrap
        ci = deltas_ci(
            finite_deltas,
            n_resamples=_c.N_RESAMPLES,
            ci_alpha=_c.CI_ALPHA,
            seed=bootstrap_seed,
        )
        ci_lower, ci_upper = ci.lo, ci.hi
        median_conform = float(_median(finite_deltas))
    else:
        ci_lower = ci_upper = 0.0
        median_conform = 0.0

    def _pack(status: RecompStatus, reasons: tuple[str, ...]) -> RecompVerdict:
        return RecompVerdict(
            recomposition_channel_status=status,
            reasons=reasons,
            n_valid_seeds=n_valid,
            median_conform=median_conform,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            median_argmax_stability=median_argmax,
            median_channel_effective_support=median_supp,
            synthetic_power_pass_rate=synthetic_power_pass_rate,
            coupling_strength_used=coupling_strength_used,
            claim_scope="synthetic_post_idle_walk_only",
            live_agent_connected=False,
        )

    # --- INCONCLUSIVE gate (checked first, conjunctive-guard order) ---
    incon = _inconclusive_reason(
        cost_ceiling_exceeded=cost_ceiling_exceeded,
        n_valid=n_valid,
        median_argmax=median_argmax,
        median_supp=median_supp,
        synthetic_power_pass_rate=synthetic_power_pass_rate,
    )
    if incon is not None:
        return _pack("INCONCLUSIVE", (incon,))

    # --- conjunctive GO condition (CI lower bound > 0) ---
    if ci_lower > 0.0:
        return _pack(
            "GO",
            (
                "conformance CI lower > 0; recomposition channel biases D (necessary "
                "substrate, not H4)",
            ),
        )
    return _pack(
        "NO_GO",
        (
            f"conformance CI lower {ci_lower:.4f} <= 0 (90% CI): channel does not "
            "couple to D for this pairing (progressive)",
        ),
    )


__all__ = [
    "ClaimScope",
    "RecompStatus",
    "RecompVerdict",
    "SeedResult",
    "compute_deltas",
    "evaluate_verdict",
]
