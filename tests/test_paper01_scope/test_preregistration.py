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
from pathlib import Path

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


# --- AC 001b-1 (Codex TASK-PRE HIGH-3 / DA-SC-19) ---------------------------


def test_stage1_outcome_enum_is_frozen() -> None:
    """STAGE1_OUTCOME_ENUM is frozen to exactly 3 values, in this order.

    design-final.md §3 Stage 1's third table row ("X0 が replicate の過半で
    eligible でない" -> "判定不能") is the reason ``"INCONCLUSIVE"`` must
    exist as its own value, distinct from ``"DEFLATION_REJECTED"`` -- a
    mutant that collapses the enum to those 2 values (e.g. by writing
    ``"INCONCLUSIVE"`` as ``"DEFLATION_REJECTED"``) must fail this exact
    tuple-equality assertion (001b-MUT's named mutant). The registered
    ``config.json`` copy (DA-SC-19: this is a pre-registration amendment,
    not a silent addition) must equal the live constant.
    """
    enum = mod.STAGE1_OUTCOME_ENUM
    assert enum == ("DEFLATION_SUPPORTED", "DEFLATION_REJECTED", "INCONCLUSIVE")
    assert len(enum) == len(set(enum)) == 3

    on_disk = mod.load_config()
    assert on_disk["stage1_outcome_enum"] == list(enum)
    assert mod.collect_preregistration()["stage1_outcome_enum"] == list(enum)


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
        "stage1_outcome": "str",
        "drop_p5_eligible": "float",
        "drop_p95_eligible": "float",
        "median_drop_eligible": "float",
        "drop_p5_strat": "float",
        "drop_p95_strat": "float",
        "median_drop_strat": "float",
        "n_objects_pool_short": "int",
        "pool_short_objects": "tuple[str, ...]",
        "median_draw_drop": "float",
        "median_draw_outcome": "str",
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
        "t_confound_note_required": "bool",
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
        "stage1_outcome": "DEFLATION_SUPPORTED",
        "drop_p5_eligible": 0.11,
        "drop_p95_eligible": 0.29,
        "median_drop_eligible": 0.19,
        "drop_p5_strat": 0.09,
        "drop_p95_strat": 0.31,
        "median_drop_strat": 0.21,
        "n_objects_pool_short": 0,
        "pool_short_objects": (),
        "median_draw_drop": 0.20,
        "median_draw_outcome": "DEFLATION_SUPPORTED",
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
        "t_confound_note_required": False,
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


# --- AC 001b-3 (Codex TASK-PRE HIGH-3 / DA-SC-19) ---------------------------

_STAGE1_RESULT_EXTENDED_FIELDS: dict[str, str] = {
    "candidate": "str",
    "n_replicates": "int",
    "drop_p5": "float",
    "drop_p95": "float",
    "median_drop": "float",
    "eligible_fraction": "float",
    "deflation_supported": "bool",
    "stage1_outcome": "str",
    "drop_p5_eligible": "float",
    "drop_p95_eligible": "float",
    "median_drop_eligible": "float",
    "drop_p5_strat": "float",
    "drop_p95_strat": "float",
    "median_drop_strat": "float",
    "n_objects_pool_short": "int",
    "pool_short_objects": "tuple[str, ...]",
    "median_draw_drop": "float",
    "median_draw_outcome": "str",
}


def test_stage1_result_contract_is_extended() -> None:
    """Stage1Result carries every issue-001b table field, name and type exact.

    Standalone from :func:`test_shared_result_contracts_are_frozen` (that one
    proves frozen-ness across all 6 dataclasses; this one is 001b's own AC,
    scoped to exactly the HIGH-3/DA-SC-19 field additions) so the two ACs
    stay independently traceable to their own test. Exact-set equality (not
    subset) means a mutant that drops or renames one of the new fields is
    killed here even if it slipped past the shared-contracts sweep.
    """
    actual = {f.name: f.type for f in dataclasses.fields(mod.Stage1Result)}
    assert actual == _STAGE1_RESULT_EXTENDED_FIELDS
    assert len(actual) == 18


# --- AC 001b-4 (the core AC: inconclusive must not collapse to rejected) ----


