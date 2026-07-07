"""ECL v1 committed-bundle replay-verify — the sealed live run's permanent CI guard.

Companion to the in-memory synthetic apparatus tests in
``test_ecl_v1_locomotion.py`` (which prove the mechanism with a mock plan and no
committed bundle). This module replay-verifies the **committed** ECL v1 sealed
live-capture artifact bundle
(``experiments/20260707-ecl-v1-locomotion/artifacts/``, the I3 sealed run against
real ``qwen3:8b`` with the locomotion→sampling channel active), so a Linux CI
runner re-derives every reproducibility invariant the sealed run recorded —
cross-platform (O3a/O3b of the v0 lineage, V3a/V3b here).

Design-copied from ``test_ecl_live_golden.py`` (the v0 committed-bundle test; v0
stays untouched, §H), with the v1 adaptations the FROZEN ADR
``.steering/20260707-ecl-v1-adr/design-final.md`` mandates:

* **Codex MEDIUM-2** — the replay drives the **seeded** state
  (:func:`locomotion_seeded_agent_state`), never the locomotion-null golden: the
  committed ``envelope_provenance`` carries the seeded ``locomotion.lam``, so a
  locomotion-null replay would not reproduce the committed artifact SHAs.
* the manifest re-render goes through :func:`attach_live_v1_observables` (the v1
  observables overlay), matching the pipeline ``scripts/ecl_v1_live_capture.py``'s
  ``capture()`` used.
* **V4a/V4b** channel-active counts are recorded as **annotations** (non-gate,
  §F), mirroring how the v0 O5 test recorded its count: the committed bundle's
  reproducibility (V2/V3) is the hard gate; the channel-firing thresholds are
  never a CI pass/fail (tune-to-pass closure). ``checksums_match`` *is* asserted
  — the two spied replays' geometry checksum must agree (an unperturbed-kinematics
  reproducibility invariant, not a channel-firing threshold).

Scope guard (§F/§G, binding — mirrors ``test_ecl_v1_locomotion.py``). This is a
*construction* apparatus, **NOT a measurement line — final judgement は holding**.
It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
computes/emits no floor / landscape / verdict / divergence statistic —
:func:`test_v1_live_golden_measurement_guard` AST-scans this module and
``scripts/ecl_v1_live_capture.py``'s ``--verify`` apparatus with the enhanced
3-hole guard (Codex HIGH-2).
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
from erre_sandbox.integration.embodied.live_v1 import (
    SamplingSpyChatClient,
    attach_live_v1_observables,
    locomotion_seeded_agent_state,
)
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient, run_ecl_loop
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from tests.test_integration._measurement_guard import (
    assert_no_measurement_surface_v1,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.schemas import AgentState

# The committed sealed v1 live-capture artifact bundle (I3).
_GOLDEN_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "20260707-ecl-v1-locomotion"
    / "artifacts"
)


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free, mirrors ``ecl_v1_live_capture.py``)."""
    vec = [0.01] * EmbeddingClient.DEFAULT_DIM

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


def _q(s: ResolvedSampling) -> tuple[float, float, float]:
    """6-decimal quantised sampling triple (the cross-platform comparison unit)."""
    return (round(s.temperature, 6), round(s.top_p, 6), round(s.repeat_penalty, 6))


