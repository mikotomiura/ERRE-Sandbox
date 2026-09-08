"""Tests for scripts/paper01_scope_condition.py (Loop I-001).

design-final.md §7 forbids a tautological AC (mirrored from the G1 ADR's own
discipline): a test that only asserts a dict against its own fields proves
nothing. Every constant-freeze test here therefore either (a) monkeypatches
the *source of truth* (the owning module's own attribute -- this module's own
globals, ``erre_sandbox.evidence.es4_actuator.constants``, or
``scripts.paper01_external_audit``) and shows the same comparison function
actually reports a mismatch, or (b) cross-checks against an independently
loaded artifact (the sealed internal gold via
``es4_scorer_diag.load_adversarial_labeled()``).

design-final.md §7 Test Plan is explicit that AC 001-1 uses identity/value
match + ``monkeypatch.setattr`` follow-through, **not** an AST scan (unlike
the G1 ADR's own AC 002-3) -- this file follows that instruction literally.

All tests are encoder-independent (CI runs with no ``[eval]`` extras) -- this
module only reads module-level constants, dataclasses, and JSON, never an
encoder.
"""

from __future__ import annotations

import dataclasses

import pytest
from scripts import paper01_scope_condition as mod

# --- AC 001-1 ----------------------------------------------------------


def test_shared_constants_are_imported_not_redefined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 8 shared floor/bootstrap/draw constants are a live read-through.

    Non-tautological (design-final.md §7 Test Plan: identity/value match +
    ``monkeypatch.setattr``, not an AST scan): after monkeypatching the
    *owning* module's attribute, the very next :func:`collect_preregistration`
    call must report the new value -- proving this module never bakes a copy
    at import time.
    """
    before = mod.collect_preregistration()["thresholds"]
    assert before["auc_floor"] == mod._c.AUC_FLOOR
    assert before["ref_dedup"] == mod._c.REF_DEDUP
    assert before["n_r_min"] == mod._c.N_R_MIN
    assert before["n_r_max"] == mod._c.N_R_MAX
    assert before["ci_alpha"] == mod._c.CI_ALPHA
    assert before["n_resamples"] == mod._c.N_RESAMPLES
    assert before["min_class_n"] == mod._g1.MIN_CLASS_N
    assert before["anchor_draws"] == mod._g1.ANCHOR_DRAWS

    monkeypatch.setattr(mod._c, "AUC_FLOOR", 0.55)
    after_c = mod.collect_preregistration()["thresholds"]
    assert after_c["auc_floor"] == 0.55
    assert after_c["auc_floor"] != before["auc_floor"]

    monkeypatch.setattr(mod._g1, "MIN_CLASS_N", 999)
    after_g1 = mod.collect_preregistration()["thresholds"]
    assert after_g1["min_class_n"] == 999
    assert after_g1["min_class_n"] != before["min_class_n"]
    # the first monkeypatch is still in effect -- proves both read-throughs
    # are independent live lookups, not a single cached snapshot.
    assert after_g1["auc_floor"] == 0.55


# --- AC 001-2 ------------------------------------------------------------


def test_config_matches_preregistration() -> None:
    """The checked-in config.json equals a fresh collect_preregistration()."""
    on_disk = mod.load_config()
    assert on_disk == mod.collect_preregistration()
    assert mod.config_matches_preregistration(on_disk)


# --- AC 001-3 ------------------------------------------------------------


def test_config_mismatch_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-tautological: monkeypatching a constant must flip the comparison.

    Proves ``config_matches_preregistration`` is a real read-through
    comparison rather than a self-referential dict check (design-final.md §7:
    "恒真でない" is itself one of the acceptance criteria, AC 001-3).
    """
    on_disk = mod.load_config()
    assert mod.config_matches_preregistration(on_disk)

    monkeypatch.setattr(mod, "SEED", 1)
    assert not mod.config_matches_preregistration(on_disk)


# --- AC 001-4 --------------------------------------------------------------


def test_seed_file_matches_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """The checked-in SEED file agrees with the SEED constant.

    Non-tautological: after monkeypatching ``mod.SEED``, the same
    (still-on-disk, unmodified) file no longer equals ``mod.SEED``.
    """
    on_disk = mod.load_seed_file()
    assert on_disk == mod.SEED
    assert on_disk == 20260908

    monkeypatch.setattr(mod, "SEED", 1)
    assert mod.load_seed_file() != mod.SEED


