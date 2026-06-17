"""Read-side gate values for the ``swm_bond_affinity_trace`` diagnostic (ADR 3.4).

These are the **gate values the loader recomputes with** — the capture (the trace
builder) bakes in none of them, so already-captured stock stays re-analysable if a
value later moves (recompute-stable, ADR section 3.2). The two promotion-gate values
mirror their ``cognition.belief`` twins (``BELIEF_THRESHOLD`` /
``BELIEF_MIN_INTERACTIONS``) as **local** constants rather than importing across the
``evidence -> cognition`` boundary (the same pattern
:mod:`erre_sandbox.evidence.saturation.constants` uses for the cap).

What is **deliberately not** here: the numeric ``(i)``-vs-``(ii)`` verdict cutoff and
the low-power N floor. Those are the cross-arm *decision* thresholds, and per the
project's forking-paths guard they must be frozen by a future GO/NO-GO ADR (mirroring
the III-a live §5.3 pre-GPU freeze) **before** any real run is scored — not invented
here while no stock exists to tune against. ``loader.score_bond_affinity`` therefore
takes them as explicit parameters with documented provisional defaults.
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

__all__ = [
    "BELIEF_MIN_INTERACTIONS",
    "BELIEF_THRESHOLD",
    "CAP_OFFSET",
    "CAP_SATURATION_TOL",
    "EPS_BAND_LO",
]
