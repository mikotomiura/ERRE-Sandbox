"""M10-A S3.5 / PR-S4b: reactivate-ADR §3.A path(a) gate evaluator (pure scorer).

Scores the **analysis layer** (②③④⑤) of the reactivate-ADR §3.A path(a)
individuation gate into one of five verdicts —
``GO`` / ``NO_GO`` / ``REJECT`` / ``INCONCLUSIVE`` / ``INVALID`` — by applying the
**frozen** decision rule (reactivate ADR §3.A + S3 conformance ADR §3/§4). Every
threshold (0.60 separation, K=1000, N=3 seeds) is a module-level :data:`Final` so the
scorer cannot silently drift from the ADR.

null-control supersede (PR-S4b): the live ④ is now the **H2 value-aware
owner-shuffle-resynth** evaluator (:func:`path_a_h2_gate.h2_owner_shuffle_resynth_3way`,
``NULL_CONTROL_KIND = "h2_owner_shuffle_resynth"`` / ``conformant``). It replaces the
legacy ④ :func:`swm_key_shuffle_projection_3way` (retained below as BLK-1 executable
evidence, **no longer wired** into :func:`score_path_a_gate`). The H2 evaluator lives
in a sibling leaf module that imports nothing from this one, so the scorer depends on
it one-directionally (no import cycle, PR-S4b plan-review HIGH).

Like :mod:`c3b_verdict`, the scorer is a **pure function over already-loaded
dataclasses** (per-individual belief / SWM substrate + the ``belief_variance`` /
``world_model_overlap_jaccard`` :class:`MetricResult` rows), never a DuckDB
reader, so the precedence machine and the null-control are exercised by synthetic
fixtures with no GPU / model / DB — the "GO 基準後出し封じ" lesson made executable.
This module lives **outside** the frozen judgment path
(``c3b_verdict`` / ``centroid_panel`` / ``layer1`` / ``c3b_pipeline``): it imports
none of them, so the frozen §9 sentinel stays ``exit=0``.

The scorer does **not** authorize the GPU smoke (S4) or the real §3.A verdict
(S5); it is the CPU-verifiable evaluator whose completion is the precondition for
S4 (S3 conformance ADR §6 / C-4). The §3 thresholds are frozen here and must not
be moved after a real run (PR-21 lesson, continuity-bias guard).

null-control supersede (PR-S4b / DA-S4B-5): the live ④ null-control is the H2
value-aware owner-shuffle-resynth (``NULL_CONTROL_KIND = "h2_owner_shuffle_resynth"``,
``NULL_CONTROL_CONFORMANCE = "conformant"``), stamped into the sidecar so the claim
boundary lives on the artifact. The stage-A spike proved this null reaches PASS on
separated substrate, so the gate is no longer structurally GO-incapable.

Decision order, per seed (most-severe wins): INVALID > NO_GO > REJECT >
INCONCLUSIVE > GO (DA-S3.5-2 / user MF-4). The experiment verdict (⑤) is the
most-severe across the N=3 seeds (GO only when every seed is GO = seed AND).

.. note::

   **Legacy ④ retained as BLK-1 evidence (DA-S4B-5).**
   :func:`swm_key_shuffle_projection_3way`
   (count-preserving relabel of the *synthesised* SWM key multiset) provably can
   **never** reach its PASS threshold (``central >= 0.90`` — an *identical* SWM gives
   ``central ≈ 0.46–0.67``, because a permutation preserves a multiset's spread and so
   carries no homogenisation). It is retained below — **no longer called by
   :func:`score_path_a_gate`** — as executable evidence of the structural finding
   (``s3.5-null-control-finding-adr.md``), with :data:`_LEGACY_NULL_CONTROL_KIND` /
   :data:`_LEGACY_NULL_CONTROL_CONFORMANCE` carrying its old marker. The supersede that
   replaced it is the H2 evaluator (stage-A H2 conformance ADR + S3.5a H1-(a)
   record-level re-synthesis null), and the ①②③ + matrix/identity/precedence
   scaffolding is reused unchanged.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.evidence.golden_baseline import derive_seed
from erre_sandbox.evidence.individuation.path_a_h2_gate import (
    H2_NULL_CONTROL_CONFORMANCE,
    H2_NULL_CONTROL_KIND,
    H2NullControlResult,
    H2Verdict,
    h2_owner_shuffle_resynth_3way,
)
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    AggregationLevel,
    MetricStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.contracts.cognition_layers import PromotedEvidenceUnit
    from erre_sandbox.evidence.individuation.models import MetricResult

# --- frozen ADR constants (one source, reactivate §3.A / S3 ADR §3) ----------
JACCARD_SEPARATION_MAX: Final[float] = 0.60
"""③: median pairwise SWM key-Jaccard ``<= 0.60`` for separation (reactivate §3.A③)."""
NULL_CONTROL_PASS_CENTRAL: Final[float] = 0.90
"""④ PASS: central tendency (median of K medians) ``>= 0.90`` (reactivate §3.A④)."""
NULL_CONTROL_INVALID_P95: Final[float] = 0.60
"""④ INVALID: 95th-percentile of the K medians ``<= 0.60`` (reactivate §3.A④)."""
NULL_SHUFFLE_K: Final[int] = 1000
"""④: number of label-shuffle permutations (reactivate §3.A④, frozen)."""
NULL_SHUFFLE_SALT: Final[str] = "c3b-reactivate-null-shuffle"
"""④: ``derive_seed`` salt for the shuffle RNG (reactivate §3.A④, frozen)."""
NULL_CONTROL_KIND: Final[str] = H2_NULL_CONTROL_KIND
"""④ live null-control kind stamped into the sidecar (PR-S4b): the H2 value-aware
owner-shuffle-resynth (``"h2_owner_shuffle_resynth"``), superseding the legacy
``swm_key_shuffle_projection`` (now :data:`_LEGACY_NULL_CONTROL_KIND`)."""
NULL_CONTROL_CONFORMANCE: Final[str] = H2_NULL_CONTROL_CONFORMANCE
"""④ conformance marker (PR-S4b): ``"conformant"`` — the stage-A spike proved the H2
null reaches PASS on separated substrate, so the gate is no longer structurally
GO-incapable (supersedes ``non_conformant_pending_supersede``)."""
_LEGACY_NULL_CONTROL_KIND: Final[str] = "swm_key_shuffle_projection"
"""Legacy ④ kind for the retained BLK-1 evidence function (DA-S4B-5, no longer live)."""
_LEGACY_NULL_CONTROL_CONFORMANCE: Final[str] = "non_conformant_pending_supersede"
"""Legacy ④ conformance marker (BLK-1): the measured-space relabel could not reach
``central >= 0.90``. Retained for the history function's pins only (not stamped)."""
REQUIRED_SEED_IDS: Final[tuple[int, ...]] = (0, 1, 2)
"""⑤: the only legal seed values (run_idx 0,1,2). path(a) is an N=3 envelope
distinct from the frozen §9 N=2 (c3b only) — §9 is not rewritten (DA-S3.5-3)."""
REQUIRED_INDIVIDUAL_COUNT: Final[int] = 3
"""Each seed must carry exactly 3 same-base individuals (reactivate §3.A, MF-3)."""