def test_inconclusive_is_not_rejection() -> None:
    """INCONCLUSIVE and DEFLATION_REJECTED share deflation_supported=False
    but remain distinguishable via stage1_outcome.

    This is the pre-registration-bias test (design-final.md §5's exit table
    reads ``deflation_supported=False`` as "deflation rejected" => write
    direction; folding "can't tell" into that reading is exactly the bias
    DA-SC-19 amended the contract to close). Both labels below are read
    out of :data:`mod.STAGE1_OUTCOME_ENUM` positionally, never as bare string
    literals, so the two constructed instances cannot silently drift away
    from the frozen vocabulary they are supposed to represent.

    **What actually kills 001b-MUT's named mutant M1** (the enum's
    ``"INCONCLUSIVE"`` entry collapsed into ``"DEFLATION_REJECTED"``) is the
    *membership* assertion immediately below -- verified by applying M1 and
    reading the failure: ``assert "INCONCLUSIVE" in mod.STAGE1_OUTCOME_ENUM``
    fires first, before any instance is built. The positional reads are
    therefore **not** a second, independent kill path for M1; claiming so
    would overstate this witness. Their job is narrower and still worth
    having: they stop this test from passing while the instances disagree
    with the enum.
    """
    assert "INCONCLUSIVE" in mod.STAGE1_OUTCOME_ENUM
    assert "DEFLATION_REJECTED" in mod.STAGE1_OUTCOME_ENUM

    rejected_label = mod.STAGE1_OUTCOME_ENUM[1]
    inconclusive_label = mod.STAGE1_OUTCOME_ENUM[2]
    assert rejected_label == "DEFLATION_REJECTED"
    assert inconclusive_label == "INCONCLUSIVE"

    base = dict(_SAMPLE_VALUES["Stage1Result"])
    del base["deflation_supported"]
    del base["stage1_outcome"]

    inconclusive = mod.Stage1Result(
        deflation_supported=False,
        stage1_outcome=inconclusive_label,
        **base,
    )
    rejected = mod.Stage1Result(
        deflation_supported=False,
        stage1_outcome=rejected_label,
        **base,
    )

    assert inconclusive.deflation_supported is False
    assert rejected.deflation_supported is False
    # deflation_supported alone cannot tell them apart -- stage1_outcome must.
    assert inconclusive.deflation_supported == rejected.deflation_supported
    assert inconclusive.stage1_outcome != rejected.stage1_outcome
    assert inconclusive.stage1_outcome == inconclusive_label
    assert rejected.stage1_outcome == rejected_label


# --- AC 001b-5 (Codex TASK-PRE HIGH-4 / DA-SC-17) ---------------------------


def test_scope_verdict_contract_is_extended() -> None:
    """ScopeVerdict gains t_confound_note_required; no other field renamed.

    DA-SC-17 (user 裁定): the frozen-code vocabulary
    (``verdict``/``deflation_supported``/``condition_c_supported``/
    ``single_point_dependent``/``fail_reason``/``notes``) is authoritative
    and must not be renamed; only the new field is additive.
    """
    actual = {f.name: f.type for f in dataclasses.fields(mod.ScopeVerdict)}
    expected = {
        "verdict": "str",
        "deflation_supported": "bool",
        "condition_c_supported": "bool",
        "single_point_dependent": "bool",
        "fail_reason": "str | None",
        "notes": "tuple[str, ...]",
        "t_confound_note_required": "bool",
    }
    assert actual == expected
    # explicit anti-rename guard: the 6 original names must still be present.
    original_names = {
        "verdict",
        "deflation_supported",
        "condition_c_supported",
        "single_point_dependent",
        "fail_reason",
        "notes",
    }
    assert original_names <= set(actual)


# --- AC 001b-6 (Codex TASK-PRE HIGH-5) --------------------------------------


def test_internal_reference_owner_is_i006() -> None:
    """InternalReference's docstring credits I-006 as the value-filler.

    Codex TASK-PRE HIGH-5 found the issue body (``issues/006.md``) and this
    docstring disagreed (docstring said I-002). ``issues/006.md``'s
    ``internal_rho_and_k() -> InternalReference`` is the correct owner --
    I-002 only supplies the low-level ρ function.
    """
    doc = mod.InternalReference.__doc__
    assert doc is not None
    assert "I-006 fills the values" in doc
    assert "I-002 fills the values" not in doc


# --- AC 001b-7 (MEDIUM-1) ----------------------------------------------------

_SECTION_ANCHOR_MARKERS: tuple[str, ...] = (
    "I-002: sparsification layer",
    "I-003: Stage 0",
    "I-004: Stage 1",
    "I-005: decision rule",
    "I-006: tau* calibration",
)


def test_section_anchors_exist_in_order() -> None:
    """The 5 I-002..I-006 section anchors exist, in this order, past EOF.

    MEDIUM-1: without these, 4 parallel fan-out branches would all append at
    the same end-of-file location and collide. Reads the module's own source
    file (not just importing it) since anchors are comment-only markers with
    no runtime-visible symbol.
    """
    source = Path(mod.__file__).read_text(encoding="utf-8")
    positions = [source.index(marker) for marker in _SECTION_ANCHOR_MARKERS]
    assert positions == sorted(positions)
    # anchors must be strictly increasing (no duplicates / no overlap)
    assert len(set(positions)) == len(positions)
