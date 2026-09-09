"""Tests for the I-006 cell pipeline (design-final.md §3 Stage 2).

Encoder-independent tests (Test Plan): :func:`~scripts.paper01_scope_
condition.build_cell` / :func:`~scripts.paper01_scope_condition.score_cell`
/ :func:`~scripts.paper01_scope_condition.common_active_objects` /
:func:`~scripts.paper01_scope_condition.run_scope` are exercised with
hand-built fixtures and monkeypatched spies -- "spy で生の呼び出し引数を見る"
(never inferring wiring from an aggregate AUC/collapsed number).

**Fidelity pin (b)** (AC 006-1) is the one real-encoder, real-network
exception: it needs the actual Ocsai corpus + four sentence-transformer
encoders to reproduce G1's committed ARM-A numbers exactly. Per this
issue's own Test Plan ("CI では skip、ローカル run.sh で必ず走らせる"), it is
triple-gated exactly like ``tests/test_training/test_qc_detectors_real.py``
(``pytest.importorskip`` + ``pytest.mark.eval`` +
``ERRE_RUN_REAL_MPNET_TESTS=1`` opt-in) so it never runs in this issue's own
CI-parity verify pass -- only when explicitly opted into (I-007's run.sh).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as g1
from scripts import paper01_scope_condition as mod

if TYPE_CHECKING:
    from pathlib import Path

SEED = mod.SEED


def _unit(vec: list[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=float)
    return arr / np.linalg.norm(arr)


def _row(row_id: int, obj: str, text: str, category: str) -> g1.CambridgeRow:
    return g1.CambridgeRow(row_id=row_id, object=obj, text=text, category=category)


class _FakeCtx:
    """Minimal :class:`~scripts.paper01_external_audit.ObjectSplitContext`
    stand-in exposing only what :func:`build_cell` reads (``object_key`` /
    ``common_pool``)."""

    def __init__(
        self, object_key: str, common_pool: tuple[g1.CambridgeRow, ...]
    ) -> None:
        self.object_key = object_key
        self.common_pool = common_pool


# --- AC 006-2 (pipeline order: dedupe(uncapped) -> cap -> draw, spy) -------


def test_cell_pipeline_order_is_dedupe_then_cap_then_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 006-2: :func:`build_cell` calls
    :func:`~scripts.paper01_scope_condition.leader_cluster_indices` with
    ``cap=len(pool)`` (**uncapped** -- never the cell's own ``cap``
    argument), and only *then* draws ``k_eff = min(cap, n_leaders)`` items
    via :func:`~scripts.paper01_external_audit.anchor_draw_indices` --
    never the reverse order. A spy on both calls records call order and
    the actual arguments received (never inferred from an aggregate
    number, per this issue's Test Plan).
    """
    rows = tuple(_row(i, "brick", f"t{i}", "common_use_only") for i in range(7))
    rng = np.random.default_rng(SEED)
    pool_embeddings = {r.text: _unit(rng.normal(size=6).tolist()) for r in rows}

    call_log: list[tuple[str, dict[str, object]]] = []
    real_leader = mod.leader_cluster_indices
    real_anchor_draw = g1.anchor_draw_indices

    def _leader_spy(embeddings: np.ndarray, *, cap: int, radius: float) -> list[int]:
        call_log.append(("leader_cluster_indices", {"cap": cap, "radius": radius}))
        return real_leader(embeddings, cap=cap, radius=radius)

    def _draw_spy(pool_size: int, k: int, *, seed: int, draw_index: int) -> np.ndarray:
        call_log.append(("anchor_draw_indices", {"pool_size": pool_size, "k": k}))
        return real_anchor_draw(pool_size, k, seed=seed, draw_index=draw_index)

    monkeypatch.setattr(mod, "leader_cluster_indices", _leader_spy)
    monkeypatch.setattr(mod._g1, "anchor_draw_indices", _draw_spy)

    ctx = _FakeCtx("brick", rows)
    cell = mod.build_cell(
        ctx, pool_embeddings, tau=0.90, cap=3, corpus="ocsai", scheme="SPLIT-BLOCK"
    )

    leader_calls = [c for c in call_log if c[0] == "leader_cluster_indices"]
    draw_calls = [c for c in call_log if c[0] == "anchor_draw_indices"]

    assert len(leader_calls) == 1, "leader clustering must run exactly once per cell"
    assert leader_calls[0][1]["cap"] == 7, (
        "leader_cluster_indices must be called uncapped (cap=len(pool)=7), "
        "never with this cell's own cap=3"
    )
    assert leader_calls[0][1]["radius"] == 0.90

    assert draw_calls, "expected anchor_draw_indices to be called"
    for _name, kwargs in draw_calls:
        assert kwargs["k"] == cell.k_effective == min(3, cell.n_leaders)
        assert kwargs["pool_size"] == cell.n_leaders

    # order: every leader_cluster_indices call precedes every draw call.
    first_draw_pos = next(
        i for i, c in enumerate(call_log) if c[0] == "anchor_draw_indices"
    )
    last_leader_pos = max(
        i for i, c in enumerate(call_log) if c[0] == "leader_cluster_indices"
    )
    assert last_leader_pos < first_draw_pos, "dedupe must run before any draw"

    assert len(cell.draw_texts_by_draw) == g1.ANCHOR_DRAWS
    assert all(len(draw) == cell.k_effective for draw in cell.draw_texts_by_draw)