_BELIEF_VARIANCE_METRIC: Final[str] = "belief_variance"
_JACCARD_METRIC: Final[str] = "world_model_overlap_jaccard"
_EXPECTED_DYAD_PAIRS: Final[int] = 3  # C(3, 2) for 3 individuals
_P95: Final[float] = 0.95


class PathAVerdict(StrEnum):
    """Five-state path(a) verdict (reactivate §3.A; ADR "NO-GO" = ``no_go``)."""

    GO = "go"
    NO_GO = "no_go"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


# Precedence rank: higher = more severe (INVALID > NO_GO > REJECT > INCONCLUSIVE >
# GO, DA-S3.5-2). ``GO`` doubles as the per-criterion "this criterion passed"
# sentinel (rank 0), so a seed is GO only when every criterion is GO.
_RANK: Final[dict[PathAVerdict, int]] = {
    PathAVerdict.GO: 0,
    PathAVerdict.INCONCLUSIVE: 1,
    PathAVerdict.REJECT: 2,
    PathAVerdict.NO_GO: 3,
    PathAVerdict.INVALID: 4,
}


def _most_severe(verdicts: Sequence[PathAVerdict]) -> PathAVerdict:
    """Return the highest-precedence verdict (DA-S3.5-2 ordering)."""
    return max(verdicts, key=lambda v: _RANK[v])


