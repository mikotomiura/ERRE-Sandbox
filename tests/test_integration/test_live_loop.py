"""Issue 003 (M13 live-loop-closure): closure composition root ``live_loop.py``.

Covers ``.steering/20260724-m13-live-loop-closure/design-final.md`` Issue
003's four Acceptance Criteria:

* AC1 — ``live_loop`` driven with ``two_phase_knob=None`` reproduces
  ``run_two_phase_capture(two_phase_knob=None, observation_factory=<same
  fixed observations>)`` byte-for-byte (organ drift pin).
* AC2 — one perturbation -> one cognition tick -> exactly one ``MoveMsg`` in
  ``runtime.drain_envelopes()`` (no double-send; HIGH-1) — plus a structural
  pin that this module's source never calls ``inject_envelope``.
* AC3 — inbound drain -> ``PerceptionEvent`` injection ->
  ``step_cognition_once`` completes end-to-end with no exception.
* AC4 — the gateway-serve stub and the driven loop are supervised inside one
  ``asyncio.TaskGroup`` on the SAME running event loop (MEDIUM-2).

Plus one Codex TASK-POST MED-2 fold-in (``decisions.md`` "TASK-POST
cross-review 採否"): a drained ``WorldPerturbationMsg`` whose
``target_agent_id`` does not match the driven agent is dropped before
injection and recorded onto ``result.rejected`` (DA-2 bounded verification)
-> :func:`test_target_agent_id_mismatch_dropped_not_injected`.

Ollama-free throughout — every test drives Ollama-free record-mode chat
clients (the same ``_MockInnerChat`` idiom ``test_two_phase_live.py``
establishes; duplicated locally per that module's own note that test files
are not a shared-code surface).

Scope guard (design-final.md §2/§7, binding). This is a **construction**
apparatus, **NOT a measurement line — verdict は holding**: no floor /
verdict / divergence / detectability / aha-proxy statistic is computed or
asserted here, only exact-match / boolean / structural checks.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff, live_loop
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.two_phase_live import run_two_phase_capture
from erre_sandbox.integration.inbound import (
    InboundSink,
    world_perturbation_to_perception,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import MoveMsg, WorldPerturbationMsg, Zone
from erre_sandbox.world import ManualClock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.inference.ollama_adapter import ChatResponse
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIVE_LOOP_SRC = (
    _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "live_loop.py"
)

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Ollama-free fixtures (mirrors test_two_phase_live.py's idiom, not shared)
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
    """Ollama-free inner chat that re-serves the golden plan every call."""

    def __init__(self) -> None:
        resp = handoff.golden_recorded_calls()[0].response
        assert resp is not None
        self._response = resp

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return self._response


def _record_llm() -> RecordReplayChatClient:
    return RecordReplayChatClient(inner=ThinkOffChatClient(_MockInnerChat()))


def _perturbation(
    *, agent_id: str, content: str, correlation_id: str = ""
) -> WorldPerturbationMsg:
    return WorldPerturbationMsg(
        tick=0,
        target_agent_id=agent_id,
        modality="sight",
        source_zone=Zone.STUDY,
        content=content,
        intensity=0.4,
        correlation_id=correlation_id,
    )


def _fixed_perturbations(*, agent_id: str, n_ticks: int) -> list[WorldPerturbationMsg]:
    """One perturbation per tick, content-tagged with its index (fidelity fixture)."""
    return [
        _perturbation(
            agent_id=agent_id,
            content=f"live-loop fidelity perturbation {i}",
            correlation_id=f"corr-{i}",
        )
        for i in range(n_ticks)
    ]


def _reference_observation_factory(
    perturbations: Sequence[WorldPerturbationMsg],
) -> Callable[[int], Sequence[Observation]]:
    """Build the SAME PerceptionEvent the driven loop would inject, via the same
    pure mapping (``world_perturbation_to_perception``) — guarantees byte-exact
    parity between the fidelity reference and the driven-loop path."""

    def factory(agent_tick: int) -> Sequence[Observation]:
        return [
            world_perturbation_to_perception(perturbations[agent_tick], tick=agent_tick)
        ]

    return factory


async def _drive_reference(
    *,
    run_id: str,
    agent_state: AgentState,
    persona: PersonaSpec,
    n_ticks: int,
    observation_factory: Callable[[int], Sequence[Observation]],
) -> Any:
    """Drive the untouched sibling ``run_two_phase_capture`` (the AC1 reference)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        return await run_two_phase_capture(
            run_id=run_id,
            store=store,
            embedding=embedding,
            llm=_record_llm(),
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=None,
            n_cognition_ticks=n_ticks,
            observation_factory=observation_factory,
        )
    finally:
        await embedding.close()
        await store.close()


