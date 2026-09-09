"""Tests for the I-004 Stage 1 deflation test (design-final.md §3 Stage 1).

Encoder-independent (Test Plan): every fixture below is a hand-built
:class:`~scripts.paper01_scope_condition.ObjectGoldPool` /
:class:`~scripts.paper01_external_audit.DrawItems` (scores/labels/objects
handmade), never routed through an encoder -- 004-6 is the sole exception
and even there the "real data path" is exercised by delegating to the
frozen :func:`~scripts.paper01_external_audit.auc_stratified` directly as
the independent oracle, never by loading real embeddings (out of I-004's
scope, lands in I-007).

This is the most deflating hypothesis test in the whole ADR (issue 004
Background): "the internal collapse is a small-sample artifact of 41
items / 25 valid pairs". A design that leans toward
``"DEFLATION_REJECTED"`` would bias the paper towards being written, so
every boundary here is pinned in the *conservative* direction (ties go to
``"INCONCLUSIVE"`` / ``"DEFLATION_SUPPORTED"``, never silently to
``"DEFLATION_REJECTED"``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import paper01_external_audit as g1
from scripts import paper01_scope_condition as mod

if TYPE_CHECKING:
    import numpy as np

SEED = mod.SEED


# --- fixture builders --------------------------------------------------------


def _pool(
    object_key: str,
    *,
    weight: float,
    n_good: int,
    n_common: int,
    good_start: int,
    common_start: int,
) -> mod.ObjectGoldPool:
    """One object's index pools, drawn from disjoint integer ranges so a
    caller can always tell which object an index came from without needing
    the ``objects`` array.
    """
    return mod.ObjectGoldPool(
        object_key=object_key,
        object_weight=weight,
        good_item_indices=tuple(range(good_start, good_start + n_good)),
        common_item_indices=tuple(range(common_start, common_start + n_common)),
    )


def _contexts_5_objects() -> dict[str, mod.ObjectGoldPool]:
    """5 active objects, generously-sized disjoint pools, distinct weights
    (so :func:`_stage1_object_order` is unambiguous) -- exercises the
    first 5 entries of :data:`STAGE1_INTERNAL_GOOD_COUNTS`
    ``(3, 3, 1, 3, 1)`` (sum 11), no object short of its assigned count.
    """
    return {
        "obj_a": _pool(
            "obj_a", weight=50.0, n_good=8, n_common=8, good_start=0, common_start=100
        ),
        "obj_b": _pool(
            "obj_b", weight=40.0, n_good=8, n_common=8, good_start=10, common_start=110
        ),
        "obj_c": _pool(
            "obj_c", weight=30.0, n_good=8, n_common=8, good_start=20, common_start=120
        ),
        "obj_d": _pool(
            "obj_d", weight=20.0, n_good=8, n_common=8, good_start=30, common_start=130
        ),
        "obj_e": _pool(
            "obj_e", weight=10.0, n_good=8, n_common=8, good_start=40, common_start=140
        ),
    }


def _contexts_18_objects() -> dict[str, mod.ObjectGoldPool]:
    """18 active objects (> the 16-entry STAGE1_INTERNAL_GOOD_COUNTS multiset)
    to exercise the cyclic wrap-around, generously-sized pools.
    """
    out: dict[str, mod.ObjectGoldPool] = {}
    for i in range(18):
        key = f"obj_{i:02d}"
        weight = 100.0 - i  # strictly descending -> unambiguous order
        out[key] = _pool(
            key,
            weight=weight,
            n_good=6,
            n_common=6,
            good_start=1000 * i,
            common_start=1000 * i + 500,
        )
    return out


# --- AC 004-1 (extraction shape) ---------------------------------------------


def test_replicate_shape_matches_internal() -> None:
    """Every replicate: exactly 1 common index per object, good totals match
    the object_weight-descending cyclic assignment of
    :data:`STAGE1_INTERNAL_GOOD_COUNTS` (AC 004-1).
    """
    contexts = _contexts_5_objects()
    subsets = mod.internal_shaped_replicates(
        contexts, replicates=25, corpus="test-corpus", scheme="SPLIT-BLOCK", seed=SEED
    )
    assert len(subsets) == 25

    order = mod._stage1_object_order(contexts)
    assert order == ["obj_a", "obj_b", "obj_c", "obj_d", "obj_e"]
    expected_good_counts = dict(
        zip(order, mod.STAGE1_INTERNAL_GOOD_COUNTS[: len(order)], strict=True)
    )
    assert expected_good_counts == {
        "obj_a": 3,
        "obj_b": 3,
        "obj_c": 1,
        "obj_d": 3,
        "obj_e": 1,
    }
    expected_total_good = sum(expected_good_counts.values())
    assert expected_total_good == 11

    for subset in subsets:
        by_object: dict[str, dict[str, int]] = {
            obj: {"good": 0, "common": 0} for obj in order
        }
        for idx in subset.item_indices:
            for obj, pool in contexts.items():
                if idx in pool.good_item_indices:
                    by_object[obj]["good"] += 1
                elif idx in pool.common_item_indices:
                    by_object[obj]["common"] += 1
        for obj in order:
            assert by_object[obj]["common"] == 1, f"{obj}: {by_object[obj]}"
            assert by_object[obj]["good"] == expected_good_counts[obj], (
                f"{obj}: {by_object[obj]}"
            )
        assert sum(v["good"] for v in by_object.values()) == expected_total_good
        assert subset.pool_short_objects == ()


def test_cyclic_assignment_wraps_past_sixteen_objects() -> None:
    """With more than 16 active objects, the good-count assignment wraps
    around :data:`STAGE1_INTERNAL_GOOD_COUNTS` (AC 004-1's cyclic clause).
    """
    contexts = _contexts_18_objects()
    good_counts = mod._stage1_good_counts(contexts)
    order = mod._stage1_object_order(contexts)
    assert len(order) == 18

    n = len(mod.STAGE1_INTERNAL_GOOD_COUNTS)
    assert n == 16
    # objects 16 and 17 (0-based) wrap back to counts[0] / counts[1]
    assert good_counts[order[16]] == mod.STAGE1_INTERNAL_GOOD_COUNTS[0]
    assert good_counts[order[17]] == mod.STAGE1_INTERNAL_GOOD_COUNTS[1]
    for i, obj in enumerate(order):
        assert good_counts[obj] == mod.STAGE1_INTERNAL_GOOD_COUNTS[i % n]


# --- AC 004-2 (same-object pair share, internal scale) -----------------------


def test_same_object_pair_share_is_internal_scale() -> None:
    """The internal shape's own same-object pair share (16 objects, common=1
    each) is exactly 6.25% -- 1/16, structurally, from
    :func:`same_object_pair_share`'s definition, never hardcoded as a
    literal expectation (AC 004-2).
    """
    internal_counts = {
        f"obj_{i}": (count, 1)
        for i, count in enumerate(mod.STAGE1_INTERNAL_GOOD_COUNTS)
    }
    internal_share = mod.same_object_pair_share(internal_counts)
    assert internal_share == 1.0 / 16.0
    assert internal_share == 0.0625


def test_same_object_pair_share_extraction_is_same_order() -> None:
    """A real :func:`internal_shaped_replicates` extraction's pooled
    same-object pair share is the same order of magnitude as the internal
    6.25% figure (AC 004-2) -- both derive from "exactly one common item
    per active object", so the share is ``1/n_active_objects`` regardless
    of the good-count assignment.
    """
    contexts = _contexts_18_objects()
    subsets = mod.internal_shaped_replicates(
        contexts, replicates=1, corpus="ocsai", scheme="SPLIT-BLOCK", seed=SEED
    )
    subset = subsets[0]

    counts_by_object: dict[str, list[int]] = {obj: [0, 0] for obj in contexts}
    for idx in subset.item_indices:
        for obj, pool in contexts.items():
            if idx in pool.good_item_indices:
                counts_by_object[obj][0] += 1
            elif idx in pool.common_item_indices:
                counts_by_object[obj][1] += 1

    share = mod.same_object_pair_share(
        {obj: (g, c) for obj, (g, c) in counts_by_object.items()}
    )
    expected = 1.0 / len(contexts)
    assert share == pytest.approx(expected)
    # both this extraction's share and the internal 6.25% figure (asserted
    # in test_same_object_pair_share_is_internal_scale above) sit in the
    # same single-digit-percent order of magnitude
    assert 0.01 < share < 0.15


# --- AC 004-3 (determinism / seed sensitivity) --------------------------------


def test_replicates_are_seeded_and_differ_across_seeds() -> None:
    """Same seed -> identical extraction; a different seed -> a different
    one (AC 004-3).
    """
    contexts = _contexts_5_objects()
    kwargs = {"replicates": 10, "corpus": "ocsai", "scheme": "SPLIT-BLOCK"}

    a1 = mod.internal_shaped_replicates(contexts, seed=SEED, **kwargs)
    a2 = mod.internal_shaped_replicates(contexts, seed=SEED, **kwargs)
    b = mod.internal_shaped_replicates(contexts, seed=SEED + 1, **kwargs)

    assert [s.item_indices for s in a1] == [s.item_indices for s in a2]
    assert [s.item_indices for s in a1] != [s.item_indices for s in b]


def test_replicates_differ_across_corpus_and_scheme() -> None:
    """``corpus`` / ``scheme`` are load-bearing, explicit arguments (Codex
    TASK-PRE MEDIUM-2) -- changing either alone (same ``seed``) changes the
    extraction.
    """
    contexts = _contexts_5_objects()
    base = mod.internal_shaped_replicates(
        contexts, replicates=10, corpus="ocsai", scheme="SPLIT-BLOCK", seed=SEED
    )
    other_corpus = mod.internal_shaped_replicates(
        contexts, replicates=10, corpus="cambridge", scheme="SPLIT-BLOCK", seed=SEED
    )
    other_scheme = mod.internal_shaped_replicates(
        contexts, replicates=10, corpus="ocsai", scheme="SPLIT-PARITY", seed=SEED
    )
    assert [s.item_indices for s in base] != [s.item_indices for s in other_corpus]
    assert [s.item_indices for s in base] != [s.item_indices for s in other_scheme]


# --- AC 004-4 (anchor is draw_index=0, spy) -----------------------------------


def test_stage1_uses_draw_index_zero_not_median(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every call ``internal_shaped_replicates`` makes to
    :func:`~scripts.paper01_external_audit.anchor_draw_indices` passes
    ``draw_index=`` :data:`STAGE1_DRAW_INDEX` (0) -- never a value derived
    from an observed statistic (AC 004-4). Spies on the real call
    argument, never infers wiring from an aggregate AUC/drop number (Test
    Plan: "AUC などの集約統計で配線を検査しない").
    """
    calls: list[dict[str, object]] = []
    real_fn = g1.anchor_draw_indices

    def _spy(pool_size: int, k: int, *, seed: int, draw_index: int) -> np.ndarray:
        calls.append(
            {"pool_size": pool_size, "k": k, "seed": seed, "draw_index": draw_index}
        )
        return real_fn(pool_size, k, seed=seed, draw_index=draw_index)

    monkeypatch.setattr(mod._g1, "anchor_draw_indices", _spy)

    contexts = _contexts_5_objects()
    mod.internal_shaped_replicates(
        contexts, replicates=5, corpus="ocsai", scheme="SPLIT-BLOCK", seed=SEED
    )

    assert calls, "expected internal_shaped_replicates to call anchor_draw_indices"
    for call in calls:
        assert call["draw_index"] == mod.STAGE1_DRAW_INDEX
        assert call["draw_index"] == 0