# H2 (④) 3-way → 5-state mapping (PR-S4b decoupling): the H2 leaf returns its own
# H2Verdict so it never imports PathAVerdict; the scorer maps it into the gate's
# precedence (PASS→GO / INVALID→INVALID / INCONCLUSIVE→INCONCLUSIVE).
_H2_TO_PATH_A: Final[dict[H2Verdict, PathAVerdict]] = {
    H2Verdict.PASS: PathAVerdict.GO,
    H2Verdict.INVALID: PathAVerdict.INVALID,
    H2Verdict.INCONCLUSIVE: PathAVerdict.INCONCLUSIVE,
}


# --- inputs (CX-MED-2: explicit per-seed identity contract) ------------------


@dataclass(frozen=True, slots=True)
class IndividualSubstrate:
    """One individual's final-tick belief / SWM substrate (from the trace).

    ``belief_classes`` is the promoted-belief class set (``None`` = no substrate),
    ``world_model_keys`` the synthesised SWM ``(axis, key)`` set (``None`` = SWM not
    captured), ``world_model_evidence`` the per-dyad raw promoted units (``None`` = no
    SWM synthesised / pre-段B trace). ``belief_classes`` feeds ② (belief-class
    distribution); ``world_model_evidence`` feeds the live H2 ④
    (owner-shuffle-resynth); ``world_model_keys`` feeds the legacy ④ history function
    (PR-S4b: no longer the live ④).
    """

    individual_id: str
    belief_classes: tuple[str, ...] | None
    world_model_keys: tuple[tuple[str, str], ...] | None
    world_model_evidence: tuple[PromotedEvidenceUnit, ...] | None = None


@dataclass(frozen=True, slots=True)
class PathARunInput:
    """One seed's scorable input (CX-MED-2 identity contract).

    ``run_idx`` (the §3.A seed, 0/1/2) and ``base_persona_id`` are not on the
    trace window / MetricResult, so they are carried explicitly. The scorer's
    identity gate checks that ``individuals`` (exactly 3), ``belief_variance_rows``
    and ``jaccard_rows`` all correspond to the same ``run_id`` / ``base_persona_id``
    / individual-id set (a mismatch is a protocol violation → INVALID).
    """

    run_idx: int
    run_id: str
    base_persona_id: str
    individuals: tuple[IndividualSubstrate, ...]
    belief_variance_rows: tuple[MetricResult, ...]
    jaccard_rows: tuple[MetricResult, ...]


@dataclass(frozen=True, slots=True)
class PathAExperiment:
    """All N=3 seeds of one same-base path(a) gate run, scored together."""

    run_id: str
    runs: tuple[PathARunInput, ...]
    required_seed_ids: tuple[int, ...] = REQUIRED_SEED_IDS


# --- outputs -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CriterionResult:
    """One criterion's (①②③) outcome for one seed (``GO`` = passed)."""

    outcome: PathAVerdict
    reason: str


