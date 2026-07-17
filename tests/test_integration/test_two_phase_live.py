"""aha!/DMN-ECN Phase 4b — λ↔two-phase knob live-activation apparatus tests.

FROZEN ADR ``.steering/20260717-aha-phase4b-construction-validation-live/
design-final.md`` (user 裁定 = Option A / organ 無改変), Codex pre-impl review
(HIGH-1 firing witness / HIGH-2 record-knob-on pin / HIGH-3 fidelity coverage).

Ollama-free throughout: every test drives a *record* run through a mock inner chat
that re-serves a fixed plan, then *replays* the captured Plane 2 with
:class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` (no live
LLM). The sealed live run (real ``qwen3:8b`` + committed artifact + WSL byte-equality)
is a separate human-gated session.

Scope guard (design-final §7, binding — mirrors ``test_ecl_v1_locomotion.py``). This
is a *construction* apparatus, **NOT a measurement line**. It imports no ``evidence``
/ ``spdm`` / ``runningness`` machinery and computes/emits no floor / landscape /
verdict / divergence / magnitude / detectability / aha proxy statistic —
:func:`test_two_phase_measurement_guard` AST-scans ``two_phase_live.py`` /
``scripts/aha_phase4b_two_phase_live_capture.py`` / this module with the shared
enhanced 3-hole guard plus a Phase 4b exact-match extension.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx

from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
    locomotion_delta,
)
from erre_sandbox.erre.two_phase import (
    TWO_PHASE_GAIN_P,
    TWO_PHASE_GAIN_R,
    TWO_PHASE_GAIN_T,
    TwoPhase,
    TwoPhaseKnob,
    phase_of_mode,
    two_phase_delta,
)
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import (
    RecordedLlmCall,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.integration.embodied.two_phase_live import (
    TWO_PHASE_LOCO_LAM0,
    build_two_phase_env_pins,
    evaluation_seeded_agent_state,
    generation_seeded_agent_state,
    quantise_sampling,
    run_two_phase_capture,
    run_two_phase_live_capture,
    sign_inversion_fired,
    two_phase_firing_summary,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import (
    ERREModeName,
    LocomotionState,
    SamplingBase,
)
from tests.test_integration._measurement_guard import (
    assert_no_measurement_surface_v1,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

    from erre_sandbox.erre.two_phase import TwoPhaseKnob as _Knob
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult
    from erre_sandbox.schemas import AgentState, Observation

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_SRC = (
    _REPO_ROOT
    / "src"
    / "erre_sandbox"
    / "integration"
    / "embodied"
    / "two_phase_live.py"
)
_SCRIPT_SRC = _REPO_ROOT / "scripts" / "aha_phase4b_two_phase_live_capture.py"
_GOLDEN_TEST_SRC = (
    _REPO_ROOT / "tests" / "test_integration" / "test_two_phase_live_golden.py"
)

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_TEST_TICKS = 8  # enough for movement so the EMA λ climbs above 0

# Phase 4b measurement-surface extension (Codex MED-2): exact-match identifier/key
# bans. Exact (not substring) so ``generate`` / ``iterate`` / ``meaning`` do not
# false-trip; bare ``aha`` is deliberately NOT banned (legit in phase/script names).
_PHASE4B_BANNED_EXACT = frozenset(
    {
        "magnitude",
        "effect_size",
        "detectability",
        "score",
        "aha_proxy",
        "aha_score",
        "ratio",
        "rate",
        "mean",
        "std",
        "p_value",
    }
)


# --------------------------------------------------------------------------- #
# Ollama-free fixtures
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free)."""
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


class _MockInnerChat:
    """Ollama-free inner chat that re-serves a fixed plan every call.

    ``plan_json=None`` re-serves the golden plan (from ``golden_recorded_calls``);
    an explicit ``plan_json`` builds a fresh response (used by the bias fixture to
    supply a destination outside the persona's preferred zones).
    """

    def __init__(self, plan_json: str | None = None) -> None:
        if plan_json is None:
            resp = handoff.golden_recorded_calls()[0].response
            assert resp is not None
            self._response = resp
        else:
            self._response = ChatResponse(
                content=plan_json,
                model="qwen3:8b",
                eval_count=0,
                prompt_eval_count=0,
                total_duration_ms=0.0,
            )

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return self._response


