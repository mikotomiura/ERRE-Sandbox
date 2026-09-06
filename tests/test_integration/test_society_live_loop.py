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

import asyncio
import inspect
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import society
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.society import SocietyRunResult, run_society_loop
from erre_sandbox.integration.embodied.society_live import (
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
)
from erre_sandbox.integration.embodied.society_live_loop import (
    RECORD_MODE_WALL_CLOCK,
    SocietyInboundRouter,
    society_live_loop_perturbation_plan,
)
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import (
    AgentState,
    PerceptionEvent,
    PersonaSpec,
    WorldPerturbationMsg,
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