@dataclass(frozen=True, slots=True)
class NullControlResult:
    """④ swm_key_shuffle_projection 3-way outcome for one seed.

    ``outcome`` is ``GO`` (PASS), ``INVALID`` (p95 ≤ 0.60) or ``INCONCLUSIVE``
    (middle band / skipped). ``swm_raw_key_count`` vs ``swm_unique_key_count``
    surfaces the pooled multiplicity (CX-LOW-2: a production writer dedups+sorts SWM
    keys, so these are equal in a real run — the diff is a defence/transparency
    measure for malformed input).
    """

    outcome: PathAVerdict
    reason: str
    central: float | None = None
    p95: float | None = None
    k: int = NULL_SHUFFLE_K
    swm_raw_key_count: int | None = None
    swm_unique_key_count: int | None = None


@dataclass(frozen=True, slots=True)
class SeedScore:
    """Per-seed scoring (or the invalid reason that stopped it)."""

    run_idx: int
    verdict: PathAVerdict
    reason: str
    invalid_reason: str | None = None
    belief_variance: CriterionResult | None = None
    belief_distribution: CriterionResult | None = None
    jaccard_separation: CriterionResult | None = None
    null_control: H2NullControlResult | None = None
    jaccard_median: float | None = None
    jaccard_valid_count: int | None = None
    belief_distribution_summary: tuple[
        tuple[str, tuple[tuple[str, int], ...]], ...
    ] = ()


@dataclass(frozen=True, slots=True)
class PathAScoreReport:
    """The scorer's five-state verdict + per-seed evidence.

    CX-MED-3: this is the scorer dataclass, not the sidecar Pydantic model
    (:class:`path_a_report.PathAVerdictReport`).
    """

    run_id: str
    verdict: PathAVerdict
    reason: str
    null_control_kind: str = NULL_CONTROL_KIND
    null_control_conformance: str = NULL_CONTROL_CONFORMANCE
    seeds: tuple[SeedScore, ...] = field(default_factory=tuple)


# --- scorer ------------------------------------------------------------------


def score_path_a_gate(experiment: PathAExperiment) -> PathAScoreReport:
    """Score one path(a) gate run to a five-state verdict (DA-S3.5-2 precedence).

    The seed matrix is validated **before** any scoring (MF-3): a matrix whose
    seed set is not exactly ``required_seed_ids`` (illegal / duplicate / missing /
    extra run_idx) is ``INVALID`` and never reaches per-seed scoring.
    """
    matrix_violation = _validate_matrix(experiment)
    if matrix_violation is not None:
        return PathAScoreReport(
            run_id=experiment.run_id,
            verdict=PathAVerdict.INVALID,
            reason=f"seed matrix protocol violation — {matrix_violation}",
            seeds=(),
        )

    seed_scores = tuple(
        _score_seed(run) for run in sorted(experiment.runs, key=lambda r: r.run_idx)
    )
    verdict = _most_severe([s.verdict for s in seed_scores])
    reason = _experiment_reason(verdict, seed_scores, experiment)
    return PathAScoreReport(
        run_id=experiment.run_id,
        verdict=verdict,
        reason=reason,
        seeds=seed_scores,
    )


def _validate_matrix(experiment: PathAExperiment) -> str | None:
    """Exact N=3 seed matrix check (MF-3): seed set must equal required_seed_ids."""
    run_idxs = [r.run_idx for r in experiment.runs]
    duplicates = sorted({i for i in run_idxs if run_idxs.count(i) > 1})
    if duplicates:
        return f"duplicate run_idx {duplicates}"
    expected = set(experiment.required_seed_ids)
    got = set(run_idxs)
    if got != expected:
        return (
            f"seed set {sorted(got)} != required {sorted(expected)}"
            " (illegal / missing / extra run_idx)"
        )
    return None


