"""Static spatial representation of the five world zones (T13).

Zones are modelled as **Voronoi-lite partitions** around five centroids in the
XZ plane: any ``(x, y, z)`` point is assigned to the zone whose centroid is
nearest in the XZ plane, which means :func:`locate_zone` never raises and
every world coordinate has a well-defined zone. A rectangular AABB layout was
considered in ``design-v1.md`` but rejected because it leaves "outside any
zone" gaps whose handling adds branches without buying expressive power at
the MVP stage (no walls, no NavMesh — see MASTER-PLAN R8).

The module is pure: no logging, no I/O, no mutable state. The only exported
constants (:data:`ZONE_CENTERS`, :data:`ADJACENCY`, :data:`ZONE_PROPS`) are
wrapped in :class:`types.MappingProxyType` so callers cannot silently mutate
the layout.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, NamedTuple

from erre_sandbox.schemas import Position, Zone

if TYPE_CHECKING:
    from collections.abc import Mapping


class PropSpec(NamedTuple):
    """Static world prop that emits :class:`AffordanceEvent` on agent proximity.

    Fields mirror :class:`AffordanceEvent` so the firing path in
    :mod:`erre_sandbox.world.tick` can translate 1:1 without re-mapping.
    Positions are in world XZ-plane coordinates at a fixed ``y`` (the prop
    height doesn't affect the current 2D affordance-radius check but is
    preserved for Godot scene wiring).
    """

    prop_id: str
    prop_kind: str
    x: float
    y: float
    z: float
    salience: float = 0.5


WORLD_SIZE_M: Final[float] = 100.0
"""Edge length (metres) of the square BaseTerrain plane.

Raised from 60 m (Slice α) to 100 m in Slice β so zone centroids spread over
a visibly larger area while 3-agent trajectories remain observable from a
single top-down camera preset. All dependent coordinates below derive from
this constant so future scaling is a one-line change.

Keep :data:`WORLD_SIZE_M` in sync with the ``PlaneMesh.size`` in
``godot_project/scenes/zones/BaseTerrain.tscn`` and the top-down camera
``max_distance`` in ``godot_project/scripts/CameraRig.gd``.
"""

_ZONE_OFFSET: Final[float] = WORLD_SIZE_M / 3.0
"""XZ offset of non-central zones from peripatos (world origin).

Non-central zones sit at (±_ZONE_OFFSET, 0, ±_ZONE_OFFSET), giving each zone
a ~_ZONE_OFFSET-radius Voronoi cell inside the terrain bounds.
"""

ZONE_CENTERS: Final[Mapping[Zone, tuple[float, float, float]]] = MappingProxyType(
    {
        Zone.STUDY: (-_ZONE_OFFSET, 0.0, -_ZONE_OFFSET),
        Zone.PERIPATOS: (0.0, 0.0, 0.0),
        Zone.CHASHITSU: (_ZONE_OFFSET, 0.0, -_ZONE_OFFSET),
        Zone.AGORA: (0.0, 0.0, _ZONE_OFFSET),
        Zone.GARDEN: (_ZONE_OFFSET, 0.0, _ZONE_OFFSET),
    },
)
"""Five zone centroids in world XZ-plane coordinates.

The ``y`` component is kept at 0.0 for the MVP flat-ground assumption; it is
preserved in the tuple so future terrain work can extend the layout without a
breaking change to the shape of this mapping. All non-central centres are
derived from :data:`WORLD_SIZE_M` via :data:`_ZONE_OFFSET`.
"""

ZONE_PROPS: Final[Mapping[Zone, tuple[PropSpec, ...]]] = MappingProxyType(
    {
        Zone.CHASHITSU: (
            PropSpec(
                prop_id="chawan_01",
                prop_kind="tea_bowl",
                x=_ZONE_OFFSET - 0.5,
                y=0.4,
                z=-_ZONE_OFFSET + 0.5,
                salience=0.7,
            ),
            PropSpec(
                prop_id="chawan_02",
                prop_kind="tea_bowl",
                x=_ZONE_OFFSET + 0.5,
                y=0.4,
                z=-_ZONE_OFFSET - 0.5,
                salience=0.6,
            ),
        ),
        Zone.STUDY: (),
        Zone.PERIPATOS: (),
        Zone.AGORA: (),
        Zone.GARDEN: (),
    },
)
"""Zone-indexed prop tables driving :class:`AffordanceEvent` firing (M7 B1).

MVP scope: chashitsu carries two ``tea_bowl`` props; the other four zones
start empty. Adding props for a new zone is a pure data change — the firing
loop in :mod:`erre_sandbox.world.tick` iterates over every entry and emits
an affordance event to agents within
:data:`erre_sandbox.world.tick._AFFORDANCE_RADIUS_M`.

Keep this table in sync with the Godot scene files under
``godot_project/scenes/zones/`` — the GDScript ``BoundaryLayer`` uses the
same coordinates hard-coded until the schema wiring lands in the next PR.
"""

ADJACENCY: Final[Mapping[Zone, frozenset[Zone]]] = MappingProxyType(
    {
        Zone.STUDY: frozenset({Zone.PERIPATOS}),
        Zone.PERIPATOS: frozenset(
            {Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN},
        ),
        Zone.CHASHITSU: frozenset({Zone.PERIPATOS, Zone.GARDEN}),
        Zone.AGORA: frozenset({Zone.PERIPATOS, Zone.GARDEN}),
        Zone.GARDEN: frozenset({Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA}),
    },
)
"""Walkable adjacency graph between zones (symmetric, anchored at peripatos)."""


def locate_zone(x: float, y: float, z: float) -> Zone:
    """Return the zone whose centroid is nearest in the XZ plane.

    The ``y`` coordinate is currently ignored but kept in the signature so the
    caller's code does not need to strip it when future terrain support lands.

    Args:
        x: World X coordinate (metres).
        y: World Y coordinate (metres, reserved).
        z: World Z coordinate (metres).

    Returns:
        The :class:`Zone` with minimal Euclidean distance in the XZ plane.
        Ties are broken by the iteration order of :data:`ZONE_CENTERS`
        (``Zone`` enum declaration order: study, peripatos, chashitsu, agora,
        garden), which is deterministic across interpreters.
    """
    del y  # reserved for future vertical layout; see module docstring.
    best_zone: Zone | None = None
    best_d2: float = float("inf")
    for zone, (cx, _cy, cz) in ZONE_CENTERS.items():
        dx = cx - x
        dz = cz - z
        d2 = dx * dx + dz * dz
        if d2 < best_d2:
            best_d2 = d2
            best_zone = zone
    assert best_zone is not None  # ZONE_CENTERS is non-empty by construction
    return best_zone


def default_spawn(zone: Zone) -> Position:
    """Return the centroid of ``zone`` as a :class:`Position` with that zone.

    Used by the runtime to place a freshly registered agent at a sensible
    starting point inside its home zone.
    """
    cx, cy, cz = ZONE_CENTERS[zone]
    return Position(x=cx, y=cy, z=cz, zone=zone)


def adjacent_zones(zone: Zone) -> frozenset[Zone]:
    """Return the set of zones directly walkable from ``zone`` (excludes self)."""
    return ADJACENCY[zone]
