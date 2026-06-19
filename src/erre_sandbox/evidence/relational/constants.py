"""Read-side gate values for the ``swm_bond_affinity_trace`` diagnostic (ADR 3.4).

These are the **gate values the loader recomputes with** — the capture (the trace
builder) bakes in none of them, so already-captured stock stays re-analysable if a
value later moves (recompute-stable, ADR section 3.2). The two promotion-gate values
mirror their ``cognition.belief`` twins (``BELIEF_THRESHOLD`` /
``BELIEF_MIN_INTERACTIONS``) as **local** constants rather than importing across the
``evidence -> cognition`` boundary (the same pattern
:mod:`erre_sandbox.evidence.saturation.constants` uses for the cap).

The cross-arm *decision* thresholds (``R_MIN_BOND`` / ``DEGENERATE_GAP_FLOOR`` /
``ON_NOISE_FACTOR`` / ``MIN_NEAR_MISS_N`` / ``MIN_PAIRED_SEEDS`` / ``SLOPE_WINDOW``)
were previously deferred to a future GO/NO-GO ADR. That ADR is now **ACCEPTED**
(``.steering/20260617-bond-affinity-diagnostic-freeze/threshold-freeze-adr.md`` §1,
binding=user, 2026-06-17): every value below was fixed **before** any real run was
scored (forking-paths guard), mirroring the III-a live §5.3 pre-GPU freeze. As with
:mod:`erre_sandbox.evidence.live_carry.constants`, a value can only change by a
deliberate edit here, which itself requires a **superseding ADR** — none is read off a
result and then tuned. ``loader.score_bond_affinity`` imports these as the (frozen)
defaults of its keyword parameters; a caller may override only for unit tests.
"""

from __future__ import annotations

from typing import Final

# --- promotion-gate values the read side recomputes the near-miss with (ADR 3.1/3.4) -
BELIEF_THRESHOLD: Final[float] = 0.45
"""``|affinity| < this`` is the affinity-gate near-miss condition.

Mirrors ``cognition.belief.BELIEF_THRESHOLD`` (ADR section 3.1) as a local copy — the
diagnostic never imports cognition. A bond at or above this has already promoted; the
diagnostic studies the sub-threshold population just below it."""

BELIEF_MIN_INTERACTIONS: Final[int] = 6
"""``ichigo_ichie_count >= this`` is the interaction-count gate near-miss condition.

Mirrors ``cognition.belief.BELIEF_MIN_INTERACTIONS`` (ADR section 3.1). The near-miss
population satisfies this gate so that **only** the affinity gate is binding (ADR
section 2) — isolating whether the cap suppresses the affinity approach."""

EPS_BAND_LO: Final[float] = 0.43
"""Lower edge of the ε-band density ``P(EPS_BAND_LO <= |affinity| < BELIEF_THRESHOLD)``
(ADR section 3.4) — the fraction of the near-miss population sitting in the last 0.02
below the gate. A descriptive proximity measure, not a verdict threshold."""

# --- cap-saturation exposure detection (mirrors evidence.saturation, ADR section 2) --
CAP_OFFSET: Final[float] = 0.15
"""A saturation-trace row is *at cap* when ``|modulated - base_floor| >= this`` (within
:data:`CAP_SATURATION_TOL`). Mirrors ``evidence.saturation.MAX_TOTAL_MODULATION`` /
``cognition.world_model.MAX_TOTAL_MODULATION`` (USE-only, local copy). Used to find
the cap-saturated ``(individual, tick)`` exposures the near-miss bonds join against."""

CAP_SATURATION_TOL: Final[float] = 1e-9
"""IEEE-754 boundary tolerance for the at-cap comparison (mirrors the live scorer's
``M2_CAP_FLOAT_TOL``): ``3 * 0.05`` evaluates to ``0.15000000000000002``, so an at-cap
offset must be tolerated rather than missed. Not a relaxation of any gate."""

# --- v2 cross-arm decision thresholds (freeze ADR §1, ACCEPTED 2026-06-17) -----------
# Single source of truth, fixed before any real run was scored. Changing any value
# requires a superseding ADR (forking-paths guard). The scorer's signal-to-noise
# decision is non-circular: it compares the cross-arm ON-OFF separation against the
# same-arm run-to-run noise floor (the live §5.3 null-hierarchy structure, ported).

R_MIN_BOND: Final[float] = 2.0
"""(i)-LEANING ratio floor: ``median_seed S(ON-OFF) / max_seed S(OFF/OFF null) >= this``
when the null is non-degenerate (freeze ADR §1). Mirrors live §5.3 ``R_MIN`` — a
cross-arm separation under twice the run-to-run noise floor does not warrant claiming
the ON arm pushes near-miss bonds closer to the gate. Change needs a superseding ADR."""