# --- AC 004-5 (median-by-drop draw is sensitivity only) -----------------------


def _draw_items(
    scores_full: list[float],
    scores_lao: list[float],
    labels: list[int],
    objects: list[str],
) -> g1.DrawItems:
    return g1.DrawItems(
        scores_full=tuple(scores_full),
        scores_lao=tuple(scores_lao),
        labels=tuple(labels),
        objects=tuple(objects),
        potency=0.5,
    )


def test_median_draw_is_sensitivity_only() -> None:
    """``median_draw_drop`` / ``median_draw_outcome`` are computed
    independently of the primary ``drop_p5``/``drop_p95``/``stage1_outcome``
    band and never override it (AC 004-5): a fixture where the primary
    band rejects deflation while the single median-drop replicate's own
    (degenerate single-point) outcome supports it.
    """
    # 3 objects, 1 good + 1 common each; item indices 0..5.
    labels = [1, 0, 1, 0, 1, 0]
    objects = ["a", "a", "b", "b", "c", "c"]
    # object "c"'s scores_lao are *not* tied (unlike a/b), so replicate 1
    # (which includes object c) gets a different auc_lao -- and therefore
    # a different drop -- from replicate 0 (which does not).
    scores_full = [0.9, 0.1, 0.9, 0.1, 0.9, 0.1]
    scores_lao = [0.5, 0.5, 0.5, 0.5, 0.9, 0.1]
    draw_items = _draw_items(scores_full, scores_lao, labels, objects)

    # Two overlapping-but-distinct replicates: replicate 0 uses object a+b
    # (indices 0-3, drop 0.5); replicate 1 uses object b+c (indices 2-5,
    # drop 0.25). This lets the pooled band (over both) differ from the
    # single median-drop replicate's own value.
    subsets = [
        mod.GoldSubset(
            replicate_index=0, item_indices=(0, 1, 2, 3), pool_short_objects=()
        ),
        mod.GoldSubset(
            replicate_index=1, item_indices=(2, 3, 4, 5), pool_short_objects=()
        ),
    ]

    # Pick a reference_drop that sits inside the pooled band but does NOT
    # equal the single median-drop replicate's own drop value, so the two
    # outcomes can disagree.
    result = mod.stage1_drop_distribution(
        draw_items, subsets, candidate="X0", reference_drop=0.4
    )

    assert result.median_draw_drop != result.drop_p5
    # the primary outcome must be derivable purely from (drop_p5, drop_p95,
    # eligible_fraction) -- recomputing it independently must match exactly
    recomputed = mod.stage1_outcome(
        (result.drop_p5, result.drop_p95), 0.4, result.eligible_fraction
    )
    assert result.stage1_outcome == recomputed
    # median_draw_outcome is allowed to differ from the primary outcome --
    # proving it is not silently copied/aliased
    assert result.median_draw_outcome in mod.STAGE1_OUTCOME_ENUM


