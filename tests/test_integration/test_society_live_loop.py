"""M13 society live-closure — Issue 001: society.py additive seam 2 本.

FROZEN ADR ``.steering/20260906-m13-society-live-closure/design-final.md``
§4 (Allowed Files) / §6 W-N5. Covers exactly the I-slice-001 acceptance
criteria (``loop/20260906-m13-society-live-closure/issues/001.md``):

* **AC1** ``test_society_loop_defaults_are_byte_identical`` — both new kwargs
  at their default (``None``) reproduce a caller that never knows about them
  (checksum / event_log_checksum / cognition_step_order /
  self_other_observation_input all agree).
* **AC2** (existing golden regression, not a new test here) — ``m2_society_golden``
  / ``m4_society_live_golden`` stay green, unmodified, in ``test_m2_society.py``
  / ``test_m4_society_live.py`` / ``test_m4_society_replay.py``.
* **AC3** ``test_runtime_ready_hook_awaited_before_first_drain`` — the hook is
  awaited before this run's first observation-factory call.
* **AC4** ``test_runtime_ready_hook_accepts_sync_and_async`` — both a plain
  synchronous callable and an ``async def`` callable are accepted.
* **AC5** ``test_runtime_ready_hook_does_not_mutate_runtime`` — a read-only
  hook (construction exposure, Codex M-5) never changes the run's output.
* **AC6** ``test_two_phase_knob_passthrough_keeps_geometry_checksum`` —
  ``two_phase_knob`` is threaded through to the driver's shared
  ``CognitionCycle`` and only modulates sampling, never geometry.

This module lands **wiring / construction, not aha / emergence / effect**
(``design-final.md`` §2, binding honest-framing regime): every assertion below
is boolean / byte-identity / count, never a floor / verdict / scorer /
divergence. Ollama-free — LLM is a scripted, record-mode double throughout
(mirrors ``test_m2_society.py``'s ``_ScriptedInner`` / ``_embed_client``
fixtures; duplicated here rather than cross-imported, following this test
suite's own established design-copy convention for small private test
doubles, e.g. ``test_m2_society_selfother.py``'s own local
``_embed_client``/``_ScriptedInner``).
"""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import inspect
import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import society, society_live_loop
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    RecordedLlmCall,
    RecordReplayChatClient,
)
from erre_sandbox.integration.embodied.society import SocietyRunResult, run_society_loop
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
)
from erre_sandbox.integration.embodied.society_live_loop import (
    COGNITION_ENVELOPE_KINDS,
    CONFORMANCE_COMPARED_FIELDS,
    CONFORMANCE_EXCLUDED_FIELDS,
    CONFORMANCE_SAMPLING_EXCLUSION_REASON,
    DIALOG_ENVELOPE_KINDS,
    EXCLUDED_ENVELOPE_KINDS,
    LIVE_ROOT_MODULE,
    RECORD_MODE_WALL_CLOCK,
    NondeterminismFinding,
    SocietyBroadcastLedger,
    SocietyInboundRouter,
    SocietyInjectedPerturbation,
    SocietyLedgerEntry,
    SocietyPlaneGReplay,
    build_society_live_world,
    committed_self_other_segments,
    ledger_observation_factories,
    live_root_nondeterminism_findings,
    live_root_source,
    recorded_llm_from_capture,
    replay_society_plane_g,
    run_society_live_loop,
    scan_nondeterminism_sources,
    self_other_segment_marker,
    society_embedding_record_from_jsonl,
    society_firing_annotation,
    society_injected_ledger_from_jsonl,
    society_ledger_entries,
    society_live_gateway_lifespan_serve,
    society_live_loop_perturbation_plan,
    society_mirror_wiring_summary,
    society_plane_g_bundle,
    society_plane_g_parity,
    society_plane_g_pins,
    society_recorded_llm_from_jsonl,
    society_request_conformance,
    society_wiring_reachability_summary,
    spy_inject_envelope_callers,
    supervise_society_live_loop,
)
from erre_sandbox.integration.embodied.traversal_live import (
    EmbeddingRecordReplayClient,
    RecordedEmbeddingCall,
)
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import (
    AgentState,
    PerceptionEvent,
    PersonaSpec,
    WorldPerturbationMsg,
    WorldTickMsg,
    Zone,
)
from erre_sandbox.world import WorldRuntime
from tests.test_integration._measurement_guard import assert_no_measurement_surface_v1

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from erre_sandbox.schemas import Observation

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)
_PLAN_JSON = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)


def _embed_client() -> EmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vec = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


class _ScriptedInner:
    """Duck-typed inner chat client returning a fixed content, call-counted."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls = 0

    async def chat(self, messages, *, sampling, model=None, options=None, think=None):  # noqa: ARG002
        self.calls += 1
        return ChatResponse(
            content=self._content,
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )


async def _run_society(
    agent_states: list[AgentState],
    personas: dict[str, PersonaSpec],
    *,
    run_id: str = "s0",
    seed: int = 0,
    n_cognition_ticks: int = 3,
    physics_ticks_per_cognition: int = 5,
    observation_factories: Mapping[str, Callable[[int], Sequence[Observation]]]
    | None = None,
    **extra: Any,
) -> SocietyRunResult:
    """One record-mode society drive on a fresh in-memory store + embedder.

    ``**extra`` forwards straight to :func:`run_society_loop` (e.g.
    ``two_phase_knob=...`` / ``on_runtime_ready=...``) — omitting a key here
    means the call to ``run_society_loop`` genuinely omits it too (exercises
    its own default), not just "passes None through a wrapper default".
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    clients = {
        s.agent_id: RecordReplayChatClient(inner=_ScriptedInner(_PLAN_JSON))
        for s in agent_states
    }
    kwargs: dict[str, Any] = {
        "run_id": run_id,
        "store": store,
        "embedding": embedding,
        "llms": clients,
        "agent_states": agent_states,
        "personas": personas,
        "retrieval_now": _FIXED,
        "base_ts": _FIXED,
        "seed": seed,
        "n_cognition_ticks": n_cognition_ticks,
        "physics_ticks_per_cognition": physics_ticks_per_cognition,
    }
    if observation_factories is not None:
        kwargs["observation_factories"] = observation_factories
    kwargs.update(extra)
    try:
        return await run_society_loop(**kwargs)
    finally:
        await embedding.close()
        await store.close()


# --------------------------------------------------------------------------- #
# AC1 — both additive kwargs at their default reproduce a pre-issue-001 caller
# --------------------------------------------------------------------------- #


