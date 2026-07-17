"""aha!/DMN-ECN Phase 4b — λ↔two-phase knob *live activation* (construction).

FROZEN ADR ``.steering/20260717-aha-phase4b-construction-validation-live/
design-final.md`` (user 裁定 = Option A, organ 無改変). Phase 4 (PR #84) built the
λ↔two-phase knob — :func:`~erre_sandbox.erre.two_phase.two_phase_delta` (a
phase-signed replacement for the ES-3 divergence-only ``locomotion_delta``) wired
into :meth:`~erre_sandbox.cognition.cycle.CognitionCycle._locomotion_delta_for`
behind the presence-only :class:`~erre_sandbox.erre.two_phase.TwoPhaseKnob`
collaborator. This module *activates* that knob in a real-``qwen3:8b`` sealed
embodied loop so a human can **boolean-observe** the two-phase bias firing.

Why a *sibling driver* and not the ecl_v1 idiom (design-final §2/§4): the knob is a
:class:`CognitionCycle` **constructor** argument, unreachable from ``agent_state``.
The ecl_v1 ``live_v1.py`` idiom (seed ``agent_state`` and call the untouched
``run_live_capture``) cannot inject it, and ``loop.run_ecl_loop`` does not thread a
``two_phase_knob`` argument. Rather than modify the frozen organ (loop/cycle/handoff/
two_phase are all **無改変**, user 裁定 Option A), :func:`run_two_phase_capture`
reconstructs ``run_ecl_loop``'s drive body and passes ``two_phase_knob`` to the
cycle it builds. It **reuses** every importable organ part
(``WorldRuntime`` / ``EclRecordMode`` / ``Retriever`` / ``ManualClock`` /
``RecordReplayChatClient`` / ``ecl_trace_checksum`` and the intra-package private
helpers ``loop._SinkContext`` / ``loop._default_observation_factory`` /
``loop._build_decision``); only the sink closure and the drive loop are copied
(Codex HIGH-3). The single safety net for that copy is the fidelity test
``run_two_phase_capture(two_phase_knob=None) ≡ run_ecl_loop`` (byte-identical
checksum + decisions + rows) — see ``test_two_phase_live.py``.

Firing witness (Codex HIGH-1, boolean/count only): with ``golden_agent_state()``'s
fixed ``deep_work`` mode (∈ ``EVALUATION_MODES``), the evaluation-phase bias inverts
the sign of the ES-3 locomotion offset. Two Ollama-free
:class:`~erre_sandbox.integration.embodied.live_v1.SamplingSpyChatClient` replays of
the *same* committed decisions — one knob-on, one knob-off — expose the per-tick
recomposed sampling (the replay client discards it, so the spy is mandatory). At a
λ>0 tick the knob-on sampling is *relatively* convergence-biased against knob-off
(``on.temperature < off.temperature`` ∧ ``on.top_p < off.top_p`` ∧
``on.repeat_penalty > off.repeat_penalty``) — :func:`sign_inversion_fired`. Both
replays' geometry checksum matches (the knob modulates sampling only, never the
trajectory).

Scope guard (design-final §7, binding, mirrors ``live_v1.py`` / ``loop.py``). This
is a **construction** apparatus, **NOT a measurement line — verdict は holding**. It
imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits
**no** floor / landscape / verdict / divergence / magnitude / detectability / aha
proxy / effect-size statistic. The firing summary is a pure boolean/count annotation
(a side file, outside the checksum / SHA / Done set), never a Done gate — the
effect's *detectability* is the frozen C-proper 第2リンク measurement line and is
**not measured** (firing⇔detectability 分離; door② UNMET, door CLOSED, R-budget=0).
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any, Final, cast

from erre_sandbox.cognition import BiasFiredEvent, CognitionCycle
from erre_sandbox.cognition.embodiment import K_ECL, EclRecordMode
from erre_sandbox.erre.locomotion_sampling import DEFAULT_LOCO_ALPHA
from erre_sandbox.erre.two_phase import (
    TWO_PHASE_GAIN_P,
    TWO_PHASE_GAIN_R,
    TWO_PHASE_GAIN_T,
    TwoPhaseKnob,
)
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import LIVE_MODEL, ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    EclReplayError,
    EclRunResult,
    EclTraceRow,
    RecordReplayChatClient,
    _build_decision,
    _default_observation_factory,
    _SinkContext,
    ecl_trace_checksum,
)
from erre_sandbox.memory import Retriever
from erre_sandbox.schemas import ERREMode, ERREModeName, LocomotionState
from erre_sandbox.world import ManualClock, WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime

    from erre_sandbox.cognition.reflection import Reflector
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclDecisionRecord
    from erre_sandbox.memory import EmbeddingClient, MemoryStore
    from erre_sandbox.schemas import (
        AgentState,
        Observation,
        PersonaSpec,
        SamplingBase,
    )

# --------------------------------------------------------------------------- #
# Pre-registered constants (sealed-run-before fixed, tune-to-pass closed)
# --------------------------------------------------------------------------- #

TWO_PHASE_LOCO_LAM0: Final[float] = 0.0
"""λ₀ seed for the live locomotion channel (design-final §5, non-tautology).

