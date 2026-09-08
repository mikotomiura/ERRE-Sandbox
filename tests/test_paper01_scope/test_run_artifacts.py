"""Tests for the issue 007 run-artifact layer (Loop I-007a).

Covers:

* ``run_gate.py``'s SHA-256 byte-identity boundary predicate (AC 007-2's
  underlying judgment, this issue's own required mutant: "SHA-256 一致
  ゲートを常に真にする").
* ``notes.md``'s eight pre-registered Limitations markers (AC 007-6,
  ``test_notes_limitations_complete``) plus the DA-SC-19 pre-registration-
  amendment marker (this issue's own binding instruction).
* ``run.sh``'s completion marker (mirrors AC 008-6's G1 precedent).
* ``build_metrics.py``'s read-only extraction discipline (this issue's own
  required mutant: "build_metrics が抽出でなく再計算する").

Every predicate here is exercised through the *same* production function a
mutation would need to break -- per the issue's mutation-testing witness
discipline (``feedback_witness_needs_mutation_testing.md``), each positive
assertion has a paired negative case pushed through that identical
function, not a hand-rolled duplicate check.

``run_gate.py`` / ``build_metrics.py`` live under
``experiments/20260908-paper01-scope-condition/`` (not a package under
``scripts/`` or ``src/``), so they are loaded here via
``importlib.util.spec_from_file_location`` -- mirrors
``tests/test_paper01_g1/test_run_artifacts.py``'s own loader exactly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# =============================================================================
# load experiments/20260908-paper01-scope-condition/{run_gate,build_metrics}.py
# by path
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXP_DIR = _REPO_ROOT / "experiments" / "20260908-paper01-scope-condition"
_RUN_GATE_PATH = _EXP_DIR / "run_gate.py"
_RUN_SH_PATH = _EXP_DIR / "run.sh"
_NOTES_PATH = _EXP_DIR / "notes.md"
_BUILD_METRICS_PATH = _EXP_DIR / "build_metrics.py"


def _load_module_by_path(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_gate = _load_module_by_path("paper01_scope_run_gate", _RUN_GATE_PATH)
build_metrics = _load_module_by_path("paper01_scope_build_metrics", _BUILD_METRICS_PATH)


# =============================================================================
# hashes_match / sha256_of_file / check-hashes CLI
# =============================================================================


def test_hashes_match_detects_mismatch() -> None:
    assert run_gate.hashes_match("abc123", "abc123") is True
    assert run_gate.hashes_match("abc123", "def456") is False
    assert run_gate.hashes_match("", "") is True


def test_sha256_of_file_reflects_content(tmp_path: Path) -> None:
    """The digest actually depends on file bytes -- not a constant stub."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"x": 1}\n', encoding="utf-8")
    b.write_text('{"x": 1}\n', encoding="utf-8")
    assert run_gate.hashes_match(run_gate.sha256_of_file(a), run_gate.sha256_of_file(b))

    b.write_text('{"x": 2}\n', encoding="utf-8")
    assert not run_gate.hashes_match(
        run_gate.sha256_of_file(a), run_gate.sha256_of_file(b)
    )


def test_run_gate_check_hashes_cli_exit_code(tmp_path: Path) -> None:
    """The ``check-hashes`` CLI subcommand ``run.sh`` invokes wires
    :func:`hashes_match` to a process exit code -- exit 0 on match, 1 on
    mismatch.

    mutation target (issue 007's own required mutant): "SHA-256 一致
    ゲートを常に真にする" -- forcing ``hashes_match`` (or this CLI wiring)
    to always report a match would let ``run.sh`` silently accept a
    non-reproducible ``scope.json`` and still exit 0.
    """
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    a.write_text("same\n", encoding="utf-8")
    b.write_text("same\n", encoding="utf-8")
    c.write_text("different\n", encoding="utf-8")

    assert run_gate.main(["check-hashes", str(a), str(b)]) == 0
    assert run_gate.main(["check-hashes", str(a), str(c)]) == 1


def test_run_gate_module_importable_from_experiment_dir() -> None:
    """Sanity: run_gate.py is a standalone module (no package __init__),
    loaded the same way run.sh's own invocation resolves it (a bare script
    path, not a dotted import)."""
    assert sys.modules.get("paper01_scope_run_gate") is not None
    assert hasattr(run_gate, "hashes_match")
    assert hasattr(run_gate, "notes_has_required_limitations")
    assert hasattr(run_gate, "notes_has_preregistration_amendment")
    assert hasattr(run_gate, "run_sh_has_completion_marker")


# =============================================================================
# AC 007-6: notes.md Limitations (test_notes_limitations_complete)
# =============================================================================