# --- AC 001-5 --------------------------------------------------------------


def test_tau_grid_is_well_formed() -> None:
    """TAU_GRID is strictly descending, has no duplicates, and lies in (0, 1)."""
    grid = mod.TAU_GRID
    assert len(grid) >= 2
    assert list(grid) == sorted(grid, reverse=True)
    assert len(set(grid)) == len(grid)
    assert all(0.0 < tau < 1.0 for tau in grid)
    assert grid == (
        0.90,
        0.85,
        0.80,
        0.75,
        0.70,
        0.65,
        0.60,
        0.55,
        0.50,
        0.45,
        0.40,
    )


# --- AC 001-6 --------------------------------------------------------------


def test_stage1_internal_shape_matches_sealed_gold() -> None:
    """STAGE1_INTERNAL_GOOD_COUNTS matches the sealed internal gold's shape.

    Cross-checks against an independently loaded artifact
    (``es4_scorer_diag.load_adversarial_labeled()``, the sealed internal
    ES-4 gold) rather than only asserting the frozen tuple against a
    hardcoded expectation, which would be tautological (design-final.md §7
    Test Plan). ``good`` per-object counts are computed fresh from the gold
    and the AUT battery's frozen 16-object roster (``_diag.load_aut_battery``)
    and compared as a multiset -- design-final.md §3 Stage 1 calls
    STAGE1_INTERNAL_GOOD_COUNTS "内部の物体別 good 件数の多重集合", so element
    *order* is not itself a pinned property, but the multiset, the sum
    (25 = the internal C0 pooled valid-pair count), and the length (16 = the
    AUT object count) all must match the real sealed data.
    """
    aut = mod._diag.load_aut_battery()
    gold = mod._diag.load_adversarial_labeled()

    good_counts: dict[str, int] = {}
    for item in gold:
        if item.category == "good":
            good_counts[item.object] = good_counts.get(item.object, 0) + 1

    measured = tuple(good_counts.get(it.object_id, 0) for it in aut.items)

    assert len(measured) == len(mod.STAGE1_INTERNAL_GOOD_COUNTS) == 16
    assert sum(measured) == sum(mod.STAGE1_INTERNAL_GOOD_COUNTS) == 25
    assert sorted(measured) == sorted(mod.STAGE1_INTERNAL_GOOD_COUNTS)


# --- AC 001-7 --------------------------------------------------------------


def test_delta_ts_candidates_are_pure_max_cos() -> None:
    """DELTA_TS_CANDIDATES is exactly the 6 pure max-cos candidates.

    X1 (mean-agg) and X2 (length-controlled) are deliberately excluded
    (design-final.md §1 HIGH-2): neither decomposes cleanly into T/S.
    """
    assert mod.DELTA_TS_CANDIDATES == ("X0", "X3a", "X3b", "X3c", "C0", "C4")
    assert "X1" not in mod.DELTA_TS_CANDIDATES
    assert "X2" not in mod.DELTA_TS_CANDIDATES
    assert len(mod.DELTA_TS_CANDIDATES) == len(set(mod.DELTA_TS_CANDIDATES)) == 6


# --- AC 001-8 --------------------------------------------------------------


def test_fail_precedence_is_complete_and_ordered() -> None:
    """FAIL_PRECEDENCE contains exactly F1-F7, first is F4."""
    precedence = mod.FAIL_PRECEDENCE
    assert set(precedence) == {"F1", "F2", "F3", "F4", "F5", "F6", "F7"}
    assert len(precedence) == len(set(precedence)) == 7
    assert precedence[0] == "F4"
    assert precedence == ("F4", "F1", "F2", "F3", "F5", "F6", "F7")


# --- AC 001-9 --------------------------------------------------------------