def _score_seed(run: PathARunInput) -> SeedScore:
    """Score one seed: identity gate → ①②③④ → most-severe per-seed verdict."""
    identity_violation = _run_identity_violation(run)
    if identity_violation is not None:
        return SeedScore(
            run_idx=run.run_idx,
            verdict=PathAVerdict.INVALID,
            reason=identity_violation,
            invalid_reason=identity_violation,
        )

    sorted_inds = sorted(run.individuals, key=lambda i: i.individual_id)
    one = _score_belief_variance(run, sorted_inds)
    three, jacc_median, jacc_valid = _score_jaccard(run)
    one_passed = one.outcome is PathAVerdict.GO
    # CX-MED-1: ② and ④ are only evaluated once ① has established the belief
    # substrate; on NO_GO they are skipped (INCONCLUSIVE) so a ④ INVALID can never
    # override NO_GO and mislabel a substrate-absent seed as a metric artifact.
    if one_passed:
        two = _score_belief_distribution(sorted_inds)
        members = [(ind.individual_id, ind.world_model_evidence) for ind in sorted_inds]
        four = h2_owner_shuffle_resynth_3way(
            members, base_persona_id=run.base_persona_id, run_idx=run.run_idx
        )
    else:
        skip = "skipped: belief substrate not established (① NO_GO)"
        two = CriterionResult(PathAVerdict.INCONCLUSIVE, skip)
        four = H2NullControlResult(H2Verdict.INCONCLUSIVE, skip)

    four_outcome = _H2_TO_PATH_A[four.outcome]
    verdict = _most_severe([one.outcome, two.outcome, three.outcome, four_outcome])
    return SeedScore(
        run_idx=run.run_idx,
        verdict=verdict,
        reason=_seed_reason(verdict, one, two, three, four_outcome, four.reason),
        belief_variance=one,
        belief_distribution=two,
        jaccard_separation=three,
        null_control=four,
        jaccard_median=jacc_median,
        jaccard_valid_count=jacc_valid,
        belief_distribution_summary=_belief_summary(sorted_inds),
    )


def _run_identity_violation(run: PathARunInput) -> str | None:
    """Identity gate (CX-MED-2): 3 same-base individuals, consistent rows.

    Returns a violation reason (→ INVALID) or ``None`` when the seed is well-formed:
    exactly 3 distinct individuals; ``belief_variance_rows`` cover exactly that
    id set (per_individual); ``jaccard_rows`` are the 3 dyad pairs of those
    individuals (per_dyad); every row shares ``run.run_id``.
    """
    ids = [i.individual_id for i in run.individuals]
    if len(ids) != REQUIRED_INDIVIDUAL_COUNT:
        return (
            f"seed has {len(ids)} individuals; need exactly {REQUIRED_INDIVIDUAL_COUNT}"
        )
    id_set = set(ids)
    if len(id_set) != REQUIRED_INDIVIDUAL_COUNT:
        return f"duplicate individual_id in {sorted(ids)}"

    bv = [
        r
        for r in run.belief_variance_rows
        if r.metric_name == _BELIEF_VARIANCE_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    ]
    bv_ids = {r.individual_id for r in bv}
    if bv_ids != id_set:
        return (
            f"belief_variance rows cover {sorted(bv_ids)}"
            f" != individuals {sorted(id_set)}"
        )
    expected_dyads = {
        f"{a}{DYAD_SEP}{b}" for a, b in itertools.combinations(sorted(ids), 2)
    }
    jc = [
        r
        for r in run.jaccard_rows
        if r.metric_name == _JACCARD_METRIC
        and r.aggregation_level is AggregationLevel.PER_DYAD
    ]
    jc_ids = {r.individual_id for r in jc}
    if jc_ids != expected_dyads:
        return (
            f"jaccard dyad rows {sorted(jc_ids)} != expected {sorted(expected_dyads)}"
        )
    bad_run = next(
        (r.run_id for r in (*bv, *jc) if r.run_id != run.run_id),
        None,
    )
    if bad_run is not None:
        return f"row run_id {bad_run!r} != seed run_id {run.run_id!r}"
    return None


