#!/usr/bin/env python
"""M13 live-loop closure — I7 sealed capture CLI (the real run is spend-gated).

FROZEN ADR ``.steering/20260724-m13-live-loop-closure/design-final.md`` §5 Issue
007 ("real qwen3 sealed live-run は code-path のみ設計、実走は spend ratify で
別ゲート", the Phase 4b O5 idiom). Session record:
``.steering/20260904-m13-live-loop-i7-real-run/``.

Design-copied from ``scripts/aha_phase4b_two_phase_live_capture.py`` (the
``--capture``/``--verify`` skeleton) and ``scripts/aha_traversal_live_capture.py``
(the ``--real`` **two-channel** record/replay: action-LLM *and* embedding), with
the driven object swapped for the live-loop closure root
(``integration.embodied.live_loop.build_live_loop_world`` +
``run_live_loop_capture``, PR #89). organ / ``live_loop.py`` / ``inbound.py`` /
``gateway.py`` / production ``bootstrap.py`` are **imported and driven, never
modified** (Option A, ADR §4 Allowed Files).

Modes
-----
``--capture`` (default, **Ollama-free**)
    A *rehearsal* capture: the same bundle shape and the same code path the real
    run takes, but with a scripted inner chat + a constant-vector mock embedding
    behind ``httpx.MockTransport``. Opens no connection and spends nothing, so
    the whole ``--verify`` path can be proven structurally green **before** any
    spend is ratified.
``--capture --real --confirm-spend``
    The sealed run: a real
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` (``qwen3:8b``,
    ``think=False`` via the organ's own ``ThinkOffChatClient``) plus a real
    :class:`~erre_sandbox.memory.embedding.EmbeddingClient` (``nomic-embed-text``)
    wrapped in ``EmbeddingRecordReplayClient`` (record mode). ``--confirm-spend``
    is mandatory: importing or running this module without it never opens a live
    connection (spend ratify is a hard gate, not a convention).
``--verify`` (**Ollama-free**, one path for both bundle shapes)
    Replays the committed bundle twice and writes two side annotations — see
    "Verify" below.

Because both modes render the *same* artifact set through the *same* code, a
green rehearsal ``--verify`` is real evidence that the sealed bundle's
``--verify`` will be structurally green too; only the Plane-1 backends differ.

Bundle
------
Four ``handoff`` artifacts (``manifest.json`` / ``ecl_trace.jsonl`` /
``decisions.jsonl`` / ``envelope_stream.jsonl``, rendered by the **unmodified**
``handoff.render_golden``) plus two side files whose SHA-256 are carried in
``env_pins`` (``handoff.build_manifest`` tracks only its own three artifacts, the
same reason ``aha_traversal_live_capture`` pins its embedding record there):

* ``embedding_record.jsonl`` — the recorded embedding channel (Plane 1, #2).
* ``inbound_perturbations.jsonl`` — the *injected* perturbation ledger
  (``agent_tick`` / ``correlation_id`` / the ``WorldPerturbationMsg`` itself), so
  ``--verify`` rebuilds the observation feed from the committed bundle rather
  than from this module's frozen plan constant.

Verify
------
* **Plane G (W-golden, regression guard)** — the committed decisions + embedding
  record replay through the **unmodified** ``two_phase_live.run_two_phase_capture``
  (observation feed rebuilt from the committed ledger) and must reproduce the
  committed ``replay_checksum`` byte-for-byte with ``inner_invocations == 0`` on
  both channels, every artifact SHA-256 matching, manifest re-render identical.
* **Plane L (W-live, reachability witness)** — the same committed channels
  re-drive ``run_live_loop_capture`` Ollama-free; its checksum must equal Plane
  G's, and ``live_loop.wiring_reachability_summary`` (**unmodified**, imported) is
  written to ``wiring_reachability.json`` as a side annotation.
* ``two_phase_firing_annotation.json`` — the knob-on/knob-off ``SamplingSpy``
  replay pair reduced by the **unmodified** ``two_phase_firing_summary``.

Honest framing (binding, design-final.md §2 — do not weaken)
------------------------------------------------------------
What this harness can produce is a **real-backend run of the wiring**, never
aha / emergence / effect. Even a fully green sealed run says only "wiring reached
each seam (live, real qwen3)". Both annotations are boolean/count side files,
outside the Done set and never a gate; ``verdict`` is an explicit ``None``. This
is a construction apparatus, **not a measurement line**: it imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no floor /
landscape / divergence / magnitude / detectability / aha-proxy statistic.

Two further I7-specific boundaries, stated so no reader has to infer them:

1. **Cognition-side only is real.** Perturbations are a pre-registered scripted
   bounded sequence pushed straight into ``InboundSink``; **no live Godot client
   is involved** (the Godot send contract was covered by Issue 005, and this host
   has no godot binary). A real-Godot end-to-end session is a separate,
   environment-gated task.
2. **Not a wall-clock real-time session.** ``ManualClock(start=0.0)`` is used so
   the capture stays byte-parity replayable, exactly as the Plane-G golden
   requires. "Live" here means the cognition channels are real, not that the loop
   ran against a wall clock.
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

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff, live_loop
from erre_sandbox.integration.embodied.live import LIVE_MODEL, ThinkOffChatClient
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.traversal_live import (
    EmbeddingRecordReplayClient,
    RecordedEmbeddingCall,
)
from erre_sandbox.integration.embodied.two_phase_live import (
    TWO_PHASE_N_COGNITION_TICKS,
    build_two_phase_env_pins,
    evaluation_seeded_agent_state,
    run_two_phase_capture,
    two_phase_firing_summary,
)
from erre_sandbox.integration.inbound import (
    InboundSink,
    world_perturbation_to_perception,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import WorldPerturbationMsg, Zone
from erre_sandbox.world import ManualClock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.inference.ollama_adapter import ChatResponse
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.schemas import Observation

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXPERIMENT_DIR = _REPO_ROOT / "experiments" / "20260904-m13-live-loop-live"
_DEFAULT_REHEARSAL_DIR = _EXPERIMENT_DIR / "rehearsal"
_DEFAULT_REAL_DIR = _EXPERIMENT_DIR / "artifacts"

_REHEARSAL_RUN_ID: Final[str] = "m13-live-loop-i7-rehearsal"
_REAL_RUN_ID: Final[str] = "m13-live-loop-i7"

EMBEDDING_RECORD_FILENAME: Final[str] = "embedding_record.jsonl"
INBOUND_LEDGER_FILENAME: Final[str] = "inbound_perturbations.jsonl"
REACHABILITY_FILENAME: Final[str] = "wiring_reachability.json"
FIRING_ANNOTATION_FILENAME: Final[str] = "two_phase_firing_annotation.json"

LIVE_LOOP_EMBED_MODEL: Final[str] = "nomic-embed-text"
"""The embedding model the sealed run pins (Ollama-local, 768d) — the same one
``aha_traversal_live_capture``'s real mode uses."""

