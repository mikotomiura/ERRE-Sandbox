"""ECL v1 apparatus — locomotion→sampling channel *live activation* (construction).

FROZEN ADR ``.steering/20260707-ecl-v1-adr/design-final.md`` (§B/§C/§E/§F/§G).
The ES-3 locomotion→sampling channel is already fully wired in production
(``cognition/cycle.py`` composes ``locomotion_delta(agent_state.locomotion, …)``
as the third additive sampling term). This module *activates* that channel for a
live single-agent run **without changing the organ**: it constructs a seeded
:class:`~erre_sandbox.schemas.AgentState` whose ``locomotion`` is a non-``None``
:class:`~erre_sandbox.schemas.LocomotionState` (λ₀=0.0) and hands it, through the
existing ``agent_state`` argument, to the untouched
:func:`~erre_sandbox.integration.embodied.live.run_live_capture`. Everything the
ECL v0 organ owns (``cycle`` / ``loop`` / ``handoff`` /
``locomotion_sampling`` / ``live`` / ``golden_agent_state``) and every committed
v0 artifact stays byte-identical (§H: a single superseding axis — a live-capture
run may now carry a non-``None`` locomotion).

Pieces this module owns (none of which the v0 seam owns):

* :data:`ECL_V1_LOCO_LAM0` — the λ₀ seed, pinned to a **literal** ``0.0`` (§C):
  static rest is armed but *unmodulated*; the channel earns modulation only when
  the agent actually changes zone and the EMA λ climbs. Never imported from
  ``evidence`` (a fresh v1 constant that merely coincides with the field default).
* :func:`locomotion_seeded_agent_state` — the seeded factory (§B): the golden
  agent with ``locomotion`` set to ``LocomotionState(lam=ECL_V1_LOCO_LAM0)``.
* :func:`run_live_capture_v1` — a thin wrapper over the untouched
  :func:`live.run_live_capture` that only defaults ``agent_state`` to the seeded
  factory. No organ line changes.
* :class:`SamplingSpyChatClient` — the **sampling-spy** (Codex HIGH-1): a thin
  wrapper that records each ``chat`` call's ``sampling`` argument *before*
  delegating. V4a/V4b observe the per-tick sampling the cycle actually
  *recomposes* on an Ollama-free replay (physics-accurate current_zone), which
  ``RecordReplayChatClient`` otherwise discards (it re-serves the *recorded*
  call, so ``result.decisions[*].call.sampling`` is identical across a seeded and
  a locomotion-null replay — comparing it is a silent fail).
* :data:`LIVE_V1_OBSERVABLES` / :func:`build_live_v1_env_pins` — the sealed-run
  pre-registration (§F) and the env-pin builder (Codex MEDIUM-3: base sampling +
  gains + α + λ₀ + decisions SHA, never a single resolved sampling — the v1
  sampling is per-tick).

**Scope guard (§F/§G, binding — mirrors ``live.py`` / ``loop.py``).** This is a
*construction* apparatus, **NOT a measurement line — final judgement は holding**.
The channel activation is the *building* of a wired organ firing, never a
"walking→divergence" measurement: it imports no ``evidence`` / ``spdm`` /
``runningness`` machinery and computes/emits no floor / landscape / final
statistic. V4a/V4b are pre-registered boolean/counting *annotations* (side file,
outside the SHA/checksum set), never a Done gate and never a measurement-line
statistic. The frozen ES-3 gains are read from
:mod:`erre_sandbox.erre.locomotion_sampling` (the production live-wiring
defaults), not from ``evidence.es3_locomotion``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_ALPHA,
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
)
from erre_sandbox.integration.embodied import handoff, live
from erre_sandbox.integration.embodied.live import LIVE_MODEL
from erre_sandbox.integration.embodied.loop import DEFAULT_PHYSICS_TICKS_PER_COGNITION
from erre_sandbox.schemas import LocomotionState

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import (
        EclRunResult,
        RecordReplayChatClient,
    )
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import (
        AgentState,
        Observation,
        PersonaSpec,
        SamplingBase,
    )

# --------------------------------------------------------------------------- #
# Pre-registered v1 constants (sealed-run-before fixed, tune-to-pass closed)
# --------------------------------------------------------------------------- #

ECL_V1_LOCO_LAM0: Final[float] = 0.0
"""The λ₀ seed for the live locomotion channel (§C, ADR-binding, non-tautology).