def _score_belief_variance(
    run: PathARunInput, sorted_inds: Sequence[IndividualSubstrate]
) -> CriterionResult:
    """① belief_variance: every individual VALID (≥2 belief class), else NO_GO."""
    by_id = {
        r.individual_id: r
        for r in run.belief_variance_rows
        if r.metric_name == _BELIEF_VARIANCE_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
    }
    degenerate = [
        ind.individual_id
        for ind in sorted_inds
        if by_id.get(ind.individual_id) is None
        or by_id[ind.individual_id].status is not MetricStatus.VALID
    ]
    if degenerate:
        return CriterionResult(
            PathAVerdict.NO_GO,
            f"belief substrate not established for {degenerate}"
            " (degenerate / single-class / no row = E1 not met)",
        )
    return CriterionResult(PathAVerdict.GO, "all individuals belief_variance valid")


def _score_belief_distribution(
    sorted_inds: Sequence[IndividualSubstrate],
) -> CriterionResult:
    """② cross-individual differentiation: not all 3 distributions identical.

    Compared on the full belief-class count distribution (``Counter`` → sorted
    ``(class, count)`` tuple). Only reached when ① passed, so every individual has
    a present ≥2-class belief set.
    """
    distributions = [_distribution(ind.belief_classes) for ind in sorted_inds]
    if len(set(distributions)) == 1:
        return CriterionResult(
            PathAVerdict.REJECT,
            "all individuals share an identical belief-class distribution"
            " (no cross-individual differentiation)",
        )
    return CriterionResult(
        PathAVerdict.GO,
        ">= 1 individual has a distinct belief-class distribution",
    )


def _score_jaccard(
    run: PathARunInput,
) -> tuple[CriterionResult, float | None, int]:
    """③ median pairwise SWM key-Jaccard <= 0.60 (real metric VALID rows).

    Requires all 3 dyad pairs VALID; fewer (DEGENERATE empty-union / UNSUPPORTED /
    missing) is a sample shortfall → INCONCLUSIVE, never a falsification (DA-S3.5-4).
    """
    valid = [
        r.value
        for r in run.jaccard_rows
        if r.metric_name == _JACCARD_METRIC
        and r.aggregation_level is AggregationLevel.PER_DYAD
        and r.status is MetricStatus.VALID
        and r.value is not None
    ]
    if len(valid) < _EXPECTED_DYAD_PAIRS:
        return (
            CriterionResult(
                PathAVerdict.INCONCLUSIVE,
                f"only {len(valid)}/{_EXPECTED_DYAD_PAIRS} dyad jaccard rows valid"
                " (degenerate / unsupported / missing = sample shortfall)",
            ),
            None,
            len(valid),
        )
    med = float(median(valid))
    if med > JACCARD_SEPARATION_MAX:
        return (
            CriterionResult(
                PathAVerdict.REJECT,
                f"median pairwise jaccard {med:.4f} > {JACCARD_SEPARATION_MAX}"
                " (separation not achieved)",
            ),
            med,
            len(valid),
        )
    return (
        CriterionResult(
            PathAVerdict.GO,
            f"median pairwise jaccard {med:.4f} <= {JACCARD_SEPARATION_MAX}",
        ),
        med,
        len(valid),
    )


