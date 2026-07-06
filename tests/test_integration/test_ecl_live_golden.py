"""ECL v0 Ollama-free live-capture replay-verify apparatus — Issue 002
(``loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md``,
``.steering/20260706-ecl-v0-live-run/decisions.md`` D-5/D-6/D-8).

Builds the apparatus that replay-verifies a *committed* ECL v0 embodiment
artifact **without Ollama**: replaying the recorded Plane 2
(``decisions.jsonl``) reproduces the committed ``manifest.json``'s
``ecl_trace_checksum`` byte-for-byte (O3a), and re-rendering the full
artifact set from the same replayed result reproduces every per-artifact
SHA-256 (O3b). O5 (D-5 refinement) is an **annotation** count, never a hard
green gate (Codex TASK-PRE HIGH-2 — an autonomous O5 gate would tune-to-pass
the loop toward it).

This module replay-verifies Issue 003's committed live artifact bundle
(``experiments/20260706-ecl-v0-live-capture/artifacts/``, Issue 004 landed the
switch from the earlier synthetic-golden template). The artifact directory is
the single module constant :data:`_GOLDEN_DIR`, and every test below is
written against the *committed manifest's* run config (never module-level
golden constants) so it generalises unchanged to a run with a different tick
count / seed / clock (D-1: the live run is 32 ticks, not the synthetic
golden's 8).

Scope guard (design-final.md §論点4, binding, mirrors ``test_ecl_handoff.py``).
This is a *construction* apparatus, **NOT a measurement line**. It imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no
floor / landscape / verdict / divergence statistic —
:func:`test_live_golden_measurement_guard` pins this by AST-scanning both this
module and ``scripts/ecl_v0_live_capture.py``'s ``--verify`` apparatus.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import (
    LIVE_O5_MIN_TICKS,
    attach_live_observables,
)
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient, run_ecl_loop
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall

# The committed sealed live-capture artifact bundle (Issue 004 repointed this
# at ``experiments/20260706-ecl-v0-live-capture/artifacts`` once the sealed
# live run was committed; the name is kept for git-blame continuity with the
# earlier synthetic-golden template).
_GOLDEN_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "20260706-ecl-v0-live-capture"
    / "artifacts"
)


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free, mirrors ``ecl_v0_golden.py``)."""
    vec = [handoff.GOLDEN_EMBED_VALUE] * EmbeddingClient.DEFAULT_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


