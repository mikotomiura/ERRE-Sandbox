"""Tests for the Slice β persona-preferred-zone bias helper.

The helper :func:`erre_sandbox.cognition.cycle._bias_target_zone` nudges the
LLM's ``destination_zone`` choice toward the persona's ``preferred_zones``
list with a per-tick probability, so three agents with disjoint preferred
lists produce three different spatial trajectories under the same LLM.

Testing focuses on the deterministic branches — empty preferred list,
already-preferred destination, ``None`` destination, probability-did-not-fire,
probability-did-fire — with a seeded :class:`random.Random` so the
branch-taken outcome is reproducible without a real LLM.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from erre_sandbox.cognition.cycle import _bias_target_zone
from erre_sandbox.cognition.parse import LLMPlan
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import PersonaSpec


_AGENT_ID = "a_rikyu_001"


def _plan(destination: Zone | None) -> LLMPlan:
    return LLMPlan(thought="t", destination_zone=destination)


def test_empty_preferred_zones_is_no_op(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    persona = make_persona_spec(preferred_zones=[])
    plan = _plan(Zone.AGORA)
    result = _bias_target_zone(plan, persona, Random(0), 1.0, agent_id=_AGENT_ID)
    assert result is plan


def test_none_destination_is_no_op(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """``destination_zone is None`` respects the LLM's choice to stay put.

    Open Question #1 in the Slice β plan — injection under ``None`` may be
    added later based on live observability; for now the first-cut helper
    must preserve the signal.
    """
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(None)
    result = _bias_target_zone(plan, persona, Random(0), 1.0, agent_id=_AGENT_ID)
    assert result is plan


def test_destination_already_preferred_is_no_op(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.CHASHITSU)
    result = _bias_target_zone(plan, persona, Random(0), 1.0, agent_id=_AGENT_ID)
    assert result is plan


def test_probability_zero_never_resamples(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.PERIPATOS)
    result = _bias_target_zone(plan, persona, Random(0), 0.0, agent_id=_AGENT_ID)
    assert result.destination_zone is Zone.PERIPATOS


def test_probability_one_always_resamples_into_preferred(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.PERIPATOS)
    result = _bias_target_zone(plan, persona, Random(0), 1.0, agent_id=_AGENT_ID)
    assert result.destination_zone in {Zone.CHASHITSU, Zone.GARDEN}
    # The plan is frozen, so resample returns a new instance — assert the
    # non-destination fields round-trip to catch accidental dropped data.
    assert result.thought == plan.thought


def test_resample_is_deterministic_under_seeded_rng(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Same seed + inputs must pick the same replacement zone across runs."""
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden", "study"])
    plan = _plan(Zone.PERIPATOS)
    first = _bias_target_zone(plan, persona, Random(42), 1.0, agent_id=_AGENT_ID)
    second = _bias_target_zone(plan, persona, Random(42), 1.0, agent_id=_AGENT_ID)
    assert first.destination_zone is second.destination_zone


# ---------------------------------------------------------------------------
# M8 baseline-quality-metric: optional bias_sink capture path
# ---------------------------------------------------------------------------


def test_bias_sink_is_called_on_fire(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """When the probability fires, the sink must receive one BiasFiredEvent."""
    from erre_sandbox.cognition.cycle import BiasFiredEvent

    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.PERIPATOS)
    captured: list[BiasFiredEvent] = []
    _bias_target_zone(
        plan,
        persona,
        Random(0),
        1.0,
        agent_id=_AGENT_ID,
        tick=42,
        bias_sink=captured.append,
    )
    assert len(captured) == 1
    event = captured[0]
    assert event.tick == 42
    assert event.agent_id == _AGENT_ID
    assert event.from_zone == "peripatos"
    assert event.to_zone in {"chashitsu", "garden"}
    assert event.bias_p == 1.0


def test_bias_sink_is_not_called_on_no_op(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """No firing -> no sink call (probability=0 branch)."""
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.PERIPATOS)
    captured: list[object] = []
    _bias_target_zone(
        plan,
        persona,
        Random(0),
        0.0,
        agent_id=_AGENT_ID,
        tick=42,
        bias_sink=captured.append,
    )
    assert captured == []


def test_bias_sink_exception_does_not_break_resample(
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Sink exceptions are swallowed so the live cycle survives broken sinks."""
    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
    plan = _plan(Zone.PERIPATOS)

    def _broken_sink(_event: object) -> None:
        msg = "persistence layer is down"
        raise RuntimeError(msg)

    result = _bias_target_zone(
        plan,
        persona,
        Random(0),
        1.0,
        agent_id=_AGENT_ID,
        tick=1,
        bias_sink=_broken_sink,
    )
    # Resample still succeeded despite the sink error.
    assert result.destination_zone in {Zone.CHASHITSU, Zone.GARDEN}