def _record_llm(inner: _MockInnerChat) -> RecordReplayChatClient:
    return RecordReplayChatClient(inner=ThinkOffChatClient(inner))


async def _drive_ecl(
    *, inner: _MockInnerChat, agent_state: AgentState, **kwargs: Any
) -> EclRunResult:
    """Drive the untouched ``run_ecl_loop`` (the fidelity reference)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        return await run_ecl_loop(
            run_id="phase4b-test",
            store=store,
            embedding=embedding,
            llm=_record_llm(inner),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            **kwargs,
        )
    finally:
        await embedding.close()
        await store.close()


async def _drive_two_phase(
    *,
    inner: _MockInnerChat,
    agent_state: AgentState,
    two_phase_knob: _Knob | None,
    **kwargs: Any,
) -> EclRunResult:
    """Drive the sibling ``run_two_phase_capture`` (record mode)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        return await run_two_phase_capture(
            run_id="phase4b-test",
            store=store,
            embedding=embedding,
            llm=_record_llm(inner),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=two_phase_knob,
            **kwargs,
        )
    finally:
        await embedding.close()
        await store.close()


async def _spied_replay(
    *,
    recorded: Sequence[RecordedLlmCall],
    agent_state: AgentState,
    two_phase_knob: _Knob | None,
    n_ticks: int = _TEST_TICKS,
) -> tuple[list[ResolvedSampling], str]:
    """Replay committed decisions through the spy → (per-tick sampling, checksum)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded))
    try:
        result = await run_two_phase_capture(
            run_id="phase4b-test",
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", spy),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=two_phase_knob,
            n_cognition_ticks=n_ticks,
        )
    finally:
        await embedding.close()
        await store.close()
    return list(spy.sampled), result.checksum


async def _record_knob_on_recorded() -> tuple[EclRunResult, list[RecordedLlmCall]]:
    """Record one knob-on evaluation run and round-trip its Plane 2 through JSONL."""
    result = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
        n_cognition_ticks=_TEST_TICKS,
    )
    recorded = handoff.recorded_calls_from_jsonl(
        handoff.decisions_to_jsonl(result.decisions)
    )
    return result, recorded


# --------------------------------------------------------------------------- #
# Seeded factories + constants
# --------------------------------------------------------------------------- #


def test_two_phase_lam0_literal_pin() -> None:
    """λ₀ is a literal 0.0 and ``two_phase_live.py`` imports no ``evidence``."""
    assert TWO_PHASE_LOCO_LAM0 == 0.0
    assert isinstance(TWO_PHASE_LOCO_LAM0, float)
    src = _MODULE_SRC.read_text(encoding="utf-8")
    assert "erre_sandbox.evidence" not in src
    tree = ast.parse(src)
    assigned = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "TWO_PHASE_LOCO_LAM0"
    ]
    assert len(assigned) == 1
    value = assigned[0].value
    assert isinstance(value, ast.Constant)
    assert value.value == 0.0


def test_evaluation_seed_is_golden_deep_work_with_locomotion() -> None:
    """Evaluation seed = golden (deep_work ∈ EVALUATION) with locomotion armed at λ₀."""
    seeded = evaluation_seeded_agent_state()
    golden = handoff.golden_agent_state()
    assert seeded.locomotion == LocomotionState(lam=TWO_PHASE_LOCO_LAM0)
    assert seeded.erre.name == ERREModeName.DEEP_WORK
    assert phase_of_mode(seeded.erre.name) is TwoPhase.EVALUATION
    exclude = {"locomotion", "wall_clock"}
    assert seeded.model_dump(exclude=exclude) == golden.model_dump(exclude=exclude)


def test_generation_seed_is_generation_phase() -> None:
    """Generation seed forces a GENERATION-phase mode (peripatetic), loco armed."""
    seeded = generation_seeded_agent_state()
    assert seeded.locomotion == LocomotionState(lam=TWO_PHASE_LOCO_LAM0)
    assert seeded.erre.name == ERREModeName.PERIPATETIC
    assert phase_of_mode(seeded.erre.name) is TwoPhase.GENERATION


# --------------------------------------------------------------------------- #
# HIGH-3 — fidelity: run_two_phase_capture(knob=None) ≡ run_ecl_loop
# --------------------------------------------------------------------------- #


def _assert_run_equal(a: EclRunResult, b: EclRunResult) -> None:
    """Byte-identical: checksum + decisions + rows (Codex HIGH-3, all three)."""
    assert a.checksum == b.checksum
    assert handoff.decisions_to_jsonl(a.decisions) == handoff.decisions_to_jsonl(
        b.decisions
    )
    assert a.rows == b.rows


async def test_fidelity_default_params() -> None:
    """knob=None ≡ run_ecl_loop on the default happy path (locomotion-null golden)."""
    golden = handoff.golden_agent_state()
    ref = await _drive_ecl(
        inner=_MockInnerChat(), agent_state=golden, n_cognition_ticks=_TEST_TICKS
    )
    sib = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=golden,
        two_phase_knob=None,
        n_cognition_ticks=_TEST_TICKS,
    )
    _assert_run_equal(ref, sib)


async def test_fidelity_varied_params() -> None:
    """knob=None ≡ run_ecl_loop across varied fixtures (Codex HIGH-3 drift coverage).

    Custom observation_factory (two obs/tick), physics_ticks_per_cognition > 1 and
    non-default, more ticks, non-default seed / k_ecl, seeded locomotion state — so
    the copied sink closure + drive loop are exercised on a non-trivial trajectory,
    not just the empty happy path.
    """

    def obs_factory(agent_tick: int) -> Sequence[Observation]:
        from erre_sandbox.schemas import PerceptionEvent, Zone

        return [
            PerceptionEvent(
                tick=agent_tick,
                agent_id=handoff.GOLDEN_AGENT_ID,
                modality="sight",
                source_zone=Zone.STUDY,
                content=f"phase4b fidelity step {agent_tick} a",
                intensity=0.4,
            ),
            PerceptionEvent(
                tick=agent_tick,
                agent_id=handoff.GOLDEN_AGENT_ID,
                modality="sound",
                source_zone=Zone.PERIPATOS,
                content=f"phase4b fidelity step {agent_tick} b",
                intensity=0.3,
            ),
        ]

    kwargs: dict[str, Any] = {
        "n_cognition_ticks": 6,
        "physics_ticks_per_cognition": 5,
        "seed": 7,
        "k_ecl": 5,
        "observation_factory": obs_factory,
    }
    seeded = evaluation_seeded_agent_state()
    ref = await _drive_ecl(inner=_MockInnerChat(), agent_state=seeded, **kwargs)
    sib = await _drive_two_phase(
        inner=_MockInnerChat(), agent_state=seeded, two_phase_knob=None, **kwargs
    )
    _assert_run_equal(ref, sib)


async def test_fidelity_bias_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """knob=None ≡ run_ecl_loop when the persona-bias resample branch fires.

    A plan whose ``destination_zone`` (agora) is outside the golden persona's
    ``preferred_zones`` + ``ERRE_ZONE_BIAS_P=1`` drives ``_bias_target_zone`` to
    resample, exercising the ``bias_slot`` path both drivers copy. Both share the
    seed-derived bias RNG, so the resample is identical — the equality holds either
    way, and this fixture makes the branch non-empty.
    """
    monkeypatch.setenv("ERRE_ZONE_BIAS_P", "1.0")
    plan = json.dumps(
        {
            "thought": "wander",
            "utterance": "行こう",
            "destination_zone": "agora",
            "animation": "walk",
        }
    )
    golden = handoff.golden_agent_state()
    ref = await _drive_ecl(
        inner=_MockInnerChat(plan), agent_state=golden, n_cognition_ticks=_TEST_TICKS
    )
    sib = await _drive_two_phase(
        inner=_MockInnerChat(plan),
        agent_state=golden,
        two_phase_knob=None,
        n_cognition_ticks=_TEST_TICKS,
    )
    _assert_run_equal(ref, sib)


async def test_knob_on_modulates_recorded_sampling() -> None:
    """knob=on vs knob=None: same geometry checksum, different recorded call.sampling.

    The knob only modulates sampling (never the trajectory), so the geometry
    checksum is invariant; the recorded per-tick ``call.sampling`` differs because
    the evaluation-phase bias inverts the locomotion offset.
    """
    seeded = evaluation_seeded_agent_state()
    on = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=seeded,
        two_phase_knob=TwoPhaseKnob(),
        n_cognition_ticks=_TEST_TICKS,
    )
    off = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=seeded,
        two_phase_knob=None,
        n_cognition_ticks=_TEST_TICKS,
    )
    assert on.checksum == off.checksum, "geometry checksum must be knob-invariant"
    assert handoff.decisions_to_jsonl(on.decisions) != handoff.decisions_to_jsonl(
        off.decisions
    ), "recorded call.sampling must differ (evaluation-phase modulation)"


# --------------------------------------------------------------------------- #
# HIGH-1 — firing witness (sign inversion) + HIGH-2 record-knob-on pin
# --------------------------------------------------------------------------- #


def test_sign_inversion_fired_predicate() -> None:
    """The witness is a relative on-vs-off comparison, not an absolute-sign test."""
    # temp/top_p down, rp up → convergence-biased → fired.
    assert sign_inversion_fired(on=(0.5, 0.8, 1.2), off=(0.9, 1.0, 1.1)) is True
    # equal (λ=0) → not fired.
    assert sign_inversion_fired(on=(0.7, 0.9, 1.1), off=(0.7, 0.9, 1.1)) is False
    # only temperature inverted → not fired (all three required).
    assert sign_inversion_fired(on=(0.5, 0.9, 1.1), off=(0.9, 0.9, 1.1)) is False


async def test_firing_evaluation_sign_inversion() -> None:
    """HIGH-1: knob-on vs knob-off spy replays invert on >=1 evaluation λ>0 tick."""
    _result, recorded = await _record_knob_on_recorded()
    on_sampling, on_ck = await _spied_replay(
        recorded=recorded,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
    )
    off_sampling, off_ck = await _spied_replay(
        recorded=recorded,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=None,
    )
    # HIGH-1: the spy captures one sampling per served decision.
    assert len(on_sampling) == len(recorded)
    assert len(off_sampling) == len(recorded)

    summary = two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_ck,
        off_checksum=off_ck,
        committed_call_samplings=[c.sampling for c in recorded],
    )
    assert summary["evaluation_phase_sign_inversion_fired"] is True
    assert summary["witness_tick_count"] >= 1
    assert summary["eligible_tick_count"] >= 1
    assert summary["checksums_match"] is True, "geometry unperturbed by the knob"
    assert summary["fail_mode"] is None
    assert summary["verdict"] is None
    assert summary["hard_gate"] is False
    # HIGH-2: the committed sampling equals the knob-on replay sampling → the record
    # genuinely ran knob-on (a knob-off record would match the off replay instead).
    assert summary["record_knob_on_pinned"] is True


async def test_record_knob_on_pin_detects_wrong_knob() -> None:
    """HIGH-2 negative: a knob-off record fails the record-knob-on pin."""
    # Record with the knob OFF, then run the firing summary as if it were knob-on.
    off_result = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=None,
        n_cognition_ticks=_TEST_TICKS,
    )
    recorded = handoff.recorded_calls_from_jsonl(
        handoff.decisions_to_jsonl(off_result.decisions)
    )
    on_sampling, on_ck = await _spied_replay(
        recorded=recorded,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
    )
    off_sampling, off_ck = await _spied_replay(
        recorded=recorded,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=None,
    )
    summary = two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_ck,
        off_checksum=off_ck,
        committed_call_samplings=[c.sampling for c in recorded],
    )
    # The committed sampling was recorded knob-off → matches the off replay, not on.
    assert summary["record_knob_on_pinned"] is False


async def test_firing_uses_spy_not_recorded_call_sampling() -> None:
    """The recorded ``call.sampling`` is identical across knob-on/off replays.

    That is why the spy is mandatory: comparing ``result.decisions[*].call.sampling``
    across the two replays would silently pass (the replay client re-serves the
    recorded call regardless of the injected knob).
    """
    _result, recorded = await _record_knob_on_recorded()
    on = await _drive_two_phase_replay(recorded=recorded, two_phase_knob=TwoPhaseKnob())
    off = await _drive_two_phase_replay(recorded=recorded, two_phase_knob=None)
    on_call = [quantise_sampling(d.call.sampling) for d in on.decisions]
    off_call = [quantise_sampling(d.call.sampling) for d in off.decisions]
    assert on_call == off_call, (
        "recorded call.sampling is knob-invariant on replay — the firing witness "
        "must read the SamplingSpy, not decisions[*].call.sampling"
    )


async def _drive_two_phase_replay(
    *, recorded: Sequence[RecordedLlmCall], two_phase_knob: _Knob | None
) -> EclRunResult:
    """Replay committed decisions (no spy) with a given knob (helper for the above)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        return await run_two_phase_capture(
            run_id="phase4b-test",
            store=store,
            embedding=embedding,
            llm=RecordReplayChatClient(recorded=recorded),
            agent_state=evaluation_seeded_agent_state(),
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=two_phase_knob,
            n_cognition_ticks=_TEST_TICKS,
        )
    finally:
        await embedding.close()
        await store.close()