_EXPECTED_CONTRACTS: dict[str, dict[str, str]] = {
    "DeltaDecomposition": {
        "source": "str",
        "candidate": "str",
        "n_good": "int",
        "n_common": "int",
        "mean_t_good": "float",
        "mean_t_common": "float",
        "mean_s_good": "float",
        "mean_s_common": "float",
        "mean_delta_good": "float",
        "mean_delta_common": "float",
        "s_common_minus_s_good": "float",
        "rho": "float",
    },
    "Stage1Result": {
        "candidate": "str",
        "n_replicates": "int",
        "drop_p5": "float",
        "drop_p95": "float",
        "median_drop": "float",
        "eligible_fraction": "float",
        "deflation_supported": "bool",
    },
    "CellResult": {
        "tau": "float",
        "k_target": "int",
        "k_effective": "int",
        "n_leaders": "int",
        "corpus": "str",
        "split_scheme": "str",
        "verdict": "str",
        "active_objects": "tuple[str, ...]",
        "object_weights": "Mapping[str, float]",
    },
    "InternalReference": {
        "object_id": "str",
        "rho_primary_c4": "float",
        "rho_secondary_c0": "float",
        "n_refs_primary_c4": "int",
        "n_refs_secondary_c0": "int",
    },
    "TauCalibration": {
        "rho_int_primary": "float",
        "rho_by_tau": "tuple[float, ...]",
        "tau_star": "float",
        "k_star": "int",
        "single_point_dependent": "bool",
    },
    "ScopeVerdict": {
        "verdict": "str",
        "deflation_supported": "bool",
        "condition_c_supported": "bool",
        "single_point_dependent": "bool",
        "fail_reason": "str | None",
        "notes": "tuple[str, ...]",
    },
}

_SAMPLE_VALUES: dict[str, dict[str, object]] = {
    "DeltaDecomposition": {
        "source": "internal_c0",
        "candidate": "X0",
        "n_good": 3,
        "n_common": 1,
        "mean_t_good": 0.9,
        "mean_t_common": 0.5,
        "mean_s_good": 0.7,
        "mean_s_common": 0.4,
        "mean_delta_good": 0.2,
        "mean_delta_common": 0.1,
        "s_common_minus_s_good": -0.3,
        "rho": 0.6,
    },
    "Stage1Result": {
        "candidate": "X0",
        "n_replicates": 500,
        "drop_p5": 0.10,
        "drop_p95": 0.30,
        "median_drop": 0.20,
        "eligible_fraction": 0.9,
        "deflation_supported": True,
    },
    "CellResult": {
        "tau": 0.90,
        "k_target": 30,
        "k_effective": 30,
        "n_leaders": 40,
        "corpus": "ocsai",
        "split_scheme": "SPLIT-BLOCK",
        "verdict": "PASS",
        "active_objects": ("brick", "paperclip"),
        "object_weights": {"brick": 0.5, "paperclip": 0.5},
    },
    "InternalReference": {
        "object_id": "brick",
        "rho_primary_c4": 0.75,
        "rho_secondary_c0": 0.70,
        "n_refs_primary_c4": 10,
        "n_refs_secondary_c0": 8,
    },
    "TauCalibration": {
        "rho_int_primary": 0.75,
        "rho_by_tau": (0.8, 0.7, 0.6),
        "tau_star": 0.7,
        "k_star": 10,
        "single_point_dependent": False,
    },
    "ScopeVerdict": {
        "verdict": "DO_NOT_WRITE",
        "deflation_supported": False,
        "condition_c_supported": False,
        "single_point_dependent": False,
        "fail_reason": "F4",
        "notes": ("no material difference",),
    },
}


def test_shared_result_contracts_are_frozen() -> None:
    """The 6 shared result dataclasses are field-only, frozen contracts.

    Checks (per class): the exact set of field names and their declared
    annotation strings match design-final.md's per-stage description, the
    class actually is a ``@dataclass``, and an instance rejects attribute
    mutation (``FrozenInstanceError``) -- proving these are frozen contracts
    a downstream issue can safely import and rely on without another issue's
    logic silently mutating a shared result in place.
    """
    assert set(_EXPECTED_CONTRACTS) == {
        "DeltaDecomposition",
        "Stage1Result",
        "CellResult",
        "InternalReference",
        "TauCalibration",
        "ScopeVerdict",
    }

    for name, expected_fields in _EXPECTED_CONTRACTS.items():
        cls = getattr(mod, name)
        assert dataclasses.is_dataclass(cls)

        actual_fields = {f.name: f.type for f in dataclasses.fields(cls)}
        assert actual_fields == expected_fields

        instance = cls(**_SAMPLE_VALUES[name])
        first_field = next(iter(expected_fields))
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(instance, first_field, getattr(instance, first_field))
