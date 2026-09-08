"""Tests for the I-007a CLI wiring (design-final.md §6 fidelity pin (b)+(c),
Cambridge cell wiring for ``--scope``).

**I-007a's own boundary**: none of these tests fetch Ocsai/Cambridge over
the network or run a real measurement -- every real-data prerequisite
(``_gather_ocsai`` / ``_gather_cambridge`` / an encoder / ``_g1.run_fidelity``)
is monkeypatched to a synthetic stand-in, per this issue's own instruction
("実データが無い環境では... 落ちるのは可。ただしデータが揃えば完走する
ことを... 既存の凍結 fixture / mock / 合成データで unit-test して示す").

Covers:

* :func:`~scripts.paper01_scope_condition.cli_fidelity` -- data-unavailable
  vs. mismatch is never conflated (this issue's own binding instruction),
  and a genuine mismatch is never silently reported as ``exit 0``
  (mutation target: "--fidelity の不一致で exit 0 を返す").
* :func:`~scripts.paper01_scope_condition.g1_arm_a_fidelity_matches` -- the
  pin (b) exact-match boundary predicate.
* :func:`~scripts.paper01_scope_condition.build_split_cells` -- DA-SC-3's
  4-cell common-active-object intersection (never a wider set) and
  MEDIUM-3's τ*-neighbour single-point-dependence check.
* :func:`~scripts.paper01_scope_condition._gather_cambridge` -- missing
  Cambridge / missing encoder both return ``None`` (never raise).
* :func:`~scripts.paper01_scope_condition.cli_scope` -- every
  source-unavailable branch, and (the completion proof) that the full
  wiring reaches :func:`~scripts.paper01_scope_condition.run_scope` and
  writes a well-shaped ``scope.json`` once every prerequisite resolves.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from scripts import paper01_external_audit as g1
from scripts import paper01_scope_condition as mod

if TYPE_CHECKING:
    from pathlib import Path

SEED = mod.SEED


def _stub_mpnet(_texts: object) -> object:
    """An encoder stand-in that is provided (so the "no encoder" branch is
    never taken) but never actually invoked in the ``cli_scope``
    source-unavailable tests below (they all fail before reaching an
    encoder call)."""
    return object()


def _fake_load_mpnet_or_none() -> object:
    """``_load_mpnet_or_none()`` stand-in that always resolves to
    :func:`_stub_mpnet`."""
    return _stub_mpnet


def _good_arm_a_result() -> mod.ArmAFidelityResult:
    """A pin (b) measurement that matches every frozen G1 ARM-A target."""
    return mod.ArmAFidelityResult(
        auc_full_at_median_draw=mod.G1_ARM_A_EXPECTED_AUC_FULL,
        auc_lao_at_median_draw=mod.G1_ARM_A_EXPECTED_AUC_LAO,
        potency_at_median_draw=mod.G1_ARM_A_EXPECTED_POTENCY,
        cell_verdict=mod.G1_ARM_A_EXPECTED_CELL_VERDICT,
        overall_verdict=mod.G1_ARM_A_EXPECTED_OVERALL_VERDICT,
        survivors=mod.G1_ARM_A_EXPECTED_SURVIVORS,
    )


# =============================================================================
# g1_arm_a_fidelity_matches (pin (b) boundary predicate)
# =============================================================================


def test_g1_arm_a_fidelity_matches_on_exact_frozen_values() -> None:
    assert mod.g1_arm_a_fidelity_matches(_good_arm_a_result())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("auc_full_at_median_draw", 0.5),
        ("auc_lao_at_median_draw", 0.5),
        ("potency_at_median_draw", 0.5),
        ("cell_verdict", "NO_VALID_SCORER"),
        ("overall_verdict", "NO_VALID_SCORER"),
        ("survivors", ("X0",)),
    ],
)
def test_g1_arm_a_fidelity_matches_rejects_any_single_disagreement(
    field: str, value: object
) -> None:
    """mutation target: any component dropped from the conjunction, or the
    conjunction relaxed to a disjunction, would let one of these six
    perturbed results wrongly report a match."""
    import dataclasses

    perturbed = dataclasses.replace(_good_arm_a_result(), **{field: value})
    assert not mod.g1_arm_a_fidelity_matches(perturbed)


def test_g1_arm_a_fidelity_matches_tolerance_boundary() -> None:
    """Within :data:`G1_ARM_A_TOLERANCE` matches; at-or-beyond it does not
    (mutation target: the tolerance loosened)."""
    import dataclasses

    just_inside = dataclasses.replace(
        _good_arm_a_result(),
        auc_full_at_median_draw=mod.G1_ARM_A_EXPECTED_AUC_FULL
        + mod.G1_ARM_A_TOLERANCE / 2,
    )
    assert mod.g1_arm_a_fidelity_matches(just_inside)

    at_boundary = dataclasses.replace(
        _good_arm_a_result(),
        auc_full_at_median_draw=mod.G1_ARM_A_EXPECTED_AUC_FULL + mod.G1_ARM_A_TOLERANCE,
    )
    assert not mod.g1_arm_a_fidelity_matches(at_boundary)


# =============================================================================
# cli_fidelity: data-unavailable vs. mismatch (never conflated)
# =============================================================================


def test_cli_fidelity_ok_when_both_pins_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod._g1,
        "run_fidelity",
        lambda: {
            "all_match": True,
            "c0": {"matches": True},
            "c4": {"matches": True},
        },
    )
    sentinel_gather = object()
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: sentinel_gather)
    monkeypatch.setattr(
        mod, "measure_g1_arm_a_fidelity", lambda _gather: _good_arm_a_result()
    )
    assert mod.cli_fidelity() == mod.FIDELITY_EXIT_OK == 0


def test_cli_fidelity_pin_c_source_unavailable_is_not_a_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RuntimeError (encoder unavailable) from pin (c) must report
    FIDELITY_EXIT_SOURCE_UNAVAILABLE, never FIDELITY_EXIT_MISMATCH, when
    pin (b) is also unavailable."""

    def _raise() -> dict[str, object]:
        msg = "MPNet encoder unavailable offline"
        raise RuntimeError(msg)

    monkeypatch.setattr(mod._g1, "run_fidelity", _raise)
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: None)
    code = mod.cli_fidelity()
    assert code == mod.FIDELITY_EXIT_SOURCE_UNAVAILABLE
    assert code != mod.FIDELITY_EXIT_MISMATCH


