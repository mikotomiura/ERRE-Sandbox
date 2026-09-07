"""Tests for scripts/paper01_external_audit.py (Loop issue I-002).

design-final.md §7 / Opus MEDIUM-11 forbids a tautological AC: a test that
only asserts a dict against its own fields proves nothing. Every constant-
freeze test here therefore either (a) monkeypatches the *source of truth*
(this module's own globals, or ``erre_sandbox.evidence.es4_actuator.
constants``) and shows the same comparison function actually reports a
mismatch, or (b) cross-checks against an independently-measured artifact
(``experiments/20260907-paper01-g1/data/source-audit.json``, Gate 0).

All tests are encoder-independent (CI runs with no ``[eval]`` extras) --
this module only reads module-level constants and JSON, never an encoder.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING

from scripts import paper01_external_audit as mod

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.reference import (
    _normalise as _internal_normalise,
)

if TYPE_CHECKING:
    import pytest

_SCRIPT_PATH = Path(mod.__file__).resolve()
_BANNED_THRESHOLD_LITERALS = {0.8, 0.9, 0.1, 10000, 30, 8}


# --- AC 002-1 ---------------------------------------------------------------


def test_preregistration_constants_match_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The checked-in config.json equals a fresh collect_preregistration().

    Non-tautological: after monkeypatching a script-owned constant, the
    *same* comparison function (``config_matches_preregistration``) must
    report the on-disk snapshot as stale, proving the comparison is a real
    read-through and not a self-referential dict check.
    """
    on_disk = mod.load_config()
    assert on_disk == mod.collect_preregistration()
    assert mod.config_matches_preregistration(on_disk)

    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 999)
    assert not mod.config_matches_preregistration(on_disk)


# --- AC 002-2 ---------------------------------------------------------------


def test_preregistration_matches_gate0_counts() -> None:
    """The frozen corpora / object list agree with Gate 0's measured audit."""
    audit = json.loads(mod.SOURCE_AUDIT_PATH.read_text(encoding="utf-8"))
    prereg = mod.collect_preregistration()

    sha_by_id = {c["identifier"]: c["sha256"] for c in prereg["corpora"]}
    assert sha_by_id["bowl"] == audit["cambridge"]["bowl"]["sha256"]
    assert sha_by_id["paperclip"] == audit["cambridge"]["paperclip"]["sha256"]
    assert sha_by_id["train"] == audit["ocsai"]["splits"]["train"]["sha256"]
    assert sha_by_id["val"] == audit["ocsai"]["splits"]["val"]["sha256"]
    assert sha_by_id["test"] == audit["ocsai"]["splits"]["test"]["sha256"]

    assert tuple(prereg["objects"]["ocsai_primary"]) == tuple(
        sorted(audit["ocsai"]["by_object"])
    )

    min_class_n = prereg["min_class_n"]
    for key in ("bowl", "paperclip"):
        assert audit["cambridge"][key]["gold_good"] >= min_class_n
        assert audit["cambridge"][key]["gold_common"] >= min_class_n
    assert audit["ocsai"]["gold_pool_good"] >= min_class_n
    assert audit["ocsai"]["gold_pool_common"] >= min_class_n


# --- AC 002-3 ---------------------------------------------------------------


def test_thresholds_are_imported_not_redefined(monkeypatch: pytest.MonkeyPatch) -> None:
    """No module-level constant restates a banned §9 threshold literal.

    AST-scans this module's top-level assignments for the shared thresholds'
    numeric values (0.8 / 0.9 / 0.1 / 10000 / 30 / 8); none may appear on
    the RHS of a constant definition here, they must only be read through
    ``erre_sandbox.evidence.es4_actuator.constants``. The second half proves
    the read-through is live: monkeypatching ``_c.AUC_FLOOR`` must move
    ``collect_preregistration()``'s reported floor.
    """
    tree = ast.parse(_SCRIPT_PATH.read_text(encoding="utf-8"))
    offenders: list[object] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Constant):
            continue
        raw = value.value
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        if raw in _BANNED_THRESHOLD_LITERALS:
            offenders.append(raw)
    assert offenders == []

    before = mod.collect_preregistration()["thresholds"]
    assert before["auc_floor"] == _c.AUC_FLOOR
    assert before["ref_dedup"] == _c.REF_DEDUP
    assert before["n_r_min"] == _c.N_R_MIN
    assert before["n_r_max"] == _c.N_R_MAX
    assert before["ci_alpha"] == _c.CI_ALPHA
    assert before["n_resamples"] == _c.N_RESAMPLES

    monkeypatch.setattr(_c, "AUC_FLOOR", 0.5)
    after = mod.collect_preregistration()["thresholds"]
    assert after["auc_floor"] == 0.5
    assert after["auc_floor"] != before["auc_floor"]


# --- AC 002-4 ----------------------------------------------------------------


def test_embedding_family_membership() -> None:
    """EMBEDDING_FAMILY_EXT is exactly the 6 embedding candidates X0-X3c."""
    assert mod.EMBEDDING_FAMILY_EXT == ("X0", "X1", "X2", "X3a", "X3b", "X3c")
    assert "X5" not in mod.EMBEDDING_FAMILY_EXT
    assert "X6" not in mod.EMBEDDING_FAMILY_EXT

    ladder_keys = [c.key for c in mod.CANDIDATE_LADDER]
    assert ladder_keys == ["X0", "X1", "X2", "X3a", "X3b", "X3c", "X5", "X6"]
    assert "X4" not in ladder_keys
    assert len(mod.CANDIDATE_LADDER) == 8


# --- AC 002-5 -----------------------------------------------------------


