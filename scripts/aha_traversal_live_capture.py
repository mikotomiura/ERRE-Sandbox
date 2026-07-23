#!/usr/bin/env python
"""M13 aha-substrate-embodiment traversal — I3 reproducibility capture CLI.

Design-copied structure from ``scripts/aha_phase4b_two_phase_live_capture.py``
(``--capture``/``--verify``) and ``scripts/ecl_v0_golden.py`` (Ollama-free
determinism, ``tests/fixtures/`` golden destination) — FROZEN ADR
``.steering/20260723-m13-aha-substrate-embodiment/design-final.md`` (Option A,
organ 無改変). The **default (scripted) mode** is fully scripted
(:class:`~erre_sandbox.integration.embodied.traversal_live.\
ScriptedTraversalChatClient`, Ollama-free from the start), so plain
``--capture``/``--verify`` never open a live connection at all — both are
deterministic and reproducible offline, mirroring ``ecl_v0_golden.py``'s
discipline while keeping the phase4b CLI shape the coordinator asked to
follow. **This no-live-connection claim is scoped to the default mode only**
(MEDIUM-3 review) — ``--real`` (see below) opens a local Ollama connection,
and only after an explicit, separate, user-ratified session invokes it.

``--capture`` drives one **knob-on record-mode** traversal run (:func:`~erre_\
sandbox.integration.embodied.traversal_live.run_traversal_capture`, ``two_\
phase_knob=TwoPhaseKnob()``, the traversal's own peripatos-seeded ``AgentState``,
``n=TRAVERSAL_HORIZON``, ``physics=TRAVERSAL_PHYSICS_TICKS_PER_COGNITION``) and
renders the four handoff artifacts (``manifest.json`` / ``ecl_trace.jsonl`` /
``decisions.jsonl`` / ``envelope_stream.jsonl``) via ``handoff.render_golden``
**unmodified** — no ``expected_placement.jsonl``: that artifact is the M2/M4
multi-agent-placement projection (a different render path entirely); this
traversal harness is single-agent, the same shape ``ecl_v0_golden`` /
Phase 4b bake to.

``--verify`` is the Ollama-free replay-verify: replay the committed
``decisions.jsonl`` alone (**through the JSONL round-trip**, not an in-memory
``EclRunResult.replay_calls()`` shortcut — I2 review LOW-4's carried-forward
discipline: an in-memory replay skips the projection-boundary re-quantisation
``decisions_to_jsonl``/``_quantize_embedded_json`` perform, so it would not
catch a cross-platform ``libm`` drift a committed golden must survive) →
byte-match the committed ``replay_checksum`` + every artifact SHA-256, then
writes the firing-annotation side file (:func:`_committed_firing_annotation`
— two Ollama-free spied replays of the SAME **committed** decisions, LOW-2
review, mirroring ``aha_phase4b_two_phase_live_capture.two_phase_firing``;
outside the manifest SHA set) and the W1 route witness.

Scope guard (design-final.md §Guard, binding, mirrors ``aha_phase4b_two_\
phase_live_capture.py``). This is a *construction* apparatus, **NOT a
measurement line**. It imports no ``evidence`` / ``spdm`` / ``runningness``
machinery and computes/emits no floor / landscape / verdict / divergence /
magnitude / detectability / aha-proxy statistic. The firing annotation is a
boolean/count side file, never a Done gate.

**Issue 004 (I4) real mode** (``--real``, code-path only — **the sealed run
itself is a separate, explicitly user-ratified, human-gated session; running
this module or importing it opens no live connection on its own**, mirroring
``aha_phase4b_two_phase_live_capture.py``'s own real-capture precedent):
:func:`real_capture` swaps the scripted plan source for a real
:class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient`
(``think=False`` via the same organ ``ThinkOffChatClient``,
:func:`~erre_sandbox.integration.embodied.traversal_live.run_traversal_\
capture`'s new ``inner_chat`` injection point) and the mock embedding for a
real :class:`~erre_sandbox.memory.embedding.EmbeddingClient`
(``nomic-embed-text``, 768d) wrapped in the new
:class:`~erre_sandbox.integration.embodied.traversal_live.\
EmbeddingRecordReplayClient` (Plane 1 determinism for the embedding channel —
a real vector is recorded once, 6-decimal quantised, then replayed
byte-identically, never re-requested). This is a **channel-exercise**, not an
emergent-traversal validation: the real backend receives the SAME
pre-registered "proceed to ``<zone>``" waypoint stimulus a scripted run does
(``run_traversal_capture``'s ``observation_factory`` is unconditional) — what
is genuinely unscripted is the backend's *response* to that stimulus (whether
it complies, ignores it, speaks instead, etc.), not the route target itself,
so the recorded route may settle (zero moves, honest — see
:func:`~erre_sandbox.integration.embodied.traversal_live.\
traversal_channel_exercise_summary`, a non-gate count annotation, never
"traversal succeeded"). ``real_verify`` replays **both** committed channels
(``decisions.jsonl`` + the new side file ``embedding_record.jsonl``)
Ollama-free.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.traversal_live import (
    TRAVERSAL_EXPECTED_ROUTE,
    TRAVERSAL_HORIZON,
    TRAVERSAL_ITINERARY,
    TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
    EmbeddingRecordReplayClient,
    RecordedEmbeddingCall,
    extract_visit_sequence,
    run_traversal_capture,
    run_traversal_replay_spy,
    traversal_channel_exercise_summary,
    traversal_observation_factory,
    traversal_seed_agent_state,
)
from erre_sandbox.integration.embodied.two_phase_live import (
    run_two_phase_capture,
    two_phase_firing_summary,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_GOLDEN_DIR = _REPO_ROOT / "tests" / "fixtures" / "aha_traversal_golden"
_DEFAULT_RUN_ID = "aha-traversal-golden"
_ANNOTATION_FILENAME = "traversal_firing_annotation.json"

# --- I4 real-mode constants (code-path only, sealed run not executed here) ---
_DEFAULT_REAL_ARTIFACT_DIR = (
    _REPO_ROOT / "experiments" / "20260723-aha-traversal-real" / "artifacts"
)
_DEFAULT_REAL_RUN_ID = "aha-traversal-real"
_DEFAULT_REAL_MODEL: Final[str] = "qwen3:8b"
_DEFAULT_REAL_EMBED_MODEL: Final[str] = "nomic-embed-text"
_EMBEDDING_RECORD_FILENAME = "embedding_record.jsonl"
_CHANNEL_EXERCISE_FILENAME = "traversal_channel_exercise_annotation.json"


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free.

    Structurally identical to ``ecl_v0_golden._offline_embedding`` /
    ``aha_phase4b_two_phase_live_capture._mock_embedding``: this script opens
    no live connection at all (traversal is scripted end to end).
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


# --------------------------------------------------------------------------- #
# Env-pin + observables overlay (self-contained: traversal_live.py is not an
# I3 Allowed File, so this mirrors two_phase_live.build_two_phase_env_pins'
# shape here rather than adding a new export to that module).
# --------------------------------------------------------------------------- #


def _traversal_env_pins(*, decisions_sha256: str) -> dict[str, Any]:
    """Merge the traversal-specific pins onto ``handoff.capture_env_pins()``."""
    pins: dict[str, Any] = dict(handoff.capture_env_pins())
    pins["model"] = "scripted-traversal"
    pins["think"] = False
    pins["two_phase_knob"] = "on"
    pins["decisions_sha256"] = decisions_sha256
    pins["traversal_itinerary"] = [z.value for z in TRAVERSAL_ITINERARY]
    pins["traversal_horizon"] = TRAVERSAL_HORIZON
    pins["traversal_physics_ticks_per_cognition"] = (
        TRAVERSAL_PHYSICS_TICKS_PER_COGNITION
    )
    return pins


TRAVERSAL_DONE_FORMULA: Final[str] = "V1∧V2∧V3"
"""The FROZEN reproducibility-Done formula: three reproducibility observables.
The firing annotation + W1 route witness are construction side-notes, not
part of it (mirrors ``two_phase_live.PHASE4B_DONE_FORMULA``)."""

TRAVERSAL_OBSERVABLES: Final[dict[str, Any]] = {
    "V1": (
        "TRAVERSAL_HORIZON cognition ticks completed against the "
        "scripted-traversal plan source with the two-phase knob active "
        "(TwoPhaseKnob injected) and no exception (exit 0)"
    ),
    "V2": (
        "replaying the committed decisions.jsonl (JSONL round-trip, not an "
        "in-memory shortcut) reproduces a byte-identical replay_checksum "
        "with inner_invocations==0"
    ),
    "V3": (
        "the same committed decisions replay to the same byte-identical "
        "per-artifact SHA-256 on both Windows (UCRT) and WSL Linux (glibc) "
        "(6-decimal quantisation absorbs libm drift; envelope_provenance's "
        "embedded serialised strings are re-quantised at the projection "
        "boundary, not just the top-level floats)"
    ),
    "w1_route_annotation": (
        "construction witness (non-gate): extract_visit_sequence(result) == "
        "the frozen TRAVERSAL_EXPECTED_ROUTE (exact match, not part of the "
        "V1-V3 Done formula)"
    ),
    "firing_annotation": (
        "construction witness (non-gate, side file, outside the manifest SHA "
        "set): the traversal-earned (not seeded) λ>0 evaluation ticks invert "
        "sign knob-on vs knob-off, the generation-phase control is "
        "non-vacuous, and the committed record pins knob-on"
    ),
    "done_formula": TRAVERSAL_DONE_FORMULA,
    "verdict": None,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass
closure). Frozen at import time (not derived from any run outcome).
``verdict`` is explicitly ``None`` — construction validation, never a
measurement verdict."""