def test_build_cell_empty_pool_never_raises() -> None:
    """An object with an empty ``common_pool`` reports a degenerate
    :class:`CellAnchors` (``ANCHOR_DRAWS`` empty draws), never raises."""
    ctx = _FakeCtx("brick", ())
    cell = mod.build_cell(
        ctx, {}, tau=0.90, cap=30, corpus="ocsai", scheme="SPLIT-BLOCK"
    )
    assert cell.n_pool == 0
    assert cell.n_leaders == 0
    assert cell.k_effective == 0
    assert len(cell.draw_texts_by_draw) == g1.ANCHOR_DRAWS
    assert all(draw == () for draw in cell.draw_texts_by_draw)


def test_active_objects_for_cell_boundary_at_n_r_min() -> None:
    """``n_leaders == N_R_MIN`` exactly is *active* (``>=``, never ``>``) --
    mirrors :attr:`~scripts.paper01_external_audit.ObjectSplitContext.
    dropped`'s own ``len(dedup_common) < N_R_MIN`` boundary (the negation
    of ``< N_R_MIN`` is ``>= N_R_MIN``, never ``> N_R_MIN``)."""
    cells_by_object = {
        "at_floor": _cell_anchors("at_floor", n_leaders=mod._c.N_R_MIN),
        "below_floor": _cell_anchors("below_floor", n_leaders=mod._c.N_R_MIN - 1),
        "above_floor": _cell_anchors("above_floor", n_leaders=mod._c.N_R_MIN + 1),
    }
    active = mod.active_objects_for_cell(cells_by_object)
    assert active == ("above_floor", "at_floor")
    assert "below_floor" not in active


# --- AC 006-8 (4-cell common-active intersection scored, spy) --------------


def _context_with_split1(
    object_key: str,
    *,
    n_good: int = 3,
    n_common: int = 3,
) -> g1.ObjectSplitContext:
    good = tuple(
        _row(i, object_key, f"{object_key}-good-{i}", "good") for i in range(n_good)
    )
    common = tuple(
        _row(100 + i, object_key, f"{object_key}-common-{i}", "common_use_only")
        for i in range(n_common)
    )
    split1 = good + common
    return g1.ObjectSplitContext(
        object_key=object_key,
        split0=(),
        split1=split1,
        common_pool=common,
        good_pool=good,
        dedup_common_pool=common,
        dedup_good_pool=good,
        dropped=False,
        idf={},
        default_idf=1.0,
    )


def _cell_anchors(object_key: str, *, n_leaders: int) -> mod.CellAnchors:
    draws = tuple(() for _ in range(g1.ANCHOR_DRAWS))
    return mod.CellAnchors(
        object_key=object_key,
        tau=0.90,
        k_target=30,
        k_effective=0,
        n_pool=n_leaders,
        n_leaders=n_leaders,
        draw_texts_by_draw=draws,
    )


