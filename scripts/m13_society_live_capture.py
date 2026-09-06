#!/usr/bin/env python
"""M13 society live-closure capture/verify CLI — Issue 006 skeleton (Plane G).

Design-copy (not import — ``scripts/m13_live_loop_capture.py`` and
``scripts/m4_society_live_capture.py`` both stay untouched) of the
``--capture`` / ``--verify`` pair those two siblings established, retargeted at
the N-agent live-closure root landed by Issues 002-006
(``integration/embodied/society_live_loop.py``).

**What this issue (I6) lands: the Plane G verification skeleton only.**

* ``--capture`` drives one **Ollama-free** record-mode society closure over a
  scripted inner chat per agent plus a constant-vector mock embedder, and
  writes the bundle (four ``handoff`` artifacts + this closure's own two replay
  inputs). It is the shape a sealed real run will use; **Issue 007 adds
  ``--real``** (a real ``OllamaChatClient`` per agent behind an explicit
  spend-ratification flag). Nothing here opens a connection.
* ``--verify`` is Ollama-free and CI/WSL-safe: it rebuilds the per-agent replay
  stream from the committed ``decisions.jsonl``, replays it through the
  **unmodified** ``society.py::run_society_loop``, and checks
  (a) Plane G byte-parity of ``ecl_trace_checksum`` / ``event_log_checksum``,
  (b) ``inner_invocations == 0`` on every channel,
  (c) **request conformance** — the replay-side spy's recomposed
  ``(agent_id, window, system_prompt, user_prompt)`` and ``(kind, text)``
  embedding requests against the committed record, with ``sampling``
  explicitly excluded (Codex **H-4**) — and
  (d) per-artifact SHA-256 + byte identity of a fresh re-render.
  It then writes/checks three **side annotations** (parity, conformance,
  per-agent firing) that live outside the manifest SHA set, so producing them
  can never change the bundle's integrity hashes.

**Honest framing (binding, ``design-final.md`` §2)**: this is *wiring* /
*construction* apparatus, never aha / emergence / effect. It imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes no floor /
verdict / divergence / detectability / scorer statistic. The firing annotation
is a **non-gate** count: firing ≠ detectability.

**Not a wall-clock real-time session (Codex M-3)**: byte-parity is scoped to
the *scripted in-process perturbation sequence* the bundle commits. Real Godot
frames, real WebSocket arrival times and real LLM latency are external
non-determinism sources outside the replay set.
"""

# ruff: noqa: T201
# T201 (print): a CLI's entire job is human-readable stdout status lines
# (mirrors scripts/m4_society_live_capture.py / m13_live_loop_capture.py).
# `scripts/` is not in CI's lint scope (`ruff check src tests`, decisions.md
# DA-SLC-5), so this exemption is stated explicitly rather than inherited.

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
)
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    society_live_agent_states,
    society_live_personas,
)
from erre_sandbox.integration.embodied.society_live_loop import (
    PLANE_G_EMBEDDING_RECORD_FILENAME,
    PLANE_G_INBOUND_LEDGER_FILENAME,
    build_society_live_world,
    replay_society_plane_g,
    run_society_live_loop,
    society_embedding_record_from_jsonl,
    society_firing_annotation,
    society_injected_ledger_from_jsonl,
    society_ledger_entries,
    society_live_loop_perturbation_plan,
    society_plane_g_bundle,
    society_plane_g_parity,
    society_plane_g_pins,
    society_recorded_llm_from_jsonl,
    society_request_conformance,
)
from erre_sandbox.integration.embodied.traversal_live import (
    EmbeddingRecordReplayClient,
)
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.society_live_loop import (
        SocietyLedgerEntry,
        SocietyPlaneGReplay,
    )

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_DEFAULT_OUT_DIR: Final[Path] = (
    _REPO_ROOT / "experiments" / "20260906-m13-society-live" / "plane-g"
)

