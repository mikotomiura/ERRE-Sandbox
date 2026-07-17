#!/usr/bin/env python
"""aha!/DMN-ECN Phase 4b two-phase-knob live-capture CLI (real run is human-gated).

Design-copied from ``scripts/ecl_v1_live_capture.py`` (ecl_v1 stays untouched),
adapted for the λ↔two-phase knob *live activation* (FROZEN ADR
``.steering/20260717-aha-phase4b-construction-validation-live/design-final.md``,
user 裁定 = Option A / organ 無改変).

``--capture`` builds a real
:class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` (the only live
piece) plus a constant-vector mock embedding and drives ONE knob-on record-mode run
through :func:`~erre_sandbox.integration.embodied.two_phase_live.\
run_two_phase_live_capture` (``two_phase_knob=TwoPhaseKnob()``, ``deep_work``
=EVALUATION seed). The four handoff artifacts are written with the Phase 4b env-pin
overlay (base sampling + two-phase gains + α + λ₀ + decisions SHA + ``two_phase_knob:
on``) and the V1-V3 + firing-annotation observables overlay (``verdict=None``). The
sealed run itself (live Ollama, committed artifacts, WSL byte-equality) is a separate
human-gated session; importing this module opens no live connection.

``--verify`` is the companion **Ollama-free** replay-verify: it replays the committed
``decisions.jsonl`` from the knob-on **seeded** state to reproduce the committed
``ecl_trace_checksum`` (V2/V3a, ``inner_invocations == 0``) and re-render the full
artifact set — manifest included — to check every SHA-256 (V3b). It then writes the
**firing annotation** side file (:func:`two_phase_firing`, outside the manifest SHA
set): two spied replays of the committed decisions — one knob-on, one knob-off —
whose recomposed per-tick sampling disagrees by an evaluation-phase sign inversion
(the construction witness), plus the HIGH-2 pin that the committed ``call.sampling``
equals the knob-on replay sampling (the record genuinely ran knob-on).

Scope guard (design-final §7, binding, mirrors ``scripts/ecl_v1_live_capture.py``).
This is a *construction* apparatus, **NOT a measurement line**. It imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no floor /
landscape / verdict / divergence / magnitude / detectability / aha proxy statistic.
The firing annotation is a boolean/counting side file, never a Done gate.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import LIVE_MODEL
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.two_phase_live import (
    TWO_PHASE_N_COGNITION_TICKS,
    attach_two_phase_observables,
    build_two_phase_env_pins,
    evaluation_seeded_agent_state,
    run_two_phase_capture,
    run_two_phase_live_capture,
    two_phase_firing_summary,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.erre.two_phase import TwoPhaseKnob as _Knob
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.schemas import AgentState

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = (
    _REPO_ROOT
    / "experiments"
    / "20260717-aha-phase4b-construction-validation-live"
    / "artifacts"
)
_DEFAULT_RUN_ID = "aha-phase4b-two-phase"
_ANNOTATION_FILENAME = "two_phase_firing_annotation.json"


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free.

    Structurally identical to the ecl_v1 script's mock (the two scripts stay
    decoupled): only the action-LLM chat call is live in a live-capture run.
    """
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


