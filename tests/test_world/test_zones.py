"""Tests for ``erre_sandbox.world.zones`` (T13).

The Voronoi partition is fully determined by :data:`ZONE_CENTERS`, so the
tests deliberately target three regimes: (1) exact centroid hits, (2) points
safely inside one zone's cell, and (3) far-field points that should still
resolve to the nearest zone (no ``ZoneNotFoundError`` in the v2 design).
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from erre_sandbox.schemas import Position, Zone
from erre_sandbox.world.zones import (
    ADJACENCY,
    ZONE_CENTERS,
    adjacent_zones,
    default_spawn,
    locate_zone,
)


class TestLocateZone:
    def test_each_centroid_maps_to_its_own_zone(self) -> None:
        for zone, (cx, cy, cz) in ZONE_CENTERS.items():
            assert locate_zone(cx, cy, cz) is zone

    @pytest.mark.parametrize(
        ("point", "expected"),
        [
            ((-10.0, 0.0, -15.0), Zone.STUDY),  # NW quadrant, closer to study
            ((1.0, 0.0, 1.0), Zone.PERIPATOS),  # near origin
            ((15.0, 0.0, -15.0), Zone.CHASHITSU),  # NE quadrant
            ((-5.0, 0.0, 15.0), Zone.AGORA),  # SW-ish (S direction in Godot z+)
            ((18.0, 0.0, 18.0), Zone.GARDEN),  # SE quadrant
        ],
    )
    def test_points_inside_cells_resolve_locally(
        self,
        point: tuple[float, float, float],
        expected: Zone,
    ) -> None:
        assert locate_zone(*point) is expected

    def test_far_field_point_still_resolves(self) -> None:
        """Outside the rough 40m bounding square, Voronoi still assigns a zone."""
        assert locate_zone(1000.0, 0.0, 1000.0) is Zone.GARDEN
        assert locate_zone(-1000.0, 0.0, -1000.0) is Zone.STUDY

    def test_y_coordinate_is_ignored(self) -> None:
        assert locate_zone(0.0, 0.0, 0.0) is locate_zone(0.0, 99.0, 0.0)

    def test_tie_broken_by_enum_declaration_order(self) -> None:
        """When equidistant, the first zone in ``ZONE_CENTERS`` iteration wins."""
        midpoint_study_peripatos = (-10.0, 0.0, -10.0)
        first = next(iter(ZONE_CENTERS))
        assert locate_zone(*midpoint_study_peripatos) is first


class TestDefaultSpawn:
    @pytest.mark.parametrize("zone", list(Zone))
    def test_spawn_is_centroid_in_its_zone(self, zone: Zone) -> None:
        spawn = default_spawn(zone)
        assert isinstance(spawn, Position)
        assert spawn.zone is zone
        cx, cy, cz = ZONE_CENTERS[zone]
        assert (spawn.x, spawn.y, spawn.z) == (cx, cy, cz)


class TestAdjacency:
    def test_adjacency_is_symmetric(self) -> None:
        for zone, neighbours in ADJACENCY.items():
            for other in neighbours:
                assert zone in ADJACENCY[other], (
                    f"{zone} lists {other} as neighbour but not vice-versa"
                )

    def test_peripatos_connects_to_all_others(self) -> None:
        """Design invariant: peripatos is the transport hub."""
        assert ADJACENCY[Zone.PERIPATOS] == frozenset(
            {Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN},
        )

    def test_no_self_loops(self) -> None:
        for zone, neighbours in ADJACENCY.items():
            assert zone not in neighbours

    def test_adjacent_zones_returns_frozen_set(self) -> None:
        neighbours = adjacent_zones(Zone.PERIPATOS)
        assert isinstance(neighbours, frozenset)
        assert Zone.STUDY in neighbours


class TestMappingImmutability:
    def test_zone_centers_is_mapping_proxy(self) -> None:
        assert isinstance(ZONE_CENTERS, MappingProxyType)

    def test_adjacency_is_mapping_proxy(self) -> None:
        assert isinstance(ADJACENCY, MappingProxyType)

    def test_zone_centers_cannot_be_mutated(self) -> None:
        with pytest.raises(TypeError):
            ZONE_CENTERS[Zone.STUDY] = (99.0, 0.0, 99.0)  # type: ignore[index]
