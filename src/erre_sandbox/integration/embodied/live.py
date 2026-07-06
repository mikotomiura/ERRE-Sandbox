"""ECL v0 live-capture apparatus — Issue 001 (loop/20260706-ecl-v0-live-run).

Builds the *apparatus* for a real-``qwen3:8b`` (Ollama) record-mode sealed run
of the Embodied Cognition Loop v0 organ (FROZEN ADR
``.steering/20260706-m13-forward-primary/design-final.md`` §FROZEN binding
a-e, §事前登録). The actual live capture is Issue 003; this module is
Ollama-free and fully testable with a mock inner chat client.

Two pieces this module owns, neither of which the existing seam owns:

* :class:`ThinkOffChatClient` — a driver-local wrapper that forces
  ``think=False`` on every ``chat`` call regardless of what the caller passed
  (Codex TASK-PRE HIGH-1). ``cognition.cycle.CognitionCycle`` calls
  ``llm.chat(..., sampling=...)`` without ever setting ``think``, and
  :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` only emits
  the wire-level ``think`` key when it is not ``None`` — so without this
  wrapper qwen3:8b spends its response budget on ``<think>`` reasoning and
  returns empty ``content``, and every action-LLM call fails to parse. The
  wrapper closes that gap **without touching** ``cognition/cycle.py``.
* :func:`run_live_capture` — dependency-injects an ``inner_chat`` (real
  ``OllamaChatClient`` in Issue 003, a mock in this module's tests), wraps it
  in :class:`ThinkOffChatClient` then
  :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` in
  *record* mode, and drives
  :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` — the existing
  Issue 004 harness, imported and called, never modified.

Pre-registered protocol constants (D-1/D-2/D-4/D-5, sealed-run-before fixed,
tune-to-pass closed): :data:`LIVE_N_COGNITION_TICKS` / :data:`LIVE_PERSONA_ID`
/ :data:`LIVE_EMBEDDING_MODE` / :data:`LIVE_O5_MIN_TICKS`.

Manifest env-pin + observables overlay (Codex TASK-PRE HIGH-1):
``handoff.build_manifest`` carries no ``observables`` field, so this module
supplies :func:`build_live_env_pins` (qwen3 digest / Ollama version / VRAM /
uv.lock hash / ``think:false`` / resolved sampling, merged into the manifest's
``env_pins`` block *without* touching ``handoff.py``) and
:func:`build_live_manifest_overlay` / :func:`attach_live_observables` (the
O1-O5 pre-registration, ``done_formula`` and ``o5_min_ticks``, attached as a
sealed-run-before constant ``observables`` block on top of the manifest dict
``handoff.build_manifest`` returns).

Scope guard (design-final.md §論点4/§論点5, binding, mirrors ``loop.py`` /
``handoff.py``). This is a *construction* apparatus, **NOT a measurement
line — final judgement は holding**. It imports no ``evidence`` / ``spdm`` /
``runningness`` machinery and computes/emits no floor / landscape / final
judgement statistic. O4/O5 are pre-registered *annotation* text only in this
module (Issue 001 scope); the actual per-tick counting (if ever computed) is a
non-gate boolean count, never a measurement-line statistic (§事前登録).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    RecordReplayChatClient,
    run_ecl_loop,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec

# --------------------------------------------------------------------------- #
# Pre-registered protocol constants (D-1/D-2/D-4/D-5, sealed-run-before fixed)
# --------------------------------------------------------------------------- #

LIVE_N_COGNITION_TICKS: Final[int] = 32
"""Sealed live run horizon (D-1): 32 cognition ticks (640 physics rows at the
default 20 physics-ticks-per-cognition), longer than the 8-tick synthetic
golden to construction-observe a longer-horizon completion. Fixed before the
sealed run; run-after tuning is a Stop condition (§事前登録 tune-to-pass
closure)."""

LIVE_PERSONA_ID: Final[str] = "kant"
"""Sealed live run persona (D-2): the golden's persona, single agent (D-2)."""