DEGENERATE_GAP_FLOOR: Final[float] = 0.02
"""Always-required materiality floor ``median_seed S(ON-OFF) >= this``, and the
degenerate-null boundary (freeze ADR §1). The null is *degenerate* (ratio undefined)
when ``max_seed S(OFF/OFF null) < this / R_MIN_BOND``; the separation must then clear
this absolute floor instead of a ratio, closing the near-zero-null ratio blow-up
(``max_null = 1e-6`` faking a huge ratio, Codex HIGH-2). Sized at the ε-band width
(``BELIEF_THRESHOLD - EPS_BAND_LO`` = 0.45 - 0.43 = 0.02). Same role as live §5.3
``DEGENERATE_NULL_FLOOR``. Change requires a superseding ADR."""

ON_NOISE_FACTOR: Final[float] = 1.5
"""ON-noise sanity: ``max_seed S(ON/ON null) <= this * max_seed S(OFF/OFF null)`` or the
ON arm is suspected of fabricating separation through its own run-to-run noise → the
verdict downgrades to INCONCLUSIVE_LOW_POWER (freeze ADR §1, mirrors live §5.3
``ON_NOISE_FACTOR``). Change requires a superseding ADR."""

MIN_NEAR_MISS_N: Final[int] = 10
"""Per-replicate-cell near-miss count floor (freeze ADR §1). A *paired seed* requires
**all four** replicate cells (ON r0 / OFF r0 / OFF r1 / ON r1) to have ``>= this``
near-miss observations, so a low-N cell cannot shrink the null estimate (Codex MED-1).
Mirrors the live §5.3 ``MIN_TICK_PAIRS`` logic. Change requires a superseding ADR."""

MIN_PAIRED_SEEDS: Final[int] = 2
"""Minimum number of paired seeds (all four cells satisfied) for a substantive verdict
(freeze ADR §1). With ``N_SEED=3`` this is **2-of-3 dropout-tolerant** (a single paired
seed is not seed-reproducible); the (i)-LEANING claim strength is bounded to this
tolerance (Codex MED-3 — a strong GO would need seed-AND = 3). Change requires a
superseding ADR."""

SLOPE_WINDOW: Final[int] = 5
"""Lagged-|affinity|-slope window (ticks) for the stale-bond guard (freeze ADR §1).
Descriptive (it shapes which bonds count as a *fresh* approach), not a verdict cutoff;
frozen here so the single source covers it too. Change requires a superseding ADR."""

# --- estimand-redesign superseding ADR §1' (ACCEPTED 2026-06-19) ---------------------
# The freeze-ADR §2 estimand (exposure-gated cross-arm proximity) is superseded by a
# bare-gate primary + within-ON cap-saturation secondary (estimand-redesign-adr.md §2').
# The §1 values above are *temporally preserved* (re-used unchanged by the bare-gate
# substrate). This one value is *added* by the superseding ADR, frozen result-blind
# (the v2 routed S / verdict numbers were not read before fixing it, §0/§1').

PROMOTION_IMBALANCE_FACTOR: Final[float] = 2.0
"""Truncation guard (superseding ADR §1'/§3', Codex HIGH-2): the bare near-miss
substrate is an outcome-band (``|affinity| < BELIEF_THRESHOLD``) selection, so an ON arm
that promotes bonds *past* the 0.45 gate drains its own near-miss pool — the surviving
``(ii)``-LEANING p95 can then be a survivor artifact, not a real null. Per cell the
promotion incidence is ``ρ = (distinct dyads reaching |affinity| >= BELIEF_THRESHOLD
with the interaction gate met) / distinct ticks``; when
``median_seed ρ(ON r0) / median_seed ρ(OFF r0) > this`` the verdict suppresses a bare
``(ii)``-LEANING and routes ``INCONCLUSIVE_TRUNCATED`` instead. A degenerate
``ρ(OFF)=0`` fires the guard only when the ON promotion is non-negligible against the
surviving near-miss pool (``median ON promoted dyads >= median ON near-miss n / this``),
so a single stray promotion cannot trip it. The guard is asymmetric — applied only to
the ``(ii)`` route, never ``(i)`` (a drained survivor pool weakens ``(i)``, so ``(i)``
needs no such protection, §3'). Same ``2.0`` spirit as ``R_MIN_BOND`` (ON at 2x OFF is
where differential promotion becomes plausible). Change requires a superseding ADR."""

__all__ = [
    "BELIEF_MIN_INTERACTIONS",
    "BELIEF_THRESHOLD",
    "CAP_OFFSET",
    "CAP_SATURATION_TOL",
    "DEGENERATE_GAP_FLOOR",
    "EPS_BAND_LO",
    "MIN_NEAR_MISS_N",
    "MIN_PAIRED_SEEDS",
    "ON_NOISE_FACTOR",
    "PROMOTION_IMBALANCE_FACTOR",
    "R_MIN_BOND",
    "SLOPE_WINDOW",
]