def _attach_traversal_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the traversal ``observables`` overlay (non-mutating)."""
    overlaid = dict(manifest)
    overlaid["observables"] = dict(TRAVERSAL_OBSERVABLES)
    return overlaid


# --------------------------------------------------------------------------- #
# Capture — knob-on record-mode run, then render the artifact bundle
# --------------------------------------------------------------------------- #


async def capture(
    *,
    run_id: str,
    seed: int,
) -> tuple[EclRunResult, dict[str, str]]:
    """Drive one knob-on record-mode traversal run and render the four artifacts.

    Ollama-free: :class:`~erre_sandbox.integration.embodied.traversal_live.\
ScriptedTraversalChatClient` never touches a live LLM, so this function opens
    no network connection other than the in-process ``httpx.MockTransport``
    mock embedding. ``retrieval_now``/``base_ts`` are pinned to
    ``handoff.GOLDEN_TS`` (fixed, not ``datetime.now()``) so the bake is
    byte-reproducible on every invocation — the same discipline
    ``ecl_v0_golden.py`` uses.
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    seed_state = traversal_seed_agent_state()
    try:
        result = await run_traversal_capture(
            run_id=run_id,
            store=store,
            embedding=embedding,
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            agent_state=seed_state,
            two_phase_knob=TwoPhaseKnob(),
            seed=seed,
        )
    finally:
        await embedding.close()
        await store.close()

    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    decisions_sha256 = hashlib.sha256(decisions_jsonl.encode("utf-8")).hexdigest()
    env_pins = _traversal_env_pins(decisions_sha256=decisions_sha256)
    run_config = {
        "seed": seed,
        "physics_ticks_per_cognition": TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
        "k_ecl": K_ECL,
        "base_ts": handoff.GOLDEN_TS.isoformat(),
        "retrieval_now": handoff.GOLDEN_TS.isoformat(),
    }
    rendered = handoff.render_golden(result, run_config=run_config, env_pins=env_pins)
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(_attach_traversal_observables(manifest)) + "\n"
    )
    return result, rendered


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# Verify (Ollama-free replay + artifact-integrity + firing annotation)
# --------------------------------------------------------------------------- #