A **literal** ``0.0`` — never imported from ``evidence``. λ₀>0 would fabricate
"modulation with zero movement"; λ₀=0 honestly represents spawn-time rest, so any
phase-signed modulation must be *earned* by the agent changing zone and the EMA λ
climbing (mirrors ecl_v1 ``ECL_V1_LOCO_LAM0``, a coincident field default, not a
reused apparatus constant)."""

TWO_PHASE_N_COGNITION_TICKS: Final[int] = 32
"""Sealed Phase 4b live run horizon (v0/v1 parity): 32 cognition ticks. Fixed
before the sealed run; run-after tuning of λ₀ / persona / N is a Stop condition."""


# --------------------------------------------------------------------------- #
# Seeded factories — arm locomotion (+ choose the phase via the ERRE mode)
# --------------------------------------------------------------------------- #


def evaluation_seeded_agent_state() -> AgentState:
    """The golden agent, locomotion armed at λ₀, in an EVALUATION-phase mode.

    ``golden_agent_state()``'s fixed ``erre.name`` is already ``deep_work`` (∈
    ``EVALUATION_MODES``) and ``run_two_phase_capture`` wires no ERRE-mode FSM, so
    the mode — and therefore ``phase_of_mode`` = EVALUATION — is constant across the
    run: this is the **primary sign-inversion witness** seed, needing no mode
    override. Only ``locomotion`` is armed (from ``None`` to ``LocomotionState(lam=
    λ₀)``); every other field is byte-identical to the golden.
    """
    return handoff.golden_agent_state().model_copy(
        update={"locomotion": LocomotionState(lam=TWO_PHASE_LOCO_LAM0)},
    )


def generation_seeded_agent_state() -> AgentState:
    """The golden agent, locomotion armed, forced into a GENERATION-phase mode.

    The ERRE mode is overridden to ``peripatetic`` (∈ ``GENERATION_MODES``) so
    ``phase_of_mode`` = GENERATION. There ``two_phase_delta`` equals the frozen ES-3
    ``locomotion_delta`` (σ=(1,1,0), same pinned gains), so knob-on ≡ knob-off — the
    **phase-conditional control** that shows the bias fires *only* in the evaluation
    phase, not unconditionally. Its ``sampling_overrides`` stay at the golden's zero
    default, so the only knob-sensitive term is the locomotion delta.
    """
    return handoff.golden_agent_state().model_copy(
        update={
            "locomotion": LocomotionState(lam=TWO_PHASE_LOCO_LAM0),
            "erre": ERREMode(name=ERREModeName.PERIPATETIC, entered_at_tick=0),
        },
    )


# --------------------------------------------------------------------------- #
# Sibling driver — reconstruct run_ecl_loop's body + inject the knob (Option A)
#
# source = loop.run_ecl_loop; the sink closure and the drive loop are copied and
# the fidelity test (run_two_phase_capture(two_phase_knob=None) ≡ run_ecl_loop,
# byte-identical checksum + decisions + rows) is REQUIRED to pin the copy against
# organ drift (Codex HIGH-3 / LOW-3). Every other part is imported, not copied.
# --------------------------------------------------------------------------- #


async def run_two_phase_capture(
    *,
    run_id: str,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llm: RecordReplayChatClient,
    agent_state: AgentState,
    persona: PersonaSpec,
    retrieval_now: datetime,
    base_ts: datetime,
    two_phase_knob: TwoPhaseKnob | None,
    seed: int = 0,
    n_cognition_ticks: int = TWO_PHASE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factory: Callable[[int], Sequence[Observation]] | None = None,
) -> EclRunResult:
    """Drive one record/replay ECL run with ``two_phase_knob`` injected (Option A).

    A faithful reconstruction of
    :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` that differs by a
    **single line** — the ``two_phase_knob=two_phase_knob`` argument to the
    :class:`CognitionCycle` it builds. ``two_phase_knob=None`` reproduces
    ``run_ecl_loop`` byte-for-byte (the fidelity contract); a
    :class:`~erre_sandbox.erre.two_phase.TwoPhaseKnob` makes the cycle's locomotion
    sampling term phase-signed. The knob carries no gains — the modulation always
    uses the pinned ``two_phase`` module constants, so injecting it is a presence
    marker, never a per-run tuning surface (Codex MED-3).

    ``two_phase_knob`` is a **required** keyword so no call path is implicit about
    which side of the contrast it drives.
    """
    agent_id = agent_state.agent_id
    ecl_mode = EclRecordMode(
        run_id=run_id,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        k_ecl=k_ecl,
        reflection_disabled=True,
    )
    retriever = Retriever(store, embedding, now_factory=retrieval_now)
    bias_slot: list[BiasFiredEvent] = []
    cycle = CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=cast("Any", llm),
        rng=Random(seed),  # noqa: S311 — determinism seed, not cryptographic
        ecl_mode=ecl_mode,
        bias_sink=bias_slot.append,
        reflector=reflector,
        two_phase_knob=two_phase_knob,  # ← the ONLY divergence from run_ecl_loop
    )
    clock = ManualClock(start=0.0)
    ctx = _SinkContext()
    order_slot = sorted([agent_id]).index(agent_id)

    rows: list[EclTraceRow] = []

    def sink(
        sink_agent_id: str,
        physics_tick_index: int,
        x: float,
        y: float,
        z: float,
        yaw: float,
        pitch: float,
        zone: Any,
    ) -> None:
        md = ctx.move
        rows.append(
            EclTraceRow(
                run_id=run_id,
                agent_id=sink_agent_id,
                physics_tick_index=physics_tick_index,
                agent_tick=ctx.agent_tick,
                order_slot=order_slot,
                x=x,
                y=y,
                z=z,
                yaw=yaw,
                pitch=pitch,
                zone=zone,
                resolved_from=md.resolved_from if md is not None else None,
                move_centroid=md.centroid if md is not None else None,
                move_provenance=md.provenance if md is not None else None,
                move_jitter=md.jitter if md is not None else None,
                move_pre_clamp=md.pre_clamp if md is not None else None,
                move_post_clamp=md.post_clamp if md is not None else None,
                move_clamp_fired=md.clamp_fired if md is not None else None,
            )
        )

    world = WorldRuntime(
        cycle=cycle,
        clock=clock,
        physics_hz=30.0,
        ecl_trace_sink=sink,
    )
    world.register_agent(agent_state, persona)
    rt = world._agents[agent_id]  # noqa: SLF001 — driving the I3 seam (sanctioned)

    obs_factory = observation_factory or _default_observation_factory(agent_id)
    decisions: list[EclDecisionRecord] = []

    for agent_tick in range(n_cognition_ticks):
        ctx.agent_tick = agent_tick
        bias_slot.clear()
        for obs in obs_factory(agent_tick):
            world.inject_observation(agent_id, obs)
        used_before = len(llm.used)
        result = await world._step_one(rt)  # noqa: SLF001 — I3 seam driver
        world._consume_result(rt, result)  # noqa: SLF001 — wires MoveMsg → kinematics
        ctx.move = result.ecl_destination
        served = llm.used[used_before:]
        if len(served) != 1:
            msg = (
                f"two-phase cognition tick {agent_tick} served {len(served)} "
                "action-LLM calls; expected exactly 1 (reflection disabled)"
            )
            raise EclReplayError(msg)
        decisions.append(
            _build_decision(
                agent_tick=agent_tick,
                call=served[0],
                result=result,
                bias_fired=bias_slot[0] if bias_slot else None,
            )
        )
        for _ in range(physics_ticks_per_cognition):
            await world._on_physics_tick()  # noqa: SLF001 — I3 seam driver

    frozen_rows = tuple(rows)
    return EclRunResult(
        run_id=run_id,
        rows=frozen_rows,
        decisions=tuple(decisions),
        checksum=ecl_trace_checksum(frozen_rows),
    )


async def run_two_phase_live_capture(
    *,
    inner_chat: Any,
    store: MemoryStore,
    embedding: EmbeddingClient,
    run_id: str,
    persona: PersonaSpec,
    retrieval_now: datetime,
    base_ts: datetime,
    two_phase_knob: TwoPhaseKnob | None,
    agent_state: AgentState | None = None,
    seed: int = 0,
    n_cognition_ticks: int = TWO_PHASE_N_COGNITION_TICKS,
    physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    k_ecl: int = K_ECL,
    reflector: Reflector | None = None,
    observation_factory: Callable[[int], Sequence[Observation]] | None = None,
) -> EclRunResult:
    """Record-mode live-capture wrapper (mirror of ``live.run_live_capture``).

    Wraps ``inner_chat`` in :class:`~erre_sandbox.integration.embodied.live.\
