"""Frozen §5 constants for the M13-ES4 actuator-sufficiency verdict.

The **single source of truth** for every value the ES-4 pre-registration freeze
fixed **before** any result (forking-paths guard, mirroring
:mod:`erre_sandbox.evidence.es3_locomotion.constants`). A value changes only by a
deliberate edit here, which itself requires a **superseding ADR**. No value is
read off a result and then tuned (``design-final.md`` §5 "forking-paths seal").

The table is the frozen ``design-final.md`` §5 numeric pre-registration
(``.steering/20260630-m13-es4-adr/``, user-ratified). Several values are
**inherited**: ``PERSONA_ROSTER`` / ``LOCO_GAIN_T`` / ``TEMP_MIN`` / ``TEMP_MAX``
from ES-3 and ``inference/sampling.py``; ``CI_ALPHA`` / ``N_RESAMPLES`` from
ES-2/ES-3. The freeze is pinned verbatim in
``tests/test_evidence/test_es4_constants.py``.

Claim boundary (``design-final.md`` §0 / §9): a GO means *actuator sufficiency*
(``qwen3:8b`` local, frozen decoding: locomotion → temperature moves output into a
divergent-favouring regime), **not** "walking → creative divergence" and **not** a
re-proof of the closed-loop core thesis.
"""

from __future__ import annotations

from typing import Final

from erre_sandbox.schemas import SamplingBase

# --- persona roster (§5 P row, blind: real YAML default_sampling) -------------

PERSONA_ROSTER: Final[tuple[tuple[str, SamplingBase], ...]] = (
    ("kant", SamplingBase(temperature=0.60, top_p=0.85, repeat_penalty=1.12)),
    ("nietzsche", SamplingBase(temperature=0.85, top_p=0.80, repeat_penalty=0.95)),
    ("rikyu", SamplingBase(temperature=0.45, top_p=0.78, repeat_penalty=1.25)),
)
"""Frozen persona roster (inherited from ES-3, blind = not chosen for this test).
``persona_id`` pinned, ``SamplingBase`` mirrored from the real ``personas/*.yaml``
``default_sampling``. The base-temperature spread (0.45 / 0.60 / 0.85) makes the
per-cell temperature reach vary. Pinned to the YAML in the constants test."""

N_PERSONA: Final[int] = 3
"""Roster size (= ``len(PERSONA_ROSTER)``)."""

# --- actuator gains (§1 / §5) -------------------------------------------------

LOCO_GAIN_T: Final[float] = 0.3
"""Temperature gain: λ=1 → +0.3 temp. Inherited ES-3 actuator value."""

LOCO_GAIN_P: Final[float] = 0.0
"""top_p gain. **0** = ES-4 is a temperature-only actuator (Codex HIGH-1): ES-3
forensic showed top_p 0/15 headroom-valid cells = unmeasurable, so ``gain_p=0``
makes "locomotion = the only temperature channel" clean at the code level. M
(temp-match) then matches the *entire* ResolvedSampling (top_p stays base+mode)."""

TEMP_MIN: Final[float] = 0.01
"""Temperature clamp floor (inherited ``inference/sampling.py``)."""

TEMP_MAX: Final[float] = 2.0
"""Temperature clamp ceiling (inherited ``inference/sampling.py``)."""

# --- condition axis: λ bands A0/A1/A2 + F (§1 / §5) ---------------------------

LAMBDA_A0: Final[float] = 0.0
"""A0 (null / ablation): λ=0 → loco temp +0. Bit-identical to ``loco_delta=None``."""

LAMBDA_BAND_A1: Final[tuple[float, float]] = (0.4, 0.6)
"""A1 band: λ∈[0.4,0.6] → loco temp ~+0.15 (mid-reach)."""

LAMBDA_BAND_A2: Final[tuple[float, float]] = (0.85, 1.0)
"""A2 band: λ∈[0.85,1.0] → loco temp ~+0.30 (full reach). dose-response primary."""

F_TEMP_DELTA: Final[float] = 0.8
"""F (forensic over-heat): base + 0.8, outside the actuator reach (+0.3). Probes
DQ turnover / garbage_rate as monotone-failure evidence (verdict non-driving)."""

# --- task battery sizes (§5 / §6) ---------------------------------------------

N_AUT: Final[int] = 16
"""AUT items = 8 classic + 8 novel-but-simple (memorisation stratification, Codex
L-2). Cluster count 3×16=48 gives the cluster-level power (HIGH-8)."""

N_AUT_CLASSIC: Final[int] = 8
N_AUT_NOVEL: Final[int] = 8

