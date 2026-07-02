"""D0a blind deterministic 3D-state trace generator (design-final.md §3).

Superset of :func:`erre_sandbox.evidence.spdm.scenario.uniform_walk`: the
zone-level backbone is the exact same uniform random walk over the mirrored
:data:`~erre_sandbox.evidence.d0_substrate.constants.ADJACENCY` graph, with a
**within-zone continuous micro-walk layer** added on top — seeded
independently per arm, seed-as-only-freedom (no stickiness / dwell / bias
knob a designer could turn).

Two arms (``"A"`` / ``"B"``) are generated per seed from a **shared start**
(drawn by the same blind RNG, mirroring SPDM's terminal-location-match
nuisance control) with **independent** walk/micro-walk RNG substreams, so
their trajectories — and hence formation locations — diverge purely from the
blind walk, never from a designer-assigned content→location binding. Each
trace row is ``(tick_index, seed, zone, x, y, z, yaw, pitch, action_id,
affordance_ids)`` (design-final.md §3): ``action_id`` is the index (into
``ADJACENCY[zone]``) the blind walk chose leaving that tick's zone;
``affordance_ids`` is the set of :data:`~...constants.ZONE_PROPS` prop ids
within :data:`~...constants.AFFORDANCE_RADIUS_M` of the tick's raw ``(x, z)``
— the R3 rung's raw observation stream (**not** the R2 perception-cone
affordance set, which :mod:`ladder` computes separately with
:data:`~...constants.CONE_APERTURE_DEG` / :data:`~...constants.CONE_RANGE_M`).

:func:`quantize_trace` is the anti-ES-1-collapse gate's paired-fixture
generator (design-final.md §2 #5, Codex HIGH-1): given a **rung name** it
collapses exactly that rung's richer-than-R0 field back to a deterministic
zone-coarse value (R1: position → zone centroid; R2: yaw → zone-default
heading; R3: action → zone-default null action) while leaving the walk
backbone (``zone`` / ``tick_index`` / the other fields) untouched — the same
seed, the same trajectory, only the richer-slice-under-test flattened.
``affordance_ids`` is recomputed from the (possibly quantized) position so it
stays internally consistent.

Determinism: every RNG substream is named
``f"d0-seed-{seed}-{arm}-{stream}"`` (:class:`random.Random`, never the
global RNG), so a re-run with the same seed bank reproduces byte-identical
traces — asserted via :func:`trace_checksum` in
``tests/test_evidence/test_d0_stub.py``.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

RungName = Literal["R1", "R2", "R3"]


@dataclass(frozen=True, slots=True)
class TraceRow:
    """One tick of one arm's blind 3D-state trace (design-final.md §3)."""

    tick_index: int
    seed: int
    zone: Zone
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    action_id: int
    affordance_ids: tuple[str, ...]


@dataclass(frozen=True)
class Trace3D:
    """One arm's full trace for one seed, plus its replay checksum."""

    seed: int
    arm: str
    rows: tuple[TraceRow, ...]

    @property
    def replay_checksum(self) -> str:
        return trace_checksum(self.rows)