async def _replay_traversal(
    *,
    recorded: Sequence[RecordedLlmCall],
    run_config: dict[str, Any],
) -> tuple[EclRunResult, RecordReplayChatClient]:
    """Replay the committed decisions through the untouched sibling driver.

    Uses the SAME traversal seed + observation factory
    (:func:`~erre_sandbox.integration.embodied.traversal_live.\
traversal_observation_factory`) the capture run used — the episodic-memory
    formation location (hence ``resolve_destination``'s weighted centroid)
    depends on the agent's *position* at each tick, not the observation
    *text*, but this keeps the replay's memory-write shape identical to the
    record's regardless (I1 discipline).
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    llm = RecordReplayChatClient(recorded=recorded)
    seed_state = traversal_seed_agent_state()
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=llm,
            agent_state=seed_state,
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
            two_phase_knob=TwoPhaseKnob(),
            seed=int(cast("int", run_config["seed"])),
            n_cognition_ticks=int(cast("int", run_config["cognition_ticks"])),
            physics_ticks_per_cognition=int(
                cast("int", run_config["physics_ticks_per_cognition"])
            ),
            k_ecl=int(cast("int", run_config["k_ecl"])),
            observation_factory=traversal_observation_factory(seed_state.agent_id),
        )
    finally:
        await embedding.close()
        await store.close()
    return result, llm


async def _committed_firing_annotation(
    *,
    recorded: Sequence[RecordedLlmCall],
    run_config: dict[str, Any],
    embedding_factory: Callable[[], Any] = _mock_embedding,
) -> dict[str, Any]:
    """The W3 firing annotation, sourced from the **committed** decisions.

    LOW-2 review (phase4b consistency): mirrors ``aha_phase4b_two_phase_live_\