async def _replay_from_manifest(
    recorded: Sequence[RecordedLlmCall],
    run_config: dict[str, object],
    agent_state: AgentState,
    *,
    spy: bool = False,
) -> tuple[EclRunResult, RecordReplayChatClient | SamplingSpyChatClient]:
    """Reconstruct + drive a run from committed decisions + the manifest's run config.

    Drives ``run_ecl_loop`` with the **committed manifest's** seed / tick count /
    clocks — never a module-level constant — so this helper is agnostic to the
    committed run's shape. Codex MEDIUM-2: the ``agent_state`` is the **seeded**
    locomotion state, so the committed ``envelope_provenance.locomotion.lam`` is
    reproduced. Optionally wraps the replay client in the sampling-spy (Codex
    HIGH-1) to observe the recomposed per-tick sampling for the V4 annotation.
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    inner = RecordReplayChatClient(recorded=recorded)
    llm: RecordReplayChatClient | SamplingSpyChatClient = (
        SamplingSpyChatClient(inner) if spy else inner
    )
    try:
        result = await run_ecl_loop(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=llm,  # type: ignore[arg-type]
            agent_state=agent_state,
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
# V2 / V3a — committed decisions replay (seeded state) to a byte-identical checksum
# --------------------------------------------------------------------------- #


async def test_v1_live_golden_replay_checksum_matches() -> None:
    """V2/V3a: the committed decisions replay from the SEEDED state to the
    committed ``replay_checksum``, byte-for-byte, touching no live LLM."""
    manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    result, llm = await _replay_from_manifest(
        recorded, manifest["run"], locomotion_seeded_agent_state()
    )

    assert llm.inner_invocations == 0, (
        "V2: replaying the committed decisions must never touch a live LLM"
    )
    assert result.checksum == manifest["replay_checksum"], (
        "V2/V3a: seeded replay-only reconstruction must reproduce the committed "
        "manifest's replay_checksum byte-for-byte"
    )


# --------------------------------------------------------------------------- #
# V3b — same raw Plane 2 re-renders the artifact set + manifest to the same SHA
# --------------------------------------------------------------------------- #


async def test_v1_live_golden_artifact_rerender_sha() -> None:
    """V3b: re-rendering from the seeded replay reproduces every artifact SHA-256
    and the manifest byte-for-byte (the new byte-change points — per-tick
    ``call.sampling`` and the envelope's ``locomotion.lam`` — are absorbed by the
    6-decimal quantisation)."""
    manifest, decisions_text, trace_text, envelope_text = _read_committed()
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    result, _llm = await _replay_from_manifest(
        recorded, manifest["run"], locomotion_seeded_agent_state()
    )

    # Reuse the COMMITTED manifest's env_pins/run block — never a fresh capture,
    # which would snapshot this machine's package versions and drift the bytes.
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
        # Byte-identical, not merely hash-identical (a stronger witness).
        assert rendered[name] == committed_text, f"{name} byte mismatch"

    # manifest.json itself: re-render through the exact same pipeline
    # ``ecl_v1_live_capture.py``'s ``capture()`` used (render_golden +
    # attach_live_v1_observables + canonical_dumps), reusing the committed
    # env_pins/run block, and assert byte-identity — so a drifted/stale manifest
    # (env_pins / v1 observables overlay / replay_checksum / artifact SHA fields)
    # cannot vacuously pass the three per-artifact checks above.
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_live_v1_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    assert rerendered_manifest == _read_manifest_text(), "manifest.json byte mismatch"


# --------------------------------------------------------------------------- #
# V4a/V4b — channel-active annotation from the committed bundle (non-gate count)
# --------------------------------------------------------------------------- #


async def test_v1_live_golden_channel_activation_annotation(tmp_path: Path) -> None:
    """Record V4a/V4b from the committed bundle — a channel-active *annotation*,
    never a hard green/red threshold (§F, mirrors the v0 O5 annotation test).

    Two Ollama-free spied replays of the committed decisions — seeded vs
    locomotion-null — expose the recomposed per-tick sampling. V4a = the distinct
    per-tick sampling count of the seeded replay; V4b = the number of ticks whose
    6-decimal sampling differs between the two replays. Both are recorded as a
    non-negative count with ``hard_gate == False`` — the channel-firing thresholds
    (V4a > 1 / V4b >= 1) are a human-judgement GO branch, not a CI pass/fail
    (tune-to-pass closure). ``checksums_match`` **is** asserted: the two replays'
    geometry checksum must agree (unperturbed-kinematics reproducibility invariant,
    not a channel-firing threshold, §F).
    """
    manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    r_seeded, spy_seeded = await _replay_from_manifest(
        recorded, manifest["run"], locomotion_seeded_agent_state(), spy=True
    )
    r_null, spy_null = await _replay_from_manifest(
        recorded, manifest["run"], handoff.golden_agent_state(), spy=True
    )
    assert isinstance(spy_seeded, SamplingSpyChatClient)
    assert isinstance(spy_null, SamplingSpyChatClient)

    seeded_sampling = [_q(s) for s in spy_seeded.sampled]
    null_sampling = [_q(s) for s in spy_null.sampled]
    v4a_distinct = len(set(seeded_sampling))
    v4b_modulated = sum(
        1
        for seeded_tick, null_tick in zip(seeded_sampling, null_sampling, strict=True)
        if seeded_tick != null_tick
    )

    # Unperturbed-kinematics reproducibility invariant (asserted, not a threshold).
    assert r_seeded.checksum == r_null.checksum, (
        "both spied replays' geometry checksum must agree (kinematics are "
        "sampling-independent, §E)"
    )

    annotation = {
        "v4a_distinct_sampling_count": v4a_distinct,
        "v4b_modulated_tick_count": v4b_modulated,
        "checksums_match": r_seeded.checksum == r_null.checksum,
        "hard_gate": False,
        "note": (
            "channel-active annotation (non-gate, §F); V4a>1 / V4b>=1 is a "
            "human-judgement GO branch, not an autonomous pass/fail"
        ),
    }
    annotation_path = tmp_path / "channel_activation.json"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")

    recorded_annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    assert isinstance(recorded_annotation["v4a_distinct_sampling_count"], int)
    assert recorded_annotation["v4a_distinct_sampling_count"] >= 1
    assert isinstance(recorded_annotation["v4b_modulated_tick_count"], int)
    assert recorded_annotation["v4b_modulated_tick_count"] >= 0
    assert recorded_annotation["hard_gate"] is False


# --------------------------------------------------------------------------- #
# V5 — parsed-history-dependent-action count (annotation, not a gate)
# --------------------------------------------------------------------------- #


def test_v1_live_golden_parsed_history_dependent_action(tmp_path: Path) -> None:
    """Count + record V5 ticks from the committed bundle — a construction-validity
    annotation, never a hard green/red condition (§F, mirrors the v0 O5 test).

    V5 = ``llm_status == "ok"`` and ``plan is not None`` and the MoveMsg
    ``resolved_from == "memory_centroid"``. ``count == 0`` would be a valid
    recorded outcome (D1 diagnostic branch for human judgement), not a test
    failure — so this asserts only that the recording mechanism ran and persisted
    a well-formed non-negative count.
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
        "v5_parsed_history_dependent_action_count": count,
        "hard_gate": False,
        "note": (
            "annotation only (§F); count>=1 is a first-contact existence proof "
            "for human judgement, not an autonomous pass/fail"
        ),
    }
    annotation_path = tmp_path / "v5_annotation.json"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")

    recorded_annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    v5_count = recorded_annotation["v5_parsed_history_dependent_action_count"]
    assert isinstance(v5_count, int)
    assert v5_count >= 0
    assert recorded_annotation["hard_gate"] is False