def test_all_cells_score_the_intersection(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 006-8: :func:`score_cell` only ever scores the explicit
    ``active_objects`` it is given -- never widens back out to every key
    ``cells_by_object`` happens to carry. Spies on
    :func:`~scripts.paper01_external_audit.score_rows_for_draw`'s ``rows``
    argument (never inferred from ``decide_external``'s aggregate verdict,
    per this issue's Test Plan).
    """
    objects = ("brick", "paperclip", "bottle")
    contexts = {o: _context_with_split1(o) for o in objects}
    # cells_by_object carries all three objects; the caller only passes two
    # as the already-intersected active set (design-final.md §3 DA-SC-3).
    cells_by_object = {o: _cell_anchors(o, n_leaders=10) for o in objects}
    active_objects = ("brick", "paperclip")

    seen_object_sets: list[frozenset[str]] = []

    def _spy(
        rows: tuple[g1.CambridgeRow, ...],
        *,
        anchor_texts_by_object: dict[str, tuple[str, ...]],
        vmaps: dict[str, dict[str, np.ndarray]],
        idf_by_object: dict[str, tuple[dict[str, float], float]],
    ) -> dict[str, g1.DrawItems]:
        del vmaps, idf_by_object
        seen_object_sets.append(frozenset(r.object for r in rows))
        seen_object_sets.append(frozenset(anchor_texts_by_object))
        return {}

    monkeypatch.setattr(mod._g1, "score_rows_for_draw", _spy)

    result = mod.score_cell(
        cells_by_object,
        contexts,
        active_objects,
        {},
        tau=0.90,
        k_target=30,
        corpus="ocsai",
        scheme="SPLIT-BLOCK",
    )

    assert seen_object_sets, "expected score_rows_for_draw to be called"
    for seen in seen_object_sets:
        assert seen == frozenset(active_objects), (
            "score_cell must restrict scoring to the intersected "
            "active_objects, never cells_by_object's own (wider) key set"
        )
    assert result.active_objects == tuple(sorted(active_objects))
    assert "bottle" not in result.active_objects


# --- AC 006-9 (F2: object collapse via real active_objects_for_cell wiring)


def test_object_collapse_is_f2() -> None:
    """AC 006-9: when the 4-cell common-active intersection (via the real
    :func:`active_objects_for_cell` / :func:`common_active_objects` wiring
    -- never hand-typed) drops below half of ARM-A's own active set,
    :func:`decide_scope` reaches F2.
    """
    dense_objects = tuple(f"obj{i}" for i in range(8))
    # ARM-A (dense tau): every object clears N_R_MIN.
    arm_a_cells = {
        o: _cell_anchors(o, n_leaders=mod._c.N_R_MIN + 2) for o in dense_objects
    }
    # ARM-S (sparse tau) and the two mixed cells: only 2 of 8 objects
    # (well under half) still clear N_R_MIN after aggressive clustering.
    sparse_active = dense_objects[:2]
    arm_s_cells = {
        o: _cell_anchors(o, n_leaders=(mod._c.N_R_MIN + 1 if o in sparse_active else 1))
        for o in dense_objects
    }

    active_by_cell = {
        "arm_a": mod.active_objects_for_cell(arm_a_cells),
        "arm_s": mod.active_objects_for_cell(arm_s_cells),
        "mixed_1": mod.active_objects_for_cell(arm_s_cells),
        "mixed_2": mod.active_objects_for_cell(arm_a_cells),
    }
    intersection = mod.common_active_objects(active_by_cell)
    assert intersection == sorted(sparse_active)
    assert len(intersection) < len(dense_objects) * 0.5

    weights_arm_a = {o: 1.0 / len(dense_objects) for o in dense_objects}
    weights_arm_s = {o: 1.0 / len(intersection) for o in intersection}

    arm_a_result = mod.CellResult(
        tau=0.90,
        k_target=30,
        k_effective=30,
        n_leaders=mod._c.N_R_MIN + 2,
        corpus="ocsai",
        split_scheme="SPLIT-BLOCK",
        verdict="PASS",
        active_objects=dense_objects,
        object_weights=weights_arm_a,
    )
    arm_s_result = mod.CellResult(
        tau=0.5,
        k_target=10,
        k_effective=10,
        n_leaders=mod._c.N_R_MIN + 1,
        corpus="ocsai",
        split_scheme="SPLIT-BLOCK",
        verdict="NO_VALID_SCORER",
        active_objects=tuple(intersection),
        object_weights=weights_arm_s,
    )
    tau_cal = mod.TauCalibration(
        rho_int_primary=0.5,
        rho_by_tau=tuple(0.5 for _ in mod.TAU_GRID),
        tau_star=0.5,
        k_star=10,
        single_point_dependent=False,
    )
    split_cells = mod.SplitCells(
        arm_a=arm_a_result, arm_s=arm_s_result, tau_calibration=tau_cal
    )
    cells = {"SPLIT-BLOCK": split_cells, "SPLIT-PARITY": split_cells}
    cambridge = arm_s_result

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
            rho=0.5,
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
            rho=0.5,
        ),
    )

    verdict = mod.decide_scope(stage0, stage1, cells, cambridge=cambridge)
    assert verdict.fail_reason == "F2"
    assert verdict.verdict == "DO_NOT_WRITE"


# --- AC 006-10 (object_weights present per cell) ----------------------------


def test_object_weights_present_per_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 006-10: :func:`score_cell`'s returned :class:`CellResult` always
    carries a non-empty per-active-object ``object_weights`` mapping."""
    objects = ("brick", "paperclip")
    contexts = {o: _context_with_split1(o, n_good=4, n_common=2) for o in objects}
    cells_by_object = {o: _cell_anchors(o, n_leaders=10) for o in objects}

    monkeypatch.setattr(mod._g1, "score_rows_for_draw", lambda *_a, **_k: {})

    result = mod.score_cell(
        cells_by_object,
        contexts,
        objects,
        {},
        tau=0.90,
        k_target=30,
        corpus="ocsai",
        scheme="SPLIT-BLOCK",
    )
    assert set(result.object_weights) == set(objects)
    for obj in objects:
        assert isinstance(result.object_weights[obj], float)
    assert result.object_weights["brick"] == pytest.approx(
        result.object_weights["paperclip"]
    )


# --- AC 006-11 (scope.json shape) -------------------------------------------


def _minimal_split_cells(split_scheme: str) -> mod.SplitCells:
    weights = {"brick": 1.0}
    arm_a = mod.CellResult(
        tau=0.90,
        k_target=30,
        k_effective=30,
        n_leaders=30,
        corpus="ocsai",
        split_scheme=split_scheme,
        verdict="PASS",
        active_objects=("brick",),
        object_weights=weights,
    )
    arm_s = mod.CellResult(
        tau=0.5,
        k_target=10,
        k_effective=10,
        n_leaders=10,
        corpus="ocsai",
        split_scheme=split_scheme,
        verdict="NO_VALID_SCORER",
        active_objects=("brick",),
        object_weights=weights,
    )
    tau_cal = mod.TauCalibration(
        rho_int_primary=0.5,
        rho_by_tau=tuple(0.5 for _ in mod.TAU_GRID),
        tau_star=0.5,
        k_star=10,
        single_point_dependent=False,
    )
    return mod.SplitCells(arm_a=arm_a, arm_s=arm_s, tau_calibration=tau_cal)


def test_scope_json_shape(tmp_path: Path) -> None:
    """AC 006-11: ``results/scope.json`` (as written by :func:`run_scope`)
    contains Stage 0 / Stage 1 / Stage 2 and the final
    :class:`ScopeVerdict` -- all four, always.
    """
    stage0 = (
        mod.DeltaDecomposition(
            source="internal_c4",
            candidate="C4",
            n_good=5,
            n_common=5,
            mean_t_good=0.6,
            mean_t_common=0.55,
            mean_s_good=0.3,
            mean_s_common=0.25,
            mean_delta_good=0.3,
            mean_delta_common=0.3,
            s_common_minus_s_good=-0.05,
            rho=0.5,
        ),
    )
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
    cells = {
        "SPLIT-BLOCK": _minimal_split_cells("SPLIT-BLOCK"),
        "SPLIT-PARITY": _minimal_split_cells("SPLIT-PARITY"),
    }
    cambridge = cells["SPLIT-BLOCK"].arm_s
    internal_references = (
        mod.InternalReference(
            object_id="brick",
            rho_primary_c4=0.5,
            rho_secondary_c0=0.4,
            n_refs_primary_c4=10,
            n_refs_secondary_c0=8,
        ),
    )

    out_path = tmp_path / "scope.json"
    payload = mod.run_scope(
        stage0=stage0,
        stage1=stage1,
        cells=cells,
        cambridge=cambridge,
        internal_references=internal_references,
        out_path=out_path,
    )

    assert out_path.exists()
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk == payload

    for top_key in ("stage0", "stage1", "stage2", "verdict"):
        assert top_key in on_disk, f"missing top-level key {top_key!r}"

    assert isinstance(on_disk["stage0"], list)
    assert on_disk["stage0"][0]["candidate"] == "C4"

    assert on_disk["stage1"]["candidate"] == "X0"

    stage2 = on_disk["stage2"]
    assert set(stage2) == {"cells", "cambridge", "internal_references"}
    assert set(stage2["cells"]) == {"SPLIT-BLOCK", "SPLIT-PARITY"}
    for split_key in ("SPLIT-BLOCK", "SPLIT-PARITY"):
        cell_block = stage2["cells"][split_key]
        assert set(cell_block) == {"arm_a", "arm_s", "tau_calibration"}
        assert cell_block["arm_a"]["object_weights"]
        assert cell_block["arm_s"]["object_weights"]
    assert stage2["cambridge"]["verdict"] == "NO_VALID_SCORER"
    assert stage2["internal_references"][0]["object_id"] == "brick"

    verdict = on_disk["verdict"]
    for verdict_key in (
        "verdict",
        "deflation_supported",
        "condition_c_supported",
        "single_point_dependent",
        "fail_reason",
        "notes",
        "t_confound_note_required",
    ):
        assert verdict_key in verdict


def test_run_scope_calls_decide_scope_not_a_reimplementation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """:func:`run_scope` must call the frozen :func:`decide_scope` (never
    re-derive the verdict independently) -- a spy confirms the call and
    that its return value is exactly what lands in the written JSON's
    ``"verdict"`` block.
    """
    calls: list[tuple[object, ...]] = []
    real_decide = mod.decide_scope

    def _spy(
        stage0: object, stage1: object, cells: object, *, cambridge: object
    ) -> object:
        calls.append((stage0, stage1, cells, cambridge))
        return real_decide(stage0, stage1, cells, cambridge=cambridge)

    monkeypatch.setattr(mod, "decide_scope", _spy)

    cells = {"SPLIT-BLOCK": _minimal_split_cells("SPLIT-BLOCK")}
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
    payload = mod.run_scope(
        stage0=(),
        stage1=stage1,
        cells=cells,
        cambridge=cells["SPLIT-BLOCK"].arm_s,
        internal_references=(),
        out_path=tmp_path / "scope.json",
    )
    assert len(calls) == 1
    import dataclasses

    assert payload["verdict"] == mod._g1._quantize_json(
        dataclasses.asdict(real_decide(*calls[0][:3], cambridge=calls[0][3]))
    )


# --- AC 006-1 (fidelity pin (b): cell(tau=0.90,k=30) reproduces G1 ARM-A) --

_RUN_REAL_MPNET = os.environ.get("ERRE_RUN_REAL_MPNET_TESTS") == "1"
_REAL_SKIP_REASON = (
    "cell-vs-ARM-A fidelity pin needs the real Ocsai corpus (network) and"
    " four sentence-transformer encoders (~1GB download); skipped by"
    " default to avoid that cost in base CI/local verify. Set"
    " ERRE_RUN_REAL_MPNET_TESTS=1 to opt in (I-007's run.sh)."
)


@pytest.mark.eval
@pytest.mark.skipif(not _RUN_REAL_MPNET, reason=_REAL_SKIP_REASON)
def test_dense_cell_reproduces_g1_arm_a() -> None:
    """AC 006-1 / fidelity pin (b) (Codex HIGH-4): ``cell(tau=REF_DEDUP,
    k=N_R_MAX)`` -- built from :func:`build_cell` / :func:`score_cell`,
    the *generalised* pipeline, never G1's own ``run_ocsai_split`` called
    directly -- reproduces G1's committed Ocsai SPLIT-BLOCK ARM-A numbers
    exactly: X3b's ``auc_full`` 0.863122 / ``auc_lao`` 0.839575 /
    ``potency`` 0.375293, ``verdict == PASS``,
    ``survivors == ("X3a", "X3b", "X3c")``.
    """
    pytest.importorskip("sentence_transformers")

    splits_data = g1.load_ocsai_raw_bytes()
    if splits_data is None:
        pytest.skip("Ocsai source unavailable (network)")
    try:
        encoders = g1.build_available_encoders()
    except g1.MissingEncoderError as exc:
        pytest.skip(f"encoder unavailable offline: {exc}")

    scheme = "SPLIT-BLOCK"
    corpus = "ocsai"
    rows = g1.load_ocsai_rows(splits_data)
    rows_by_object = {
        obj: tuple(r for r in rows if r.object == obj)
        for obj in g1.OCSAI_PRIMARY_OBJECTS
    }
    vmaps = g1.embed_all_texts(rows_by_object, encoders)
    mpnet_vmap = vmaps.get("mpnet", {})
    contexts = {
        obj: g1.build_object_split_context(obj, rows_by_object[obj], scheme, mpnet_vmap)
        for obj in g1.OCSAI_PRIMARY_OBJECTS
    }

    active = [
        obj
        for obj in g1.OCSAI_PRIMARY_OBJECTS
        if not contexts[obj].dropped and g1.object_has_both_gold_classes(contexts[obj])
    ]

    cells_by_object = {
        obj: mod.build_cell(
            contexts[obj],
            mpnet_vmap,
            tau=mod._c.REF_DEDUP,
            cap=mod._c.N_R_MAX,
            corpus=corpus,
            scheme=scheme,
        )
        for obj in active
    }
    final_active = mod.active_objects_for_cell(cells_by_object)
    final_active = tuple(o for o in final_active if o in active)

    captured_draws: dict[str, list[g1.DrawItems]] = {
        c.key: [] for c in g1.CANDIDATE_LADDER
    }
    real_score = g1.score_rows_for_draw

    def _score_spy(*args: object, **kwargs: object) -> dict[str, g1.DrawItems]:
        scored = real_score(*args, **kwargs)
        for key, items in scored.items():
            captured_draws[key].append(items)
        return scored

    import unittest.mock

    with unittest.mock.patch.object(g1, "score_rows_for_draw", side_effect=_score_spy):
        result = mod.score_cell(
            cells_by_object,
            contexts,
            final_active,
            vmaps,
            tau=mod._c.REF_DEDUP,
            k_target=mod._c.N_R_MAX,
            corpus=corpus,
            scheme=scheme,
        )

    assert result.verdict == "PASS"

    summary = g1.build_candidate_report(
        "X3b",
        "embedding",
        captured_draws["X3b"],
        bootstrap_seed=g1.derive_seed(corpus, scheme, "X3b", "bootstrap"),
        permutation_seed=g1.derive_seed(corpus, scheme, "X3b", "permutation"),
    )
    assert summary.report.auc_full_at_median_draw == pytest.approx(0.863122, abs=1e-6)
    assert summary.report.auc_lao_at_median_draw == pytest.approx(0.839575, abs=1e-6)
    assert summary.report.potency_at_median_draw == pytest.approx(0.375293, abs=1e-6)

    class_sizes = g1.cambridge_class_sizes([contexts[o] for o in final_active])
    reports = []
    for cand in g1.CANDIDATE_LADDER:
        if cand.key not in g1.EMBEDDING_FAMILY_EXT or not captured_draws[cand.key]:
            continue
        s = g1.build_candidate_report(
            cand.key,
            cand.family,
            captured_draws[cand.key],
            bootstrap_seed=g1.derive_seed(corpus, scheme, cand.key, "bootstrap"),
            permutation_seed=g1.derive_seed(corpus, scheme, cand.key, "permutation"),
        )
        reports.append(s.report)
    verdict = g1.decide_external(reports, class_sizes=class_sizes)
    assert verdict.verdict == "PASS"
    assert verdict.survivors == ("X3a", "X3b", "X3c")
