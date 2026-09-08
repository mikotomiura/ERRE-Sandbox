"""Tests for the issue 008 run-artifact layer (Loop I-008).

Covers:

* AC 008-3 -- ``run_external_audit``'s combined output never grows a
  top-level aggregate ``verdict`` (design-final.md §6 / DA-G1-12).
* The corpus-``status`` symmetrisation (orchestrator disposition DA-G1-28):
  both ``cambridge`` and ``ocsai`` blocks now carry a ``status`` key, and
  ``both_corpora_available`` / ``main --audit``'s exit code are the boundary
  predicates that gate on it (AC 008-7, Codex HIGH-4).
* AC 008-5 -- ``notes.md`` carries all six pre-registered Limitations
  markers.
* AC 008-6 -- ``run.sh`` emits the completion marker its own log tail is
  judged by (never a tqdm-style latest-line read,
  ``feedback_log_tail_completion_marker.md``).
* ``run_gate.py``'s SHA-256 byte-identity boundary predicate (AC 008-4's
  underlying judgment, mutation target ②).

Every predicate here is exercised through the *same* production function a
mutation would need to break -- per the issue's mutation-testing witness
discipline (``feedback_witness_needs_mutation_testing.md``), each positive
assertion has a paired negative case pushed through that identical
function, not a hand-rolled duplicate check.

``run_gate.py`` lives under ``experiments/20260907-paper01-g1/`` (not a
package under ``scripts/`` or ``src/``), so it is loaded here via
``importlib.util.spec_from_file_location`` rather than a normal import.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as mod

if TYPE_CHECKING:
    from collections.abc import Sequence

# =============================================================================
# load experiments/20260907-paper01-g1/run_gate.py by path
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXP_DIR = _REPO_ROOT / "experiments" / "20260907-paper01-g1"
_RUN_GATE_PATH = _EXP_DIR / "run_gate.py"
_RUN_SH_PATH = _EXP_DIR / "run.sh"
_NOTES_PATH = _EXP_DIR / "notes.md"


def _load_run_gate() -> object:
    spec = importlib.util.spec_from_file_location("paper01_g1_run_gate", _RUN_GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_gate = _load_run_gate()


# =============================================================================
# shared stub-encoder / synthetic-row helpers (encoder-independent, mirrors
# test_external_audit.py's / test_ocsai_adapter.py's own style)
# =============================================================================

_FAKE_ENCODER_DIM = 16
_FAKE_ENCODER_HALF = _FAKE_ENCODER_DIM // 2


def _fake_encoder(texts: Sequence[str]) -> np.ndarray:
    """Deterministic 16-dim stub embedding (pure numpy/hash, no ML model).

    A "good" text's vector lives entirely in the first half of the
    dimensions, a "common" text's entirely in the second half.
    """
    out = np.zeros((len(texts), _FAKE_ENCODER_DIM), dtype=float)
    for i, t in enumerate(texts):
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        vec = rng.normal(size=_FAKE_ENCODER_HALF)
        vec = vec / np.linalg.norm(vec)
        if "good" in t:
            out[i, :_FAKE_ENCODER_HALF] = vec
        else:
            out[i, _FAKE_ENCODER_HALF:] = vec
    return out


def _fixed_bootstrap(ci_lower: float, ci_upper: float):
    def _fake(
        *,
        scores_full: Sequence[float],
        scores_lao: Sequence[float],
        labels: Sequence[int],
        objects: Sequence[str],
        seed: int,
    ) -> mod.BootstrapDropResult:
        del scores_full, scores_lao, labels, objects, seed
        return mod.BootstrapDropResult(
            auc_full_ci=(0.0, 1.0),
            auc_lao_ci=(ci_lower, ci_upper),
            drop_ci=(0.0, 0.0),
            p_drop_le_zero=0.5,
        )

    return _fake


def _fake_permutation(
    scores: Sequence[float], labels: Sequence[int], objects: Sequence[str], *, seed: int
) -> float:
    del scores, labels, objects, seed
    return 0.5


def _make_rows(object_key: str, *, n: int = 60) -> tuple[mod.CambridgeRow, ...]:
    """``n`` interleaved rows (1/3 good, 2/3 common) with a stable ``row_id``
    scan order, so both SPLIT-BLOCK and SPLIT-PARITY see a mix of both
    classes in both halves."""
    rows: list[mod.CambridgeRow] = []
    for row_id in range(n):
        if row_id % 3 == 0:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{object_key} good idea {row_id}",
                    category="good",
                )
            )
        else:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{object_key} common idea {row_id}",
                    category="common_use_only",
                )
            )
    return tuple(rows)


# =============================================================================
# AC 008-3: no aggregate top-level verdict
# =============================================================================


def test_no_aggregate_verdict_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """design-final.md §6 / DA-G1-12: ``run_external_audit`` combines the two
    corpora's own (independently computed) verdicts -- it never adds a
    top-level aggregate ``verdict`` of its own.

    Exercises the real ``run_external_audit`` wrapper; only its two heavy
    callees are mocked, so a future change that appended e.g.
    ``result["verdict"] = ...`` after building the dict would be caught
    here.
    """
    fake_cambridge = {
        "corpus": "cambridge",
        "status": "ok",
        "splits": {"SPLIT-BLOCK": {"verdict": {"verdict": "PASS"}}},
    }
    fake_ocsai = {
        "corpus": "ocsai",
        "status": "ok",
        "splits": {"SPLIT-BLOCK": {"verdict": {"verdict": "NO_VALID_SCORER"}}},
    }
    monkeypatch.setattr(mod, "load_cambridge_raw_bytes", dict)
    monkeypatch.setattr(mod, "run_cambridge_audit", lambda raw=None: fake_cambridge)  # noqa: ARG005
    monkeypatch.setattr(
        mod,
        "run_ocsai_audit",
        lambda cambridge_rows_by_object=None: fake_ocsai,  # noqa: ARG005
    )

    combined = mod.run_external_audit()

    assert set(combined) == {"cambridge", "ocsai"}
    assert "verdict" not in combined
    assert "collapse_reproduced" not in combined
    assert combined["cambridge"] == fake_cambridge
    assert combined["ocsai"] == fake_ocsai


# =============================================================================
# corpus-status symmetrisation (DA-G1-28) / AC 008-7 (Codex HIGH-4)
# =============================================================================


def test_both_corpora_available_requires_ok_status_on_both() -> None:
    """AC-MUT ①'s unit-level coverage: ``both_corpora_available`` is a plain
    conjunction over :data:`mod.CORPUS_KEYS`, never a special case for
    either corpus."""
    both_ok = {"cambridge": {"status": "ok"}, "ocsai": {"status": "ok"}}
    ocsai_unavailable = {
        "cambridge": {"status": "ok"},
        "ocsai": {"status": "source_unavailable"},
    }
    cambridge_missing_key_entirely = {"ocsai": {"status": "ok"}}
    neither_ok = {
        "cambridge": {"status": "source_unavailable"},
        "ocsai": {"status": "source_unavailable"},
    }

    assert mod.both_corpora_available(both_ok) is True
    assert mod.both_corpora_available(ocsai_unavailable) is False
    assert mod.both_corpora_available(cambridge_missing_key_entirely) is False
    assert mod.both_corpora_available(neither_ok) is False


def test_run_sh_fails_when_a_corpus_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 008-7 (Codex HIGH-4): ``main``'s ``--audit`` exit code is the
    boundary predicate ``run.sh`` relies on (``set -euo pipefail``) to abort
    when G2 (both corpora available) is not met -- exercised through
    ``main`` itself, not ``both_corpora_available`` in isolation, so a
    regression in the *wiring* (not just the predicate) is also caught.
    """
    unavailable_result = {
        "cambridge": {"status": "ok"},
        "ocsai": {"status": "source_unavailable"},
    }
    monkeypatch.setattr(
        mod,
        "write_external_audit",
        lambda path=mod.EXTERNAL_AUDIT_PATH: unavailable_result,  # noqa: ARG005
    )
    assert mod.main(["--audit"]) != 0

    available_result = {"cambridge": {"status": "ok"}, "ocsai": {"status": "ok"}}
    monkeypatch.setattr(
        mod,
        "write_external_audit",
        lambda path=mod.EXTERNAL_AUDIT_PATH: available_result,  # noqa: ARG005
    )
    assert mod.main(["--audit"]) == 0