capture.two_phase_firing`` — two Ollama-free spied replays of the SAME
    ``recorded`` (committed ``decisions.jsonl``) decisions, one knob-on one
    knob-off, never a fresh re-record. This makes ``record_knob_on_pinned``
    pin the **golden's own** committed knob-on record (``committed_call_\
samplings=[c.sampling for c in recorded]`` below), not a re-generated run's —
    a golden-bundle-native witness, matching ``traversal_firing_summary``'s
    on/off-replay half without repeating its own internal record step.

    ``embedding_factory`` (I4 extension) defaults to :func:`_mock_embedding`
    (every I3 scripted-mode caller, unchanged) — a fresh instance is built
    for **each** of the two spied replays (matching the fresh-store-per-branch
    discipline below). Real mode (I4) passes a factory building fresh
    :class:`~erre_sandbox.integration.embodied.traversal_live.\
EmbeddingRecordReplayClient` **replay**-mode instances from the SAME
    committed embedding record instead: since the physical trajectory (hence
    ``move_t``, hence λ, hence the sampling the knob modulates) depends on
    ``resolve_destination``'s embedding-driven centroid, the on/off replays
    must see the SAME embedding source the original real capture did — the
    constant-vector mock would silently diverge the trajectory and make
    ``record_knob_on_pinned`` meaningless for a real-mode bundle.
    """
    retrieval_now = datetime.fromisoformat(str(run_config["retrieval_now"]))
    base_ts = datetime.fromisoformat(str(run_config["base_ts"]))
    seed_state = traversal_seed_agent_state()

    on_store = MemoryStore(db_path=":memory:")
    on_store.create_schema()
    on_embedding = cast("EmbeddingClient", embedding_factory())
    try:
        on_sampling, on_checksum = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=seed_state,
            two_phase_knob=TwoPhaseKnob(),
            store=on_store,
            embedding=on_embedding,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
        )
    finally:
        await on_embedding.close()
        await on_store.close()

    off_store = MemoryStore(db_path=":memory:")
    off_store.create_schema()
    off_embedding = cast("EmbeddingClient", embedding_factory())
    try:
        off_sampling, off_checksum = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=seed_state,
            two_phase_knob=None,
            store=off_store,
            embedding=off_embedding,
            retrieval_now=retrieval_now,
            base_ts=base_ts,
        )
    finally:
        await off_embedding.close()
        await off_store.close()

    return two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_checksum,
        off_checksum=off_checksum,
        committed_call_samplings=[c.sampling for c in recorded],
    )


async def verify(golden_dir: Path, *, annotation_dir: Path | None = None) -> bool:
    """Ollama-free replay-verify of the committed traversal golden bundle.

    Design-copied from ``aha_phase4b_two_phase_live_capture.verify`` /
    ``ecl_v0_golden.verify``: replays the committed ``decisions.jsonl`` (the
    JSONL text on disk — I2 review LOW-4's carried-forward discipline, never
    the in-memory ``EclRunResult.replay_calls()`` shortcut) → checksum
    byte-match → re-render → per-artifact SHA-256 byte-match → manifest
    re-render byte-match, then writes the firing annotation (side file) and
    checks the W1 route witness.

    ``annotation_dir`` (M-1 review, hermeticity) defaults to ``golden_dir``
    (the CLI's own ``--verify`` still writes the annotation alongside the
    golden it just checked, unchanged). A caller that must NOT mutate
    ``golden_dir`` (a pytest hermeticity requirement against a **committed**
    fixture) passes a separate scratch directory instead — this function
    itself never assumes the annotation belongs next to the golden.
    """
    write_dir = annotation_dir if annotation_dir is not None else golden_dir
    manifest_text = (golden_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    decisions_text = (golden_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (golden_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (golden_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    run_config = cast("dict[str, Any]", manifest["run"])

    ok = True
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)

    result, llm = await _replay_traversal(recorded=recorded, run_config=run_config)

    # V2 — inner_invocations == 0 + replay checksum byte-match.
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

    # V3 (this-machine leg) — re-render (committed env_pins/run reused) →
    # per-artifact SHA-256. The cross-platform leg (Win vs WSL) is a separate
    # developer procedure (I3-G3), not this in-process check.
    rendered = handoff.render_golden(
        result,
        run_config=run_config,
        env_pins=cast("dict[str, Any]", manifest["env_pins"]),
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
        else:
            print(f"[verify] OK {name} sha256 {actual}")

    rerendered_manifest = (
        handoff.canonical_dumps(
            _attach_traversal_observables(json.loads(rendered["manifest.json"]))
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

    # W1 — the recorded physical visit sequence still exact-matches the frozen
    # itinerary on this replay (non-gate re-confirmation, not part of V1-V3).
    visited = extract_visit_sequence(result)
    if visited != TRAVERSAL_EXPECTED_ROUTE:
        ok = False
        print(
            f"[verify] FAIL W1 route mismatch: {visited} != {TRAVERSAL_EXPECTED_ROUTE}"
        )
    else:
        print(f"[verify] OK W1 route == {[z.value for z in visited]}")

    # Firing annotation (side file, outside the SHA set) — LOW-2: sourced from
    # the committed decisions (see _committed_firing_annotation), never a
    # fresh record. M-1(b): written via handoff.canonical_dumps (the SAME
    # 6-decimal-quantised, sorted, compact canonicalisation every other
    # golden artifact uses) rather than a bespoke plain json.dumps, so this
    # side file cannot introduce its own cross-platform float-drift path.
    annotation = await _committed_firing_annotation(
        recorded=recorded, run_config=run_config
    )
    (write_dir / _ANNOTATION_FILENAME).write_text(
        handoff.canonical_dumps(annotation) + "\n",
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

    print("[verify] GOLDEN OK" if ok else "[verify] GOLDEN MISMATCH")
    return ok


# --------------------------------------------------------------------------- #
# I4 real mode — channel exercise (code path only; the sealed run itself is
# a separate, explicitly user-ratified, human-gated session — see the module
# docstring. Defining/importing everything below opens no connection.)
# --------------------------------------------------------------------------- #


def _embedding_call_to_dict(call: RecordedEmbeddingCall) -> dict[str, Any]:
    return {"kind": call.kind, "text": call.text, "vector": list(call.vector)}


def _embedding_calls_to_jsonl(calls: Sequence[RecordedEmbeddingCall]) -> str:
    """Serialise the recorded embedding channel as canonical JSONL (I4).

    One line per call via ``handoff.canonical_dumps`` (sort_keys + 6-decimal
    quantisation — a no-op here since :class:`~erre_sandbox.integration.\
embodied.traversal_live.EmbeddingRecordReplayClient` already quantises on
    record, but this keeps every artifact in the bundle on the SAME
    canonicalisation rule, not a bespoke one).
    """
    return "".join(
        f"{handoff.canonical_dumps(_embedding_call_to_dict(c))}\n" for c in calls
    )


def _embedding_calls_from_jsonl(text: str) -> list[RecordedEmbeddingCall]:
    """Reconstruct the recorded embedding channel from committed JSONL (I4)."""
    calls: list[RecordedEmbeddingCall] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        calls.append(
            RecordedEmbeddingCall(
                kind=data["kind"],
                text=data["text"],
                vector=tuple(data["vector"]),
            )
        )
    return calls


def _real_env_pins(
    *,
    decisions_sha256: str,
    embedding_calls_sha256: str,
    model: str,
    embed_model: str,
) -> dict[str, Any]:
    """Merge the I4 real-mode pins onto ``handoff.capture_env_pins()``.

    ``embedding_record_sha256`` is a pin, not a ``manifest["artifacts"]``
    entry — ``handoff.build_manifest`` (organ, unmodified) tracks only its
    own three known artifacts, so the new embedding-channel side file gets
    its integrity hash carried here instead (mirrors how ``two_phase_live.\
build_two_phase_env_pins`` carries ``decisions_sha256`` rather than adding a
    fourth ``handoff`` artifact entry).
    """
    pins: dict[str, Any] = dict(handoff.capture_env_pins())
    pins["model"] = model
    pins["embed_model"] = embed_model
    pins["think"] = False
    pins["two_phase_knob"] = "on"
    pins["decisions_sha256"] = decisions_sha256
    pins["embedding_record_sha256"] = embedding_calls_sha256
    pins["traversal_horizon"] = TRAVERSAL_HORIZON
    pins["traversal_physics_ticks_per_cognition"] = (
        TRAVERSAL_PHYSICS_TICKS_PER_COGNITION
    )
    pins["channel_exercise_mode"] = "real"
    return pins


REAL_TRAVERSAL_DONE_FORMULA: Final[str] = "R1∧R2∧R3"
"""The FROZEN I4 reproducibility-Done formula — three reproducibility
observables over BOTH Plane 1 channels (LLM + embedding). The
channel-exercise + firing annotations are construction side-notes, not part
of it (mirrors :data:`TRAVERSAL_DONE_FORMULA`)."""

REAL_TRAVERSAL_OBSERVABLES: Final[dict[str, Any]] = {
    "R1": (
        "TRAVERSAL_HORIZON cognition ticks completed against a live "
        "qwen3:8b (think=False) action-LLM AND a live nomic-embed-text "
        "embedding backend, with the two-phase knob active (TwoPhaseKnob "
        "injected), and no exception (exit 0)"
    ),
    "R2": (
        "replaying the committed decisions.jsonl AND embedding_record.jsonl "
        "(BOTH Plane 1 channels, JSONL round-trip) reproduces a "
        "byte-identical replay_checksum with inner_invocations==0 on both "
        "the LLM and the embedding replay client"
    ),
    "R3": (
        "the same committed decisions + embedding record replay to the same "
        "byte-identical per-artifact SHA-256 on both Windows (UCRT) and WSL "
        "Linux (glibc) (6-decimal quantisation on both channels absorbs "
        "libm/backend drift)"
    ),
    "channel_exercise_annotation": (
        "construction witness (non-gate, side file, outside the manifest SHA "
        "set): honest distinct-zone / move-tick counts of a real-LLM's "
        "unscripted RESPONSE to the SAME pre-registered waypoint stimulus a "
        "scripted run receives (not an emergent/self-chosen route — only "
        "the response to the stimulus is unscripted) — NOT a "
        "traversal-success claim; a settled/blank run (0 moves, λ stays 0) "
        "is a legitimate, honestly-reported outcome, never retried until it "
        "moves"
    ),
    "firing_annotation": (
        "construction witness (non-gate, side file): the evaluation-phase "
        "sign inversion on the real (unscripted-response) run's own λ>0 "
        "tick(s), if any (see "
        "channel_exercise_annotation.settled_no_movement for whether there "
        "were any), generation-phase control non-vacuous, committed record "
        "pins knob-on"
    ),
    "done_formula": REAL_TRAVERSAL_DONE_FORMULA,
    "verdict": None,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass
closure, mirrors :data:`TRAVERSAL_OBSERVABLES`). Frozen at import time — not
derived from any run outcome. ``verdict`` is explicitly ``None``."""