def test_cli_fidelity_pin_c_missing_phase_a_artifact_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> dict[str, object]:
        raise FileNotFoundError("Phase A artifact missing")

    monkeypatch.setattr(mod._g1, "run_fidelity", _raise)
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: None)
    assert mod.cli_fidelity() == mod.FIDELITY_EXIT_SOURCE_UNAVAILABLE


def test_cli_fidelity_pin_c_mismatch_never_reports_exit_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mutation target (issue 007's own required mutant): "--fidelity の
    不一致で exit 0 を返す"."""
    monkeypatch.setattr(
        mod._g1,
        "run_fidelity",
        lambda: {
            "all_match": False,
            "c0": {"matches": False},
            "c4": {"matches": True},
        },
    )
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: None)
    code = mod.cli_fidelity()
    assert code == mod.FIDELITY_EXIT_MISMATCH
    assert code != mod.FIDELITY_EXIT_OK


def test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dataclasses

    monkeypatch.setattr(
        mod._g1,
        "run_fidelity",
        lambda: {
            "all_match": True,
            "c0": {"matches": True},
            "c4": {"matches": True},
        },
    )
    sentinel_gather = object()
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: sentinel_gather)
    bad_result = dataclasses.replace(_good_arm_a_result(), auc_full_at_median_draw=0.1)
    monkeypatch.setattr(mod, "measure_g1_arm_a_fidelity", lambda _gather: bad_result)
    code = mod.cli_fidelity()
    assert code == mod.FIDELITY_EXIT_MISMATCH
    assert code != mod.FIDELITY_EXIT_OK