def test_median_draw_outcome_never_feeds_primary_outcome() -> None:
    """A fixture where the single median-by-drop replicate is itself
    ``INCONCLUSIVE`` (below-floor ``AUC_full``) while the *pooled* majority
    is eligible -- ``median_draw_outcome`` reports ``"INCONCLUSIVE"`` while
    the primary ``stage1_outcome`` does not, proving the two are wired
    independently (AC 004-5's non-degeneracy witness, not the same value
    under two names).

    3 replicates, one object each (disjoint item indices so each
    replicate's own AUC is fully controlled): replicate 0
    (eligible, drop 0.0), replicate 1 (eligible, drop 1.0), replicate 2
    (``AUC_full=0.5`` -- below :data:`~scripts.paper01_scope_condition._c.
    AUC_FLOOR` -- drop 0.5). Sorted drops ``[0.0, 0.5, 1.0]`` put
    replicate 2 (the ineligible one) exactly at the median.
    """
    labels = [1, 0, 1, 0, 1, 0]
    objects = ["x", "x", "x", "x", "x", "x"]
    # replicate 0 (indices 0-1): auc_full=1.0, auc_lao=1.0 -> drop 0.0, eligible
    # replicate 1 (indices 2-3): auc_full=1.0, auc_lao=0.0 -> drop 1.0, eligible
    # replicate 2 (indices 4-5): auc_full=0.5, auc_lao=0.0 -> drop 0.5, INELIGIBLE
    scores_full = [0.9, 0.1, 0.9, 0.1, 0.5, 0.5]
    scores_lao = [0.9, 0.1, 0.1, 0.9, 0.1, 0.9]
    draw_items = _draw_items(scores_full, scores_lao, labels, objects)

    subsets = [
        mod.GoldSubset(replicate_index=0, item_indices=(0, 1), pool_short_objects=()),
        mod.GoldSubset(replicate_index=1, item_indices=(2, 3), pool_short_objects=()),
        mod.GoldSubset(replicate_index=2, item_indices=(4, 5), pool_short_objects=()),
    ]
    result = mod.stage1_drop_distribution(
        draw_items, subsets, candidate="X0", reference_drop=0.3
    )

    assert result.median_draw_drop == pytest.approx(0.5)
    assert result.eligible_fraction == pytest.approx(2.0 / 3.0)
    assert result.eligible_fraction > 0.5
    # the pooled majority is eligible, so the primary outcome is decided by
    # the band, not folded to INCONCLUSIVE
    assert result.stage1_outcome != "INCONCLUSIVE"
    # but the single median-drop replicate is itself below AUC_FLOOR, so
    # its own degenerate-band outcome is INCONCLUSIVE regardless
    assert result.median_draw_outcome == "INCONCLUSIVE"
    assert result.stage1_outcome != result.median_draw_outcome


