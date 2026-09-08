"""Tests for the I-003 Stage 0 Δ = T − S decomposition (design-final.md §1/§3).

Encoder-independent (Test Plan): every fixture below is a hand-built unit
vector (via a small angle helper, mirroring ``test_sparsify.py``'s stub
convention) or a hand-picked raw score tuple -- never a real embedding.
:func:`_diag.embed_rarity` (the frozen apparatus) is called directly for AC
003-1/003-2/003-3 rather than hardcoding its output, per design-final.md §7's
"期待値をハードコードしない" discipline.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scripts import paper01_scope_condition as mod

from erre_sandbox.evidence.es4_actuator.battery import AdversarialItem


def _angle_vec(deg: float) -> np.ndarray:
    """A 2D unit vector at ``deg`` degrees from the positive x-axis."""
    rad = math.radians(deg)
    return np.array([math.cos(rad), math.sin(rad)])


def _random_unit(rng: np.random.Generator, dim: int) -> np.ndarray:
    raw = rng.normal(size=dim)
    return raw / np.linalg.norm(raw)


# --- AC 003-1 (fidelity: matches embed_rarity, max-agg) ---------------------


def test_delta_matches_embed_rarity_max_agg() -> None:
    """``Δ = T - S`` for max-agg matches the actual ``_diag.embed_rarity`` output.

    3 anchors (0/30/85 deg); 4 items straddling the ``REF_DEDUP`` boundary
    against the two close anchors, all landing above it (all "engaged"), 2
    good / 2 common. Expected per-class means are computed independently in
    this test from the same raw ``T``/``S`` arrays ``split_delta`` receives
    -- not a separate hardcoded number -- so this pins the algebra, not a
    restatement of the implementation.
    """
    ref = np.stack([_angle_vec(0.0), _angle_vec(30.0), _angle_vec(85.0)])
    items = [
        (_angle_vec(2.0), 1),  # good
        (_angle_vec(15.0), 1),  # good
        (_angle_vec(33.0), 0),  # common
        (_angle_vec(90.0), 0),  # common
    ]
    labels = tuple(lb for _, lb in items)

    scores_full = tuple(
        mod._diag.embed_rarity(vec, ref, leave_anchor_out=False, agg="max")
        for vec, _ in items
    )
    scores_lao = tuple(
        mod._diag.embed_rarity(vec, ref, leave_anchor_out=True, agg="max")
        for vec, _ in items
    )
    max_sim_full = tuple(1.0 - s for s in scores_full)
    assert all(s >= mod._c.REF_DEDUP for s in max_sim_full), (
        "fixture must land every item above REF_DEDUP (all engaged) -- "
        "otherwise this test would silently exercise the engaged filter "
        "instead of the T-S algebra AC 003-1 targets"
    )

    result = mod.split_delta(
        scores_full,
        scores_lao,
        labels,
        max_sim_full,
        source="stub_internal",
        candidate="X0",
        rho=0.5,
    )

    t_vals = [1.0 - s for s in scores_full]
    s_vals = [1.0 - s for s in scores_lao]
    delta_vals = [t - s for t, s in zip(t_vals, s_vals, strict=True)]
    good_idx = [i for i, lb in enumerate(labels) if lb == 1]
    common_idx = [i for i, lb in enumerate(labels) if lb == 0]

    def _mean(vals: list[float], idx: list[int]) -> float:
        return sum(vals[i] for i in idx) / len(idx)

    assert result.source == "stub_internal"
    assert result.candidate == "X0"
    assert result.rho == pytest.approx(0.5)
    assert result.n_good == len(good_idx)
    assert result.n_common == len(common_idx)
    assert result.mean_t_good == pytest.approx(_mean(t_vals, good_idx), abs=1e-12)
    assert result.mean_t_common == pytest.approx(_mean(t_vals, common_idx), abs=1e-12)
    assert result.mean_s_good == pytest.approx(_mean(s_vals, good_idx), abs=1e-12)
    assert result.mean_s_common == pytest.approx(_mean(s_vals, common_idx), abs=1e-12)
    assert result.mean_delta_good == pytest.approx(
        _mean(delta_vals, good_idx), abs=1e-12
    )
    assert result.mean_delta_common == pytest.approx(
        _mean(delta_vals, common_idx), abs=1e-12
    )
    # Δ = T - S holds at the per-class-mean level too (linear -> exact).
    assert result.mean_delta_good == pytest.approx(
        result.mean_t_good - result.mean_s_good, abs=1e-12
    )
    assert result.mean_delta_common == pytest.approx(
        result.mean_t_common - result.mean_s_common, abs=1e-12
    )


def test_delta_is_t_minus_s_not_s_minus_t() -> None:
    """The subtraction direction is ``T - S``, never ``S - T`` (AC 003-1's
    sign, isolated with a single item so a flipped subtraction is unmissable:
    ``T=1.0``, ``S=0.5`` gives ``+0.5``, a flip would give ``-0.5``.
    """
    result = mod.split_delta(
        (0.0,),
        (0.5,),
        (1,),
        (1.0,),
        source="stub",
        candidate="X0",
        rho=0.0,
    )
    assert result.mean_t_good == pytest.approx(1.0)
    assert result.mean_s_good == pytest.approx(0.5)
    assert result.mean_delta_good == pytest.approx(0.5)


# --- AC 003-2 (empty-survivor semantics, Codex MEDIUM-2) --------------------


def test_empty_survivor_gives_full_coverage() -> None:
    """LAO leaving zero survivors -> frozen ``embed_rarity`` returns ``0.0``
    -> ``S = 1 - 0.0 = 1.0`` ("fully covered"), read straight through from
    the actual frozen call, not a hardcoded ``1.0``.
    """
    ref = np.stack([_angle_vec(0.0)])  # single anchor
    vec = _angle_vec(0.0)  # exact duplicate of the only anchor
    rarity_full = mod._diag.embed_rarity(vec, ref, leave_anchor_out=False, agg="max")
    rarity_lao = mod._diag.embed_rarity(vec, ref, leave_anchor_out=True, agg="max")
    assert rarity_lao == 0.0  # frozen semantics: empty survivor set -> 0.0

    result = mod.split_delta(
        (rarity_full,),
        (rarity_lao,),
        (1,),
        (1.0 - rarity_full,),
        source="stub",
        candidate="X0",
        rho=0.0,
    )
    assert result.mean_s_good == pytest.approx(1.0, abs=1e-12)
    assert result.mean_t_good == pytest.approx(1.0, abs=1e-12)  # exact dup -> T=1.0
    assert result.mean_delta_good == pytest.approx(0.0, abs=1e-12)
    # no common items at all -- fail-open default, never a crash
    assert result.n_common == 0
    assert result.mean_t_common == 0.0
    assert result.mean_s_common == 0.0
    assert result.mean_delta_common == 0.0


# --- AC 003-3 (Δ(X2) ≡ Δ(X0), length term cancels) ---------------------------


def test_length_control_cancels_in_delta() -> None:
    """``_diag._length_controlled`` (X2) subtracts the *same* length term
    from both the full and LAO rarity of one item, so it cancels exactly out
    of ``Δ = rarity_LAO - rarity_full`` (DA-SC-9) even though the individual
    ``T``/``S`` values themselves differ from X0's.
    """
    anchors = ["anchor short", "an anchor of noticeably greater length"]
    items_text = [
        ("short good", "good"),
        ("a somewhat longer good text item here", "good"),
        ("common", "common_use_only"),
        ("a rather much longer common text item indeed", "common_use_only"),
    ]
    obj = "obj"
    rng = np.random.default_rng(mod.SEED)
    vmap = {t: _random_unit(rng, 6) for t in anchors + [t for t, _ in items_text]}

    gold_items = [
        AdversarialItem(
            text=text,
            object=obj,
            label="appropriate" if category == "good" else "inappropriate",
            category=category,
        )
        for text, category in items_text
    ]

    x0 = mod._g1.make_embed_candidate("X0", "base", vmap, {obj: anchors}, agg="max")
    x2 = mod._diag._length_controlled(x0, gold_items)

    scores_full_x0 = tuple(
        x0.rarity(obj, text, leave_anchor_out=False) for text, _ in items_text
    )
    scores_lao_x0 = tuple(
        x0.rarity(obj, text, leave_anchor_out=True) for text, _ in items_text
    )
    scores_full_x2 = tuple(
        x2.rarity(obj, text, leave_anchor_out=False) for text, _ in items_text
    )
    scores_lao_x2 = tuple(
        x2.rarity(obj, text, leave_anchor_out=True) for text, _ in items_text
    )

    delta_x0 = tuple(
        lao - full for full, lao in zip(scores_full_x0, scores_lao_x0, strict=True)
    )
    delta_x2 = tuple(
        lao - full for full, lao in zip(scores_full_x2, scores_lao_x2, strict=True)
    )
    for d0, d2 in zip(delta_x0, delta_x2, strict=True):
        assert d2 == pytest.approx(d0, abs=1e-9)

    # Not vacuous: the individual (non-decomposed) scores really do differ.
    assert any(
        abs(f0 - f2) > 1e-9
        for f0, f2 in zip(scores_full_x0, scores_full_x2, strict=True)
    )

    # X2 (like X1) is never accepted by split_delta -- T/S cannot be
    # recovered individually even though Delta is identical to X0's.
    with pytest.raises(ValueError, match="X2"):
        mod.split_delta(
            scores_full_x2,
            scores_lao_x2,
            (1, 1, 0, 0),
            (0.95, 0.95, 0.95, 0.95),
            source="stub",
            candidate="X2",
            rho=0.0,
        )


# --- AC 003-4 (X1 mean-agg rejected) -----------------------------------------


def test_mean_agg_candidate_is_rejected() -> None:
    """X1 (and X2) are not members of ``DELTA_TS_CANDIDATES`` and are
    explicitly rejected by ``split_delta`` (HIGH-2 / DA-SC-9), never
    silently scored.
    """
    assert "X1" not in mod.DELTA_TS_CANDIDATES
    assert "X2" not in mod.DELTA_TS_CANDIDATES
    for bad_candidate in ("X1", "X2"):
        with pytest.raises(ValueError, match=bad_candidate):
            mod.split_delta(
                (0.1, 0.2),
                (0.3, 0.4),
                (1, 0),
                (0.95, 0.92),
                source="stub",
                candidate=bad_candidate,
                rho=0.0,
            )


# --- AC 003-5 (engaged predicate == potency_and_near_dup's item set) --------


def test_engaged_predicate_matches_potency() -> None:
    """The engaged item set (used to filter T/S/Δ means) selects exactly the
    same items :func:`_g1.potency_and_near_dup` internally treats as
    near-dup -- cross-checked via its *aggregate* per-class rate (the only
    thing it exposes), not a reimplemented mask.
    """
    max_sim_full = (0.95, 0.5, 0.92, 0.3, 0.89, 0.99)
    labels = (1, 1, 0, 0, 1, 0)
    scores_full = tuple(1.0 - s for s in max_sim_full)
    scores_lao = tuple(max(0.0, s - 0.1) for s in scores_full)

    result = mod.split_delta(
        scores_full,
        scores_lao,
        labels,
        max_sim_full,
        source="stub",
        candidate="X0",
        rho=0.0,
    )

    expected_engaged_idx = [
        i for i, s in enumerate(max_sim_full) if s >= mod._c.REF_DEDUP
    ]
    expected_n_good = sum(1 for i in expected_engaged_idx if labels[i] == 1)
    expected_n_common = sum(1 for i in expected_engaged_idx if labels[i] == 0)
    n_good_total = sum(1 for lb in labels if lb == 1)
    n_common_total = sum(1 for lb in labels if lb == 0)

    # Non-tautological: filtering actually drops some items of each class.
    assert 0 < expected_n_good < n_good_total
    assert 0 < expected_n_common < n_common_total

    assert result.n_good == expected_n_good
    assert result.n_common == expected_n_common

    potency = mod._g1.potency_and_near_dup(list(max_sim_full), list(labels))
    assert potency.near_dup_good == pytest.approx(expected_n_good / n_good_total)
    assert potency.near_dup_common == pytest.approx(expected_n_common / n_common_total)


# --- AC 003-6 (label-stratified means, one-sided input safety) -------------


def test_label_stratified_means() -> None:
    """One-sided engaged input (only ``good``) does not break, defaulting
    the empty class to ``0.0``; a mixed-class fixture's good/common means
    are consistent with the plain overall mean over all engaged items
    (the "全体平均と整合" requirement).
    """
    only_good = mod.split_delta(
        (0.05, 0.02),
        (0.5, 0.6),
        (1, 1),
        (0.95, 0.98),
        source="stub",
        candidate="X0",
        rho=0.0,
    )
    assert only_good.n_common == 0
    assert only_good.mean_t_common == 0.0
    assert only_good.mean_s_common == 0.0
    assert only_good.mean_delta_common == 0.0
    assert only_good.s_common_minus_s_good == pytest.approx(
        -only_good.mean_s_good, abs=1e-12
    )

    scores_full = (0.05, 0.02, 0.10, 0.20, 0.15)
    labels = (1, 1, 0, 0, 0)
    max_sim_full = (0.95, 0.98, 0.93, 0.91, 0.99)  # all engaged
    mixed = mod.split_delta(
        scores_full,
        (0.50, 0.60, 0.40, 0.55, 0.30),
        labels,
        max_sim_full,
        source="stub",
        candidate="X0",
        rho=0.0,
    )
    assert mixed.n_good == 2
    assert mixed.n_common == 3

    weighted_overall_t = (
        mixed.n_good * mixed.mean_t_good + mixed.n_common * mixed.mean_t_common
    ) / (mixed.n_good + mixed.n_common)
    direct_overall_t = sum(1.0 - s for s in scores_full) / len(scores_full)
    assert weighted_overall_t == pytest.approx(direct_overall_t, abs=1e-12)


# --- AC 003-7 (S_common - S_good matches a hand computation) ---------------


def test_s_common_minus_s_good() -> None:
    scores_full = (0.05, 0.02, 0.10, 0.20, 0.15)
    scores_lao = (0.50, 0.60, 0.40, 0.55, 0.30)
    labels = (1, 1, 0, 0, 0)
    max_sim_full = (0.95, 0.98, 0.93, 0.91, 0.99)  # all engaged

    result = mod.split_delta(
        scores_full,
        scores_lao,
        labels,
        max_sim_full,
        source="stub",
        candidate="X0",
        rho=0.0,
    )

    s_good = [1.0 - scores_lao[i] for i in range(5) if labels[i] == 1]
    s_common = [1.0 - scores_lao[i] for i in range(5) if labels[i] == 0]
    expected = (sum(s_common) / len(s_common)) - (sum(s_good) / len(s_good))
    assert result.s_common_minus_s_good == pytest.approx(expected, abs=1e-12)


# --- AC 003-8 (delta_attribution: T / S / both all reachable) --------------


def test_delta_attribution_all_branches_reachable() -> None:
    """All three outputs reachable from disjoint fixtures (non-tautological),
    with the ``1.0 ± 0.1`` band's both boundary points and their immediate
    outside neighbours pinned explicitly.
    """
    assert mod.delta_attribution(1.0, 0.0, 0.0, 0.0) == "T"
    assert mod.delta_attribution(0.0, 1.0, 0.0, 0.0) == "S"
    assert mod.delta_attribution(1.0, 0.0, 0.0, 1.0) == "both"  # ratio 1.0

    assert mod.delta_attribution(0.9, 0.0, 0.0, 1.0) == "both"  # ratio 0.9 (lo)
    assert mod.delta_attribution(1.1, 0.0, 0.0, 1.0) == "both"  # ratio 1.1 (hi)
    assert mod.delta_attribution(0.89, 0.0, 0.0, 1.0) == "S"  # just below lo
    assert mod.delta_attribution(1.11, 0.0, 0.0, 1.0) == "T"  # just above hi

    assert mod.delta_attribution(0.0, 0.0, 0.0, 0.0) == "both"  # degenerate 0/0


# --- AC 003-9 (delta_is_material boundary) -----------------------------------


def test_delta_material_boundary() -> None:
    eps = mod.DELTA_MATERIAL_EPS
    assert mod.delta_is_material(0.0, eps) is True
    assert mod.delta_is_material(0.0, eps - 1e-9) is False
    assert mod.delta_is_material(0.0, eps + 1e-9) is True
    assert mod.delta_is_material(0.005, 0.005) is False
