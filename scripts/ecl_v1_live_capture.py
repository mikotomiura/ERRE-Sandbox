#!/usr/bin/env python
"""ECL v1 live-capture CLI — locomotion channel active (real run is I3).

Design-copied from ``scripts/ecl_v0_live_capture.py`` (v0 stays untouched, §H),
adapted for the ECL v1 locomotion→sampling channel activation (FROZEN ADR
``.steering/20260707-ecl-v1-adr/design-final.md`` §B/§E/§F/§G).

``--capture`` builds a real
:class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` (the only live
piece) plus a constant-vector mock embedding and drives one record-mode run
through :func:`~erre_sandbox.integration.embodied.live_v1.run_live_capture_v1`
— i.e. the untouched v0 ``run_live_capture`` seeded with a non-``None``
``LocomotionState(lam=λ₀)`` via the existing ``agent_state`` argument. The four
handoff artifacts are written into ``--out-dir`` with the v1 env-pin overlay
(base sampling + gains + α + λ₀ + decisions SHA, Codex MEDIUM-3) and the v1
observables overlay (V1-V5, ``done_formula = V1∧V2∧V3a∧V3b``, ``verdict = None``).
The sealed run itself (live Ollama, committed artifacts, WSL byte-equality) is
I3, a separate human-gated session; importing this module opens no live
connection.

``--verify`` is the companion **Ollama-free** replay-verify: it replays the
committed ``decisions.jsonl`` from the **seeded** state (Codex MEDIUM-2 — the
committed ``envelope_provenance`` carries the seeded ``locomotion.lam``, so a
locomotion-null replay would not reproduce it) to reproduce the committed
``ecl_trace_checksum`` (V2/V3a, ``inner_invocations == 0``) and re-render the
full artifact set — manifest included — to check every SHA-256 (V3b). It then
writes the **channel-active annotation** side file (:func:`channel_activation`,
outside the manifest SHA set): the V4a distinct per-tick sampling count and the
V4b seeded-vs-null modulated-tick count, both observed through the
:class:`~erre_sandbox.integration.embodied.live_v1.SamplingSpyChatClient`
(Codex HIGH-1 — the recorded ``call.sampling`` is identical across the two
replays, so the recomposed per-tick sampling is only visible at the spy).

Scope guard (§F/§G, binding, mirrors ``scripts/ecl_v0_live_capture.py``). This
is a *construction* apparatus, **NOT a measurement line**. It imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no floor /
landscape / final statistic. V4a/V4b are boolean/counting annotations, never a
Done gate and never a measurement statistic.
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

from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import LIVE_MODEL
from erre_sandbox.integration.embodied.live_v1 import (
    LIVE_V1_N_COGNITION_TICKS,
    SamplingSpyChatClient,
    attach_live_v1_observables,
    build_live_v1_env_pins,
    locomotion_seeded_agent_state,
    run_live_capture_v1,
)
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.schemas import AgentState

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = (
    _REPO_ROOT / "experiments" / "20260707-ecl-v1-locomotion" / "artifacts"
)
_DEFAULT_RUN_ID = "ecl-v1-locomotion"
_ANNOTATION_FILENAME = "channel_activation_annotation.json"


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free.

    Independent of ``scripts.ecl_v0_live_capture._mock_embedding`` (the two
    scripts stay decoupled) but structurally identical: only the action-LLM chat
    call is live in a live-capture run."""
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


