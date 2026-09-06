#!/usr/bin/env python
"""M13 society live-closure capture/verify CLI — Issue 007 (spend-gated real path).

Design-copy (not import — ``scripts/m13_live_loop_capture.py`` and
``scripts/m4_society_live_capture.py`` both stay untouched) of the
``--capture`` / ``--capture --real --confirm-spend`` / ``--verify`` triple those
two siblings established, retargeted at the N-agent live-closure root landed by
Issues 002-006 (``integration/embodied/society_live_loop.py``).

Three entry points, **one code path**:

``--capture``
    A *rehearsal*: the same bundle shape and the same code the sealed run
    would take, with the per-agent inner chat scripted and the embedder behind
    an ``httpx.MockTransport``. Opens no connection and spends nothing.
``--capture --real --confirm-spend``
    The sealed run: a real ``OllamaChatClient`` per agent (``think=False``
    forced by the organ's own ``ThinkOffChatClient``, which
    ``build_society_live_world`` wraps every inner chat in) plus a real
    ``EmbeddingClient``. :func:`assert_sealed_real_run` gates it **inside**
    :func:`capture`, **before any client is constructed**, and refuses three
    ways: an unratified spend, parameters that deviate from the frozen
    pre-registration, and unpinned provenance that would leave the artifact
    unauditable. **As of Issue 007 this path has never been executed**: the
    real spend is a separate, explicitly user-ratified gate (``design-final.md``
    grill G4), so what this issue lands is the code path, not a run.
``--verify``
    Ollama-free and CI/WSL-safe: it rebuilds the per-agent replay stream from
    the committed ``decisions.jsonl``, replays it through the **unmodified**
    ``society.py::run_society_loop``, and checks
    (a) Plane G byte-parity of ``ecl_trace_checksum`` / ``event_log_checksum``,
    (b) ``inner_invocations == 0`` on every channel,
    (c) **request conformance** — the replay-side spy's recomposed
    ``(agent_id, window, system_prompt, user_prompt)`` and ``(kind, text)``
    embedding requests against the committed record, with ``sampling``
    explicitly excluded (Codex **H-4**),
    (d) the fixed-constructor fingerprint recomputed from a fresh constructor
    call against the committed one, and
    (e) per-artifact SHA-256 + byte identity of a fresh re-render.
    It then writes/checks three **side annotations** (parity, conformance,
    per-agent firing) that live outside the manifest SHA set, so producing them
    can never change the bundle's integrity hashes.

Because the rehearsal and the sealed run render the same artifacts through the
same functions — only the two backend objects differ — **a green rehearsal
``--verify`` is real evidence that the sealed bundle's verify path holds**
(the precedent's DA-I7-1), not a separate toy.

**Honest framing (binding, ``design-final.md`` §2)**: this is *wiring* /
*construction* apparatus, never aha / emergence / effect. It imports no
``evidence`` / ``spdm`` / ``runningness`` machinery and computes no floor /
verdict / divergence / detectability / scorer statistic. The firing annotation
is a **non-gate** count: firing is not detectability.

**Not a wall-clock real-time session (Codex M-3)**: byte-parity is scoped to
the *scripted in-process perturbation sequence* the bundle commits. Real Godot
frames, real WebSocket arrival times and real LLM latency are external
non-determinism sources outside the replay set. No live Godot client is
involved at all (this host has no godot binary).
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
from erre_sandbox.integration.embodied.live import LIVE_MODEL
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
)
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    apply_self_other_env_pin,
    build_society_live_env_pins,
    fixed_constructor_fingerprint,
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
    society_embedding_record_to_jsonl,
    society_firing_annotation,
    society_injected_ledger_from_jsonl,
    society_injected_ledger_to_jsonl,
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
        SocietyLiveRunResult,
        SocietyPlaneGReplay,
    )
    from erre_sandbox.schemas import AgentState, PersonaSpec

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_EXPERIMENT_DIR: Final[Path] = _REPO_ROOT / "experiments" / "20260907-m13-society-live"
_DEFAULT_REHEARSAL_DIR: Final[Path] = _EXPERIMENT_DIR / "rehearsal"
_DEFAULT_REAL_DIR: Final[Path] = _EXPERIMENT_DIR / "artifacts"

REHEARSAL_RUN_ID: Final[str] = "m13-society-live-rehearsal"
REAL_RUN_ID: Final[str] = "m13-society-live"

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


# --------------------------------------------------------------------------- #
# Pre-registration — FROZEN AT IMPORT TIME (AC7)
#
# These are module constants, never derived from a run outcome and never
# reachable from the CLI: `main()` deliberately exposes no --seed /
# --cognition-ticks / --physics-ticks-per-cognition / --run-id flag, so an
# argparse error is the only thing a caller who tries gets. Changing any of
# them after a sealed run is tune-to-pass (Stop condition S3), not an edit.
# --------------------------------------------------------------------------- #

SOCIETY_LIVE_MODEL: Final[str] = LIVE_MODEL
"""Sealed action-LLM tag (``qwen3:8b``), imported from the organ's own
constant rather than re-spelled."""

SOCIETY_LIVE_EMBED_MODEL: Final[str] = "nomic-embed-text"
"""Sealed embedding model (Ollama-local, 768d) — the one every sibling sealed
run in this repo uses."""

SOCIETY_LIVE_SEED: Final[int] = 0
"""Sealed RNG seed. The experiment directory's ``SEED`` file carries the same
value."""

SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION: Final[int] = (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION
)
"""Sealed physics-per-cognition ratio (20), the repo-wide sealed value."""

SOCIETY_LIVE_PERTURBATION_COUNT: Final[int] = (
    len(SOCIETY_LIVE_AGENT_IDS) * SOCIETY_LIVE_N_COGNITION_TICKS
)
"""36 = N=3 agents x 12 windows, one stimulus per (agent, window) pair —
``design-final.md`` grill G1's frozen perturbation budget."""