A **literal** ``0.0`` — never imported from ``evidence.es3_locomotion``. λ₀>0
would fabricate "modulation with zero movement" and turn V4 into a tautology; λ₀=0
honestly represents spawn-time rest, so any sampling modulation must be *earned*
by the agent actually changing zone and the EMA λ climbing. That it coincides
with :attr:`~erre_sandbox.schemas.LocomotionState.lam`'s field default is a
virtue, not a reuse of a frozen apparatus constant — this is a fresh v1 pin, and
``test_v1_lam0_literal_pin`` asserts the literal and the no-``evidence``-import."""

LIVE_V1_N_COGNITION_TICKS: Final[int] = 32
"""Sealed v1 live run horizon (v0 parity): 32 cognition ticks. Fixed before the
sealed run; run-after tuning of λ₀ / persona / N is a Stop condition (§F
tune-to-pass closure, degradation branch D1)."""


# --------------------------------------------------------------------------- #
# Seeded factory — activate the channel via the existing agent_state argument
# --------------------------------------------------------------------------- #


def locomotion_seeded_agent_state() -> AgentState:
    """The golden agent with the locomotion channel armed at λ₀ (§B).

    :func:`~erre_sandbox.integration.embodied.handoff.golden_agent_state` (frozen,
    locomotion-``None``) copied with ``locomotion`` set to
    ``LocomotionState(lam=ECL_V1_LOCO_LAM0)``. Every other field is byte-identical
    to the golden, so the only new degree of freedom is the armed channel — the
    single superseding axis of §H. ``golden_agent_state`` itself is never mutated
    (``model_copy`` returns a fresh state).
    """
    return handoff.golden_agent_state().model_copy(
        update={"locomotion": LocomotionState(lam=ECL_V1_LOCO_LAM0)}
    )


# --------------------------------------------------------------------------- #
# Sampling-spy replay client (Codex HIGH-1) — observe the recomposed per-tick sampling
# --------------------------------------------------------------------------- #


class SamplingSpyChatClient:
    """Wraps a chat client and records each ``chat`` call's ``sampling`` (HIGH-1).

    Duck-typed to the ``chat`` keyword surface
    :class:`~erre_sandbox.cognition.CognitionCycle` calls, so it stands in
    transparently for the wrapped
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`. On
    each call it appends the ``sampling`` argument to :attr:`sampled` **before**
    delegating, then returns the inner client's response verbatim.

    Why this is mandatory for V4a/V4b (Codex HIGH-1): in replay mode
    ``RecordReplayChatClient`` re-serves the *recorded* call and appends *that*
    (with its recorded sampling) to ``used`` — it discards the ``sampling`` the
    cognition cycle just recomposed from the (seeded) locomotion state. So
    ``result.decisions[*].call.sampling`` is byte-identical across a seeded and a
    locomotion-null replay of the same committed decisions, and comparing it would
    silently pass. The recomposed per-tick sampling — the thing the locomotion
    channel actually modulates — is visible *only* at the ``chat`` boundary, which
    is what this spy captures.

    ``used`` / ``inner_invocations`` / ``is_replay`` delegate to the wrapped
    client so the spy is a drop-in for ``run_ecl_loop``'s driver (which reads
    ``llm.used``) and the replay-verify (which asserts ``inner_invocations == 0``).
    """

    def __init__(self, inner: RecordReplayChatClient) -> None:
        self._inner = inner
        self._sampled: list[ResolvedSampling] = []

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        self._sampled.append(sampling)
        return await self._inner.chat(
            messages,
            sampling=sampling,
            model=model,
            options=options,
            think=think,
        )

    @property
    def sampled(self) -> tuple[ResolvedSampling, ...]:
        """The per-tick ``sampling`` the cycle recomposed, in call order.

        On a replay this is the λ-modulated sampling the locomotion channel
        produced this tick (physics-accurate current_zone, since the real loop
        ran) — the V4a/V4b observation surface.
        """
        return tuple(self._sampled)

    @property
    def used(self) -> tuple[Any, ...]:
        """Delegate to the wrapped client (``run_ecl_loop`` reads ``llm.used``)."""
        return self._inner.used

    @property
    def inner_invocations(self) -> int:
        """Delegate: 0 in replay mode (the ``inner_invocations == 0`` witness)."""
        return self._inner.inner_invocations

    @property
    def is_replay(self) -> bool:
        """Delegate to the wrapped client's replay flag."""
        return self._inner.is_replay


# --------------------------------------------------------------------------- #
# Live capture harness (record mode) — organ untouched, only the seeded state differs
# --------------------------------------------------------------------------- #


async def run_live_capture_v1(
    *,
    inner_chat: Any,
    store: MemoryStore,
    embedding: EmbeddingClient,
    run_id: str,
    persona: PersonaSpec,
    retrieval_now: datetime,
    base_ts: datetime,
    agent_state: AgentState | None = None,
    seed: int = 0,
    n_cognition_ticks: int = LIVE_V1_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factory: Callable[[int], Sequence[Observation]] | None = None,
) -> EclRunResult:
    """Drive one record-mode ECL run with the locomotion channel active (§B).

    Identical to :func:`live.run_live_capture` — it wraps ``inner_chat`` in
    :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient` then a
    record-mode ``RecordReplayChatClient`` and calls the untouched
    :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` — **except** the
    default ``agent_state`` is :func:`locomotion_seeded_agent_state` (locomotion
    armed at λ₀) rather than the locomotion-null golden. The activation is purely
    the seeded ``agent_state`` argument; not one organ line changes. A caller may
    pass an explicit ``agent_state`` (e.g. the locomotion-null golden) to
    demonstrate flag-off byte-invariance against the v0 path.
    """
    state = agent_state if agent_state is not None else locomotion_seeded_agent_state()
    return await live.run_live_capture(
        inner_chat=inner_chat,
        store=store,
        embedding=embedding,
        run_id=run_id,
        agent_state=state,
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
# Env-pin builder (Codex MEDIUM-3) + observables pre-registration (§F)
# --------------------------------------------------------------------------- #


def build_live_v1_env_pins(
    *,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    base_sampling: SamplingBase,
    decisions_sha256: str,
    gain_t: float = DEFAULT_LOCO_GAIN_T,
    gain_p: float = DEFAULT_LOCO_GAIN_P,
    alpha: float = DEFAULT_LOCO_ALPHA,
    lam0: float = ECL_V1_LOCO_LAM0,
    model: str = LIVE_MODEL,
    base_env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the v1 env pins onto ``handoff.capture_env_pins()`` (Codex MEDIUM-3).

    Unlike the v0 live-capture pin (a single ``resolved_sampling``), the v1
    sampling is **per-tick** (the locomotion delta modulates it), so a single
    resolved value would be meaningless. The pins instead record the *inputs* that
    determine every per-tick sampling — the persona ``base_sampling``, the frozen
    locomotion ``gain_t`` / ``gain_p`` / ``alpha``, the ``lam0`` seed — plus the
    ``decisions_sha256`` of the committed ``decisions.jsonl`` (whose per-tick
    ``call.sampling`` column is the recorded, λ-modulated sampling). Also pins the
    model tag, qwen3 digest, Ollama version, VRAM, ``uv.lock`` hash, and the forced
    ``think=False`` — as the v0 builder does. ``handoff.py`` is never touched.
    """
    pins: dict[str, Any] = dict(
        base_env_pins if base_env_pins is not None else handoff.capture_env_pins()
    )
    pins["model"] = model
    pins["qwen3_model_digest"] = qwen3_model_digest
    pins["ollama_version"] = ollama_version
    pins["vram_gb"] = vram_gb
    pins["uv_lock_sha256"] = uv_lock_sha256
    pins["think"] = False
    pins["base_sampling"] = base_sampling.model_dump(mode="json")
    pins["locomotion_gains"] = {"gain_t": gain_t, "gain_p": gain_p, "alpha": alpha}
    pins["locomotion_lam0"] = lam0
    pins["decisions_sha256"] = decisions_sha256
    return pins


LIVE_V1_DONE_FORMULA: Final[str] = "V1∧V2∧V3a∧V3b"
"""The FROZEN reproducibility-Done formula (§F): the four reproducibility
observables. V4a/V4b/V5 are channel-active/diagnostic annotations, not part of it."""

LIVE_V1_OBSERVABLES: Final[dict[str, Any]] = {
    "V1": (
        "N cognition x M physics ticks completed against a live Ollama qwen3:8b "
        "with the locomotion channel active and no exception (exit 0)"
    ),
    "V2": (
        "replaying the committed decisions.jsonl from the SEEDED state reproduces "
        "a byte-identical ecl_trace_checksum with inner_invocations==0"
    ),
    "V3a": (
        "the same committed decisions replay to the same checksum with "
        "inner_invocations==0 on both WSL Linux (glibc) and Windows (UCRT)"
    ),
    "V3b": (
        "the same raw Plane 2 re-renders every artifact SHA-256 identically on "
        "both platforms (6-decimal quantisation absorbs libm drift); the only new "
        "byte-change points are per-tick call.sampling and the envelope's "
        "locomotion.lam"
    ),
    "V4a": (
        "channel-active annotation (non-gate, side file): the SEEDED spied "
        "replay's per-tick sampling has more than one distinct value (a pure "
        "distinct count, never a spread/variance statistic)"
    ),
    "V4b": (
        "channel-active annotation (non-gate, side file): the SEEDED and the "
        "locomotion-null spied replays disagree on at least one tick's 6-decimal "
        "sampling, while both replays' ecl_trace_checksum match. The sampling-spy "
        "is mandatory: the recorded call.sampling is identical across both replays"
    ),
    "V5": (
        "parsed-action diagnostic (non-gate): at least one tick with "
        "llm_status=='ok' and plan is not None and the MoveMsg "
        "resolved_from=='memory_centroid'"
    ),
    "done_formula": LIVE_V1_DONE_FORMULA,
    "verdict": None,
}
"""Sealed-run-before constant observables pre-registration (§F, tune-to-pass
closure). Frozen at import time (not derived from any run outcome). ``verdict`` is
explicitly ``None`` — this is construction validation, not a measurement verdict."""


def build_live_v1_manifest_overlay() -> dict[str, Any]:
    """Return the sealed-run-before v1 ``observables`` overlay block (a fresh copy)."""
    return dict(LIVE_V1_OBSERVABLES)


def attach_live_v1_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the v1 ``observables`` overlay attached (non-mutating).

    ``handoff.build_manifest`` (untouched) has no ``observables`` field; this is the
    v1 live-capture seam that adds it on top.
    """
    overlaid = dict(manifest)
    overlaid["observables"] = build_live_v1_manifest_overlay()
    return overlaid


__all__ = [
    "ECL_V1_LOCO_LAM0",
    "LIVE_V1_DONE_FORMULA",
    "LIVE_V1_N_COGNITION_TICKS",
    "LIVE_V1_OBSERVABLES",
    "SamplingSpyChatClient",
    "attach_live_v1_observables",
    "build_live_v1_env_pins",
    "build_live_v1_manifest_overlay",
    "locomotion_seeded_agent_state",
    "run_live_capture_v1",
]
