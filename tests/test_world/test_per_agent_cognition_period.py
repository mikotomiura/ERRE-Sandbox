"""M7ζ-3: phase-wheel cognition cadence + post-MoveMsg dwell.

The global cognition heap event still fires at ``_cognition_period`` (10 s),
but :meth:`WorldRuntime._on_cognition_tick` now selects only agents whose
``next_cognition_due`` has elapsed and which are not in seiza dwell. This
file verifies that two distinct mechanisms produce visibly different step
counts in a 60 s window:

* **Phase wheel** — three personas with distinct ``cognition_period_s``
  step at distinct cadences. The 10 s global grid rounds finer periods up
  to grid multiples, so 14 s and 18 s tie at the 20 s effective rate while
  7 s rides every global tick. Live divergence between Kant (14 s) and
  Rikyū (18 s) comes from the second mechanism below.
* **Dwell** — a persona with ``dwell_time_s > 0`` is suppressed for that
  duration after firing a MoveMsg. Rikyū's 90 s dwell after one move
  dampens the next several global ticks, which is what gives Rikyū the
  visible "long seiza" cadence in live observation.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import CycleResult
from erre_sandbox.schemas import AgentUpdateMsg, MoveMsg, Position, Zone

if TYPE_CHECKING:
    from .conftest import MockCycleCall, RuntimeHarness


async def _pump(times: int = 10) -> None:
    for _ in range(times):
        await asyncio.sleep(0)


async def test_phase_wheel_diverges_per_persona_period(
    world_harness: RuntimeHarness,
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    world_harness.runtime.register_agent(
        make_agent_state(agent_id="a_kant"),
        make_persona_spec(behavior_profile={"cognition_period_s": 14.0}),
    )
    world_harness.runtime.register_agent(
        make_agent_state(agent_id="a_niet"),
        make_persona_spec(behavior_profile={"cognition_period_s": 7.0}),
    )
    world_harness.runtime.register_agent(
        make_agent_state(agent_id="a_rikyu"),
        make_persona_spec(behavior_profile={"cognition_period_s": 18.0}),
    )

    task = asyncio.create_task(world_harness.runtime.run())
    await _pump()
    # Six global cognition ticks at 10 s cadence (60 s wall-clock).
    for _ in range(6):
        world_harness.clock.advance(10.0)
        await _pump(800)

    counts = Counter(c.agent_state.agent_id for c in world_harness.cycle.calls)

    # Nietzsche (7 s, finer than the 10 s global grid) must outpace both
    # peers — this is the headline "burst" cadence.
    assert counts["a_niet"] > counts["a_kant"]
    assert counts["a_niet"] > counts["a_rikyu"]
    # Kant (14 s) and Rikyū (18 s) both round up to 20 s on the 10 s grid,
    # so they tie at this resolution; the dwell test below differentiates
    # them. Both must still register at least one step in the window.
    assert counts["a_kant"] >= 1
    assert counts["a_rikyu"] >= 1

    world_harness.runtime.stop()
    world_harness.clock.advance(1.0)
    await _pump()
    await task


async def test_dwell_suppresses_cognition_after_move(
    world_harness: RuntimeHarness,
    make_agent_state: Any,
    make_persona_spec: Any,
) -> None:
    async def respond_with_move(call: MockCycleCall) -> object:
        return CycleResult(
            agent_state=call.agent_state,
            envelopes=[
                AgentUpdateMsg(
                    tick=call.agent_state.tick,
                    agent_state=call.agent_state,
                ),
                MoveMsg(
                    tick=call.agent_state.tick,
                    agent_id=call.agent_state.agent_id,
                    target=Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY),
                    speed=1.0,
                ),
            ],
        )

    world_harness.cycle.set_responder(respond_with_move)
    world_harness.runtime.register_agent(
        make_agent_state(agent_id="a_rikyu"),
        make_persona_spec(
            behavior_profile={
                "cognition_period_s": 10.0,
                "dwell_time_s": 90.0,
            },
        ),
    )

    task = asyncio.create_task(world_harness.runtime.run())
    await _pump()
    # Six global cognition ticks at 10 s cadence (60 s wall-clock). The
    # first one fires the MoveMsg and arms a 90 s dwell, so the remaining
    # five must be suppressed.
    for _ in range(6):
        world_harness.clock.advance(10.0)
        await _pump(800)

    assert len(world_harness.cycle.calls) == 1

    world_harness.runtime.stop()
    world_harness.clock.advance(1.0)
    await _pump()
    await task