def trace_checksum(rows: Sequence[TraceRow]) -> str:
    """SHA-256 over the canonical-serialised trace (replay checksum, §3)."""
    canonical = [
        {
            "tick_index": r.tick_index,
            "seed": r.seed,
            "zone": r.zone.value,
            "x": r.x,
            "y": r.y,
            "z": r.z,
            "yaw": r.yaw,
            "pitch": r.pitch,
            "action_id": r.action_id,
            "affordance_ids": list(r.affordance_ids),
        }
        for r in rows
    ]
    blob = json.dumps(canonical, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _draw_zone(rng: random.Random) -> Zone:
    return _c.ZONES[rng.randrange(len(_c.ZONES))]


def draw_start_terminal(seed: int) -> tuple[Zone, Zone]:
    """Shared start/terminal zones for both arms of ``seed`` (blind RNG).

    Mirrors ``spdm.scenario.build_seed_result``'s ``base`` RNG: both arms
    share the same start (a conservative matched element) and the same
    terminal location is available to callers that need a terminal-location
    read (R0/R1 retrieval landscape), while each arm's *walk* diverges from
    its own independent RNG substream.
    """
    base = random.Random(f"d0-seed-{seed}")  # noqa: S311 — deterministic science RNG
    start = _draw_zone(base)
    terminal = _draw_zone(base)
    return start, terminal


def _walk_with_actions(
    start: Zone, steps: int, rng: random.Random
) -> tuple[list[Zone], list[int]]:
    """Blind uniform walk + the per-step chosen-neighbour index.

    ES-1 ``uniform_walk`` backbone plus ``action_id`` (design-final.md §3).
    """
    here = start
    zones: list[Zone] = []
    actions: list[int] = []
    for _ in range(steps):
        zones.append(here)
        options = _c.ADJACENCY[here]
        idx = rng.randrange(len(options))
        actions.append(idx)
        here = options[idx]
    return zones, actions


def _affordance_ids_near(x: float, z: float, zone: Zone) -> tuple[str, ...]:
    hits = [
        prop.prop_id
        for prop in _c.ZONE_PROPS.get(zone, ())
        if math.hypot(x - prop.x, z - prop.z) <= _c.AFFORDANCE_RADIUS_M
    ]
    return tuple(hits)


def zone_default_heading(zone: Zone) -> float:
    """Deterministic canonical facing for ``zone`` (R2 quantize target).

    Facing toward the zone's own prop mass-centre when it has props
    (design-final.md §2: "ZONE_PROPS 質量中心向き"); otherwise facing toward
    the PERIPATOS hub (the world's canonical reference direction), and
    ``0.0`` for PERIPATOS itself. Pure function of ``zone`` — never reads a
    trace, so it cannot leak richer-rung information back into the quantized
    fixture.
    """
    cx, _cy, cz = _c.ZONE_CENTERS[zone]
    props = _c.ZONE_PROPS.get(zone, ())
    if props:
        mx = sum(p.x for p in props) / len(props)
        mz = sum(p.z for p in props) / len(props)
        return math.atan2(mz - cz, mx - cx)
    if zone is Zone.PERIPATOS:
        return 0.0
    hx, _hy, hz = _c.ZONE_CENTERS[Zone.PERIPATOS]
    return math.atan2(hz - cz, hx - cx)


ZONE_DEFAULT_NULL_ACTION: Literal[0] = 0
"""R3 quantize target: the action-independent null policy is "always take
the canonical (index-0) neighbour" (design-final.md §2: "action 非依存の
null policy"), regardless of which action the blind walk actually drew."""


def build_trace(
    seed: int, arm: str, start: Zone, steps: int = _c.M_MEMORIES
) -> Trace3D:
    """One arm's full-richness blind trace: zone backbone + micro-walk.

    ``arm`` selects the RNG substream (``"A"`` / ``"B"``); the walk and
    micro-walk RNGs are independent per arm so two arms sharing ``start``
    diverge purely from the blind walk (seed-as-only-freedom, no stickiness/
    dwell/bias knob).
    """
    zone_rng = random.Random(f"d0-seed-{seed}-{arm}-zone")  # noqa: S311
    zones, actions = _walk_with_actions(start, steps, zone_rng)

    micro_rng = random.Random(f"d0-seed-{seed}-{arm}-micro")  # noqa: S311
    rows: list[TraceRow] = []
    for i, zone in enumerate(zones):
        cx, cy, cz = _c.ZONE_CENTERS[zone]
        # Disc-uniform offset (polar, area-preserving sqrt(u) radius draw) so
        # the micro-walk genuinely stays within a CELL_MICRO_RADIUS_M-radius
        # disc, not a +-radius square (whose corners reach radius*sqrt(2)).
        r = _c.CELL_MICRO_RADIUS_M * math.sqrt(micro_rng.random())
        theta = micro_rng.uniform(0.0, 2.0 * math.pi)
        dx = r * math.cos(theta)
        dz = r * math.sin(theta)
        yaw = micro_rng.uniform(0.0, 2.0 * math.pi)
        x = cx + dx
        z = cz + dz
        rows.append(
            TraceRow(
                tick_index=i,
                seed=seed,
                zone=zone,
                x=x,
                y=cy,
                z=z,
                yaw=yaw,
                pitch=0.0,
                action_id=actions[i],
                affordance_ids=_affordance_ids_near(x, z, zone),
            ),
        )
    return Trace3D(seed=seed, arm=arm, rows=tuple(rows))


def build_seed_pair(
    seed: int, steps: int = _c.M_MEMORIES
) -> tuple[Trace3D, Trace3D, Zone, Zone]:
    """Both arms' traces for ``seed``, plus the shared ``(start, terminal)``."""
    start, terminal = draw_start_terminal(seed)
    trace_a = build_trace(seed, "A", start, steps)
    trace_b = build_trace(seed, "B", start, steps)
    return trace_a, trace_b, start, terminal


def quantize_trace(trace: Trace3D, rung: RungName) -> Trace3D:
    """Seed-paired quantized fixture for the anti-collapse gate (§2 #5).

    Collapses exactly ``rung``'s richer-than-R0 field to a deterministic
    zone-coarse value on the **same walk backbone** (same ``zone`` /
    ``tick_index`` sequence as ``trace``):

    * ``"R1"`` — position → zone centroid.
    * ``"R2"`` — yaw → :func:`zone_default_heading`.
    * ``"R3"`` — ``action_id`` → :data:`ZONE_DEFAULT_NULL_ACTION`.

    ``affordance_ids`` is recomputed from the (possibly quantized) position
    so the quantized trace stays internally consistent.
    """
    new_rows: list[TraceRow] = []
    for row in trace.rows:
        x, y, z, yaw, action_id = row.x, row.y, row.z, row.yaw, row.action_id
        if rung == "R1":
            x, y, z = _c.ZONE_CENTERS[row.zone]
        elif rung == "R2":
            yaw = zone_default_heading(row.zone)
        elif rung == "R3":
            action_id = ZONE_DEFAULT_NULL_ACTION
        new_rows.append(
            replace(
                row,
                x=x,
                y=y,
                z=z,
                yaw=yaw,
                action_id=action_id,
                affordance_ids=_affordance_ids_near(x, z, row.zone),
            ),
        )
    return Trace3D(
        seed=trace.seed, arm=f"{trace.arm}-quant-{rung}", rows=tuple(new_rows)
    )


def default_seed_bank() -> tuple[int, ...]:
    """The pre-registered blind seed bank: ``range(B)`` (= 0..63).

    Fixed before the run; no seed is added or dropped after seeing a result
    (forking-paths guard). A superseding ADR is required to change it.
    """
    return tuple(range(_c.B))


__all__ = [
    "ZONE_DEFAULT_NULL_ACTION",
    "RungName",
    "Trace3D",
    "TraceRow",
    "build_seed_pair",
    "build_trace",
    "default_seed_bank",
    "draw_start_terminal",
    "quantize_trace",
    "trace_checksum",
    "zone_default_heading",
]