SOCIETY_LIVE_THINK: Final[bool] = False
"""``think=False`` is not a flag here: ``build_society_live_world`` wraps every
inner chat in the organ's ``ThinkOffChatClient``, so the sealed value is
structurally enforced rather than passed (memory
``reference_qwen3_ollama_gotchas``)."""

SOCIETY_LIVE_DONE_FORMULA: Final[str] = "L1∧L2∧L3"
"""The FROZEN reproducibility-Done formula for the sealed society run. The
three side annotations are construction notes and are deliberately NOT part of
it, so none of them can ever be tuned into a pass."""


class SpendNotRatifiedError(RuntimeError):
    """A real (spending) capture was requested without an explicit ratification.

    The precedent's Codex **H-1**: a ``--confirm-spend`` gate that only guarded
    ``main()`` would leave a Python caller (a test, a notebook, a future sibling
    script) free to reach a live backend through ``capture(real=True)``. The
    gate therefore lives on the function that actually constructs the clients.
    """


class SealedParameterError(RuntimeError):
    """A real capture deviated from the pre-registration, or is unauditable.

    Two refusals share this type because both make the committed artifact lie
    about itself: a run driven with off-plan parameters would inherit
    :data:`SOCIETY_LIVE_CLOSURE_ANNOTATIONS`' frozen text that names the sealed
    ones, and a run whose ``qwen3_model_digest`` / ``ollama_version`` /
    ``vram_gb`` / ``uv_lock_sha256`` are unpinned could never be audited after
    the fact. Both are refused **before** anything is spent.
    """


class SealedBundleExistsError(RuntimeError):
    """A real capture would overwrite an existing sealed bundle.

    Silently overwriting ``artifacts/`` is exactly the mechanism a tune-to-pass
    re-run would use, and the pre-registration says a settled run is reported
    as such and never retried until it fires. Overwriting therefore requires an
    explicit ``--force`` plus a recorded reason.
    """