def swm_key_shuffle_projection_3way(
    sorted_inds: Sequence[IndividualSubstrate],
    *,
    base_persona_id: str,
    run_idx: int,
) -> NullControlResult:
    """Legacy ④: SWM ``(axis,key)`` label-shuffle projection (BLK-1 history).

    .. deprecated:: PR-S4b
       **No longer the live ④** (:func:`score_path_a_gate` calls
       :func:`path_a_h2_gate.h2_owner_shuffle_resynth_3way`). Retained as executable
       evidence of the BLK-1 structural finding (this null can never reach
       ``central >= 0.90``); :data:`_LEGACY_NULL_CONTROL_KIND` carries its old marker.

    Procedure (DA-S3.5-5, reproducible):

    1. individuals are already ``individual_id``-sorted (stable) by the caller;
    2. flatten the per-individual SWM key sets into one raw multiset
       (``len = Σ raw_count_i``);
    3. seed ``numpy.random.PCG64`` from
       ``derive_seed(base_persona_id, run_idx, salt=NULL_SHUFFLE_SALT)`` and permute
       the pool index;
    4. split back preserving each individual's original key count;
    5. canonical-set-ise each chunk (``frozenset``, matching
       :mod:`world_model_metrics`) and take the median of the pairwise Jaccards;
    6. over K=1000 permutations, ``central = median(K medians)`` and
       ``p95 = numpy.quantile(K medians, 0.95, method="linear")`` (CX-LOW-1).

    Mutually-exclusive 3-way (reactivate §3.A④): central ≥ 0.90 → PASS (``GO``) /
    p95 ≤ 0.60 → INVALID (artifact) / otherwise INCONCLUSIVE (middle band). Returns
    INCONCLUSIVE when the SWM substrate is insufficient (a member with no captured
    SWM, or an empty pool) — consistent with ③'s shortfall (DA-S3.5-4).

    This is the **measured-space projection** named by
    :data:`_LEGACY_NULL_CONTROL_KIND`, not the ADR-literal promoted-belief record
    shuffle (MF-1 / module docstring); the live record-level re-synthesis null is now
    :mod:`path_a_h2_gate` (PR-S4b).
    """
    if any(ind.world_model_keys is None for ind in sorted_inds):
        return NullControlResult(
            PathAVerdict.INCONCLUSIVE,
            "insufficient SWM substrate (a member has no captured SWM key set)",
        )
    key_lists = [list(ind.world_model_keys or ()) for ind in sorted_inds]
    counts = [len(kl) for kl in key_lists]
    pool: list[tuple[str, str]] = [k for kl in key_lists for k in kl]
    raw_count = len(pool)
    unique_count = len(frozenset(pool))
    if raw_count == 0:
        return NullControlResult(
            PathAVerdict.INCONCLUSIVE,
            "empty SWM substrate (no keys to shuffle)",
            swm_raw_key_count=0,
            swm_unique_key_count=0,
        )

    seed = derive_seed(base_persona_id, run_idx, salt=NULL_SHUFFLE_SALT)
    rng = np.random.Generator(np.random.PCG64(seed))
    index = np.arange(raw_count)
    medians: list[float] = []
    for _ in range(NULL_SHUFFLE_K):
        rng.shuffle(index)
        sets: list[frozenset[tuple[str, str]]] = []
        offset = 0
        for count in counts:
            chunk = index[offset : offset + count]
            offset += count
            sets.append(frozenset(pool[j] for j in chunk))
        medians.append(_median_pairwise_jaccard(sets))

    central = float(median(medians))
    p95 = float(np.quantile(np.asarray(medians), _P95, method="linear"))

    def _result(outcome: PathAVerdict, reason: str) -> NullControlResult:
        return NullControlResult(
            outcome,
            reason,
            central=central,
            p95=p95,
            swm_raw_key_count=raw_count,
            swm_unique_key_count=unique_count,
        )

    if central >= NULL_CONTROL_PASS_CENTRAL:
        return _result(
            PathAVerdict.GO,
            f"null-control PASS: central {central:.4f} >= {NULL_CONTROL_PASS_CENTRAL}"
            " (shuffling labels collapses the separation = real effect)",
        )
    if p95 <= NULL_CONTROL_INVALID_P95:
        return _result(
            PathAVerdict.INVALID,
            f"null-control INVALID: p95 {p95:.4f} <= {NULL_CONTROL_INVALID_P95}"
            " (separation survives shuffling = metric / fixture artifact)",
        )
    return _result(
        PathAVerdict.INCONCLUSIVE,
        f"null-control inconclusive (middle band): central {central:.4f} <"
        f" {NULL_CONTROL_PASS_CENTRAL}, p95 {p95:.4f} > {NULL_CONTROL_INVALID_P95}",
    )