LIVE_LOOP_N_COGNITION_TICKS: Final[int] = TWO_PHASE_N_COGNITION_TICKS
"""Sealed horizon = 32 cognition ticks, imported from the Phase 4b constant
rather than re-declared: this run is the same shape as the closest sealed
precedent (32 x 20), so the two bundles stay comparable and no new horizon is
introduced at I7."""

LIVE_LOOP_MAX_DRAIN_PER_TICK: Final[int] = 1
"""One perturbation drained per cognition tick. The sink is preloaded with the
whole plan up front, so push order == tick order and perturbation *i* lands on
tick *i* — the same 1:1 alignment ``tests/test_integration/test_live_loop_golden.py``
relies on, which is what makes the injected ledger a faithful replay source."""


# --------------------------------------------------------------------------- #
# Pre-registered bounded perturbation plan (frozen; sealed-run-before)
# --------------------------------------------------------------------------- #

_PERTURBATION_ZONES: Final[tuple[Zone, ...]] = (
    Zone.STUDY,
    Zone.PERIPATOS,
    Zone.CHASHITSU,
    Zone.AGORA,
    Zone.GARDEN,
)
_PERTURBATION_MODALITY: Final[str] = "sight"
_PERTURBATION_INTENSITY: Final[float] = 0.4
_PERTURBATION_TEMPLATE: Final[str] = (
    "live-loop stimulus {tick}: movement and light from the {zone}"
)


def live_loop_perturbation_plan(
    *,
    agent_id: str,
    n_ticks: int,
    sent_at: datetime = handoff.GOLDEN_TS,
) -> tuple[WorldPerturbationMsg, ...]:
    """Build the frozen bounded stimulus sequence (one per cognition tick).

    A pure function of ``(agent_id, n_ticks, sent_at)`` and this module's frozen
    constants — never of a run outcome — so the plan is fixed before the sealed
    run and a re-bake reproduces it exactly. Each message is a *world stimulus*
    (``design-final.md`` DA-2 semantics): it carries no knob / mode /
    destination override, so it cannot bypass the cognition loop. ``source_zone``
    cycles the five zones deterministically; ``modality`` / ``intensity`` are
    constant so the only thing varying across ticks is the stimulus text and its
    origin zone.

    ``sent_at`` is pinned rather than left to ``_EnvelopeBase``'s
    ``default_factory=_utc_now``. This plan is synthesised **in-process** — it is
    never received over a wire — so a real send-time would be pure
    non-determinism in a committed artifact: two bakes of the same plan would
    differ, and with them the ledger SHA and the manifest. Pinning it to the
    record-mode clock is the same convention ``handoff``'s determinism checklist
    already states for the outbound side ("envelope sent_at pinned to the
    record-mode clock"). Nothing downstream reads it: ``sent_at`` is not one of
    the fields ``world_perturbation_to_perception`` copies, so this pin cannot
    touch cognition, geometry or the checksum — only the ledger's bytes.

    The stimulus is scripted; the model's *response* to it is not. That
    distinction is the honest one (``aha_traversal_live_capture``'s LOW-2 note):
    an unscripted response to a pre-registered stimulus is not an emergent or
    self-chosen behaviour.
    """
    plan: list[WorldPerturbationMsg] = []
    for index in range(n_ticks):
        zone = _PERTURBATION_ZONES[index % len(_PERTURBATION_ZONES)]
        plan.append(
            WorldPerturbationMsg(
                tick=0,
                sent_at=sent_at,
                target_agent_id=agent_id,
                modality=cast("Any", _PERTURBATION_MODALITY),
                source_zone=zone,
                content=_PERTURBATION_TEMPLATE.format(tick=index, zone=zone.value),
                intensity=_PERTURBATION_INTENSITY,
                correlation_id=f"wp-i7-{index:03d}",
            )
        )
    return tuple(plan)


