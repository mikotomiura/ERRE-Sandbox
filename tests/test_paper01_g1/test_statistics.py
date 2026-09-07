"""Tests for the §5 statistics layer in scripts/paper01_external_audit.py (I-004).

design-final.md §1 / §5 is the single source of truth for the procedures
under test. Every test here is **encoder-independent**: rarity/membership
scores and object labels are synthetic Python/numpy values pushed directly
through :func:`~scripts.paper01_external_audit.auc_stratified` and friends
-- no adapter, no encoder, no ``[eval]`` extras.

Per design-final.md §7 (Opus MEDIUM-11 "eliminate tautological ACs"):

* 004-1 hardcodes a hand-computed expected value and checks it against the
  implementation's output -- it never compares the implementation to
  itself.
* 004-2 uses synthetic data where pooled and stratified AUC are *provably*
  different values (not a case where they happen to coincide).
* 004-5 constructs input where a naive "marginal median of AUC_full / AUC_LAO
  taken separately" reading and the real per-draw-proportion reading
  disagree, and asserts the implementation takes the per-draw side.
* 004-8 asserts both same-seed reproducibility and different-seed
  divergence.
* 004-9 spies on the module-level ``permutation_p_stratified`` /
  ``bootstrap_stratified_drop`` names via ``monkeypatch.setattr`` to count
  calls, rather than trusting a self-report.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as mod

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator import controls

if TYPE_CHECKING:
    from collections.abc import Sequence

_FLOOR = _c.AUC_FLOOR  # 0.80, read once for readability in hand-picked fixtures


# --- 004-1 --------------------------------------------------------------


def test_auc_stratified_matches_hand_computation() -> None:
    """Hand-computed weighted-average AUC over 2 unequally-weighted objects.

    ``o1``: good=[0.9,0.8,0.7], common=[0.4] -> AUC_o1 = 1.0, w=3*1=3
    ``o2``: good=[0.3], common=[0.6,0.5] -> AUC_o2 = 0.0, w=1*2=2
    ``AUC_strat = (3*1.0 + 2*0.0) / (3 + 2) = 0.6``.

    The unequal weights (3 vs 2) are deliberate: a mutant that replaces
    ``w(o) = n_good(o) * n_common(o)`` with a uniform weight of 1 would
    still average to 0.5 here, not 0.6 -- so this fixture is sensitive to
    the weighting formula, not just to the per-object AUC values.
    """
    scores = [0.9, 0.8, 0.7, 0.4, 0.3, 0.6, 0.5]
    labels = [1, 1, 1, 0, 1, 0, 0]
    objects = ["o1", "o1", "o1", "o1", "o2", "o2", "o2"]

    assert mod.auc_stratified(scores, labels, objects) == pytest.approx(0.6)


# --- 004-2 --------------------------------------------------------------


def test_stratified_differs_from_pooled() -> None:
    """Pooled and within-object AUC are provably different values here.

    Object A and object B each separate their own good/common perfectly
    (AUC_A = AUC_B = 1.0 within-object -> stratified = 1.0), but object A's
    scores are uniformly higher than object B's, so pooling across objects
    interleaves B's good scores below A's common scores and drags the
    pooled AUC down to 0.75. A test that only checked "some difference" on
    an input where both statistics coincide would prove nothing; here they
    provably differ (1.0 vs 0.75).
    """
    scores = [0.9, 0.9, 0.3, 0.3, 0.5, 0.5, 0.1, 0.1]
    labels = [1, 1, 1, 1, 0, 0, 0, 0]
    objects = ["A", "A", "B", "B", "A", "A", "B", "B"]

    pooled = controls.auc(scores, labels)
    stratified = mod.auc_stratified(scores, labels, objects)

    assert pooled == pytest.approx(0.75)
    assert stratified == pytest.approx(1.0)
    assert stratified != pytest.approx(pooled)


# --- 004-3 --------------------------------------------------------------


def test_single_object_degenerates_to_pooled() -> None:
    """With exactly one object, stratified AUC collapses to the pooled AUC."""
    scores = [0.9, 0.4, 0.6, 0.2, 0.8, 0.1]
    labels = [1, 0, 1, 0, 1, 0]
    objects = ["only"] * 6

    stratified = mod.auc_stratified(scores, labels, objects)
    pooled = controls.auc(scores, labels)

    assert stratified == pytest.approx(pooled)


# --- 004-4 --------------------------------------------------------------


def test_object_without_both_classes_is_excluded() -> None:
    """An object missing one class gets weight 0 and is fully excluded.

    Object "B" here has only ``common`` items (n_good=0). Its presence must
    not move :func:`auc_stratified`'s result at all: calling the function
    on the full 6-item input must equal calling it on the 3-item input with
    "B" removed entirely.
    """
    scores = [0.9, 0.6, 0.4, 0.2, 0.1, 0.3]
    labels = [1, 1, 0, 0, 0, 0]
    objects = ["A", "A", "A", "B", "B", "B"]

    with_b = mod.auc_stratified(scores, labels, objects)
    without_b = mod.auc_stratified(scores[:3], labels[:3], objects[:3])

    assert with_b == pytest.approx(without_b)
    # Sanity: "A" alone is not itself degenerate (both classes present).
    assert with_b != pytest.approx(0.5)


# --- 004-5 --------------------------------------------------------------


def test_aggregation_is_per_draw_not_marginal_median() -> None:
    """§5.1: candidate-level ``collapsed`` comes from the per-draw proportion,
    never from a marginal median of ``AUC_full`` / ``AUC_LAO`` taken
    separately.

    3 draws, each internally consistent:

    * draw 0: full=0.95, lao=0.95 -> eligible, not collapsed
    * draw 1: full=0.95, lao=0.55 -> eligible, collapsed
    * draw 2: full=0.55, lao=0.55 -> NOT eligible (full below floor)

    Per-draw proportion: only 1/3 draws collapsed (< 0.5 threshold) ->
    candidate-level ``collapsed`` is False.

    A naive "marginal median" reading would instead take
    ``median(AUC_full) = 0.95`` (>= floor -> "eligible") and
    ``median(AUC_LAO) = 0.55`` (< floor -> "collapsed") *independently* --
    a (full, LAO) pairing that **no single draw above ever produced** (draw
    1 has that low LAO but draw 2, not draw 0, supplies the low-full
    reading) -- and would misjudge the candidate as collapsed.
    """
    draws = [
        mod.DrawResult(auc_full=0.95, auc_lao=0.95, potency=0.5),
        mod.DrawResult(auc_full=0.95, auc_lao=0.55, potency=0.5),
        mod.DrawResult(auc_full=0.55, auc_lao=0.55, potency=0.5),
    ]

    aggregate = mod.aggregate_candidate_draws(draws)
    assert aggregate.collapsed is False
    assert aggregate.eligible is True
    assert aggregate.collapsed_draw_share == pytest.approx(1.0 / 3.0)

    # The naive marginal-median reading this fixture is designed to defeat.
    naive_median_full = float(np.median([d.auc_full for d in draws]))
    naive_median_lao = float(np.median([d.auc_lao for d in draws]))
    naive_would_call_collapsed = (
        naive_median_full >= _FLOOR and naive_median_lao < _FLOOR
    )
    assert naive_would_call_collapsed is True
    assert aggregate.collapsed != naive_would_call_collapsed


# --- 004-6 --------------------------------------------------------------


def test_bootstrap_strata_are_object_by_class() -> None:
    """Every bootstrap resample's (object, label) multiset equals the
    original -- resampling never crosses an object or a class boundary.

    If the implementation stratified only by object (ignoring class), a
    resample could pull all-good indices into a slot that was originally
    common, changing the (object, label) counts. If it stratified only by
    class (ignoring object), items could cross between objects. Either bug
    would make at least one seed's resampled multiset diverge from the
    original; this checks 20 independent seeds.
    """
    labels = [1, 1, 0, 0, 0, 1, 0, 0, 1, 1]
    objects = ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C"]
    original = Counter(zip(objects, labels, strict=True))

    for seed in range(20):
        rng = np.random.default_rng(seed)
        idx = mod.bootstrap_resample_indices(labels, objects, rng)
        assert len(idx) == len(labels)
        resampled = Counter((objects[i], labels[i]) for i in idx)
        assert resampled == original


# --- 004-7 --------------------------------------------------------------


def test_membership_auc_orientation() -> None:
    """``AUC_membership = auc(1 - m, label_good)`` -- orientation is flipped.

    ``membership`` is high for common items and low for good items here
    (a scorer that is very "close to the anchor pool" for common use, and
    far from it for good/novel ideas). Flipping via ``1 - m`` before
    scoring should read this as high discrimination (AUC ~= 1.0); scoring
    the raw, unflipped ``m`` directly against the same labels must give the
    inverted reading (AUC ~= 0.0) -- proving the module actually applies
    the flip rather than passing membership through unchanged.
    """
    membership = [0.9, 0.85, 0.8, 0.1, 0.05, 0.02]
    labels = [0, 0, 0, 1, 1, 1]

    flipped_result = mod.auc_membership(membership, labels)
    unflipped_result = controls.auc(membership, labels)

    assert flipped_result == pytest.approx(1.0)
    assert unflipped_result == pytest.approx(0.0)
    assert flipped_result != pytest.approx(unflipped_result)


# --- 004-8 --------------------------------------------------------------


def test_bootstrap_seeded_and_seed_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same seed reproduces the bootstrap result bit-for-bit; a different
    seed produces a different result.

    ``N_RESAMPLES`` is monkeypatched down to keep the test fast -- the
    function reads it fresh from ``_c.N_RESAMPLES`` on every call (never
    cached), so this does not require touching the function's signature.
    """
    monkeypatch.setattr(_c, "N_RESAMPLES", 200)

    # Within-object overlap between good/common is deliberate: if the two
    # classes were perfectly separated, every bootstrap resample would give
    # the same AUC (1.0) regardless of which items land in which slot, and
    # this test would pass by accident rather than by exercising real
    # resample variance.
    scores_full = [0.9, 0.55, 0.35, 0.6, 0.45, 0.2, 0.65, 0.55, 0.4, 0.35]
    scores_lao = [0.7, 0.5, 0.3, 0.55, 0.4, 0.25, 0.5, 0.48, 0.3, 0.45]
    labels = [1, 1, 1, 0, 0, 0, 1, 0, 1, 0]
    objects = ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B"]

    result_same_a = mod.bootstrap_stratified_drop(
        scores_full, scores_lao, labels, objects, seed=123
    )
    result_same_b = mod.bootstrap_stratified_drop(
        scores_full, scores_lao, labels, objects, seed=123
    )
    result_other_seed = mod.bootstrap_stratified_drop(
        scores_full, scores_lao, labels, objects, seed=456
    )

    assert result_same_a == result_same_b
    assert result_same_a != result_other_seed