# --------------------------------------------------------------------------- #
# Generation-phase control (phase-conditionality)
# --------------------------------------------------------------------------- #


def test_generation_delta_equals_locomotion_delta() -> None:
    """two_phase_delta(GENERATION) ≡ locomotion_delta (phase-conditional identity)."""
    loco = LocomotionState(lam=0.5)
    gen = two_phase_delta(
        loco,
        phase_of_mode(ERREModeName.PERIPATETIC),
        gain_t=TWO_PHASE_GAIN_T,
        gain_p=TWO_PHASE_GAIN_P,
        gain_r=TWO_PHASE_GAIN_R,
    )
    loco_only = locomotion_delta(
        loco, gain_t=DEFAULT_LOCO_GAIN_T, gain_p=DEFAULT_LOCO_GAIN_P
    )
    assert gen == loco_only


async def test_generation_seed_no_inversion() -> None:
    """Control: in the generation phase knob-on ≡ knob-off (no sign inversion)."""
    _result, recorded = await _record_knob_on_recorded()
    on_sampling, _on_ck = await _spied_replay(
        recorded=recorded,
        agent_state=generation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
    )
    off_sampling, _off_ck = await _spied_replay(
        recorded=recorded,
        agent_state=generation_seeded_agent_state(),
        two_phase_knob=None,
    )
    on_q = [quantise_sampling(s) for s in on_sampling]
    off_q = [quantise_sampling(s) for s in off_sampling]
    assert on_q == off_q, "generation phase must not invert (two_phase_delta≡loco)"