def _attach_real_traversal_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the I4 real-mode ``observables`` overlay."""
    overlaid = dict(manifest)
    overlaid["observables"] = dict(REAL_TRAVERSAL_OBSERVABLES)
    return overlaid


async def real_capture(
    *,
    run_id: str,
    seed: int,
    model: str,
    embed_model: str,
    n_cognition_ticks: int = TRAVERSAL_HORIZON,
    physics_ticks_per_cognition: int = TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
) -> tuple[EclRunResult, dict[str, str], tuple[RecordedEmbeddingCall, ...]]:
    """I4 real-mode capture (**code path only — see module docstring**).

    Drives one knob-on record-mode traversal run against a REAL
    ``qwen3:8b`` (``think=False``) action-LLM and a REAL ``nomic-embed-text``
    embedding backend — both local Ollama (default ``127.0.0.1:11434``),
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` /
    :class:`~erre_sandbox.memory.embedding.EmbeddingClient`, both unmodified,
    read-only reuse. Real qwen3 receives the exact SAME pre-registered
    "proceed to ``<zone>``" waypoint stimulus a scripted (I1-I3) run does
    (``run_traversal_capture``'s ``observation_factory`` does not change with
    ``inner_chat``) and answers it however it genuinely chooses — the LLM's
    *response* is unscripted, the stimulus is not (a channel exercise, not a
    scripted traversal and not an emergent/self-chosen route; the recorded
    route may settle if the response never complies). The embedding channel
    is wrapped in :class:`~erre_sandbox.integration.\