# --------------------------------------------------------------------------- #
# Observables pre-registration (sealed-run-before, frozen at import time)
# --------------------------------------------------------------------------- #

LIVE_LOOP_DONE_FORMULA: Final[str] = "L1∧L2∧L3"
"""The FROZEN I7 reproducibility-Done formula. Both annotations (reachability,
firing) are construction side-notes and are deliberately NOT part of it —
the same split ``PHASE4B_DONE_FORMULA`` / ``REAL_TRAVERSAL_DONE_FORMULA`` make."""

LIVE_LOOP_OBSERVABLES: Final[dict[str, Any]] = {
    "L1": (
        "N cognition x M physics ticks completed through the live-loop closure "
        "root (build_live_loop_world + run_live_loop_capture, TwoPhaseKnob "
        "injected) against a live qwen3:8b (think=False) action-LLM AND a live "
        "nomic-embed-text embedding backend, with the pre-registered bounded "
        "perturbation plan injected via InboundSink, and no exception (exit 0)"
    ),
    "L2": (
        "replaying the committed decisions.jsonl + embedding_record.jsonl "
        "(BOTH Plane 1 channels) with the observation feed rebuilt from the "
        "committed inbound_perturbations.jsonl reproduces a byte-identical "
        "replay_checksum through the UNMODIFIED run_two_phase_capture, with "
        "inner_invocations==0 on both replay clients; the Plane L re-drive of "
        "run_live_loop_capture over the same committed channels reproduces the "
        "same checksum"
    ),
    "L3": (
        "the same committed bundle re-renders every artifact to the same "
        "SHA-256 on both Windows (UCRT) and WSL Linux (glibc) (6-decimal "
        "quantisation on both channels absorbs libm/backend drift)"
    ),
    "wiring_reachability_annotation": (
        "construction witness (non-gate, side file, outside the manifest SHA "
        "set): live_loop.wiring_reachability_summary's boolean per-correlation-id "
        "seam reachability -- 'wiring reached each seam' -- plus plain "
        "perturbation / envelope-kind / eligible-tick counts. Reachability is "
        "NOT causation, and the firing_summary / same_tick_envelope_observed "
        "seams are tick-level co-occurrence (correlation-id never reaches the "
        "outbound wire protocol, grill G2)"
    ),
    "firing_annotation": (
        "construction witness (non-gate, side file): the evaluation-phase sign "
        "inversion on this run's own lambda>0 tick(s), if any. A settled run "
        "(no eligible tick, lambda stays 0 -- Phase 4b run1's honest outcome) is "
        "reported as such and never retried until it fires"
    ),
    "scope_boundary": (
        "cognition-side real only: the action-LLM and embedding channels are "
        "real, the perturbations are a scripted bounded plan pushed straight "
        "into InboundSink, and NO live Godot client is involved (Issue 005 "
        "covered the Godot send contract). ManualClock(start=0.0) is used for "
        "byte-parity, so this is not a wall-clock real-time session either. A "
        "green run means 'wiring reached each seam (live, real qwen3)' -- never "
        "aha, emergence, or an effect"
    ),
    "done_formula": LIVE_LOOP_DONE_FORMULA,
    "verdict": None,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass
closure). Frozen at import time — not derived from any run outcome. ``verdict``
is an explicit ``None``: construction validation, never a measurement verdict."""


def attach_live_loop_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the I7 ``observables`` overlay (non-mutating)."""
    overlaid = dict(manifest)
    overlaid["observables"] = dict(LIVE_LOOP_OBSERVABLES)
    return overlaid


# --------------------------------------------------------------------------- #
# Ollama-free rehearsal backends (mirror the sibling scripts' mocks)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding backend — deterministic and Ollama-free."""
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


class _ScriptedInnerChat:
    """Rehearsal-only inner chat: re-serves the golden plan on every call.

    The same stand-in ``tests/test_integration/test_live_loop_golden.py`` uses.
    It exists so the rehearsal exercises the identical wrapper stack
    (``ThinkOffChatClient`` -> ``RecordReplayChatClient`` record mode) the real
    run does, with the only difference being what sits at the bottom.
    """

    def __init__(self) -> None:
        response = handoff.golden_recorded_calls()[0].response
        if response is None:  # pragma: no cover - the golden always carries one
            msg = "golden_recorded_calls()[0] carries no response to re-serve"
            raise RuntimeError(msg)
        self._response = response

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return self._response

    async def close(self) -> None:
        """No-op — kept so capture()'s teardown is uniform across both modes."""