async def _build_handle(
    *,
    run_id: str,
    agent_state: AgentState,
    persona: PersonaSpec,
    two_phase_knob: TwoPhaseKnob | None,
    store: MemoryStore,
    embedding: EmbeddingClient,
) -> live_loop.LiveLoopWorld:
    return live_loop.build_live_loop_world(
        run_id=run_id,
        store=store,
        embedding=embedding,
        llm=_record_llm(),
        agent_state=agent_state,
        persona=persona,
        retrieval_now=_FIXED_CLOCK,
        base_ts=_FIXED_CLOCK,
        two_phase_knob=two_phase_knob,
        clock=ManualClock(start=0.0),
    )


# --------------------------------------------------------------------------- #
# AC1 — knob=None fidelity, byte-identical against run_two_phase_capture
# --------------------------------------------------------------------------- #


async def test_knob_none_fidelity_byte_identical() -> None:
    """AC1: live_loop(knob=None) driven from a fixed inbound feed == the sibling
    driver fed the SAME observations via ``observation_factory``, byte-for-byte."""
    run_id = "live-loop-fidelity-test"
    agent_state = handoff.golden_agent_state()
    persona = handoff.golden_persona()
    n_ticks = 4
    perturbations = _fixed_perturbations(agent_id=agent_state.agent_id, n_ticks=n_ticks)

    ref = await _drive_reference(
        run_id=run_id,
        agent_state=agent_state,
        persona=persona,
        n_ticks=n_ticks,
        observation_factory=_reference_observation_factory(perturbations),
    )

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = await _build_handle(
            run_id=run_id,
            agent_state=agent_state,
            persona=persona,
            two_phase_knob=None,
            store=store,
            embedding=embedding,
        )
        sink = InboundSink()
        for p in perturbations:
            sink.push(p)
        # max_drain_per_tick=1: the sink is preloaded with all N perturbations
        # up front (push order == tick order), so draining exactly 1 per tick
        # keeps tick alignment identical to the reference's observation_factory.
        live_result = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=sink,
            n_cognition_ticks=n_ticks,
            max_drain_per_tick=1,
        )
    finally:
        await embedding.close()
        await store.close()

    assert live_result.checksum == ref.checksum
    assert handoff.decisions_to_jsonl(live_result.ecl.decisions) == (
        handoff.decisions_to_jsonl(ref.decisions)
    )
    assert live_result.ecl.rows == ref.rows


# --------------------------------------------------------------------------- #
# AC2 — single move envelope, no double-send (HIGH-1)
# --------------------------------------------------------------------------- #


async def test_single_move_broadcast_no_double_send() -> None:
    """AC2: 1 perturbation -> 1 tick -> exactly one MoveMsg in drain_envelopes()."""
    agent_state = handoff.golden_agent_state()
    persona = handoff.golden_persona()
    sink = InboundSink()
    sink.push(
        _perturbation(agent_id=agent_state.agent_id, content="a single gust of wind")
    )

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = await _build_handle(
            run_id="live-loop-single-move-test",
            agent_state=agent_state,
            persona=persona,
            two_phase_knob=TwoPhaseKnob(),
            store=store,
            embedding=embedding,
        )
        await live_loop.run_live_loop_capture(
            handle, inbound_sink=sink, n_cognition_ticks=1
        )
    finally:
        await embedding.close()
        await store.close()

    drained = handle.world.drain_envelopes()
    moves = [env for env in drained if isinstance(env, MoveMsg)]
    assert len(moves) == 1, f"expected exactly 1 MoveMsg, got {len(moves)}: {drained!r}"

    # Structural pin (HIGH-1): the closure root never re-injects outbound —
    # outbound stays single-owner (WorldRuntime._consume_result). Checks for
    # an actual CALL (`inject_envelope(`), not the bare identifier, since the
    # module's docstrings legitimately name the method by way of explanation.
    src = _LIVE_LOOP_SRC.read_text(encoding="utf-8")
    assert "inject_envelope(" not in src, (
        "live_loop.py must never call inject_envelope (HIGH-1: double-send)"
    )


# --------------------------------------------------------------------------- #
# AC3 — end-to-end fires with no exception
# --------------------------------------------------------------------------- #