LIVE_EMBEDDING_MODE: Final[str] = "mock"
"""Sealed live run embedding source (D-4): a constant-vector mock (the same
family as ``scripts.ecl_v0_golden._offline_embedding``), never real
``nomic-embed-text``. Only the action-LLM chat call is live (minimal reality
surface, ADR §DA-FWD-2)."""

LIVE_O5_MIN_TICKS: Final[int] = 1
"""Minimum tick count for the O5 parsed-history-dependent-action annotation
(D-5): ``llm_status=="ok"`` and ``plan is not None`` and the MoveMsg
``resolved_from=="memory_centroid"`` on at least this many ticks is the
first-contact existence proof. **Not a hard green gate** — D-5 records O5 as a
count annotation with a human-judgement construction-validity branch, not an
autonomous pass/fail (Codex TASK-PRE HIGH-2: an autonomous gate on O5 would
tune-to-pass the loop toward it)."""

LIVE_DONE_FORMULA: Final[str] = "O1∧O2∧O3a∧O3b"
"""The FROZEN reproducibility-Done formula (design-final.md §事前登録): a
conjunction of the four reproducibility observables. O4/O5 are
channel-exercise annotations, not part of this formula."""

# --------------------------------------------------------------------------- #
# ThinkOffChatClient — force think=False without touching cognition/cycle.py
# --------------------------------------------------------------------------- #


class ThinkOffChatClient:
    """Wraps an inner chat client and forces ``think=False`` (Codex HIGH-1).

    Duck-typed to the same ``chat`` keyword surface
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient.chat`
    exposes (and that :class:`~erre_sandbox.cognition.CognitionCycle` calls),
    so it stands in transparently as the ``inner`` of a
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`.

    ``messages`` / ``sampling`` / ``model`` / ``options`` are forwarded
    unchanged; only ``think`` is overridden — whatever the caller passed (in
    practice always ``None``, since ``cognition/cycle.py`` never sets it) is
    replaced with ``False`` before the inner client is called. The inner
    client's :class:`~erre_sandbox.inference.ollama_adapter.ChatResponse` (or a
    raised
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaUnavailableError`) is
    returned/propagated verbatim.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,  # noqa: ARG002 — always overridden below
    ) -> ChatResponse:
        return await self._inner.chat(
            messages,
            sampling=sampling,
            model=model,
            options=options,
            think=False,
        )


# --------------------------------------------------------------------------- #
# Live capture harness (record mode only; replay reuses loop.replay_client_from)
# --------------------------------------------------------------------------- #


async def run_live_capture(
    *,
    inner_chat: Any,
    store: MemoryStore,
    embedding: EmbeddingClient,
    run_id: str,
    agent_state: AgentState,
    persona: PersonaSpec,
    retrieval_now: datetime,
    base_ts: datetime,
    seed: int = 0,
    n_cognition_ticks: int = LIVE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factory: Callable[[int], Sequence[Observation]] | None = None,
) -> EclRunResult:
    """Drive one record-mode ECL v0 run through ``inner_chat`` (real or mock).

    Wraps ``inner_chat`` in :class:`ThinkOffChatClient` (forces ``think=False``)
    then in a record-mode
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`, and
    hands both plus every other argument to the existing
    :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` driver
    **unmodified**. ``store`` / ``embedding`` are dependency-injected so this
    function never constructs its own Ollama or sqlite-vec connection — a live
    caller (Issue 003) wires a real ``OllamaChatClient``; the tests in this
    module wire a mock.
    """
    think_off = ThinkOffChatClient(inner_chat)
    llm = RecordReplayChatClient(inner=think_off)
    return await run_ecl_loop(
        run_id=run_id,
        store=store,
        embedding=embedding,
        llm=llm,
        agent_state=agent_state,
        persona=persona,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        k_ecl=k_ecl,
        reflector=reflector,
        observation_factory=observation_factory,
    )


# --------------------------------------------------------------------------- #
# Manifest env-pin + observables overlay (handoff.py untouched, overlay lives here)
# --------------------------------------------------------------------------- #


def build_live_env_pins(
    *,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    resolved_sampling: ResolvedSampling,
    base_env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the live-capture env pins onto ``handoff.capture_env_pins()``.

    Adds the fields the sealed live run must pin beyond the synthetic golden's
    ``env_pins`` (python/packages/godot/ERRE_ZONE_BIAS_P): the qwen3 model
    digest actually pulled, the Ollama server version, available VRAM, the
    ``uv.lock`` hash (reproducibility-discipline), the forced ``think=False``
    flag (D-5/Codex HIGH-1), and the cycle's live-resolved sampling verbatim
    (D-3: sampling is captured, never manually overridden). ``base_env_pins``
    defaults to a fresh :func:`~...handoff.capture_env_pins` snapshot so a
    caller can also pass a frozen snapshot for reproducible tests.
    """
    pins: dict[str, Any] = dict(
        base_env_pins if base_env_pins is not None else handoff.capture_env_pins()
    )
    pins["qwen3_model_digest"] = qwen3_model_digest
    pins["ollama_version"] = ollama_version
    pins["vram_gb"] = vram_gb
    pins["uv_lock_sha256"] = uv_lock_sha256
    pins["think"] = False
    pins["resolved_sampling"] = resolved_sampling.model_dump(mode="json")
    return pins


