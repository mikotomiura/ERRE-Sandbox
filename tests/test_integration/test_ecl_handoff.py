"""ECL v0 cross-machine handoff tests (M13, Issue 005, design-final.md §論点5).

The handoff module (``integration/embodied/handoff.py``) turns an Issue 004
:class:`~erre_sandbox.integration.embodied.loop.EclRunResult` (consumed, never
modified) into the repo-tracked manifest + committed golden a MacBook Godot build
replays offline. These tests pin the frozen handoff contract:

* **AC1** ``test_ecl_v0_handoff_manifest_pins`` — the manifest carries the frozen
  ``SCHEMA_VERSION`` + coordinate convention (Y-up / XZ / meters / yaw=atan2) +
  the two-axis tick mapping (``physics_tick_index`` vs ``agent_tick``) + the
  determinism checklist.
* **AC2** ``test_ecl_v0_handoff_golden_sample_matches`` — replaying the committed
  golden's ``decisions.jsonl`` alone reproduces the committed manifest's
  ``replay_checksum`` byte-for-byte (the cross-machine reproducibility contract).
* **AC3** ``test_ecl_v0_envelope_conformance`` — the converter's envelope stream
  is ``ControlEnvelope``-conformant and ordered deterministically by
  ``(order_slot, agent_tick, seq)``.

A measurement-line non-re-entry guard (design §論点4) mirrors the Issue 004 loop
guard: the handoff module imports no ``evidence`` / ``spdm`` / ``runningness``
machinery and defines no floor / landscape / verdict identifier.

The LLM is the recorded Plane 2 (replay, no live Ollama); the embedding is a
constant-vector in-memory mock; sqlite-vec runs in ``:memory:``.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.loop import (
    RecordReplayChatClient,
    ecl_trace_checksum,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall

_GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ecl_v0_golden"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _offline_embedding() -> EmbeddingClient:
    """Constant-vector embedding (pinned to ``GOLDEN_EMBED_VALUE``, Ollama-free)."""
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


async def _run_golden(recorded_calls: Sequence[RecordedLlmCall]) -> EclRunResult:
    """Drive the golden ECL loop in replay mode from ``recorded_calls``."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _offline_embedding()
    llm = RecordReplayChatClient(recorded=recorded_calls)
    try:
        result = await run_ecl_loop(
            run_id=handoff.GOLDEN_RUN_ID,
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=handoff.golden_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            seed=handoff.GOLDEN_SEED,
            n_cognition_ticks=handoff.GOLDEN_N_COGNITION_TICKS,
            physics_ticks_per_cognition=handoff.GOLDEN_PHYSICS_TICKS_PER_COGNITION,
        )
    finally:
        await embedding.close()
        await store.close()
    assert llm.inner_invocations == 0, "golden replay must not touch a live LLM"
    return result


# --------------------------------------------------------------------------- #
# AC1 — manifest pins
# --------------------------------------------------------------------------- #


async def test_ecl_v0_handoff_manifest_pins() -> None:
    result = await _run_golden(handoff.golden_recorded_calls())
    artifacts = handoff.render_golden(result, env_pins={"pinned": "for-test"})
    manifest = json.loads(artifacts["manifest.json"])

    # SCHEMA_VERSION (wire) + handoff manifest version.
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["manifest_version"] == handoff.MANIFEST_SCHEMA_VERSION

    # Coordinate convention: Y-up / XZ ground / meters / yaw=atan2(dz, dx).
    coord = manifest["coordinate_convention"]
    assert coord["up_axis"] == "Y"
    assert coord["ground_plane"] == "XZ"
    assert coord["units"] == "meters"
    assert coord["yaw"] == "atan2(dz, dx)"

    # Two-axis tick mapping is explicit and separated (Codex MEDIUM-2).
    tick_mapping = manifest["tick_mapping"]
    assert "physics_tick_index" in tick_mapping
    assert "agent_tick" in tick_mapping
    assert "30 Hz" in tick_mapping["physics_tick_index"]
    assert "distinct axes" in tick_mapping["axis_separation"]

    # Determinism checklist present + non-trivial.
    checklist = manifest["determinism_checklist"]
    assert isinstance(checklist, list)
    assert len(checklist) == len(handoff.DETERMINISM_CHECKLIST)
    assert any("Plane 1 pinned" in item for item in checklist)
    assert any("reflection disabled" in item for item in checklist)

    # Run metadata + authoritative checksum + integrity hashes.
    assert manifest["run"]["run_id"] == handoff.GOLDEN_RUN_ID
    assert manifest["run"]["seed"] == handoff.GOLDEN_SEED
    assert manifest["run"]["cognition_ticks"] == handoff.GOLDEN_N_COGNITION_TICKS
    assert manifest["replay_checksum"] == result.checksum
    assert set(manifest["artifacts"]) == {
        "ecl_trace.jsonl",
        "decisions.jsonl",
        "envelope_stream.jsonl",
    }
    # Canonical JSON rules pinned (byte-reproducibility contract).
    assert manifest["canonical_json_rules"]["sort_keys"] is True
    assert manifest["canonical_json_rules"]["allow_nan"] is False