ThinkOffChatClient` (forces ``think=False``) then a record-mode
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`, and
    drives :func:`run_two_phase_capture` with the knob. ``agent_state`` defaults to
    :func:`evaluation_seeded_agent_state` (deep_work=EVALUATION, locomotion armed) —
    the primary sign-inversion seed. The record-mode ``RecordReplayChatClient``
    captures each ``call.sampling`` verbatim, so a knob-on record commits the
    knob-on recomposed sampling into ``decisions.jsonl`` (Codex HIGH-2: verify then
    pins ``committed call.sampling == knob-on replay spy sampling``).
    """
    state = agent_state if agent_state is not None else evaluation_seeded_agent_state()
    think_off = ThinkOffChatClient(inner_chat)
    llm = RecordReplayChatClient(inner=think_off)
    return await run_two_phase_capture(
        run_id=run_id,
        store=store,
        embedding=embedding,
        llm=llm,
        agent_state=state,
        persona=persona,
        retrieval_now=retrieval_now,
        base_ts=base_ts,
        two_phase_knob=two_phase_knob,
        seed=seed,
        n_cognition_ticks=n_cognition_ticks,
        physics_ticks_per_cognition=physics_ticks_per_cognition,
        k_ecl=k_ecl,
        reflector=reflector,
        observation_factory=observation_factory,
    )


# --------------------------------------------------------------------------- #
# Firing witness — pure boolean/count only (Codex HIGH-1 / MED-1 / MED-4 / LOW)
# --------------------------------------------------------------------------- #

_SamplingTriple = tuple[float, float, float]


def quantise_sampling(sampling: ResolvedSampling) -> _SamplingTriple:
    """6-decimal (temperature, top_p, repeat_penalty) triple (Codex MED-1).

    The cross-platform comparison unit: repeat_penalty is a new per-tick byte point
    in the evaluation phase, so it is quantised on the same 6-decimal rule as the
    ES-3 sampling fields to absorb libm drift between Windows (UCRT) and Linux.
    """
    return (
        round(sampling.temperature, 6),
        round(sampling.top_p, 6),
        round(sampling.repeat_penalty, 6),
    )


def sign_inversion_fired(*, on: _SamplingTriple, off: _SamplingTriple) -> bool:
    """The evaluation-phase two-phase firing witness (Codex HIGH-1).

    ``on`` / ``off`` are the knob-on / knob-off **recomposed** per-tick sampling
    (from the :class:`SamplingSpyChatClient`, never the replay client's discarded
    ``call.sampling``). Fires iff the knob-on sampling is *relatively*
    convergence-biased against knob-off — temperature and top_p pushed **down**, and
    repeat_penalty pushed **up** — the σ=(−1,−1,+1) evaluation direction. This is a
    relative (on-vs-off) comparison, never an absolute-sign test (temperature/top_p
    are ordinarily positive). At a λ=0 tick both are equal, so it returns ``False``;
    a λ>0 tick with the frozen gains satisfies all three. Boolean only — no
    magnitude, spread, or effect is produced.
    """
    return on[0] < off[0] and on[1] < off[1] and on[2] > off[2]


def two_phase_firing_summary(
    *,
    on_samplings: Sequence[ResolvedSampling],
    off_samplings: Sequence[ResolvedSampling],
    on_checksum: str,
    off_checksum: str,
    committed_call_samplings: Sequence[ResolvedSampling] | None = None,
) -> dict[str, Any]:
    """Pure boolean/count firing annotation (non-gate, side file — Codex MED-4).

    Two spied replays of the *same* committed decisions (knob-on vs knob-off)
    expose the recomposed per-tick sampling. Per tick it records the knob-on/off
    6-decimal sampling and the :func:`sign_inversion_fired` boolean. The summary is
    pure boolean/count:

    * ``evaluation_phase_sign_inversion_fired`` — ``witness_tick_count >= 1``.
    * ``witness_tick_count`` — ticks satisfying the inversion witness (Codex LOW-1:
      a plain count, never a threshold / rate / ratio).
    * ``eligible_tick_count`` — ticks where knob-on ≠ knob-off (the λ>0 proxy).
    * ``fail_mode`` — ``None`` when fired, else ``"no_eligible_tick"`` (the agent
      never moved so λ stayed 0) or ``"eligible_no_inversion"`` (λ>0 ticks exist but
      none inverted — a construction failure, honestly recorded, Codex LOW-2).
    * ``checksums_match`` — both replays' geometry checksum equal (the knob
      modulates sampling only, never the trajectory).
    * ``record_knob_on_pinned`` — the committed ``call.sampling`` equals the knob-on
      replay spy sampling (Codex HIGH-2: the live record genuinely ran knob-on;
      ``None`` when not supplied). A mismatch is a construction failure.

    Carries **no** verdict / floor / divergence / magnitude / detectability / score:
    the effect's detectability is the frozen 第2リンク and is not measured here.
    ``verdict`` is an explicit ``None`` marker.
    """
    on_q = [quantise_sampling(s) for s in on_samplings]
    off_q = [quantise_sampling(s) for s in off_samplings]
    if len(on_q) != len(off_q):
        msg = f"spy sample-count mismatch: knob-on {len(on_q)} != knob-off {len(off_q)}"
        raise EclReplayError(msg)
    per_tick: list[dict[str, Any]] = []
    witness_tick_count = 0
    eligible_tick_count = 0
    for tick, (on_tick, off_tick) in enumerate(zip(on_q, off_q, strict=True)):
        eligible = on_tick != off_tick
        fired = sign_inversion_fired(on=on_tick, off=off_tick)
        eligible_tick_count += int(eligible)
        witness_tick_count += int(fired)
        per_tick.append(
            {
                "agent_tick": tick,
                "phase": "evaluation",
                "knob_on_sampling": list(on_tick),
                "knob_off_sampling": list(off_tick),
                "sign_inverted": fired,
            }
        )
    fired_overall = witness_tick_count >= 1
    if fired_overall:
        fail_mode: str | None = None
    elif eligible_tick_count == 0:
        fail_mode = "no_eligible_tick"
    else:
        fail_mode = "eligible_no_inversion"

    record_knob_on_pinned: bool | None = None
    if committed_call_samplings is not None:
        committed_q = [quantise_sampling(s) for s in committed_call_samplings]
        record_knob_on_pinned = committed_q == on_q

    return {
        "phase": "evaluation",
        "n_ticks": len(on_q),
        "per_tick": per_tick,
        "evaluation_phase_sign_inversion_fired": fired_overall,
        "witness_tick_count": witness_tick_count,
        "eligible_tick_count": eligible_tick_count,
        "fail_mode": fail_mode,
        "checksums_match": on_checksum == off_checksum,
        "record_knob_on_pinned": record_knob_on_pinned,
        "hard_gate": False,
        "verdict": None,
        "note": (
            "construction firing witness (non-gate, side file, outside the "
            "checksum/SHA/Done set): pure boolean/count of the knob-on-vs-knob-off "
            "recomposed per-tick sampling (SamplingSpy). The bias's detectability "
            "(whether it changes zone/behaviour/aha) is the frozen second link and "
            "is NOT measured here (firing vs detectability 分離)."
        ),
    }


# --------------------------------------------------------------------------- #
# Env-pin builder + observables pre-registration (mirror live_v1, MED-1/MED-5)
# --------------------------------------------------------------------------- #


def build_two_phase_env_pins(
    *,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    base_sampling: SamplingBase,
    decisions_sha256: str,
    gain_t: float = TWO_PHASE_GAIN_T,
    gain_p: float = TWO_PHASE_GAIN_P,
    gain_r: float = TWO_PHASE_GAIN_R,
    alpha: float = DEFAULT_LOCO_ALPHA,
    lam0: float = TWO_PHASE_LOCO_LAM0,
    model: str = LIVE_MODEL,
    base_env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the Phase 4b env pins onto ``handoff.capture_env_pins()``.

    Like the v1 builder the per-tick sampling is not a single resolved value, so the
    pins record the *inputs* — persona ``base_sampling`` + the frozen two-phase
    ``gain_t`` / ``gain_p`` / ``gain_r`` + ``alpha`` + ``lam0`` — plus the
    ``decisions_sha256`` (whose ``call.sampling`` column is the recorded knob-on
    sampling) and a ``two_phase_knob: "on"`` marker. ``think=False`` is pinned; the
    replay-determinism + byte-parity are the reproducibility claim, not the live
    record's cross-environment reproduction (Codex MED-5). ``handoff.py`` untouched.
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
    pins["two_phase_gains"] = {
        "gain_t": gain_t,
        "gain_p": gain_p,
        "gain_r": gain_r,
        "alpha": alpha,
    }
    pins["locomotion_lam0"] = lam0
    pins["two_phase_knob"] = "on"
    pins["decisions_sha256"] = decisions_sha256
    return pins


PHASE4B_DONE_FORMULA: Final[str] = "V1∧V2∧V3a∧V3b"
"""The FROZEN reproducibility-Done formula: the four reproducibility observables.
The firing annotation is a construction witness, not part of it (Codex MED-4)."""

PHASE4B_OBSERVABLES: Final[dict[str, Any]] = {
    "V1": (
        "N cognition x M physics ticks completed against a live Ollama qwen3:8b "
        "with the two-phase knob active (TwoPhaseKnob injected) and no exception "
        "(exit 0)"
    ),
    "V2": (
        "replaying the committed decisions.jsonl from the knob-on SEEDED state "
        "reproduces a byte-identical ecl_trace_checksum with inner_invocations==0"
    ),
    "V3a": (
        "the same committed decisions replay to the same checksum with "
        "inner_invocations==0 on both WSL Linux (glibc) and Windows (UCRT)"
    ),
    "V3b": (
        "the same raw Plane 2 re-renders every artifact SHA-256 identically on both "
        "platforms (6-decimal quantisation absorbs libm drift); the new byte-change "
        "points are per-tick call.sampling (temperature/top_p/repeat_penalty) and "
        "the envelope's locomotion.lam"
    ),
    "firing_annotation": (
        "construction witness (non-gate, side file, outside the checksum/SHA/Done "
        "set): the knob-on vs knob-off SamplingSpy replays disagree by an "
        "evaluation-phase sign inversion (on.temperature<off ∧ on.top_p<off ∧ "
        "on.repeat_penalty>off) on >=1 lambda>0 tick, both replays' checksum equal, "
        "and the committed call.sampling equals the knob-on replay sampling "
        "(record ran knob-on). Pure boolean/count; detectability NOT measured"
    ),
    "done_formula": PHASE4B_DONE_FORMULA,
    "verdict": None,
}
"""Sealed-run-before constant observables pre-registration (tune-to-pass closure).
Frozen at import time (not derived from any run outcome). ``verdict`` is explicitly
``None`` — construction validation, not a measurement verdict."""


def build_two_phase_manifest_overlay() -> dict[str, Any]:
    """Return the sealed-run-before ``observables`` overlay block (a fresh copy)."""
    return dict(PHASE4B_OBSERVABLES)


def attach_two_phase_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the Phase 4b ``observables`` overlay (non-mutating).

    ``handoff.build_manifest`` (untouched) has no ``observables`` field; this is the
    Phase 4b live-capture seam that adds it on top.
    """
    overlaid = dict(manifest)
    overlaid["observables"] = build_two_phase_manifest_overlay()
    return overlaid


__all__ = [
    "PHASE4B_DONE_FORMULA",
    "PHASE4B_OBSERVABLES",
    "TWO_PHASE_LOCO_LAM0",
    "TWO_PHASE_N_COGNITION_TICKS",
    "attach_two_phase_observables",
    "build_two_phase_env_pins",
    "build_two_phase_manifest_overlay",
    "evaluation_seeded_agent_state",
    "generation_seeded_agent_state",
    "quantise_sampling",
    "run_two_phase_capture",
    "run_two_phase_live_capture",
    "sign_inversion_fired",
    "two_phase_firing_summary",
]
