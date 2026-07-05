"""ECL v0 world-seam tests (M13, Issue 003).

Two seams meet the ``world`` layer for the Embodied Cognition Loop v0:

* the **embodiment trace sink** — a house-style injected ``Callable | None`` fired
  after ``step_kinematics`` on each physics tick, in deterministic
  ``sorted(agent_id)`` order, with the 30 Hz ``physics_tick_index`` kept distinct
  from the agent cognition tick (design §論点3, Codex MEDIUM-2/3); and
* the **history-dependent MoveMsg** the ECL cycle emits — a *concrete* coordinate
  (not a zone tag), so the world's zone-only → ``default_spawn`` resolution branch
  never fires and the agent transits continuously.

Tests:

* **AC2** ``test_ecl_v0_embodied_move_continuous`` — the ECL MoveMsg target is a
  ``locate_zone``-consistent coordinate (``default_spawn`` branch non-firing) and
  ``step_kinematics`` walks the agent across > 1 tick.
* **AC3** ``test_ecl_v0_move_msg_history_dependent`` — the cycle-resolved target ≠
  ``default_spawn(zone)``.
* **AC6** ``test_ecl_trace_sink_noop_and_axes`` — ``None`` sink emits nothing and
  leaves the physics path unchanged; a wired sink fires in ``sorted(agent_id)``
  order with a ``physics_tick_index`` axis separate from the cognition tick.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from random import Random
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.embodiment import EclRecordMode
from erre_sandbox.contracts import geometry
from erre_sandbox.inference.ollama_adapter import OllamaChatClient
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import (
    AgentState,
    MemoryEntry,
    MemoryKind,
    MoveMsg,
    PerceptionEvent,
    SpatialContext,
    Zone,
)
from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics

if TYPE_CHECKING:
    from collections.abc import Callable

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)
_PLAN_JSON = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)


# --------------------------------------------------------------------------- #
# Self-contained mock inference clients (test_world has no cognition conftest)
# --------------------------------------------------------------------------- #


def _chat_client(content: str) -> OllamaChatClient:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(
            httpx.codes.OK,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
            },
        )

    client = httpx.AsyncClient(
        base_url=OllamaChatClient.DEFAULT_ENDPOINT,
        transport=httpx.MockTransport(handler),
    )
    return OllamaChatClient(client=client)


def _embed_client() -> EmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vec = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    client = httpx.AsyncClient(
        base_url=EmbeddingClient.DEFAULT_ENDPOINT,
        transport=httpx.MockTransport(handler),
    )
    return EmbeddingClient(client=client)


async def _run_ecl_move(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., Any],
) -> tuple[MoveMsg, AgentState, Any]:
    """Run one ECL record-mode cognition tick and return its MoveMsg.

    Seeds a located self-memory offset from the PERIPATOS centroid so the resolver's
    strength-weighted centroid — hence the emitted MoveMsg target — is a concrete,
    history-dependent coordinate distinct from ``default_spawn(peripatos)``.
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    emb_retr = _embed_client()
    emb_cycle = _embed_client()
    llm = _chat_client(_PLAN_JSON)
    retriever = Retriever(store, emb_retr)
    try:
        px, _py, pz = geometry.ZONE_CENTERS[Zone.PERIPATOS]
        await store.add(
            MemoryEntry(
                id="seed",
                agent_id="a_kant_001",
                kind=MemoryKind.EPISODIC,
                content="walked here before",
                importance=0.8,
                created_at=_FIXED,
                location=SpatialContext(
                    zone=Zone.PERIPATOS, x=px + 6.0, y=0.0, z=pz - 6.0
                ),
            ),
            embedding=[0.01] * EmbeddingClient.DEFAULT_DIM,
        )
        cycle = CognitionCycle(
            retriever=retriever,
            store=store,
            embedding=emb_cycle,
            llm=llm,
            rng=Random(0),
            ecl_mode=EclRecordMode(run_id="r0", retrieval_now=_FIXED, base_ts=_FIXED),
        )
        agent = make_agent_state()
        persona = make_persona_spec()
        result = await cycle.step(
            agent,
            persona,
            [
                PerceptionEvent(
                    tick=1,
                    agent_id="a_kant_001",
                    modality="sight",
                    source_zone=Zone.STUDY,
                    content="library shelves",
                    intensity=0.4,
                )
            ],
        )
    finally:
        await emb_retr.close()
        await emb_cycle.close()
        await llm.close()
        await store.close()
    move = next(e for e in result.envelopes if isinstance(e, MoveMsg))
    return move, agent, result


# --------------------------------------------------------------------------- #
# AC3 — history-dependent move (cycle-resolved target ≠ default_spawn)
# --------------------------------------------------------------------------- #