async def capture(
    *,
    run_id: str,
    seed: int,
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
) -> tuple[EclRunResult, dict[str, str]]:
    """Drive one knob-on live-capture run and render the four handoff artifacts.

    Builds a real ``OllamaChatClient`` (the sole live piece) and a mock embedding,
    runs :func:`run_two_phase_live_capture` with ``two_phase_knob=TwoPhaseKnob()``
    (the ``deep_work``=EVALUATION seed), then renders the artifacts via ``handoff``'s
    serialisers plus the Phase 4b env-pin + observables overlay. Writes nothing to
    disk (``main`` does that).
    """
    from erre_sandbox.inference.ollama_adapter import OllamaChatClient

    now = datetime.now(UTC)
    persona = handoff.golden_persona()
    inner = OllamaChatClient(model=LIVE_MODEL)
    embedding = _mock_embedding()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        result = await run_two_phase_live_capture(
            inner_chat=inner,
            store=store,
            embedding=embedding,
            run_id=run_id,
            persona=persona,
            retrieval_now=now,
            base_ts=now,
            two_phase_knob=TwoPhaseKnob(),
            agent_state=evaluation_seeded_agent_state(),
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
    finally:
        await inner.close()
        await embedding.close()
        await store.close()

    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    decisions_sha256 = hashlib.sha256(decisions_jsonl.encode("utf-8")).hexdigest()
    env_pins = build_two_phase_env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
        base_sampling=persona.default_sampling,
        decisions_sha256=decisions_sha256,
    )
    run_config = {
        "seed": seed,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
        "k_ecl": handoff.K_ECL,
        "base_ts": now.isoformat(),
        "retrieval_now": now.isoformat(),
    }
    rendered = handoff.render_golden(result, run_config=run_config, env_pins=env_pins)
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(attach_two_phase_observables(manifest)) + "\n"
    )
    return result, rendered


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


