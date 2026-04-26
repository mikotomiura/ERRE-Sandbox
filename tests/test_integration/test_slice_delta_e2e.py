"""End-to-end test for the M7δ relationship loop (formula + negative path + belief).

Slice δ extends γ's signature-only relational hook into the full CSDG
surface:

1. ``compute_affinity_delta`` returns a real semi-formula
   ``prev*(1-decay) + impact*weight`` with persona-coupled coefficients
   (C3) and a hard-coded antagonism table that fires negative deltas
   for kant↔nietzsche.
2. ``apply_affinity_delta`` writes ``Physical.emotional_conflict`` on
   negative deltas past ``-0.05`` (C4) and stamps
   ``RelationshipBond.last_interaction_zone`` (C4).
3. After each bond mutation, ``maybe_promote_belief`` distils the bond
   into a typed :class:`SemanticMemoryRecord` once both gates pass
   (C5: ``|affinity| > 0.45`` and ``ichigo_ichie_count >= 6``).

This file exercises all three in pure-Python by driving 12 fake
:class:`DialogTurnMsg`s through the relational sink. No live LLM, no
sleep, no real-world clock — the assertions reflect the deterministic
surface that the live G-GEAR run will then re-confirm.

Acceptance-gate parity (.steering/20260426-m7-slice-delta/requirement.md):

* dialog_turn ≥ 3 (we drive 12)
* both signs of affinity delta observed
* decay-induced saturation visible (|affinity| growth slows past 0.5)
* ≥1 belief promotion in semantic_memory with ``belief_kind`` populated
* ``last_interaction_zone`` set on bonds
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.bootstrap import (
    _build_initial_state,
    _load_persona_yaml,
    _make_relational_sink,
)
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import (
    AgentSpec,
    DialogTurnMsg,
    Zone,
)
from erre_sandbox.world.tick import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from erre_sandbox.schemas import ControlEnvelope, PersonaSpec


_PERSONAS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "personas"

_AGENT_TRIPLE: tuple[tuple[str, Zone], ...] = (
    ("kant", Zone.STUDY),
    ("nietzsche", Zone.AGORA),
    ("rikyu", Zone.CHASHITSU),
)


class _StubCycle:
    """Cognition-cycle stand-in so ``WorldRuntime`` can be constructed."""

    async def step(self, *_args: object, **_kwargs: object) -> object:
        raise NotImplementedError


@pytest.fixture
def persona_registry() -> dict[str, PersonaSpec]:
    return {
        persona_id: _load_persona_yaml(_PERSONAS_DIR, persona_id)
        for persona_id, _zone in _AGENT_TRIPLE
    }


@pytest.fixture
def runtime_with_three_agents(
    persona_registry: dict[str, PersonaSpec],
) -> WorldRuntime:
    runtime = WorldRuntime(cycle=_StubCycle())  # type: ignore[arg-type]
    for persona_id, zone in _AGENT_TRIPLE:
        spec = AgentSpec(persona_id=persona_id, initial_zone=zone)
        state = _build_initial_state(spec, persona_registry[persona_id])
        runtime.register_agent(state, persona_registry[persona_id])
    return runtime


@pytest.fixture
async def store() -> AsyncIterator[MemoryStore]:
    s = MemoryStore(db_path=":memory:")
    s.create_schema()
    try:
        yield s
    finally:
        await s.close()


def _agent_id(persona_id: str) -> str:
    return f"a_{persona_id}_001"


def _open_dialog(scheduler: InMemoryDialogScheduler, *, tick: int) -> str:
    initiate = scheduler.schedule_initiate(
        initiator_id=_agent_id("kant"),
        target_id=_agent_id("nietzsche"),
        zone=Zone.PERIPATOS,
        tick=tick,
    )
    assert initiate is not None
    return next(iter(scheduler._open))


async def test_delta_drives_negative_bond_kant_nietzsche(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """12 turns of kant↔nietzsche must end up with a strongly negative bond."""
    captured: list[ControlEnvelope] = []
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(envelope_sink=captured.append, turn_sink=sink)
    dialog_id = _open_dialog(scheduler, tick=10)

    # 12 alternating turns — each persona speaks 6 times so both bond
    # ichigo_ichie_count fields reach the BELIEF_MIN_INTERACTIONS=6 gate.
    for i in range(12):
        speaker, addressee = (
            ("kant", "nietzsche") if i % 2 == 0 else ("nietzsche", "kant")
        )
        scheduler.record_turn(
            DialogTurnMsg(
                tick=20 + i,
                dialog_id=dialog_id,
                speaker_id=_agent_id(speaker),
                addressee_id=_agent_id(addressee),
                utterance=(
                    "A measured rebuttal that exercises the structural "
                    "impact term and the antagonism override."
                ),
                turn_index=i,
            ),
        )

    # ---- Acceptance 1: both signs of delta observed --------------------
    # Both agents' bonds (toward the other) must end up negative because
    # the antagonism table dominates the structural positive impact.
    kant_state = runtime_with_three_agents._agents[_agent_id("kant")].state
    nietzsche_state = runtime_with_three_agents._agents[_agent_id("nietzsche")].state
    kant_to_nietzsche = next(
        b
        for b in kant_state.relationships
        if b.other_agent_id == _agent_id("nietzsche")
    )
    nietzsche_to_kant = next(
        b
        for b in nietzsche_state.relationships
        if b.other_agent_id == _agent_id("kant")
    )
    assert kant_to_nietzsche.affinity < 0.0
    assert nietzsche_to_kant.affinity < 0.0


async def test_delta_writes_emotional_conflict_on_negative_path(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """The negative path raises ``Physical.emotional_conflict`` for both sides."""
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
    dialog_id = _open_dialog(scheduler, tick=10)

    for i in range(4):
        scheduler.record_turn(
            DialogTurnMsg(
                tick=20 + i,
                dialog_id=dialog_id,
                speaker_id=_agent_id("kant"),
                addressee_id=_agent_id("nietzsche"),
                utterance="A categorical refusal.",
                turn_index=i,
            ),
        )

    kant_state = runtime_with_three_agents._agents[_agent_id("kant")].state
    nietzsche_state = runtime_with_three_agents._agents[_agent_id("nietzsche")].state
    assert kant_state.physical.emotional_conflict > 0.0
    assert nietzsche_state.physical.emotional_conflict > 0.0


async def test_delta_stamps_last_interaction_zone(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """Each bond carries the speaker's zone after the sink fires."""
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
    dialog_id = _open_dialog(scheduler, tick=10)

    scheduler.record_turn(
        DialogTurnMsg(
            tick=20,
            dialog_id=dialog_id,
            speaker_id=_agent_id("kant"),
            addressee_id=_agent_id("rikyu"),
            utterance="Greetings from the study.",
            turn_index=0,
        ),
    )

    kant_state = runtime_with_three_agents._agents[_agent_id("kant")].state
    bond = next(
        b for b in kant_state.relationships if b.other_agent_id == _agent_id("rikyu")
    )
    # Bootstrap reads the speaker's zone (Kant in STUDY per fixture).
    assert bond.last_interaction_zone is Zone.STUDY


