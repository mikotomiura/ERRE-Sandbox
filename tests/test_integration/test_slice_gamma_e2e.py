"""End-to-end test for the M7γ relational loop (sink + bond + trace decoration).

Slice γ wires three things in sequence:

1. ``InMemoryDialogScheduler.record_turn`` invokes the relational sink
   built by ``bootstrap._make_relational_sink``.
2. The sink inserts a ``MemoryKind.RELATIONAL`` row into
   :class:`MemoryStore` and applies a bidirectional ``apply_affinity_delta``
   on :class:`WorldRuntime`'s :class:`RelationshipBond` table.
3. ``cognition.cycle._decision_with_affinity`` reads the resulting bond
   when assembling :class:`ReasoningTrace.decision`, so the LLM-emitted
   rationale always trails an ``affinity=±0.NN with <other>`` hint when
   the agent has spoken to anyone.

Live G-GEAR acceptance asserts the same surface; this test pins the
relationship in pure-Python so a regression in any of the three hops
breaks CI before it reaches a long live run. No persona prompt is
exercised — the constant ``+0.02`` delta from ``compute_affinity_delta``
deterministically marches both bonds toward saturation, which is exactly
what the integration contract requires for γ.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# The relational sink lives behind a leading underscore in bootstrap.py
# (it is a composition-root helper, not a public API). The γ acceptance
# test reaches in deliberately so a refactor that loses the sink is
# detected by CI.
from erre_sandbox.bootstrap import (
    _build_initial_state,
    _load_persona_yaml,
    _make_relational_sink,
)
from erre_sandbox.cognition.cycle import _decision_with_affinity
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import (
    AgentSpec,
    DialogTurnMsg,
    MemoryKind,
    Zone,
)
from erre_sandbox.world.tick import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from erre_sandbox.schemas import ControlEnvelope, PersonaSpec


_PERSONAS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "personas"

# Three personas + zones chosen to exercise both halves of the M7γ
# observability surface: kant in study (deep_work), nietzsche in agora
# (peripatetic), rikyu in chashitsu (chashitsu mode). Each agent is
# the speaker on at least one turn so all three end up with at least
# one outbound RELATIONAL memory.
_AGENT_TRIPLE: tuple[tuple[str, Zone], ...] = (
    ("kant", Zone.STUDY),
    ("nietzsche", Zone.AGORA),
    ("rikyu", Zone.CHASHITSU),
)


class _StubCycle:
    """Cognition-cycle stand-in so ``WorldRuntime`` can be constructed.

    The runtime is exercised solely for ``register_agent`` /
    ``apply_affinity_delta`` in this test; ``run`` is never awaited so
    the cycle's ``step`` is intentionally a hard error if reached.
    """

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
    """Mirror ``bootstrap._build_initial_state``'s ``a_<persona>_001`` rule."""
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