def test_cli_fidelity_mismatch_takes_priority_over_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pin (c) mismatches *and* pin (b) is unavailable in the same
    invocation, the combined exit code must be the mismatch code (the
    stronger signal), never the unavailable code."""
    monkeypatch.setattr(
        mod._g1,
        "run_fidelity",
        lambda: {
            "all_match": False,
            "c0": {"matches": False},
            "c4": {"matches": False},
        },
    )
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: None)
    assert mod.cli_fidelity() == mod.FIDELITY_EXIT_MISMATCH


# =============================================================================
# build_split_cells: DA-SC-3 intersection + MEDIUM-3 neighbour check
# =============================================================================


def _fake_gather(objects: tuple[str, ...]) -> mod._OcsaiGather:
    contexts = {o: object() for o in objects}
    return mod._OcsaiGather(
        scheme="SPLIT-BLOCK",
        contexts=contexts,  # type: ignore[arg-type]
        vmaps={},
        encoders={},
        active_objects=objects,
    )


def _n_leaders_build_cell(table: dict[tuple[float, str], int]) -> object:
    """A ``build_cell`` stand-in: n_leaders is looked up by (tau, object),
    defaulting to 10 (well above N_R_MIN=8) for any (tau, object) pair not
    explicitly listed."""

    def _fake(
        ctx: object,
        pool_embeddings: object,
        *,
        tau: float,
        cap: int,
        corpus: str,
        scheme: str,
    ) -> mod.CellAnchors:
        del pool_embeddings, corpus, scheme
        object_key = ctx.object_key  # type: ignore[attr-defined]
        n_leaders = table.get((round(tau, 2), object_key), 10)
        return mod.CellAnchors(
            object_key=object_key,
            tau=tau,
            k_target=cap,
            k_effective=min(cap, n_leaders),
            n_pool=n_leaders,
            n_leaders=n_leaders,
            draw_texts_by_draw=tuple(() for _ in range(g1.ANCHOR_DRAWS)),
        )

    return _fake


class _FakeCtxWithKey:
    def __init__(self, object_key: str) -> None:
        self.object_key = object_key


def _make_gather(objects: tuple[str, ...]) -> mod._OcsaiGather:
    contexts = {o: _FakeCtxWithKey(o) for o in objects}
    return mod._OcsaiGather(
        scheme="SPLIT-BLOCK",
        contexts=contexts,  # type: ignore[arg-type]
        vmaps={},
        encoders={},
        active_objects=objects,
    )


def _fake_cell_result(
    tau: float, k_target: int, active: tuple[str, ...], *, verdict: str
) -> mod.CellResult:
    return mod.CellResult(
        tau=tau,
        k_target=k_target,
        k_effective=len(active),
        n_leaders=10,
        corpus="ocsai",
        split_scheme="SPLIT-BLOCK",
        verdict=verdict,
        active_objects=tuple(sorted(active)),
        object_weights={o: 1.0 / max(len(active), 1) for o in active},
    )


def test_build_split_cells_scores_da_sc3_intersection_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two diagonal ``score_cell`` calls (ARM-A / ARM-S) must be scored
    over the 4-corner common-active-object intersection, never a wider set
    -- "c" clears N_R_MIN at the dense (tau=REF_DEDUP) corners but not at
    the sparse (tau=tau_star) corners, so it must be excluded from both.
    """
    objects = ("a", "b", "c")
    gather = _make_gather(objects)

    leaders_table = {
        (0.9, "a"): 10,
        (0.9, "b"): 10,
        (0.9, "c"): 10,
        (0.5, "a"): 10,
        (0.5, "b"): 10,
        (0.5, "c"): 2,  # below N_R_MIN=8 -- drops at the sparse corners
    }
    monkeypatch.setattr(mod, "build_cell", _n_leaders_build_cell(leaders_table))
    monkeypatch.setattr(
        mod,
        "external_rho_by_tau",
        lambda _contexts, _vmap, _active, tau_grid=mod.TAU_GRID: tuple(
            0.5 for _ in tau_grid
        ),
    )
    monkeypatch.setattr(
        mod,
        "calibrate_tau",
        lambda rho_ext_by_tau, rho_int_primary, *, k_star: mod.TauCalibration(
            rho_int_primary=rho_int_primary,
            rho_by_tau=rho_ext_by_tau,
            tau_star=0.5,
            k_star=k_star,
            single_point_dependent=False,
        ),
    )

    seen_active: list[tuple[float, tuple[str, ...]]] = []

    def _fake_score_cell(
        cells_by_object,
        contexts,
        active_objects,
        vmaps,
        *,
        tau,
        k_target,
        corpus,
        scheme,
    ):
        del cells_by_object, contexts, vmaps, corpus, scheme
        seen_active.append((tau, tuple(sorted(active_objects))))
        verdict = "PASS" if tau == mod._c.REF_DEDUP else "NO_VALID_SCORER"
        return _fake_cell_result(tau, k_target, tuple(active_objects), verdict=verdict)

    monkeypatch.setattr(mod, "score_cell", _fake_score_cell)

    split_cells, dense_k_max = mod.build_split_cells(
        gather, rho_int_primary=0.5, k_star=10, corpus="ocsai"
    )

    assert split_cells.arm_a.active_objects == ("a", "b")
    assert split_cells.arm_s.active_objects == ("a", "b")
    assert "c" not in split_cells.arm_a.active_objects
    assert "c" not in split_cells.arm_s.active_objects
    # every score_cell call in the diagonal (never the neighbour check,
    # which this scenario never reaches since condition 1 does not hold at
    # tau=0.90 -- ARM-A is PASS but the neighbour check only fires when
    # ARM-S is NO_VALID_SCORER *and* ARM-A is PASS, which is exactly this
    # scenario, so the neighbour check *does* run here) is scored over the
    # same intersected set.
    for _tau, active in seen_active:
        assert active == ("a", "b")
    assert dense_k_max.keys() == set(objects)