async def _replay_from_manifest(
    recorded: Sequence[RecordedLlmCall], run_config: dict[str, object]
) -> tuple[EclRunResult, RecordReplayChatClient]:
    """Reconstruct + drive a run from committed decisions + the manifest's run config.

    Uses the golden persona/agent-state fixture (D-2: the sealed live run uses
    the same single kant persona/agent as the synthetic golden — both
    ``scripts/ecl_v0_golden.py`` and ``scripts/ecl_v0_live_capture.py`` build
    their agent from ``handoff.golden_agent_state()``/``golden_persona()``) but
    drives ``run_ecl_loop`` with the **committed manifest's** seed / tick count
    / clocks — never a module-level golden constant — so this helper
    generalises unchanged once Issue 004 repoints :data:`_GOLDEN_DIR` at a live
    artifact with a different run config (D-1: 32 ticks, not 8).
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    llm = RecordReplayChatClient(recorded=recorded)
    try:
        result = await run_ecl_loop(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=handoff.golden_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
            seed=int(run_config["seed"]),  # type: ignore[arg-type]
            n_cognition_ticks=int(run_config["cognition_ticks"]),  # type: ignore[arg-type]
            physics_ticks_per_cognition=int(  # type: ignore[arg-type]
                run_config["physics_ticks_per_cognition"]
            ),
            k_ecl=int(run_config["k_ecl"]),  # type: ignore[arg-type]
        )
    finally:
        await embedding.close()
        await store.close()
    return result, llm


def _read_committed() -> tuple[dict[str, object], str, str, str]:
    """Read the committed manifest + the three data artifacts as text."""
    manifest = json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    decisions_text = (_GOLDEN_DIR / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (_GOLDEN_DIR / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (_GOLDEN_DIR / "envelope_stream.jsonl").read_text(encoding="utf-8")
    return manifest, decisions_text, trace_text, envelope_text


def _read_manifest_text() -> str:
    """Read the committed ``manifest.json`` as raw text (byte-comparison base)."""
    return (_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# I4-G1 / O3a — committed decisions alone replay to a byte-identical checksum
# --------------------------------------------------------------------------- #


async def test_live_golden_replay_checksum_matches() -> None:
    manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    result, llm = await _replay_from_manifest(recorded, manifest["run"])  # type: ignore[arg-type]

    assert llm.inner_invocations == 0, (
        "O3a: replaying the committed decisions must never touch a live LLM"
    )
    assert result.checksum == manifest["replay_checksum"], (
        "O3a: replay-only reconstruction must reproduce the committed "
        "manifest's replay_checksum byte-for-byte"
    )


# --------------------------------------------------------------------------- #
# I4-G2 / O3b — same raw Plane 2 re-renders the artifact set to the same SHA
# --------------------------------------------------------------------------- #


async def test_live_golden_artifact_rerender_sha() -> None:
    manifest, decisions_text, trace_text, envelope_text = _read_committed()
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    result, _llm = await _replay_from_manifest(recorded, manifest["run"])  # type: ignore[arg-type]

    # Codex TASK-PRE MEDIUM-2: re-render reusing the COMMITTED manifest's
    # env_pins/run block — never a fresh handoff.render_golden(env_pins=None,
    # run_config=None) capture, which would snapshot *this* machine's
    # python/package versions and drift manifest bytes across runners.
    rendered = handoff.render_golden(
        result,
        run_config=manifest["run"],  # type: ignore[arg-type]
        env_pins=manifest["env_pins"],  # type: ignore[arg-type]
    )

    committed = {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    for name, committed_text in committed.items():
        expected_sha = artifacts[name]["sha256"]
        actual_sha = hashlib.sha256(rendered[name].encode("utf-8")).hexdigest()
        assert actual_sha == expected_sha, f"{name} sha256 mismatch"
        # Byte-identical, not merely hash-identical (a stronger reproduction
        # witness than SHA-256 equality alone).
        assert rendered[name] == committed_text, f"{name} byte mismatch"

    # manifest.json itself (Codex TASK-POST HIGH-1): the three per-artifact
    # SHA-256 checks above never touch the committed manifest — a
    # drifted/stale manifest (env_pins / observables overlay / replay_checksum
    # / artifact SHA fields) would otherwise vacuously pass this test. Re-render
    # the manifest through the exact same pipeline
    # ``scripts/ecl_v0_live_capture.py``'s ``capture()`` used (``render_golden``
    # + ``attach_live_observables`` + ``canonical_dumps``), reusing the
    # committed ``env_pins``/``run`` block (same MEDIUM-2 rationale as above),
    # and assert byte-identity against the committed ``manifest.json``.
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_live_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    assert rerendered_manifest == _read_manifest_text(), "manifest.json byte mismatch"


# --------------------------------------------------------------------------- #
# I4-G3 / O5 — parsed-history-dependent-action count (annotation, not a gate)
# --------------------------------------------------------------------------- #


def test_live_golden_parsed_history_dependent_action(tmp_path: Path) -> None:
    """Count + record O5 ticks — a construction-validity annotation, never a
    hard green/red condition (D-5, Codex TASK-PRE HIGH-2).

    O5 = ``llm_status == "ok"`` and ``plan is not None`` and the MoveMsg
    ``resolved_from == "memory_centroid"``: the tick is judged to have parsed a
    real plan that drove a history-dependent move. ``count == 0`` on this
    synthetic golden template would be a valid recorded outcome (a
    construction-validity branch for human judgement, Execution Result), not a
    test failure — so this test asserts only that the recording mechanism ran
    and persisted a well-formed non-negative count, never ``count >=
    LIVE_O5_MIN_TICKS``.
    """
    _manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
    decisions = [
        json.loads(line) for line in decisions_text.splitlines() if line.strip()
    ]

    count = sum(
        1
        for d in decisions
        if d["llm_status"] == "ok"
        and d["plan"] is not None
        and d["move_decision"] is not None
        and d["move_decision"]["resolved_from"] == "memory_centroid"
    )

    annotation = {
        "o5_parsed_history_dependent_action_count": count,
        "o5_min_ticks_first_contact_threshold": LIVE_O5_MIN_TICKS,
        "hard_gate": False,
        "note": (
            "annotation only (D-5); count>=threshold is a human-judgement "
            "construction-validity branch, not an autonomous pass/fail"
        ),
    }
    annotation_path = tmp_path / "o5_annotation.json"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")

    recorded_annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    o5_count = recorded_annotation["o5_parsed_history_dependent_action_count"]
    assert isinstance(o5_count, int)
    assert o5_count >= 0
    assert recorded_annotation["hard_gate"] is False


# --------------------------------------------------------------------------- #
# I4-G4 — measurement-line non-re-entry guard
# --------------------------------------------------------------------------- #

_THIS_FILE = Path(__file__)
_LIVE_CAPTURE_FILE = (
    Path(__file__).resolve().parents[2] / "scripts" / "ecl_v0_live_capture.py"
)

_BANNED_IMPORT_PREFIX = ("erre_sandbox.evidence",)
_BANNED_IMPORT_SUB = ("spdm", "runningness")
_BANNED_IDENTIFIER = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")


def _assert_no_measurement_surface(tree: ast.Module) -> None:
    """Mirror ``test_ecl_handoff.py``'s guards: no measurement import/identifier."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(_BANNED_IMPORT_PREFIX), node.module
            assert not any(s in node.module for s in _BANNED_IMPORT_SUB), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(_BANNED_IMPORT_PREFIX), alias.name
                assert not any(s in alias.name for s in _BANNED_IMPORT_SUB), alias.name
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
            low = name.lower()
            assert not any(tok in low for tok in _BANNED_IDENTIFIER), name


def test_live_golden_measurement_guard() -> None:
    """The replay-verify apparatus computes/emits no floor/landscape/verdict.

    Scans both this test module and ``scripts/ecl_v0_live_capture.py`` (the
    ``--verify`` CLI apparatus it exercises indirectly via ``repro.sh``) — the
    same identifier-level guard ``test_ecl_handoff.py`` applies to
    ``handoff.py`` (design §論点4 non-re-entry, holding intact)."""
    for path in (_THIS_FILE, _LIVE_CAPTURE_FILE):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _assert_no_measurement_surface(tree)