class BundleVerificationError(RuntimeError):
    """A committed bundle is structurally unusable (not merely non-matching)."""


_PLAN_JSON: Final[str] = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    },
    ensure_ascii=False,
)


# --------------------------------------------------------------------------- #
# Observables pre-registration (sealed-run-before, frozen at import time)
#
# Key is `annotations`, not `observables`: the society-scope convention
# (society_live.build_society_live_manifest_overlay) so the manifest never
# carries a `verdict` / `passed` / `score` / `floor` key at ANY nesting level.
# --------------------------------------------------------------------------- #

SOCIETY_LIVE_CLOSURE_ANNOTATIONS: Final[dict[str, Any]] = {
    "L1": (
        "holds ONLY for a bundle whose own env_pins record capture_mode == "
        "'real' and real_backend is True (Codex TASK-POST M-1: this text is "
        "shared verbatim by every bundle this harness renders, real or "
        "rehearsal, so the condition is stated up front rather than left "
        "implicit -- check real_run_status for what THIS bundle actually "
        "is before citing this sentence on its own): N=3 agents x 12 "
        "cognition windows x 20 physics ticks completed through the society "
        "live-closure root (build_society_live_world + "
        "run_society_live_loop driving the UNMODIFIED run_society_loop, "
        "TwoPhaseKnob injected, self_other_enabled=True) against a live "
        "qwen3:8b (think=False) action-LLM and a live nomic-embed-text "
        "embedding backend, with the pre-registered 36-message bounded "
        "perturbation plan injected via InboundSink, no exception (exit 0), "
        "and the full artifact set written. A capture_mode == "
        "'scripted-rehearsal' bundle (real_backend is False) does NOT "
        "satisfy this condition"
    ),
    "L2": (
        "replaying the committed decisions.jsonl + embedding_record.jsonl "
        "with the per-agent observation feed rebuilt from the committed "
        "inbound_ledger.jsonl reproduces byte-identical ecl_trace_checksum "
        "AND event_log_checksum through the UNMODIFIED run_society_loop "
        "(knob-off), with inner_invocations == 0 on every replay channel, and "
        "request conformance holding on both faces -- (agent_id, window, "
        "system_prompt, user_prompt) for the LLM and (kind, text) for the "
        "embedder -- with sampling explicitly excluded from the comparison"
    ),
    "L3": (
        "the same committed bundle re-renders every artifact to the same "
        "SHA-256 on both Windows (UCRT) and Linux (glibc), 6-decimal "
        "quantisation absorbing libm drift. What that measures exactly: bytes "
        "baked under UCRT replay identically under glibc -- it is NOT a "
        "re-bake of the capture on Linux, which is impossible there because a "
        "real Ollama session is not available on the CI runner"
    ),
    "done_formula": SOCIETY_LIVE_DONE_FORMULA,
    "side_files": (
        "plane_g_parity.json / request_conformance.json / "
        "firing_annotation.json are derived side files written OUTSIDE the "
        "manifest SHA set, so producing them can never change the bundle's "
        "integrity hashes. They are checked byte-for-byte against the "
        "committed copies on every verify"
    ),
    "firing_annotation": (
        "construction witness, NON-GATE and outside the Done formula: the "
        "per-agent evaluation-phase sign inversion on this run's own "
        "lambda>0 windows, if any. firing is not detectability. A settled run "
        "(no eligible window, lambda stays 0) is reported as such and is "
        "never retried until it fires"
    ),
    "scope_boundary": (
        "construction wiring only. A green run means 'the wiring reached each "
        "seam (live, real qwen3)' and never aha, emergence, or an effect. "
        "Cognition-side real only: the perturbations are a scripted "
        "in-process bounded plan pushed straight into InboundSink and NO live "
        "Godot client is involved (this host has no godot binary). "
        "run_society_loop's internal ManualClock(start=0.0) is what gives "
        "byte-parity, so this is not a wall-clock real-time session either"
    ),
    "real_run_status": (
        "NOT RUN as of Issue 007. This harness is code-path only: "
        "--capture --real --confirm-spend is implemented and gated but has "
        "never been executed, and the committed rehearsal bundle was produced "
        "Ollama-free. The real spend is a separate, explicitly user-ratified "
        "gate (design-final.md grill G4)"
    ),
    "preregistration_note": (
        "frozen at import time as module constants, never derived from a run "
        "outcome and not reachable from the CLI. Changing any of them after a "
        "sealed run is tune-to-pass (Stop condition S3), not an edit"
    ),
}
"""Sealed-run-before constant pre-registration (tune-to-pass closure).

Deliberately carries **no** ``verdict`` key at all — the society-scope
convention (``society_live.build_society_live_manifest_overlay``): construction
validation never renders a measurement verdict, not even a ``None`` one.
"""