def test_both_corpora_carry_a_status_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Symmetrisation pin (DA-G1-28): ``run_cambridge_audit``'s *real*
    production dict-literal now carries ``"status": "ok"`` -- before this
    issue only ``run_ocsai_audit`` ever did. Exercises the real function
    end to end (encoder/bootstrap/permutation stubbed for speed), not a
    hand-copied dict, so deleting the key from the source would fail this
    test.
    """
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 2)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(0.5, 0.95))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)
    monkeypatch.setattr(
        mod, "build_available_encoders", lambda: {"mpnet": _fake_encoder}
    )
    monkeypatch.setattr(
        mod,
        "load_cambridge_rows",
        lambda obj, data: _make_rows(obj),  # noqa: ARG005
    )

    result = mod.run_cambridge_audit({"bowl": b"", "paperclip": b""})

    assert result["status"] == "ok"
    assert result["corpus"] == "cambridge"


def test_committed_external_audit_has_status_ok_for_both_corpora() -> None:
    """Real-artifact bonus pin: once ``run.sh`` has produced
    ``results/external-audit.json``, both persisted corpus blocks carry
    ``status: "ok"``. Skips (not fails) on a checkout where ``run.sh`` has
    not been run yet.
    """
    if not mod.EXTERNAL_AUDIT_PATH.exists():
        pytest.skip("results/external-audit.json not yet produced by run.sh")
    data = json.loads(mod.EXTERNAL_AUDIT_PATH.read_text(encoding="utf-8"))
    for corpus in mod.CORPUS_KEYS:
        assert data[corpus]["status"] == "ok", (
            f"{corpus} block does not report status=ok: {data[corpus].get('status')!r}"
        )


# =============================================================================
# AC-MUT ②: SHA-256 byte-identity boundary predicate (run_gate.py)
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
    mismatch."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    a.write_text("same\n", encoding="utf-8")
    b.write_text("same\n", encoding="utf-8")
    c.write_text("different\n", encoding="utf-8")

    assert run_gate.main(["check-hashes", str(a), str(b)]) == 0
    assert run_gate.main(["check-hashes", str(a), str(c)]) == 1


# =============================================================================
# AC 008-5 / AC-MUT ③: notes.md Limitations
# =============================================================================


def test_notes_has_required_limitations() -> None:
    """AC 008-5: ``notes.md`` carries all six pre-registered Limitations
    markers (design-final.md §8 / issue 008)."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    assert run_gate.notes_has_required_limitations(text) is True
    for marker in run_gate.REQUIRED_LIMITATIONS:
        assert marker in text