def test_seed_file_matches_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """The checked-in SEED file agrees with the SEED constant.

    Non-tautological: after monkeypatching ``mod.SEED``, the same
    (still-on-disk, unmodified) file no longer equals ``mod.SEED``.
    """
    on_disk = mod.load_seed_file()
    assert on_disk == mod.SEED
    assert on_disk == 20260907

    monkeypatch.setattr(mod, "SEED", 1)
    assert mod.load_seed_file() != mod.SEED


# --- AC 002-6 -----------------------------------------------------------


def test_arm_c_declared_ocsai_only() -> None:
    arm_c = next(arm for arm in mod.ARMS if arm.key == "ARM-C")
    assert arm_c.scope == "ocsai_only"
    assert arm_c.role != "verdict"


# --- AC 002-7 -----------------------------------------------------------


def test_verdict_arm_is_arm_a() -> None:
    verdict_arms = [arm for arm in mod.ARMS if arm.role == "verdict"]
    assert [arm.key for arm in verdict_arms] == ["ARM-A"]
    assert mod.VERDICT_ARM_KEY == "ARM-A"
    for arm in mod.ARMS:
        if arm.key != "ARM-A":
            assert arm.role != "verdict"


# --- AC 002-8 -----------------------------------------------------------


def test_anchor_draw_count_and_seed_frozen() -> None:
    assert mod.ANCHOR_DRAWS == 200
    assert mod.SEED == 20260907
    assert mod.collect_preregistration()["anchor_draws"] == 200
    assert mod.collect_preregistration()["seed"] == 20260907


# --- AC 002-9 -----------------------------------------------------------


def test_draw_size_is_min_of_cap_and_pool() -> None:
    assert mod.draw_size(5) == 5
    assert mod.draw_size(30) == 30
    assert mod.draw_size(100) == 30

    assert mod.draws_effective(5) == 1
    assert mod.draws_effective(29) == 1
    assert mod.draws_effective(30) == mod.ANCHOR_DRAWS
    assert mod.draws_effective(500) == mod.ANCHOR_DRAWS


# --- AC 002-10 ----------------------------------------------------------


def test_ocsai_object_sets_frozen() -> None:
    assert len(mod.OCSAI_PRIMARY_OBJECTS) == 21
    assert len(set(mod.OCSAI_PRIMARY_OBJECTS)) == 21

    sensitivity = set(mod.OCSAI_SENSITIVITY_OBJECTS)
    assert sensitivity == {"brick", "paperclip", "bottle", "shoe"}
    assert sensitivity.issubset(set(mod.OCSAI_PRIMARY_OBJECTS))

    assert set(mod.CAMBRIDGE_OBJECTS) == {"bowl", "paperclip"}


# --- AC 002-11' -----------------------------------------------------------


def test_draw_aggregation_is_per_draw_not_marginal_median() -> None:
    """§5.1: aggregate the *per-draw booleans*' proportion, not a median.

    A marginal-median design would compare ``median(AUC_full)`` and
    ``median(AUC_LAO)`` computed separately -- a configuration that need not
    correspond to any single draw. ``aggregate_draws`` instead only ever
    sees pre-decided booleans and thresholds their proportion.
    """
    assert mod.DRAW_AGGREGATION_THRESHOLD == 0.5

    assert mod.aggregate_draws([True, True, False]) is True  # 2/3 >= 0.5
    assert mod.aggregate_draws([True, False, False]) is False  # 1/3 < 0.5
    assert mod.aggregate_draws([True, False]) is True  # boundary: 0.5 >= 0.5
    assert mod.aggregate_draws([]) is False


def test_bootstrap_applies_to_median_draw_only() -> None:
    assert mod.BOOTSTRAP_APPLIES_TO == "median_draw"
    assert mod.BOOTSTRAP_APPLIES_TO in mod.BOOTSTRAP_SCOPE_OPTIONS
    assert mod.BOOTSTRAP_APPLIES_TO != "all_draws"


# --- AC 002-12 ----------------------------------------------------------


def test_source_unavailable_is_not_a_verdict() -> None:
    assert "source_unavailable" not in mod.VERDICT_ENUM
    assert mod.VERDICT_ENUM == (
        "PASS",
        "NO_VALID_SCORER",
        "INVALID_TASK_BATTERY",
        "INCONCLUSIVE_UNDERPOWERED",
    )


# --- additional -----------------------------------------------------------


def test_normalise_matches_internal_reference_normalise() -> None:
    """NORMALISE is byte-identical to the frozen internal reference._normalise."""
    samples = [
        "  Unlock a Door  ",
        "key\n",
        "Multiple   spaces\tand\ttabs",
        "MixedCASE\r\nWith Newlines",
        "",
        "already normal",
    ]
    for sample in samples:
        assert mod.NORMALISE(sample) == _internal_normalise(sample)


def test_split_schemes_both_frozen() -> None:
    keys = {split.key: split for split in mod.SPLIT_SCHEMES}
    assert set(keys) == {"SPLIT-BLOCK", "SPLIT-PARITY"}
    assert keys["SPLIT-BLOCK"].role == "primary"
    assert keys["SPLIT-PARITY"].role == "sensitivity"


def test_negative_controls_are_preregistered() -> None:
    keys = {control.key for control in mod.NEGATIVE_CONTROLS}
    assert keys == {"NC-1", "NC-2"}
    for control in mod.NEGATIVE_CONTROLS:
        assert control.role == "control"
        assert control.definition


def test_arm_x_is_preregistered() -> None:
    arm_x = next(arm for arm in mod.ARMS if arm.key == "ARM-X")
    assert arm_x.scope == "paperclip_only"
    assert arm_x.role != "verdict"
    assert "Cambridge" in arm_x.definition
    assert "Ocsai" in arm_x.definition
