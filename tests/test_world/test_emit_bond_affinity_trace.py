"""``_emit_bond_affinity_trace`` forwards the bond list or no-ops (ADR section 3.3).

Carrier A: the flag-on per-(agent, tick) bond sink reads
``res.agent_state.relationships`` and passes it straight to the eval-side closure, so
``world`` imports no ``evidence``. Flag-off (sink ``None``) must be a no-op so the
DuckDB stays byte-identical.
"""

from __future__ import annotations

from typing import Any

from erre_sandbox.cognition import CycleResult
from erre_sandbox.schemas import RelationshipBond, Zone
from erre_sandbox.world import ManualClock, WorldRuntime


def _with_bonds(state: Any, bonds: list[RelationshipBond]) -> Any:
    return state.model_copy(update={"relationships": bonds})


class TestEmitBondAffinityTrace:
    """The flag-on bond-affinity sink hook in ``_consume_result`` (carrier A)."""

    def test_emit_forwards_agent_id_relationships_and_tick(
        self,
        manual_clock: ManualClock,
        mock_cycle: Any,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """flag-on: the sink receives (agent_id, relationships, tick)."""
        captured: list[tuple[str, Any, int]] = []
        runtime = WorldRuntime(
            cycle=mock_cycle,  # type: ignore[arg-type]
            clock=manual_clock,
            bond_affinity_trace_sink=lambda aid, bonds, t: captured.append(
                (aid, bonds, t)
            ),
        )
        runtime.register_agent(
            make_agent_state(agent_id="a_rikyu_001", persona_id="rikyu"),
            make_persona_spec(persona_id="rikyu"),
        )
        rt = runtime._agents["a_rikyu_001"]
        bonds = [
            RelationshipBond(
                other_agent_id="a_kant_001",
                affinity=-0.44,
                ichigo_ichie_count=7,
                last_interaction_tick=rt.state.tick,
                last_interaction_zone=Zone.CHASHITSU,
            )
        ]
        res = CycleResult(agent_state=_with_bonds(rt.state, bonds))

        runtime._emit_bond_affinity_trace(rt, res)

        assert len(captured) == 1
        agent_id, relationships, tick = captured[0]
        assert agent_id == "a_rikyu_001"
        assert tick == rt.state.tick
        assert relationships[0].other_agent_id == "a_kant_001"
        assert relationships[0].affinity == -0.44

    def test_emit_noops_without_sink(
        self,
        manual_clock: ManualClock,
        mock_cycle: Any,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """flag-off (sink None): no error and no call — the byte-invariant path."""
        runtime = WorldRuntime(cycle=mock_cycle, clock=manual_clock)  # type: ignore[arg-type]
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        res = CycleResult(agent_state=rt.state)
        # Sink unset -> no-op (no exception, nothing emitted).
        runtime._emit_bond_affinity_trace(rt, res)

    def test_emit_forwards_empty_relationships(
        self,
        manual_clock: ManualClock,
        mock_cycle: Any,
        make_agent_state: Any,
        make_persona_spec: Any,
    ) -> None:
        """An agent with no bonds still calls the sink with an empty list (per-tick)."""
        captured: list[tuple[str, Any, int]] = []
        runtime = WorldRuntime(
            cycle=mock_cycle,  # type: ignore[arg-type]
            clock=manual_clock,
            bond_affinity_trace_sink=lambda aid, bonds, t: captured.append(
                (aid, bonds, t)
            ),
        )
        runtime.register_agent(make_agent_state(), make_persona_spec())
        rt = runtime._agents[runtime.agent_ids[0]]
        res = CycleResult(agent_state=_with_bonds(rt.state, []))
        runtime._emit_bond_affinity_trace(rt, res)
        assert len(captured) == 1
        assert captured[0][1] == []
