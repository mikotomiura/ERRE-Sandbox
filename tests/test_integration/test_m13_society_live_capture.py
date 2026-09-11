"""Issue 007 (M13 society live-closure): the spend-gated capture harness.

Covers ``scripts/m13_society_live_capture.py`` — the apparatus a ratified real
qwen3 society run would use — **without ever opening a connection**. The whole
point of the harness' two-mode design is that the *rehearsal* path (scripted
per-agent chat + mock embedding) and the *real* path (qwen3:8b +
nomic-embed-text) render the same bundle through the same code, so exercising
the rehearsal here is genuine evidence about the sealed run's verify path
rather than a separate toy.

**No real run happens in this issue, and none can happen from this module.**
Every ``--real`` code path this file touches is one that refuses *before* a
client is constructed (:func:`test_spend_gate_rejects_direct_call_without_ratify`
and :func:`test_sealed_bundle_overwrite_is_refused`), and
:func:`test_spend_gate_rejects_direct_call_without_ratify` additionally pins the
structural fact that makes that safe: the harness names no live client at
module scope, and its single ``OllamaChatClient`` import sits *inside*
``capture()`` **after** the ``assert_sealed_real_run`` call.

Acceptance coverage (``loop/20260906-m13-society-live-closure/issues/007.md``):

* AC1 — ``--capture`` (Ollama-free) completes and ``--verify`` is green
  -> :func:`test_rehearsal_capture_then_verify_is_green`
* AC2 — the spend gate lives in ``capture()`` itself, so a **direct call** that
  bypasses the CLI is refused too
  -> :func:`test_spend_gate_rejects_direct_call_without_ratify`
* AC3 — unpinned provenance (model digest / Ollama version / VRAM / uv.lock
  SHA) is refused -> :func:`test_unpinned_provenance_is_rejected`
* AC4 — an existing sealed bundle is never silently overwritten
  -> :func:`test_sealed_bundle_overwrite_is_refused`
* AC5 — verify checks ``inner_invocations == 0`` and request conformance on
  both channels -> :func:`test_verify_checks_conformance_and_no_llm`
* AC6 — the manifest carries no ``verdict`` and no effect / divergence / floor
  / score key at any nesting level
  -> :func:`test_manifest_has_no_verdict_or_measurement_keys`
* AC7 — the pre-registered constants are frozen at import time and are not
  reachable from the CLI -> :func:`test_preregistered_constants_are_frozen`

Every gate is exercised with a **negative example that actually fires**
(``decisions.md`` DA-SLC-8: a witness whose acceptance form is tautological is
worth nothing), and the committed-bundle tests skip when the bundle is absent
so a checkout without ``artifacts/`` still has a green suite.

**Honest framing (binding, ``design-final.md`` §2)**: everything here concerns
*wiring* — that a bounded stimulus reaches each seam and that a run is
deterministically reconstructable from committed bytes. Nothing in this module
measures or asserts an aha / emergence / effect claim, and no floor / landscape
/ divergence / detectability statistic is computed anywhere.
"""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from typing import Any, Final

import pytest
from scripts.m13_society_live_capture import (
    CONFORMANCE_FILENAME,
    FIRING_ANNOTATION_FILENAME,
    FORCE_REASON_LOG_FILENAME,
    PARITY_FILENAME,
    REHEARSAL_RUN_ID,
    SIDE_ANNOTATION_FILENAMES,
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_CLOSURE_ANNOTATIONS,
    SOCIETY_LIVE_DONE_FORMULA,
    SOCIETY_LIVE_EMBED_MODEL,
    SOCIETY_LIVE_MODEL,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    SOCIETY_LIVE_PERTURBATION_COUNT,
    SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION,
    SOCIETY_LIVE_SEED,
    SOCIETY_LIVE_THINK,
    SealedBundleExistsError,
    SealedParameterError,
    SpendNotRatifiedError,
    assert_bundle_dir_writable,
    assert_sealed_real_run,
    attach_society_live_annotations,
    capture,
    main,
    record_force_reason,
    uv_lock_sha256,
    write_bundle,
)
from scripts.m13_society_live_capture import verify as harness_verify

from erre_sandbox.integration.embodied.society_live_loop import (
    PLANE_G_EMBEDDING_RECORD_FILENAME,
    PLANE_G_INBOUND_LEDGER_FILENAME,
    society_live_loop_perturbation_plan,
)
from tests.test_integration._measurement_guard import assert_no_measurement_surface_v1

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_SRC = _REPO_ROOT / "scripts" / "m13_society_live_capture.py"
_EXPERIMENT_DIR = _REPO_ROOT / "experiments" / "20260907-m13-society-live"
_REHEARSAL_DIR = _EXPERIMENT_DIR / "rehearsal"
_REAL_DIR = _EXPERIMENT_DIR / "artifacts"

