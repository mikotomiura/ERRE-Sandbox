"""Tests for the M7ζ-3 separation force in :class:`WorldRuntime`.

When two agents end up within either persona's ``separation_radius_m`` on
the XZ plane, ``_apply_separation_force`` nudges them apart by
``_SEP_PUSH_M`` (0.4 m) per physics tick. The push must

* actually move the pair apart even from perfect collapse (``d == 0``),
* leave pairs beyond the radius untouched,
* preserve the unit-vector direction between the two positions, and
* stay well inside the 5 m proximity threshold so the dialog-scheduler
  ``ProximityEvent`` enter/leave crossings keep firing as the pair
  gradually spreads.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.world import ManualClock, WorldRuntime
from erre_sandbox.world.tick import _PROXIMITY_THRESHOLD_M, _SEP_PUSH_M

if TYPE_CHECKING:
    from collections.abc import Callable


def test_separation_pushes_apart_from_collapse(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 10.0, "z": 10.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="nietzsche",
            position={"x": 10.0, "z": 10.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )

    runtime._apply_separation_force()
    pa = runtime._agents["a"].state.position
    pb = runtime._agents["b"].state.position
    distance = math.hypot(pa.x - pb.x, pa.z - pb.z)
    # Both agents push by _SEP_PUSH_M in opposite directions → pair gap
    # is at least 2 × the push distance after one tick.
    assert distance >= 2 * _SEP_PUSH_M


def test_separation_preserves_unit_vector_direction(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="nietzsche",
            position={"x": 1.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )

    runtime._apply_separation_force()
    pa = runtime._agents["a"].state.position
    pb = runtime._agents["b"].state.position
    # a is at -X relative to b → pushed further -X by _SEP_PUSH_M.
    # b is at +X relative to a → pushed further +X by _SEP_PUSH_M.
    assert pa.x == pytest.approx(-_SEP_PUSH_M)
    assert pb.x == pytest.approx(1.0 + _SEP_PUSH_M)
    assert pa.z == 0.0
    assert pb.z == 0.0


def test_separation_skips_pairs_outside_radius(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),  # default separation_radius_m = 1.5
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="nietzsche",
            position={"x": 4.5, "z": 0.0},  # outside both 1.5 m radii
        ),
        make_persona_spec(persona_id="nietzsche"),
    )

    runtime._apply_separation_force()
    assert runtime._agents["a"].state.position.x == 0.0
    assert runtime._agents["b"].state.position.x == 4.5


def test_separation_uses_max_of_pair_radii(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # rikyu's tight 1.2 m bubble must NOT prevent kant's wider 1.5 m bubble
    # from pushing them apart when distance == 1.3 m (inside kant's radius
    # but outside rikyu's).
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(behavior_profile={"separation_radius_m": 1.5}),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="rikyu",
            position={"x": 1.3, "z": 0.0},
        ),
        make_persona_spec(
            persona_id="rikyu",
            behavior_profile={"separation_radius_m": 1.2},
        ),
    )

    runtime._apply_separation_force()
    pa = runtime._agents["a"].state.position
    pb = runtime._agents["b"].state.position
    distance = math.hypot(pa.x - pb.x, pa.z - pb.z)
    # 1.3 m + 2 × 0.4 m push = 2.1 m
    assert distance == pytest.approx(1.3 + 2 * _SEP_PUSH_M)


def test_separation_skips_zero_radius_pair(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # Both personas opt out of separation (radius = 0).
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(behavior_profile={"separation_radius_m": 0.0}),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="nietzsche",
            position={"x": 0.0, "z": 0.0},
        ),
        make_persona_spec(
            persona_id="nietzsche",
            behavior_profile={"separation_radius_m": 0.0},
        ),
    )

    runtime._apply_separation_force()
    assert runtime._agents["a"].state.position.x == 0.0
    assert runtime._agents["b"].state.position.x == 0.0


def test_separation_stays_inside_proximity_threshold(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
) -> None:
    runtime = WorldRuntime(cycle=object(), clock=ManualClock())  # type: ignore[arg-type]
    # Start at distance 1.0 m, well inside both bubbles.
    runtime.register_agent(
        make_agent_state(agent_id="a", position={"x": 0.0, "z": 0.0}),
        make_persona_spec(),
    )
    runtime.register_agent(
        make_agent_state(
            agent_id="b",
            persona_id="nietzsche",
            position={"x": 1.0, "z": 0.0},
        ),
        make_persona_spec(persona_id="nietzsche"),
    )
    # Many ticks of separation must never push the pair past the 5 m
    # proximity threshold (radius is only 1.5 m, push 0.4 m, so the
    # equilibrium is reached at ≥ radius and stays << threshold).
    for _ in range(20):
        runtime._apply_separation_force()
    pa = runtime._agents["a"].state.position
    pb = runtime._agents["b"].state.position
    distance = math.hypot(pa.x - pb.x, pa.z - pb.z)
    assert distance < _PROXIMITY_THRESHOLD_M