# --------------------------------------------------------------------------- #
# Side-file serialisation (canonical, 6-decimal quantised via handoff)
# --------------------------------------------------------------------------- #


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embedding_call_to_dict(call: RecordedEmbeddingCall) -> dict[str, Any]:
    return {"kind": call.kind, "text": call.text, "vector": list(call.vector)}


def embedding_calls_to_jsonl(calls: Sequence[RecordedEmbeddingCall]) -> str:
    """Serialise the recorded embedding channel as canonical JSONL."""
    return "".join(
        f"{handoff.canonical_dumps(_embedding_call_to_dict(c))}\n" for c in calls
    )


def embedding_calls_from_jsonl(text: str) -> list[RecordedEmbeddingCall]:
    """Reconstruct the recorded embedding channel from committed JSONL."""
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


def injected_to_jsonl(injected: Sequence[live_loop.InjectedPerturbation]) -> str:
    """Serialise the *injected* perturbation ledger as canonical JSONL.

    One line per perturbation that was actually injected, in injection order —
    which is also drain order and (with :data:`LIVE_LOOP_MAX_DRAIN_PER_TICK` = 1)
    push order. Perturbations the driven loop *rejected* (a ``target_agent_id``
    mismatch) are deliberately not here: they never became a
    ``PerceptionEvent``, so they are not part of the observation feed a replay
    must reconstruct. Their count is pinned separately by the reachability
    annotation's ``target_agent_mismatch_count``.
    """
    return "".join(
        handoff.canonical_dumps(
            {
                "agent_tick": inj.agent_tick,
                "correlation_id": inj.correlation_id,
                "msg": inj.msg.model_dump(mode="json"),
            }
        )
        + "\n"
        for inj in injected
    )