# Small drive shape for the round-trip tests: the committed rehearsal bundle
# already carries the full sealed 3 x 12 x 20 shape, so these only need to
# prove the code path, not re-bake it.
_N_TICKS: Final[int] = 3

_BUNDLE_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "manifest.json",
        "ecl_trace.jsonl",
        "decisions.jsonl",
        "envelope_stream.jsonl",
        PLANE_G_INBOUND_LEDGER_FILENAME,
        PLANE_G_EMBEDDING_RECORD_FILENAME,
    }
)

# A fully pinned, on-plan real-run argument set. Every negative case below is
# this dict with exactly one field spoiled, so a refusal can only be caused by
# the field under test.
_SEALED_ARGS: Final[dict[str, Any]] = {
    "confirm_spend": True,
    "model": SOCIETY_LIVE_MODEL,
    "embed_model": SOCIETY_LIVE_EMBED_MODEL,
    "agent_ids": SOCIETY_LIVE_AGENT_IDS,
    "n_cognition_ticks": SOCIETY_LIVE_N_COGNITION_TICKS,
    "physics_ticks_per_cognition": SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION,
    "seed": SOCIETY_LIVE_SEED,
    "perturbation_count": SOCIETY_LIVE_PERTURBATION_COUNT,
    "qwen3_model_digest": "0" * 64,
    "ollama_version": "0.32.12",
    "vram_gb": 16.0,
    "uv_lock_pin": "f" * 64,
}

# Emit-surface names this construction apparatus must never grow, matched
# exactly (identifiers and dict keys only) so legitimate words such as
# "effective" do not false-trip. Prose that *negates* them is legitimate and is
# never substring-scanned.
_SOCIETY_BANNED_EXACT: Final[frozenset[str]] = frozenset(
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

# The measurement-surface names a *manifest* must not carry at any depth
# (AC6). ``verdict`` is included here even though the side annotations
# legitimately emit an explicit ``verdict: None`` -- those files live outside
# the manifest and outside its SHA set.
_MANIFEST_BANNED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "verdict",
        "passed",
        "effect",
        "effect_size",
        "divergence",
        "floor",
        "landscape",
        "score",
        "detectability",
        "magnitude",
        "aha_proxy",
        "r_min",
        "jaccard",
    }
)


async def _capture_bundle(out_dir: Path, *, n_ticks: int = _N_TICKS) -> None:
    """Bake one Ollama-free rehearsal bundle into ``out_dir``."""
    _, rendered = await capture(n_cognition_ticks=n_ticks)
    write_bundle(out_dir, rendered)


def _banned_keys(node: Any, path: str = "") -> tuple[list[str], int]:
    """Walk every nested mapping key; return (hits, keys visited).

    The visit count is returned so a caller can assert the walk was not vacuous
    -- a recursive checker that silently stopped at the top level would pass
    every negative assertion for the wrong reason.
    """
    hits: list[str] = []
    visited = 0
    if isinstance(node, dict):
        for key, value in node.items():
            visited += 1
            if str(key).lower() in _MANIFEST_BANNED_KEYS:
                hits.append(f"{path}/{key}")
            sub_hits, sub_visited = _banned_keys(value, f"{path}/{key}")
            hits += sub_hits
            visited += sub_visited
    elif isinstance(node, list):
        for index, value in enumerate(node):
            sub_hits, sub_visited = _banned_keys(value, f"{path}[{index}]")
            hits += sub_hits
            visited += sub_visited
    return hits, visited


def _capture_function(tree: ast.Module) -> ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "capture":
            return node
    msg = "scripts/m13_society_live_capture.py no longer defines capture()"
    raise AssertionError(msg)


# --------------------------------------------------------------------------- #
# AC1 -- the Ollama-free rehearsal completes and verifies
# --------------------------------------------------------------------------- #