async def test_driven_loop_end_to_end_fires() -> None:
    """AC3: inbound drain -> PerceptionEvent -> step_cognition_once, exit 0."""
    agent_state = handoff.golden_agent_state()
    persona = handoff.golden_persona()
    sink = InboundSink()
    sink.push(
        _perturbation(agent_id=agent_state.agent_id, content="footsteps on gravel")
    )

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = await _build_handle(
            run_id="live-loop-e2e-test",
            agent_state=agent_state,
            persona=persona,
            two_phase_knob=TwoPhaseKnob(),
            store=store,
            embedding=embedding,
        )
        result = await live_loop.run_live_loop_capture(
            handle, inbound_sink=sink, n_cognition_ticks=3
        )
    finally:
        await embedding.close()
        await store.close()

    assert len(result.ecl.decisions) == 3
    assert result.checksum
    # Exactly one perturbation was ever injected (only tick 0 had one queued).
    assert len(result.injected) == 1
    assert result.injected[0].agent_tick == 0


# --------------------------------------------------------------------------- #
# Codex TASK-POST MED-2 — target_agent_id bounded verification (DA-2)
# --------------------------------------------------------------------------- #


async def test_target_agent_id_mismatch_dropped_not_injected() -> None:
    """A drained WorldPerturbationMsg aimed at some OTHER agent must be
    dropped before injection — never turned into a PerceptionEvent on this
    (single-agent v0) drive's pending queue — and recorded onto
    ``result.rejected`` as a plain ledger entry, not silently discarded.
    The drive still completes the tick normally (bounded verification, not a
    fatal error)."""
    agent_state = handoff.golden_agent_state()
    persona = handoff.golden_persona()
    sink = InboundSink()
    sink.push(
        _perturbation(agent_id="some-other-agent-entirely", content="not for you")
    )

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = await _build_handle(
            run_id="live-loop-target-mismatch-test",
            agent_state=agent_state,
            persona=persona,
            two_phase_knob=None,
            store=store,
            embedding=embedding,
        )
        result = await live_loop.run_live_loop_capture(
            handle, inbound_sink=sink, n_cognition_ticks=1
        )
    finally:
        await embedding.close()
        await store.close()

    # Never injected — no PerceptionEvent was built for the mismatched
    # target, no InjectedPerturbation ledger entry either.
    assert result.injected == ()
    # ...but not silently dropped — recorded so a caller can observe it.
    assert len(result.rejected) == 1
    assert result.rejected[0].target_agent_id == "some-other-agent-entirely"
    assert result.rejected[0].content == "not for you"
    # The tick itself still completed normally — a mismatched perturbation
    # is bounded-verified and dropped, not treated as a fatal error.
    assert len(result.ecl.decisions) == 1


# --------------------------------------------------------------------------- #
# AC4 — same-event-loop TaskGroup supervise (MEDIUM-2)
# --------------------------------------------------------------------------- #


async def test_same_event_loop_taskgroup_supervise() -> None:
    """AC4: gateway-serve stub + driven loop run on the SAME running event loop.

    Both tasks are created via ``tg.create_task`` inside one
    ``async with asyncio.TaskGroup()`` block, so ``serve_task.get_loop() is
    driven_task.get_loop()`` is trivially true by ``TaskGroup``'s own
    contract — a single loop is the only outcome that construction can ever
    produce. This test is therefore a **regression pin**, not a live
    discriminating check: it exists to catch a future edit that accidentally
    offloads either task to a second event loop or a background thread
    (``asyncio.new_event_loop()`` / ``threading.Thread`` / ``run_in_executor``)
    — a change that WOULD make this assertion fail — rather than to prove
    anything ``TaskGroup`` doesn't already guarantee by construction.
    """
    outer_loop = asyncio.get_running_loop()
    seen: list[tuple[asyncio.AbstractEventLoop, asyncio.AbstractEventLoop]] = []

    async def stub_gateway_serve() -> None:
        await asyncio.Event().wait()  # blocks until the supervisor cancels it

    agent_state = handoff.golden_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = await _build_handle(
            run_id="live-loop-supervise-test",
            agent_state=agent_state,
            persona=persona,
            two_phase_knob=None,
            store=store,
            embedding=embedding,
        )

        def _record_loops(
            serve_task: asyncio.Task[None], driven_task: asyncio.Task[None]
        ) -> None:
            seen.append((serve_task.get_loop(), driven_task.get_loop()))

        result = await live_loop.supervise_live_loop(
            handle=handle,
            inbound_sink=InboundSink(),
            gateway_serve=stub_gateway_serve,
            n_cognition_ticks=0,
            on_tasks_scheduled=_record_loops,
        )
    finally:
        await embedding.close()
        await store.close()

    assert len(seen) == 1
    serve_loop, driven_loop = seen[0]
    assert serve_loop is outer_loop
    assert driven_loop is outer_loop
    assert serve_loop is driven_loop
    # n_cognition_ticks=0 -> the driven loop never runs a tick.
    assert result.ecl.decisions == ()
    assert result.injected == ()