def injected_from_jsonl(text: str) -> list[tuple[int, WorldPerturbationMsg]]:
    """Reconstruct ``(agent_tick, msg)`` pairs from the committed ledger."""
    entries: list[tuple[int, WorldPerturbationMsg]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        entries.append(
            (int(data["agent_tick"]), WorldPerturbationMsg.model_validate(data["msg"]))
        )
    return entries


def ledger_observation_factory(
    entries: Sequence[tuple[int, WorldPerturbationMsg]],
) -> Callable[[int], Sequence[Observation]]:
    """Rebuild the per-tick observation feed from a committed ledger.

    Applies the **same pure mapping** the driven loop applied
    (``inbound.world_perturbation_to_perception``, imported not re-implemented),
    so a Plane-G replay sees byte-identical observations without this script
    owning any mapping logic of its own. Shaped like
    ``LiveLoopCaptureResult.observation_factory`` so it drops straight into
    ``run_two_phase_capture(observation_factory=...)``.
    """
    by_tick: dict[int, list[Observation]] = {}
    for agent_tick, msg in entries:
        by_tick.setdefault(agent_tick, []).append(
            world_perturbation_to_perception(msg, tick=agent_tick)
        )

    def factory(agent_tick: int) -> Sequence[Observation]:
        return tuple(by_tick.get(agent_tick, ()))

    return factory


# --------------------------------------------------------------------------- #
# env pins
# --------------------------------------------------------------------------- #


def build_live_loop_env_pins(
    *,
    decisions_sha256: str,
    embedding_record_sha256: str,
    inbound_ledger_sha256: str,
    model: str,
    embed_model: str,
    capture_mode: str,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
) -> dict[str, Any]:
    """Merge the I7 pins onto the **unmodified** Phase 4b pin builder.

    ``build_two_phase_env_pins`` (organ) already carries the base sampling, the
    frozen two-phase gains, alpha, lambda0, ``think=False``, the knob marker and
    ``decisions_sha256`` — reused wholesale rather than re-derived. What I7 adds
    on top is the second Plane-1 channel, the inbound face, and the clock /
    capture-mode facts a reader needs to know this bundle is not a wall-clock
    real-time session.
    """
    pins: dict[str, Any] = dict(
        build_two_phase_env_pins(
            qwen3_model_digest=qwen3_model_digest,
            ollama_version=ollama_version,
            vram_gb=vram_gb,
            uv_lock_sha256=uv_lock_sha256,
            base_sampling=handoff.golden_persona().default_sampling,
            decisions_sha256=decisions_sha256,
            model=model,
        )
    )
    pins["embed_model"] = embed_model
    pins["embedding_record_sha256"] = embedding_record_sha256
    pins["inbound_perturbations_sha256"] = inbound_ledger_sha256
    pins["capture_mode"] = capture_mode
    pins["clock"] = "ManualClock(start=0.0)"
    pins["inbound_sent_at"] = (
        "pinned to the record-mode clock (handoff.GOLDEN_TS); the plan is "
        "synthesised in-process, never received over a wire"
    )
    pins["max_drain_per_tick"] = LIVE_LOOP_MAX_DRAIN_PER_TICK
    pins["inbound_face"] = (
        "InboundSink preloaded with the pre-registered bounded perturbation "
        "plan; no live Godot client (Issue 005 covered the send contract)"
    )
    return pins


# --------------------------------------------------------------------------- #
# capture (rehearsal + real share one code path; only the backends differ)
# --------------------------------------------------------------------------- #


async def capture(
    *,
    run_id: str,
    seed: int,
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int,
    real: bool,
    model: str = LIVE_MODEL,
    embed_model: str = LIVE_LOOP_EMBED_MODEL,
    qwen3_model_digest: str = "unknown",
    ollama_version: str = "unknown",
    vram_gb: float = 0.0,
    uv_lock_sha256: str = "unknown",
) -> tuple[live_loop.LiveLoopCaptureResult, dict[str, str]]:
    """Drive one knob-on live-loop capture and render the bundle (writes nothing).

    ``real=False`` (the default) uses the scripted chat + mock embedding, opening
    no connection at all; ``real=True`` constructs a real ``OllamaChatClient``
    (``think=False`` through the organ's ``ThinkOffChatClient``) and a real
    ``EmbeddingClient``. Everything downstream of those two objects — the record
    wrappers, the closure root, the perturbation plan, the artifact rendering —
    is byte-for-byte the same code in both modes, which is what makes the
    rehearsal a genuine rehearsal.
    """
    if real:
        from erre_sandbox.inference.ollama_adapter import OllamaChatClient

        inner_chat: Any = OllamaChatClient(model=model)
        embedding_inner: Any = EmbeddingClient(model=embed_model)
        capture_mode = "real"
    else:
        inner_chat = _ScriptedInnerChat()
        embedding_inner = _mock_embedding()
        capture_mode = "scripted-rehearsal"

    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding_wrapper = EmbeddingRecordReplayClient(inner=embedding_inner)
    llm = RecordReplayChatClient(inner=ThinkOffChatClient(inner_chat))
    plan = live_loop_perturbation_plan(
        agent_id=agent_state.agent_id,
        n_ticks=n_cognition_ticks,
        sent_at=handoff.GOLDEN_TS,
    )
    try:
        handle = live_loop.build_live_loop_world(
            run_id=run_id,
            store=store,
            embedding=cast("EmbeddingClient", embedding_wrapper),
            llm=llm,
            agent_state=agent_state,
            persona=persona,
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            two_phase_knob=TwoPhaseKnob(),
            seed=seed,
            clock=ManualClock(start=0.0),
        )
        sink = InboundSink(maxsize=max(len(plan), 1))
        for msg in plan:
            sink.push(msg)
        result = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=sink,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            max_drain_per_tick=LIVE_LOOP_MAX_DRAIN_PER_TICK,
        )
    finally:
        await embedding_wrapper.close()
        await inner_chat.close()
        await store.close()

    decisions_jsonl = handoff.decisions_to_jsonl(result.ecl.decisions)
    embedding_jsonl = embedding_calls_to_jsonl(embedding_wrapper.used)
    ledger_jsonl = injected_to_jsonl(result.injected)
    env_pins = build_live_loop_env_pins(
        decisions_sha256=_sha256(decisions_jsonl),
        embedding_record_sha256=_sha256(embedding_jsonl),
        inbound_ledger_sha256=_sha256(ledger_jsonl),
        model=model,
        embed_model=embed_model,
        capture_mode=capture_mode,
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
    )
    run_config = {
        "seed": seed,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
        "k_ecl": handoff.K_ECL,
        "base_ts": handoff.GOLDEN_TS.isoformat(),
        "retrieval_now": handoff.GOLDEN_TS.isoformat(),
    }
    rendered = handoff.render_golden(
        result.ecl, run_config=run_config, env_pins=env_pins
    )
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(attach_live_loop_observables(manifest)) + "\n"
    )
    rendered[EMBEDDING_RECORD_FILENAME] = embedding_jsonl
    rendered[INBOUND_LEDGER_FILENAME] = ledger_jsonl
    return result, rendered