SEALED_RUN_ID: Final[str] = "m13-society-live-plane-g"
SEALED_TS: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed clocks — the same record-mode pin the live root applies to every
in-process-synthesised field. A real send/receive time in a committed artifact
would be pure non-determinism."""

PARITY_FILENAME: Final[str] = "plane_g_parity.json"
CONFORMANCE_FILENAME: Final[str] = "request_conformance.json"
FIRING_ANNOTATION_FILENAME: Final[str] = "firing_annotation.json"

SIDE_ANNOTATION_FILENAMES: Final[tuple[str, ...]] = (
    PARITY_FILENAME,
    CONFORMANCE_FILENAME,
    FIRING_ANNOTATION_FILENAME,
)
"""Derived side files, deliberately OUTSIDE the manifest SHA set: producing
them can never change the bundle's integrity hashes."""

_PLAN_JSON: Final[str] = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    },
    ensure_ascii=False,
)


class SealedBundleExistsError(RuntimeError):
    """The target bundle directory already holds a committed bundle."""


class BundleVerificationError(RuntimeError):
    """A committed bundle is structurally unusable (not merely non-matching)."""


# --------------------------------------------------------------------------- #
# Ollama-free doubles (Issue 007 swaps the chat side for a real client)
# --------------------------------------------------------------------------- #


class _ScriptedInnerChat:
    """Scripted inner chat returning one fixed plan (never a connection)."""

    def __init__(self, content: str = _PLAN_JSON) -> None:
        self._content = content
        self.calls = 0

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        self.calls += 1
        return ChatResponse(
            content=self._content,
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )

    async def close(self) -> None:
        return None


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedder over an httpx MockTransport (no network)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vector = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vector] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _uv_lock_sha256() -> str:
    """SHA-256 of the repo's ``uv.lock`` (reproducibility-discipline env pin)."""
    lock_path = _REPO_ROOT / "uv.lock"
    if not lock_path.exists():  # pragma: no cover — the repo always ships one
        return "unknown"
    return hashlib.sha256(lock_path.read_bytes()).hexdigest()


def _run_config(
    *,
    seed: int,
    physics_ticks_per_cognition: int,
    k_ecl: int,
) -> dict[str, Any]:
    return {
        "seed": seed,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
        "k_ecl": k_ecl,
        "base_ts": SEALED_TS.isoformat(),
        "retrieval_now": SEALED_TS.isoformat(),
    }


def _clock_from(run_config: dict[str, Any], key: str) -> datetime:
    """Read a clock out of the committed manifest, never a module global.

    A verify that hardcoded its clocks while *reading* the manifest for
    everything else would let a manifest claim any ``base_ts`` it liked and
    still replay green — that part of the provenance would be unfalsifiable.
    """
    return datetime.fromisoformat(str(run_config[key]))


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #


async def capture(
    *,
    run_id: str = SEALED_RUN_ID,
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    seed: int = 0,
    k_ecl: int = K_ECL,
) -> dict[str, str]:
    """Drive one knob-ON record-mode society closure and render its bundle.

    Ollama-free: the per-agent inner chat is :class:`_ScriptedInnerChat` and the
    embedder is a mock transport. **Issue 007 adds ``--real``**, which swaps the
    inner chats for real ``OllamaChatClient``s behind spend ratification; the
    surrounding shape (record-mode wrapping, the frozen perturbation plan, the
    rendered bundle) is what this issue pins so that swap changes one thing.

    Knob-ON on purpose: Plane G's claim is that a knob-ON capture replays
    byte-identically through a knob-OFF unmodified ``run_society_loop``.
    """
    states = [
        state
        for state in society_live_agent_states()
        if state.agent_id in set(agent_ids)
    ]
    personas = {
        agent_id: persona
        for agent_id, persona in society_live_personas().items()
        if agent_id in set(agent_ids)
    }
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    inner_embedding = _mock_embedding()
    recorder = EmbeddingRecordReplayClient(inner=inner_embedding)
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={state.agent_id: _ScriptedInnerChat() for state in states},
        store=store,
        embedding=cast("EmbeddingClient", recorder),
        inbound_sink=sink,
        knob=TwoPhaseKnob(),
        agent_states=states,
        personas=personas,
        max_drain_per_tick=len(states),
    )
    for msg in society_live_loop_perturbation_plan(
        agent_ids=list(agent_ids), n_ticks=n_cognition_ticks
    ):
        sink.push(msg)
    try:
        run = await run_society_live_loop(
            world,
            run_id=run_id,
            retrieval_now=SEALED_TS,
            base_ts=SEALED_TS,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            k_ecl=k_ecl,
        )
    finally:
        await inner_embedding.close()
        await store.close()

    ledger = society_ledger_entries(run.ledger.injected)
    recorded_embedding = tuple(recorder.used)
    env_pins = {
        **handoff.capture_env_pins(),
        "uv_lock_sha256": _uv_lock_sha256(),
        "society_event_log_checksum": run.result.event_log_checksum,
        "society_cognition_step_order": list(run.result.cognition_step_order),
        "max_drain_per_tick": len(states),
        "knob_on": True,
        "self_other_enabled": True,
        "inbound_injected_count": len(ledger),
        "inbound_rejected_count": len(run.ledger.rejected),
        "inbound_dropped_count": run.ledger.dropped,
        "embedding_record_count": len(recorded_embedding),
        "real_backend": False,
        "wall_clock_real_time_session": False,
    }
    bundle = society_plane_g_bundle(
        run.result,
        ledger=ledger,
        recorded_embedding=recorded_embedding,
        run_config=_run_config(
            seed=seed,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            k_ecl=k_ecl,
        ),
        env_pins=env_pins,
    )
    # Side-file SHAs are carried in env_pins (handoff's manifest tracks only its
    # own three artifacts), so the manifest must be rebuilt once they are known.
    env_pins["inbound_ledger_sha256"] = _sha256(bundle[PLANE_G_INBOUND_LEDGER_FILENAME])
    env_pins["embedding_record_sha256"] = _sha256(
        bundle[PLANE_G_EMBEDDING_RECORD_FILENAME]
    )
    return society_plane_g_bundle(
        run.result,
        ledger=ledger,
        recorded_embedding=recorded_embedding,
        run_config=_run_config(
            seed=seed,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            k_ecl=k_ecl,
        ),
        env_pins=env_pins,
    )


def write_bundle(
    out_dir: Path, rendered: dict[str, str], *, refuse_non_empty: bool = True
) -> None:
    """Write every rendered artifact into ``out_dir`` (the only side effect)."""
    if refuse_non_empty and out_dir.exists() and any(out_dir.iterdir()):
        msg = (
            f"{out_dir} already holds a bundle; refusing to overwrite a "
            "committed capture (pass --allow-overwrite to re-bake deliberately)"
        )
        raise SealedBundleExistsError(msg)
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# verify: Ollama-free replay of a committed bundle
# --------------------------------------------------------------------------- #


async def _replay(
    *,
    recorded_llm: dict[str, tuple[Any, ...]],
    recorded_embedding: Sequence[Any],
    ledger: Sequence[SocietyLedgerEntry],
    run_config: dict[str, Any],
    run_id: str,
    agent_ids: Sequence[str],
    n_cognition_ticks: int,
    two_phase_knob: TwoPhaseKnob | None,
) -> SocietyPlaneGReplay:
    """One Plane G replay on a fresh in-memory store (never a connection)."""
    states = [
        state
        for state in society_live_agent_states()
        if state.agent_id in set(agent_ids)
    ]
    personas = {
        agent_id: persona
        for agent_id, persona in society_live_personas().items()
        if agent_id in set(agent_ids)
    }
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        return await replay_society_plane_g(
            recorded_llm=recorded_llm,
            recorded_embedding=recorded_embedding,
            ledger=ledger,
            store=store,
            agent_states=states,
            personas=personas,
            run_id=run_id,
            retrieval_now=_clock_from(run_config, "retrieval_now"),
            base_ts=_clock_from(run_config, "base_ts"),
            seed=int(run_config["seed"]),
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=int(run_config["physics_ticks_per_cognition"]),
            k_ecl=int(run_config["k_ecl"]),
            two_phase_knob=two_phase_knob,
        )
    finally:
        await store.close()