async def test_three_agent_relational_loop(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """3-agent fixture, ≥3 relational rows, every decision carries ``affinity``."""
    captured: list[ControlEnvelope] = []
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(
        envelope_sink=captured.append,
        turn_sink=sink,
    )
    dialog_id = _open_dialog(scheduler, tick=10)

    # Three turns rotating through every (speaker, addressee) pair so that
    # each persona ends up with bonds toward both peers.
    rotations = [
        ("kant", "nietzsche", "Pflicht ist nicht Neigung."),
        ("nietzsche", "rikyu", "Tanze, nicht meditiere."),
        ("rikyu", "kant", "一期一会、ただ一服を。"),
    ]
    for i, (speaker, addressee, utterance) in enumerate(rotations):
        scheduler.record_turn(
            DialogTurnMsg(
                tick=20 + i,
                dialog_id=dialog_id,
                speaker_id=_agent_id(speaker),
                addressee_id=_agent_id(addressee),
                utterance=utterance,
                turn_index=i,
            ),
        )

    # ---- Assertion 1 — relational_memory has ≥3 rows (one per turn). -----
    relational_rows = []
    for persona_id, _zone in _AGENT_TRIPLE:
        relational_rows.extend(
            await store.list_by_agent(
                _agent_id(persona_id),
                MemoryKind.RELATIONAL,
                limit=10,
            ),
        )
    assert len(relational_rows) >= 3, (
        f"Expected ≥3 relational_memory rows, got {len(relational_rows)}; "
        "relational sink wiring may have regressed."
    )
    # Every row must record both sides of the dialog (speaker as agent_id,
    # addressee tagged in the entry's ``tags`` list).
    addressee_tags = {
        tag
        for entry in relational_rows
        for tag in entry.tags
        if tag.startswith("addressee:")
    }
    assert len(addressee_tags) >= 2, (
        "Expected at least two distinct addressees in relational memory tags; "
        f"got {addressee_tags}"
    )

    # ---- Assertion 2 — every agent has bonds with both other personas. ---
    for persona_id, _zone in _AGENT_TRIPLE:
        agent_id = _agent_id(persona_id)
        rt = runtime_with_three_agents._agents[agent_id]
        bonds = rt.state.relationships
        partners = {bond.other_agent_id for bond in bonds}
        # Each persona spoke once and was addressed once → exactly two partners.
        expected_partners = {
            _agent_id(other_id)
            for other_id, _zone2 in _AGENT_TRIPLE
            if other_id != persona_id
        }
        assert partners == expected_partners, (
            f"{agent_id} bonds {partners} != expected {expected_partners}"
        )
        for bond in bonds:
            # Slice δ semi-formula: delta is non-zero (positive for
            # non-antagonistic pairings, negative for kant↔nietzsche via
            # the _TRAIT_ANTAGONISM table). Either sign is valid; only
            # zero (γ-era constant defeat) would indicate the formula
            # silently regressed. ichigo_ichie_count must be exactly 1
            # because each agent participated in exactly one turn.
            assert bond.affinity != pytest.approx(0.0), (
                f"{agent_id} bond with {bond.other_agent_id} has zero "
                f"affinity — semi-formula did not fire."
            )
            assert bond.ichigo_ichie_count == 1
            assert bond.last_interaction_tick is not None

    # ---- Assertion 3 — ReasoningTrace.decision suffix carries "affinity". -
    for persona_id, _zone in _AGENT_TRIPLE:
        agent_id = _agent_id(persona_id)
        rt = runtime_with_three_agents._agents[agent_id]
        decorated = _decision_with_affinity("placeholder rationale", rt.state)
        assert decorated is not None
        assert "affinity" in decorated, (
            f"_decision_with_affinity dropped the affinity hint for {agent_id}; "
            f"got {decorated!r}"
        )
        # Even when the LLM offers no rationale, the hint must stand alone
        # so the γ wire-level assertion still passes.
        bare = _decision_with_affinity(None, rt.state)
        assert bare is not None
        assert "affinity" in bare


async def test_relational_sink_skips_unknown_speaker(
    runtime_with_three_agents: WorldRuntime,
    store: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> None:
    """A turn from an unregistered speaker must no-op rather than crash.

    Mirrors ``bootstrap._make_relational_sink``'s defence: live runs may
    race a (future) deregistration, so the sink logs and returns rather
    than raising. The relational table must remain empty in that case so
    downstream evidence aggregations don't double-count phantom turns.
    """
    captured: list[ControlEnvelope] = []
    sink = _make_relational_sink(
        runtime=runtime_with_three_agents,
        memory=store,
        persona_registry=persona_registry,
    )
    scheduler = InMemoryDialogScheduler(
        envelope_sink=captured.append,
        turn_sink=sink,
    )
    dialog_id = _open_dialog(scheduler, tick=10)

    scheduler.record_turn(
        DialogTurnMsg(
            tick=12,
            dialog_id=dialog_id,
            speaker_id="a_ghost_001",  # not registered anywhere
            addressee_id=_agent_id("kant"),
            utterance="...",
            turn_index=0,
        ),
    )

    rows = await store.list_by_agent(
        "a_ghost_001",
        MemoryKind.RELATIONAL,
        limit=10,
    )
    assert rows == []
    kant_runtime = runtime_with_three_agents._agents[_agent_id("kant")]
    assert kant_runtime.state.relationships == []
