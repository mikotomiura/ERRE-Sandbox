"""Tests for the I-006 τ* calibration (design-final.md §2.1/§2.3/§2.4).

Encoder-independent (Test Plan): :func:`~scripts.paper01_scope_condition.
internal_rho_and_k` / :func:`~scripts.paper01_scope_condition.calibrate_tau`
/ :func:`~scripts.paper01_scope_condition.adjacent_tau_indices` are pure
aggregation over hand-built :class:`~scripts.paper01_scope_condition.
InternalReference` rows and plain ``tuple[float, ...]`` inputs -- no
encoder, no I/O. :func:`~scripts.paper01_scope_condition.
internal_reference_per_object`'s ``mpnet``-dependent half is exercised via
monkeypatched stand-ins for ``_g1._c4_fidelity_context`` /
``_g1._c0_fidelity_context`` (never a real sentence-transformers load --
that is reserved for the eval-gated fidelity pin in ``test_cells.py``), per
this issue's Test Plan: "spy で生の呼び出し引数を見る".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_scope_condition as mod

if TYPE_CHECKING:
    from collections.abc import Sequence


def _unit(vec: Sequence[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=float)
    return arr / np.linalg.norm(arr)


# --- AC 006-3 / 006-4 (rho_int basis: raw C4-curated primary, C0-dedup secondary)


def test_rho_int_uses_raw_curated_not_deduped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 006-3: ``rho_int_primary`` is computed over the *raw* C4 curated
    reference set -- never a deduped subset.

    ``_g1._c4_fidelity_context`` is monkeypatched to return a curated set
    with two near-duplicate texts (cosine ~0.999, well above ``REF_DEDUP``
    = 0.90) alongside one distinct text. If :func:`internal_reference_per_
    object` deduped the C4 side before computing ``rho``, the reported
    ``rho_primary_c4`` would equal the redundancy of the *2*-point deduped
    set; instead it must equal the redundancy of the *raw* 3-point set --
    proven by comparing against a direct :func:`reference_redundancy` call
    over the same three embeddings (never a hardcoded number), and by a
    spy confirming the embeddings array :func:`reference_redundancy`
    receives has length 3, never 2.
    """
    near_a = _unit([1.0, 0.0, 0.0])
    near_b = _unit([0.999, 0.02, 0.0])
    distinct = _unit([0.0, 1.0, 0.0])
    vmap_c4 = {"dup-a": near_a, "dup-b": near_b, "distinct": distinct}
    curated = {"brick": ["dup-a", "dup-b", "distinct"]}

    vmap_c0 = {"c0-only": _unit([0.0, 0.0, 1.0])}
    full_ref_texts = {"brick": ["c0-only"]}

    sentinel_mpnet = object()
    calls: list[tuple[object, ...]] = []

    def _fake_c4(
        mpnet: object,
    ) -> tuple[None, dict[str, np.ndarray], dict[str, list[str]]]:
        calls.append(("c4", mpnet))
        return None, vmap_c4, curated

    def _fake_c0(
        mpnet: object, run_dir: object
    ) -> tuple[None, dict[str, np.ndarray], dict[str, list[str]]]:
        calls.append(("c0", mpnet, run_dir))
        return None, vmap_c0, full_ref_texts

    monkeypatch.setattr(mod._g1, "_c4_fidelity_context", _fake_c4)
    monkeypatch.setattr(mod._g1, "_c0_fidelity_context", _fake_c0)

    rho_calls: list[np.ndarray] = []
    real_rho = mod.reference_redundancy

    def _rho_spy(embeddings: np.ndarray) -> float:
        rho_calls.append(embeddings)
        return real_rho(embeddings)

    monkeypatch.setattr(mod, "reference_redundancy", _rho_spy)

    refs = mod.internal_reference_per_object(sentinel_mpnet, run_dir=None)

    assert calls[0] == ("c4", sentinel_mpnet)
    assert calls[1][0] == "c0"
    assert calls[1][1] is sentinel_mpnet

    brick = next(r for r in refs if r.object_id == "brick")
    expected_raw_rho = real_rho(np.asarray([near_a, near_b, distinct]))
    deduped_rho = real_rho(np.asarray([near_a, distinct]))
    assert brick.rho_primary_c4 == expected_raw_rho
    assert brick.rho_primary_c4 != deduped_rho
    assert brick.n_refs_primary_c4 == 3

    c4_call_lengths = sorted(len(c) for c in rho_calls if len(c) > 0)
    assert 3 in c4_call_lengths, "reference_redundancy must see all 3 raw C4 texts"