# --- AC 004-6 (shrinkage-only: full gold reproduces the pooled statistic) ----


def test_full_gold_reproduces_g1_pooled() -> None:
    """Passing *every* item (no shrinkage) reproduces exactly what calling
    the frozen :func:`~scripts.paper01_external_audit.auc_stratified`
    directly on the same arrays gives (AC 004-6: "縮小以外が動いていない").

    Uses a tie-heavy fixture so a naive reimplementation (e.g. plain
    ``np.mean``-based AUC) would diverge from ``controls.auc``'s specific
    tie-rank handling -- a non-vacuous cross-check against the frozen
    apparatus's own reported computation, never a value invented purely by
    this new code.
    """
    labels = [1, 0, 1, 0, 1, 0, 1, 0]
    objects = [
        "brick",
        "brick",
        "brick",
        "brick",
        "paperclip",
        "paperclip",
        "paperclip",
        "paperclip",
    ]
    # deliberate ties within object "brick" to exercise controls.auc's tie
    # handling; "paperclip" is untied.
    scores_full = [0.7, 0.7, 0.9, 0.2, 0.8, 0.3, 0.6, 0.4]
    scores_lao = [0.5, 0.5, 0.5, 0.5, 0.55, 0.45, 0.55, 0.45]
    draw_items = _draw_items(scores_full, scores_lao, labels, objects)

    all_indices = tuple(range(len(labels)))
    subset = mod.GoldSubset(
        replicate_index=0, item_indices=all_indices, pool_short_objects=()
    )

    result = mod.stage1_drop_distribution(
        draw_items, [subset], candidate="X0", reference_drop=0.0
    )

    expected_auc_full = g1.auc_stratified(scores_full, labels, objects)
    expected_auc_lao = g1.auc_stratified(scores_lao, labels, objects)
    expected_drop = expected_auc_full - expected_auc_lao

    assert result.n_replicates == 1
    assert result.median_drop == pytest.approx(expected_drop, abs=1e-12)
    assert result.drop_p5 == pytest.approx(expected_drop, abs=1e-12)
    assert result.drop_p95 == pytest.approx(expected_drop, abs=1e-12)


