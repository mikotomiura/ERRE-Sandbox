"""I7 (M13 live-loop-closure): the sealed-capture harness, Ollama-free.

Covers ``scripts/m13_live_loop_capture.py`` — the apparatus the spend-gated real
qwen3 run will use — without ever opening a connection. The whole point of the
harness' two-mode design is that the *rehearsal* path (scripted chat + mock
embedding) and the *real* path (qwen3:8b + nomic-embed-text) render the same
bundle through the same code, so exercising the rehearsal here is genuine
evidence about the sealed run's verify path, not a separate toy.

Acceptance coverage (``.steering/20260904-m13-live-loop-i7-real-run/requirement.md``):

* AC1 — ``--capture`` writes the full bundle
  -> :func:`test_capture_writes_full_bundle`.
* AC2 — ``--verify`` replays both committed Plane-1 channels through the
  **unmodified** ``run_two_phase_capture`` and matches every checksum/SHA
  -> :func:`test_capture_verify_round_trip` /
  :func:`test_committed_rehearsal_bundle_verifies`.
* AC3 — the Plane L re-drive agrees with Plane G and every correlation-id
  reaches every seam -> :func:`test_committed_rehearsal_reachability_annotation`.
* AC4 — the observables are a frozen sealed-run-before pre-registration whose
  Done set claims nothing causal -> :func:`test_observables_are_frozen_preregistration`.
* AC5 — measurement-line non-re-entry (AST guard)
  -> :func:`test_live_loop_capture_measurement_guard`.

Plus the two gates the honest framing depends on being *enforced*, not merely
documented: the real-spend refusal
(:func:`test_real_capture_refuses_without_confirm_spend`) and the ledger
tamper detection (:func:`test_tampered_ledger_fails_verify`).

**Honest framing (binding, design-final.md §2)**: everything here concerns
*wiring* — that a bounded stimulus reaches each seam and that the run is
deterministically reconstructable. Nothing in this module measures or asserts an
aha / emergence / effect claim, and no floor / landscape / divergence /
magnitude / detectability statistic is computed anywhere.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Final

from scripts.m13_live_loop_capture import (
    EMBEDDING_RECORD_FILENAME,
    FIRING_ANNOTATION_FILENAME,
    INBOUND_LEDGER_FILENAME,
    LIVE_LOOP_DONE_FORMULA,
    LIVE_LOOP_MAX_DRAIN_PER_TICK,
    LIVE_LOOP_N_COGNITION_TICKS,
    LIVE_LOOP_OBSERVABLES,
    REACHABILITY_FILENAME,
    capture,
    live_loop_perturbation_plan,
    main,
    write_bundle,
)
from scripts.m13_live_loop_capture import verify as harness_verify

from tests.test_integration._measurement_guard import assert_no_measurement_surface_v1

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_SRC = _REPO_ROOT / "scripts" / "m13_live_loop_capture.py"
_REHEARSAL_DIR = (
    _REPO_ROOT / "experiments" / "20260904-m13-live-loop-live" / "rehearsal"
)

# Small drive shape for the round-trip tests -- the committed rehearsal bundle
# carries the full 32 x 20 sealed shape, so these only need to prove the code
# path, not re-bake it.
_N_TICKS: Final[int] = 3
_PHYSICS_TICKS: Final[int] = 4
_RUN_ID: Final[str] = "m13-live-loop-i7-test"

_BUNDLE_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "manifest.json",
        "ecl_trace.jsonl",
        "decisions.jsonl",
        "envelope_stream.jsonl",
        EMBEDDING_RECORD_FILENAME,
        INBOUND_LEDGER_FILENAME,
    }
)

# Exact-match extension over the shared v1 guard, mirroring
# ``test_traversal_live.py``'s ``_TRAVERSAL_BANNED_EXACT``: the shared guard
# already bans floor/verdict/divergence as identifier *substrings*; these are
# the emit-surface names this closure must also never grow, matched exactly so
# legitimate words ("effective", "affect") do not false-trip. Identifiers and
# dict keys only -- prose that *negates* these words (the honest framing does
# so repeatedly) is legitimate and is never string-scanned for them.
_LIVE_LOOP_BANNED_EXACT: Final[frozenset[str]] = frozenset(
    {
        "effect",
        "effect_size",
        "detectability",
        "aha_proxy",
        "aha_score",
        "magnitude",
        "score",
    }
)


async def _capture_bundle(out_dir: Path) -> dict[str, str]:
    """Drive one Ollama-free rehearsal capture and write it into ``out_dir``."""
    _result, rendered = await capture(
        run_id=_RUN_ID,
        seed=0,
        n_cognition_ticks=_N_TICKS,
        physics_ticks_per_cognition=_PHYSICS_TICKS,
        real=False,
    )
    write_bundle(out_dir, rendered)
    return rendered


# --------------------------------------------------------------------------- #
# Pre-registered perturbation plan
# --------------------------------------------------------------------------- #


def test_perturbation_plan_is_pure_and_bounded() -> None:
    """The plan is a pure function of (agent_id, n) and this module's frozen
    constants -- never of a run outcome -- and every message is bounded and
    aimed at the driven agent (design-final.md DA-2 "bounded")."""
    first = live_loop_perturbation_plan(agent_id="a_kant_001", n_ticks=7)
    second = live_loop_perturbation_plan(agent_id="a_kant_001", n_ticks=7)
    assert first == second, "the plan must be reproducible across calls"
    assert len(first) == 7

    correlation_ids = [msg.correlation_id for msg in first]
    assert len(set(correlation_ids)) == len(correlation_ids), "corr-ids must be unique"
    assert correlation_ids == sorted(correlation_ids), "corr-ids must be tick-ordered"

    zones = [msg.source_zone for msg in first]
    assert len(set(zones)) == 5, "the plan cycles all five zones"
    for msg in first:
        assert msg.target_agent_id == "a_kant_001"
        assert msg.kind == "world_perturbation"
        assert 0.0 <= msg.intensity <= 1.0
        assert len(msg.content) <= 512


def test_plan_carries_no_loop_bypass() -> None:
    """A perturbation is a *world stimulus*, never a knob/mode/destination
    override -- ``WorldPerturbationMsg`` has no such field at all, so a client
    cannot bypass the cognition loop (design-final.md DA-2 semantics)."""
    msg = live_loop_perturbation_plan(agent_id="a_kant_001", n_ticks=1)[0]
    fields = set(msg.model_dump().keys())
    for bypass in ("knob", "two_phase_knob", "erre", "mode", "destination", "sampling"):
        assert bypass not in fields


# --------------------------------------------------------------------------- #
# AC1/AC2 -- capture -> verify round trip (Ollama-free)
# --------------------------------------------------------------------------- #


async def test_capture_writes_full_bundle(tmp_path: Path) -> None:
    """AC1: one rehearsal capture renders the four handoff artifacts plus the
    two side files, and every one lands on disk."""
    rendered = await _capture_bundle(tmp_path)
    assert set(rendered) == _BUNDLE_FILENAMES
    for name in _BUNDLE_FILENAMES:
        assert (tmp_path / name).exists(), name

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["run_id"] == _RUN_ID
    assert manifest["run"]["cognition_ticks"] == _N_TICKS
    assert manifest["env_pins"]["capture_mode"] == "scripted-rehearsal"
    assert manifest["env_pins"]["think"] is False
    assert manifest["env_pins"]["two_phase_knob"] == "on"
    assert manifest["env_pins"]["max_drain_per_tick"] == LIVE_LOOP_MAX_DRAIN_PER_TICK
    # The two side files are pinned through env_pins, not handoff's artifact set.
    assert manifest["env_pins"]["embedding_record_sha256"]
    assert manifest["env_pins"]["inbound_perturbations_sha256"]
    assert set(manifest["artifacts"]) == {
        "ecl_trace.jsonl",
        "decisions.jsonl",
        "envelope_stream.jsonl",
    }


async def test_capture_is_deterministic(tmp_path: Path) -> None:
    """Two rehearsal captures over identical inputs render byte-identical
    bundles -- the precondition every SHA-256 pin in the manifest rests on."""
    first = await _capture_bundle(tmp_path / "a")
    second = await _capture_bundle(tmp_path / "b")
    assert first == second


async def test_capture_verify_round_trip(tmp_path: Path) -> None:
    """AC2: a freshly captured bundle verifies green through the harness'
    own ``--verify`` path (Plane G replay + Plane L re-drive + both
    annotations), with the annotations landing as side files."""
    await _capture_bundle(tmp_path)
    assert await harness_verify(tmp_path) is True
    assert (tmp_path / REACHABILITY_FILENAME).exists()
    assert (tmp_path / FIRING_ANNOTATION_FILENAME).exists()


async def test_tampered_ledger_fails_verify(tmp_path: Path) -> None:
    """A hand-edited inbound ledger fails the byte check instead of being
    trusted: the committed bytes must be exactly what this apparatus' own
    serialiser produces for the messages they decode to."""
    await _capture_bundle(tmp_path)
    ledger_path = tmp_path / INBOUND_LEDGER_FILENAME
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["msg"]["content"] = "tampered stimulus"
    lines[0] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    assert await harness_verify(tmp_path, annotation_dir=tmp_path / "ann") is False


# --------------------------------------------------------------------------- #
# AC2/AC3 -- the committed rehearsal bundle (structural-green evidence)
# --------------------------------------------------------------------------- #


async def test_committed_rehearsal_bundle_verifies(tmp_path: Path) -> None:
    """AC2: the *committed* rehearsal bytes -- not a freshly baked copy --
    replay green. Annotations are written to ``tmp_path`` so a test run never
    rewrites the committed evidence, and the freshly derived annotations must
    match the committed ones byte-for-byte."""
    assert await harness_verify(_REHEARSAL_DIR, annotation_dir=tmp_path) is True
    for name in (REACHABILITY_FILENAME, FIRING_ANNOTATION_FILENAME):
        fresh = (tmp_path / name).read_text(encoding="utf-8")
        committed = (_REHEARSAL_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"{name} drifted from the committed annotation"


async def test_committed_rehearsal_is_rebakeable() -> None:
    """The committed rehearsal is a deterministic function of the harness, not
    a stale one-off copy: baking it again from scratch reproduces every
    artifact byte-for-byte (which is also what makes the manifest's SHA-256
    pins meaningful)."""
    _result, rendered = await capture(
        run_id="m13-live-loop-i7-rehearsal",
        seed=0,
        n_cognition_ticks=LIVE_LOOP_N_COGNITION_TICKS,
        physics_ticks_per_cognition=20,
        real=False,
    )
    for name, text in rendered.items():
        committed = (_REHEARSAL_DIR / name).read_text(encoding="utf-8")
        assert text == committed, f"{name} drifted from the committed rehearsal"


def test_committed_rehearsal_has_sealed_run_shape() -> None:
    """The committed rehearsal is the *same shape* the sealed run will take
    (32 cognition x 20 physics ticks, knob on, one perturbation per tick), so
    a green rehearsal is evidence about the real bundle rather than about a
    smaller toy."""
    manifest = json.loads(
        (_REHEARSAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["run"]["cognition_ticks"] == LIVE_LOOP_N_COGNITION_TICKS
    assert manifest["env_pins"]["capture_mode"] == "scripted-rehearsal"
    ledger_lines = (
        (_REHEARSAL_DIR / INBOUND_LEDGER_FILENAME)
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert len(ledger_lines) == LIVE_LOOP_N_COGNITION_TICKS


def test_committed_rehearsal_reachability_annotation() -> None:
    """AC3: every injected correlation-id reached every seam, the broadcast
    queue holds exactly the ledger's own envelope multiset (no double send),
    and nothing was injected onto a wrong agent.

    Reachability is **not** causation (``wiring_reachability_summary``'s own
    contract): the ``firing_summary`` / ``same_tick_envelope_observed`` seams
    are tick-level co-occurrence. What this asserts is that the wiring reached
    each seam -- nothing more."""
    annotation = json.loads(
        (_REHEARSAL_DIR / REACHABILITY_FILENAME).read_text(encoding="utf-8")
    )
    assert annotation["all_correlation_ids_reach_all_seams"] is True
    assert annotation["perturbation_count"] == LIVE_LOOP_N_COGNITION_TICKS
    assert annotation["no_double_send"] is True
    assert annotation["target_agent_mismatch_count"] == 0
    assert annotation["verdict"] is None


def test_committed_rehearsal_firing_annotation_is_non_gate() -> None:
    """The firing annotation is a boolean/count side note with an explicit
    ``hard_gate: False`` and ``verdict: None`` -- whatever it reports (fired,
    or an honest ``no_eligible_tick`` settle) it is never a Done gate."""
    annotation = json.loads(
        (_REHEARSAL_DIR / FIRING_ANNOTATION_FILENAME).read_text(encoding="utf-8")
    )
    assert annotation["hard_gate"] is False
    assert annotation["verdict"] is None
    assert annotation["n_ticks"] == LIVE_LOOP_N_COGNITION_TICKS
    assert isinstance(annotation["evaluation_phase_sign_inversion_fired"], bool)


# --------------------------------------------------------------------------- #
# AC4 -- sealed-run-before observables pre-registration
# --------------------------------------------------------------------------- #


def test_observables_are_frozen_preregistration() -> None:
    """AC4: the observables are frozen at import time (constants, not run
    outputs), ``verdict`` is an explicit ``None``, and the Done set is the
    three reproducibility observables only -- both annotations are outside
    it, so neither can ever be tuned into a pass."""
    assert LIVE_LOOP_OBSERVABLES["verdict"] is None
    assert LIVE_LOOP_OBSERVABLES["done_formula"] == LIVE_LOOP_DONE_FORMULA
    assert set(LIVE_LOOP_OBSERVABLES) == {
        "L1",
        "L2",
        "L3",
        "wiring_reachability_annotation",
        "firing_annotation",
        "scope_boundary",
        "done_formula",
        "verdict",
    }
    for key in ("L1", "L2", "L3"):
        assert key in LIVE_LOOP_DONE_FORMULA
    for annotation_key in ("wiring_reachability_annotation", "firing_annotation"):
        assert annotation_key not in LIVE_LOOP_DONE_FORMULA
        assert "non-gate" in LIVE_LOOP_OBSERVABLES[annotation_key]


def test_done_set_claims_nothing_causal() -> None:
    """AC4: the Done-set entries (the actual claims this run can make) contain
    no causal/emergence vocabulary. The annotation and ``scope_boundary``
    entries legitimately *use* those words to negate them, so they are checked
    for the negation instead."""
    forbidden = ("caused", "emergence", "aha happened", "closure proof")
    for key in ("L1", "L2", "L3"):
        lowered = LIVE_LOOP_OBSERVABLES[key].lower()
        for word in forbidden:
            assert word not in lowered, f"{key} carries over-claim vocabulary: {word}"

    boundary = LIVE_LOOP_OBSERVABLES["scope_boundary"].lower()
    assert "wiring reached each seam" in boundary
    assert "never" in boundary
    assert "no live godot client" in boundary
    assert "not a wall-clock real-time session" in boundary


# --------------------------------------------------------------------------- #
# Spend gate -- enforced, not merely documented
# --------------------------------------------------------------------------- #


def test_real_capture_refuses_without_confirm_spend(capsys) -> None:
    """``--capture --real`` without ``--confirm-spend`` refuses with a non-zero
    exit *before* constructing any client, so a stray command can never open a
    live qwen3 session (design-final.md Issue 007 spend gate)."""
    exit_code = main(["--capture", "--real"])
    assert exit_code == 2
    assert "REFUSED" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# AC5 -- measurement-line non-re-entry
# --------------------------------------------------------------------------- #


def _assert_no_live_loop_measurement_surface(tree: ast.Module) -> None:
    """Exact-match extension over the shared v1 guard (identifiers + dict keys)."""
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        for name in names:
            assert name.lower() not in _LIVE_LOOP_BANNED_EXACT, name
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    assert key.value.lower() not in _LIVE_LOOP_BANNED_EXACT, key.value


def test_live_loop_capture_measurement_guard() -> None:
    """AC5: no measurement import / identifier / dict key / annotation filename
    in the I7 harness or this module -- the shared ECL v1 3-hole AST guard plus
    the exact-match extension above. The harness scans with
    ``scan_strings=True`` (it is the file that *emits* side files, so it gets
    the strictest scan); this module stays ``False`` because it legitimately
    names the banned tokens to build the guard."""
    for path, scan_strings in ((_SCRIPT_SRC, True), (_THIS_FILE, False)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
        _assert_no_live_loop_measurement_surface(tree)