async def test_society_loop_defaults_are_byte_identical(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """A caller that never passes the two new kwargs must be unaffected.

    NOT a structural-floor verdict; verdict は holding. This compares a call
    that genuinely omits ``two_phase_knob``/``on_runtime_ready`` (the pre-issue
    -001 call shape every existing caller uses) against one that passes both
    explicitly as ``None`` — the two must agree on every field that matters
    for reproducibility (§M4.4 / W-N5), proving the additive seam does not
    perturb the default path.
    """
    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
        make_agent_state(agent_id="a_three", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}

    pre_issue_001 = await _run_society(agent_states, personas, run_id="ac1")
    both_explicit_none = await _run_society(
        agent_states,
        personas,
        run_id="ac1",
        two_phase_knob=None,
        on_runtime_ready=None,
    )

    assert both_explicit_none.checksum == pre_issue_001.checksum
    assert both_explicit_none.event_log_checksum == pre_issue_001.event_log_checksum
    assert both_explicit_none.cognition_step_order == pre_issue_001.cognition_step_order
    assert (
        both_explicit_none.self_other_observation_input
        == pre_issue_001.self_other_observation_input
    )
    assert both_explicit_none.dialog_events == pre_issue_001.dialog_events
    assert both_explicit_none.pair_events == pre_issue_001.pair_events


# --------------------------------------------------------------------------- #
# AC3 — on_runtime_ready is awaited before the first observation drain
# --------------------------------------------------------------------------- #


async def test_runtime_ready_hook_awaited_before_first_drain(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The readiness barrier must finish (including its own await) before
    this run's first per-agent observation-factory call (§Codex H-1/L-3).

    The hook itself awaits a real suspension point (``asyncio.sleep(0)``) so
    a synchronous-callback implementation (which would return before the
    factory could ever observe it) is distinguished from the required
    awaitable-barrier behaviour.
    """
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")

    marker: list[str] = []

    async def on_ready(world: WorldRuntime) -> None:
        assert isinstance(world, WorldRuntime)
        await asyncio.sleep(0)
        marker.append("ready")

    drain_saw_marker: list[bool] = []

    def observation_factory(agent_tick: int) -> list[PerceptionEvent]:
        if agent_tick == 0:
            drain_saw_marker.append(bool(marker))
        return [
            PerceptionEvent(
                tick=agent_tick,
                agent_id=agent_state.agent_id,
                modality="sight",
                source_zone=Zone.STUDY,
                content=f"ac3 probe step {agent_tick}",
                intensity=0.4,
            )
        ]

    result = await _run_society(
        [agent_state],
        {agent_state.agent_id: persona},
        run_id="ac3",
        n_cognition_ticks=1,
        observation_factories={agent_state.agent_id: observation_factory},
        on_runtime_ready=on_ready,
    )

    assert marker == ["ready"], "on_runtime_ready must be called exactly once"
    assert drain_saw_marker == [True], (
        "the first observation-factory call must observe the hook already "
        "awaited (readiness barrier, not a fire-and-forget callback)"
    )
    assert result.rows, "sanity: the run must have actually produced trace rows"


# --------------------------------------------------------------------------- #
# AC4 — on_runtime_ready accepts both a sync callable and an async callable
# --------------------------------------------------------------------------- #


async def test_runtime_ready_hook_accepts_sync_and_async(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")

    sync_calls: list[WorldRuntime] = []

    def sync_hook(world: WorldRuntime) -> None:
        sync_calls.append(world)

    sync_result = await _run_society(
        [agent_state],
        {agent_state.agent_id: persona},
        run_id="ac4",
        n_cognition_ticks=2,
        on_runtime_ready=sync_hook,
    )
    assert len(sync_calls) == 1
    assert isinstance(sync_calls[0], WorldRuntime)

    async_calls: list[WorldRuntime] = []

    async def async_hook(world: WorldRuntime) -> None:
        await asyncio.sleep(0)
        async_calls.append(world)

    async_result = await _run_society(
        [agent_state],
        {agent_state.agent_id: persona},
        run_id="ac4",
        n_cognition_ticks=2,
        on_runtime_ready=async_hook,
    )
    assert len(async_calls) == 1
    assert isinstance(async_calls[0], WorldRuntime)

    # Both hook shapes are non-mutating reads of an otherwise identical
    # scenario, so the two runs must agree (sync vs async is a calling
    # convention, not a behavioural difference, §Codex H-1/L-3).
    assert sync_result.checksum == async_result.checksum
    assert sync_result.event_log_checksum == async_result.event_log_checksum


# --------------------------------------------------------------------------- #
# AC5 — construction-exposure contract: the hook must not mutate the runtime
# --------------------------------------------------------------------------- #


async def test_runtime_ready_hook_does_not_mutate_runtime(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """A read-only hook (Codex M-5's construction-exposure contract) must
    leave the run's construction output byte-identical to no hook at all.

    ``world.layout_snapshot()`` is the concrete read-only access pattern the
    ADR names (gateway-shaped ``recv_envelope``/``layout_snapshot`` consumer,
    ``design-final.md`` §4) — calling it here is a realistic non-mutating use
    of the hook, not a synthetic no-op.
    """
    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}

    snapshots: list[Any] = []

    def read_only_hook(world: WorldRuntime) -> None:
        snapshots.append(world.layout_snapshot())

    without_hook = await _run_society(
        agent_states, personas, run_id="ac5", n_cognition_ticks=2
    )
    with_hook = await _run_society(
        agent_states,
        personas,
        run_id="ac5",
        n_cognition_ticks=2,
        on_runtime_ready=read_only_hook,
    )

    assert snapshots, "the hook must have actually been invoked"
    assert with_hook.checksum == without_hook.checksum
    assert with_hook.event_log_checksum == without_hook.event_log_checksum
    assert with_hook.cognition_step_order == without_hook.cognition_step_order
    assert with_hook.dialog_events == without_hook.dialog_events
    assert with_hook.pair_events == without_hook.pair_events


# --------------------------------------------------------------------------- #
# AC6 — two_phase_knob passthrough: threaded to CognitionCycle, geometry-inert
# --------------------------------------------------------------------------- #


async def test_two_phase_knob_passthrough_keeps_geometry_checksum(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``two_phase_knob`` reaches the driver's shared ``CognitionCycle`` and
    only ever modulates the sampling term the cycle composes for its next
    call — it must never change the geometry checksum this driver computes
    (destination/zone resolution comes from the recorded/replayed
    ``LLMPlan``, not from sampling).

    The structural check below is a construction discovery-guard (mirrors
    ``test_m2_society.py``'s ``asyncio.gather`` absence check): it proves the
    kwarg is actually threaded through, not silently dropped on the floor.
    """
    source = inspect.getsource(society.run_society_loop)
    assert "two_phase_knob=two_phase_knob" in source, (
        "two_phase_knob must be passed straight through to CognitionCycle"
    )

    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}

    knob_off = await _run_society(
        agent_states, personas, run_id="ac6", n_cognition_ticks=3
    )
    knob_on = await _run_society(
        agent_states,
        personas,
        run_id="ac6",
        n_cognition_ticks=3,
        two_phase_knob=TwoPhaseKnob(),
    )

    assert knob_on.checksum == knob_off.checksum, (
        "TwoPhaseKnob is a sampling-only marker (no gains carried) — geometry "
        "must be unaffected by its presence"
    )
    assert len(knob_on.rows) == len(knob_off.rows)


# =============================================================================
# Issue 002 — SocietyInboundRouter (router部のみ) + N-agent perturbation plan
# =============================================================================
#
# ``loop/20260906-m13-society-live-closure/issues/002.md``: Ollama-free,
# router-only tests. ``run_society_loop`` is NOT driven here — ``InboundSink``
# is pushed to directly and the router is exercised standalone (Test Plan,
# issue 002).


def _perturbation(
    *,
    target_agent_id: str,
    correlation_id: str,
    zone: Zone = Zone.STUDY,
    content: str = "stimulus",
) -> WorldPerturbationMsg:
    """A minimal, field-complete ``WorldPerturbationMsg`` for router tests."""
    return WorldPerturbationMsg(
        tick=0,
        target_agent_id=target_agent_id,
        modality="sight",
        source_zone=zone,
        content=content,
        intensity=0.4,
        correlation_id=correlation_id,
    )


def test_inbound_router_drains_once_per_window() -> None:
    """AC1 (Codex M-1): ``begin_window(tick)`` drains at most once per tick.

    A message pushed onto the sink AFTER the first ``begin_window(0)`` call
    must still be sitting in the sink after two further ``begin_window(0)``
    calls for the SAME tick — proving those are true no-ops, not re-drains —
    and only actually drains once the tick genuinely advances.
    """
    sink = InboundSink()
    router = SocietyInboundRouter(sink, agent_ids=["a_one"])

    sink.push(_perturbation(target_agent_id="a_one", correlation_id="c0"))
    router.begin_window(0)
    sink.push(_perturbation(target_agent_id="a_one", correlation_id="c1"))
    router.begin_window(0)
    router.begin_window(0)

    ledger = router.ledger
    assert [m.correlation_id for m in ledger.drained] == ["c0"]

    router.begin_window(1)
    ledger_after = router.ledger
    assert [m.correlation_id for m in ledger_after.drained] == ["c0", "c1"]


def test_inbound_router_buckets_by_target_agent() -> None:
    """AC2: a perturbation lands only in its ``target_agent_id``'s bucket.

    ``a_two``'s factory is deliberately called BEFORE ``a_one``'s (the
    factory that happens to trigger the drain) to prove bucketing is
    correct regardless of per-agent factory call order (Codex M-1 motive).
    """
    sink = InboundSink()
    router = SocietyInboundRouter(sink, agent_ids=["a_one", "a_two"])
    sink.push(_perturbation(target_agent_id="a_one", correlation_id="to-one"))

    factories = router.observation_factories(["a_one", "a_two"])
    obs_two = factories["a_two"](0)
    obs_one = factories["a_one"](0)

    assert obs_two == ()
    assert len(obs_one) == 1
    assert obs_one[0].agent_id == "a_one"


def test_inbound_router_rejects_unknown_target() -> None:
    """AC3: an unregistered ``target_agent_id`` is never injected."""
    sink = InboundSink()
    router = SocietyInboundRouter(sink, agent_ids=["a_one"])
    sink.push(_perturbation(target_agent_id="a_unregistered", correlation_id="ghost"))

    factory = router.observation_factories(["a_one"])["a_one"]
    obs = factory(0)

    assert obs == ()
    ledger = router.ledger
    assert [m.correlation_id for m in ledger.rejected] == ["ghost"]
    assert ledger.injected == ()
    assert "ghost" not in ledger.injected_correlation_ids


def test_inbound_router_ledger_five_way_split() -> None:
    """AC4 (Codex M-2): pushed/dropped/drained/injected/rejected 5分割.

    Overflow negative fixture: ``InboundSink(maxsize=2)`` forces drop-oldest
    to actually evict two messages (``c0``/``c1``) before they are ever
    drained — proving ``dropped`` becomes non-zero and the dropped
    correlation-ids never surface in ``injected``.
    """
    sink = InboundSink(maxsize=2)
    router = SocietyInboundRouter(sink, agent_ids=["a_one", "a_two"])

    # 4 pushes into a maxsize=2 sink: c0/c1 are evicted (drop-oldest) before
    # any drain ever runs; only c2 (registered target) / c3 (unknown target)
    # survive to be drained.
    sink.push(_perturbation(target_agent_id="a_one", correlation_id="c0"))
    sink.push(_perturbation(target_agent_id="a_one", correlation_id="c1"))
    sink.push(_perturbation(target_agent_id="a_two", correlation_id="c2"))
    sink.push(_perturbation(target_agent_id="a_unknown", correlation_id="c3"))

    factories = router.observation_factories(["a_one", "a_two"])
    factories["a_one"](0)
    factories["a_two"](0)

    ledger = router.ledger
    assert ledger.dropped == 2
    assert {m.correlation_id for m in ledger.drained} == {"c2", "c3"}
    assert [inj.correlation_id for inj in ledger.injected] == ["c2"]
    assert [m.correlation_id for m in ledger.rejected] == ["c3"]
    # Exhaustive partition: every drained message is either injected or rejected.
    assert len(ledger.injected) + len(ledger.rejected) == len(ledger.drained)
    # A dropped (overflow-evicted) correlation-id must never surface as injected.
    assert "c0" not in ledger.injected_correlation_ids
    assert "c1" not in ledger.injected_correlation_ids
    assert ledger.pushed == ledger.dropped + len(ledger.drained)


def test_inbound_observation_wall_clock_pinned() -> None:
    """AC5: inbound-sourced ``PerceptionEvent.wall_clock`` is pinned.

    ``world_perturbation_to_perception`` (unmodified) defaults
    ``wall_clock`` to real ``_utc_now()`` — the router must override it to
    :data:`RECORD_MODE_WALL_CLOCK` so two independent constructions agree
    byte-for-byte instead of disagreeing at microsecond resolution.
    """
    sink = InboundSink()
    router = SocietyInboundRouter(sink, agent_ids=["a_one"])
    sink.push(_perturbation(target_agent_id="a_one", correlation_id="c0"))
    obs = router.observation_factories(["a_one"])["a_one"](0)

    assert len(obs) == 1
    assert obs[0].wall_clock == RECORD_MODE_WALL_CLOCK

    sink2 = InboundSink()
    router2 = SocietyInboundRouter(sink2, agent_ids=["a_one"])
    sink2.push(_perturbation(target_agent_id="a_one", correlation_id="c0"))
    obs2 = router2.observation_factories(["a_one"])["a_one"](0)

    assert obs2[0].model_dump_json() == obs[0].model_dump_json()


def test_perturbation_plan_is_pure() -> None:
    """AC6: the N-agent perturbation plan builder is a pure function.

    Building it twice with the same (default, sealed) arguments must
    reproduce a byte-identical tuple, ``correlation_id`` and ``sent_at``
    included.
    """
    plan1 = society_live_loop_perturbation_plan()
    plan2 = society_live_loop_perturbation_plan()

    assert plan1 == plan2
    assert [m.model_dump_json() for m in plan1] == [m.model_dump_json() for m in plan2]
    assert len(plan1) == len(SOCIETY_LIVE_AGENT_IDS) * SOCIETY_LIVE_N_COGNITION_TICKS
    assert all(m.sent_at == RECORD_MODE_WALL_CLOCK for m in plan1)

    # window-major / agent-minor ordering: the first len(agent_ids) messages
    # are window 0, one per agent, in SOCIETY_LIVE_AGENT_IDS order.
    first_window_targets = [
        m.target_agent_id for m in plan1[: len(SOCIETY_LIVE_AGENT_IDS)]
    ]
    assert first_window_targets == list(SOCIETY_LIVE_AGENT_IDS)


def test_inbound_router_preserves_fifo_order() -> None:
    """AC7: push order == drain order == bucket order for a single agent."""
    sink = InboundSink()
    router = SocietyInboundRouter(sink, agent_ids=["a_one"])
    sink.push(
        _perturbation(target_agent_id="a_one", correlation_id="c0", content="first")
    )
    sink.push(
        _perturbation(target_agent_id="a_one", correlation_id="c1", content="second")
    )
    sink.push(
        _perturbation(target_agent_id="a_one", correlation_id="c2", content="third")
    )

    obs = router.observation_factories(["a_one"])["a_one"](0)

    assert [o.content for o in obs] == ["first", "second", "third"]
    ledger = router.ledger
    assert [inj.correlation_id for inj in ledger.injected] == ["c0", "c1", "c2"]
    assert [m.correlation_id for m in ledger.drained] == ["c0", "c1", "c2"]


# =============================================================================
# Issue 003 — closure root proper (build_society_live_world /
# run_society_live_loop / supervise_society_live_loop)
# =============================================================================
#
# ``loop/20260906-m13-society-live-closure/issues/003.md``: Ollama-free.
# ``gateway_serve`` stubs below are deliberately lightweight coroutines (never
# a real uvicorn server) -- this is a construction-wiring witness, not a real
# network probe.


def _fresh_store_and_embedding() -> tuple[MemoryStore, EmbeddingClient]:
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    return store, _embed_client()


# --------------------------------------------------------------------------- #
# AC1 — gateway app built/started before the drive's first cognition window
# --------------------------------------------------------------------------- #


async def test_gateway_started_before_first_window(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The readiness barrier (Codex H-1) must finish before the first
    cognition-window LLM call.

    A window's first LLM ``chat()`` call happens strictly AFTER that same
    window's observation drain (``run_society_loop``'s own per-window body:
    inject observations for every agent, THEN step cognition for every
    agent) -- so "gateway started before the first LLM call" is a sufficient,
    honest proxy for "gateway started before the first window", never a
    tautological check (the marker is appended by the LLM double itself, a
    call the supervisor's own code never touches).
    """
    markers: list[str] = []

    class _MarkingInner:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(
            self,
            messages: Any,  # noqa: ARG002
            *,
            sampling: Any,  # noqa: ARG002
            model: str | None = None,  # noqa: ARG002
            options: dict[str, Any] | None = None,  # noqa: ARG002
            think: bool | None = None,  # noqa: ARG002
        ) -> ChatResponse:
            self.calls += 1
            markers.append("first_cognition_call")
            return ChatResponse(
                content=_PLAN_JSON,
                model="qwen3:8b",
                eval_count=1,
                total_duration_ms=0.0,
            )

    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={agent_state.agent_id: _MarkingInner()},
        store=store,
        embedding=embedding,
        inbound_sink=sink,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )

    async def gateway_serve(app: Any) -> None:  # noqa: ARG001 — stub, app unused here
        markers.append("gateway_started")
        await asyncio.Event().wait()

    try:
        result = await supervise_society_live_loop(
            world=world,
            gateway_serve=gateway_serve,
            run_id="ac1",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=2,
        )
    finally:
        await embedding.close()
        await store.close()

    assert markers == ["gateway_started", "first_cognition_call"]
    assert result.result.rows, "sanity: the drive must have actually run"


# --------------------------------------------------------------------------- #
# AC2 — serve task and driven task share one event loop
# --------------------------------------------------------------------------- #


async def test_serve_and_drive_share_one_event_loop(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={agent_state.agent_id: _ScriptedInner(_PLAN_JSON)},
        store=store,
        embedding=embedding,
        inbound_sink=sink,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )

    async def gateway_serve(app: Any) -> None:  # noqa: ARG001
        await asyncio.Event().wait()

    scheduled: list[tuple[asyncio.Task[None], asyncio.Task[None]]] = []

    def on_tasks_scheduled(
        serve_task: asyncio.Task[None], driven_task: asyncio.Task[None]
    ) -> None:
        scheduled.append((serve_task, driven_task))

    try:
        await supervise_society_live_loop(
            world=world,
            gateway_serve=gateway_serve,
            run_id="ac2",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=2,
            on_tasks_scheduled=on_tasks_scheduled,
        )
    finally:
        await embedding.close()
        await store.close()

    assert len(scheduled) == 1
    serve_task, driven_task = scheduled[0]
    assert serve_task is not driven_task
    assert serve_task.get_loop() is driven_task.get_loop()


# --------------------------------------------------------------------------- #
# AC3 — completion cancels serve cleanly; a real exception propagates as
# ExceptionGroup (positive + negative)
# --------------------------------------------------------------------------- #


async def test_supervisor_cancels_serve_and_propagates_real_errors(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")

    # --- positive: normal completion cancels the still-blocked serve task
    # cleanly -- no exception escapes the TaskGroup. ------------------------
    cancelled_cleanly: list[bool] = []

    async def gateway_serve_ok(app: Any) -> None:  # noqa: ARG001
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled_cleanly.append(True)
            raise

    store_ok, embedding_ok = _fresh_store_and_embedding()
    sink_ok = InboundSink()
    world_ok = build_society_live_world(
        inner_chats={agent_state.agent_id: _ScriptedInner(_PLAN_JSON)},
        store=store_ok,
        embedding=embedding_ok,
        inbound_sink=sink_ok,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )
    try:
        result = await supervise_society_live_loop(
            world=world_ok,
            gateway_serve=gateway_serve_ok,
            run_id="ac3-ok",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=2,
        )
    finally:
        await embedding_ok.close()
        await store_ok.close()

    assert result.result.rows
    assert cancelled_cleanly == [True]

    # --- negative: a genuine exception from gateway_serve must propagate as
    # an ExceptionGroup, never be silently absorbed alongside the
    # shutdown-cancel suppress. ---------------------------------------------
    class _GatewayBoomError(Exception):
        pass

    async def gateway_serve_boom(app: Any) -> None:  # noqa: ARG001
        msg = "gateway exploded"
        raise _GatewayBoomError(msg)

    store_boom, embedding_boom = _fresh_store_and_embedding()
    sink_boom = InboundSink()
    world_boom = build_society_live_world(
        inner_chats={agent_state.agent_id: _ScriptedInner(_PLAN_JSON)},
        store=store_boom,
        embedding=embedding_boom,
        inbound_sink=sink_boom,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )
    try:
        with pytest.raises(ExceptionGroup) as excinfo:
            await supervise_society_live_loop(
                world=world_boom,
                gateway_serve=gateway_serve_boom,
                run_id="ac3-boom",
                retrieval_now=_FIXED,
                base_ts=_FIXED,
                n_cognition_ticks=1,
                physics_ticks_per_cognition=2,
            )
    finally:
        await embedding_boom.close()
        await store_boom.close()

    assert any(isinstance(exc, _GatewayBoomError) for exc in excinfo.value.exceptions)


# --------------------------------------------------------------------------- #
# AC4 — knob=None fidelity: the closure root adds no behaviour of its own
# --------------------------------------------------------------------------- #


async def test_live_root_knob_none_fidelity_byte_identical(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``run_society_live_loop`` with ``knob=None`` must reproduce exactly
    what a direct ``run_society_loop`` call (same agent_states/personas,
    equivalently-wrapped llms, an equivalent empty router's
    ``observation_factories``, ``self_other_enabled=True``, ``two_phase_knob=
    None``) would produce -- proving the closure root is a thin pass-through,
    never a second source of geometry/behaviour drift (organ drift pin, the
    same discipline Issue 001's AC1 established one layer down)."""
    agent_states = [
        make_agent_state(agent_id="a_one", persona_id="kant"),
        make_agent_state(agent_id="a_two", persona_id="kant"),
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in agent_states}
    agent_ids = [s.agent_id for s in agent_states]

    # (a) via the composition root.
    store_a, embedding_a = _fresh_store_and_embedding()
    sink_a = InboundSink()
    world_a = build_society_live_world(
        inner_chats={aid: _ScriptedInner(_PLAN_JSON) for aid in agent_ids},
        store=store_a,
        embedding=embedding_a,
        inbound_sink=sink_a,
        agent_states=agent_states,
        personas=personas,
    )
    try:
        via_root = await run_society_live_loop(
            world_a,
            run_id="ac4",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=3,
            physics_ticks_per_cognition=4,
        )
    finally:
        await embedding_a.close()
        await store_a.close()

    # (b) a direct run_society_loop call, same shape, no closure root at all.
    store_b, embedding_b = _fresh_store_and_embedding()
    sink_b = InboundSink()
    router_b = SocietyInboundRouter(sink_b, agent_ids=agent_ids)
    llms_b = {
        aid: RecordReplayChatClient(
            inner=ThinkOffChatClient(_ScriptedInner(_PLAN_JSON))
        )
        for aid in agent_ids
    }
    try:
        direct = await run_society_loop(
            run_id="ac4",
            store=store_b,
            embedding=embedding_b,
            llms=llms_b,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=3,
            physics_ticks_per_cognition=4,
            observation_factories=router_b.observation_factories(agent_ids),
            self_other_enabled=True,
            two_phase_knob=None,
            on_runtime_ready=None,
        )
    finally:
        await embedding_b.close()
        await store_b.close()

    assert via_root.result.checksum == direct.checksum
    assert via_root.result.event_log_checksum == direct.event_log_checksum
    assert via_root.result.cognition_step_order == direct.cognition_step_order
    assert via_root.result.dialog_events == direct.dialog_events
    assert via_root.result.pair_events == direct.pair_events
    assert (
        via_root.result.self_other_observation_input
        == direct.self_other_observation_input
    )


# --------------------------------------------------------------------------- #
# AC5 — N=3 / 12-window drive completes; each agent gets 12 decisions;
# cognition_step_order is the sorted roster repeated
# --------------------------------------------------------------------------- #


async def test_live_root_drives_three_agents_twelve_windows() -> None:
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={aid: _ScriptedInner(_PLAN_JSON) for aid in SOCIETY_LIVE_AGENT_IDS},
        store=store,
        embedding=embedding,
        inbound_sink=sink,
    )
    try:
        result = await run_society_live_loop(
            world,
            run_id="ac5",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=SOCIETY_LIVE_N_COGNITION_TICKS,
            physics_ticks_per_cognition=2,
        )
    finally:
        await embedding.close()
        await store.close()

    assert set(result.result.decisions) == set(SOCIETY_LIVE_AGENT_IDS)
    for agent_id in SOCIETY_LIVE_AGENT_IDS:
        assert len(result.result.decisions[agent_id]) == SOCIETY_LIVE_N_COGNITION_TICKS

    step_order = result.result.cognition_step_order
    n_agents = len(SOCIETY_LIVE_AGENT_IDS)
    assert len(step_order) == n_agents * SOCIETY_LIVE_N_COGNITION_TICKS
    expected_window = sorted(SOCIETY_LIVE_AGENT_IDS)
    for window_index in range(SOCIETY_LIVE_N_COGNITION_TICKS):
        start = window_index * n_agents
        end = start + n_agents
        assert list(step_order[start:end]) == expected_window


# --------------------------------------------------------------------------- #
# AC6 — gateway and driver observe the SAME runtime instance (no second
# channel)
# --------------------------------------------------------------------------- #


async def test_gateway_and_driver_share_same_runtime_instance(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={agent_state.agent_id: _ScriptedInner(_PLAN_JSON)},
        store=store,
        embedding=embedding,
        inbound_sink=sink,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )

    apps: list[Any] = []

    async def gateway_serve(app: Any) -> None:
        apps.append(app)
        await asyncio.Event().wait()

    try:
        result = await supervise_society_live_loop(
            world=world,
            gateway_serve=gateway_serve,
            run_id="ac6",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=2,
        )
    finally:
        await embedding.close()
        await store.close()

    assert len(apps) == 1
    assert apps[0].state.runtime is result.runtime
    assert isinstance(result.runtime, WorldRuntime)


# --------------------------------------------------------------------------- #
# Codex TASK-POST M-5 — SocietyBroadcastLedger.detach() actually releases the
# reserved Registry session slot (previously dead code: 0 callers, 0 tests).
# --------------------------------------------------------------------------- #


async def test_supervisor_detaches_broadcast_ledger_registry_slot(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``SocietyBroadcastLedger.attach`` reserves a session slot on the app's
    ``Registry`` exactly like a real peer would (SH-2 cap enforcement); this
    pins that ``supervise_society_live_loop`` actually releases it again once
    the record is complete, rather than holding the slot for the app's whole
    lifetime with no caller ever able to reach ``detach`` (the shape TASK-POST
    M-5 flagged as dead code).

    Uses the same minimal stub-``gateway_serve`` pattern as
    ``test_gateway_and_driver_share_same_runtime_instance`` (no real lifespan
    needed to observe registry bookkeeping): ``SocietyBroadcastLedger.attach``/
    ``detach`` only touch ``Registry.reserve_slot``/``release_slot``, neither
    of which depends on the ``_broadcaster`` task actually running.
    """
    agent_state = make_agent_state(agent_id="a_one", persona_id="kant")
    persona = make_persona_spec(persona_id="kant")
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={agent_state.agent_id: _ScriptedInner(_PLAN_JSON)},
        store=store,
        embedding=embedding,
        inbound_sink=sink,
        agent_states=[agent_state],
        personas={agent_state.agent_id: persona},
    )
    apps: list[Any] = []

    async def gateway_serve(app: Any) -> None:
        apps.append(app)
        await asyncio.Event().wait()

    mid_drive_session_counts: list[int] = []

    def on_tasks_scheduled(
        serve_task: asyncio.Task[None], driven_task: asyncio.Task[None]
    ) -> None:
        del serve_task, driven_task
        # Fires (readiness-barrier docstring, above) strictly after ``attach``
        # and strictly before the drive's first cognition window -- a
        # mid-flight snapshot proving the slot really was reserved, so the
        # post-call ``== 0`` below cannot pass for the wrong reason (a dead
        # ``attach`` that never reserved anything in the first place).
        mid_drive_session_counts.append(len(apps[0].state.registry))

    ledger = SocietyBroadcastLedger()
    try:
        await supervise_society_live_loop(
            world=world,
            gateway_serve=gateway_serve,
            run_id="m5-detach",
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=1,
            physics_ticks_per_cognition=2,
            broadcast_ledger=ledger,
            on_tasks_scheduled=on_tasks_scheduled,
        )
    finally:
        await embedding.close()
        await store.close()

    assert len(apps) == 1
    assert mid_drive_session_counts == [1], "attach() did not reserve the slot"
    registry = apps[0].state.registry
    assert len(registry) == 0, "detach() did not release the reserved slot"


# =============================================================================
# Issue 004 — W-N1 reachability witness + W-N3 outbound-ownership witness
# =============================================================================
#
# ``loop/20260906-m13-society-live-closure/issues/004.md``: Ollama-free.
# The consume-side ledger is taken through gateway.py's PUBLIC session seam
# (``Registry.reserve_slot``, reached via ``SocietyBroadcastLedger.attach``) --
# gateway.py is unmodified, and no test below observes
# ``WorldRuntime.drain_envelopes()`` to BUILD a witness (Codex H-2: that is
# race-dependent because the gateway's own ``_broadcaster`` consumes the very
# same queue). Every assertion is boolean / count / multiset -- never a floor,
# verdict, divergence or scorer (``design-final.md`` §2 honest framing).


async def _drive_with_broadcast_ledger(
    *,
    agent_states: list[AgentState],
    personas: dict[str, PersonaSpec],
    run_id: str,
    n_cognition_ticks: int = 2,
    perturbations: Sequence[WorldPerturbationMsg] = (),
    sink: InboundSink | None = None,
    max_drain_per_tick: int | None = None,
) -> tuple[Any, SocietyBroadcastLedger, list[str]]:
    """Drive a real supervised society closure with the consume-side ledger on.

    ``gateway_serve`` is :func:`society_live_gateway_lifespan_serve` -- the real
    ``gateway.py`` lifespan (and therefore its real ``_broadcaster`` task) runs
    in this same event loop, so the ledger records genuine ``Registry.fan_out``
    deliveries rather than a simulation of them.

    ``max_drain_per_tick`` defaults to ``len(agent_states)`` so a window-major
    perturbation plan lands exactly one message per agent per window (rather
    than the whole plan collapsing onto window 0).
    """
    store, embedding = _fresh_store_and_embedding()
    inbound = sink if sink is not None else InboundSink()
    world = build_society_live_world(
        inner_chats={s.agent_id: _ScriptedInner(_PLAN_JSON) for s in agent_states},
        store=store,
        embedding=embedding,
        inbound_sink=inbound,
        agent_states=agent_states,
        personas=personas,
        max_drain_per_tick=(
            len(agent_states) if max_drain_per_tick is None else max_drain_per_tick
        ),
    )
    for msg in perturbations:
        inbound.push(msg)
    ledger = SocietyBroadcastLedger()
    try:
        with spy_inject_envelope_callers() as callers:
            result = await supervise_society_live_loop(
                world=world,
                gateway_serve=society_live_gateway_lifespan_serve(),
                run_id=run_id,
                retrieval_now=_FIXED,
                base_ts=_FIXED,
                n_cognition_ticks=n_cognition_ticks,
                physics_ticks_per_cognition=2,
                broadcast_ledger=ledger,
            )
    finally:
        await embedding.close()
        await store.close()
    return result, ledger, callers


def _roster(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    agent_ids: Sequence[str],
) -> tuple[list[AgentState], dict[str, PersonaSpec]]:
    states = [
        make_agent_state(agent_id=agent_id, persona_id="kant") for agent_id in agent_ids
    ]
    personas = {s.agent_id: make_persona_spec(persona_id="kant") for s in states}
    return states, personas


# --------------------------------------------------------------------------- #
# AC1 — every injected correlation-id reaches all per-correlation seams
# --------------------------------------------------------------------------- #


async def test_reachability_per_correlation_seams_all_true(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Wiring reached each seam, for every injected correlation-id.

    "Reached", never "caused": the seams below are boolean records of where
    the wiring carried a message, not evidence that any message produced a
    behaviour (``design-final.md`` §2).
    """
    agent_ids = ["a_one", "a_two"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)
    plan = society_live_loop_perturbation_plan(agent_ids=agent_ids, n_ticks=2)

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac1",
        n_cognition_ticks=2,
        perturbations=plan,
    )
    summary = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )

    assert summary["injected_count"] == len(plan)
    assert set(summary["per_correlation_id"]) == {m.correlation_id for m in plan}
    for correlation_id, seams in summary["per_correlation_id"].items():
        assert seams["perturbation"] is True, correlation_id
        assert seams["perception"] is True, correlation_id
        assert seams["target_agent_routing"] is True, correlation_id
        assert seams["capture"] is True, correlation_id
        assert seams["all_seams_reached"] is True, correlation_id
    assert summary["all_correlation_ids_reach_all_seams"] is True

    # Non-vacuity of the N-agent routing seam: it is NOT the tautology
    # ``msg.target_agent_id == observation.agent_id`` on its own (the pure
    # inbound mapping guarantees that half). Flipping only the recorded
    # routing bucket must break the OTHER half.
    injected = result.ledger.injected[0]
    mis_routed = SocietyInjectedPerturbation(
        agent_tick=injected.agent_tick,
        correlation_id=injected.correlation_id,
        msg=injected.msg,
        observation=injected.observation,
        routed_agent_id="a_two" if injected.routed_agent_id == "a_one" else "a_one",
    )
    assert mis_routed.msg.target_agent_id == mis_routed.observation.agent_id
    assert mis_routed.msg.target_agent_id != mis_routed.routed_agent_id

    # TASK-POST HIGH-1: the tautology check above, on its own, only proves a
    # fact about the FIXTURE's own fields -- it never fed the mis-bucketed
    # row back through the witness function real callers read, so deleting
    # ``target_agent_routing``'s second comparison
    # (``... and injected.msg.target_agent_id == injected.routed_agent_id``)
    # in ``society_wiring_reachability_summary`` left this whole test suite
    # green (mutation-tested below and in this session's report). Splice the
    # mis-bucketed row into a REAL drive's ledger with ``dataclasses.replace``
    # (both dataclasses are frozen; this never mutates ``result`` itself) and
    # run it through the same witness a caller would.
    mis_routed_ledger = dataclasses.replace(
        result.ledger, injected=(mis_routed, *result.ledger.injected[1:])
    )
    mis_routed_result = dataclasses.replace(result, ledger=mis_routed_ledger)
    mis_routed_summary = society_wiring_reachability_summary(
        mis_routed_result, broadcast_envelope_kinds=ledger.envelope_kinds
    )
    mis_routed_seams = mis_routed_summary["per_correlation_id"][
        mis_routed.correlation_id
    ]
    assert mis_routed_seams["target_agent_routing"] is False
    assert mis_routed_seams["all_seams_reached"] is False
    assert mis_routed_summary["all_correlation_ids_reach_all_seams"] is False
    # This is a targeted single-field corruption, not a general one: every
    # other per-correlation seam on this same row is untouched.
    assert mis_routed_seams["perturbation"] is True
    assert mis_routed_seams["perception"] is True

    # Codex M-3 (piggybacked on the same real-ledger splice above): a
    # DIFFERENT single-field corruption -- ``agent_tick`` moved to a window
    # this 2-tick drive never reaches -- demonstrates (rather than merely
    # documents) what ``perception`` / ``capture`` / the tick-level seams
    # actually detect. Routing itself is untouched, so
    # ``target_agent_routing`` stays true here; it is exactly the
    # complementary failure mode to the routing-bucket flip above.
    mis_tick = dataclasses.replace(injected, agent_tick=999)
    mis_tick_ledger = dataclasses.replace(
        result.ledger, injected=(mis_tick, *result.ledger.injected[1:])
    )
    mis_tick_result = dataclasses.replace(result, ledger=mis_tick_ledger)
    mis_tick_summary = society_wiring_reachability_summary(
        mis_tick_result, broadcast_envelope_kinds=ledger.envelope_kinds
    )
    mis_tick_seams = mis_tick_summary["per_correlation_id"][mis_tick.correlation_id]
    assert mis_tick_seams["perception"] is False
    assert mis_tick_seams["capture"] is False
    assert mis_tick_seams["same_tick_cognition_stepped"] is False
    assert mis_tick_seams["same_tick_envelope_observed"] is False
    assert mis_tick_seams["target_agent_routing"] is True
    assert mis_tick_seams["all_seams_reached"] is False


# --------------------------------------------------------------------------- #
# AC2 — the reachability population is the injected partition only
# --------------------------------------------------------------------------- #


async def test_reachability_population_is_injected_only(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``rejected`` / ``dropped`` correlation-ids stay out of the population.

    Codex M-2: an overflow-evicted message never became an observation, and a
    message aimed at an unregistered agent was never bucketed -- scoring
    either as "did not reach a seam" would manufacture a failure for a message
    that never entered the pipeline. Both are plain counts instead.
    """
    agent_ids = ["a_one"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)

    # maxsize=2 forces drop-oldest: c0/c1 are evicted before any drain runs.
    sink = InboundSink(maxsize=2)
    perturbations = [
        _perturbation(target_agent_id="a_one", correlation_id="c0"),
        _perturbation(target_agent_id="a_one", correlation_id="c1"),
        _perturbation(target_agent_id="a_one", correlation_id="c2"),
        _perturbation(target_agent_id="a_ghost", correlation_id="c3"),
    ]

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac2",
        n_cognition_ticks=2,
        perturbations=perturbations,
        sink=sink,
        max_drain_per_tick=8,
    )
    summary = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )

    assert set(summary["per_correlation_id"]) == {"c2"}
    for excluded in ("c0", "c1", "c3"):
        assert excluded not in summary["per_correlation_id"]
    assert summary["injected_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["dropped_count"] == 2
    assert isinstance(summary["rejected_count"], int)
    assert isinstance(summary["dropped_count"], int)
    assert summary["per_correlation_id"]["c2"]["all_seams_reached"] is True


# --------------------------------------------------------------------------- #
# AC3 — cognition-kind multiset agrees with the CONSUME-side ledger
# --------------------------------------------------------------------------- #


async def test_cognition_kind_multiset_matches_consume_side_ledger(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """W-N3: enqueue-side provenance == what the gateway actually fanned out.

    Also the direct witness for Codex H-2: the summary is built from the
    consume side, so it survives the broadcaster having already drained the
    runtime queue. The rejected post-hoc shape (``drain_envelopes()`` after
    the run, PR #89's ``_broadcast_envelope_kinds``) is exercised right here
    and shown NOT to reproduce the enqueue multiset.
    """
    agent_ids = ["a_one", "a_two"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)
    plan = society_live_loop_perturbation_plan(agent_ids=agent_ids, n_ticks=2)

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac3",
        n_cognition_ticks=2,
        perturbations=plan,
    )
    summary = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )

    enqueued = summary["cognition_envelope_kinds_enqueued"]
    consumed = summary["cognition_envelope_kinds_consumed"]
    assert enqueued, "sanity: the drive must have emitted cognition envelopes"
    assert set(enqueued) <= COGNITION_ENVELOPE_KINDS
    assert enqueued == consumed
    assert summary["no_double_send"] is True

    # The gateway really consumed the queue: a post-hoc drain (the Codex H-2
    # anti-pattern) now sees none of those cognition envelopes, so a witness
    # built that way would have disagreed with the enqueue side.
    post_hoc = Counter(
        env.kind
        for env in result.runtime.drain_envelopes()
        if env.kind in COGNITION_ENVELOPE_KINDS
    )
    assert post_hoc != Counter(enqueued)
    assert sum(post_hoc.values()) < sum(enqueued.values())

    # Non-vacuity of the gate: one extra cognition envelope on the consume
    # side (what a re-injection bug would look like) must break it.
    bugged = society_wiring_reachability_summary(
        result,
        broadcast_envelope_kinds=(*ledger.envelope_kinds, "move"),
    )
    assert bugged["no_double_send"] is False


# --------------------------------------------------------------------------- #
# AC4 — dialog envelopes are a plain count annotation, never gated
# --------------------------------------------------------------------------- #


async def test_dialog_envelopes_are_annotation_only(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Codex H-3: ``dialog_*`` is counted, never folded into ``no_double_send``.

    Reason (asserted to be documented in the artifact, not only here): the
    dialog scheduler's envelope sink is fixed to ``world.inject_envelope``
    inside ``run_society_loop``, so its enqueue side cannot be reconstructed
    without a third additive kwarg -- deferred to a separate
    ``dialog_envelope_sink`` ADR.
    """
    agent_ids = ["a_one", "a_two"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac4",
        n_cognition_ticks=2,
    )

    baseline = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )
    with_dialog = society_wiring_reachability_summary(
        result,
        broadcast_envelope_kinds=(
            *ledger.envelope_kinds,
            "dialog_initiate",
            "dialog_turn",
            "dialog_turn",
            "dialog_close",
        ),
    )

    # Non-vacuous: this scenario's dialog scheduler really did fire, so the
    # gateway genuinely fanned out dialog_* envelopes whose enqueue side this
    # witness cannot reconstruct -- exactly the Codex H-3 situation. They are
    # counted, and the gate is nonetheless green.
    assert sum(baseline["dialog_envelope_counts"].values()) > 0
    assert set(baseline["dialog_envelope_counts"]) == set(DIALOG_ENVELOPE_KINDS)
    assert with_dialog["dialog_envelope_counts"] == {
        "dialog_initiate": baseline["dialog_envelope_counts"]["dialog_initiate"] + 1,
        "dialog_turn": baseline["dialog_envelope_counts"]["dialog_turn"] + 2,
        "dialog_close": baseline["dialog_envelope_counts"]["dialog_close"] + 1,
    }
    # Annotation only: four extra dialog envelopes leave the gate untouched.
    assert with_dialog["no_double_send"] is True
    assert baseline["no_double_send"] is True
    assert (
        with_dialog["cognition_envelope_kinds_consumed"]
        == baseline["cognition_envelope_kinds_consumed"]
    )
    assert set(DIALOG_ENVELOPE_KINDS) <= EXCLUDED_ENVELOPE_KINDS
    assert set(DIALOG_ENVELOPE_KINDS).isdisjoint(COGNITION_ENVELOPE_KINDS)
    assert "dialog_envelope_sink" in with_dialog["note"]


# --------------------------------------------------------------------------- #
# AC5 — the live root never calls WorldRuntime.inject_envelope
# --------------------------------------------------------------------------- #


async def test_live_root_never_calls_inject_envelope(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Outbound single-owner witness (W-N3 third bullet, PR #89 HIGH-1 heir).

    Two independent checks, because either alone is weak: a spy that records
    zero calls could simply be a dead instrument, and a static check alone
    cannot see a dynamic dispatch.
    """
    agent_ids = ["a_one", "a_two"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)

    result, _, callers = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac5",
        n_cognition_ticks=2,
    )

    assert callers.count(LIVE_ROOT_MODULE) == 0
    assert society_live_loop.__name__ == LIVE_ROOT_MODULE

    # Non-vacuity: the spy DOES record a real call, so the zero above is a
    # fact about the live root, not about a dead instrument.
    with spy_inject_envelope_callers() as probe:
        result.runtime.inject_envelope(WorldTickMsg(tick=0, active_agents=0))
    assert probe == [__name__]
    assert LIVE_ROOT_MODULE not in probe

    # Static guard: the live-root module contains no ``*.inject_envelope(...)``
    # call at all (it only rebinds the attribute inside the spy itself).
    tree = ast.parse(inspect.getsource(society_live_loop))
    called = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "inject_envelope"
    ]
    assert called == []


# --------------------------------------------------------------------------- #
# AC6 — verdict is an explicit None; no effect/divergence/floor/score key
# --------------------------------------------------------------------------- #


async def test_reachability_summary_has_no_verdict(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Measurement non-reentry (``design-final.md`` §2, binding).

    Negative assertion: the forbidden vocabulary must not intersect the
    summary's key space, at either nesting level.
    """
    agent_ids = ["a_one", "a_two"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)
    plan = society_live_loop_perturbation_plan(agent_ids=agent_ids, n_ticks=2)

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac6",
        n_cognition_ticks=2,
        perturbations=plan,
    )
    summary = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )

    assert "verdict" in summary
    assert summary["verdict"] is None

    forbidden_names = {
        "effect",
        "divergence",
        "floor",
        "score",
        "scorer",
        "detectability",
        "magnitude",
        "aha",
    }
    forbidden_substrings = (
        "effect",
        "diverg",
        "floor",
        "scor",
        "detect",
        "magnitude",
        "aha",
    )
    all_keys = set(summary)
    for seams in summary["per_correlation_id"].values():
        all_keys |= set(seams)

    assert all_keys.isdisjoint(forbidden_names)
    for key in all_keys:
        for banned in forbidden_substrings:
            assert banned not in key.lower(), f"{key} names a measurement claim"

    # Honest framing is carried by the artifact, not only by this test.
    assert "Reachability is not causation" in summary["note"]
    assert "not uniform" in summary["note"].lower()


# --------------------------------------------------------------------------- #
# AC7 — tick-level seams are shared, by construction, within one tick
# --------------------------------------------------------------------------- #


async def test_tick_level_seams_are_shared_within_a_tick(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Several perturbations on one tick read the SAME tick-level booleans.

    This is by construction, never an over-count: ``correlation_id`` does not
    reach the cognition/outbound seams, so the only honest claim available at
    that granularity is "the tick co-occurred" -- asserted here to be shared
    rather than silently attributed to each perturbation individually.
    """
    agent_ids = ["a_one", "a_two", "a_three"]
    states, personas = _roster(make_agent_state, make_persona_spec, agent_ids)
    plan = society_live_loop_perturbation_plan(agent_ids=agent_ids, n_ticks=2)

    result, ledger, _ = await _drive_with_broadcast_ledger(
        agent_states=states,
        personas=personas,
        run_id="i4-ac7",
        n_cognition_ticks=2,
        perturbations=plan,
    )
    summary = society_wiring_reachability_summary(
        result, broadcast_envelope_kinds=ledger.envelope_kinds
    )

    by_tick: dict[int, list[str]] = {}
    for injected in result.ledger.injected:
        by_tick.setdefault(injected.agent_tick, []).append(injected.correlation_id)

    assert len(by_tick) >= 2, "sanity: perturbations must span >1 tick"
    tick_level_keys = ("same_tick_cognition_stepped", "same_tick_envelope_observed")
    for agent_tick, correlation_ids in by_tick.items():
        assert len(correlation_ids) == len(agent_ids), (
            f"tick {agent_tick} must carry one perturbation per agent"
        )
        for key in tick_level_keys:
            values = {
                summary["per_correlation_id"][correlation_id][key]
                for correlation_id in correlation_ids
            }
            assert len(values) == 1, (
                f"{key} must be shared by every perturbation on tick {agent_tick}"
            )

    # ... while a per-correlation seam stays genuinely per-correlation: each
    # message's own routing bucket differs within that same shared tick.
    first_tick = min(by_tick)
    routed = {
        injected.routed_agent_id
        for injected in result.ledger.injected
        if injected.agent_tick == first_tick
    }
    assert routed == set(agent_ids)


# =============================================================================
# Issue 005 — W-N2 mirror (prompt-level self-other context) wiring witness
# =============================================================================
#
# ``loop/20260906-m13-society-live-closure/issues/005.md``: Ollama-free, record
# mode, scripted inner-chat doubles. The mirror is NOT re-implemented by the
# live root -- ``run_society_loop(self_other_enabled=True)`` builds it through
# ``society.py``'s own ``build_self_other_context``, and every assertion below
# reads the COMMITTED record back out (``RecordedLlmCall.user_prompt``).
#
# **Every witness below carries a breaking negative** (DA-SLC-8's lesson: an
# orchestrator-specified seam equality turned out to be tautological, so
# non-tautology must be demanded by the AC rather than left to the implementer):
# AC1 is falsified by a ``self_other_enabled=False`` control, AC2/AC3/AC5 by
# doctored committed records that the SAME witness function must report as
# ``False``. Nothing here grades the segment's content (Stop condition S4) and
# nothing reads whether the segment changed any behaviour (frozen second link).


class _EchoingInner:
    """Adversarial inner chat: echoes the self-other marker into its own output.

    Design-copy of ``test_m2_society_selfother.py::_EchoingChat`` (this suite's
    convention for small private doubles), with one deliberate difference: it
    echoes the WHOLE marker (society's own framing line) rather than an ASCII
    head of it, and serialises with ``ensure_ascii=False`` so the marker's em
    dash survives verbatim into ``RecordedLlmCall.raw_response``. That is what
    makes the Codex L-2 discrimination non-vacuous: the marker genuinely appears
    in the LLM's own output, and the witness must still report the
    observation-derived memory field as clean.
    """

    def __init__(self, marker: str) -> None:
        self._marker = marker
        self.echoed = False

    async def chat(self, messages, *, sampling, model=None, options=None, think=None):  # noqa: ARG002
        user = next((m.content for m in messages if m.role == "user"), "")
        has_segment = self._marker in user
        self.echoed = self.echoed or has_segment
        payload = {
            "thought": self._marker if has_segment else "no self-other segment",
            "utterance": self._marker if has_segment else "散歩へ",
            "destination_zone": "peripatos",
            "animation": "walk",
        }
        return ChatResponse(
            content=json.dumps(payload, ensure_ascii=False),
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )


async def _drive_mirror(
    *,
    run_id: str,
    n_cognition_ticks: int = 3,
    self_other_enabled: bool = True,
    inner_chats: Mapping[str, Any] | None = None,
) -> SocietyRunResult:
    """One sealed-roster (N=3) drive, Layer2 on or off, otherwise identical.

    ``self_other_enabled=True`` goes through the live closure root itself
    (:func:`run_society_live_loop`). ``False`` is the ablation control: it
    reproduces that function's own ``run_society_loop`` call field-for-field
    except the flag (and the runtime-capture hook, which only reads the runtime
    and never touches cognition), so an on/off comparison differs in the mirror
    and in nothing else -- the AC4 call-budget equality is then a real
    measurement of the flag's cost, not a comparison of two identical configs.

    The frozen perturbation plan is pushed into the sink so every window has
    real inbound observations, and therefore real observation-derived episodic
    memory rows for the AC3 disjointness check to be non-vacuous about.
    """
    agent_ids = tuple(SOCIETY_LIVE_AGENT_IDS)
    store, embedding = _fresh_store_and_embedding()
    sink = InboundSink()
    chats = (
        {aid: _ScriptedInner(_PLAN_JSON) for aid in agent_ids}
        if inner_chats is None
        else dict(inner_chats)
    )
    world = build_society_live_world(
        inner_chats=chats,
        store=store,
        embedding=embedding,
        inbound_sink=sink,
        max_drain_per_tick=len(agent_ids),
    )
    for msg in society_live_loop_perturbation_plan(
        agent_ids=agent_ids, n_ticks=n_cognition_ticks
    ):
        sink.push(msg)
    try:
        if self_other_enabled:
            run = await run_society_live_loop(
                world,
                run_id=run_id,
                retrieval_now=_FIXED,
                base_ts=_FIXED,
                n_cognition_ticks=n_cognition_ticks,
                physics_ticks_per_cognition=2,
            )
            return run.result
        return await run_society_loop(
            run_id=run_id,
            store=world.store,
            embedding=world.embedding,
            llms=world.llms,
            agent_states=world.agent_states,
            personas=world.personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            seed=0,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=2,
            observation_factories=world.router.observation_factories(agent_ids),
            self_other_enabled=False,
            two_phase_knob=world.knob,
        )
    finally:
        await embedding.close()
        await store.close()


def _replace_decisions(
    result: SocietyRunResult,
    decisions: Mapping[str, tuple[Any, ...]],
) -> SocietyRunResult:
    """A doctored copy of a committed result (negative fixtures only)."""
    return dataclasses.replace(result, decisions=dict(decisions))


def _nested_keys(summary: Mapping[str, Any]) -> set[str]:
    """Every key name in ``summary``, at any nesting depth."""
    keys: set[str] = set()
    stack: list[Any] = [summary]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            keys |= set(map(str, node))
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    return keys


# --------------------------------------------------------------------------- #
# AC1 — a non-empty self-other segment rode in a committed live cognition call
# (+ the flag-off control that must NOT detect one: the witness is not
# tautologically true)
# --------------------------------------------------------------------------- #


async def test_self_other_segment_present_in_committed_prompt() -> None:
    marker = self_other_segment_marker()
    assert marker, "society's public builder rendered no framing line"

    on_result = await _drive_mirror(run_id="i5-ac1-on")
    on_summary = society_mirror_wiring_summary(on_result)

    assert on_summary["segment_marker"] == marker
    assert on_summary["any_agent_window_has_segment"] is True
    assert on_summary["segment_present_count"] >= 1
    # The segment really is in the committed prompt, not only in the witness.
    carried = [
        (segment.agent_id, segment.window)
        for segment in committed_self_other_segments(on_result)
    ]
    assert carried, "no committed call carried a self-other segment"
    for agent_id, window in carried:
        assert marker in on_result.decisions[agent_id][window].call.user_prompt

    # Breaking negative (non-tautology): the identical drive with Layer2 off
    # must be reported by the SAME witness as carrying no segment at all.
    off_result = await _drive_mirror(run_id="i5-ac1-off", self_other_enabled=False)
    off_summary = society_mirror_wiring_summary(off_result)

    assert off_summary["any_agent_window_has_segment"] is False
    assert off_summary["segment_present_count"] == 0
    assert not committed_self_other_segments(off_result)


# --------------------------------------------------------------------------- #
# AC2 — window 0 carries no segment (strict prefix filter's observable
# consequence: no prior window, and never the observer itself)
# --------------------------------------------------------------------------- #


async def test_self_other_segment_empty_at_window_zero() -> None:
    result = await _drive_mirror(run_id="i5-ac2")
    summary = society_mirror_wiring_summary(result)

    assert summary["window_zero_segment_absent"] is True
    for windows in summary["segment_present_windows_per_agent"].values():
        assert all(window >= 1 for window in windows)
    # Non-vacuous: some window >= 1 DID carry a segment, so "absent at 0" is a
    # real filter result rather than "absent everywhere".
    assert summary["segment_present_count"] >= 1
    # Self never leaks into its own observer's segment, and the render contract
    # was genuinely parsed (an empty parse would flip the second boolean).
    assert summary["segment_never_names_observer"] is True
    assert summary["every_nonempty_segment_names_a_roster_agent"] is True
    assert summary["roster_ids_prefix_free"] is True

    # Breaking negative (non-tautology): doctor window 0's committed prompt so
    # it DOES carry a segment; the same witness must report False.
    agent_id = sorted(result.decisions)[0]
    other_id = sorted(result.decisions)[1]
    records = list(result.decisions[agent_id])
    forged = f"{summary['segment_marker']}\n- {other_id}: zone=study"
    records[0] = dataclasses.replace(
        records[0],
        call=dataclasses.replace(
            records[0].call,
            user_prompt=f"{records[0].call.user_prompt}\n\n{forged}\n\n",
        ),
    )
    doctored = _replace_decisions(
        result, {**result.decisions, agent_id: tuple(records)}
    )
    doctored_summary = society_mirror_wiring_summary(doctored)

    assert doctored_summary["window_zero_segment_absent"] is False
    assert 0 in doctored_summary["segment_present_windows_per_agent"][agent_id]


# --------------------------------------------------------------------------- #
# AC3 — disjointness, scoped to the observation-derived memory field (Codex
# L-2), made non-vacuous by an echoing adversary mock
# --------------------------------------------------------------------------- #


async def test_self_other_segment_disjoint_from_observation_memory() -> None:
    marker = self_other_segment_marker()
    echoers = {aid: _EchoingInner(marker) for aid in SOCIETY_LIVE_AGENT_IDS}
    result = await _drive_mirror(run_id="i5-ac3", inner_chats=echoers)
    summary = society_mirror_wiring_summary(result)

    # Non-vacuous adversary: at least one agent actually saw AND echoed it.
    assert any(inner.echoed for inner in echoers.values()), (
        "the echoing mock never saw the self-other segment -- vacuous adversary"
    )
    assert summary["llm_output_segment_echo_count"] > 0
    # Non-vacuous sink: observation-derived episodic rows were really written.
    assert summary["observation_memory_row_count"] > 0
    assert summary["observation_memory_kinds"] == {
        "episodic": summary["observation_memory_row_count"]
    }
    # Non-vacuous seam: the segment really was on the live prompts this run.
    assert summary["segment_present_count"] >= 1

    # Codex L-2: the LLM echoing the marker into its OWN raw response is not a
    # disjointness violation -- the inspected field is the observation-derived
    # memory content, which must stay clean even under that adversary.
    assert summary["segment_absent_from_observation_memory"] is True
    assert summary["observation_memory_rows_carrying_segment"] == []
    echoing_calls = [
        record
        for records in result.decisions.values()
        for record in records
        if marker in record.call.raw_response
    ]
    assert echoing_calls, "adversary never reached the committed record"

    # Breaking negative (non-tautology): a committed run whose observation
    # memory DID carry the segment must be reported as not disjoint.
    leaked_from = result.memory_mutations[0]
    leaked = dataclasses.replace(
        leaked_from,
        memory_id="leaked-observation-row",
        content=f"{leaked_from.content} {marker}",
    )
    doctored = dataclasses.replace(
        result, memory_mutations=(*result.memory_mutations, leaked)
    )
    doctored_summary = society_mirror_wiring_summary(doctored)

    assert doctored_summary["segment_absent_from_observation_memory"] is False
    assert doctored_summary["observation_memory_rows_carrying_segment"] == [
        "leaked-observation-row"
    ]

    # A partial leak (one observed-other bullet line, no framing header) is
    # caught too -- the needle set is not just the header.
    body_line = committed_self_other_segments(result)[0].text.splitlines()[1]
    partial = dataclasses.replace(
        leaked_from, memory_id="partial-leak-row", content=body_line
    )
    partial_summary = society_mirror_wiring_summary(
        dataclasses.replace(
            result, memory_mutations=(*result.memory_mutations, partial)
        )
    )
    assert partial_summary["segment_absent_from_observation_memory"] is False


# --------------------------------------------------------------------------- #
# AC4 — the mirror adds no LLM call: N x ticks, identical with the flag on/off
# (Codex M-4)
# --------------------------------------------------------------------------- #


async def test_llm_call_count_is_n_agents_times_ticks() -> None:
    n_agents = len(SOCIETY_LIVE_AGENT_IDS)
    ticks = SOCIETY_LIVE_N_COGNITION_TICKS

    on_result = await _drive_mirror(run_id="i5-ac4-on", n_cognition_ticks=ticks)
    off_result = await _drive_mirror(
        run_id="i5-ac4-off", n_cognition_ticks=ticks, self_other_enabled=False
    )
    on_summary = society_mirror_wiring_summary(on_result)
    off_summary = society_mirror_wiring_summary(off_result)

    assert on_summary["llm_call_count"] == n_agents * ticks == 36
    assert on_summary["llm_call_count"] == off_summary["llm_call_count"]
    assert on_summary["llm_call_count_equals_agents_times_windows"] is True
    assert off_summary["llm_call_count_equals_agents_times_windows"] is True
    assert on_summary["windows_per_agent"] == off_summary["windows_per_agent"]
    assert set(on_summary["windows_per_agent"].values()) == {ticks}

    # The two runs really did differ in the mirror -- otherwise the equality
    # above would be comparing two identical configurations.
    assert on_summary["segment_present_count"] > 0
    assert off_summary["segment_present_count"] == 0

    # Breaking negative: a run that HAD added a call per segment would not
    # satisfy the pin, and the same witness reports that.
    agent_id = sorted(on_result.decisions)[0]
    inflated = _replace_decisions(
        on_result,
        {
            **on_result.decisions,
            agent_id: (
                *on_result.decisions[agent_id],
                on_result.decisions[agent_id][0],
            ),
        },
    )
    inflated_summary = society_mirror_wiring_summary(inflated)
    assert inflated_summary["llm_call_count"] == n_agents * ticks + 1
    assert inflated_summary["llm_call_count_equals_agents_times_windows"] is False


# --------------------------------------------------------------------------- #
# AC5 — per-agent call attribution is unique (Codex M-4)
# --------------------------------------------------------------------------- #


async def test_per_agent_call_attribution_is_unique() -> None:
    result = await _drive_mirror(run_id="i5-ac5")
    summary = society_mirror_wiring_summary(result)

    assert summary["agent_ids"] == sorted(SOCIETY_LIVE_AGENT_IDS)
    assert summary["agent_window_pairs_unique"] is True
    assert summary["agent_windows_complete"] is True
    # A call filed under the wrong observer would name that observer in its own
    # segment; it does not.
    assert summary["segment_never_names_observer"] is True
    assert summary["every_nonempty_segment_names_a_roster_agent"] is True
    # The driver's own step order agrees: sorted roster, once per window.
    assert list(result.cognition_step_order[: len(summary["agent_ids"])]) == sorted(
        SOCIETY_LIVE_AGENT_IDS
    )

    # Breaking negative A (mis-attribution): swap two agents' committed call
    # streams. Each now carries segments naming its own key -> witness False.
    first, second = sorted(result.decisions)[:2]
    swapped = _replace_decisions(
        result,
        {
            **result.decisions,
            first: result.decisions[second],
            second: result.decisions[first],
        },
    )
    swapped_summary = society_mirror_wiring_summary(swapped)
    assert swapped_summary["segment_never_names_observer"] is False
    assert swapped_summary["agent_window_pairs_unique"] is True  # still a bijection

    # Breaking negative B (duplicate attribution): the same (agent, window) twice.
    duplicated = _replace_decisions(
        result,
        {
            **result.decisions,
            first: (*result.decisions[first], result.decisions[first][0]),
        },
    )
    duplicated_summary = society_mirror_wiring_summary(duplicated)
    assert duplicated_summary["agent_window_pairs_unique"] is False
    assert duplicated_summary["agent_windows_complete"] is False


# --------------------------------------------------------------------------- #
# AC6 — verdict is an explicit None; no effect / detectability / divergence /
# floor / scorer key at any nesting level (measurement non-reentry)
# --------------------------------------------------------------------------- #


async def test_mirror_witness_has_no_verdict() -> None:
    result = await _drive_mirror(run_id="i5-ac6")
    summary = society_mirror_wiring_summary(result)

    assert "verdict" in summary
    assert summary["verdict"] is None

    forbidden_names = {
        "effect",
        "divergence",
        "floor",
        "score",
        "scorer",
        "detectability",
        "magnitude",
        "aha",
    }
    forbidden_substrings = (
        "effect",
        "diverg",
        "floor",
        "scor",
        "detect",
        "magnitude",
        "aha",
    )
    all_keys = _nested_keys(summary)
    assert all_keys.isdisjoint(forbidden_names)
    for key in all_keys:
        for banned in forbidden_substrings:
            assert banned not in key.lower(), f"{key} names a measurement claim"

    # Honest framing is carried by the artifact, not only by this test
    # (Codex L-1: no "simulate ... inner state" vocabulary of this module's own;
    # the marker VALUE quotes society's render verbatim, the note does not).
    note = summary["note"].lower()
    assert "construction wiring" in note
    assert "not a theory of mind" in note
    assert "not an estimate of any agent's inner state" in note
    assert "not a measurement" in note
    assert "simulate" not in note
    assert "observation-derived memory field" in note


# --------------------------------------------------------------------------- #
# Issue 006 — Plane G byte-parity + request conformance (design-final.md §6 W-N4)
#
# Ollama-free throughout: a record-mode capture and its replay run in the SAME
# process, both over scripted doubles. Every assertion is a checksum identity, a
# boolean or a count -- never a floor / verdict / scorer / divergence
# (``design-final.md`` §2 honest framing).
#
# **Non-vacuity is the point (``decisions.md`` DA-SLC-8)**: AC4 / AC6 / AC7 each
# carry a negative fixture that makes the guard FAIL, so none of them can be
# "an inspection that only ever returns True". AC1's Plane G parity carries its
# own: the drift fixture in AC4 shows the geometry checksum stays green while
# conformance goes red, which is exactly the failure mode an ordinal replay
# hides and the reason Codex H-4 required a replay-side spy at all.
# --------------------------------------------------------------------------- #

_PLANE_G_TICKS = 3
_PLANE_G_PHYSICS = 2


@dataclasses.dataclass(frozen=True, slots=True)
class _PlaneGCapture:
    """One committed record-mode society capture plus its replay inputs."""

    result: SocietyRunResult
    ledger: tuple[SocietyLedgerEntry, ...]
    recorded_llm: Mapping[str, tuple[RecordedLlmCall, ...]]
    recorded_embedding: tuple[RecordedEmbeddingCall, ...]
    agent_states: list[AgentState]
    personas: dict[str, PersonaSpec]

    @property
    def committed_embedding_requests(self) -> list[tuple[str, str]]:
        return [(call.kind, call.text) for call in self.recorded_embedding]


async def _capture_for_plane_g(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    *,
    run_id: str,
    agent_ids: Sequence[str] = SOCIETY_LIVE_AGENT_IDS,
    n_cognition_ticks: int = _PLANE_G_TICKS,
) -> _PlaneGCapture:
    """Drive one knob-ON live capture and collect everything a replay needs.

    Knob-on on purpose: Plane G's whole claim is that a knob-ON capture replays
    byte-identically through a knob-OFF unmodified ``run_society_loop``, so a
    knob-off capture would make the test vacuous on the very property it pins.
    """
    states, personas = _roster(make_agent_state, make_persona_spec, list(agent_ids))
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    inner_embedding = _embed_client()
    recorder = EmbeddingRecordReplayClient(inner=inner_embedding)
    sink = InboundSink()
    world = build_society_live_world(
        inner_chats={state.agent_id: _ScriptedInner(_PLAN_JSON) for state in states},
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
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=_PLANE_G_PHYSICS,
        )
    finally:
        await inner_embedding.close()
        await store.close()
    return _PlaneGCapture(
        result=run.result,
        ledger=society_ledger_entries(run.ledger.injected),
        recorded_llm=recorded_llm_from_capture(run.result),
        recorded_embedding=tuple(recorder.used),
        agent_states=states,
        personas=personas,
    )


async def _replay_plane_g(
    capture: _PlaneGCapture,
    *,
    run_id: str,
    ledger: Sequence[SocietyLedgerEntry] | None = None,
    two_phase_knob: TwoPhaseKnob | None = None,
    n_cognition_ticks: int = _PLANE_G_TICKS,
) -> SocietyPlaneGReplay:
    """Replay ``capture`` through the UNMODIFIED driver on a fresh store."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    try:
        return await replay_society_plane_g(
            recorded_llm=capture.recorded_llm,
            recorded_embedding=capture.recorded_embedding,
            ledger=capture.ledger if ledger is None else ledger,
            store=store,
            agent_states=capture.agent_states,
            personas=capture.personas,
            run_id=run_id,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=n_cognition_ticks,
            physics_ticks_per_cognition=_PLANE_G_PHYSICS,
            two_phase_knob=two_phase_knob,
        )
    finally:
        await store.close()


def _plane_g_run_config() -> dict[str, Any]:
    return {
        "seed": 0,
        "physics_ticks_per_cognition": _PLANE_G_PHYSICS,
        "k_ecl": K_ECL,
        "base_ts": _FIXED.isoformat(),
        "retrieval_now": _FIXED.isoformat(),
    }


# --------------------------------------------------------------------------- #
# AC1 — the committed capture replays byte-identically through the UNMODIFIED
# ``run_society_loop`` (knob-on capture -> knob-off replay)
# --------------------------------------------------------------------------- #


async def test_plane_g_replay_checksums_byte_identical(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``ecl_trace_checksum`` AND ``event_log_checksum`` both byte-match.

    Plane G (``design-final.md`` §5): committed inbound ledger ->
    :func:`ledger_observation_factories` -> unmodified ``run_society_loop``
    (replay clients, ``self_other_enabled=True``, knob-off) -> the same two
    checksums the knob-on live capture produced.

    Scope (Codex M-3, binding): this parity is over the SCRIPTED in-process
    perturbation sequence only. It is not a wall-clock real-time session, and
    real Godot / WS arrival times / LLM latency are outside the replay set.
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac1"
    )
    replay = await _replay_plane_g(capture, run_id="i6-ac1")
    parity = society_plane_g_parity(
        pins=society_plane_g_pins(capture.result), replay=replay
    )

    assert replay.result.checksum == capture.result.checksum
    assert replay.result.event_log_checksum == capture.result.event_log_checksum
    assert parity["geometry_checksum_match"] is True
    assert parity["event_log_checksum_match"] is True
    assert parity["cognition_step_order_match"] is True
    assert parity["verdict"] is None

    # Non-vacuity: the checksums are real digests of a real N-agent run, not
    # two empty strings agreeing with each other.
    assert len(capture.result.checksum) == 64
    assert len(capture.result.event_log_checksum) == 64
    assert capture.result.checksum != capture.result.event_log_checksum
    assert len(capture.result.decisions) == len(SOCIETY_LIVE_AGENT_IDS)
    assert len(capture.ledger) == len(SOCIETY_LIVE_AGENT_IDS) * _PLANE_G_TICKS


async def test_ledger_factories_group_by_routed_agent_id(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The replay feed keys on ``routed_agent_id``, never ``target_agent_id``.

    ``decisions.md`` DA-SLC-8, restated as a negative fixture: a mis-bucketed
    row (routed to an agent other than the one it was aimed at) must follow the
    bucket it actually landed in. A factory table keyed on the message's
    ``target_agent_id`` — or on ``observation.agent_id``, which ``inbound.py``
    copies from it unconditionally — would put it in the wrong agent's window
    and this assertion would fail.
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac1-routing"
    )
    row = capture.ledger[0]
    other_agent_id = next(
        agent_id
        for agent_id in SOCIETY_LIVE_AGENT_IDS
        if agent_id != row.routed_agent_id
    )
    mis_bucketed = SocietyLedgerEntry(
        agent_tick=row.agent_tick,
        correlation_id=row.correlation_id,
        routed_agent_id=other_agent_id,
        msg=row.msg,
    )

    factories = ledger_observation_factories(
        [mis_bucketed], agent_ids=SOCIETY_LIVE_AGENT_IDS
    )
    assert len(factories[other_agent_id](row.agent_tick)) == 1
    assert factories[row.routed_agent_id](row.agent_tick) == ()
    # The observation still NAMES the intended agent -- which is exactly why
    # grouping on that field would be a tautology.
    assert (
        factories[other_agent_id](row.agent_tick)[0].agent_id == row.msg.target_agent_id
    )
    assert row.msg.target_agent_id != other_agent_id


# --------------------------------------------------------------------------- #
# AC2 — the replay reached no backend at all
# --------------------------------------------------------------------------- #


async def test_plane_g_replay_touches_no_llm(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Every replay channel's ``inner_invocations`` is 0 (both planes)."""
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac2"
    )
    replay = await _replay_plane_g(capture, run_id="i6-ac2")

    assert set(replay.llm_inner_invocations) == set(SOCIETY_LIVE_AGENT_IDS)
    for agent_id in sorted(replay.llm_inner_invocations):
        assert replay.llm_inner_invocations[agent_id] == 0
    assert replay.embedding_inner_invocations == 0

    parity = society_plane_g_parity(
        pins=society_plane_g_pins(capture.result), replay=replay
    )
    assert parity["replay_touched_no_llm"] is True

    # Non-vacuity: the replay really did serve calls -- a run that made no call
    # at all would also report 0 inner invocations.
    assert len(replay.llm_requests) == len(SOCIETY_LIVE_AGENT_IDS) * _PLANE_G_TICKS
    assert replay.embedding_requests
    assert tuple(replay.embedding_used) == capture.recorded_embedding


# --------------------------------------------------------------------------- #
# AC3 — request conformance on (agent_id, window, system_prompt, user_prompt),
# with ``sampling`` explicitly excluded (Codex H-4)
# --------------------------------------------------------------------------- #


async def test_request_conformance_prompts_match_excluding_sampling(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The recomposed requests match the committed record; sampling is out.

    The exclusion is not an undocumented omission: it is a named module
    constant, it is carried in the artifact this function returns, and the
    spy *does* observe the sampling — it just keeps it in a separate channel
    (:attr:`samplings`) so the conformance comparison can never include it.
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac3"
    )
    replay = await _replay_plane_g(capture, run_id="i6-ac3")
    summary = society_request_conformance(
        replay=replay,
        recorded_llm=capture.recorded_llm,
        committed_embedding_requests=capture.committed_embedding_requests,
    )

    assert summary["llm_requests_match"] is True
    assert summary["llm_first_drift"] is None
    assert summary["embedding_requests_match"] is True
    assert summary["embedding_first_drift"] is None
    assert summary["verdict"] is None

    # The exclusion is explicit, in the API surface and in the artifact.
    assert "sampling" not in CONFORMANCE_COMPARED_FIELDS
    assert CONFORMANCE_EXCLUDED_FIELDS == ("sampling",)
    assert summary["compared_fields"] == [
        "agent_id",
        "window",
        "system_prompt",
        "user_prompt",
    ]
    assert summary["excluded_fields"] == ["sampling"]
    assert summary["excluded_fields_reason"] == CONFORMANCE_SAMPLING_EXCLUSION_REASON
    assert "knob-off" in summary["excluded_fields_reason"]
    assert "record_knob_on_pinned" in summary["excluded_fields_reason"]

    # The excluded field is genuinely observed, not simply unavailable.
    for agent_id in sorted(replay.samplings_per_agent):
        assert len(replay.samplings_per_agent[agent_id]) == _PLANE_G_TICKS

    # The self-other segment is read through society's own render contract
    # (``self_other_segment_contract``), never a literal copied into this test.
    assert summary["self_other_segment_marker"] == self_other_segment_marker()
    assert summary["self_other_segment_present_count_committed"] > 0
    assert summary["self_other_segments_match"] is True


# --------------------------------------------------------------------------- #
# AC4 — a one-character prompt drift makes conformance FAIL (non-vacuous)
# --------------------------------------------------------------------------- #


async def test_request_conformance_detects_prompt_drift(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Two independent negative fixtures; the check is not tautological.

    **(a) committed-side drift** — one character changed in one committed
    ``user_prompt`` turns ``llm_requests_match`` ``False`` and the drift record
    names the exact ``(agent_id, window, field)``.

    **(b) replay-side drift (the Codex H-4 scenario proper)** — one character
    changed in one committed *observation*, so the cognition cycle recomposes a
    different prompt on replay. The ordinal replay client still serves the same
    recorded answers, so **the geometry checksum stays byte-identical and green**
    — and conformance is the only thing that catches it. That is the whole
    reason a replay-side spy exists rather than a comparison of
    ``result.decisions[*].call`` against the record (which would compare the
    committed record with itself).
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac4"
    )
    replay = await _replay_plane_g(capture, run_id="i6-ac4")

    # (a) committed-side: mutate ONE character of ONE committed user_prompt.
    drifted_agent_id = sorted(capture.recorded_llm)[1]
    drifted_calls = list(capture.recorded_llm[drifted_agent_id])
    original = drifted_calls[1]
    drifted_calls[1] = dataclasses.replace(
        original, user_prompt=original.user_prompt + "X"
    )
    drifted_record = dict(capture.recorded_llm)
    drifted_record[drifted_agent_id] = tuple(drifted_calls)

    committed_drift = society_request_conformance(
        replay=replay,
        recorded_llm=drifted_record,
        committed_embedding_requests=capture.committed_embedding_requests,
    )
    assert committed_drift["llm_requests_match"] is False
    drift = committed_drift["llm_first_drift"]
    assert drift is not None
    assert drift["agent_id"] == drifted_agent_id
    assert drift["window"] == 1
    assert drift["fields"] == ["user_prompt"]

    # An embedding-side drift is caught by its own half of the check.
    mutated_embedding = list(capture.committed_embedding_requests)
    kind, text = mutated_embedding[0]
    mutated_embedding[0] = (kind, text + "X")
    embedding_drift = society_request_conformance(
        replay=replay,
        recorded_llm=capture.recorded_llm,
        committed_embedding_requests=mutated_embedding,
    )
    assert embedding_drift["embedding_requests_match"] is False
    assert embedding_drift["embedding_first_drift"] == {
        "index": 0,
        "reason": "field_mismatch",
        "kind_matches": True,
    }

    # (b) replay-side: one character changed in one committed observation.
    first = capture.ledger[0]
    apparatus_drift_ledger = (
        SocietyLedgerEntry(
            agent_tick=first.agent_tick,
            correlation_id=first.correlation_id,
            routed_agent_id=first.routed_agent_id,
            msg=first.msg.model_copy(update={"content": first.msg.content + "X"}),
        ),
        *capture.ledger[1:],
    )
    drifted_replay = await _replay_plane_g(
        capture, run_id="i6-ac4", ledger=apparatus_drift_ledger
    )
    assert drifted_replay.result.checksum == capture.result.checksum  # still green
    apparatus_conformance = society_request_conformance(
        replay=drifted_replay,
        recorded_llm=capture.recorded_llm,
        committed_embedding_requests=capture.committed_embedding_requests,
    )
    assert apparatus_conformance["llm_requests_match"] is False
    assert apparatus_conformance["llm_first_drift"] is not None
    assert apparatus_conformance["llm_first_drift"]["fields"] == ["user_prompt"]


# --------------------------------------------------------------------------- #
# AC5 — the run-level self-other slot survives the replay unchanged
# --------------------------------------------------------------------------- #


async def test_self_other_slot_reproduced_on_replay(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``self_other_observation_input`` is identical live vs replayed.

    Non-vacuous by construction: the slot is asserted **populated** first, so
    the equality is not two ``None``s agreeing (which is what a Layer2-off run
    would produce).
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac5"
    )
    replay = await _replay_plane_g(capture, run_id="i6-ac5")

    assert capture.result.self_other_observation_input is not None
    assert (
        replay.result.self_other_observation_input
        == capture.result.self_other_observation_input
    )
    parity = society_plane_g_parity(
        pins=society_plane_g_pins(capture.result), replay=replay
    )
    assert parity["self_other_slot_present"] is True
    assert parity["self_other_slot_match"] is True

    # A doctored pin (slot removed) must make the same witness go False --
    # otherwise the boolean would be reporting nothing.
    blank_pins = dataclasses.replace(
        society_plane_g_pins(capture.result), self_other_observation_input=None
    )
    assert (
        society_plane_g_parity(pins=blank_pins, replay=replay)["self_other_slot_match"]
        is False
    )


# --------------------------------------------------------------------------- #
# AC6 — no new non-determinism source in the live root (AST guard + negatives)
# --------------------------------------------------------------------------- #

_NONDETERMINISM_NEGATIVE_FIXTURE = '''
"""A live root that leaks -- the guard must flag every line below."""
import uuid
from datetime import datetime


def leaky(mapping, pairs):
    dialog_id = uuid.uuid4()
    stamp = datetime.now()
    for key in mapping.keys():
        print(key)
    for agent_id in set(pairs):
        print(agent_id)
    return [value for value in mapping.values()], dialog_id, stamp
'''

_NONDETERMINISM_CLEAN_FIXTURE = '''
"""The same module written the way the live root is."""
from datetime import UTC, datetime

PINNED = datetime(2026, 1, 1, tzinfo=UTC)


def tidy(mapping, pairs):
    for key in sorted(mapping):
        print(key)
    for agent_id in sorted(set(pairs)):
        print(agent_id)
    return [mapping[key] for key in sorted(mapping)], PINNED
'''


def test_no_new_nondeterminism_sources() -> None:
    """The live root carries no uuid4 / ``datetime.now()`` / unsorted iteration.

    ``design-final.md`` §5's determinism table, enforced mechanically rather
    than by review: :func:`scan_nondeterminism_sources` parses the module's own
    source and flags forbidden calls and order-unstable iteration.

    The negative fixture is what makes the empty result meaningful — it proves
    the scanner is capable of returning findings, so "no findings on the live
    root" is a result rather than the only thing it can say. The clean fixture
    closes the other side: the guard does not simply flag everything.
    """
    assert live_root_nondeterminism_findings() == ()
    assert "society_live_loop" in LIVE_ROOT_MODULE
    assert "def scan_nondeterminism_sources" in live_root_source()

    findings = scan_nondeterminism_sources(_NONDETERMINISM_NEGATIVE_FIXTURE)
    assert findings, "the guard must be able to fail"
    by_name = {finding.name for finding in findings}
    kinds = {finding.kind for finding in findings}
    assert "uuid4" in by_name
    assert "now" in by_name
    assert ".keys()" in by_name
    assert ".values()" in by_name
    assert "set()" in by_name
    assert kinds == {"nondeterministic_call", "unsorted_iteration"}
    assert all(isinstance(finding, NondeterminismFinding) for finding in findings)
    assert all(finding.lineno > 0 for finding in findings)
    # Deterministic output order (the guard is itself part of the live root).
    assert list(findings) == sorted(findings, key=lambda f: (f.lineno, f.kind, f.name))

    assert scan_nondeterminism_sources(_NONDETERMINISM_CLEAN_FIXTURE) == ()


# --------------------------------------------------------------------------- #
# Codex TASK-POST M-2 — shared ECL v1 measurement-line guard, applied to the
# module that actually EMITS the five W-N1/W-N3 witnesses (society_live_loop.py
# itself), not just to the capture harness and its test. ``_measurement_guard.py``
# is unmodified (shared file, binding); this only adds a caller.
# --------------------------------------------------------------------------- #


def test_live_root_has_no_measurement_surface() -> None:
    """``society_live_loop.py`` carries no banned import / identifier / dict
    key / ``.json(l)`` filename token, ``scan_strings=True`` included.

    Prior to this test, :func:`~tests.test_integration._measurement_guard.
    assert_no_measurement_surface_v1` was only wired to
    ``scripts/m13_society_live_capture.py`` (the harness) and its own test --
    never to this module, even though this module is the one that actually
    *emits* all five witnesses (:func:`society_wiring_reachability_summary`,
    :func:`society_mirror_wiring_summary`, :func:`society_plane_g_parity`,
    :func:`society_request_conformance`, :func:`society_firing_annotation`).
    It happens to PASS with ``scan_strings=True`` today -- this test locks
    that in mechanically rather than by review, the same way
    :func:`test_no_new_nondeterminism_sources` locks in the determinism
    table above.

    ``society.py`` (the frozen ADR §1 core this module wraps, unmodified by
    this task) also happens to pass the same scan, so it is pinned here too
    -- the shared guard file itself stays untouched either way.
    """
    tree = ast.parse(live_root_source())
    assert_no_measurement_surface_v1(tree, scan_strings=True)

    society_tree = ast.parse(inspect.getsource(society))
    assert_no_measurement_surface_v1(society_tree, scan_strings=True)


# --------------------------------------------------------------------------- #
# AC7 — floats inside embedded serialised JSON go through the 6-decimal
# re-quantisation at the projection boundary
# --------------------------------------------------------------------------- #


def _float_leaves(node: Any) -> list[float]:
    """Every float leaf in a parsed JSON payload."""
    if isinstance(node, bool):
        return []
    if isinstance(node, float):
        return [node]
    if isinstance(node, dict):
        return [leaf for key in sorted(node) for leaf in _float_leaves(node[key])]
    if isinstance(node, list):
        return [leaf for item in node for leaf in _float_leaves(item)]
    return []


def _shift_first_physical_float(
    capture: SocietyRunResult, *, field: str, delta: float
) -> SocietyRunResult:
    """Nudge one float **inside** a pre-serialised ``envelope_provenance`` entry.

    The mutated value lives in a ``model_dump_json`` string, i.e. as TEXT — the
    exact place the surrounding canonicaliser's blanket float rule cannot see
    and where ``handoff``'s ``_quantize_embedded_json`` is the only thing
    standing between a Windows bake and a Linux one
    (``feedback_golden_crossplatform_float_drift``, PR #55/#76).
    """
    agent_id = sorted(capture.decisions)[0]
    records = list(capture.decisions[agent_id])
    envelopes = list(records[0].envelope_provenance)
    index = next(i for i, env in enumerate(envelopes) if f'"{field}"' in env)
    payload = json.loads(envelopes[index])
    physical = payload["agent_state"]["physical"]
    physical[field] = physical[field] + delta
    envelopes[index] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    records[0] = dataclasses.replace(records[0], envelope_provenance=tuple(envelopes))
    decisions = dict(capture.decisions)
    decisions[agent_id] = tuple(records)
    return _replace_decisions(capture, decisions)


def _event_log_checksum_of(result: SocietyRunResult) -> str:
    return society.event_log_checksum(
        rows=result.rows,
        decisions=result.decisions,
        pair_events=result.pair_events,
        dialog_events=result.dialog_events,
        affinity_deltas=result.affinity_deltas,
        memory_mutations=result.memory_mutations,
        self_other_observation_input=result.self_other_observation_input,
    )


async def test_embedded_json_floats_are_requantised(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """The bundle projection re-quantises floats inside embedded JSON strings.

    Positive: no float inside any projected ``envelope_provenance`` entry keeps
    more than six decimals.

    Negative fixture 1 (the guard is load-bearing): the RAW pre-projection
    strings do carry longer floats, and a naive ``json.dumps`` pass-through
    keeps them verbatim — so the quantised output is the projection's doing,
    not an accident of the data already being short.

    Negative fixture 2 (non-vacuous in BOTH directions): a sub-quantum nudge
    (below half of 1e-6, i.e. the cross-platform ``libm`` drift this rule
    exists to absorb) leaves the projected bytes and the event-log checksum
    byte-identical, while a supra-quantum nudge changes both. A projection that
    quantised everything to a constant, or one that quantised nothing, would
    fail one of those two.
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac7"
    )
    field = "sleep_quality"
    bundle = society_plane_g_bundle(
        capture.result,
        ledger=capture.ledger,
        recorded_embedding=capture.recorded_embedding,
        run_config=_plane_g_run_config(),
        env_pins={"society_event_log_checksum": capture.result.event_log_checksum},
    )

    projected_floats: list[float] = []
    for line in bundle["decisions.jsonl"].splitlines():
        for envelope_json in json.loads(line)["decision"]["envelope_provenance"]:
            projected_floats.extend(_float_leaves(json.loads(envelope_json)))
    assert projected_floats
    for value in projected_floats:
        assert round(value, 6) == value, f"{value} escaped the 6-decimal rule"

    # Negative fixture 1: the raw record really does carry longer floats.
    raw_floats: list[float] = []
    for agent_id in sorted(capture.result.decisions):
        for record in capture.result.decisions[agent_id]:
            for envelope_json in record.envelope_provenance:
                raw_floats.extend(_float_leaves(json.loads(envelope_json)))
    assert any(round(value, 6) != value for value in raw_floats)
    naive = json.dumps(
        {
            "envelope_provenance": list(
                capture.result.decisions[sorted(capture.result.decisions)[0]][
                    0
                ].envelope_provenance
            )
        }
    )
    assert any(str(value) in naive for value in raw_floats if round(value, 6) != value)

    # Negative fixture 2: sub-quantum absorbed, supra-quantum not.
    sub_quantum = _shift_first_physical_float(capture.result, field=field, delta=4e-10)
    supra_quantum = _shift_first_physical_float(capture.result, field=field, delta=1e-3)

    def _decisions_text(result: SocietyRunResult) -> str:
        return society_plane_g_bundle(
            result,
            ledger=capture.ledger,
            recorded_embedding=capture.recorded_embedding,
            run_config=_plane_g_run_config(),
            env_pins={"society_event_log_checksum": "pin"},
        )["decisions.jsonl"]

    base_text = _decisions_text(capture.result)
    sub_text = _decisions_text(sub_quantum)
    supra_text = _decisions_text(supra_quantum)
    assert sub_text == base_text
    assert supra_text != base_text
    assert _event_log_checksum_of(sub_quantum) == _event_log_checksum_of(capture.result)
    assert _event_log_checksum_of(supra_quantum) != _event_log_checksum_of(
        capture.result
    )

    # The two replay-input side files round-trip through their own projections.
    assert (
        society_injected_ledger_from_jsonl(bundle["inbound_ledger.jsonl"])
        == capture.ledger
    )
    assert (
        society_embedding_record_from_jsonl(bundle["embedding_record.jsonl"])
        == capture.recorded_embedding
    )
    assert society_recorded_llm_from_jsonl(bundle["decisions.jsonl"]) == dict(
        capture.recorded_llm
    )


# --------------------------------------------------------------------------- #
# AC8 — the per-agent firing annotation is NOT a gate
# --------------------------------------------------------------------------- #


async def test_firing_annotation_is_non_gate(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``verdict`` is ``None``; ``eligible`` / ``witness`` are plain counts.

    The summary itself is the **unmodified**
    ``two_phase_live.two_phase_firing_summary`` applied per agent — this module
    contributes the per-agent dispatch and the honest framing, never a new
    statistic. firing ≠ detectability: nothing here claims a behaviour changed.
    """
    capture = await _capture_for_plane_g(
        make_agent_state, make_persona_spec, run_id="i6-ac8"
    )
    knob_on = await _replay_plane_g(
        capture, run_id="i6-ac8", two_phase_knob=TwoPhaseKnob()
    )
    knob_off = await _replay_plane_g(capture, run_id="i6-ac8")
    annotation = society_firing_annotation(
        knob_on=knob_on, knob_off=knob_off, recorded_llm=capture.recorded_llm
    )

    assert annotation["verdict"] is None
    assert annotation["hard_gate"] is False
    assert annotation["agent_ids"] == sorted(SOCIETY_LIVE_AGENT_IDS)
    assert isinstance(annotation["eligible_tick_count"], int)
    assert isinstance(annotation["witness_tick_count"], int)
    assert annotation["eligible_tick_count"] >= 0
    assert annotation["witness_tick_count"] >= 0
    for agent_id in annotation["agent_ids"]:
        per_agent = annotation["per_agent"][agent_id]
        assert per_agent["verdict"] is None
        assert per_agent["hard_gate"] is False
        assert per_agent["n_ticks"] == _PLANE_G_TICKS
        assert isinstance(per_agent["eligible_tick_count"], int)
        assert isinstance(per_agent["witness_tick_count"], int)
        # The committed capture genuinely ran knob-ON: the knob-on replay's
        # recomposed sampling reproduces the committed call sampling.
        assert per_agent["record_knob_on_pinned"] is True
        assert per_agent["checksums_match"] is True

    forbidden_substrings = (
        "effect",
        "diverg",
        "floor",
        "scor",
        "detect",
        "magnitude",
        "aha",
    )
    for key in _nested_keys(annotation):
        for banned in forbidden_substrings:
            assert banned not in key.lower(), f"{key} names a measurement claim"

    assert "firing != detectability" in annotation["note"]
    assert "NON-GATE" in annotation["note"]