# --- 004-9 --------------------------------------------------------------


def test_permutation_called_once_per_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    """``permutation_p_stratified`` is called exactly once regardless of how
    many anchor draws are passed in -- never once per draw.

    Both heavy §5.2/§5.3 functions are replaced with call-counting spies
    (``monkeypatch.setattr`` on the module-level names
    ``build_candidate_report`` actually calls), so this test is fast and
    directly counts invocations rather than trusting a self-report.
    """
    permutation_calls: list[tuple[Sequence[float], Sequence[int], Sequence[str]]] = []
    bootstrap_calls: list[int] = []

    def _fake_permutation(
        scores: Sequence[float],
        labels: Sequence[int],
        objects: Sequence[str],
        *,
        seed: int,
    ) -> float:
        del seed
        permutation_calls.append((scores, labels, objects))
        return 0.5

    def _fake_bootstrap(
        *,
        scores_full: Sequence[float],
        scores_lao: Sequence[float],
        labels: Sequence[int],
        objects: Sequence[str],
        seed: int,
    ) -> mod.BootstrapDropResult:
        del scores_full, scores_lao, labels, objects, seed
        bootstrap_calls.append(1)
        return mod.BootstrapDropResult(
            auc_full_ci=(0.85, 0.95),
            auc_lao_ci=(0.5, 0.6),
            drop_ci=(0.1, 0.3),
            p_drop_le_zero=0.02,
        )

    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fake_bootstrap)

    draws = [
        mod.DrawItems(
            scores_full=(0.9, 0.4),
            scores_lao=(0.6, 0.3),
            labels=(1, 0),
            objects=("A", "A"),
            potency=0.2 + 0.01 * i,
        )
        for i in range(7)
    ]

    summary = mod.build_candidate_report(
        "X0", "embedding", draws, bootstrap_seed=1, permutation_seed=2
    )

    assert len(permutation_calls) == 1
    assert len(bootstrap_calls) == 1
    assert summary.permutation_p == 0.5
    assert summary.bootstrap.auc_lao_ci == (0.5, 0.6)
    assert summary.report.auc_lao_ci_lower == 0.5
    assert summary.report.auc_lao_ci_upper == 0.6