def attach_society_live_annotations(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the frozen ``annotations`` overlay (non-mutating)."""
    overlaid = dict(manifest)
    overlaid["annotations"] = dict(SOCIETY_LIVE_CLOSURE_ANNOTATIONS)
    return overlaid


# --------------------------------------------------------------------------- #
# Ollama-free rehearsal doubles (the real path swaps exactly these two objects)
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
            model=SOCIETY_LIVE_MODEL,
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


def uv_lock_sha256() -> str:
    """SHA-256 of the repo's ``uv.lock`` (reproducibility-discipline env pin).

    Derived rather than hand-passed: a provenance pin a human has to remember
    to supply is the one that ends up unpinned in the artifact that mattered.
    Reading the file is deterministic and opens no connection.
    """
    lock_path = _REPO_ROOT / "uv.lock"
    if not lock_path.exists():  # pragma: no cover — the repo always ships one
        msg = f"uv.lock not found at {lock_path}; pass --uv-lock-sha256 explicitly"
        raise SealedParameterError(msg)
    return hashlib.sha256(lock_path.read_bytes()).hexdigest()


def _roster(
    agent_ids: Sequence[str],
) -> tuple[list[AgentState], dict[str, PersonaSpec]]:
    """The fixed N=3 constructors, filtered to ``agent_ids`` (reused, unmodified).

    ``society_live.py`` stays import-only: this is the single place capture and
    verify both go through, so a constructor drift between the two would be
    impossible rather than merely unlikely.
    """
    wanted = set(agent_ids)
    states = [s for s in society_live_agent_states() if s.agent_id in wanted]
    personas = {
        agent_id: persona
        for agent_id, persona in society_live_personas().items()
        if agent_id in wanted
    }
    return states, personas


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


def render_bundle(
    result: Any,
    *,
    ledger: Sequence[SocietyLedgerEntry],
    recorded_embedding: Sequence[Any],
    run_config: dict[str, Any],
    env_pins: dict[str, Any],
) -> dict[str, str]:
    """Render the Plane G bundle + the frozen ``annotations`` overlay.

    The single projection both :func:`capture` and :func:`verify` go through.
    Sharing it is what makes ``manifest.json``'s byte-identity check meaningful:
    a verify that re-rendered through a *different* overlay path would compare
    two things that were never supposed to match.
    """
    rendered = dict(
        society_plane_g_bundle(
            result,
            ledger=ledger,
            recorded_embedding=recorded_embedding,
            run_config=run_config,
            env_pins=env_pins,
        )
    )
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(attach_society_live_annotations(manifest)) + "\n"
    )
    return rendered


# --------------------------------------------------------------------------- #
# Spend / pre-registration / overwrite gates (enforced, not documented)
# --------------------------------------------------------------------------- #


def assert_sealed_real_run(
    *,
    confirm_spend: bool,
    model: str,
    embed_model: str,
    agent_ids: Sequence[str],
    n_cognition_ticks: int,
    physics_ticks_per_cognition: int,
    seed: int,
    perturbation_count: int,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_pin: str,
) -> None:
    """Gate a real capture **before** any client is constructed.

    Three refusals, in the order a reader would want them:

    1. **Not ratified** — ``confirm_spend`` is the ratified-spend gate; without
       it nothing opens (:class:`SpendNotRatifiedError`).
    2. **Off the pre-registration** — a real run must use the sealed roster,
       horizon, seed, perturbation budget, model and embedding backend, because
       :data:`SOCIETY_LIVE_CLOSURE_ANNOTATIONS` is frozen sealed-run-before text
       that names them. An exploratory sweep is a legitimate thing to want, but
       it is not this bundle and must not inherit this bundle's annotations.
    3. **Unpinned provenance** — an artifact whose model digest, Ollama
       version, VRAM or ``uv.lock`` hash is unpinned cannot be audited later,
       so the spend is refused rather than producing an unauditable record.

    Raises :class:`SpendNotRatifiedError` for (1) and
    :class:`SealedParameterError` for (2) and (3). Returns ``None`` when the
    run is cleared to spend — this function never opens anything itself.
    """
    if not confirm_spend:
        msg = (
            "real capture requires an explicitly ratified spend "
            "(confirm_spend=True / --confirm-spend). Issue 007 lands the code "
            "path only; the real run is a separate, user-ratified gate."
        )
        raise SpendNotRatifiedError(msg)

    sealed: tuple[tuple[str, object, object], ...] = (
        ("model", model, SOCIETY_LIVE_MODEL),
        ("embed_model", embed_model, SOCIETY_LIVE_EMBED_MODEL),
        ("agent_ids", tuple(agent_ids), tuple(SOCIETY_LIVE_AGENT_IDS)),
        ("n_cognition_ticks", n_cognition_ticks, SOCIETY_LIVE_N_COGNITION_TICKS),
        (
            "physics_ticks_per_cognition",
            physics_ticks_per_cognition,
            SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION,
        ),
        ("seed", seed, SOCIETY_LIVE_SEED),
        (
            "perturbation_count",
            perturbation_count,
            SOCIETY_LIVE_PERTURBATION_COUNT,
        ),
    )
    off_plan = [
        f"{name}={value!r} (pre-registered: {expected!r})"
        for name, value, expected in sealed
        if value != expected
    ]
    if off_plan:
        msg = (
            "real capture deviates from the sealed pre-registration: "
            + "; ".join(off_plan)
            + ". SOCIETY_LIVE_CLOSURE_ANNOTATIONS is frozen sealed-run-before "
            "text that names these values; a run with different ones needs its "
            "own pre-registration, not this one's."
        )
        raise SealedParameterError(msg)

    unpinned = [
        name
        for name, is_unpinned in (
            ("qwen3_model_digest", qwen3_model_digest.strip() in ("", "unknown")),
            ("ollama_version", ollama_version.strip() in ("", "unknown")),
            ("vram_gb", vram_gb <= 0.0),
            ("uv_lock_sha256", uv_lock_pin.strip() in ("", "unknown")),
        )
        if is_unpinned
    ]
    if unpinned:
        msg = (
            "real capture would produce an unauditable artifact — unpinned "
            f"provenance: {', '.join(unpinned)}. Supply them (run.ps1 reads "
            "them from the environment and fails fast when unset); the "
            "uv.lock hash is derived from this checkout automatically."
        )
        raise SealedParameterError(msg)


def assert_bundle_dir_writable(out_dir: Path, *, refuse_non_empty: bool) -> None:
    """Refuse to overwrite an existing sealed bundle (tune-to-pass closure).

    Called **before** the spend as well as before the write, so a real run that
    would clobber ``artifacts/`` fails while it is still free to fail. Only
    ``refuse_non_empty`` (real mode without ``--force``) refuses; the rehearsal
    directory stays freely re-bakeable, which is what the determinism checks
    depend on.
    """
    if not refuse_non_empty or not out_dir.exists():
        return
    existing = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    if existing:
        msg = (
            f"{out_dir} already holds a sealed bundle ({', '.join(existing)}). "
            "Overwriting it is how a tune-to-pass re-run would happen, and the "
            "pre-registration says a settled run is reported as such, never "
            "retried until it fires. Keep the first run and pass --force only "
            "with a recorded reason."
        )
        raise SealedBundleExistsError(msg)


# --------------------------------------------------------------------------- #
# capture (rehearsal + real share one code path; only the backends differ)
# --------------------------------------------------------------------------- #


async def capture(
    *,
    real: bool = False,
    confirm_spend: bool = False,
    run_id: str | None = None,
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
    n_cognition_ticks: int = SOCIETY_LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = SOCIETY_LIVE_PHYSICS_TICKS_PER_COGNITION,
    seed: int = SOCIETY_LIVE_SEED,
    k_ecl: int = K_ECL,
    model: str = SOCIETY_LIVE_MODEL,
    embed_model: str = SOCIETY_LIVE_EMBED_MODEL,
    qwen3_model_digest: str = "unknown",
    ollama_version: str = "unknown",
    vram_gb: float = 0.0,
    uv_lock_pin: str | None = None,
) -> tuple[SocietyLiveRunResult, dict[str, str]]:
    """Drive one knob-ON record-mode society closure and render its bundle.

    ``real=False`` (the default) uses :class:`_ScriptedInnerChat` per agent plus
    a mock-transport embedder and opens no connection at all. ``real=True``
    constructs a real ``OllamaChatClient`` per agent and a real
    ``EmbeddingClient`` — but only after :func:`assert_sealed_real_run` clears
    the spend. **The gate is here, on the function that builds the clients**,
    not only on the CLI: a Python caller that reaches for ``capture(real=True)``
    without ratification is refused exactly like a stray command line is.

    Everything downstream of those two objects — the record wrappers
    (``ThinkOffChatClient`` -> ``RecordReplayChatClient``, installed by
    ``build_society_live_world``), the closure root, the frozen perturbation
    plan, the artifact rendering — is byte-for-byte the same code in both
    modes. That is what makes the rehearsal a genuine rehearsal rather than a
    parallel toy.

    Knob-ON on purpose: Plane G's claim is that a knob-ON capture replays
    byte-identically through a knob-OFF unmodified ``run_society_loop``.

    ``uv_lock_pin`` defaults to ``None`` = derive it from this checkout's
    ``uv.lock``; pass a string only to pin a lock this checkout does not hold.
    """
    resolved_run_id = (
        run_id if run_id is not None else (REAL_RUN_ID if real else REHEARSAL_RUN_ID)
    )
    states, personas = _roster(agent_ids)
    plan = society_live_loop_perturbation_plan(
        agent_ids=list(agent_ids), n_ticks=n_cognition_ticks
    )
    lock_pin = uv_lock_pin if uv_lock_pin is not None else uv_lock_sha256()

    if real:
        assert_sealed_real_run(
            confirm_spend=confirm_spend,
            model=model,
            embed_model=embed_model,
            agent_ids=agent_ids,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            seed=seed,
            perturbation_count=len(plan),
            qwen3_model_digest=qwen3_model_digest,
            ollama_version=ollama_version,
            vram_gb=vram_gb,
            uv_lock_pin=lock_pin,
        )

    inner_chats: dict[str, Any]
    if real:
        # Imported here, not at module scope: the rehearsal path must not even
        # be able to name a live client, and this import is the ONLY place the
        # apparatus can reach one — reached only after the gate above cleared.
        from erre_sandbox.inference.ollama_adapter import (  # noqa: PLC0415
            OllamaChatClient,
        )

        inner_chats = {
            state.agent_id: OllamaChatClient(model=model) for state in states
        }
        inner_embedding: EmbeddingClient = EmbeddingClient(model=embed_model)
        capture_mode = "real"
    else:
        inner_chats = {state.agent_id: _ScriptedInnerChat() for state in states}
        inner_embedding = _mock_embedding()
        capture_mode = "scripted-rehearsal"

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    recorder = EmbeddingRecordReplayClient(inner=inner_embedding)
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats=inner_chats,
        store=store,
        embedding=cast("EmbeddingClient", recorder),
        inbound_sink=sink,
        knob=TwoPhaseKnob(),
        agent_states=states,
        personas=personas,
        max_drain_per_tick=len(states),
    )
    for msg in plan:
        sink.push(msg)
    try:
        run = await run_society_live_loop(
            world,
            run_id=resolved_run_id,
            retrieval_now=SEALED_TS,
            base_ts=SEALED_TS,
            seed=seed,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=physics_ticks_per_cognition,
            k_ecl=k_ecl,
        )
    finally:
        await inner_embedding.close()
        for chat in inner_chats.values():
            await chat.close()
        await store.close()

    ledger = society_ledger_entries(run.ledger.injected)
    recorded_embedding = tuple(recorder.used)
    ledger_jsonl = society_injected_ledger_to_jsonl(ledger)
    embedding_jsonl = society_embedding_record_to_jsonl(recorded_embedding)

    first_with_calls = next(
        (
            agent_id
            for agent_id in sorted(run.result.decisions)
            if run.result.decisions[agent_id]
        ),
        None,
    )
    if first_with_calls is None:
        msg = "the drive produced no recorded call; nothing to pin sampling from"
        raise BundleVerificationError(msg)
    resolved_sampling = run.result.decisions[first_with_calls][0].call.sampling

    env_pins = build_society_live_env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=lock_pin,
        resolved_sampling=resolved_sampling,
        agent_states=states,
        personas=personas,
        model=model,
        run_id=resolved_run_id,
        n_cognition_ticks=n_cognition_ticks,
        seed=seed,
    )
    apply_self_other_env_pin(env_pins, self_other_enabled=True)
    env_pins.update(
        {
            "embed_model": embed_model,
            "capture_mode": capture_mode,
            "real_backend": real,
            "wall_clock_real_time_session": False,
            "clock": "run_society_loop's internal ManualClock(start=0.0)",
            "inbound_sent_at": (
                "pinned to the record-mode clock; the plan is synthesised "
                "in-process, never received over a wire"
            ),
            "society_event_log_checksum": run.result.event_log_checksum,
            "society_cognition_step_order": list(run.result.cognition_step_order),
            "max_drain_per_tick": len(states),
            "knob_on": True,
            "perturbation_count": len(plan),
            "inbound_injected_count": len(ledger),
            "inbound_rejected_count": len(run.ledger.rejected),
            "inbound_dropped_count": run.ledger.dropped,
            "embedding_record_count": len(recorded_embedding),
            "inbound_ledger_sha256": _sha256(ledger_jsonl),
            "embedding_record_sha256": _sha256(embedding_jsonl),
        }
    )
    rendered = render_bundle(
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
    return run, rendered


def write_bundle(
    out_dir: Path, rendered: dict[str, str], *, refuse_non_empty: bool = False
) -> None:
    """Write every rendered artifact into ``out_dir`` (the only side effect)."""
    assert_bundle_dir_writable(out_dir, refuse_non_empty=refuse_non_empty)
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
    states, personas = _roster(agent_ids)
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
    committed records, so this is the code path a CI runner (and the WSL
    cross-platform check) takes on a bundle it could not possibly re-bake.
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

    # --- Fixed constructors: recompute the fingerprint, never trust the pin.
    fresh_states, fresh_personas = _roster(agent_ids)
    fresh_fingerprint = fixed_constructor_fingerprint(
        agent_states=fresh_states, personas=fresh_personas
    )
    checks.append(
        (
            env_pins.get("fixed_constructor_fingerprint") == fresh_fingerprint,
            "[verify] fixed_constructor_fingerprint matches a fresh constructor call",
        )
    )

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
    rendered = render_bundle(
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
        "[verify] capture_mode="
        f"{env_pins.get('capture_mode', 'unknown')} "
        f"real_backend={env_pins.get('real_backend')}"
    )
    print(
        "[verify] firing annotation is NON-GATE (firing is not detectability): "
        f"eligible={firing['eligible_tick_count']} "
        f"witness={firing['witness_tick_count']}"
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
    out_dir = (
        args.out_dir
        if args.out_dir is not None
        else (_DEFAULT_REAL_DIR if args.real else _DEFAULT_REHEARSAL_DIR)
    )
    refuse_non_empty = bool(args.real) and not bool(args.force)
    try:
        # Check the destination BEFORE the spend, not just before the write: a
        # real run that would clobber a sealed bundle should fail while it is
        # still free to fail.
        assert_bundle_dir_writable(out_dir, refuse_non_empty=refuse_non_empty)
        run, rendered = asyncio.run(
            capture(
                real=bool(args.real),
                confirm_spend=bool(args.confirm_spend),
                model=str(args.model),
                embed_model=str(args.embed_model),
                qwen3_model_digest=str(args.qwen3_model_digest),
                ollama_version=str(args.ollama_version),
                vram_gb=float(args.vram_gb),
                uv_lock_pin=args.uv_lock_sha256,
            )
        )
    except (
        SpendNotRatifiedError,
        SealedParameterError,
        SealedBundleExistsError,
    ) as exc:
        print(f"[capture] REFUSED: {exc}")
        return 2
    write_bundle(out_dir, rendered, refuse_non_empty=refuse_non_empty)
    for filename in sorted(rendered):
        print(f"[capture] wrote {out_dir / filename}")
    print(f"[capture] mode = {'real' if args.real else 'scripted-rehearsal'}")
    print(f"[capture] replay_checksum = {run.result.checksum}")
    print(f"[capture] injected perturbations = {len(run.ledger.injected)}")
    if not args.real:
        print(
            "[capture] Ollama-free scripted rehearsal (no backend was "
            "contacted). --real --confirm-spend is the separate, "
            "user-ratified spend gate."
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "M13 society live-closure Plane G capture/verify (construction "
            "wiring apparatus, not a measurement line). Ollama-free by "
            "default; --real opens a live qwen3:8b + nomic-embed-text session "
            "for every agent and therefore additionally requires "
            "--confirm-spend (a ratified-spend gate, not a convention). The "
            "pre-registered roster / horizon / seed / perturbation budget are "
            "frozen module constants and are deliberately NOT exposed as "
            "flags."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one record-mode closure and write the bundle",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify of a committed bundle",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help=(
            "use a real qwen3:8b action-LLM per agent + a real "
            "nomic-embed-text embedder instead of the rehearsal doubles. Also "
            "switches the default run-id and directory to the sealed ones. "
            "With --verify it only selects the sealed directory (verify never "
            "spends)."
        ),
    )
    parser.add_argument(
        "--confirm-spend",
        action="store_true",
        help="required alongside --capture --real: the ratified-spend gate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "allow a real capture to overwrite an existing sealed bundle. "
            "Only with a recorded reason: overwriting is how a tune-to-pass "
            "re-run would happen, and a settled run is meant to be kept."
        ),
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--annotation-dir", type=Path, default=None)
    parser.add_argument("--model", default=SOCIETY_LIVE_MODEL)
    parser.add_argument("--embed-model", default=SOCIETY_LIVE_EMBED_MODEL)
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument(
        "--uv-lock-sha256",
        default=None,
        help="override the uv.lock hash (default: derive it from this checkout)",
    )
    parser.add_argument(
        "--update-annotations",
        action="store_true",
        help="refresh committed side annotations on purpose (verify only)",
    )
    args = parser.parse_args(argv)

    if args.capture:
        return _capture_main(args)
    artifact_dir = (
        args.out_dir
        if args.out_dir is not None
        else (_DEFAULT_REAL_DIR if args.real else _DEFAULT_REHEARSAL_DIR)
    )
    ok = asyncio.run(
        verify(
            artifact_dir,
            annotation_dir=args.annotation_dir,
            update_annotations=args.update_annotations,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    sys.exit(main())