# --- 004-MUT: pooled/stratified must not be interchangeable ------------------


def test_stratified_statistic_diverges_from_pooled_under_skewed_weights() -> None:
    """The primary pooled drop and the secondary layer-stratified ("副") drop
    are genuinely different computations -- kills a mutant that swaps which
    statistic feeds ``drop_p5``/``drop_p95`` vs. ``drop_p5_strat``/
    ``drop_p95_strat`` (design-final.md §3 Stage 1's "pooled AUC を主、
    層別を副").

    Object "big" (weight 3*3=9, ``AUC_full=1.0``) dominates the pooled
    (weighted) statistic; object "small" (weight 1*1=1, ``AUC_full=0.0``)
    contributes equally to the unweighted per-object mean. ``AUC_lao`` is
    tied (0.5) for every item, identical for both formulas, so the two
    drops differ *only* through how ``AUC_full`` is aggregated.
    """
    labels = [1, 1, 1, 0, 0, 0, 1, 0]
    objects = ["big", "big", "big", "big", "big", "big", "small", "small"]
    scores_full = [
        0.9,
        0.8,
        0.7,
        0.3,
        0.2,
        0.1,
        0.1,
        0.9,
    ]  # big: AUC=1.0, small: AUC=0.0
    scores_lao = [0.5] * 8  # tied everywhere -> AUC=0.5 for both objects/formulas
    draw_items = _draw_items(scores_full, scores_lao, labels, objects)

    all_indices = tuple(range(len(labels)))
    subset = mod.GoldSubset(
        replicate_index=0, item_indices=all_indices, pool_short_objects=()
    )
    result = mod.stage1_drop_distribution(
        draw_items, [subset], candidate="X0", reference_drop=0.0
    )

    # pooled (weighted by n_good*n_common): (9*1.0 + 1*0.0) / 10 - 0.5 = 0.4
    assert result.drop_p5 == pytest.approx(0.4, abs=1e-9)
    assert result.drop_p95 == pytest.approx(0.4, abs=1e-9)
    # stratified (unweighted per-object mean): (1.0 + 0.0)/2 - 0.5 = 0.0
    assert result.drop_p5_strat == pytest.approx(0.0, abs=1e-9)
    assert result.drop_p95_strat == pytest.approx(0.0, abs=1e-9)
    assert result.drop_p5 != result.drop_p5_strat


