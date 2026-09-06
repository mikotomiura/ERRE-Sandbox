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
import inspect
import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import society, society_live_loop
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.society import SocietyRunResult, run_society_loop
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
)
from erre_sandbox.integration.embodied.society_live_loop import (
    COGNITION_ENVELOPE_KINDS,
    DIALOG_ENVELOPE_KINDS,
    EXCLUDED_ENVELOPE_KINDS,
    LIVE_ROOT_MODULE,
    RECORD_MODE_WALL_CLOCK,
    SocietyBroadcastLedger,
    SocietyInboundRouter,
    SocietyInjectedPerturbation,
    build_society_live_world,
    run_society_live_loop,
    society_live_gateway_lifespan_serve,
    society_live_loop_perturbation_plan,
    society_wiring_reachability_summary,
    spy_inject_envelope_callers,
    supervise_society_live_loop,
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
