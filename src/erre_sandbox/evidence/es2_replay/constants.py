"""Frozen §11 constants for the M13-ES2 path-recombination replay verdict.

This module is the **single source of truth** for every value the ES-2
pre-registration freeze fixed **before** any replay result was seen
(forking-paths guard, mirroring :mod:`erre_sandbox.evidence.spdm.constants`). A
value can only change by a deliberate edit here, which itself requires a
**superseding ADR**. No value is read off a result and then tuned.

The table is the ``design-final.md`` §11 freeze verbatim (``.steering/
20260628-m13-es2-replay/``, /reimagine hybrid + Codex ADOPT-WITH-CHANGES, all 6
HIGH reflected before freeze). Several thresholds are **inherited** from the
ES-1 / III-a freeze rather than newly invented: ``CI_ALPHA`` / ``N_RESAMPLES`` /
``NULL_NOISE_FACTOR`` / ``DENOVO_DIVERGENCE_FLOOR`` / ``NO_SPURIOUS_TOL`` track
the established Jaccard-divergence house style so a freshly chosen threshold does
not re-introduce arbitrariness. The freeze is pinned verbatim in
``tests/test_evidence/test_es2_constants.py``.

Claim boundary (``design-final.md`` §0): a GO verdict means "eligible to proceed
to ES-3 (walk → sampling modulation) — the recombination substrate generates
path-dependent novel seeds above a matched null", **not** the full-hypothesis
(LLM-level de-novo cognitive divergence). NO_GO is a *progressive* finding
(recombination alone is insufficient → ES-3 / richer primitive), never a
refutation. INCONCLUSIVE (low power / invalid apparatus) is kept distinct.
"""

from __future__ import annotations

from typing import Final

# --- movement (④ preferential-return Pólya-urn, §2) ---------------------------

POLYA_ALPHA: Final[float] = 1.0
"""Pólya-urn prior weight in ``weight(z) = POLYA_ALPHA + visit_count(z)`` (Song
2010 preferential return). The single canonical parameter = minimal rigging
surface; early stochastic reinforcement diverges A/B into distinct home-ranges
with re-visits (the spatial-temporal crossing that drives replay novelty)."""

M_FRAGMENTS: Final[int] = 48
"""Trajectory length = experience-fragment count per individual (Codex LOW range
40-64); thick enough that a 5-zone preferential-return walk is not degenerate."""

# --- recombination kernel (③ stochastic replay walk, §4) ----------------------

L_SEED: Final[int] = 4
"""Distinct fragments per replay seed (Codex LOW: 4 primary; 6+ drives Jaccard
sparsity). ``unique_fragment_count == L_SEED`` is a per-seed validity invariant
(Codex H2: self-loop / adjacent duplicate forbidden)."""

N_REPLAY: Final[int] = 4096
"""Replay seeds generated per individual per arm (Codex LOW 4096-8192). Large
enough that the within-agent split-half ``D_self`` self-null is stable."""

# --- statistics (① matched permutation null + bootstrap, §7) ------------------

N_SEED: Final[int] = 64
"""Scenario-seed count = the **outer independent unit** for the bootstrap CI
(Codex H5 / LOW: 64 preferred). The CI's effective sample size is the scenario
seed, never ``N_PERM`` (which only estimates a per-seed null quantile)."""

N_PERM: Final[int] = 5000
"""Content-stratified paired permutations per scenario seed (Codex LOW 5000
preferred). Used to estimate the per-seed null quantile ``null_q_s``, NOT as a
bootstrap sample size (pseudo-replication guard, Codex H5)."""

PERM_NULL_QUANTILE: Final[float] = 0.95
"""One-sided upper quantile of the per-seed permutation null ``D_perm_s``
distribution that ``delta_s = D_obs_s - null_q_s`` is measured against (integrates
with the 90 % one-sided ``CI_ALPHA``)."""