# --- AC 004-7 (band decision is non-tautological, both branches) -------------


def test_deflation_band_both_branches() -> None:
    """``stage1_outcome`` reaches both ``"DEFLATION_SUPPORTED"`` (band
    contains 0.2350) and ``"DEFLATION_REJECTED"`` (band excludes it) --
    AC 004-7, majority-eligible in both so INCONCLUSIVE never masks it.
    """
    reference = mod.STAGE1_INTERNAL_DROP_REF
    supported = mod.stage1_outcome((0.10, 0.30), reference, eligible_fraction=0.9)
    rejected = mod.stage1_outcome((0.50, 0.60), reference, eligible_fraction=0.9)
    assert supported == "DEFLATION_SUPPORTED"
    assert rejected == "DEFLATION_REJECTED"
    assert supported != rejected

    assert mod.stage1_deflation_supported((0.10, 0.30), reference, 0.9) is True
    assert mod.stage1_deflation_supported((0.50, 0.60), reference, 0.9) is False


# --- Codex TASK-PRE MEDIUM-3 boundary tests -----------------------------------


def test_reference_drop_on_band_boundary_is_supported() -> None:
    """``0.2350`` exactly equal to ``drop_p5`` or ``drop_p95`` counts as
    *inside* the band -- ``"DEFLATION_SUPPORTED"`` (closed interval, frozen
    and pinned).
    """
    reference = mod.STAGE1_INTERNAL_DROP_REF
    at_lower_edge = mod.stage1_outcome(
        (reference, 0.99), reference, eligible_fraction=0.9
    )
    at_upper_edge = mod.stage1_outcome(
        (0.0, reference), reference, eligible_fraction=0.9
    )
    assert at_lower_edge == "DEFLATION_SUPPORTED"
    assert at_upper_edge == "DEFLATION_SUPPORTED"


def test_eligible_fraction_exactly_half_is_inconclusive() -> None:
    """``eligible_fraction == 0.5`` exactly is ``<= 0.5`` -> ``"INCONCLUSIVE"``
    (the frozen floor is inclusive, not a strict ``<``)."""
    reference = mod.STAGE1_INTERNAL_DROP_REF
    result = mod.stage1_outcome(
        (reference, reference), reference, eligible_fraction=0.5
    )
    assert result == "INCONCLUSIVE"
    # just above the floor: no longer inconclusive
    just_above = mod.stage1_outcome(
        (reference, reference), reference, eligible_fraction=0.500001
    )
    assert just_above != "INCONCLUSIVE"