N_RAT: Final[int] = 16
"""RAT items (convergent supporting). Pool of 16; contamination exclusion thins it
(Codex M-2), so ``MIN_VALID_RAT`` valid is required."""

MIN_VALID_AUT: Final[int] = 12
"""Valid-AUT floor (of 16) for a valid battery; below → INVALID_TASK_BATTERY."""

MIN_VALID_RAT: Final[int] = 8
"""Valid-RAT floor for a valid battery; below → INVALID_TASK_BATTERY."""

# --- seeds (§5) ---------------------------------------------------------------

N_SEED_PHASE0: Final[int] = 10
"""Phase 0 pilot seeds per (persona, item, condition): feasibility binary gate
minimum."""

N_SEED_PHASE1: Final[int] = 20
"""Phase 1 seeds: common-seed paired across A0/A1/A2/M2, so cluster-mean precision
is stable (Codex HIGH-8; pairing reduces variance)."""

# --- scoring (§2.1 / §2.2 / §5) -----------------------------------------------

K_IDEAS: Final[int] = 5
"""first-K-valid cap: DQ is computed over the first K gate-passing ideas (Codex
HIGH-3, high-V inflation guard)."""

IDEA_MIN_TOK: Final[int] = 3
"""Degeneracy filter: minimum tokens for an idea (§2.1 (c) gate stage 1)."""

IDEA_MAX_TOK: Final[int] = 40
"""Degeneracy filter: maximum tokens for an idea."""

DISTINCT_TOKEN_RATIO_MIN: Final[float] = 0.4
"""Degeneracy filter: distinct-token / total-token ratio floor (loop guard)."""

NGRAM_LOOP_N: Final[int] = 3
"""Degeneracy filter: a repeated ``NGRAM_LOOP_N``-gram marks a degenerate loop."""

MIN_VALID_IDEAS_FOR_DQ: Final[int] = 2
"""V<2 → DQ=0 (worst value, not drop): blocks condition-dependent selection bias
(Codex HIGH-3)."""

NUM_PREDICT_AUT: Final[int] = 384
"""Generation token budget for AUT (multi-idea)."""

NUM_PREDICT_RAT: Final[int] = 32
"""Generation token budget for RAT (single word)."""

# --- rarity reference R_object construction (§2.2b, Codex 2nd HIGH-A) ----------

N_CURATED: Final[int] = 10
"""Curated common-use anchors per object (hand-frozen in ``common_uses.yaml``)."""

REF_SEEDS: Final[int] = 50
"""Held-out reference seeds per object (verdict-disjoint), for the high-frequency
augmentation. Index range must not overlap the verdict seeds."""

REF_FREQ_MIN: Final[float] = 0.20
"""Held-out augmentation: an idea appearing in ≥20% (≥10/50) of reference
generations is added to the anchor set."""

REF_DEDUP: Final[float] = 0.90
"""Near-duplicate merge threshold: ideas with cosine ≥ 0.90 are collapsed."""

N_R_MIN: Final[int] = 8
"""R_object sufficiency floor: ``|R_object| < 8`` → fallback to curated-only."""

N_R_MAX: Final[int] = 30
"""R_object size cap per object after merge."""

REF_TEMP: Final[float] = 0.7
"""Reference generation temperature (neutral, persona-independent)."""

# --- verdict thresholds (§5 / §8) ---------------------------------------------

MDE_CLUSTER_D: Final[float] = 0.40
"""Minimum detectable cluster-level paired effect size. 48 clusters paired give
power 0.80 / one-sided α 0.05 at d≈0.36; 0.40 is the honest achievable value
(Codex HIGH-8)."""

POWER: Final[float] = 0.80
"""Target power (standard)."""

ALPHA_ONE_SIDED: Final[float] = 0.05
"""One-sided α (divergent-favouring is a directional hypothesis)."""

PROJECTED_CLUSTER_MAX: Final[int] = 48
"""Power-feasibility ceiling: if the projected cluster count needed to detect
``MDE_CLUSTER_D`` at ``POWER`` / ``ALPHA_ONE_SIDED`` exceeds the frozen
``N_PERSONA × N_AUT = 48``, the design is INCONCLUSIVE_UNDERPOWERED (§4.1.4)."""

DQ_FLOOR_STD_CI_LOWER: Final[float] = 0.20
"""DQ_FLOOR part 1: cluster-paired ΔDQ_std CI_lower ≥ 0.20 (small-moderate
practical lower bound)."""

DQ_FLOOR_RAW: Final[float] = 0.02
"""DQ_FLOOR part 2: raw ΔDQ ≥ 0.02 cosine (ES-3 ``AMP_FLOOR`` scale)."""