CI_ALPHA: Final[float] = 0.10
"""Two-sided alpha for the bootstrap CI of ``{delta_s}`` (90 % CI). GO requires
the CI **lower** bound > 0; a CI straddling 0 is INCONCLUSIVE (ES-1 integration)."""

N_RESAMPLES: Final[int] = 2000
"""Bootstrap resample count (= ``bootstrap_ci.DEFAULT_N_RESAMPLES``; ES-1
integration) so CI stability matches the established metric pipeline."""

# --- INCONCLUSIVE gate (§9, calibration-free) ---------------------------------

MIN_VALID_SEEDS: Final[int] = 32
"""Minimum valid scenario seeds (of ``N_SEED``) for a strong verdict; below it →
INCONCLUSIVE (Codex LOW: half of ``N_SEED``)."""

MIN_DENOVO_SEEDS: Final[int] = 256
"""Minimum de-novo-eligible replay seeds per individual; below it the per-arm
seed-structure set is under-sampled → INCONCLUSIVE (absolute sampling adequacy,
~6 % of ``N_REPLAY=4096``; calibration-free, no pilot threshold)."""

NULL_NOISE_FACTOR: Final[float] = 1.5
"""Relative noise gate (ES-1 integration): ``median(D_obs) <= NULL_NOISE_FACTOR *
max(median(D_self), DENOVO_DIVERGENCE_FLOOR)`` ⇒ the cross-agent divergence does
not effectively exceed within-agent split-half sampling noise → INCONCLUSIVE.
The floor protects a degenerate (near-0) ``D_self`` from skipping the gate."""

# --- verdict thresholds (§10, conjunctive) ------------------------------------

DENOVO_DIVERGENCE_FLOOR: Final[float] = 0.10
"""Always-on minimum practical effect: ``median(D_obs) >= this`` (ES-1 practical
floor integration); a thin A/B structure separation cannot GO."""

NOVELTY_FLOOR: Final[float] = 0.20
"""Lower bound on the median novel directed-transition seed rate (a *floor*, not a
target). The exact-de-novo rate is a non-degenerate **secondary** only (Codex H3);
the temporal-replay negative control must fall **below** this floor for the
apparatus to be valid."""

NO_SPURIOUS_TOL: Final[float] = 0.05
"""③ no-spurious control: under semantic-isomorphic relabeling (raw id changed,
pairwise semantic matrix preserved) the de-novo position-set divergence margin
must be ``<= this`` (ES-1 integration, Codex M2)."""

COMPETITION_MIN_VAR: Final[float] = 0.02
"""② validity gate: ``var(pairwise cosine) >= this`` over the synthetic content
embeddings; below it semantic competition is absent (ties degenerate) → the ②
factor is hollow → INCONCLUSIVE (Codex M3, LOW: cosine-variance lower bound)."""

# --- synthetic embedding (② semantic competition, §3) -------------------------

EMBED_DIM: Final[int] = 16
"""Synthetic content-embedding dimension (cosine variance headroom; freeze)."""

EMBED_SALT: Final[str] = "es2-replay-v1"
"""Deterministic salt for ``e_i = unit(hash(EMBED_SALT, i))`` (freeze). The hash
embedding is **synthetic semantic competition** (verdict-blind, not natural
meaning; Codex M3)."""

__all__ = [
    "CI_ALPHA",
    "COMPETITION_MIN_VAR",
    "DENOVO_DIVERGENCE_FLOOR",
    "EMBED_DIM",
    "EMBED_SALT",
    "L_SEED",
    "MIN_DENOVO_SEEDS",
    "MIN_VALID_SEEDS",
    "M_FRAGMENTS",
    "NOVELTY_FLOOR",
    "NO_SPURIOUS_TOL",
    "NULL_NOISE_FACTOR",
    "N_PERM",
    "N_REPLAY",
    "N_RESAMPLES",
    "N_SEED",
    "PERM_NULL_QUANTILE",
    "POLYA_ALPHA",
]