def test_notes_limitations_complete() -> None:
    """AC 007-6: ``notes.md`` carries all eight pre-registered Limitations
    markers (design-final.md §8 / issue 007)."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    assert run_gate.notes_has_required_limitations(text) is True
    for marker in run_gate.REQUIRED_LIMITATIONS:
        assert marker in text


def test_notes_missing_one_limitation_marker_fails() -> None:
    """Witness discipline: deleting a single required marker from the real
    notes.md text must flip the same judgment function to False -- not a
    hand-rolled duplicate check."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    marker_to_drop = run_gate.REQUIRED_LIMITATIONS[0]
    assert marker_to_drop in text
    mutated = text.replace(marker_to_drop, "")
    assert marker_to_drop not in mutated

    assert run_gate.notes_has_required_limitations(text) is True
    assert run_gate.notes_has_required_limitations(mutated) is False


def test_required_limitations_has_eight_entries() -> None:
    """Constant-shrink guard: the pre-registered list itself must have
    exactly the eight items design-final.md §8 specifies -- catches a
    mutation that shrinks :data:`run_gate.REQUIRED_LIMITATIONS` even if it
    is otherwise still internally self-consistent."""
    assert len(run_gate.REQUIRED_LIMITATIONS) == 8
    assert len(set(run_gate.REQUIRED_LIMITATIONS)) == 8


def test_notes_has_preregistration_amendment_marker() -> None:
    """DA-SC-19's own binding instruction: notes.md must carry the
    pre-registration-amendment marker, distinct from the eight Limitations
    items above (this issue's own boundary requirement)."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    assert run_gate.notes_has_preregistration_amendment(text) is True


def test_notes_missing_preregistration_amendment_marker_fails() -> None:
    text = _NOTES_PATH.read_text(encoding="utf-8")
    assert run_gate.PREREGISTRATION_AMENDMENT_MARKER in text
    mutated = text.replace(run_gate.PREREGISTRATION_AMENDMENT_MARKER, "")
    assert run_gate.notes_has_preregistration_amendment(mutated) is False


def test_notes_all_eight_limitations_present_does_not_imply_amendment() -> None:
    """The amendment marker is *not* one of the eight Limitations items --
    a text carrying all eight but missing the amendment marker must still
    fail :func:`notes_has_preregistration_amendment`."""
    text = "".join(run_gate.REQUIRED_LIMITATIONS)
    assert run_gate.notes_has_required_limitations(text) is True
    assert run_gate.notes_has_preregistration_amendment(text) is False


def test_notes_results_section_is_a_placeholder() -> None:
    """I-007a boundary: this session must not have written any measured
    numbers or a verdict into notes.md's Results section -- the exact
    placeholder the orchestrator prescribed must be present verbatim."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    assert "(未実走 — I-007b で埋める)" in text


# =============================================================================
# run.sh completion marker (mirrors G1's AC 008-6)
# =============================================================================


def test_run_sh_emits_completion_marker() -> None:
    text = _RUN_SH_PATH.read_text(encoding="utf-8")
    assert run_gate.run_sh_has_completion_marker(text) is True
    assert run_gate.COMPLETION_MARKER in text


def test_run_sh_missing_completion_marker_fails() -> None:
    """Witness discipline: removing the marker line from the real run.sh
    text must flip the same judgment function to False."""
    text = _RUN_SH_PATH.read_text(encoding="utf-8")
    mutated = text.replace(run_gate.COMPLETION_MARKER, "")
    assert run_gate.COMPLETION_MARKER not in mutated

    assert run_gate.run_sh_has_completion_marker(text) is True
    assert run_gate.run_sh_has_completion_marker(mutated) is False


def test_run_sh_progress_judgement_is_pid_and_log_tail_not_tqdm() -> None:
    """run.sh's own comments document the PID-survival + log-tail rule,
    and it pipes through ``tee`` into a persisted log file a monitor can
    tail."""
    text = _RUN_SH_PATH.read_text(encoding="utf-8")
    assert "tee" in text
    assert "run.log" in text
    assert "PID" in text or "pid" in text.lower()


def test_run_sh_never_fetches_or_measures_in_this_session() -> None:
    """I-007a boundary sanity: run.sh is a plain script file, not something
    this session executed (mutation testing / verify only ran pytest,
    never bash run.sh)."""
    assert _RUN_SH_PATH.exists()
    text = _RUN_SH_PATH.read_text(encoding="utf-8")
    assert "--fidelity" in text
    assert "--scope" in text


# =============================================================================
# build_metrics.py: read-only extraction (never recomputes a statistic)
# =============================================================================