def test_build_split_cells_single_point_dependent_true_when_no_neighbour_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """condition 1 holds at tau*=0.50 but *neither* TAU_GRID neighbour
    (0.55 / 0.45) reproduces NO_VALID_SCORER -> single_point_dependent."""
    objects = ("a", "b")
    gather = _make_gather(objects)
    monkeypatch.setattr(mod, "build_cell", _n_leaders_build_cell({}))
    monkeypatch.setattr(
        mod,
        "external_rho_by_tau",
        lambda _contexts, _vmap, _active, tau_grid=mod.TAU_GRID: tuple(
            0.5 for _ in tau_grid
        ),
    )
    monkeypatch.setattr(
        mod,
        "calibrate_tau",
        lambda rho_ext_by_tau, rho_int_primary, *, k_star: mod.TauCalibration(
            rho_int_primary=rho_int_primary,
            rho_by_tau=rho_ext_by_tau,
            tau_star=0.5,
            k_star=k_star,
            single_point_dependent=False,
        ),
    )

    verdict_by_tau = {0.9: "PASS", 0.5: "NO_VALID_SCORER", 0.55: "PASS", 0.45: "PASS"}

    def _fake_score_cell(
        cells_by_object,
        contexts,
        active_objects,
        vmaps,
        *,
        tau,
        k_target,
        corpus,
        scheme,
    ):
        del cells_by_object, contexts, vmaps, corpus, scheme
        verdict = verdict_by_tau[round(tau, 2)]
        return _fake_cell_result(tau, k_target, tuple(active_objects), verdict=verdict)

    monkeypatch.setattr(mod, "score_cell", _fake_score_cell)

    split_cells, _dense = mod.build_split_cells(
        gather, rho_int_primary=0.5, k_star=10, corpus="ocsai"
    )
    assert split_cells.tau_calibration.single_point_dependent is True


def test_build_split_cells_single_point_dependent_false_when_a_neighbour_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """condition 1 holds at tau*=0.50 and at least one neighbour (0.55)
    also reproduces NO_VALID_SCORER -> robust, never single-point."""
    objects = ("a", "b")
    gather = _make_gather(objects)
    monkeypatch.setattr(mod, "build_cell", _n_leaders_build_cell({}))
    monkeypatch.setattr(
        mod,
        "external_rho_by_tau",
        lambda _contexts, _vmap, _active, tau_grid=mod.TAU_GRID: tuple(
            0.5 for _ in tau_grid
        ),
    )
    monkeypatch.setattr(
        mod,
        "calibrate_tau",
        lambda rho_ext_by_tau, rho_int_primary, *, k_star: mod.TauCalibration(
            rho_int_primary=rho_int_primary,
            rho_by_tau=rho_ext_by_tau,
            tau_star=0.5,
            k_star=k_star,
            single_point_dependent=False,
        ),
    )

    verdict_by_tau = {
        0.9: "PASS",
        0.5: "NO_VALID_SCORER",
        0.55: "NO_VALID_SCORER",
        0.45: "PASS",
    }

    def _fake_score_cell(
        cells_by_object,
        contexts,
        active_objects,
        vmaps,
        *,
        tau,
        k_target,
        corpus,
        scheme,
    ):
        del cells_by_object, contexts, vmaps, corpus, scheme
        verdict = verdict_by_tau[round(tau, 2)]
        return _fake_cell_result(tau, k_target, tuple(active_objects), verdict=verdict)

    monkeypatch.setattr(mod, "score_cell", _fake_score_cell)

    split_cells, _dense = mod.build_split_cells(
        gather, rho_int_primary=0.5, k_star=10, corpus="ocsai"
    )
    assert split_cells.tau_calibration.single_point_dependent is False


