#!/usr/bin/env python
"""ECL v0 golden bake / offline replay-verify (Issue 005, design-final.md §論点5).

One-command offline apparatus for the cross-machine handoff golden:

* ``--bake``   — run the golden ECL loop (replay mode, no live LLM) and write the
  four committed artifacts into ``tests/fixtures/ecl_v0_golden/``. Run once; the
  output is committed.
* ``--verify`` — reproduce the run from the committed ``decisions.jsonl`` **alone**
  and assert the ``ecl_trace_checksum`` byte-matches the committed
  ``manifest.json`` (the reproducibility contract a MacBook consumer runs offline
  via ``scripts/repro.sh``). Also re-checks the per-artifact SHA-256 hashes, the
  serialised ``ecl_trace.jsonl`` checksum, and envelope-stream schema conformance.

Determinism: the LLM is the recorded Plane 2 (replay, ``inner_invocations == 0``)
and the embedding is a constant-vector in-memory mock, so no Ollama is required
on either machine (design §論点3). This is a construction apparatus, NOT a
measurement line — it emits no floor / landscape / verdict statistic.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
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

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_GOLDEN_DIR = _REPO_ROOT / "tests" / "fixtures" / "ecl_v0_golden"


def _offline_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free.

    Pinned to :data:`handoff.GOLDEN_EMBED_VALUE` so bake and replay share one
    source (the value does not affect the trace; uniform embeddings rank purely
    by the tie-break)."""
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


async def run_golden(recorded_calls: Sequence[RecordedLlmCall]) -> EclRunResult:
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
    if llm.inner_invocations != 0:  # pragma: no cover - replay invariant
        msg = f"golden replay touched a live LLM ({llm.inner_invocations} calls)"
        raise RuntimeError(msg)
    return result


async def bake(golden_dir: Path) -> None:
    """Bake the committed golden from the hand-built recorded Plane 2."""
    result = await run_golden(handoff.golden_recorded_calls())
    handoff.write_golden(result, golden_dir)
    print(f"[bake] wrote {len(handoff.GOLDEN_FILENAMES)} artifacts to {golden_dir}")
    print(f"[bake] replay_checksum = {result.checksum}")


async def verify(golden_dir: Path) -> bool:
    """Reproduce the run from committed ``decisions.jsonl`` and check the golden."""
    manifest = json.loads((golden_dir / "manifest.json").read_text(encoding="utf-8"))
    decisions_text = (golden_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (golden_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (golden_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")

    ok = True

    # 1. Replay from committed decisions alone → checksum byte-match.
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)
    result = await run_golden(recorded)
    if result.checksum != manifest["replay_checksum"]:
        ok = False
        print(
            f"[verify] FAIL replay checksum {result.checksum} != "
            f"manifest {manifest['replay_checksum']}"
        )
    else:
        print(f"[verify] OK replay checksum {result.checksum}")

    # 2. Committed ecl_trace.jsonl reloads to the same checksum.
    reloaded_checksum = ecl_trace_checksum(handoff.trace_rows_from_jsonl(trace_text))
    if reloaded_checksum != manifest["replay_checksum"]:
        ok = False
        print(f"[verify] FAIL reloaded trace checksum {reloaded_checksum}")

    # 3. Per-artifact SHA-256 integrity.
    artifacts = {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }
    for name, text in artifacts.items():
        expected = manifest["artifacts"][name]["sha256"]
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual != expected:
            ok = False
            print(f"[verify] FAIL {name} sha256 {actual} != {expected}")

    # 4. Envelope stream schema conformance.
    envelopes = handoff.validate_envelope_stream(envelope_text)
    print(f"[verify] OK {len(envelopes)} envelopes schema-conformant")

    print("[verify] GOLDEN OK" if ok else "[verify] GOLDEN MISMATCH")
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECL v0 golden bake / verify")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bake", action="store_true", help="write the committed golden")
    group.add_argument(
        "--verify", action="store_true", help="offline replay-verify the golden"
    )
    parser.add_argument("--golden-dir", type=Path, default=_DEFAULT_GOLDEN_DIR)
    args = parser.parse_args(argv)

    if args.bake:
        asyncio.run(bake(args.golden_dir))
        return 0
    ok = asyncio.run(verify(args.golden_dir))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