async def test_rehearsal_capture_then_verify_is_green(tmp_path: Path) -> None:
    """AC1: ``--capture`` writes the full bundle and ``--verify`` is green.

    Both halves run the *same* code the sealed run would take -- only the two
    backend objects differ -- which is what makes a green rehearsal evidence
    about the sealed bundle's verify path rather than about a toy.

    Verify is run twice on purpose: the second pass finds the side annotations
    already committed and compares them byte-for-byte instead of writing them,
    so this also pins that the write-or-check branch agrees with itself.
    """
    await _capture_bundle(tmp_path)
    # A synchronous `tmp_path.iterdir()` inside this pytest-asyncio test body
    # lists a handful of just-written files on a local temp dir -- nothing
    # else runs concurrently in a single test, so there is no event loop to
    # block. Not worth a trio/anyio dependency for this.
    filenames = {p.name for p in tmp_path.iterdir()}  # noqa: ASYNC240
    assert filenames == set(_BUNDLE_FILENAMES)

    assert await harness_verify(tmp_path) is True
    for name in SIDE_ANNOTATION_FILENAMES:
        assert (tmp_path / name).exists(), name
    assert await harness_verify(tmp_path) is True

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["run_id"] == REHEARSAL_RUN_ID
    assert manifest["env_pins"]["capture_mode"] == "scripted-rehearsal"
    assert manifest["env_pins"]["real_backend"] is False
    assert manifest["env_pins"]["think"] is SOCIETY_LIVE_THINK


async def test_rehearsal_capture_is_deterministic() -> None:
    """Two bakes of the same shape are byte-identical (no clock/uuid leak)."""
    _, first = await capture(n_cognition_ticks=_N_TICKS)
    _, second = await capture(n_cognition_ticks=_N_TICKS)
    assert first == second


async def test_tampered_bundle_fails_verify(tmp_path: Path) -> None:
    """Non-vacuity for the whole verify layer: a hand-edited committed ledger
    fails instead of being trusted verbatim."""
    await _capture_bundle(tmp_path)
    ledger_path = tmp_path / PLANE_G_INBOUND_LEDGER_FILENAME
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["msg"]["content"] = "a stimulus this run never received"
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    assert await harness_verify(tmp_path, annotation_dir=tmp_path / "ann") is False


# --------------------------------------------------------------------------- #
# AC2 -- the spend gate is on capture(), not on the CLI
# --------------------------------------------------------------------------- #