def _check_bytes(
    *, name: str, actual_text: str, committed_text: str, expected_sha: str
) -> tuple[bool, str]:
    """One artifact's SHA-256 + byte-identity check."""
    actual_sha = _sha256(actual_text)
    if actual_sha != expected_sha:
        return False, f"[verify] {name} sha256 {actual_sha} != {expected_sha}"
    if actual_text != committed_text:  # pragma: no cover — defensive
        return False, f"[verify] {name} byte mismatch despite matching sha256"
    return True, f"[verify] {name} sha256 {actual_sha}"


def _check_or_write_annotation(
    path: Path, *, text: str, update: bool
) -> tuple[bool, str]:
    """Verify a committed side annotation, or write it when absent.

    An existing file is compared byte-for-byte (a mismatch is a FAILED check),
    a missing one is written, and ``update`` is the explicit way to refresh a
    committed annotation on purpose — so a drifted annotation can never be
    silently overwritten and reported green.
    """
    if path.exists() and not update:
        committed = path.read_text(encoding="utf-8")
        if committed == text:
            return True, f"[verify] {path.name} matches the committed annotation"
        return False, f"[verify] {path.name} DRIFTED from the committed annotation"
    existed = path.exists()
    path.write_text(text, encoding="utf-8", newline="\n")
    return True, f"[verify] {'updated' if existed else 'wrote'} {path.name}"


