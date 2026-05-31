"""M10-A E1: the belief-promotion sink generates the ``belief_variance`` substrate.

This is the behavioural half of E1 (the wiring half is
``tests/test_cli/test_eval_run_golden_belief_sink.py``). It proves the chain the
evaluation epoch now runs end-to-end:

    relational sink fires → beliefs promoted into the MemoryStore →
    ``list_semantic_beliefs`` returns >= 2 distinct belief classes →
    ``belief_variance`` flips from ``degenerate`` ("no belief records") to
    ``valid``.

The belief_classes are read from ``list_semantic_beliefs`` **after** the
promotions land (Codex C4b: the cognition tick that emits the trace reads the
store, so the final-tick trace reflects the run's promoted beliefs). The same
``belief_classes`` feeds the real ``layer1.belief_variance`` metric so the flip
is shown against the actual claim-boundary implementation, not a mock.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from erre_sandbox.bootstrap import _make_relational_sink
from erre_sandbox.evidence.individuation.layer1 import MetricContext, belief_variance
from erre_sandbox.evidence.individuation.policy import (
    TICK_AGGREGATE_SENTINEL,
    AggregationLevel,
    MetricStatus,
)
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import (
    AgentState,
    CognitiveHabit,
    DialogTurnMsg,
    ERREMode,
    ERREModeName,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    Position,
    Zone,
)
from erre_sandbox.world import ManualClock, WorldRuntime

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


class _NoopCycle:
    """Duck-typed CognitionCycle — never invoked (we drive the turn sink directly)."""

    async def step(
        self, *_args: object, **_kwargs: object
    ) -> object:  # pragma: no cover
        raise AssertionError("cycle must not run in this sink-level test")


def _rikyu_persona() -> PersonaSpec:
    return PersonaSpec(
        persona_id="rikyu",
        display_name="Rikyu",
        era="1522-1591",
        personality=PersonalityTraits(),
        cognitive_habits=[
            CognitiveHabit(
                description="seiza",
                source="x",
                flag=HabitFlag.FACT,
                mechanism="vagal",
            ),
        ],
        preferred_zones=[Zone.CHASHITSU],
    )


def _state(agent_id: str) -> AgentState:
    return AgentState(
        agent_id=agent_id,
        persona_id="rikyu",
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=Zone.CHASHITSU),
        erre=ERREMode(name=ERREModeName.DEEP_WORK, entered_at_tick=0),
    )


def _ctx() -> MetricContext:
    return MetricContext(
        run_id="run0",
        individual_id="a_rikyu_001",
        base_persona_id="rikyu",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=TICK_AGGREGATE_SENTINEL,
        source_epoch_phase="evaluation",
        source_individual_layer_enabled=True,
        source_filter_hash="test",
    )


def _saturate(runtime: WorldRuntime, *, focal: str, other: str, sign: float) -> None:
    """Push ``focal``'s bond toward ``other`` past the belief gate (|aff|, N>=6)."""
    for tick in range(8):
        runtime.apply_affinity_delta(
            agent_id=focal,
            other_agent_id=other,
            delta=sign * 0.3,
            tick=tick,
            zone=Zone.CHASHITSU,
        )


@pytest.mark.asyncio
async def test_relational_sink_promotes_two_classes_belief_variance_valid() -> None:
    memory = MemoryStore(db_path=":memory:")
    memory.create_schema()
    try:
        runtime = WorldRuntime(
            cycle=_NoopCycle(),  # type: ignore[arg-type]  # never invoked here
            clock=ManualClock(start=0.0),
        )
        persona = _rikyu_persona()
        for aid in ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003"):
            runtime.register_agent(_state(aid), persona)

        # a_rikyu_001 builds a strong positive bond to _002 and a strong negative
        # bond to _003 — two distinct belief classes for one individual.
        _saturate(runtime, focal="a_rikyu_001", other="a_rikyu_002", sign=1.0)
        _saturate(runtime, focal="a_rikyu_001", other="a_rikyu_003", sign=-1.0)

        # Baseline (pre-promotion): an empty belief set is the forensic
        # degenerate cell "no belief records".
        degenerate = belief_variance([], ctx=_ctx(), computed_at=_NOW)
        assert degenerate.status is MetricStatus.DEGENERATE

        sink = _make_relational_sink(
            runtime=runtime,
            memory=memory,
            persona_registry={"rikyu": persona},
        )
        # Fire one turn per dyad; the sink promotes a_rikyu_001's saturated bonds.
        sink(
            DialogTurnMsg(
                dialog_id="d1",
                speaker_id="a_rikyu_001",
                addressee_id="a_rikyu_002",
                utterance="the kettle hums quietly",
                turn_index=0,
                tick=8,
            )
        )
        sink(
            DialogTurnMsg(
                dialog_id="d2",
                speaker_id="a_rikyu_001",
                addressee_id="a_rikyu_003",
                utterance="the kettle hums quietly",
                turn_index=0,
                tick=9,
            )
        )

        beliefs = await memory.list_semantic_beliefs("a_rikyu_001")
        belief_classes = [b.belief_kind for b in beliefs if b.belief_kind is not None]
    finally:
        await memory.close()

    # The sink generated the substrate: >= 2 distinct belief classes.
    assert len(set(belief_classes)) >= 2, belief_classes

    # The same belief_classes (as the post-promotion trace would carry) flip the
    # real metric from degenerate to valid (Gini-Simpson in [0, 1)).
    valid = belief_variance(belief_classes, ctx=_ctx(), computed_at=_NOW)
    assert valid.status is MetricStatus.VALID
    assert valid.value is not None
    assert 0.0 < valid.value < 1.0