def test_spend_gate_rejects_direct_call_without_ratify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2: the gate lives on ``capture`` itself, so the CLI is a second door
    onto it, never the gate.

    Three witnesses, in increasing strength:

    1. a **direct call** that bypasses ``main()`` entirely is refused;
    2. it stays refused even when every provenance pin *is* supplied, so the
       refusal is the ratification and not a missing-argument accident;
    3. structurally: the harness names no live client at module scope, and the
       one ``OllamaChatClient`` import sits inside ``capture()`` **after** the
       ``assert_sealed_real_run`` call. A gate that ran after the client was
       constructed would already have spent.

    Deliberately a **sync** ``def`` (not ``async``): ``main()`` is a synchronous
    CLI entry point that drives ``capture()`` itself via ``asyncio.run()``, so
    calling it from inside an already-running event loop (an ``async def``
    test under ``asyncio_mode = "auto"``) would raise ``RuntimeError:
    asyncio.run() cannot be called from a running event loop`` before the gate
    ever got a chance to fire. Driving the two direct-call witnesses through
    ``asyncio.run()`` here too keeps every witness in this test on the same
    "no event loop is already running" footing that a real CLI invocation has.
    """
    with pytest.raises(SpendNotRatifiedError):
        asyncio.run(capture(real=True))

    with pytest.raises(SpendNotRatifiedError):
        asyncio.run(
            capture(
                real=True,
                confirm_spend=False,
                qwen3_model_digest="0" * 64,
                ollama_version="0.32.12",
                vram_gb=16.0,
            )
        )

    # The CLI refuses too, without writing anything.
    assert main(["--capture", "--real", "--out-dir", str(tmp_path)]) == 2
    assert "REFUSED" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []

    tree = ast.parse(_SCRIPT_SRC.read_text(encoding="utf-8"))
    module_level_names = [
        alias.name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]
    assert "OllamaChatClient" not in module_level_names

    capture_fn = _capture_function(tree)
    gate_lines = [
        node.lineno
        for node in ast.walk(capture_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_sealed_real_run"
    ]
    client_import_lines = [
        node.lineno
        for node in ast.walk(capture_fn)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "OllamaChatClient" for alias in node.names)
    ]
    assert len(gate_lines) == 1, "capture() must call the gate exactly once"
    assert len(client_import_lines) == 1, "one live-client import inside capture()"
    assert gate_lines[0] < client_import_lines[0]


# --------------------------------------------------------------------------- #
# AC3 -- unpinned provenance is refused before the spend
# --------------------------------------------------------------------------- #


def test_unpinned_provenance_is_rejected() -> None:
    """AC3: an artifact nobody could audit afterwards is refused, one pin at a
    time.

    The fully pinned tuple is accepted first, so the per-field refusals below
    are attributable to that field alone rather than to a gate that always
    says no.
    """
    assert_sealed_real_run(**_SEALED_ARGS)

    for field, unpinned in (
        ("qwen3_model_digest", "unknown"),
        ("qwen3_model_digest", ""),
        ("ollama_version", "unknown"),
        ("ollama_version", "   "),
        ("vram_gb", 0.0),
        ("uv_lock_pin", "unknown"),
        ("uv_lock_pin", ""),
    ):
        with pytest.raises(SealedParameterError):
            assert_sealed_real_run(**{**_SEALED_ARGS, field: unpinned})


# --------------------------------------------------------------------------- #
# AC3 (Codex TASK-POST M-B) -- digest / lock-hash FORMAT is validated, not
# just non-emptiness. Before this fix a non-empty placeholder like "abc"
# satisfied the gate; each case below is a malformed value that must now be
# refused on its own, one field/shape at a time.
# --------------------------------------------------------------------------- #


def test_malformed_qwen3_digest_is_rejected() -> None:
    """AC3/M-B: ``qwen3_model_digest`` must be 64 hex chars or
    ``sha256:<64 hex>`` -- a real Ollama digest shape -- not merely non-empty."""
    for malformed in (
        "abc",
        "not-a-sha",
        "0" * 63,  # one hex char short
        "0" * 65,  # one hex char long
        "g" * 64,  # right length, non-hex characters
        "sha256:" + "0" * 63,  # prefixed but short
        "sha256:" + "g" * 64,  # prefixed but non-hex
    ):
        with pytest.raises(SealedParameterError):
            assert_sealed_real_run(**{**_SEALED_ARGS, "qwen3_model_digest": malformed})

    # Positive: the prefixed Ollama shape is accepted, not just the bare one.
    assert_sealed_real_run(
        **{**_SEALED_ARGS, "qwen3_model_digest": "sha256:" + "0" * 64}
    )


def test_malformed_uv_lock_pin_is_rejected() -> None:
    """AC3/M-B: ``uv_lock_pin`` must be exactly 64 hex chars (the shape
    ``hashlib.sha256(...).hexdigest()`` always produces), not merely
    non-empty."""
    for malformed in (
        "abc",
        "not-a-sha",
        "0" * 63,
        "0" * 65,
        "g" * 64,
    ):
        with pytest.raises(SealedParameterError):
            assert_sealed_real_run(**{**_SEALED_ARGS, "uv_lock_pin": malformed})


def test_uv_lock_pin_is_derived_not_defaulted() -> None:
    """AC3: the ``uv.lock`` hash is computed from this checkout, so it can never
    silently seal as ``"unknown"`` because a flag was forgotten."""
    derived = uv_lock_sha256()
    assert len(derived) == 64
    assert derived == uv_lock_sha256()


# --------------------------------------------------------------------------- #
# AC4 -- a sealed bundle is never silently overwritten
# --------------------------------------------------------------------------- #


def test_sealed_bundle_overwrite_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC4: overwriting a sealed bundle is the mechanism a tune-to-pass re-run
    would use, so a non-empty real destination is refused.

    The CLI half monkeypatches ``capture`` to explode on call: that turns "the
    directory check happens before the spend" from a claim about statement
    order into something the test would fail if it were ever false -- and it
    means this test cannot reach a backend even if the ordering regressed.
    """
    import scripts.m13_society_live_capture as harness

    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SealedBundleExistsError):
        assert_bundle_dir_writable(tmp_path, refuse_non_empty=True)
    # The rehearsal directory (and an explicit --force) pass straight through.
    assert_bundle_dir_writable(tmp_path, refuse_non_empty=False)

    def _never_called(**_kwargs: Any) -> None:
        msg = "capture() must not be reached once the destination is refused"
        raise AssertionError(msg)

    monkeypatch.setattr(harness, "capture", _never_called)
    exit_code = main(
        [
            "--capture",
            "--real",
            "--confirm-spend",
            "--qwen3-model-digest",
            "0" * 64,
            "--ollama-version",
            "0.32.12",
            "--vram-gb",
            "16",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 2
    assert "REFUSED" in capsys.readouterr().out
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == "{}"


# --------------------------------------------------------------------------- #
# AC4 (Codex TASK-POST M-C) -- --force requires a RECORDED --force-reason,
# not just a flag: --force's own help text has always said "only with a
# recorded reason" but nothing enforced or persisted one until this fix.
# --------------------------------------------------------------------------- #


def test_force_without_reason_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """M-C: ``--force`` without ``--force-reason`` is refused before
    ``capture()`` is ever reached (the same "cannot reach a backend even if
    the ordering regressed" witness as :func:`test_sealed_bundle_overwrite_is_refused`),
    and a blank/whitespace-only reason is refused the same way as a missing one."""
    import scripts.m13_society_live_capture as harness

    def _never_called(**_kwargs: Any) -> None:
        msg = "capture() must not be reached when --force-reason is missing"
        raise AssertionError(msg)

    monkeypatch.setattr(harness, "capture", _never_called)

    base_argv = [
        "--capture",
        "--real",
        "--confirm-spend",
        "--force",
        "--qwen3-model-digest",
        "0" * 64,
        "--ollama-version",
        "0.32.12",
        "--vram-gb",
        "16",
        "--out-dir",
        str(tmp_path),
    ]
    exit_code = main(base_argv)
    assert exit_code == 2
    captured = capsys.readouterr().out
    assert "REFUSED" in captured
    assert "--force-reason" in captured

    exit_code = main([*base_argv, "--force-reason", "   "])
    assert exit_code == 2
    assert "REFUSED" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_force_reason_is_recorded_on_successful_capture(tmp_path: Path) -> None:
    """M-C: a successful ``--force`` capture actually persists the reason to
    the bundle directory's audit log -- not merely accepts the flag.

    Ollama-free: ``--real`` is deliberately NOT passed (``--force`` is a
    no-op without it, refuse_non_empty stays False either way), so this
    exercises the CLI-level requirement + the recording end-to-end without
    ever touching a real backend. A plain ``def`` (not ``async def``) for the
    same "no event loop already running" reason documented on
    :func:`test_spend_gate_rejects_direct_call_without_ratify`.
    """
    reason = "re-baking the committed rehearsal after the M-A/M-B/M-C fix"
    exit_code = main(
        [
            "--capture",
            "--force",
            "--force-reason",
            reason,
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    log_path = tmp_path / FORCE_REASON_LOG_FILENAME
    assert log_path.exists()
    logged = log_path.read_text(encoding="utf-8")
    assert reason in logged
    assert logged.count("\n") == 1, "one audit line for one forced capture"


def test_record_force_reason_appends_not_truncates(tmp_path: Path) -> None:
    """M-C: repeated forced overwrites keep a HISTORY of reasons -- the audit
    log is append-only, never truncated to just the latest one."""
    record_force_reason(tmp_path, reason="first forced overwrite")
    record_force_reason(tmp_path, reason="second forced overwrite")

    lines = (
        (tmp_path / FORCE_REASON_LOG_FILENAME).read_text(encoding="utf-8").splitlines()
    )
    assert len(lines) == 2
    assert "first forced overwrite" in lines[0]
    assert "second forced overwrite" in lines[1]


async def test_drifted_annotation_fails_verify(tmp_path: Path) -> None:
    """A committed side annotation is a *checked input*, not just an output:
    one that has drifted fails instead of being silently refreshed."""
    await _capture_bundle(tmp_path)
    assert await harness_verify(tmp_path) is True

    (tmp_path / PARITY_FILENAME).write_text(
        '{"geometry_checksum_match": true}\n', encoding="utf-8"
    )
    assert await harness_verify(tmp_path) is False


# --------------------------------------------------------------------------- #
# AC5 -- inner_invocations == 0 and request conformance on both channels
# --------------------------------------------------------------------------- #


async def test_verify_checks_conformance_and_no_llm(tmp_path: Path) -> None:
    """AC5: the replay channels serve committed bytes only, and the *requests*
    they were served against are compared with the committed record.

    The negative half is the point of the check: the organ's replay clients are
    **ordinal** (they serve ``recorded[i]`` without looking at what was asked),
    so a drifted prompt still replays to a green checksum. Rewriting one
    committed ``system_prompt`` is therefore invisible to every parity check and
    can only be caught by conformance.
    """
    await _capture_bundle(tmp_path)
    assert await harness_verify(tmp_path) is True

    parity = json.loads((tmp_path / PARITY_FILENAME).read_text(encoding="utf-8"))
    conformance = json.loads(
        (tmp_path / CONFORMANCE_FILENAME).read_text(encoding="utf-8")
    )
    firing = json.loads(
        (tmp_path / FIRING_ANNOTATION_FILENAME).read_text(encoding="utf-8")
    )

    assert parity["replay_touched_no_llm"] is True
    assert parity["embedding_inner_invocations"] == 0
    assert set(parity["llm_inner_invocations"]) == set(SOCIETY_LIVE_AGENT_IDS)
    assert set(parity["llm_inner_invocations"].values()) == {0}

    assert conformance["llm_requests_match"] is True
    assert conformance["embedding_requests_match"] is True
    assert conformance["self_other_segments_match"] is True
    assert conformance["excluded_fields"] == ["sampling"]
    assert "sampling" not in conformance["compared_fields"]
    # Non-vacuity: requests were actually compared on both faces, and the
    # self-other segment really was present rather than absent on both sides.
    assert (
        conformance["llm_request_count_committed"]
        == len(SOCIETY_LIVE_AGENT_IDS) * _N_TICKS
    )
    assert conformance["embedding_request_count_committed"] > 0
    assert conformance["self_other_segment_present_count_committed"] > 0

    # The firing annotation is non-gate: a settled rehearsal is a legitimate
    # outcome and is reported, never re-run until it fires.
    assert firing["hard_gate"] is False
    assert firing["verdict"] is None

    decisions_path = tmp_path / "decisions.jsonl"
    lines = decisions_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    # Each committed row is ``{"agent_id": ..., "decision": {"call": {...}}}``
    # (``society_recorded_llm_from_jsonl`` unwraps the ``"decision"`` envelope
    # before delegating to ``handoff.recorded_calls_from_jsonl``) -- the call
    # payload is nested one level deeper than a flat row would be.
    first["decision"]["call"]["system_prompt"] = "a prompt this run never composed"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    decisions_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    assert await harness_verify(tmp_path, annotation_dir=tmp_path / "ann") is False
    drifted = json.loads(
        (tmp_path / "ann" / CONFORMANCE_FILENAME).read_text(encoding="utf-8")
    )
    assert drifted["llm_requests_match"] is False
    assert drifted["llm_first_drift"] is not None


# --------------------------------------------------------------------------- #
# AC6 -- no measurement surface in the manifest, at any nesting level
# --------------------------------------------------------------------------- #


async def test_manifest_has_no_verdict_or_measurement_keys(tmp_path: Path) -> None:
    """AC6: the manifest carries no ``verdict`` and no effect / divergence /
    floor / score key anywhere in its tree.

    Three things are asserted, not one: that the walk finds nothing, that the
    walk actually descended (a checker that stopped at the top level would
    "pass" for the wrong reason), and that the same walk *does* catch a planted
    key -- so the negative assertion is falsifiable.
    """
    await _capture_bundle(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    hits, visited = _banned_keys(manifest)
    assert hits == []
    assert visited > 100, "the walk must descend into the nested blocks"

    planted = json.loads(json.dumps(manifest))
    planted["env_pins"]["nested"] = {"deeper": {"verdict": None}}
    planted_hits, _ = _banned_keys(planted)
    assert planted_hits == ["/env_pins/nested/deeper/verdict"]

    # The frozen overlay really is in the manifest (so AC6 is not passing
    # merely because nothing was attached).
    assert manifest["annotations"] == dict(SOCIETY_LIVE_CLOSURE_ANNOTATIONS)


def test_annotations_overlay_is_non_mutating() -> None:
    """The frozen pre-registration cannot be edited through a rendered manifest."""
    overlaid = attach_society_live_annotations({"run": {}})
    overlaid["annotations"]["L1"] = "tampered"
    assert SOCIETY_LIVE_CLOSURE_ANNOTATIONS["L1"] != "tampered"


# --------------------------------------------------------------------------- #
# AC7 -- pre-registered constants frozen at import, unreachable from the CLI
# --------------------------------------------------------------------------- #


def test_preregistered_constants_are_frozen() -> None:
    """AC7: N=3 / ticks=12 / 36 perturbations / seed=0 / think=False are module
    constants, and **no CLI flag can override any of them**.

    The negative half enumerates the flags a caller would reach for. Each one
    is an argparse error (``SystemExit(2)``) rather than an accepted override,
    which is the only way "frozen" is a property of the apparatus instead of a
    convention in a document.
    """
    assert SOCIETY_LIVE_AGENT_IDS == ("a_kant", "a_nietzsche", "a_rikyu")
    assert len(SOCIETY_LIVE_AGENT_IDS) == 3
    assert SOCIETY_LIVE_N_COGNITION_TICKS == 12
    assert SOCIETY_LIVE_PERTURBATION_COUNT == 36
    assert SOCIETY_LIVE_SEED == 0
    assert SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION == 20
    assert SOCIETY_LIVE_THINK is False
    assert SOCIETY_LIVE_MODEL == "qwen3:8b"
    assert SOCIETY_LIVE_EMBED_MODEL == "nomic-embed-text"
    # The perturbation budget is not a number in a docstring: the frozen plan
    # really produces 36 messages for the sealed roster and horizon.
    assert len(society_live_loop_perturbation_plan()) == SOCIETY_LIVE_PERTURBATION_COUNT

    assert set(SOCIETY_LIVE_CLOSURE_ANNOTATIONS) == {
        "L1",
        "L2",
        "L3",
        "done_formula",
        "side_files",
        "firing_annotation",
        "scope_boundary",
        "real_run_status",
        "preregistration_note",
    }
    assert "verdict" not in SOCIETY_LIVE_CLOSURE_ANNOTATIONS
    assert SOCIETY_LIVE_CLOSURE_ANNOTATIONS["done_formula"] == SOCIETY_LIVE_DONE_FORMULA
    for key in ("L1", "L2", "L3"):
        assert key in SOCIETY_LIVE_DONE_FORMULA
        lowered = SOCIETY_LIVE_CLOSURE_ANNOTATIONS[key].lower()
        for word in ("caused", "emergence", "emergent", "aha happened"):
            assert word not in lowered, f"{key} carries over-claim vocabulary: {word}"
    assert "NOT RUN" in SOCIETY_LIVE_CLOSURE_ANNOTATIONS["real_run_status"]
    boundary = SOCIETY_LIVE_CLOSURE_ANNOTATIONS["scope_boundary"].lower()
    assert "never aha, emergence, or an effect" in boundary
    assert "no live" in boundary
    assert "not a wall-clock real-time session" in boundary

    for flag, value in (
        ("--seed", "1"),
        ("--run-id", "someone-elses-run"),
        ("--cognition-ticks", "3"),
        ("--n-cognition-ticks", "3"),
        ("--physics-ticks-per-cognition", "5"),
        ("--agent-ids", "a_kant"),
        ("--perturbation-count", "3"),
        ("--think", "true"),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main(["--capture", flag, value])
        assert excinfo.value.code == 2, flag


def test_sealed_gate_rejects_off_plan_parameters() -> None:
    """AC7 (API side): even a ratified, fully pinned real run is refused when a
    parameter deviates from the pre-registration -- the frozen annotations text
    names those values, so an off-plan run would make the artifact describe
    itself falsely. An exploratory sweep needs its own pre-registration."""
    for field, off_plan in (
        ("model", "llama3:8b"),
        ("embed_model", "some-other-embed"),
        ("agent_ids", ("a_kant",)),
        ("n_cognition_ticks", 8),
        ("physics_ticks_per_cognition", 5),
        ("seed", 1),
        ("perturbation_count", 12),
    ):
        with pytest.raises(SealedParameterError):
            assert_sealed_real_run(**{**_SEALED_ARGS, field: off_plan})


# --------------------------------------------------------------------------- #
# Committed bundles (skip when absent so a bare checkout stays green)
# --------------------------------------------------------------------------- #


async def test_committed_rehearsal_bundle_verifies(tmp_path: Path) -> None:
    """L3 (cross-platform): the committed rehearsal bytes replay green on
    whatever platform runs this suite.

    On the Linux CI runner that *is* the cross-platform measurement -- and the
    honest scope of it is narrow: bytes baked under Windows/UCRT replay
    identically under glibc. It is **not** a re-bake of the capture on Linux.

    The annotations are re-derived into ``tmp_path`` and compared byte-for-byte
    rather than rewritten in place, so a drift shows up as a failure here.
    """
    if not (_REHEARSAL_DIR / "manifest.json").exists():
        pytest.skip("committed rehearsal bundle not present in this checkout")
    assert await harness_verify(_REHEARSAL_DIR, annotation_dir=tmp_path) is True
    for name in SIDE_ANNOTATION_FILENAMES:
        fresh = (tmp_path / name).read_text(encoding="utf-8")
        committed = (_REHEARSAL_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"{name} drifted from the committed annotation"


def test_committed_rehearsal_has_the_preregistered_shape() -> None:
    """The committed rehearsal is the sealed shape (so a green rehearsal verify
    is evidence about the sealed bundle) **and is honestly labelled as a
    rehearsal**: Issue 007 ran no real backend."""
    manifest_path = _REHEARSAL_DIR / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("committed rehearsal bundle not present in this checkout")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run = manifest["run"]
    pins = manifest["env_pins"]

    assert tuple(run["agent_ids"]) == SOCIETY_LIVE_AGENT_IDS
    assert run["cognition_ticks"] == SOCIETY_LIVE_N_COGNITION_TICKS
    assert (
        run["physics_ticks_per_cognition"] == SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION
    )
    assert run["seed"] == SOCIETY_LIVE_SEED
    assert pins["perturbation_count"] == SOCIETY_LIVE_PERTURBATION_COUNT
    assert pins["capture_mode"] == "scripted-rehearsal"
    assert pins["real_backend"] is False
    assert pins["think"] is False
    assert pins["wall_clock_real_time_session"] is False

    ledger = (
        (_REHEARSAL_DIR / PLANE_G_INBOUND_LEDGER_FILENAME)
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(ledger) == SOCIETY_LIVE_PERTURBATION_COUNT


async def test_committed_sealed_real_bundle_verifies(tmp_path: Path) -> None:
    """The ratified real bundle replays green through the very same Ollama-free
    verify path.

    The bundle exists: the user-ratified real spend ran on 2026-09-07 and its
    bytes are committed under ``experiments/20260907-m13-society-live/artifacts/``
    (PR #93). On the Linux CI runner this replay *is* the cross-platform
    measurement — bytes baked under Windows/UCRT verifying under glibc — and the
    same holds on the Windows CI leg added for paper 03's gate G1. Reviewers can
    close the loop themselves by running this test: ``verify`` is Ollama-free by
    construction, so it needs neither an LLM nor a GPU.

    The guard below keeps the test meaningful in a checkout that does not carry
    ``artifacts/``; it is not a statement that the run has yet to happen.
    """
    if not (_REAL_DIR / "manifest.json").exists():
        pytest.skip("sealed real bundle not present in this checkout")
    assert await harness_verify(_REAL_DIR, annotation_dir=tmp_path) is True
    manifest = json.loads((_REAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    pins = manifest["env_pins"]
    assert pins["capture_mode"] == "real"
    assert pins["real_backend"] is True
    assert pins["model"] == SOCIETY_LIVE_MODEL
    assert pins["embed_model"] == SOCIETY_LIVE_EMBED_MODEL
    for pin in ("qwen3_model_digest", "ollama_version"):
        assert pins[pin] not in ("", "unknown"), pin


# --------------------------------------------------------------------------- #
# Measurement-line non-re-entry
# --------------------------------------------------------------------------- #


def _assert_no_society_measurement_surface(tree: ast.Module) -> None:
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
            assert name.lower() not in _SOCIETY_BANNED_EXACT, name
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    assert key.value.lower() not in _SOCIETY_BANNED_EXACT, key.value


def _parse_for_guard(path: Path) -> ast.Module:
    """Parse ``path`` for the measurement guard, excluding **this test
    module's own top-level function names** from the identifier scan.

    The shared guard's ``_guard_identifiers`` bans any identifier containing a
    substring like ``verdict`` -- including a ``FunctionDef`` /
    ``AsyncFunctionDef`` **name**. That is right for the harness (it must
    genuinely define no such identifier) but self-trips on this module: a test
    named ``test_manifest_has_no_verdict_or_measurement_keys`` legitimately
    names ``verdict`` in order to assert its *absence* from the manifest
    (AC6), it does not introduce it. That is a self-reference, not the
    violation the guard exists to catch, so only this module's own top-level
    function names are blanked before the scan -- imports, variables,
    parameters, dict keys, and every other file's function names (the harness
    included) stay fully scanned. The blanking is local to this throwaway
    parse tree; it never touches the real, pytest-collected test function.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if path == _THIS_FILE:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node.name = "_self_reference_excluded_from_guard_scan"
    return tree


def test_society_live_capture_measurement_guard() -> None:
    """No measurement import / identifier / dict key / annotation filename in
    the harness or in this module. The harness is scanned with
    ``scan_strings=True`` (it is the file that *emits* side files); this module
    stays ``False`` because it legitimately names the banned tokens in order to
    build the guard."""
    for path, scan_strings in ((_SCRIPT_SRC, True), (_THIS_FILE, False)):
        tree = _parse_for_guard(path)
        assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
        _assert_no_society_measurement_surface(tree)