async def verify(
    artifact_dir: Path,
    *,
    annotation_dir: Path | None = None,
    update_annotations: bool = False,
) -> bool:
    """Ollama-free replay-verify of a committed Plane G bundle.

    Never opens a connection: every backend is a replay client over the
    committed records.
    """
    write_dir = annotation_dir if annotation_dir is not None else artifact_dir
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
    envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    ledger_text = (artifact_dir / PLANE_G_INBOUND_LEDGER_FILENAME).read_text(
        encoding="utf-8"
    )
    embedding_text = (artifact_dir / PLANE_G_EMBEDDING_RECORD_FILENAME).read_text(
        encoding="utf-8"
    )
    run_config = cast("dict[str, Any]", manifest["run"])
    env_pins = cast("dict[str, Any]", manifest["env_pins"])

    recorded_llm = society_recorded_llm_from_jsonl(decisions_text)
    ledger = society_injected_ledger_from_jsonl(ledger_text)
    recorded_embedding = society_embedding_record_from_jsonl(embedding_text)
    agent_ids = [str(a) for a in run_config["agent_ids"]]
    if sorted(recorded_llm) != sorted(agent_ids):
        msg = (
            f"decisions.jsonl covers {sorted(recorded_llm)} but the manifest "
            f"pins {sorted(agent_ids)}"
        )
        raise BundleVerificationError(msg)
    n_cognition_ticks = int(run_config["cognition_ticks"])

    checks: list[tuple[bool, str]] = []

    # --- Plane G: the UNMODIFIED driver reproduces the run (knob-off).
    replay = await _replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
        run_id=str(run_config["run_id"]),
        agent_ids=agent_ids,
        n_cognition_ticks=n_cognition_ticks,
        two_phase_knob=None,
    )
    pins = society_plane_g_pins(replay.result)
    committed_pins = type(pins)(
        geometry_checksum=str(manifest["replay_checksum"]),
        event_log_checksum=str(env_pins["society_event_log_checksum"]),
        cognition_step_order=tuple(
            str(a) for a in env_pins["society_cognition_step_order"]
        ),
        self_other_observation_input=manifest.get("self_other_observation_input"),
    )
    parity = society_plane_g_parity(pins=committed_pins, replay=replay)
    checks.extend(
        (bool(parity[key]), f"[verify] Plane G {key}={parity[key]}")
        for key in (
            "geometry_checksum_match",
            "event_log_checksum_match",
            "cognition_step_order_match",
            "self_other_slot_match",
            "replay_touched_no_llm",
        )
    )

    # --- Request conformance (Codex H-4): sampling explicitly excluded.
    conformance = society_request_conformance(
        replay=replay,
        recorded_llm=recorded_llm,
        committed_embedding_requests=[
            (call.kind, call.text) for call in recorded_embedding
        ],
    )
    checks.extend(
        (bool(conformance[key]), f"[verify] conformance {key}={conformance[key]}")
        for key in (
            "llm_requests_match",
            "embedding_requests_match",
            "self_other_segments_match",
        )
    )

    # --- Artifact re-render from the REPLAY result: SHA-256 + byte identity.
    rendered = society_plane_g_bundle(
        replay.result,
        ledger=ledger,
        recorded_embedding=recorded_embedding,
        run_config=run_config,
        env_pins=env_pins,
    )
    for name, committed_text in (
        ("ecl_trace.jsonl", trace_text),
        ("decisions.jsonl", decisions_text),
        ("envelope_stream.jsonl", envelope_text),
    ):
        checks.append(
            _check_bytes(
                name=name,
                actual_text=rendered[name],
                committed_text=committed_text,
                expected_sha=str(manifest["artifacts"][name]["sha256"]),
            )
        )
    for name, committed_text, pin_key in (
        (PLANE_G_INBOUND_LEDGER_FILENAME, ledger_text, "inbound_ledger_sha256"),
        (
            PLANE_G_EMBEDDING_RECORD_FILENAME,
            embedding_text,
            "embedding_record_sha256",
        ),
    ):
        checks.append(
            _check_bytes(
                name=name,
                actual_text=rendered[name],
                committed_text=committed_text,
                expected_sha=str(env_pins[pin_key]),
            )
        )
    checks.append(
        (
            rendered["manifest.json"] == manifest_text,
            "[verify] manifest.json re-render byte identity",
        )
    )

    # --- Side annotations (outside the SHA set).
    knob_on = await _replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
        run_id=str(run_config["run_id"]),
        agent_ids=agent_ids,
        n_cognition_ticks=n_cognition_ticks,
        two_phase_knob=TwoPhaseKnob(),
    )
    firing = society_firing_annotation(
        knob_on=knob_on, knob_off=replay, recorded_llm=recorded_llm
    )
    write_dir.mkdir(parents=True, exist_ok=True)
    for name, derived in (
        (PARITY_FILENAME, parity),
        (CONFORMANCE_FILENAME, conformance),
        (FIRING_ANNOTATION_FILENAME, firing),
    ):
        checks.append(
            _check_or_write_annotation(
                write_dir / name,
                text=handoff.canonical_dumps(derived) + "\n",
                update=update_annotations,
            )
        )

    for ok, line in checks:
        print(f"{'PASS' if ok else 'FAIL'} {line}")
    print(
        "[verify] firing annotation is NON-GATE (firing != detectability): "
        f"eligible={firing['eligible_tick_count']} "
        f"witness={firing['witness_tick_count']} verdict={firing['verdict']}"
    )
    print(
        "[verify] scope: SCRIPTED in-process perturbation sequence only -- "
        "not a wall-clock real-time session (Codex M-3)"
    )
    return all(ok for ok, _ in checks)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _capture_main(args: argparse.Namespace) -> int:
    rendered = asyncio.run(
        capture(
            run_id=str(args.run_id),
            n_cognition_ticks=int(args.cognition_ticks),
            physics_ticks_per_cognition=int(args.physics_ticks_per_cognition),
            seed=int(args.seed),
        )
    )
    write_bundle(
        Path(args.out_dir), rendered, refuse_non_empty=not args.allow_overwrite
    )
    for filename in sorted(rendered):
        print(f"[capture] wrote {Path(args.out_dir) / filename}")
    print(
        "[capture] Ollama-free scripted capture (no backend was contacted). "
        "Issue 007 adds --real."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "M13 society live-closure Plane G capture/verify "
            "(construction wiring apparatus, not a measurement line)"
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one Ollama-free record-mode closure and write the bundle",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify of a committed bundle",
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument("--annotation-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=SEALED_RUN_ID)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--cognition-ticks", type=int, default=SOCIETY_LIVE_N_COGNITION_TICKS
    )
    parser.add_argument(
        "--physics-ticks-per-cognition",
        type=int,
        default=DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument(
        "--update-annotations",
        action="store_true",
        help="refresh committed side annotations on purpose (verify only)",
    )
    args = parser.parse_args(argv)

    if args.capture:
        return _capture_main(args)
    ok = asyncio.run(
        verify(
            Path(args.out_dir),
            annotation_dir=args.annotation_dir,
            update_annotations=args.update_annotations,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    sys.exit(main())