# --------------------------------------------------------------------------- #
# AC2 — committed golden replays to a byte-identical checksum
# --------------------------------------------------------------------------- #


async def test_ecl_v0_handoff_golden_sample_matches() -> None:
    manifest = json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    decisions_text = (_GOLDEN_DIR / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (_GOLDEN_DIR / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (_GOLDEN_DIR / "envelope_stream.jsonl").read_text(encoding="utf-8")

    # Replay from the committed decisions ALONE ⇒ byte-identical checksum.
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)
    assert len(recorded) == handoff.GOLDEN_N_COGNITION_TICKS
    result = await _run_golden(recorded)
    assert result.checksum == manifest["replay_checksum"]

    # The committed ecl_trace.jsonl reloads to the same checksum (self-consistent).
    reloaded_rows = handoff.trace_rows_from_jsonl(trace_text)
    assert ecl_trace_checksum(reloaded_rows) == manifest["replay_checksum"]

    # Re-rendering the golden from the replayed result reproduces the trace and the
    # envelope stream byte-for-byte (determinism, no drift). ``decisions.jsonl`` is
    # NOT asserted byte-stable: its ``envelope_provenance`` embeds the AgentUpdate
    # ``agent_state.wall_clock`` and the ReasoningTrace ``created_at`` — unpinned
    # ``_utc_now`` snapshot fields in the frozen I3/I4 record path (not the
    # sent_at-pinned wire clock). They never enter the reproducibility checksum and
    # are filtered out of ``envelope_stream.jsonl`` (agent_update / reasoning_trace
    # are not replayable kinds), so the authoritative contract (replay → checksum)
    # and the Godot replay stream stay deterministic. The committed
    # ``decisions.jsonl`` therefore carries a one-time bake-time provenance stamp.
    rendered = handoff.render_golden(result, env_pins=manifest["env_pins"])
    assert rendered["ecl_trace.jsonl"] == trace_text
    assert rendered["envelope_stream.jsonl"] == envelope_text

    # Per-artifact SHA-256 integrity hashes match the committed files (the
    # committed manifest and committed artifacts agree).
    assert _sha256(trace_text) == manifest["artifacts"]["ecl_trace.jsonl"]["sha256"]
    assert _sha256(decisions_text) == manifest["artifacts"]["decisions.jsonl"]["sha256"]
    assert (
        _sha256(envelope_text)
        == manifest["artifacts"]["envelope_stream.jsonl"]["sha256"]
    )


# --------------------------------------------------------------------------- #
# AC3 — converter output is ControlEnvelope-conformant + deterministically ordered
# --------------------------------------------------------------------------- #


async def test_ecl_v0_envelope_conformance() -> None:
    result = await _run_golden(handoff.golden_recorded_calls())
    stream = handoff.build_envelope_stream(result)

    assert stream, "converter produced no envelopes"
    # One agent × 8 ticks × 3 replayable kinds (speech/move/animation).
    assert len(stream) == handoff.GOLDEN_N_COGNITION_TICKS * 3

    # Ordering is deterministic: sorted by (order_slot, agent_tick, seq).
    keys = [(e["order_slot"], e["agent_tick"], e["seq"]) for e in stream]
    assert keys == sorted(keys)
    # Single agent → order_slot 0 everywhere.
    assert {e["order_slot"] for e in stream} == {0}

    # Every wrapped envelope validates against the ControlEnvelope union and is a
    # replayable kind.
    text = handoff.envelope_stream_to_jsonl(stream)
    envelopes = handoff.validate_envelope_stream(text)
    assert len(envelopes) == len(stream)
    kinds = {e["envelope"]["kind"] for e in stream}
    assert kinds <= set(handoff.ENVELOPE_STREAM_KINDS)
    # The move envelope carries a history-dependent, locate_zone-consistent target
    # (not the default spawn): the converter faithfully forwards the ECL target.
    move_targets = [
        e["envelope"]["target"] for e in stream if e["envelope"]["kind"] == "move"
    ]
    assert move_targets, "no move envelope in the stream"
    assert all(t["zone"] == "peripatos" for t in move_targets)


# --------------------------------------------------------------------------- #
# Measurement-line non-re-entry (import / output guard, not a word ban)
# --------------------------------------------------------------------------- #


_HANDOFF_TREE = ast.parse(Path(handoff.__file__).read_text(encoding="utf-8"))


def test_ecl_handoff_no_measurement_imports() -> None:
    """The handoff module imports no measurement machinery (design §論点4)."""
    banned_prefix = ("erre_sandbox.evidence",)
    banned_sub = ("spdm", "runningness")
    for node in ast.walk(_HANDOFF_TREE):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(banned_prefix), node.module
            assert not any(s in node.module for s in banned_sub), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_prefix), alias.name
                assert not any(s in alias.name for s in banned_sub), alias.name


def test_ecl_handoff_no_measurement_output_identifiers() -> None:
    """No floor / landscape / verdict output identifier is defined (docstrings may
    still name them). Identifier-level, mirroring the Issue 004 loop guard."""
    banned = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
    for node in ast.walk(_HANDOFF_TREE):
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
            assert not any(tok in low for tok in banned), name
