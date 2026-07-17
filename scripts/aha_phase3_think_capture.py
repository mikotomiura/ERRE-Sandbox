#!/usr/bin/env python
"""aha!/DMN-ECN Phase 3 — think=True capture CLI (real run is the sealed run).

Thin CLI over :mod:`erre_sandbox.integration.embodied.think_capture`:

* ``--capture`` (the **only** live-Ollama path): preflight-validates the committed ECL v0
  prompt provenance (:func:`~...think_capture.validate_prompt_provenance`, Codex H3), issues
  ``think=True`` for each of the 32 kant prompts against a real ``qwen3:8b`` via
  :class:`~...think_capture.ThinkTraceClient`, and writes ``manifest.json`` (no Phase 3
  ``replay_checksum`` by design, Codex H2) + ``think_traces.jsonl`` into ``--out-dir``. A
  transport failure writes a partial diagnostic and exits nonzero (Codex H5); an empty /
  unparseable thinking outcome is a valid recorded trace (exit 0 + note).

* ``--observe`` (**Ollama-free**): reads a committed ``think_traces.jsonl`` and surfaces the
  reconsideration-marker *excerpt inventory* + boolean presence + thinking excerpts as raw
  material for the human ``observation-memo.md`` (§(b) principle 4). It computes **no**
  verdict / score / count-as-metric (Codex H4).

Scope guard (design-final §Guard, binding, mirrors ``scripts/ecl_v0_live_capture.py``): a
**construction** apparatus, **NOT a measurement line**. No ``evidence`` / ``spdm`` /
``runningness`` import; no floor / verdict / divergence statistic. Import has no side
effects — a bare ``--capture`` is the only path that touches a live Ollama.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.think_capture import (
    PHASE3_SOURCE_ARTIFACT,
    PHASE3_THINK_NUM_PREDICT,
    ThinkCapturePartialError,
    ThinkTraceClient,
    build_phase3_env_pins,
    build_phase3_manifest,
    records_to_jsonl,
    run_think_capture,
    surface_reconsideration_markers,
    validate_prompt_provenance,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.think_capture import ThinkCaptureRecord

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SOURCE_DIR = _REPO_ROOT / PHASE3_SOURCE_ARTIFACT
_DEFAULT_OUT_DIR = (
    _REPO_ROOT / "experiments" / "20260717-aha-phase3-think-true-live" / "artifacts"
)
_DEFAULT_MODEL = "qwen3:8b"
# code-reviewer MEDIUM-3: cap the excerpts printed per trace so a very long trace does not
# flood the console. Display-only; NOT a measure of marker frequency (over-read guard).
_MAX_DISPLAYED_EXCERPTS = 8


def _read_source(source_dir: Path) -> tuple[str, dict]:
    """Read the committed ECL v0 ``decisions.jsonl`` + ``manifest.json`` (UTF-8)."""
    decisions_text = (source_dir / "decisions.jsonl").read_text(encoding="utf-8")
    manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    return decisions_text, manifest


async def _capture(
    *,
    source_dir: Path,
    out_dir: Path,
    model: str,
    endpoint: str | None,
    num_predict: int,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
) -> int:
    decisions_text, source_manifest = _read_source(source_dir)
    # Preflight (Codex H3): a structural Stop BEFORE any live call / spend.
    provenance = validate_prompt_provenance(
        decisions_text=decisions_text, manifest=source_manifest
    )
    print(
        f"[capture] provenance OK: N={provenance.n_source_calls} persona={provenance.persona} "
        f"source_manifest_checksum={provenance.source_manifest_checksum[:16]}"
    )

    partial = False
    records: tuple[ThinkCaptureRecord, ...] = ()
    # code-reviewer MEDIUM-1: use the client's own async context manager.
    async with ThinkTraceClient(model=model, endpoint=endpoint) as client:
        try:
            records = await run_think_capture(
                prompts=provenance.calls, client=client, num_predict=num_predict
            )
        except ThinkCapturePartialError as exc:
            # Transport failure (Codex H5): write what we have as a partial diagnostic.
            records = exc.records
            partial = True
            print(f"[capture] TRANSPORT FAILURE: {exc}", file=sys.stderr)

    env_pins = build_phase3_env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
        model=model,
    )
    manifest = build_phase3_manifest(
        provenance=provenance,
        records=records,
        env_pins=env_pins,
        num_predict=num_predict,
        partial=partial,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        handoff.canonical_dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )
    (out_dir / "think_traces.jsonl").write_text(
        records_to_jsonl(records), encoding="utf-8", newline="\n"
    )
    counts = manifest["mechanical_technical_counts"]
    print(
        f"[capture] wrote {len(records)} traces to {out_dir} "
        f"(mechanical: parseable={counts['thinking_parseable']}/{counts['total']}, "
        f"finish_length={counts['finish_length']})"
    )
    if partial:
        print("[capture] PARTIAL run (transport failure) — see stderr", file=sys.stderr)
        return 1
    return 0


def _observe(traces_path: Path) -> int:
    """Ollama-free: surface raw material (excerpts + marker inventory) for the human memo."""
    text = traces_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    print(f"[observe] {len(lines)} traces in {traces_path}")
    for ln in lines:
        rec = json.loads(ln)
        idx = rec["source_index"]
        thinking = rec.get("thinking", "")
        excerpts = surface_reconsideration_markers(thinking)
        markers_present = "yes" if excerpts else "no"
        print(
            f"\n--- trace #{idx} (thinking_source={rec['thinking_source']}, "
            f"parseable={rec['thinking_parseable']}, chars={rec['thinking_char_count']}, "
            f"markers_present={markers_present}) ---"
        )
        head = thinking[:400].replace("\n", " ")
        print(f"  thinking[head]: {head}")
        # Excerpt inventory (Codex H4): illustrative excerpts only, NOT a count/score/gate.
        for ex in excerpts[:_MAX_DISPLAYED_EXCERPTS]:
            print(f"  · marker excerpt: …{ex}…")
    print(
        "\n[observe] raw material only — write the descriptive two-phase observation into "
        "observation-memo.md by hand. NO verdict/score computed here (design-final §Guard)."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="aha Phase 3 think=True capture (sealed-run apparatus)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="issue think=True for the 32 committed prompts against a live Ollama and write artifacts",
    )
    group.add_argument(
        "--observe",
        action="store_true",
        help="Ollama-free: surface excerpts + marker inventory from committed think_traces.jsonl",
    )
    parser.add_argument("--source-dir", type=Path, default=_DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument(
        "--traces",
        type=Path,
        default=_DEFAULT_OUT_DIR / "think_traces.jsonl",
        help="committed think_traces.jsonl to observe (--observe only)",
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("OLLAMA_HOST"),
        help="Ollama endpoint (default: $OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    parser.add_argument("--num-predict", type=int, default=PHASE3_THINK_NUM_PREDICT)
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument("--uv-lock-sha256", default="unknown")
    args = parser.parse_args(argv)

    if args.observe:
        return _observe(args.traces)

    return asyncio.run(
        _capture(
            source_dir=args.source_dir,
            out_dir=args.out_dir,
            model=args.model,
            endpoint=args.endpoint,
            num_predict=args.num_predict,
            qwen3_model_digest=args.qwen3_model_digest,
            ollama_version=args.ollama_version,
            vram_gb=args.vram_gb,
            uv_lock_sha256=args.uv_lock_sha256,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