# --------------------------------------------------------------------------- #
# Env pins + replay determinism
# --------------------------------------------------------------------------- #


def test_env_pins_structure() -> None:
    """Env pins carry base/gains/α/λ₀ + knob marker + decisions SHA, not a single
    resolved sampling."""
    pins = build_two_phase_env_pins(
        qwen3_model_digest="digest",
        ollama_version="0.0.0",
        vram_gb=16.0,
        uv_lock_sha256="lockhash",
        base_sampling=SamplingBase(),
        decisions_sha256="deadbeef",
        base_env_pins={},
    )
    assert "resolved_sampling" not in pins, "sampling is per-tick, not single"
    assert pins["base_sampling"] == SamplingBase().model_dump(mode="json")
    assert pins["two_phase_gains"] == {
        "gain_t": TWO_PHASE_GAIN_T,
        "gain_p": TWO_PHASE_GAIN_P,
        "gain_r": TWO_PHASE_GAIN_R,
        "alpha": pins["two_phase_gains"]["alpha"],
    }
    assert pins["locomotion_lam0"] == TWO_PHASE_LOCO_LAM0
    assert pins["two_phase_knob"] == "on"
    assert pins["decisions_sha256"] == "deadbeef"
    assert pins["think"] is False


async def test_replay_deterministic_knob_on() -> None:
    """Knob-on replay reproduces the capture checksum, Ollama-free (V2)."""
    recorded_result, recorded = await _record_knob_on_recorded()
    r1 = await _drive_two_phase_replay(recorded=recorded, two_phase_knob=TwoPhaseKnob())
    r2 = await _drive_two_phase_replay(recorded=recorded, two_phase_knob=TwoPhaseKnob())
    assert r1.checksum == recorded_result.checksum, "V2: replay reproduces capture"
    assert r1.checksum == r2.checksum, "replay is deterministic"