LIVE_OBSERVABLES: Final[dict[str, Any]] = {
    "O1": (
        "N cognition ticks x M physics ticks completed against a live Ollama "
        "qwen3:8b with no exception (full completion)"
    ),
    "O2": (
        "replaying from the captured decisions alone reproduces a "
        "byte-identical ecl_trace_checksum with inner_invocations==0"
    ),
    "O3a": (
        "the same committed decisions.jsonl replays to the same checksum "
        "with inner_invocations==0 on both WSL Linux (glibc) and Windows (UCRT)"
    ),
    "O3b": (
        "the same raw Plane 2 re-renders the full artifact set to the same "
        "SHA-256 set on both platforms (6-decimal float quantisation absorbs "
        "libm drift)"
    ),
    "O4": (
        "non-degeneracy: a pure boolean count (never a divergence/floor "
        "statistic) of whether the LLM chose >1 distinct destination zone "
        "and/or the resolver produced >1 distinct move target across the run "
        "(annotation, not a Done gate)"
    ),
    "O5": (
        "parsed-history-dependent-action count (D-5 refinement, annotation, "
        "not a hard green gate): the tick count where llm_status=='ok' and "
        "plan is not None and the MoveMsg resolved_from=='memory_centroid'; "
        f">= {LIVE_O5_MIN_TICKS} tick is the first-contact existence proof"
    ),
    "done_formula": LIVE_DONE_FORMULA,
    "o5_min_ticks": LIVE_O5_MIN_TICKS,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass
closure, Codex TASK-PRE HIGH-1): the O1-O5 definitions design-final.md
§事前登録 fixes, plus the FROZEN ``done_formula`` and the D-5
``o5_min_ticks`` threshold. Frozen at import time (not derived from any run
outcome), so a sealed run cannot retroactively redefine what it is judged
against."""


def build_live_manifest_overlay() -> dict[str, Any]:
    """Return the sealed-run-before ``observables`` overlay block (a fresh copy)."""
    return dict(LIVE_OBSERVABLES)


def attach_live_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the ``observables`` overlay attached (non-mutating).

    ``handoff.build_manifest`` (untouched) has no ``observables`` field; this
    function is the live-capture-side seam that adds it on top of the dict
    ``build_manifest`` returns, so ``handoff.py`` never needs to know about the
    live-capture pre-registration.
    """
    overlaid = dict(manifest)
    overlaid["observables"] = build_live_manifest_overlay()
    return overlaid


__all__ = [
    "LIVE_DONE_FORMULA",
    "LIVE_EMBEDDING_MODE",
    "LIVE_N_COGNITION_TICKS",
    "LIVE_O5_MIN_TICKS",
    "LIVE_OBSERVABLES",
    "LIVE_PERSONA_ID",
    "ThinkOffChatClient",
    "attach_live_observables",
    "build_live_env_pins",
    "build_live_manifest_overlay",
    "run_live_capture",
]
