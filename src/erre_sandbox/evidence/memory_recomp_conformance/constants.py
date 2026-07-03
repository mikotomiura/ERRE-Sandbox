"""Frozen constants for the memory-recomposition seam channel-conformance verdict.

This module is the **single source of truth** for every value the pre-registration
freeze fixed **before** any conformance result was seen (forking-paths guard,
mirroring :mod:`erre_sandbox.evidence.es2_replay.constants`). Two kinds of value
live here:

1. **Inherited (byte, import-only)** — the house-style statistics constants come
   straight from ``es2_replay.constants`` via ``_es2_c`` and are **never
   re-declared or re-tuned** (design-final.md §6). Re-exporting (rather than
   copying the literal) makes the byte inheritance machine-checkable: the pin test
   asserts identity with the ES-2 source.
2. **Newly frozen (this ADR §8, ``DA-MEMSEAM-IMPL-1``)** — the three gate
   thresholds, the ``zone_of_formation`` contract, and the deterministic RNG
   stream namespacing. These were fixed from **result-independent principle**
   (majority rule / Cohen 1988 power convention / D0-pack ``MIN_PROP_ZONES``
   analogue / 1:1 formation), **before** the verdict run, in Plan mode + Opus.

A value can only change by a deliberate edit here, which itself requires a
**superseding ADR**. The freeze is pinned verbatim in
``tests/test_evidence/test_memory_recomp_conformance_constants.py``.

Claim boundary (design-final.md §4): a GO verdict means "the recomposition channel
gives an independent downstream discrete choice a non-circular causal bias"
(necessary-substrate type), **not** proof of H4. NO_GO is progressive;
INCONCLUSIVE is kept distinct.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from erre_sandbox.evidence.es2_replay import constants as _es2_c

# --- inherited house-style constants (byte, import-only; never re-declared) ----
# design-final.md §6: continue the ES-1/ES-2/ES-3 house style. Re-exported from the
# ES-2 source so the pin test can assert *identity*, not just value-equality.

POLYA_ALPHA: Final[float] = _es2_c.POLYA_ALPHA
"""Pólya-urn prior weight, also **reused verbatim** as the ``target_zone`` coupling
bonus strength (no new free effect parameter, design-final.md §6)."""

M_FRAGMENTS: Final[int] = _es2_c.M_FRAGMENTS
"""Formation-trajectory length = experience-fragment count; also the post-idle
occupancy-walk length (no new constant)."""

POST_IDLE_REALIZATIONS: Final[int] = 256
"""Post-idle occupancy-walk realizations pooled per config to estimate the
**expected** occupancy distribution (design-final.md §2 conditions ``D`` on ``C``
*in distribution*, not in a single realization). A Monte-Carlo precision constant,
not an effect knob: derived from the ES-2 per-arm pooled sample size
(``N_REPLAY·(L_SEED-1) ≈ 4096·3 = 12288`` transitions) at walk length
``M_FRAGMENTS``: ``12288 / 48 = 256`` (``DA-MEMSEAM-IMPL-5``). A single realization
makes ``conform_s`` degenerate (exactly 0 whenever the bonus flips no discrete
selection); pooling recovers the smooth expected entropy reduction."""

L_SEED: Final[int] = _es2_c.L_SEED
"""Fragments per idle-recomposition replay seed (ES-2 kernel input)."""

N_REPLAY: Final[int] = _es2_c.N_REPLAY
"""Idle-recomposition replay seeds generated per scenario seed (produces C)."""

N_SEED: Final[int] = _es2_c.N_SEED
"""Scenario-seed count = the outer independent unit for the bootstrap CI."""

N_PERM: Final[int] = _es2_c.N_PERM
"""C↔D pairing-destroying permutation ceiling per scenario seed. The permuted
``target_zone`` support is only ``Z = 5`` zones, so rather than draw ``N_PERM``
samples the null is computed **deterministically** as the exact Type-7 empirical
quantile over the population ``target_zone`` assignments (design-final.md §4-4).
Note (TASK-POST cross-review, ``DA-MEMSEAM-IMPL-7``): this population Type-7 quantile
is *not identical* to the ``N_PERM → ∞`` sampling limit (which converges to the
inverse-CDF quantile) — they differ by ``≤ 0.00247`` on this run, **verdict-invariant**
(the argmax gate fires first). The deterministic form is used for reproducibility.
Pinned as the pre-registered ceiling."""

PERM_NULL_QUANTILE: Final[float] = _es2_c.PERM_NULL_QUANTILE
"""One-sided upper quantile of the per-seed permutation null that ``delta_s`` is
measured against (integrates with the 90 % one-sided ``CI_ALPHA``)."""

CI_ALPHA: Final[float] = _es2_c.CI_ALPHA
"""Two-sided alpha for the bootstrap CI of ``{delta_s}`` (90 % CI). GO requires the
CI **lower** bound > 0; a CI straddling 0 is NO_GO (adequate power) — never tuned."""

N_RESAMPLES: Final[int] = _es2_c.N_RESAMPLES
"""Bootstrap resample count (ES-1 integration) so CI stability matches the
established metric pipeline. Also the argmax-stability resample budget."""

MIN_VALID_SEEDS: Final[int] = _es2_c.MIN_VALID_SEEDS
"""Minimum valid scenario seeds (of ``N_SEED``); below it → INCONCLUSIVE."""

# --- newly frozen gate thresholds (this ADR §8, DA-MEMSEAM-IMPL-1) -------------
# Fixed from result-independent principle in Plan mode + Opus, BEFORE the verdict
# run (D0-pack CONE_APERTURE_DEG-style "ratify-time numeric freeze"). Changing any
# of these requires a superseding ADR.

ARGMAX_STABILITY_MIN: Final[float] = 0.5
"""Lower bound on the channel argmax's bootstrap-resample recovery rate. **Majority
rule**: below 0.5 some other cell is at least as often the resampled argmax, so
"this is *the* dominant transition cell ``C``" is not even majority-supported ⇒ the
channel is ill-posed ⇒ INCONCLUSIVE. The minimal non-arbitrary well-posedness bar
(literature echo: DAT / generalization cards flag the argmax discrete summary as
unstable — this diagnostic is exactly that guard)."""

EFFECTIVE_SUPPORT_MIN: Final[float] = 2.0
"""Lower bound on the channel transition distribution's inverse-Simpson effective
support (``1/Σp²``). Below 2 one cell holds the overwhelming mass and the argmax is
the *sole* occupant, not a competitive winner ⇒ degenerate channel ⇒ INCONCLUSIVE.
D0-pack ``MIN_PROP_ZONES = 2`` analogue ("need ≥2 contenders to speak of a
winner"). In the ES-2 near-uniform regime (effective support ~1635) this passes
trivially; it binds only the opposite collapse case."""

SYNTHETIC_POWER_PASS_MIN: Final[float] = 0.80
"""Pass bar for the synthetic-surrogate power simulation at the true coupling
strength (``1.0 × POLYA_ALPHA``): the fraction of synthetic replicate banks — built
with a *known* injected channel effect — that recover ``CI_lower > 0``. Below it the
statistics are underpowered for the effect the design targets ⇒ INCONCLUSIVE.
**Cohen (1988) 0.80 power convention**, a data-independent textbook standard. The
simulation touches synthetic data only; it never reads the real verdict."""

# --- synthetic power-simulation parameters (feasibility gate, design-final.md §4-2)
SYNTH_COUPLING_LADDER: Final[tuple[float, ...]] = (0.0, 0.25, 0.5, 1.0)
"""Injected coupling strengths (× ``POLYA_ALPHA``) for the power ladder. 0.0 is the
null-calibration rung (no effect ⇒ detection ≈ ``CI_ALPHA``); 1.0 is the design's
actual strength, gated by ``SYNTHETIC_POWER_PASS_MIN``. These are **simulation**
parameters, not real-verdict effect knobs (design-final.md §6)."""

SYNTH_N_REPLICATES: Final[int] = 100
"""Synthetic replicate banks per ladder rung (detection-rate precision SE ≈ 0.04 at
rate 0.8). A simulation-precision choice like ``N_RESAMPLES``, not an effect knob."""

# --- deterministic RNG stream namespacing (design-final.md §5) -----------------
# ``_rng(seed, stream) = np.random.default_rng([_SEED_BASE, seed, stream])``. The
# base differs from ES-2's ``0x_E5_2A`` so the two homes' streams never collide even
# at equal (seed, stream). C and D take DISTINCT streams: D's occupancy walk shares
# nothing with C's replay batch but the target_zone bonus (the §5 independence).

_SEED_BASE: Final[int] = 0x_135C
"""``memory_recomp_conformance``-private RNG base (M13 + SC = Seam-Conformance).
Distinct from ES-2's ``0x_E5_2A`` (verified sole ``_SEED_BASE`` in evidence/)."""

STREAM_C_IDLE: Final[int] = 0
"""Idle-recomposition replay batch stream (produces the channel ``C``)."""

STREAM_D_POST_IDLE: Final[int] = 1
"""Independent post-idle occupancy-walk stream (produces the decision ``D``)."""

STREAM_ARGMAX_BOOT: Final[int] = 2
"""Argmax-stability bootstrap-resample stream (channel well-posedness diagnostic).
The pairing-destroying null needs no stream — it is computed exactly (see
``N_PERM``)."""

STREAM_SYNTH_POWER: Final[int] = 3
"""Synthetic power-simulation stream (feasibility gate, synthetic data only)."""


def stream_rng(seed: int, stream: int) -> np.random.Generator:
    """Independent reproducible numpy stream for one ``(scenario seed, role)``.

    ``np.random.default_rng([_SEED_BASE, seed, stream])``. The base differs from
    ES-2's ``0x_E5_2A`` so the two homes' streams never collide even at equal
    ``(seed, stream)`` (design-final.md §5). Kept here so the private ``_SEED_BASE``
    is never accessed across modules.
    """
    return np.random.default_rng([_SEED_BASE, seed, stream])


__all__ = [
    "ARGMAX_STABILITY_MIN",
    "CI_ALPHA",
    "EFFECTIVE_SUPPORT_MIN",
    "L_SEED",
    "MIN_VALID_SEEDS",
    "M_FRAGMENTS",
    "N_PERM",
    "N_REPLAY",
    "N_RESAMPLES",
    "N_SEED",
    "PERM_NULL_QUANTILE",
    "POLYA_ALPHA",
    "POST_IDLE_REALIZATIONS",
    "SYNTHETIC_POWER_PASS_MIN",
    "SYNTH_COUPLING_LADDER",
    "SYNTH_N_REPLICATES",
    "stream_rng",
]
