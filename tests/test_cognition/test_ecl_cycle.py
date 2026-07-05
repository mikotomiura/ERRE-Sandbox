"""ECL v0 live-seam tests for :class:`CognitionCycle` (M13, Issue 003).

Issue 003 wires the Embodied Cognition Loop v0 into the live cognition hot path.
The **load-bearing** contract is that ``ecl_mode=None`` (the default, and every
live / flag-off tick) leaves the cycle byte-identical to pre-ECL behaviour; only
an injected :class:`~erre_sandbox.cognition.embodiment.EclRecordMode` turns on the
deterministic record seam. These tests pin:

* **AC1** ``test_ecl_flag_off_byte_invariant`` — flag-off ``_build_envelopes`` output
  is byte-identical; the ECL branch changes *only* the MoveMsg target when wired.
* **AC4** ``test_ecl_deterministic_injection`` — record mode injects a deterministic
  memory id / tick-derived ``created_at`` / formation ``location`` (Codex HIGH-2),
  runs the ECL retrieval with ``k_world=0`` + ``mark_recalled=False``, and pins the
  emitted envelope ``sent_at`` to the fixed clock.
* **AC5** ``test_ecl_reflection_skipped`` — the second (reflection) LLM call is
  disabled in record mode (Codex HIGH-1), so Plane 2 records only the action LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from random import Random
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.embodiment import K_ECL, EclDestination, EclRecordMode
from erre_sandbox.cognition.parse import LLMPlan
from erre_sandbox.schemas import (
    AgentState,
    MoveMsg,
    Position,
    SpatialContext,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.memory.retrieval import RankedMemory
    from erre_sandbox.schemas import PerceptionEvent, PersonaSpec

_FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed record-mode clock (retrieval + envelope ``sent_at`` pin)."""

_BASE_TS = datetime(2026, 1, 1, tzinfo=UTC)
"""Deterministic base for tick-derived memory ``created_at``."""

_FULL_PLAN = LLMPlan(
    thought="deliberate",
    utterance="今日も散歩へ",
    destination_zone=Zone.PERIPATOS,
    animation="walk",
    salient="the peripatos path",
    decision="take the daily walk",
    next_intent="return to study after",
)
"""A plan exercising every envelope kind (agent_update/speech/move/animation/trace)."""


def _build_cycle(
    *,
    retriever: Retriever,
    store: MemoryStore,
    embedding: EmbeddingClient,
    llm: OllamaChatClient,
    ecl_mode: EclRecordMode | None = None,
    reflector: Any | None = None,
) -> CognitionCycle:
    return CognitionCycle(
        retriever=retriever,
        store=store,
        embedding=embedding,
        llm=llm,
        rng=Random(0),
        ecl_mode=ecl_mode,
        reflector=reflector,
    )


def _canonical(envelopes: list[Any]) -> list[dict[str, Any]]:
    """Envelope dicts with the wall-clock ``sent_at`` stripped for byte comparison."""
    out: list[dict[str, Any]] = []
    for env in envelopes:
        dumped = env.model_dump(mode="json")
        dumped.pop("sent_at", None)
        out.append(dumped)
    return out


class _SpyRetriever:
    """Wraps a real retriever, recording the kwargs each ``retrieve`` call saw."""

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner
        self.calls: list[dict[str, object]] = []

    async def retrieve(
        self,
        agent_id: str,
        query: str,
        *,
        k_agent: int = 8,
        k_world: int = 3,
        current_location: object | None = None,
        mark_recalled: bool = True,
    ) -> list[RankedMemory]:
        self.calls.append(
            {"k_agent": k_agent, "k_world": k_world, "mark_recalled": mark_recalled}
        )
        return await self._inner.retrieve(
            agent_id,
            query,
            k_agent=k_agent,
            k_world=k_world,
            current_location=current_location,
            mark_recalled=mark_recalled,
        )