def test_build_split_cells_no_neighbour_check_when_condition1_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """condition 1 never holds at tau* (ARM-A itself is not PASS) --
    single_point_dependent must stay False without even attempting the
    neighbour check."""
    objects = ("a", "b")
    gather = _make_gather(objects)
    monkeypatch.setattr(mod, "build_cell", _n_leaders_build_cell({}))
    monkeypatch.setattr(
        mod,
        "external_rho_by_tau",
        lambda _contexts, _vmap, _active, tau_grid=mod.TAU_GRID: tuple(
            0.5 for _ in tau_grid
        ),
    )
    monkeypatch.setattr(
        mod,
        "calibrate_tau",
        lambda rho_ext_by_tau, rho_int_primary, *, k_star: mod.TauCalibration(
            rho_int_primary=rho_int_primary,
            rho_by_tau=rho_ext_by_tau,
            tau_star=0.5,
            k_star=k_star,
            single_point_dependent=False,
        ),
    )

    calls: list[float] = []

    def _fake_score_cell(
        cells_by_object,
        contexts,
        active_objects,
        vmaps,
        *,
        tau,
        k_target,
        corpus,
        scheme,
    ):
        del cells_by_object, contexts, vmaps, corpus, scheme
        calls.append(tau)
        # ARM-A itself is NO_VALID_SCORER here -- condition 1 requires PASS.
        return _fake_cell_result(
            tau, k_target, tuple(active_objects), verdict="NO_VALID_SCORER"
        )

    monkeypatch.setattr(mod, "score_cell", _fake_score_cell)

    split_cells, _dense = mod.build_split_cells(
        gather, rho_int_primary=0.5, k_star=10, corpus="ocsai"
    )
    assert split_cells.tau_calibration.single_point_dependent is False
    # only the two diagonal cells were scored -- no neighbour calls.
    assert sorted(calls) == sorted([mod._c.REF_DEDUP, 0.5])


# =============================================================================
# _gather_cambridge: missing prerequisites return None, never raise
# =============================================================================


def test_gather_cambridge_returns_none_when_raw_bytes_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> dict[str, bytes]:
        raise FileNotFoundError("no cambridge data")

    monkeypatch.setattr(mod._g1, "load_cambridge_raw_bytes", _raise)
    assert mod._gather_cambridge() is None


def test_gather_cambridge_returns_none_when_encoder_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod._g1, "load_cambridge_raw_bytes", lambda: {"bowl": b"", "paperclip": b""}
    )
    monkeypatch.setattr(mod._g1, "load_cambridge_rows", lambda _obj, _data: ())

    def _raise() -> dict[str, object]:
        raise mod._g1.MissingEncoderError("no encoder")

    monkeypatch.setattr(mod._g1, "build_available_encoders", _raise)
    assert mod._gather_cambridge() is None


# =============================================================================
# cli_scope: source-unavailable branches + the completion proof
# =============================================================================


def test_cli_scope_mpnet_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_load_mpnet_or_none", lambda: None)
    out = tmp_path / "scope.json"
    assert mod.cli_scope(out_path=out) == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "source_unavailable"


def test_cli_scope_cambridge_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_load_mpnet_or_none", _fake_load_mpnet_or_none)
    monkeypatch.setattr(mod, "_gather_cambridge", lambda: None)
    out = tmp_path / "scope.json"
    assert mod.cli_scope(out_path=out) == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "source_unavailable"