# --------------------------------------------------------------------------- #
# Committed side-file structural integrity (Codex LOW-1) — non-gate
# --------------------------------------------------------------------------- #


def test_v1_live_golden_committed_annotation_wellformed() -> None:
    """The committed ``channel_activation_annotation.json`` side file is
    well-formed — a stale/malformed guard, still non-gate (Codex LOW-1).

    The V4a/V4b annotation is committed alongside the bundle (outside the manifest
    SHA set), so a drifted or truncated side file would otherwise ship unnoticed.
    This asserts the key set, the reproducibility-invariant ``checksums_match is
    True`` (the two spied replays' geometry must agree — see
    :func:`test_v1_live_golden_channel_activation_annotation`) and ``hard_gate is
    False`` (the non-gate contract, §F), and that the two counts are non-negative
    ints — never the channel-firing *thresholds* (V4a > 1 / V4b >= 1), which stay
    a human-judgement GO branch, not a CI pass/fail (tune-to-pass closure).
    """
    annotation = json.loads(
        (_GOLDEN_DIR / "channel_activation_annotation.json").read_text(encoding="utf-8")
    )
    assert set(annotation) >= {
        "v4a_distinct_sampling_count",
        "v4b_modulated_tick_count",
        "checksums_match",
        "hard_gate",
    }
    assert annotation["hard_gate"] is False
    assert annotation["checksums_match"] is True
    assert isinstance(annotation["v4a_distinct_sampling_count"], int)
    assert annotation["v4a_distinct_sampling_count"] >= 0
    assert isinstance(annotation["v4b_modulated_tick_count"], int)
    assert annotation["v4b_modulated_tick_count"] >= 0


# --------------------------------------------------------------------------- #
# Measurement-line non-re-entry guard (enhanced 3-hole guard, Codex HIGH-2, §G)
# --------------------------------------------------------------------------- #

_THIS_FILE = Path(__file__)
_V1_SCRIPT_SRC = (
    Path(__file__).resolve().parents[2] / "scripts" / "ecl_v1_live_capture.py"
)


def test_v1_live_golden_measurement_guard() -> None:
    """The committed-bundle replay-verify computes/emits no floor/landscape/verdict.

    Scans this test module and ``scripts/ecl_v1_live_capture.py`` (the ``--verify``
    apparatus exercised indirectly via ``repro.sh``) with the shared enhanced
    3-hole guard (§G non-re-entry, holding intact)."""
    for path, scan_strings in ((_THIS_FILE, False), (_V1_SCRIPT_SRC, True)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