def write_bundle(out_dir: Path, rendered: dict[str, str]) -> None:
    """Write every rendered artifact into ``out_dir`` (the only side effect)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# verify — Plane G (unmodified sibling driver) + Plane L (closure root re-drive)
# --------------------------------------------------------------------------- #


async def _plane_g_replay(
    *,
    recorded_llm: Sequence[RecordedLlmCall],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    ledger: Sequence[tuple[int, WorldPerturbationMsg]],
    run_config: dict[str, Any],
) -> tuple[EclRunResult, RecordReplayChatClient, EmbeddingRecordReplayClient]:
    """Replay both committed Plane-1 channels through the UNMODIFIED organ driver."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    llm = RecordReplayChatClient(recorded=recorded_llm)
    embedding_client = EmbeddingRecordReplayClient(recorded=recorded_embedding)
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=cast("EmbeddingClient", embedding_client),
            llm=llm,
            agent_state=evaluation_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            two_phase_knob=TwoPhaseKnob(),
            seed=int(run_config["seed"]),
            n_cognition_ticks=int(run_config["cognition_ticks"]),
            physics_ticks_per_cognition=int(run_config["physics_ticks_per_cognition"]),
            k_ecl=int(run_config["k_ecl"]),
            observation_factory=ledger_observation_factory(ledger),
        )
    finally:
        await embedding_client.close()
        await store.close()
    return result, llm, embedding_client


async def _plane_l_redrive(
    *,
    recorded_llm: Sequence[RecordedLlmCall],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    ledger: Sequence[tuple[int, WorldPerturbationMsg]],
    run_config: dict[str, Any],
    max_drain_per_tick: int,
) -> tuple[live_loop.LiveLoopWorld, live_loop.LiveLoopCaptureResult]:
    """Re-drive the closure root Ollama-free over the same committed channels.

    Rebuilds the inbound sink from the committed ledger (injection order == push
    order) so the driven loop re-injects exactly the perturbations the capture
    injected. Returns the handle too, because the caller must drain the world's
    broadcast queue afterwards for the ``no_double_send`` check.
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding_client = EmbeddingRecordReplayClient(recorded=recorded_embedding)
    llm = RecordReplayChatClient(recorded=recorded_llm)
    try:
        handle = live_loop.build_live_loop_world(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=cast("EmbeddingClient", embedding_client),
            llm=llm,
            agent_state=evaluation_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            two_phase_knob=TwoPhaseKnob(),
            seed=int(run_config["seed"]),
            k_ecl=int(run_config["k_ecl"]),
            clock=ManualClock(start=0.0),
        )
        sink = InboundSink(maxsize=max(len(ledger), 1))
        for _agent_tick, msg in ledger:
            sink.push(msg)
        capture_result = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=sink,
            n_cognition_ticks=int(run_config["cognition_ticks"]),
            physics_ticks_per_cognition=int(run_config["physics_ticks_per_cognition"]),
            max_drain_per_tick=max_drain_per_tick,
        )
    finally:
        await embedding_client.close()
        await store.close()
    return handle, capture_result


async def _spied_replay(
    *,
    recorded_llm: Sequence[RecordedLlmCall],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    ledger: Sequence[tuple[int, WorldPerturbationMsg]],
    run_config: dict[str, Any],
    knob: TwoPhaseKnob | None,
) -> tuple[list[Any], str]:
    """One knob-gated spied replay -> (per-tick recomposed sampling, checksum).

    The recorded ``call.sampling`` is discarded by the replay client, which is
    exactly why the spy is mandatory: the per-tick sampling the firing witness
    compares is the one the cognition cycle *recomposes*. Both branches read the
    SAME committed embedding record (a mock default would silently change the
    geometry and make ``record_knob_on_pinned`` meaningless).
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding_client = EmbeddingRecordReplayClient(recorded=recorded_embedding)
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded_llm))
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=cast("EmbeddingClient", embedding_client),
            llm=cast("RecordReplayChatClient", spy),
            agent_state=evaluation_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=handoff.GOLDEN_TS,
            base_ts=handoff.GOLDEN_TS,
            two_phase_knob=knob,
            seed=int(run_config["seed"]),
            n_cognition_ticks=int(run_config["cognition_ticks"]),
            physics_ticks_per_cognition=int(run_config["physics_ticks_per_cognition"]),
            k_ecl=int(run_config["k_ecl"]),
            observation_factory=ledger_observation_factory(ledger),
        )
    finally:
        await embedding_client.close()
        await store.close()
    return list(spy.sampled), result.checksum


async def committed_firing_annotation(
    *,
    recorded_llm: Sequence[RecordedLlmCall],
    recorded_embedding: Sequence[RecordedEmbeddingCall],
    ledger: Sequence[tuple[int, WorldPerturbationMsg]],
    run_config: dict[str, Any],
) -> dict[str, Any]:
    """Firing annotation (non-gate, side file) via the UNMODIFIED organ summary."""
    on_sampling, on_checksum = await _spied_replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
        knob=TwoPhaseKnob(),
    )
    off_sampling, off_checksum = await _spied_replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
        knob=None,
    )
    return two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_checksum,
        off_checksum=off_checksum,
        committed_call_samplings=[c.sampling for c in recorded_llm],
    )


def _check_bytes(
    *, name: str, actual_text: str, committed_text: str, expected_sha: str
) -> tuple[bool, str]:
    """One artifact's SHA-256 + byte-identity check."""
    actual_sha = _sha256(actual_text)
    if actual_sha != expected_sha:
        return False, f"[verify] {name} sha256 {actual_sha} != {expected_sha}"
    if actual_text != committed_text:  # pragma: no cover - defensive
        return False, f"[verify] {name} byte mismatch despite matching sha256"
    return True, f"[verify] {name} sha256 {actual_sha}"