# --- AC 004-8 (ineligible majority -> undecidable, eligible band as 副) ------


def test_ineligible_majority_is_recorded_as_undecidable() -> None:
    """When the majority of replicates are not eligible, the primary
    outcome is ``"INCONCLUSIVE"`` and the eligible-limited band
    (``drop_p5_eligible``/``drop_p95_eligible``) is reported from the
    minority of eligible replicates only (AC 004-8).
    """
    labels = [1, 0]
    objects = ["a", "a"]
    # AUC_FLOOR-relative construction: most replicates score AUC_full below
    # the floor (ineligible), a minority score above it (eligible).
    auc_floor = mod._c.AUC_FLOOR

    below_floor_full = [0.5, 0.5]  # AUC = 0.5, below any positive floor
    above_floor_full = [0.99, 0.01]  # AUC = 1.0, clears any floor <= 1.0
    assert 0.5 < auc_floor <= 1.0, (
        "fixture assumes AUC_FLOOR strictly between 0.5 and 1.0"
    )

    scores_lao = [0.5, 0.5]
    n_ineligible = 7
    n_eligible = 3
    assert n_eligible < n_ineligible  # minority, not vacuous

    # stage1_drop_distribution takes one DrawItems, so build a combined
    # 20-item array: first 14 items = 7 ineligible replicates' worth (2
    # items each), last 6 items = 3 eligible replicates' worth.
    combined_labels: list[int] = []
    combined_objects: list[str] = []
    combined_full: list[float] = []
    combined_lao: list[float] = []
    subsets: list[mod.GoldSubset] = []
    cursor = 0
    for _ in range(n_ineligible):
        combined_labels.extend(labels)
        combined_objects.extend(objects)
        combined_full.extend(below_floor_full)
        combined_lao.extend(scores_lao)
        subsets.append(
            mod.GoldSubset(
                replicate_index=len(subsets),
                item_indices=(cursor, cursor + 1),
                pool_short_objects=(),
            )
        )
        cursor += 2
    for _ in range(n_eligible):
        combined_labels.extend(labels)
        combined_objects.extend(objects)
        combined_full.extend(above_floor_full)
        combined_lao.extend(scores_lao)
        subsets.append(
            mod.GoldSubset(
                replicate_index=len(subsets),
                item_indices=(cursor, cursor + 1),
                pool_short_objects=(),
            )
        )
        cursor += 2

    draw_items = _draw_items(
        combined_full, combined_lao, combined_labels, combined_objects
    )
    result = mod.stage1_drop_distribution(
        draw_items, subsets, candidate="X0", reference_drop=mod.STAGE1_INTERNAL_DROP_REF
    )

    expected_fraction = n_eligible / (n_eligible + n_ineligible)
    assert result.eligible_fraction == pytest.approx(expected_fraction)
    assert expected_fraction <= 0.5
    assert result.stage1_outcome == "INCONCLUSIVE"
    assert result.deflation_supported is False

    # eligible-limited band is computed from the 3 eligible replicates
    # only, whose drop is (1.0 - 0.5) == 0.5 in every one of them
    assert result.drop_p5_eligible == pytest.approx(0.5)
    assert result.drop_p95_eligible == pytest.approx(0.5)
    assert result.median_drop_eligible == pytest.approx(0.5)
    # the *pooled* (unrestricted) band must differ from the eligible-only
    # band, proving the two are genuinely separate computations
    assert (
        result.drop_p5 != result.drop_p5_eligible
        or result.drop_p95 != result.drop_p95_eligible
    )


# --- AC 004-9 (partial pool shortage is surfaced, never silent) --------------