# --- §5.1 per-draw predicate boundaries -------------------------------------
#
# Added by the orchestrator after independent mutation testing found three
# escaped mutants in the per-draw predicates: ``potency > 0`` relaxed to
# ``>= 0``, ``auc_lao < floor`` relaxed to ``<=``, and the ``engaged``
# conjunct removed from ``is_draw_collapsed`` all left the suite green.
# Those are exactly the guards DA-G1-11 and design-final.md §5.1 rest on, so
# each boundary now has a test that pins the strict side.


def test_draw_engaged_requires_strictly_positive_potency() -> None:
    """potency == 0 is *not* engaged (DA-G1-11: the audit never fired).

    Kills the ``potency >= 0.0`` mutant: with a non-strict comparison every
    draw would count as engaged, so a candidate whose LAO audit never fires
    could reach ``PASS`` on ``auc_lao == auc_full``.
    """
    assert mod.is_draw_engaged(0.0) is False
    assert mod.is_draw_engaged(1e-12) is True
    assert mod.is_draw_engaged(0.5) is True


def test_draw_collapsed_requires_auc_strictly_below_floor() -> None:
    """``auc_lao == floor`` is not a collapse (§5.1 uses ``<``, not ``<=``)."""
    floor = _c.AUC_FLOOR
    on_floor = mod.is_draw_collapsed(
        eligible=True, engaged=True, auc_lao=floor, floor=floor
    )
    below = mod.is_draw_collapsed(
        eligible=True, engaged=True, auc_lao=floor - 1e-9, floor=floor
    )
    assert on_floor is False
    assert below is True