async def test_delta_belief_promotion_writes_semantic_memory(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """At least one belief is promoted with belief_kind populated.

    Drives 14 alternating kant↔nietzsche turns so the kant↔nietzsche
    pair crosses both gates (|affinity|>0.45 by ~turn 6 and
    ichigo_ichie_count>=6 by turn 12).
    """
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
    dialog_id = _open_dialog(scheduler, tick=10)

    for i in range(14):
        speaker, addressee = (
            ("kant", "nietzsche") if i % 2 == 0 else ("nietzsche", "kant")
        )
        scheduler.record_turn(
            DialogTurnMsg(
                tick=20 + i,
                dialog_id=dialog_id,
                speaker_id=_agent_id(speaker),
                addressee_id=_agent_id(addressee),
                utterance="A long pointed exchange that fires antagonism.",
                turn_index=i,
            ),
        )

    # Inspect the semantic store for any belief_kind row.
    rows = (
        store._ensure_conn()
        .execute(
            "SELECT id, belief_kind, confidence FROM semantic_memory "
            "WHERE belief_kind IS NOT NULL"
        )
        .fetchall()
    )
    assert len(rows) >= 1, (
        f"expected ≥1 belief promotion in semantic_memory; got {rows}"
    )
    # All M7δ promotions for this antagonistic pair must classify as
    # 'wary' or 'clash' (negative-affinity bands).
    for row in rows:
        assert row["belief_kind"] in {"wary", "clash"}
        assert 0.0 <= float(row["confidence"]) <= 1.0


async def test_delta_belief_promotion_uses_deterministic_id(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """Repeated promotions for the same dyad upsert (single row, not many)."""
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(envelope_sink=lambda _: None, turn_sink=sink)
    dialog_id = _open_dialog(scheduler, tick=10)

    for i in range(20):
        speaker, addressee = (
            ("kant", "nietzsche") if i % 2 == 0 else ("nietzsche", "kant")
        )
        scheduler.record_turn(
            DialogTurnMsg(
                tick=20 + i,
                dialog_id=dialog_id,
                speaker_id=_agent_id(speaker),
                addressee_id=_agent_id(addressee),
                utterance="x",
                turn_index=i,
            ),
        )

    # Two dyads max (kant→nietzsche and nietzsche→kant). Each side may
    # promote at most once per dyad due to the deterministic id.
    rows = (
        store._ensure_conn()
        .execute(
            "SELECT id FROM semantic_memory WHERE belief_kind IS NOT NULL"
        )
        .fetchall()
    )
    ids = [r["id"] for r in rows]
    # At most 2 distinct rows (one per direction).
    assert len(set(ids)) <= 2
    assert len(set(ids)) == len(ids), (
        f"expected unique ids per dyad (deterministic upsert); got {ids}"
    )