async def test_live_capture_wrapper_defaults_to_evaluation_seed() -> None:
    """``run_two_phase_live_capture`` defaults ``agent_state`` to the eval seed."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        result = await run_two_phase_live_capture(
            inner_chat=_MockInnerChat(),
            store=store,
            embedding=embedding,
            run_id="phase4b-test",
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            n_cognition_ticks=_TEST_TICKS,
        )
    finally:
        await embedding.close()
        await store.close()
    # Same evaluation seed as an explicit call → same checksum.
    explicit = await _drive_two_phase(
        inner=_MockInnerChat(),
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
        n_cognition_ticks=_TEST_TICKS,
    )
    assert result.checksum == explicit.checksum


# --------------------------------------------------------------------------- #
# Measurement-line non-re-entry guard + gain-override closure (MED-2/3/4)
# --------------------------------------------------------------------------- #


def _assert_no_phase4b_measurement_surface(tree: ast.Module) -> None:
    """Phase 4b exact-match extension over the shared guard (Codex MED-2)."""
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        for name in names:
            assert name.lower() not in _PHASE4B_BANNED_EXACT, name
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    assert key.value.lower() not in _PHASE4B_BANNED_EXACT, key.value


def test_two_phase_measurement_guard() -> None:
    """No measurement import/identifier/key/filename in any Phase 4b file."""
    for path, scan_strings in (
        (_MODULE_SRC, True),
        (_SCRIPT_SRC, True),
        (_THIS_FILE, False),
        (_GOLDEN_TEST_SRC, False),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
        _assert_no_phase4b_measurement_surface(tree)


def test_two_phase_knob_has_no_gain_override_surface() -> None:
    """MED-3: the knob is a presence marker; no gain/threshold/score tuning surface."""
    assert dataclasses.fields(TwoPhaseKnob) == ()
    sig = inspect.signature(run_two_phase_capture)
    forbidden = ("gain", "threshold", "score", "amplitude", "lam0", "alpha")
    for pname in sig.parameters:
        low = pname.lower()
        assert not any(tok in low for tok in forbidden), pname
    # The CLI exposes no gain/threshold/score flag either.
    script_src = _SCRIPT_SRC.read_text(encoding="utf-8")
    for flag in ("--gain", "--threshold", "--score", "--lam0", "--alpha"):
        assert flag not in script_src, flag


def test_firing_summary_is_side_file_shaped() -> None:
    """MED-4: the firing summary is a boolean/count annotation, never a Done gate."""
    base: dict[str, Any] = {
        "on_samplings": [],
        "off_samplings": [],
        "on_checksum": "x",
        "off_checksum": "x",
    }
    summary = two_phase_firing_summary(**base)
    assert summary["verdict"] is None
    assert summary["hard_gate"] is False
    # No measurement key leaks into the annotation.
    for key in summary:
        assert key.lower() not in _PHASE4B_BANNED_EXACT, key
    # Empty run → no eligible tick, honestly recorded (Codex LOW-2).
    assert summary["evaluation_phase_sign_inversion_fired"] is False
    assert summary["fail_mode"] == "no_eligible_tick"


def test_experiments_scaffold() -> None:
    """The experiments scaffold exists and repro drives the --verify path."""
    exp = (
        _REPO_ROOT / "experiments" / "20260717-aha-phase4b-construction-validation-live"
    )
    assert (exp / "env.md").exists(), "missing experiments scaffold: env.md"
    repro = exp / "repro.ps1"
    run = exp / "run.ps1"
    assert repro.exists(), "missing experiments scaffold: repro.ps1"
    assert run.exists(), "missing experiments scaffold: run.ps1"
    repro_text = repro.read_text(encoding="utf-8")
    assert "--verify" in repro_text
    assert "aha_phase4b_two_phase_live_capture" in repro_text
