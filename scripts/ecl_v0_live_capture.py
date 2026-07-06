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

Scope guard (design-final.md §論点4, binding, mirrors ``scripts/ecl_v0_golden.py``
/ ``live.py``). This is a *construction* apparatus, **NOT a measurement line**.
It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
computes/emits no floor / landscape / verdict statistic.
"""

from __future__ import annotations

import argparse
import asyncio
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
from erre_sandbox.integration.embodied.loop import DEFAULT_PHYSICS_TICKS_PER_COGNITION
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECL v0 live-capture (Issue 001 apparatus)")
    parser.add_argument(
        "--capture",
        action="store_true",
        required=True,
        help="drive one record-mode run against a live Ollama and write artifacts",
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
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