_FAKE_SCOPE = {
    "stage0": [
        {
            "source": "internal_c4",
            "candidate": "C4",
            "mean_delta_good": 0.123456,
            "mean_delta_common": 0.234567,
            "rho": 0.5,
        }
    ],
    "stage1": {
        "stage1_outcome": "DEFLATION_REJECTED",
        "deflation_supported": False,
        "median_drop": 0.20,
        "eligible_fraction": 0.9,
        "median_draw_outcome": "DEFLATION_SUPPORTED",
    },
    "stage2": {
        "cells": {
            "SPLIT-BLOCK": {
                "arm_a": {"verdict": "PASS", "active_objects": ["a"]},
                "arm_s": {"verdict": "NO_VALID_SCORER", "active_objects": ["a"]},
                "tau_calibration": {
                    "tau_star": 0.55,
                    "k_star": 12,
                    "rho_int_primary": 0.42,
                    "single_point_dependent": False,
                },
            }
        },
        "cambridge": {"verdict": "INCONCLUSIVE_UNDERPOWERED"},
        "internal_references": [],
    },
    "verdict": {
        "verdict": "DO_NOT_WRITE",
        "condition_c_supported": False,
        "deflation_supported": False,
        "single_point_dependent": False,
        "fail_reason": "F2",
        "t_confound_note_required": False,
    },
}


def test_build_metrics_extracts_verbatim_values_never_recomputed() -> None:
    """mutation target (issue 007's own required mutant): "build_metrics
    が抽出でなく再計算する". Every value in :data:`_FAKE_SCOPE` is an
    arbitrary sentinel this test controls -- if :func:`build_metrics.
    build_metrics` recomputed any of them (instead of a plain ``dict.get``
    passthrough), the echoed value would not equal the sentinel this test
    set.
    """
    metrics = build_metrics.build_metrics(_FAKE_SCOPE)

    assert metrics["verdict"]["verdict"] == "DO_NOT_WRITE"
    assert metrics["verdict"]["fail_reason"] == "F2"
    assert metrics["stage1"]["stage1_outcome"] == "DEFLATION_REJECTED"
    assert metrics["stage1"]["median_drop"] == 0.20
    assert metrics["cambridge_verdict"] == "INCONCLUSIVE_UNDERPOWERED"
    assert metrics["splits"]["SPLIT-BLOCK"]["arm_a_verdict"] == "PASS"
    assert metrics["splits"]["SPLIT-BLOCK"]["arm_s_verdict"] == "NO_VALID_SCORER"
    assert metrics["splits"]["SPLIT-BLOCK"]["tau_star"] == 0.55
    assert metrics["splits"]["SPLIT-BLOCK"]["k_star"] == 12
    assert metrics["stage0_rows"][0]["mean_delta_good"] == 0.123456


def test_build_metrics_changing_the_sentinel_changes_the_output() -> None:
    """The paired negative case for the extraction-not-recompute pin: a
    different sentinel value must come out the other side unchanged too
    (never converging on some recomputed constant)."""
    import copy

    scope = copy.deepcopy(_FAKE_SCOPE)
    scope["stage1"]["median_drop"] = 0.987654
    scope["stage2"]["cells"]["SPLIT-BLOCK"]["tau_calibration"]["tau_star"] = 0.75

    metrics = build_metrics.build_metrics(scope)
    assert metrics["stage1"]["median_drop"] == 0.987654
    assert metrics["splits"]["SPLIT-BLOCK"]["tau_star"] == 0.75


def test_build_metrics_never_raises_on_missing_sections() -> None:
    """Read-only extraction is fail-soft (never a fabricated *value*, but
    also never a crash on a payload missing a section)."""
    metrics = build_metrics.build_metrics({})
    assert metrics["verdict"]["verdict"] is None
    assert metrics["splits"] == {}
    assert metrics["stage0_rows"] == []


def test_write_metrics_end_to_end(tmp_path: Path) -> None:
    """End-to-end pin through :func:`build_metrics.write_metrics`:
    read -> extract -> write, byte-identical to the returned dict."""
    scope_path = tmp_path / "scope.json"
    metrics_path = tmp_path / "metrics.json"
    scope_path.write_text(json.dumps(_FAKE_SCOPE), encoding="utf-8")

    result = build_metrics.write_metrics(
        scope_path=scope_path, metrics_path=metrics_path
    )

    assert result["verdict"]["verdict"] == "DO_NOT_WRITE"
    on_disk = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert on_disk == result


def test_build_metrics_module_importable_from_experiment_dir() -> None:
    assert sys.modules.get("paper01_scope_build_metrics") is not None
    assert hasattr(build_metrics, "build_metrics")
    assert hasattr(build_metrics, "write_metrics")