AUC_FLOOR: Final[float] = 0.80
"""(a1) stratified discrimination AUC floor and adversarial judge-AUC floor."""

DELTA_EQUIV: Final[float] = 0.15
"""(b) TOST equivalence margin in SD units."""

GARBAGE_RATE_CEILING: Final[float] = 0.30
"""A2 garbage-rate ceiling: above it the A2 effect is garbage-driven → NO_GO."""

EMPTY_PARSE_FAIL_CEILING: Final[float] = 0.05
"""empty / parse-fail rate ceiling (think-suppression monitor)."""

CROSS_COND_DIVERGENCE_MAX: Final[float] = 0.30
"""cross-condition valid-rate / missing-rate divergence ceiling (selection-bias
hard gate, Codex HIGH-3)."""

# --- bootstrap (§5, inherited ES-2/ES-3) --------------------------------------

CI_ALPHA: Final[float] = 0.10
"""90% bootstrap CI (ES-2/ES-3 inherited)."""

N_RESAMPLES: Final[int] = 10000
"""Bootstrap resample count (standard)."""

ZERO_TOL: Final[float] = 1e-9
"""Numerical zero tolerance for the pre-flight sampling-hash equivalence asserts."""

# --- item-level validity gate (§3, frozen) ------------------------------------

AUT_MIN_IDEAS_BASE: Final[int] = 2
"""AUT item validity: ≥2 valid ideas required at base temperature."""

AUT_MIN_TRIAL_FRAC: Final[float] = 0.70
"""AUT item validity: the ≥2-idea criterion must hold in ≥70% of base trials."""

PARSE_SUCCESS_MIN: Final[float] = 0.90
"""AUT item validity: parse success rate floor."""

RAT_ACC_MIN: Final[float] = 0.10
"""RAT item validity: base accuracy lower bound (exclusive)."""

RAT_ACC_MAX: Final[float] = 0.90
"""RAT item validity / contamination: base accuracy upper bound; accuracy ≥ 0.90
items are excluded as contaminated (Codex M-2, no replacement)."""

# --- budget gates (§4.1, total-inclusive, Codex M-7) --------------------------

PHASE0_GPU_HOUR_CAP: Final[float] = 8.0
"""Phase 0 hard budget cap (GPU-hours, total-inclusive: gen+judge+atlas+embed+
overhead)."""

PHASE1_GPU_HOUR_CAP: Final[float] = 30.0
"""Phase 1 hard budget cap (GPU-hours, total-inclusive)."""

__all__ = [
    "ALPHA_ONE_SIDED",
    "AUC_FLOOR",
    "AUT_MIN_IDEAS_BASE",
    "AUT_MIN_TRIAL_FRAC",
    "CI_ALPHA",
    "CROSS_COND_DIVERGENCE_MAX",
    "DELTA_EQUIV",
    "DISTINCT_TOKEN_RATIO_MIN",
    "DQ_FLOOR_RAW",
    "DQ_FLOOR_STD_CI_LOWER",
    "EMPTY_PARSE_FAIL_CEILING",
    "F_TEMP_DELTA",
    "GARBAGE_RATE_CEILING",
    "IDEA_MAX_TOK",
    "IDEA_MIN_TOK",
    "K_IDEAS",
    "LAMBDA_A0",
    "LAMBDA_BAND_A1",
    "LAMBDA_BAND_A2",
    "LOCO_GAIN_P",
    "LOCO_GAIN_T",
    "MDE_CLUSTER_D",
    "MIN_VALID_AUT",
    "MIN_VALID_IDEAS_FOR_DQ",
    "MIN_VALID_RAT",
    "NGRAM_LOOP_N",
    "NUM_PREDICT_AUT",
    "NUM_PREDICT_RAT",
    "N_AUT",
    "N_AUT_CLASSIC",
    "N_AUT_NOVEL",
    "N_CURATED",
    "N_PERSONA",
    "N_RAT",
    "N_RESAMPLES",
    "N_R_MAX",
    "N_R_MIN",
    "N_SEED_PHASE0",
    "N_SEED_PHASE1",
    "PARSE_SUCCESS_MIN",
    "PERSONA_ROSTER",
    "PHASE0_GPU_HOUR_CAP",
    "PHASE1_GPU_HOUR_CAP",
    "POWER",
    "PROJECTED_CLUSTER_MAX",
    "RAT_ACC_MAX",
    "RAT_ACC_MIN",
    "REF_DEDUP",
    "REF_FREQ_MIN",
    "REF_SEEDS",
    "REF_TEMP",
    "TEMP_MAX",
    "TEMP_MIN",
    "ZERO_TOL",
]