def test_draw_collapsed_requires_engaged() -> None:
    """A draw whose audit never fired cannot be a collapse.

    Kills the mutant that drops the ``engaged`` conjunct. Without it a
    potency-0 draw would be scored as collapsed purely because its (identical)
    full and LAO AUC sit below the floor, which is the ineligible-scorer case,
    not evidence that the anchor audit moved anything.
    """
    floor = _c.AUC_FLOOR
    assert (
        mod.is_draw_collapsed(
            eligible=True, engaged=False, auc_lao=floor - 0.3, floor=floor
        )
        is False
    )
    assert (
        mod.is_draw_collapsed(
            eligible=True, engaged=True, auc_lao=floor - 0.3, floor=floor
        )
        is True
    )


def test_draw_collapsed_requires_eligible() -> None:
    """An ineligible draw is never counted as a collapse (§6 eligibility guard)."""
    floor = _c.AUC_FLOOR
    assert (
        mod.is_draw_collapsed(
            eligible=False, engaged=True, auc_lao=floor - 0.3, floor=floor
        )
        is False
    )


def test_draw_eligible_boundary_is_inclusive_at_the_floor() -> None:
    """``AUC_strat(full) == floor`` clears eligibility (§5.1 uses ``>=``)."""
    floor = _c.AUC_FLOOR
    assert mod.is_draw_eligible(floor, floor=floor) is True
    assert mod.is_draw_eligible(floor - 1e-9, floor=floor) is False


def test_median_draw_values_are_not_across_draw_medians() -> None:
    """``*_at_median_draw`` and §5.1's across-draw summaries are different things.

    The median draw is selected by ``drop``, so the AUC it happens to carry
    need not be ``median_b(AUC_full)``. This was observed on real data: on
    Cambridge SPLIT-PARITY, X0 reports ``auc_full_at_median_draw`` 0.8156
    while only 32.5% of its draws clear the 0.80 floor -- a reader who took
    the field for ``median_b(AUC_full)`` would call those two numbers
    contradictory. The names must stay distinct, and both must be emitted.
    """
    # Three draws. The middle-by-drop draw is deliberately *not* the
    # middle-by-AUC_full draw.
    draws = [
        mod.DrawResult(auc_full=0.95, auc_lao=0.35, potency=0.5),  # drop 0.60
        mod.DrawResult(auc_full=0.60, auc_lao=0.30, potency=0.5),  # drop 0.30
        mod.DrawResult(auc_full=0.70, auc_lao=0.60, potency=0.5),  # drop 0.10
    ]
    idx = mod.median_draw_index([d.drop for d in draws])
    aggregate = mod.aggregate_candidate_draws(draws)

    assert draws[idx].drop == pytest.approx(0.30)  # median by drop
    assert draws[idx].auc_full == 0.60  # ... but the *lowest* AUC_full
    assert aggregate.median_drop == pytest.approx(0.30)
    # The across-draw median of AUC_full is 0.70, which the median draw does
    # not carry -- so the two quantities genuinely disagree here.
    assert float(np.median([d.auc_full for d in draws])) == 0.70
    assert draws[idx].auc_full != float(np.median([d.auc_full for d in draws]))


def test_candidate_summary_emits_section_5_1_reporting_block() -> None:
    """§5.1's required reporting stats travel with every bootstrapped candidate.

    ``collapsed_draw_share`` / ``median_b(drop)`` / the 5-95 percentile band
    are mandated by design-final.md §5.1 for the reported candidates, not
    only for the lexical ones that skip the bootstrap.
    """
    draws = [
        mod.DrawItems(
            scores_full=[0.9, 0.8, 0.2, 0.1],
            scores_lao=[0.9, 0.8, 0.2, 0.1],
            labels=[1, 1, 0, 0],
            objects=["bowl", "clip", "bowl", "clip"],
            potency=0.25 + 0.01 * i,
        )
        for i in range(3)
    ]
    summary = mod.build_candidate_report(
        "X0", "embedding", draws, bootstrap_seed=1, permutation_seed=2
    )
    assert isinstance(summary.aggregate, mod.DrawAggregate)
    assert summary.aggregate.median_draw_index == summary.median_draw_index
    for field in ("collapsed_draw_share", "median_drop", "drop_p5", "drop_p95"):
        assert hasattr(summary.aggregate, field)