async def test_ecl_v0_move_msg_history_dependent(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., Any],
) -> None:
    move, _agent, result = await _run_ecl_move(make_agent_state, make_persona_spec)
    spawn = geometry.default_spawn(Zone.PERIPATOS)
    assert move.target.zone is Zone.PERIPATOS
    assert (move.target.x, move.target.z) != (spawn.x, spawn.z)
    assert result.ecl_destination is not None
    assert result.ecl_destination.resolved_from == "memory_centroid"


# --------------------------------------------------------------------------- #
# AC2 — concrete target drives continuous transit (default_spawn non-firing)
# --------------------------------------------------------------------------- #


async def test_ecl_v0_embodied_move_continuous(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., Any],
) -> None:
    move, agent, _result = await _run_ecl_move(make_agent_state, make_persona_spec)
    tgt = move.target
    # Concrete coordinate: locate_zone agrees with the tag, so the world's zone-only
    # → default_spawn resolution branch (tick.py) would NOT fire on this MoveMsg.
    assert geometry.locate_zone(tgt.x, tgt.y, tgt.z) is tgt.zone

    # Continuous transit at 30 Hz: the agent does not snap in one tick and is still
    # moving on tick 2, so the walk spans > 1 physics tick.
    dt = 1.0 / 30.0
    kin = Kinematics(position=agent.position, speed_mps=move.speed)
    apply_move_command(kin, move)
    assert move.speed > 0.0

    start = kin.position
    pos1, _z1 = step_kinematics(kin, dt)
    assert kin.destination is not None  # target not reached in one tick
    moved1 = math.hypot(pos1.x - start.x, pos1.z - start.z)
    assert moved1 > 0.0

    pos2, _z2 = step_kinematics(kin, dt)
    moved2 = math.hypot(pos2.x - pos1.x, pos2.z - pos1.z)
    assert moved2 > 0.0  # still in transit on the second tick


# --------------------------------------------------------------------------- #
# AC6 — trace sink no-op + physics/cognition axis separation + sorted order
# --------------------------------------------------------------------------- #


def _register(
    runtime: WorldRuntime,
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., Any],
    *,
    agent_id: str,
    zone: Zone,
) -> None:
    cx, cy, cz = geometry.ZONE_CENTERS[zone]
    state = make_agent_state(
        agent_id=agent_id,
        position={"x": cx, "y": cy, "z": cz, "zone": zone.value},
    )
    runtime.register_agent(state, make_persona_spec())


async def test_ecl_trace_sink_noop_and_axes(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., Any],
    mock_cycle: Any,
    manual_clock: ManualClock,
) -> None:
    # --- sink=None: nothing emitted, physics path unchanged ---
    quiet = WorldRuntime(cycle=mock_cycle, clock=manual_clock, physics_hz=30.0)
    _register(quiet, make_agent_state, make_persona_spec, agent_id="a", zone=Zone.STUDY)
    await quiet._on_physics_tick()
    # (no sink wired ⇒ no capture list to compare; exercising the branch proves the
    #  no-op path does not raise and leaves the tick loop intact.)

    # --- sink wired: capture (agent_id, physics_tick_index, x,y,z, yaw,pitch, zone) ---
    captured: list[tuple[Any, ...]] = []

    def sink(
        agent_id: str,
        physics_tick_index: int,
        x: float,
        y: float,
        z: float,
        yaw: float,
        pitch: float,
        zone: Zone,
    ) -> None:
        captured.append((agent_id, physics_tick_index, x, y, z, yaw, pitch, zone))

    runtime = WorldRuntime(
        cycle=mock_cycle,
        clock=ManualClock(start=0.0),
        physics_hz=30.0,
        ecl_trace_sink=sink,
    )
    # Register out of sorted order (b before a) in far-apart zones so the separation
    # nudge never fires and the sink's sorted(agent_id) order is unambiguous.
    _register(
        runtime, make_agent_state, make_persona_spec, agent_id="b", zone=Zone.GARDEN
    )
    _register(
        runtime, make_agent_state, make_persona_spec, agent_id="a", zone=Zone.STUDY
    )

    physics_ticks = 3
    for _ in range(physics_ticks):
        await runtime._on_physics_tick()

    # Two agents × three ticks = six rows, grouped by an incrementing physics index.
    assert len(captured) == physics_ticks * 2
    indices = [row[1] for row in captured]
    assert indices == [0, 0, 1, 1, 2, 2]
    # Within every physics tick the sink fires in sorted(agent_id) order (Codex M3).
    for tick_idx in range(physics_ticks):
        pair = [row[0] for row in captured if row[1] == tick_idx]
        assert pair == ["a", "b"]

    # Axis separation: the 30 Hz physics index advanced 0→2 while each agent's
    # cognition tick stayed put (no cognition tick fired) — the two are distinct.
    assert max(indices) == physics_ticks - 1
    assert all(runtime._agents[aid].state.tick == 0 for aid in ("a", "b"))