def _quant(s: ResolvedSampling) -> tuple[float, float, float]:
    """6-decimal quantised sampling triple (cross-platform comparison unit)."""
    return (round(s.temperature, 6), round(s.top_p, 6), round(s.repeat_penalty, 6))


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
    """Drive one v1 live-capture run and render the four handoff artifacts.

    Builds a real ``OllamaChatClient`` (the sole live piece) and a mock
    embedding, runs :func:`run_live_capture_v1` (seeded locomotion state), then
    renders the artifacts via ``handoff``'s serialisers plus the v1 env-pin +
    observables overlay. Writes nothing to disk (``main`` does that)."""
    from erre_sandbox.inference.ollama_adapter import OllamaChatClient

    now = datetime.now(UTC)
    persona = handoff.golden_persona()
    inner = OllamaChatClient(model=LIVE_MODEL)
    embedding = _mock_embedding()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        result = await run_live_capture_v1(
            inner_chat=inner,
            store=store,
            embedding=embedding,
            run_id=run_id,
            persona=persona,
            retrieval_now=now,
            base_ts=now,
            agent_state=locomotion_seeded_agent_state(),
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
    finally:
        await inner.close()
        await embedding.close()
        await store.close()

    # The v1 env pins record the *inputs* to every per-tick sampling (base +
    # gains + α + λ₀) plus the SHA of decisions.jsonl (whose call.sampling column
    # is the recorded, λ-modulated sampling), never a single resolved sampling
    # (Codex MEDIUM-3). Compute the decisions SHA on the same bytes render_golden
    # will emit.
    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    decisions_sha256 = hashlib.sha256(decisions_jsonl.encode("utf-8")).hexdigest()
    env_pins = build_live_v1_env_pins(
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
        handoff.canonical_dumps(attach_live_v1_observables(manifest)) + "\n"
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
) -> tuple[tuple[tuple[float, float, float], ...], str]:
    """Ollama-free replay through the sampling-spy → (per-tick sampling, checksum).

    Drives the real loop with ``agent_state`` (seeded or locomotion-null) and a
    :class:`SamplingSpyChatClient` wrapping the recorded Plane 2, so the spy
    captures the per-tick sampling the cognition cycle *recomposes* (the recorded
    ``call.sampling`` is discarded by the replay client, Codex HIGH-1)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded))
    try:
        result = await run_ecl_loop(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", spy),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
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
    return tuple(_quant(s) for s in spy.sampled), result.checksum


async def channel_activation(
    *, decisions_text: str, run_config: dict[str, object]
) -> dict[str, object]:
    """V4a/V4b channel-active annotation (non-gate, outside the manifest SHA set).

    Two Ollama-free spied replays of the same committed decisions — one seeded,
    one locomotion-null — expose the recomposed per-tick sampling. V4a = the
    distinct-value count of the seeded per-tick sampling (>1 ⇒ λ actually
    advanced). V4b = the number of ticks whose 6-decimal sampling differs between
    the seeded and null replays (≥1 ⇒ the channel actually modulated), with both
    replays' geometry checksum equal (unperturbed kinematics). Pure boolean/
    counting; no spread / variance / floor / landscape statistic (§F/§G)."""
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)
    seeded_sampling, seeded_checksum = await _spied_replay(
        recorded, run_config, locomotion_seeded_agent_state()
    )
    null_sampling, null_checksum = await _spied_replay(
        recorded, run_config, handoff.golden_agent_state()
    )
    v4a_distinct = len(set(seeded_sampling))
    v4b_modulated = sum(
        1
        for seeded_tick, null_tick in zip(seeded_sampling, null_sampling, strict=True)
        if seeded_tick != null_tick
    )
    return {
        "v4a_distinct_sampling_count": v4a_distinct,
        "v4b_modulated_tick_count": v4b_modulated,
        "checksums_match": seeded_checksum == null_checksum,
        "hard_gate": False,
        "note": (
            "channel-active annotation (non-gate, §F): sampling-spy on the "
            "recomposed per-tick sampling of two Ollama-free replays (seeded vs "
            "locomotion-null); pure distinct/modulated counts, no measurement "
            "statistic and no Done contribution"
        ),
    }


async def verify(artifact_dir: Path) -> bool:
    """Ollama-free replay-verify of a committed v1 artifact bundle (V2/V3 + V4 side file).

    Design-copied from ``scripts/ecl_v0_live_capture.py``'s ``verify`` (v0 stays
    untouched, §H), with two v1 changes: the replay uses the **seeded** state
    (Codex MEDIUM-2) and the manifest re-render uses the v1 observables overlay;
    after the byte checks it writes the V4a/V4b channel-active annotation side
    file (:func:`channel_activation`, outside the manifest SHA set)."""
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
        result = await run_ecl_loop(
            run_id=run_config["run_id"],
            store=store,
            embedding=embedding,
            llm=llm,
            # Codex MEDIUM-2: replay from the SEEDED state (the committed
            # envelope_provenance carries the seeded locomotion.lam).
            agent_state=locomotion_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(run_config["retrieval_now"]),
            base_ts=datetime.fromisoformat(run_config["base_ts"]),
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

    # V3b (manifest.json itself): re-render through the same pipeline capture()
    # used (render_golden + attach_live_v1_observables + canonical_dumps),
    # reusing the committed env_pins/run block, and assert byte-identity.
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_live_v1_observables(json.loads(rendered["manifest.json"]))
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

    # V4a/V4b channel-active annotation (side file, outside the SHA set).
    annotation = await channel_activation(
        decisions_text=decisions_text, run_config=run_config
    )
    (artifact_dir / _ANNOTATION_FILENAME).write_text(
        json.dumps(annotation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[verify] annotation V4a distinct={annotation['v4a_distinct_sampling_count']} "
        f"V4b modulated={annotation['v4b_modulated_tick_count']} "
        f"checksums_match={annotation['checksums_match']}"
    )

    print("[verify] LIVE ARTIFACT OK" if ok else "[verify] LIVE ARTIFACT MISMATCH")
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ECL v1 live-capture (locomotion active)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one record-mode run against a live Ollama and write artifacts (I3)",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed artifact bundle + V4 annotation",
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
        "--n-cognition-ticks", type=int, default=LIVE_V1_N_COGNITION_TICKS
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