class _SpyReflector:
    """Duck-typed reflector recording every ``maybe_reflect`` invocation."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def maybe_reflect(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _record_mode() -> EclRecordMode:
    return EclRecordMode(run_id="r0", retrieval_now=_FIXED_NOW, base_ts=_BASE_TS)


# --------------------------------------------------------------------------- #
# AC1 — flag-off byte invariant
# --------------------------------------------------------------------------- #


async def test_ecl_flag_off_byte_invariant(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    persona = make_persona_spec()
    # ``_build_envelopes`` consumes the post-tick state; a plain factory state is
    # sufficient (it does no I/O).
    new_state = make_agent_state(tick=1)
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
        )
        flag_off = cycle._build_envelopes(new_state, _FULL_PLAN, persona=persona)
        # The same call with an ECL destination injected (what the record-mode seam
        # passes) must differ from flag-off in EXACTLY the move target.
        ecl_dest = EclDestination(
            target=Position(x=3.0, y=0.0, z=4.0, zone=Zone.PERIPATOS),
            resolved_from="memory_centroid",
            centroid=(3.0, 4.0),
            provenance=("m0",),
            jitter=(0.0, 0.0),
            pre_clamp=(3.0, 4.0),
            post_clamp=(3.0, 4.0),
            clamp_fired=False,
        )
        flag_on = cycle._build_envelopes(
            new_state, _FULL_PLAN, persona=persona, ecl_destination=ecl_dest
        )
    finally:
        await embedding.close()
        await llm.close()

    # Every envelope kind is present in the frozen order.
    assert [e.kind for e in flag_off] == [
        "agent_update",
        "speech",
        "move",
        "animation",
        "reasoning_trace",
    ]

    # Flag-off MoveMsg target is byte-exactly the pre-ECL zone-only formula.
    off_move = next(e for e in flag_off if isinstance(e, MoveMsg))
    expected_target = new_state.position.model_copy(update={"zone": Zone.PERIPATOS})
    assert off_move.target == expected_target

    # Byte-invariant: flag-off vs flag-on differ ONLY in the move target. Strip the
    # target and the two canonical envelope lists are identical — the ECL seam
    # touches nothing else on the hot path.
    off_c = _canonical(flag_off)
    on_c = _canonical(flag_on)
    move_idx = next(i for i, e in enumerate(flag_off) if isinstance(e, MoveMsg))
    assert off_c[move_idx]["target"] != on_c[move_idx]["target"]
    off_c[move_idx].pop("target")
    on_c[move_idx].pop("target")
    assert off_c == on_c

    # And the flag-on target is exactly the resolver's — the only injected change.
    on_move = next(e for e in flag_on if isinstance(e, MoveMsg))
    assert on_move.target == ecl_dest.target


# --------------------------------------------------------------------------- #
# AC4 — deterministic injection (id / ts / location / retrieval kwargs / sent_at)
# --------------------------------------------------------------------------- #


async def test_ecl_deterministic_injection(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    agent = make_agent_state()  # tick 0, agent a_kant_001, study @ (0,0,0)
    persona = make_persona_spec()
    spy = _SpyRetriever(cognition_retriever)
    embedding = make_embedding_client()
    llm = make_chat_client()  # DEFAULT_PLAN → destination_zone=peripatos
    try:
        cycle = _build_cycle(
            retriever=spy,  # type: ignore[arg-type]
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            ecl_mode=_record_mode(),
        )
        result = await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()

    # One observation → one deterministic episodic memory.
    assert result.new_memory_ids == [f"ecl-{agent.agent_id}-{agent.tick:04d}"]
    stored = await cognition_store.get_by_id(result.new_memory_ids[0])
    assert stored is not None
    # Tick-derived created_at and current-position formation location (Codex HIGH-2).
    assert stored.created_at == _BASE_TS
    assert stored.location == SpatialContext(
        zone=agent.position.zone,
        x=agent.position.x,
        y=agent.position.y,
        z=agent.position.z,
    )

    # The ECL forage retrieval used the binding kwargs: k_agent=K_ECL, k_world=0
    # (self memory only), mark_recalled=False (no recall_count side effect). The
    # prompt-feeding retrieval keeps its defaults, so we assert the ECL call exists.
    assert {"k_agent": K_ECL, "k_world": 0, "mark_recalled": False} in spy.calls

    # Every emitted envelope's sent_at is pinned to the record-mode clock (Plane 1).
    assert result.envelopes  # sanity: the move plan emitted envelopes
    assert all(e.sent_at == _FIXED_NOW for e in result.envelopes)

    # The move-decision provenance is surfaced for the I4 harness.
    assert result.ecl_destination is not None


# --------------------------------------------------------------------------- #
# AC5 — reflection LLM disabled in record mode
# --------------------------------------------------------------------------- #


async def test_ecl_reflection_skipped(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    agent = make_agent_state()
    persona = make_persona_spec()

    # Record mode: the reflector must never be consulted (Codex HIGH-1).
    spy_on = _SpyReflector()
    embedding = make_embedding_client()
    llm = make_chat_client()
    try:
        cycle = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            ecl_mode=_record_mode(),
            reflector=spy_on,
        )
        await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    assert spy_on.calls == []

    # Control: with ecl_mode off the reflector IS consulted every tick, proving the
    # spy is wired and the skip is the record-mode branch (not a dead reflector).
    spy_off = _SpyReflector()
    embedding2 = make_embedding_client()
    llm2 = make_chat_client()
    try:
        cycle_off = _build_cycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding2,
            llm=llm2,
            reflector=spy_off,
        )
        await cycle_off.step(make_agent_state(), persona, [perception_event])
    finally:
        await embedding2.close()
        await llm2.close()
    assert len(spy_off.calls) == 1
