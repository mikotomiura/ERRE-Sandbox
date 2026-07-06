#!/usr/bin/env python
"""ECL v0 live-capture CLI — Issue 001 apparatus (real run is Issue 003).

Thin CLI over :func:`erre_sandbox.integration.embodied.live.run_live_capture`:
``--capture`` builds a real
:class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` (the only live
piece, D-4) plus a constant-vector mock embedding (D-4: real ``nomic-embed-text``
is out of scope, minimal reality surface is the action-LLM chat call alone),
drives one record-mode ECL v0 run through
:func:`~erre_sandbox.integration.embodied.live.run_live_capture`, and writes the
four handoff artifacts (``manifest.json`` with the live env-pin + observables
overlay, ``ecl_trace.jsonl``, ``decisions.jsonl``, ``envelope_stream.jsonl``)
into ``--out-dir`` (default ``experiments/20260706-ecl-v0-live-capture/artifacts``,
D-8).

This module constructs the sealed-run inputs (persona/agent state = the golden
Kant fixture, D-2) but does **not** perform the sealed run itself — actually
invoking ``--capture`` against a live Ollama, committing the resulting
artifacts, and the cross-platform (WSL) byte-equality check are Issue 003.
Import of this module has no side effects (no live connection opened at
import time); a bare ``python scripts/ecl_v0_live_capture.py --capture`` is the
only path that touches a live Ollama.

``--verify`` (Issue 002, ``loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md``)
is the companion **Ollama-free** replay-verify apparatus: it reproduces a
committed artifact bundle's ``ecl_trace_checksum`` from ``decisions.jsonl``
alone (:func:`verify`'s O3a step, ``inner_invocations == 0``) and re-renders
the full artifact set from the same raw Plane 2 to check every per-artifact
SHA-256 (O3b). Design-copied from ``scripts/ecl_v0_golden.py``'s ``verify``
(D-7: copied, not imported, so that script stays untouched). Critically, the
re-render step reuses the **committed manifest's** ``env_pins`` and ``run``
block rather than a fresh :func:`~erre_sandbox.integration.embodied.handoff.build_manifest`
capture (Codex TASK-PRE MEDIUM-2): a fresh capture snapshots the *current*
machine's python/package versions and drifts the manifest bytes across
runners, which is not what a reproduction check should assert.

Scope guard (design-final.md §論点4, binding, mirrors ``scripts/ecl_v0_golden.py``
/ ``live.py``). This is a *construction* apparatus, **NOT a measurement line**.
It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
computes/emits no floor / landscape / verdict statistic.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import (
    LIVE_N_COGNITION_TICKS,
    attach_live_observables,
    build_live_env_pins,
    run_live_capture,
)
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = (
    _REPO_ROOT / "experiments" / "20260706-ecl-v0-live-capture" / "artifacts"
)
_DEFAULT_RUN_ID = "ecl-v0-live-capture"


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free (D-4).

    Independent of ``scripts.ecl_v0_golden._offline_embedding`` (D-7: the two
    scripts stay decoupled) but structurally identical: only the action-LLM
    chat call is live in a live-capture run.
    """
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
    """Drive one live-capture run and render the four handoff artifacts.

    Builds a real ``OllamaChatClient`` (the sole live piece) and a mock
    embedding (D-4), runs :func:`run_live_capture`, then renders the artifacts
    via ``handoff``'s existing serialisers plus the live env-pin +
    observables overlay this module owns. Does not write anything to disk —
    the caller (``main``) does that, so this function is unit-testable without
    touching a filesystem.
    """
    # Imported lazily so a plain ``import`` of this module (e.g. from tests)
    # never requires ``httpx``-level Ollama reachability.
    from erre_sandbox.inference.ollama_adapter import OllamaChatClient

    now = datetime.now(UTC)
    inner = OllamaChatClient()
    embedding = _mock_embedding()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        result = await run_live_capture(
            inner_chat=inner,
            store=store,
            embedding=embedding,
            run_id=run_id,
            agent_state=handoff.golden_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=now,
            base_ts=now,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
        )
    finally:
        await inner.close()
        await embedding.close()
        await store.close()

    resolved_sampling = result.decisions[0].call.sampling
    env_pins = build_live_env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
        resolved_sampling=resolved_sampling,
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
    rendered["manifest.json"] = handoff.canonical_dumps(attach_live_observables(manifest)) + "\n"
    return result, rendered


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


async def verify(artifact_dir: Path) -> bool:
    """Ollama-free replay-verify of a committed live-capture artifact bundle.

    Issue 002 apparatus (design-copied from ``scripts/ecl_v0_golden.py``'s
    ``verify``, D-7 — copied, not imported, so that script stays untouched):

    1. **O3a** — replay from the committed ``decisions.jsonl`` *alone*
       (``inner_invocations == 0``) reproduces the committed manifest's
       ``replay_checksum`` byte-for-byte.
    2. **O3b** — re-rendering the full artifact set from the same replayed
       result reproduces every per-artifact SHA-256. The re-render reuses the
       **committed manifest's** ``env_pins``/``run`` block (Codex TASK-PRE
       MEDIUM-2), never a fresh ``handoff.build_manifest(env_pins=None)``
       capture (which would snapshot the *current* machine and drift the
       manifest bytes across runners).

    Ollama-free: the LLM is the recorded Plane 2 (replay only) and the
    embedding is the constant-vector mock, exactly as ``capture`` uses when
    building the live artifact in the first place. This function computes no
    floor / landscape / verdict / divergence statistic (measurement-line
    non-re-entry, design §論点4) — it is a byte-equality reproduction check.
    """
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
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
            agent_state=handoff.golden_agent_state(),
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

    # O3a — inner_invocations == 0 + replay checksum byte-match.
    if llm.inner_invocations != 0:
        ok = False
        print(f"[verify] FAIL replay touched a live LLM ({llm.inner_invocations} calls)")
    if result.checksum != manifest["replay_checksum"]:
        ok = False
        print(
            f"[verify] FAIL replay checksum {result.checksum} != "
            f"manifest {manifest['replay_checksum']}"
        )
    else:
        print(f"[verify] OK replay checksum {result.checksum}")

    # O3b — re-render (committed env_pins/run reused) → per-artifact SHA-256.
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

    envelopes = handoff.validate_envelope_stream(envelope_text)
    print(f"[verify] OK {len(envelopes)} envelopes schema-conformant")

    print("[verify] LIVE ARTIFACT OK" if ok else "[verify] LIVE ARTIFACT MISMATCH")
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECL v0 live-capture (Issue 001/002 apparatus)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one record-mode run against a live Ollama and write artifacts",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed artifact bundle (Issue 002)",
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
    parser.add_argument("--n-cognition-ticks", type=int, default=LIVE_N_COGNITION_TICKS)
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