embodied.traversal_live.EmbeddingRecordReplayClient` (record mode), so the
    real 768d vectors — and hence every downstream ``resolve_destination``
    centroid they drive — are captured for Ollama-free replay.

    Returns the run result, the rendered handoff-artifact dict (plus the new
    ``embedding_record.jsonl`` entry), and the raw recorded embedding calls
    (for a caller that wants them without re-parsing the rendered JSONL).
    """
    from erre_sandbox.inference.ollama_adapter import OllamaChatClient

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    real_chat = OllamaChatClient(model=model)
    embedding_wrapper = EmbeddingRecordReplayClient(
        inner=EmbeddingClient(model=embed_model)
    )
    seed_state = traversal_seed_agent_state()
    try:
        result = await run_traversal_capture(
            run_id=run_id,
            store=store,
            embedding=cast("EmbeddingClient", embedding_wrapper),
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            agent_state=seed_state,
            two_phase_knob=TwoPhaseKnob(),
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            inner_chat=real_chat,
        )
    finally:
        await embedding_wrapper.close()
        await real_chat.close()
        await store.close()

    embedding_calls = embedding_wrapper.used
    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    decisions_sha256 = hashlib.sha256(decisions_jsonl.encode("utf-8")).hexdigest()
    embedding_jsonl = _embedding_calls_to_jsonl(embedding_calls)
    embedding_sha256 = hashlib.sha256(embedding_jsonl.encode("utf-8")).hexdigest()
    env_pins = _real_env_pins(
        decisions_sha256=decisions_sha256,
        embedding_calls_sha256=embedding_sha256,
        model=model,
        embed_model=embed_model,
    )
    run_config = {
        "seed": seed,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
        "k_ecl": K_ECL,
        "base_ts": handoff.GOLDEN_TS.isoformat(),
        "retrieval_now": handoff.GOLDEN_TS.isoformat(),
    }
    rendered = handoff.render_golden(result, run_config=run_config, env_pins=env_pins)
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(_attach_real_traversal_observables(manifest)) + "\n"
    )
    rendered[_EMBEDDING_RECORD_FILENAME] = embedding_jsonl
    return result, rendered, embedding_calls


async def _real_replay(
    *,
    recorded_llm: Sequence[RecordedLlmCall],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    run_config: dict[str, Any],
) -> tuple[EclRunResult, RecordReplayChatClient, EmbeddingRecordReplayClient]:
    """Replay both committed I4 Plane 1 channels through the sibling driver."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    llm = RecordReplayChatClient(recorded=recorded_llm)
    embedding_client = EmbeddingRecordReplayClient(recorded=recorded_embedding)
    seed_state = traversal_seed_agent_state()
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=cast("EmbeddingClient", embedding_client),
            llm=llm,
            agent_state=seed_state,
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
            two_phase_knob=TwoPhaseKnob(),
            seed=int(cast("int", run_config["seed"])),
            n_cognition_ticks=int(cast("int", run_config["cognition_ticks"])),
            physics_ticks_per_cognition=int(
                cast("int", run_config["physics_ticks_per_cognition"])
            ),
            k_ecl=int(cast("int", run_config["k_ecl"])),
            observation_factory=traversal_observation_factory(seed_state.agent_id),
        )
    finally:
        await embedding_client.close()
        await store.close()
    return result, llm, embedding_client


def _check_artifact_bytes(
    *, label: str, name: str, actual_text: str, committed_text: str, expected_sha: str
) -> tuple[bool, str]:
    """One artifact's SHA-256 + byte-identity check (shared by both verifiers)."""
    actual_sha = hashlib.sha256(actual_text.encode("utf-8")).hexdigest()
    if actual_sha != expected_sha:
        return False, f"[{label}] FAIL {name} sha256 {actual_sha} != {expected_sha}"
    if actual_text != committed_text:  # pragma: no cover - defensive
        return False, f"[{label}] FAIL {name} byte mismatch despite matching sha256"
    return True, f"[{label}] OK {name} sha256 {actual_sha}"


async def real_verify(
    artifact_dir: Path, *, annotation_dir: Path | None = None
) -> bool:
    """Ollama-free replay-verify of a committed I4 real-mode bundle.

    Mirrors :func:`verify` but replays **both** Plane 1 channels (LLM via
    ``recorded_calls_from_jsonl`` + embedding via
    :func:`_embedding_calls_from_jsonl`) from their committed JSONL, and
    writes the channel-exercise count annotation
    (:func:`~erre_sandbox.integration.embodied.traversal_live.\