def test_cli_scope_ocsai_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_load_mpnet_or_none", _fake_load_mpnet_or_none)
    monkeypatch.setattr(mod, "_gather_cambridge", object)
    monkeypatch.setattr(mod, "internal_reference_per_object", lambda _mpnet: ())
    monkeypatch.setattr(mod, "internal_rho_and_k", lambda _refs: (0.5, 0.4, 10))
    dummy_row = mod.DeltaDecomposition(
        source="internal_c4",
        candidate="C4",
        n_good=0,
        n_common=0,
        mean_t_good=0.0,
        mean_t_common=0.0,
        mean_s_good=0.0,
        mean_s_common=0.0,
        mean_delta_good=0.0,
        mean_delta_common=0.0,
        s_common_minus_s_good=0.0,
        rho=0.5,
    )

    def _fake_stage0_internal_row(_mpnet, *, rho_int_primary):
        del rho_int_primary
        return dummy_row

    monkeypatch.setattr(mod, "_stage0_internal_row", _fake_stage0_internal_row)
    monkeypatch.setattr(mod, "_gather_ocsai", lambda _scheme: None)
    out = tmp_path / "scope.json"
    assert mod.cli_scope(out_path=out) == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "source_unavailable"


def _dummy_split_cells() -> mod.SplitCells:
    weights = {"a": 1.0}
    arm_a = mod.CellResult(
        tau=0.90,
        k_target=30,
        k_effective=30,
        n_leaders=30,
        corpus="ocsai",
        split_scheme="SPLIT-BLOCK",
        verdict="PASS",
        active_objects=("a",),
        object_weights=weights,
    )
    arm_s = mod.CellResult(
        tau=0.5,
        k_target=10,
        k_effective=10,
        n_leaders=10,
        corpus="ocsai",
        split_scheme="SPLIT-BLOCK",
        verdict="NO_VALID_SCORER",
        active_objects=("a",),
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


def test_cli_scope_completes_and_writes_scope_json_when_data_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """This issue's own boundary proof: once every prerequisite resolves,
    ``--scope`` reaches :func:`run_scope` and writes a well-shaped
    ``scope.json`` -- never stuck reporting ``source_unavailable``.
    """
    monkeypatch.setattr(mod, "_load_mpnet_or_none", _fake_load_mpnet_or_none)
    monkeypatch.setattr(mod, "_gather_cambridge", object)

    fake_refs = (
        mod.InternalReference(
            object_id="a",
            rho_primary_c4=0.5,
            rho_secondary_c0=0.4,
            n_refs_primary_c4=10,
            n_refs_secondary_c0=8,
        ),
    )
    monkeypatch.setattr(mod, "internal_reference_per_object", lambda _mpnet: fake_refs)
    monkeypatch.setattr(mod, "internal_rho_and_k", lambda _refs: (0.5, 0.4, 10))

    gathers = {
        scheme_def.key: _fake_gather((scheme_def.key,))
        for scheme_def in g1.SPLIT_SCHEMES
    }
    monkeypatch.setattr(mod, "_gather_ocsai", lambda scheme: gathers[scheme])

    split_cells = _dummy_split_cells()
    dense_k_max: dict[str, object] = {}

    def _fake_build_split_cells(_gather, *, rho_int_primary, k_star, corpus="ocsai"):
        del rho_int_primary, k_star, corpus
        return split_cells, dense_k_max

    monkeypatch.setattr(mod, "build_split_cells", _fake_build_split_cells)

    internal_row = mod.DeltaDecomposition(
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
    )

    def _fake_stage0_internal_row(_mpnet, *, rho_int_primary):
        del rho_int_primary
        return internal_row

    monkeypatch.setattr(mod, "_stage0_internal_row", _fake_stage0_internal_row)
    monkeypatch.setattr(mod, "_stage0_external_row", lambda _gather, _dense: None)

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
    monkeypatch.setattr(mod, "_stage1_result", lambda _gather, _dense: stage1)

    cambridge_cell = mod.CellResult(
        tau=0.5,
        k_target=10,
        k_effective=10,
        n_leaders=10,
        corpus="cambridge",
        split_scheme="SPLIT-BLOCK",
        verdict="NO_VALID_SCORER",
        active_objects=("bowl",),
        object_weights={"bowl": 1.0},
    )
    monkeypatch.setattr(
        mod,
        "_score_cambridge_arm_s",
        lambda _cambridge_gather, _tau_cal: cambridge_cell,
    )

    out = tmp_path / "scope.json"
    code = mod.cli_scope(out_path=out)
    assert code == 0
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in ("stage0", "stage1", "stage2", "verdict"):
        assert key in payload
    assert payload["stage2"]["cambridge"]["verdict"] == "NO_VALID_SCORER"
    assert set(payload["stage2"]["cells"]) == {s.key for s in g1.SPLIT_SCHEMES}