def test_rho_int_reports_both_bases(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 006-4: ``rho_int_secondary`` (C0-dedup) is *also* reported,
    alongside ``rho_int_primary`` (C4-raw) -- distinct values from distinct
    reference sets, never one silently mirroring the other.
    """
    vmap_c4 = {
        "c4-a": _unit([1.0, 0.0]),
        "c4-b": _unit([0.0, 1.0]),
    }
    curated = {"brick": ["c4-a", "c4-b"]}

    vmap_c0 = {
        "c0-a": _unit([1.0, 0.0]),
        "c0-b": _unit([0.9, 0.1]),
        "c0-c": _unit([0.0, 1.0]),
    }
    full_ref_texts = {"brick": ["c0-a", "c0-b", "c0-c"]}

    def _fake_c4(
        _mpnet: object,
    ) -> tuple[None, dict[str, np.ndarray], dict[str, list[str]]]:
        return None, vmap_c4, curated

    def _fake_c0(
        _mpnet: object, _run_dir: object
    ) -> tuple[None, dict[str, np.ndarray], dict[str, list[str]]]:
        return None, vmap_c0, full_ref_texts

    monkeypatch.setattr(mod._g1, "_c4_fidelity_context", _fake_c4)
    monkeypatch.setattr(mod._g1, "_c0_fidelity_context", _fake_c0)

    refs = mod.internal_reference_per_object(object(), run_dir=None)
    brick = next(r for r in refs if r.object_id == "brick")

    assert brick.rho_primary_c4 == mod.reference_redundancy(
        np.asarray([vmap_c4["c4-a"], vmap_c4["c4-b"]])
    )
    assert brick.rho_secondary_c0 == mod.reference_redundancy(
        np.asarray([vmap_c0["c0-a"], vmap_c0["c0-b"], vmap_c0["c0-c"]])
    )
    assert brick.rho_primary_c4 != brick.rho_secondary_c0
    assert brick.n_refs_secondary_c0 == 3

    rho_primary, rho_secondary, k_star = mod.internal_rho_and_k(refs)
    assert rho_primary == pytest.approx(brick.rho_primary_c4)
    assert rho_secondary == pytest.approx(brick.rho_secondary_c0)
    assert k_star == brick.n_refs_primary_c4


# --- AC 006-5 (tau* tie-break to the larger tau) ----------------------------


def test_tau_tie_breaks_high() -> None:
    """AC 006-5: on an exact tie between two grid points' ``|rho_ext -
    rho_int|`` gap, ``tau_star`` resolves to the **larger** τ.

    Two adjacent grid points (0.85 and 0.80) are constructed to be exactly
    equidistant from ``rho_int_primary``; every other grid point is placed
    far away so it cannot win.
    """
    rho_int = 0.625
    rho_ext = []
    for tau in mod.TAU_GRID:
        if tau == 0.85:
            rho_ext.append(0.625 + 0.025)  # gap 0.025
        elif tau == 0.80:
            rho_ext.append(0.625 - 0.025)  # gap 0.025, tied with 0.85
        else:
            rho_ext.append(0.625 + 10.0)  # far away, cannot win
    tc = mod.calibrate_tau(tuple(rho_ext), rho_int, k_star=12)
    assert tc.tau_star == 0.85
    assert tc.k_star == 12
    assert tc.rho_int_primary == rho_int
    assert tc.rho_by_tau == tuple(rho_ext)


def test_calibrate_tau_rejects_misaligned_length() -> None:
    """``rho_ext_by_tau`` must be index-aligned with :data:`TAU_GRID`;
    a mismatched length raises rather than silently truncating/padding."""
    with pytest.raises(ValueError, match="index-aligned"):
        mod.calibrate_tau((0.5, 0.4), 0.3, k_star=10)


# --- AC 006-6 (F1: rho unreachable even at the ladder's low end) -----------


def test_unreachable_rho_is_f1() -> None:
    """AC 006-6: when ``rho_ext(tau)`` never drops as low as ``rho_int``
    even at :data:`TAU_GRID`'s sparsest entry (index -1), the resulting
    :class:`~scripts.paper01_scope_condition.TauCalibration` feeds
    :func:`~scripts.paper01_scope_condition.decide_scope` into F1 --
    exercised through the *real* :func:`calibrate_tau` output, not a
    hand-typed ``rho_by_tau``.
    """
    rho_int = 0.30
    rho_ext = tuple(0.90 - 0.03 * i for i in range(len(mod.TAU_GRID)))
    assert rho_ext[-1] > rho_int, "fixture sanity: never reaches rho_int"

    tc = mod.calibrate_tau(rho_ext, rho_int, k_star=10)
    assert tc.rho_by_tau[-1] > tc.rho_int_primary

    objects = ("brick", "paperclip")
    weights = {obj: 1.0 / len(objects) for obj in objects}

    def _cell(verdict: str, tau: float, k_target: int) -> mod.CellResult:
        return mod.CellResult(
            tau=tau,
            k_target=k_target,
            k_effective=k_target,
            n_leaders=k_target,
            corpus="ocsai",
            split_scheme="SPLIT-BLOCK",
            verdict=verdict,
            active_objects=objects,
            object_weights=weights,
        )

    split_cells = mod.SplitCells(
        arm_a=_cell("PASS", 0.90, 30),
        arm_s=_cell("NO_VALID_SCORER", tc.tau_star, 10),
        tau_calibration=tc,
    )
    cells = {
        "SPLIT-BLOCK": split_cells,
        "SPLIT-PARITY": split_cells,
    }
    cambridge = _cell("NO_VALID_SCORER", tc.tau_star, 10)
    stage1 = mod.Stage1Result(
        candidate="X0",
        n_replicates=500,
        drop_p5=0.10,
        drop_p95=0.30,
        median_drop=0.20,
        eligible_fraction=0.9,
        deflation_supported=False,
        stage1_outcome="DEFLATION_REJECTED",
        drop_p5_eligible=0.11,
        drop_p95_eligible=0.29,
        median_drop_eligible=0.19,
        drop_p5_strat=0.09,
        drop_p95_strat=0.31,
        median_drop_strat=0.21,
        n_objects_pool_short=0,
        pool_short_objects=(),
        median_draw_drop=0.20,
        median_draw_outcome="DEFLATION_SUPPORTED",
    )

    stage0 = (
        mod.DeltaDecomposition(
            source="internal_c4",
            candidate="C4",
            n_good=5,
            n_common=5,
            mean_t_good=0.60,
            mean_t_common=0.55,
            mean_s_good=0.30,
            mean_s_common=0.25,
            mean_delta_good=0.30,
            mean_delta_common=0.30,
            s_common_minus_s_good=-0.05,
            rho=rho_int,
        ),
        mod.DeltaDecomposition(
            source="external_ocsai_arm_a",
            candidate="X0",
            n_good=5,
            n_common=5,
            mean_t_good=0.60,
            mean_t_common=0.55,
            mean_s_good=0.55,
            mean_s_common=0.50,
            mean_delta_good=0.05,
            mean_delta_common=0.05,
            s_common_minus_s_good=-0.05,
            rho=rho_ext[0],
        ),
    )
    assert abs(0.30 - 0.05) >= mod.DELTA_MATERIAL_EPS, (
        "fixture sanity: F4 must not fire"
    )

    verdict = mod.decide_scope(stage0, stage1, cells, cambridge=cambridge)
    assert verdict.fail_reason == "F1"
    assert verdict.verdict == "DO_NOT_WRITE"


# --- AC 006-7 (adjacent-tau identification, grid edges) --------------------


def test_adjacent_tau_at_grid_edges() -> None:
    """AC 006-7: the sole neighbour is reported at either grid edge (never
    dropped, never a nonexistent out-of-range index); two neighbours in
    the interior."""
    last = len(mod.TAU_GRID) - 1
    assert mod.adjacent_tau_indices(0) == (1,)
    assert mod.adjacent_tau_indices(last) == (last - 1,)
    for i in range(1, last):
        assert mod.adjacent_tau_indices(i) == (i - 1, i + 1)

    # every returned index is a valid TAU_GRID index, for every position.
    for i in range(len(mod.TAU_GRID)):
        for neighbour in mod.adjacent_tau_indices(i):
            assert 0 <= neighbour < len(mod.TAU_GRID)
            assert neighbour != i


# --- internal_rho_and_k edge cases ------------------------------------------


def test_internal_rho_and_k_empty_is_fail_closed() -> None:
    """An empty ``references`` tuple reports ``(0.0, 0.0, 0)`` -- fail-
    closed, mirroring :func:`_stage0_t_s_delta`'s convention for a missing
    row, never raising."""
    assert mod.internal_rho_and_k(()) == (0.0, 0.0, 0)


def test_internal_rho_and_k_k_star_is_median_not_mean() -> None:
    """``k_star`` is the median of ``n_refs_primary_c4``, not the mean --
    an odd-length, non-symmetric multiset distinguishes the two."""
    refs = (
        mod.InternalReference("a", 0.5, 0.5, 5, 5),
        mod.InternalReference("b", 0.5, 0.5, 10, 10),
        mod.InternalReference("c", 0.5, 0.5, 100, 100),
    )
    _rho_p, _rho_s, k_star = mod.internal_rho_and_k(refs)
    assert k_star == 10  # median, not mean (== 38.33)