async def _spied_replay(
    recorded: Sequence[RecordedLlmCall],
    run_config: dict[str, object],
    agent_state: AgentState,
    two_phase_knob: _Knob | None,
) -> tuple[tuple[ResolvedSampling, ...], str]:
    """Ollama-free knob-gated replay through the spy → (per-tick sampling, checksum).

    Drives :func:`run_two_phase_capture` (knob on or off) with ``agent_state`` and a
    :class:`SamplingSpyChatClient` wrapping the recorded Plane 2, so the spy captures
    the per-tick sampling the cognition cycle *recomposes* (the recorded
    ``call.sampling`` is discarded by the replay client — the reason the spy is
    mandatory).
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded))
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", spy),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
            two_phase_knob=two_phase_knob,
            seed=int(cast("int", run_config["seed"])),
            n_cognition_ticks=int(cast("int", run_config["cognition_ticks"])),
            physics_ticks_per_cognition=int(
                cast("int", run_config["physics_ticks_per_cognition"])
            ),
            k_ecl=int(cast("int", run_config["k_ecl"])),
        )
    finally:
        await embedding.close()
        await store.close()
    return spy.sampled, result.checksum


async def two_phase_firing(
    *, decisions_text: str, run_config: dict[str, object]
) -> dict[str, object]:
    """Firing annotation (non-gate, outside the manifest SHA set).

    Two Ollama-free spied replays of the same committed decisions from the
    evaluation seed — one knob-on, one knob-off — expose the recomposed per-tick
    sampling. :func:`two_phase_firing_summary` reduces them to the pure boolean/count
    witness (evaluation-phase sign inversion on >=1 λ>0 tick, both checksums equal),
    and pins that the committed ``call.sampling`` equals the knob-on replay sampling
    (the record ran knob-on). No spread / variance / floor / magnitude statistic.
    """
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)
    seed = evaluation_seeded_agent_state()
    on_sampling, on_checksum = await _spied_replay(
        recorded, run_config, seed, TwoPhaseKnob()
    )
    off_sampling, off_checksum = await _spied_replay(
        recorded, run_config, evaluation_seeded_agent_state(), None
    )
    return two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_checksum,
        off_checksum=off_checksum,
        committed_call_samplings=[c.sampling for c in recorded],
    )


async def verify(artifact_dir: Path) -> bool:
    """Ollama-free replay-verify of a committed Phase 4b bundle (V2/V3 + firing side file).

    Design-copied from ``scripts/ecl_v1_live_capture.py``'s ``verify``: the replay
    uses the knob-on **seeded** state and the manifest re-render uses the Phase 4b
    observables overlay; after the byte checks it writes the firing-annotation side
    file (:func:`two_phase_firing`, outside the manifest SHA set).
    """
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    run_config = manifest["run"]

    ok = True
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    llm = RecordReplayChatClient(recorded=recorded)
    try:
        result = await run_two_phase_capture(
            run_id=run_config["run_id"],
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=evaluation_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(run_config["retrieval_now"]),
            base_ts=datetime.fromisoformat(run_config["base_ts"]),
            two_phase_knob=TwoPhaseKnob(),
            seed=run_config["seed"],
            n_cognition_ticks=run_config["cognition_ticks"],
            physics_ticks_per_cognition=run_config["physics_ticks_per_cognition"],
            k_ecl=run_config["k_ecl"],
        )
    finally:
        await embedding.close()
        await store.close()

    # V2/V3a — inner_invocations == 0 + replay checksum byte-match.
    if llm.inner_invocations != 0:
        ok = False
        print(
            f"[verify] FAIL replay touched a live LLM ({llm.inner_invocations} calls)"
        )
    if result.checksum != manifest["replay_checksum"]:
        ok = False
        print(
            f"[verify] FAIL replay checksum {result.checksum} != "
            f"manifest {manifest['replay_checksum']}"
        )
    else:
        print(f"[verify] OK replay checksum {result.checksum}")

    # V3b — re-render (committed env_pins/run reused) → per-artifact SHA-256.
    rendered = handoff.render_golden(
        result, run_config=run_config, env_pins=manifest["env_pins"]
    )
    artifacts = {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }
    for name, committed_text in artifacts.items():
        expected = manifest["artifacts"][name]["sha256"]
        actual = hashlib.sha256(rendered[name].encode("utf-8")).hexdigest()
        if actual != expected:
            ok = False
            print(f"[verify] FAIL {name} sha256 {actual} != {expected}")
        elif rendered[name] != committed_text:  # pragma: no cover - defensive
            ok = False
            print(f"[verify] FAIL {name} byte mismatch despite matching sha256")

    # V3b (manifest.json itself): re-render through the same pipeline capture() used.
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_two_phase_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    if rerendered_manifest != manifest_text:
        ok = False
        print("[verify] FAIL manifest.json byte mismatch on re-render")
    else:
        print("[verify] OK manifest.json byte-identical re-render")

    envelopes = handoff.validate_envelope_stream(envelope_text)
    print(f"[verify] OK {len(envelopes)} envelopes schema-conformant")

    # Firing annotation (side file, outside the SHA set).
    annotation = await two_phase_firing(
        decisions_text=decisions_text, run_config=run_config
    )
    (artifact_dir / _ANNOTATION_FILENAME).write_text(
        json.dumps(annotation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "[verify] annotation "
        f"fired={annotation['evaluation_phase_sign_inversion_fired']} "
        f"witness_ticks={annotation['witness_tick_count']} "
        f"eligible_ticks={annotation['eligible_tick_count']} "
        f"checksums_match={annotation['checksums_match']} "
        f"record_knob_on_pinned={annotation['record_knob_on_pinned']} "
        f"fail_mode={annotation['fail_mode']}"
    )

    print("[verify] LIVE ARTIFACT OK" if ok else "[verify] LIVE ARTIFACT MISMATCH")
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="aha Phase 4b two-phase knob live-capture (knob active)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one knob-on record-mode run against a live Ollama + write artifacts",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed bundle + firing annotation",
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help="artifact bundle to replay-verify (--verify only)",
    )
    parser.add_argument("--run-id", default=_DEFAULT_RUN_ID)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--n-cognition-ticks", type=int, default=TWO_PHASE_N_COGNITION_TICKS
    )
    parser.add_argument(
        "--physics-ticks-per-cognition",
        type=int,
        default=DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    )
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument("--uv-lock-sha256", default="unknown")
    args = parser.parse_args(argv)

    if args.verify:
        ok = asyncio.run(verify(args.artifact_dir))
        return 0 if ok else 1

    result, rendered = asyncio.run(
        capture(
            run_id=args.run_id,
            seed=args.seed,
            n_cognition_ticks=args.n_cognition_ticks,
            physics_ticks_per_cognition=args.physics_ticks_per_cognition,
            qwen3_model_digest=args.qwen3_model_digest,
            ollama_version=args.ollama_version,
            vram_gb=args.vram_gb,
            uv_lock_sha256=args.uv_lock_sha256,
        )
    )
    _write(args.out_dir, rendered)
    print(f"[capture] wrote {len(rendered)} artifacts to {args.out_dir}")
    print(f"[capture] replay_checksum = {result.checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