traversal_channel_exercise_summary`) in place of the W1 frozen-route check —
    there is no frozen route in real mode: the waypoint stimulus is the SAME
    pre-registered sequence a scripted run receives, but the LLM's *response*
    to it is genuinely unscripted, so the resulting route is not pinned.
    """
    write_dir = annotation_dir if annotation_dir is not None else artifact_dir
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    embedding_text = (artifact_dir / _EMBEDDING_RECORD_FILENAME).read_text(
        encoding="utf-8"
    )
    run_config = cast("dict[str, Any]", manifest["run"])

    recorded_llm = handoff.recorded_calls_from_jsonl(decisions_text)
    recorded_embedding = _embedding_calls_from_jsonl(embedding_text)
    result, llm, embedding_client = await _real_replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        run_config=run_config,
    )

    checks: list[tuple[bool, str]] = []
    # R2-equivalent — both channels inner_invocations == 0 + checksum match.
    checks.append(
        (
            llm.inner_invocations == 0,
            f"[real-verify] LLM inner_invocations={llm.inner_invocations}",
        )
    )
    checks.append(
        (
            embedding_client.inner_invocations == 0,
            "[real-verify] embedding inner_invocations="
            f"{embedding_client.inner_invocations}",
        )
    )
    # MEDIUM-1 review (forward-risk): inner_invocations==0 alone only proves
    # the replay never touched a live backend — it says nothing about WHICH
    # or HOW MANY of the committed embedding records were actually consumed.
    # A committed stream with extra trailing (or corrupted) records could
    # still replay "successfully" while silently under-consuming. Pin full
    # consumption directly: every recorded call, in order, was served.
    checks.append(
        (
            tuple(embedding_client.used) == tuple(recorded_embedding),
            "[real-verify] embedding replay consumed "
            f"{len(embedding_client.used)}/{len(recorded_embedding)} "
            "committed records",
        )
    )
    checks.append(
        (
            result.checksum == manifest["replay_checksum"],
            f"[real-verify] replay checksum {result.checksum} vs manifest "
            f"{manifest['replay_checksum']}",
        )
    )

    rendered = handoff.render_golden(
        result,
        run_config=run_config,
        env_pins=cast("dict[str, Any]", manifest["env_pins"]),
    )
    for name, committed_text in {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }.items():
        checks.append(
            _check_artifact_bytes(
                label="real-verify",
                name=name,
                actual_text=rendered[name],
                committed_text=committed_text,
                expected_sha=manifest["artifacts"][name]["sha256"],
            )
        )
    # embedding_record.jsonl — side channel pinned via env_pins (see
    # _real_env_pins), not the handoff artifacts SHA set.
    checks.append(
        _check_artifact_bytes(
            label="real-verify",
            name=_EMBEDDING_RECORD_FILENAME,
            actual_text=_embedding_calls_to_jsonl(recorded_embedding),
            committed_text=embedding_text,
            expected_sha=manifest["env_pins"]["embedding_record_sha256"],
        )
    )

    rerendered_manifest = (
        handoff.canonical_dumps(
            _attach_real_traversal_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    checks.append(
        (rerendered_manifest == manifest_text, "[real-verify] manifest.json re-render")
    )

    envelopes = handoff.validate_envelope_stream(envelope_text)
    print(f"[real-verify] OK {len(envelopes)} envelopes schema-conformant")
    for passed, message in checks:
        print(f"{message} {'OK' if passed else 'FAIL'}")
    ok = all(passed for passed, _ in checks)

    # Channel-exercise annotation (non-gate, side file) — replaces the W1
    # frozen-route check: real mode has no frozen itinerary to match against.
    channel_summary = traversal_channel_exercise_summary(result)
    (write_dir / _CHANNEL_EXERCISE_FILENAME).write_text(
        handoff.canonical_dumps(channel_summary) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "[real-verify] channel-exercise "
        f"distinct_zones={channel_summary['distinct_zone_count']} "
        f"move_ticks={channel_summary['move_tick_count']} "
        f"settled={channel_summary['settled_no_movement']}"
    )

    # Firing annotation (side file) — sourced from the committed decisions,
    # replayed through the SAME committed embedding record on both branches
    # (see _committed_firing_annotation's embedding_factory docstring for why
    # the mock default would be wrong here).
    annotation = await _committed_firing_annotation(
        recorded=recorded_llm,
        run_config=run_config,
        embedding_factory=lambda: EmbeddingRecordReplayClient(
            recorded=recorded_embedding
        ),
    )
    (write_dir / _ANNOTATION_FILENAME).write_text(
        handoff.canonical_dumps(annotation) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "[real-verify] annotation "
        f"fired={annotation['evaluation_phase_sign_inversion_fired']} "
        f"witness_ticks={annotation['witness_tick_count']} "
        f"eligible_ticks={annotation['eligible_tick_count']} "
        f"checksums_match={annotation['checksums_match']} "
        f"record_knob_on_pinned={annotation['record_knob_on_pinned']} "
        f"fail_mode={annotation['fail_mode']}"
    )

    print("[real-verify] BUNDLE OK" if ok else "[real-verify] BUNDLE MISMATCH")
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "aha M13 traversal reproducibility capture (Ollama-free scripted "
            "by default; --real is a channel-exercise code path — the sealed "
            "run itself requires a separate, explicitly user-ratified session)"
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one knob-on record-mode traversal run + write the artifacts",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed bundle + firing annotation",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help=(
            "I4 channel-exercise mode: real qwen3:8b + real nomic-embed-text "
            "instead of the scripted/mock plan+embedding source. --golden-dir "
            "defaults to experiments/20260723-aha-traversal-real/artifacts/ "
            "when --real is set. REQUIRES a separate, explicitly "
            "user-ratified session to actually run — see the module docstring."
        ),
    )
    parser.add_argument("--golden-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--model",
        default=_DEFAULT_REAL_MODEL,
        help="--real only: the Ollama chat model tag",
    )
    parser.add_argument(
        "--embed-model",
        default=_DEFAULT_REAL_EMBED_MODEL,
        help="--real only: the Ollama embedding model tag",
    )
    args = parser.parse_args(argv)

    golden_dir = args.golden_dir
    if golden_dir is None:
        golden_dir = _DEFAULT_REAL_ARTIFACT_DIR if args.real else _DEFAULT_GOLDEN_DIR
    run_id = args.run_id
    if run_id is None:
        run_id = _DEFAULT_REAL_RUN_ID if args.real else _DEFAULT_RUN_ID

    if args.verify:
        ok = asyncio.run(real_verify(golden_dir) if args.real else verify(golden_dir))
        return 0 if ok else 1

    if args.real:
        result, rendered, _embedding_calls = asyncio.run(
            real_capture(
                run_id=run_id,
                seed=args.seed,
                model=args.model,
                embed_model=args.embed_model,
            )
        )
    else:
        result, rendered = asyncio.run(capture(run_id=run_id, seed=args.seed))
    _write(golden_dir, rendered)
    print(f"[capture] wrote {len(rendered)} artifacts to {golden_dir}")
    print(f"[capture] replay_checksum = {result.checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