def test_notes_missing_one_limitation_marker_fails() -> None:
    """Witness discipline (feedback_witness_needs_mutation_testing.md):
    deleting a single required marker from the real notes.md text must flip
    the same judgment function to False -- not a hand-rolled duplicate
    check."""
    text = _NOTES_PATH.read_text(encoding="utf-8")
    marker_to_drop = run_gate.REQUIRED_LIMITATIONS[0]
    assert marker_to_drop in text
    mutated = text.replace(marker_to_drop, "")
    assert marker_to_drop not in mutated

    assert run_gate.notes_has_required_limitations(text) is True
    assert run_gate.notes_has_required_limitations(mutated) is False


def test_required_limitations_has_six_entries() -> None:
    """AC-MUT ③'s constant-shrink guard: the pre-registered list itself
    must have exactly the six items issue 008 specifies -- catches a
    mutation that shrinks :data:`run_gate.REQUIRED_LIMITATIONS` even if it
    is otherwise still internally self-consistent."""
    assert len(run_gate.REQUIRED_LIMITATIONS) == 6
    assert len(set(run_gate.REQUIRED_LIMITATIONS)) == 6


# =============================================================================
# AC 008-6 / AC-MUT ④: run.sh completion marker
# =============================================================================


def test_run_sh_emits_completion_marker() -> None:
    """AC 008-6: ``run.sh``'s own source emits the completion marker its
    log tail is judged by (PID-survival + log-tail progress judgement,
    never a tqdm-style latest-line read)."""
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
    """AC 008-6's Test Plan wording, pinned structurally: run.sh's own
    comments document the PID-survival + log-tail rule, and it pipes
    through ``tee`` into a persisted log file a monitor can tail."""
    text = _RUN_SH_PATH.read_text(encoding="utf-8")
    assert "tee" in text
    assert "run.log" in text
    assert "PID" in text or "pid" in text.lower()


# =============================================================================
# reused-not-duplicated: AC 008 "source_unavailable is not a verdict" pin
# already lives at tests/test_paper01_g1/test_preregistration.py::
# test_source_unavailable_is_not_a_verdict -- not re-asserted here, per the
# issue prompt's "既存があれば流用".
# =============================================================================


def test_run_gate_module_importable_from_experiment_dir() -> None:
    """Sanity: run_gate.py is a standalone module (no package __init__),
    loaded the same way run.sh's own invocation resolves it (a bare script
    path, not a dotted import)."""
    assert sys.modules.get("paper01_g1_run_gate") is not None
    assert hasattr(run_gate, "hashes_match")
    assert hasattr(run_gate, "notes_has_required_limitations")
    assert hasattr(run_gate, "run_sh_has_completion_marker")


# --- Codex TASK-POST MEDIUM-1 regression -------------------------------------


def test_missing_encoder_is_fatal_not_a_silent_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing encoder must block the verdict (design-final.md §6).

    ``build_available_encoders`` used to drop an uncached model silently, so a
    *subset* ladder could still produce a verdict that reads as the full
    pre-registered battery -- exactly the forking path §6 closes with
    "encoder が 1 つでも取得できなければ verdict を発行せず exit != 0"
    (Opus MEDIUM-5). Codex found the discrepancy in the TASK-POST review.
    """
    real = mod._diag.make_encoder

    def _one_missing(model_id: str) -> object | None:
        return None if "bge" in model_id else real(model_id)

    monkeypatch.setattr(mod._diag, "make_encoder", _one_missing)

    with pytest.raises(mod.MissingEncoderError) as excinfo:
        mod.build_available_encoders()
    assert "bge" in str(excinfo.value)

    # ...and the observation-only escape hatch still returns the partial set,
    # so the guard is a verdict gate rather than a blanket import failure.
    partial = mod.build_available_encoders(require_all=False)
    assert "bge-small-en-v1.5" not in partial
