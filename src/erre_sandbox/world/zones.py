"""Static spatial representation of the five world zones (T13).

Zones are modelled as **Voronoi-lite partitions** around five centroids in the
XZ plane: any ``(x, y, z)`` point is assigned to the zone whose centroid is
nearest in the XZ plane, which means :func:`locate_zone` never raises and
every world coordinate has a well-defined zone. A rectangular AABB layout was
considered in ``design-v1.md`` but rejected because it leaves "outside any
zone" gaps whose handling adds branches without buying expressive power at
the MVP stage (no walls, no NavMesh — see MASTER-PLAN R8).

The module is pure: no logging, no I/O, no mutable state. The only exported
constants (:data:`ZONE_CENTERS`, :data:`ADJACENCY`) are wrapped in
:class:`types.MappingProxyType` so callers cannot silently mutate the layout.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from erre_sandbox.schemas import Position, Zone

if TYPE_CHECKING:
    from collections.abc import Mapping

ZONE_CENTERS: Final[Mapping[Zone, tuple[float, float, float]]] = MappingProxyType(
    {
        Zone.STUDY: (-20.0, 0.0, -20.0),
        Zone.PERIPATOS: (0.0, 0.0, 0.0),
        Zone.CHASHITSU: (20.0, 0.0, -20.0),
        Zone.AGORA: (0.0, 0.0, 20.0),
        Zone.GARDEN: (20.0, 0.0, 20.0),
    },
)
"""Five zone centroids in world XZ-plane coordinates.

The ``y`` component is kept at 0.0 for the MVP flat-ground assumption; it is
preserved in the tuple so future terrain work can extend the layout without a
breaking change to the shape of this mapping.
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