async def verify(artifact_dir: Path, *, annotation_dir: Path | None = None) -> bool:
    """Ollama-free replay-verify of a committed I7 bundle (both planes).

    Never opens a connection: every backend is a replay client over the
    committed records. Writes the two side annotations into ``annotation_dir``
    (default: ``artifact_dir``) — both outside the manifest SHA set, so writing
    them can never change the bundle's integrity hashes.
    """
    write_dir = annotation_dir if annotation_dir is not None else artifact_dir
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
    trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
    envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
    embedding_text = (artifact_dir / EMBEDDING_RECORD_FILENAME).read_text(
        encoding="utf-8"
    )
    ledger_text = (artifact_dir / INBOUND_LEDGER_FILENAME).read_text(encoding="utf-8")
    run_config = cast("dict[str, Any]", manifest["run"])
    env_pins = cast("dict[str, Any]", manifest["env_pins"])

    recorded_llm = handoff.recorded_calls_from_jsonl(decisions_text)
    recorded_embedding = embedding_calls_from_jsonl(embedding_text)
    ledger = injected_from_jsonl(ledger_text)

    checks: list[tuple[bool, str]] = []

    # --- Plane G (W-golden): the UNMODIFIED sibling driver reproduces the run.
    plane_g, plane_g_llm, plane_g_embedding = await _plane_g_replay(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
    )
    checks.append(
        (
            plane_g_llm.inner_invocations == 0,
            f"[verify] Plane G LLM inner_invocations={plane_g_llm.inner_invocations}",
        )
    )
    checks.append(
        (
            plane_g_embedding.inner_invocations == 0,
            "[verify] Plane G embedding inner_invocations="
            f"{plane_g_embedding.inner_invocations}",
        )
    )
    checks.append(
        (
            tuple(plane_g_embedding.used) == tuple(recorded_embedding),
            "[verify] Plane G embedding replay consumed "
            f"{len(plane_g_embedding.used)}/{len(recorded_embedding)} records",
        )
    )
    checks.append(
        (
            plane_g.checksum == manifest["replay_checksum"],
            f"[verify] Plane G replay checksum {plane_g.checksum} vs manifest "
            f"{manifest['replay_checksum']}",
        )
    )

    # --- Artifact re-render: per-file SHA-256 + byte identity.
    rendered = handoff.render_golden(plane_g, run_config=run_config, env_pins=env_pins)
    for name, committed_text in {
        "ecl_trace.jsonl": trace_text,
        "decisions.jsonl": decisions_text,
        "envelope_stream.jsonl": envelope_text,
    }.items():
        checks.append(
            _check_bytes(
                name=name,
                actual_text=rendered[name],
                committed_text=committed_text,
                expected_sha=manifest["artifacts"][name]["sha256"],
            )
        )
    # Side files: pinned through env_pins (handoff tracks only its own three).
    checks.append(
        _check_bytes(
            name=EMBEDDING_RECORD_FILENAME,
            actual_text=embedding_calls_to_jsonl(recorded_embedding),
            committed_text=embedding_text,
            expected_sha=env_pins["embedding_record_sha256"],
        )
    )
    checks.append(
        _check_bytes(
            name=INBOUND_LEDGER_FILENAME,
            actual_text=injected_ledger_roundtrip(ledger_text),
            committed_text=ledger_text,
            expected_sha=env_pins["inbound_perturbations_sha256"],
        )
    )
    rerendered_manifest = (
        handoff.canonical_dumps(
            attach_live_loop_observables(json.loads(rendered["manifest.json"]))
        )
        + "\n"
    )
    checks.append(
        (rerendered_manifest == manifest_text, "[verify] manifest.json re-render")
    )

    envelopes = handoff.validate_envelope_stream(envelope_text)
    checks.append((True, f"[verify] {len(envelopes)} envelopes schema-conformant"))

    # --- Plane L (W-live): re-drive the closure root over the same channels.
    plane_l_handle, plane_l = await _plane_l_redrive(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
        max_drain_per_tick=int(env_pins["max_drain_per_tick"]),
    )
    checks.append(
        (
            plane_l.checksum == plane_g.checksum,
            f"[verify] Plane L re-drive checksum {plane_l.checksum} vs Plane G "
            f"{plane_g.checksum}",
        )
    )

    firing = await committed_firing_annotation(
        recorded_llm=recorded_llm,
        recorded_embedding=recorded_embedding,
        ledger=ledger,
        run_config=run_config,
    )
    broadcast_kinds = [env.kind for env in plane_l_handle.world.drain_envelopes()]
    reachability = live_loop.wiring_reachability_summary(
        plane_l,
        firing_summary=firing,
        broadcast_envelope_kinds=broadcast_kinds,
    )
    write_dir.mkdir(parents=True, exist_ok=True)
    (write_dir / REACHABILITY_FILENAME).write_text(
        handoff.canonical_dumps(reachability) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (write_dir / FIRING_ANNOTATION_FILENAME).write_text(
        handoff.canonical_dumps(firing) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    for passed, message in checks:
        print(f"{message} {'OK' if passed else 'FAIL'}")
    print(
        "[verify] reachability (annotation, non-gate) "
        f"all_seams={reachability['all_correlation_ids_reach_all_seams']} "
        f"perturbations={reachability['perturbation_count']} "
        f"no_double_send={reachability['no_double_send']} "
        f"target_agent_mismatch={reachability['target_agent_mismatch_count']} "
        f"eligible_ticks={reachability['eligible_tick_count']}"
    )
    print(
        "[verify] firing (annotation, non-gate) "
        f"fired={firing['evaluation_phase_sign_inversion_fired']} "
        f"witness_ticks={firing['witness_tick_count']} "
        f"eligible_ticks={firing['eligible_tick_count']} "
        f"checksums_match={firing['checksums_match']} "
        f"record_knob_on_pinned={firing['record_knob_on_pinned']} "
        f"fail_mode={firing['fail_mode']}"
    )
    ok = all(passed for passed, _ in checks)
    print("[verify] BUNDLE OK" if ok else "[verify] BUNDLE MISMATCH")
    return ok


def injected_ledger_roundtrip(text: str) -> str:
    """Re-serialise a committed ledger through parse -> render.

    Not a no-op read-back: parsing to :class:`WorldPerturbationMsg` and
    re-rendering through :func:`injected_to_jsonl` proves the committed bytes
    are exactly what this apparatus' own serialiser produces for the messages
    they decode to — a hand-edited or schema-drifted ledger fails the byte
    check instead of being trusted verbatim.
    """
    return injected_to_jsonl(
        [
            live_loop.InjectedPerturbation(
                agent_tick=agent_tick,
                correlation_id=msg.correlation_id,
                msg=msg,
                observation=world_perturbation_to_perception(msg, tick=agent_tick),
            )
            for agent_tick, msg in injected_from_jsonl(text)
        ]
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "M13 live-loop I7 capture/verify. Ollama-free by default; --real "
            "opens a live qwen3:8b + nomic-embed-text session and therefore "
            "additionally requires --confirm-spend (a ratified-spend gate, not "
            "a convention)."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one knob-on live-loop record run and write the bundle",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify of a committed bundle (both planes)",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help=(
            "use the real qwen3:8b action-LLM + real nomic-embed-text embedding "
            "instead of the scripted/mock rehearsal backends. Also switches the "
            "default run-id and directory to the sealed-run ones."
        ),
    )
    parser.add_argument(
        "--confirm-spend",
        action="store_true",
        help="required alongside --capture --real: the ratified-spend gate",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--annotation-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--n-cognition-ticks", type=int, default=LIVE_LOOP_N_COGNITION_TICKS
    )
    parser.add_argument(
        "--physics-ticks-per-cognition",
        type=int,
        default=DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    )
    parser.add_argument("--model", default=LIVE_MODEL)
    parser.add_argument("--embed-model", default=LIVE_LOOP_EMBED_MODEL)
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument("--uv-lock-sha256", default="unknown")
    args = parser.parse_args(argv)

    default_dir = _DEFAULT_REAL_DIR if args.real else _DEFAULT_REHEARSAL_DIR
    default_run_id = _REAL_RUN_ID if args.real else _REHEARSAL_RUN_ID

    if args.verify:
        artifact_dir = args.artifact_dir if args.artifact_dir is not None else default_dir
        ok = asyncio.run(verify(artifact_dir, annotation_dir=args.annotation_dir))
        return 0 if ok else 1

    if args.real and not args.confirm_spend:
        print(
            "[capture] REFUSED: --real spends a live qwen3:8b + embedding "
            "session. Pass --confirm-spend only after the spend has been "
            "explicitly ratified (design-final.md Issue 007 gate)."
        )
        return 2

    out_dir = args.out_dir if args.out_dir is not None else default_dir
    run_id = args.run_id if args.run_id is not None else default_run_id
    result, rendered = asyncio.run(
        capture(
            run_id=run_id,
            seed=args.seed,
            n_cognition_ticks=args.n_cognition_ticks,
            physics_ticks_per_cognition=args.physics_ticks_per_cognition,
            real=args.real,
            model=args.model,
            embed_model=args.embed_model,
            qwen3_model_digest=args.qwen3_model_digest,
            ollama_version=args.ollama_version,
            vram_gb=args.vram_gb,
            uv_lock_sha256=args.uv_lock_sha256,
        )
    )
    write_bundle(out_dir, rendered)
    print(f"[capture] mode = {'real' if args.real else 'scripted-rehearsal'}")
    print(f"[capture] wrote {len(rendered)} artifacts to {out_dir}")
    print(f"[capture] replay_checksum = {result.checksum}")
    print(f"[capture] injected perturbations = {len(result.injected)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
