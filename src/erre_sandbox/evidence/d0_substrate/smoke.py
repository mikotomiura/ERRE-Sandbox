"""D0b-runtime veto smoke (design-final.md §3, DA-SUB1-3 physics-locus).

Drives the **real** :func:`erre_sandbox.world.physics.step_kinematics` (this
architecture's authoritative physics; Godot is a WebSocket render client
with no G-GEAR-native binary) over a fixed-seed short episode and checks
what a pure offline synthetic trace (:mod:`~erre_sandbox.evidence.
d0_substrate.stub`) cannot: (i) physics/tick-coupling monotonicity and
gap-freeness, (ii) affordance-event firing order determinism against the
action stream, (iii) ``Position`` wire round-trip byte fidelity.

**DA-D0S-5 (implementation clarification, not a design reopening)**: this
module deliberately does **not** import ``erre_sandbox.world.tick`` for its
``ManualClock`` / ``WorldRuntime``, even though design-final.md §3 names
"``world/tick.py`` + ``ManualClock``". ``world/tick.py`` transitively
imports ``erre_sandbox.cognition.{relational,world_model}`` (verified:
``world/`` -> ``cognition/`` is the legitimate dependency direction for the
*production* world layer, ``docs/repository-structure.md`` §4), which would
make this ``evidence``-layer package depend on ``cognition`` at import time —
violating the ADR's own "evidence -> schemas/memory/world の USE-only、
cognition 非import" constraint (design-final.md, prompt, ``decisions.md``
DA-SUB1-3). Both constraints come from the same ADR; resolving the tension
in favour of the binding USE-only rule while still using the *real* physics
function (the literal, checkable part of "Python tick-loop + real
step_kinematics") preserves the ADR's intent without violating its own
import discipline. This module instead implements a minimal deterministic
tick scheduler (:class:`SmokeClock`) with the same "advance in fixed steps,
no wall-clock" semantics as ``world.tick.ManualClock``, driving the same
:func:`~erre_sandbox.world.physics.step_kinematics` /
:class:`~erre_sandbox.world.physics.Kinematics` the production runtime uses,
plus a local re-implementation of the affordance-firing check (mirroring
``world.tick.WorldRuntime._fire_affordance_events``'s crossing-only
semantics) over the real :data:`~...constants.ZONE_PROPS` mirror.

Wire contract (Codex MEDIUM-4): ``Position`` / ``MoveMsg`` /
``ZoneTransitionEvent`` get a **runtime round-trip** (constructed from live
tick-loop state, JSON round-tripped); ``AgentUpdateMsg`` gets a
**schema-only** round-trip (it is a cognition-side emission in production,
not physics-tick-native, so this module never claims to exercise its live
emission path). A failure downgrades ``STRUCTURAL_READY`` to
``INCONCLUSIVE_STRUCTURAL`` and the ladder estimand is not computed for
:data:`SmokeResult.passed` ``== False`` (design-final.md §3).

``STRUCTURAL_READY`` reached via this smoke is **G-GEAR runtime-ready**,
*not* Godot render-ready (D0b-render / cross-machine coupling is deferred,
design-final.md §3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.stub import draw_start_terminal
from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    ERREMode,
    ERREModeName,
    MoveMsg,
    Position,
    Zone,
    ZoneTransitionEvent,
)
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics
from erre_sandbox.world.zones import locate_zone

_TICK_DELTA_TOL_S: float = 1e-9
"""Numerical tolerance for the fixed-``dt`` monotonicity/gap-freeness check."""

D0B_SEED: int = 0
"""Fixed smoke-episode seed (design-final.md §6 handoff: seed pinned)."""

D0B_TICK_HZ: float = 30.0
"""Physics tick rate, pinned equal to
``erre_sandbox.world.tick.WorldRuntime.DEFAULT_PHYSICS_HZ`` (the real
production tick rate this smoke exercises)."""

D0B_EPISODE_TICKS: int = 90
"""Fixed episode length (3 seconds at 30 Hz): long enough to cross at least
one zone boundary from any start/destination pair drawn by
:func:`erre_sandbox.evidence.d0_substrate.stub.draw_start_terminal`."""

_AFFORDANCE_RADIUS_M = _c.AFFORDANCE_RADIUS_M


class SmokeClock:
    """Minimal deterministic tick scheduler (mirrors ``ManualClock`` semantics).

    No wall-clock, no ``asyncio`` waiters — this smoke drives
    :func:`~erre_sandbox.world.physics.step_kinematics` synchronously tick by
    tick, which is all the monotonicity/gap-freeness/firing-order checks
    need. See the module docstring (DA-D0S-5) for why this does not import
    the real ``erre_sandbox.world.tick.ManualClock``.
    """

    def __init__(self, dt_seconds: float) -> None:
        self.dt_seconds = dt_seconds
        self._now = 0.0

    def advance(self) -> float:
        self._now += self.dt_seconds
        return self._now

    @property
    def now(self) -> float:
        return self._now


@dataclass(frozen=True, slots=True)
class TickRecord:
    tick_index: int
    wall_clock: float
    position: Position
    zone_transition: ZoneTransitionEvent | None
    affordance_prop_ids: tuple[str, ...]


@dataclass(frozen=True)
class SmokeResult:
    """D0b-runtime verdict: pass/fail + the forensic trail."""

    passed: bool
    monotone_gap_free: bool
    affordance_order_deterministic: bool
    position_round_trip_ok: bool
    move_msg_round_trip_ok: bool
    zone_transition_round_trip_ok: bool
    agent_update_schema_round_trip_ok: bool
    n_ticks: int
    n_zone_transitions: int
    n_affordance_events: int
    reasons: tuple[str, ...]


def _affordance_hits(position: Position, seen: dict[str, float]) -> tuple[str, ...]:
    """Crossing-only affordance detection (mirrors ``_fire_affordance_events``)."""
    hits: list[str] = []
    for props in _c.ZONE_PROPS.values():
        for prop in props:
            distance = math.hypot(position.x - prop.x, position.z - prop.z)
            prev = seen.get(prop.prop_id)
            seen[prop.prop_id] = distance
            if prev is None:
                continue
            if prev >= _AFFORDANCE_RADIUS_M and distance < _AFFORDANCE_RADIUS_M:
                hits.append(prop.prop_id)
    return tuple(hits)


def _run_episode(seed: int) -> list[TickRecord]:
    start_zone, terminal_zone = _draw_smoke_endpoints(seed)
    sx, sy, sz = _c.ZONE_CENTERS[start_zone]
    tx, ty, tz = _c.ZONE_CENTERS[terminal_zone]
    start = Position(x=sx, y=sy, z=sz, zone=start_zone)
    dest = Position(x=tx, y=ty, z=tz, zone=terminal_zone)

    kin = Kinematics(position=start)
    apply_move_command(
        kin, MoveMsg(tick=0, agent_id="d0-smoke", target=dest, speed=1.3)
    )

    clock = SmokeClock(1.0 / D0B_TICK_HZ)
    seen: dict[str, float] = {}
    records: list[TickRecord] = []
    prev_zone = start.zone
    for i in range(D0B_EPISODE_TICKS):
        now = clock.advance()
        new_pos, zone_changed = step_kinematics(kin, clock.dt_seconds)
        transition: ZoneTransitionEvent | None = None
        if zone_changed is not None:
            transition = ZoneTransitionEvent(
                tick=i, agent_id="d0-smoke", from_zone=prev_zone, to_zone=zone_changed
            )
            prev_zone = zone_changed
        hits = _affordance_hits(new_pos, seen)
        records.append(
            TickRecord(
                tick_index=i,
                wall_clock=now,
                position=new_pos,
                zone_transition=transition,
                affordance_prop_ids=hits,
            ),
        )
    return records


def _draw_smoke_endpoints(seed: int) -> tuple[Zone, Zone]:
    return draw_start_terminal(seed)


def _check_monotone_gap_free(records: list[TickRecord]) -> bool:
    if not records:
        return False
    expected = 1.0 / D0B_TICK_HZ
    prev = 0.0
    for r in records:
        delta = r.wall_clock - prev
        if delta <= 0.0 or abs(delta - expected) > _TICK_DELTA_TOL_S:
            return False
        prev = r.wall_clock
    return True


def _check_affordance_order_deterministic(seed: int) -> bool:
    first = _run_episode(seed)
    second = _run_episode(seed)
    first_order = [(r.tick_index, r.affordance_prop_ids) for r in first]
    second_order = [(r.tick_index, r.affordance_prop_ids) for r in second]
    return first_order == second_order


def _check_position_round_trip(records: list[TickRecord]) -> bool:
    """``Position`` JSON round-trip byte fidelity + coordinate-convention check.

    ``step_kinematics`` (mid-flight *and* snapped branches alike) always
    sets ``Position.zone`` via ``locate_zone(x, y, z)``, so every record's
    wire-carried zone must agree with a fresh ``locate_zone`` re-derivation
    (Codex MEDIUM-4 coordinate-convention byte fidelity).
    """
    for r in records:
        restored = Position.model_validate_json(r.position.model_dump_json())
        if restored != r.position:
            return False
        if locate_zone(restored.x, restored.y, restored.z) != restored.zone:
            return False
    return True


def _check_move_msg_round_trip(records: list[TickRecord]) -> bool:
    if not records:
        return False
    msg = MoveMsg(tick=0, agent_id="d0-smoke", target=records[-1].position, speed=1.3)
    restored = MoveMsg.model_validate_json(msg.model_dump_json())
    return restored == msg


def _check_zone_transition_round_trip(records: list[TickRecord]) -> bool:
    transitions = [r.zone_transition for r in records if r.zone_transition is not None]
    for t in transitions:
        restored = ZoneTransitionEvent.model_validate_json(t.model_dump_json())
        if restored != t:
            return False
    return True


def _check_agent_update_schema_round_trip(records: list[TickRecord]) -> bool:
    """Schema-only round-trip check (Codex MEDIUM-4).

    ``AgentUpdateMsg`` is a cognition-side emission in production, not
    physics-tick-native, so this smoke never claims to drive its live
    emission — only that the schema itself round-trips byte-faithfully with
    tick-loop-sourced field values.
    """
    if not records:
        return False
    last = records[-1]
    state = AgentState(
        agent_id="d0-smoke",
        persona_id="d0-smoke-persona",
        tick=last.tick_index,
        position=last.position,
        erre=ERREMode(name=ERREModeName.SHALLOW, entered_at_tick=last.tick_index),
    )
    msg = AgentUpdateMsg(tick=last.tick_index, agent_state=state)
    restored = AgentUpdateMsg.model_validate_json(msg.model_dump_json())
    return restored == msg


def run_smoke(seed: int = D0B_SEED) -> SmokeResult:
    """Run the D0b-runtime veto smoke once (deterministic, fixed seed).

    Returns :class:`SmokeResult`; ``passed=False`` must downgrade
    ``STRUCTURAL_READY`` to ``INCONCLUSIVE_STRUCTURAL`` at the verdict layer
    (design-final.md §3/§6) without computing a ladder estimand.
    """
    records = _run_episode(seed)
    monotone_ok = _check_monotone_gap_free(records)
    affordance_ok = _check_affordance_order_deterministic(seed)
    position_ok = _check_position_round_trip(records)
    move_ok = _check_move_msg_round_trip(records)
    zone_ok = _check_zone_transition_round_trip(records)
    agent_update_ok = _check_agent_update_schema_round_trip(records)

    reasons: list[str] = []
    if not monotone_ok:
        reasons.append("physics tick delta not monotone/gap-free")
    if not affordance_ok:
        reasons.append("affordance-event firing order not deterministic across re-runs")
    if not position_ok:
        reasons.append("Position wire round-trip mismatch")
    if not move_ok:
        reasons.append("MoveMsg wire round-trip mismatch")
    if not zone_ok:
        reasons.append("ZoneTransitionEvent wire round-trip mismatch")
    if not agent_update_ok:
        reasons.append("AgentUpdateMsg schema-only round-trip mismatch")

    passed = (
        monotone_ok
        and affordance_ok
        and position_ok
        and move_ok
        and zone_ok
        and agent_update_ok
    )
    return SmokeResult(
        passed=passed,
        monotone_gap_free=monotone_ok,
        affordance_order_deterministic=affordance_ok,
        position_round_trip_ok=position_ok,
        move_msg_round_trip_ok=move_ok,
        zone_transition_round_trip_ok=zone_ok,
        agent_update_schema_round_trip_ok=agent_update_ok,
        n_ticks=len(records),
        n_zone_transitions=sum(1 for r in records if r.zone_transition is not None),
        n_affordance_events=sum(len(r.affordance_prop_ids) for r in records),
        reasons=tuple(reasons),
    )


__all__ = [
    "D0B_EPISODE_TICKS",
    "D0B_SEED",
    "D0B_TICK_HZ",
    "SmokeClock",
    "SmokeResult",
    "TickRecord",
    "run_smoke",
]