def test_insufficient_pool_objects_are_surfaced() -> None:
    """Exactly one of several objects is short of its assigned good count --
    ``pool_short_objects`` names only that object, ``n_objects_pool_short``
    is neither 0 nor the full object count (AC 004-9).
    """
    contexts = _contexts_5_objects()
    # obj_c is assigned good_count=1 (see test_replicate_shape_matches_
    # internal) -- shrink obj_b (assigned 3) down to only 1 available good
    # item so it alone becomes pool-short.
    contexts = dict(contexts)
    contexts["obj_b"] = mod.ObjectGoldPool(
        object_key="obj_b",
        object_weight=contexts["obj_b"].object_weight,
        good_item_indices=(10,),  # only 1 available, but 3 are needed
        common_item_indices=contexts["obj_b"].common_item_indices,
    )

    subsets = mod.internal_shaped_replicates(
        contexts, replicates=4, corpus="ocsai", scheme="SPLIT-BLOCK", seed=SEED
    )

    for subset in subsets:
        assert subset.pool_short_objects == ("obj_b",)

    n_objects = len(contexts)
    n_short = len(subsets[0].pool_short_objects)
    assert n_short == 1
    assert n_short != 0
    assert n_short != n_objects

    # best-effort draw: obj_b still contributes what IS available (1 good
    # item), never silently drops to zero
    for subset in subsets:
        obj_b_good = [
            idx
            for idx in subset.item_indices
            if idx in contexts["obj_b"].good_item_indices
        ]
        assert obj_b_good == [10]


def test_all_objects_short_is_also_surfaced() -> None:
    """The all-short case (every object under-supplied) is also recorded,
    not just the partial case -- ``n_objects_pool_short`` equals the full
    object count.
    """
    contexts = {
        "solo_a": mod.ObjectGoldPool(
            object_key="solo_a",
            object_weight=2.0,
            good_item_indices=(0,),  # needs 3 (first STAGE1_INTERNAL_GOOD_COUNTS entry)
            common_item_indices=(100,),
        ),
        "solo_b": mod.ObjectGoldPool(
            object_key="solo_b",
            object_weight=1.0,
            good_item_indices=(1,),  # needs 3 (second entry)
            common_item_indices=(101,),
        ),
    }
    subsets = mod.internal_shaped_replicates(
        contexts, replicates=2, corpus="ocsai", scheme="SPLIT-BLOCK", seed=SEED
    )
    assert set(subsets[0].pool_short_objects) == {"solo_a", "solo_b"}
    assert len(subsets[0].pool_short_objects) == len(contexts)


# --- 004-MUT: boundary predicate mutation witnesses ---------------------------


def test_mutant_eligible_floor_strict_less_than_is_killed() -> None:
    """A mutant that relaxes ``eligible_fraction <= 0.5`` to ``< 0.5`` would
    make ``eligible_fraction == 0.5`` fall through to the band check
    instead of ``"INCONCLUSIVE"`` -- this test's assertion at exactly 0.5
    kills it (paired with the mutation-log manual verification).
    """
    reference = mod.STAGE1_INTERNAL_DROP_REF
    result = mod.stage1_outcome(
        (reference, reference), reference, eligible_fraction=0.5
    )
    assert result == "INCONCLUSIVE"


def test_mutant_inconclusive_folded_to_rejected_is_killed() -> None:
    """A mutant that maps ``"INCONCLUSIVE"`` to ``"DEFLATION_REJECTED"``
    would make this assertion fail (paired with the mutation-log manual
    verification): the two are distinct enum members with distinct
    downstream consequences (``decide_scope``'s write gate, I-005).
    """
    reference = mod.STAGE1_INTERNAL_DROP_REF
    result = mod.stage1_outcome(
        (reference, reference), reference, eligible_fraction=0.1
    )
    assert result == "INCONCLUSIVE"
    assert result != "DEFLATION_REJECTED"


def test_mutant_band_open_interval_is_killed() -> None:
    """A mutant that relaxes the closed-interval band check (``<=``) to an
    open one (``<``) would flip the boundary-equal case from
    ``"DEFLATION_SUPPORTED"`` to ``"DEFLATION_REJECTED"`` -- this test's
    exact-boundary assertion kills it.
    """
    reference = mod.STAGE1_INTERNAL_DROP_REF
    result = mod.stage1_outcome((reference, 0.99), reference, eligible_fraction=0.9)
    assert result == "DEFLATION_SUPPORTED"