def _median_pairwise_jaccard(
    sets: Sequence[frozenset[tuple[str, str]]],
) -> float:
    """Median Jaccard over the dyad pairs with a non-empty union (set-ise semantics).

    A pair whose union is empty (both members empty) is undefined and skipped; with
    a non-empty pool at least one member is non-empty, so >= 2 of the 3 pairs are
    defined and the median is always well-formed.
    """
    jaccards: list[float] = []
    for a, b in itertools.combinations(range(len(sets)), 2):
        union = sets[a] | sets[b]
        if union:
            jaccards.append(len(sets[a] & sets[b]) / len(union))
    return float(median(jaccards))


def _distribution(
    belief_classes: tuple[str, ...] | None,
) -> tuple[tuple[str, int], ...]:
    """Belief-class count distribution as a sorted ``(class, count)`` tuple."""
    if not belief_classes:
        return ()
    return tuple(sorted(Counter(belief_classes).items()))


def _belief_summary(
    sorted_inds: Sequence[IndividualSubstrate],
) -> tuple[tuple[str, tuple[tuple[str, int], ...]], ...]:
    """Per-individual belief-class distribution summary for the sidecar evidence."""
    return tuple(
        (ind.individual_id, _distribution(ind.belief_classes)) for ind in sorted_inds
    )


def _seed_reason(
    verdict: PathAVerdict,
    one: CriterionResult,
    two: CriterionResult,
    three: CriterionResult,
    four_outcome: PathAVerdict,
    four_reason: str,
) -> str:
    """The reason of the criterion that drove the most-severe per-seed verdict.

    ④ is the H2 null-control, whose outcome is already mapped to PathAVerdict by the
    caller (``four_outcome``); ``four_reason`` is the H2 result's reason.
    """
    if verdict is PathAVerdict.GO:
        return "all criteria (①②③④) pass"
    for label, outcome, reason in (
        ("①belief_variance", one.outcome, one.reason),
        ("②belief_distribution", two.outcome, two.reason),
        ("③jaccard", three.outcome, three.reason),
        ("④h2_null_control", four_outcome, four_reason),
    ):
        if outcome is verdict:
            return f"{label}: {reason}"
    return verdict.value


def _experiment_reason(
    verdict: PathAVerdict,
    seeds: Sequence[SeedScore],
    experiment: PathAExperiment,
) -> str:
    """The experiment-level reason (seed AND with §3.A precedence)."""
    if verdict is PathAVerdict.GO:
        return (
            f"all criteria pass in {len(seeds)}/{len(experiment.required_seed_ids)}"
            " seeds (seed AND)"
        )
    driving = [f"seed {s.run_idx}: {s.reason}" for s in seeds if s.verdict is verdict]
    return f"most-severe across seeds = {verdict.value} — " + "; ".join(driving)


__all__ = [
    "JACCARD_SEPARATION_MAX",
    "NULL_CONTROL_CONFORMANCE",
    "NULL_CONTROL_INVALID_P95",
    "NULL_CONTROL_KIND",
    "NULL_CONTROL_PASS_CENTRAL",
    "NULL_SHUFFLE_K",
    "NULL_SHUFFLE_SALT",
    "REQUIRED_INDIVIDUAL_COUNT",
    "REQUIRED_SEED_IDS",
    "CriterionResult",
    "IndividualSubstrate",
    "NullControlResult",
    "PathAExperiment",
    "PathARunInput",
    "PathAScoreReport",
    "PathAVerdict",
    "SeedScore",
    "score_path_a_gate",
    "swm_key_shuffle_projection_3way",
]
