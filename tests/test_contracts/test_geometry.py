"""Tests for ``erre_sandbox.contracts.geometry`` (M13 ECL v0, Issue 001).

The geometry SSOT was relocated here from ``world.zones`` so the ``cognition``
layer can resolve history-dependent destinations without importing ``world``.
These tests pin: (AC1) the relocated values, (AC2) the ``world.zones`` shim
backward-compat (``is``-identity), (AC3) the design-copied micro geometry
(``disc_jitter`` / ``reflect_clamp``), (AC4) the one-way dependency direction,
and (AC5) that cold-importing either module raises no circular ImportError.
"""

from __future__ import annotations

import ast
import random
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

from erre_sandbox.contracts import geometry
from erre_sandbox.schemas import Position, Zone

_GEOMETRY_SRC = Path(geometry.__file__)


class TestRelocatedValues:
    """AC1: the relocated geometry SSOT carries the expected values."""

    def test_world_size_and_offset(self) -> None:
        assert geometry.WORLD_SIZE_M == 100.0
        assert pytest.approx(100.0 / 3.0) == geometry._ZONE_OFFSET

    def test_zone_centers_are_frozen_mapping(self) -> None:
        assert isinstance(geometry.ZONE_CENTERS, MappingProxyType)
        assert set(geometry.ZONE_CENTERS) == set(Zone)
        off = geometry._ZONE_OFFSET
        assert geometry.ZONE_CENTERS[Zone.PERIPATOS] == (0.0, 0.0, 0.0)
        assert geometry.ZONE_CENTERS[Zone.STUDY] == (-off, 0.0, -off)
        assert geometry.ZONE_CENTERS[Zone.GARDEN] == (off, 0.0, off)

    def test_locate_zone_maps_each_centroid_to_its_zone(self) -> None:
        for zone, (cx, cy, cz) in geometry.ZONE_CENTERS.items():
            assert geometry.locate_zone(cx, cy, cz) is zone

    def test_default_spawn_is_centroid(self) -> None:
        for zone in Zone:
            spawn = geometry.default_spawn(zone)
            assert isinstance(spawn, Position)
            assert spawn.zone is zone
            assert (spawn.x, spawn.y, spawn.z) == geometry.ZONE_CENTERS[zone]

    def test_cell_micro_radius_matches_frozen_value(self) -> None:
        # Value-identical to evidence.d0_substrate.constants.CELL_MICRO_RADIUS_M
        # and consistent with the 100 m world (grill G-4). Imported here from the
        # frozen mirror only as a read-only equality check, never mutated.
        from erre_sandbox.evidence.d0_substrate import constants as d0c

        assert geometry.CELL_MICRO_RADIUS_M == 10.0
        assert geometry.CELL_MICRO_RADIUS_M == d0c.CELL_MICRO_RADIUS_M


class TestShimBackwardCompat:
    """AC2: world.zones re-exports the relocated symbols with is-identity."""

    def test_reexport_is_identity(self) -> None:
        from erre_sandbox.world import zones

        assert zones.WORLD_SIZE_M == geometry.WORLD_SIZE_M
        assert zones.ZONE_CENTERS is geometry.ZONE_CENTERS
        assert zones.locate_zone is geometry.locate_zone
        assert zones.default_spawn is geometry.default_spawn

    def test_zone_props_and_adjacency_stay_in_world_zones(self) -> None:
        from erre_sandbox.world import zones

        # Codex LOW-1 / G-9: these stay in world.zones, not contracts.geometry.
        assert hasattr(zones, "ZONE_PROPS")
        assert hasattr(zones, "ADJACENCY")
        assert not hasattr(geometry, "ZONE_PROPS")
        assert not hasattr(geometry, "ADJACENCY")


class TestDiscJitter:
    """AC3: disc_jitter is an area-preserving disc-uniform offset."""

    def test_all_samples_stay_within_radius(self) -> None:
        rng = random.Random("ecl-geometry-test")
        for _ in range(5000):
            dx, dz = geometry.disc_jitter(rng)
            assert (dx * dx + dz * dz) ** 0.5 <= geometry.CELL_MICRO_RADIUS_M + 1e-9

    def test_deterministic_under_same_seed(self) -> None:
        a = [geometry.disc_jitter(random.Random("s")) for _ in range(1)]
        b = [geometry.disc_jitter(random.Random("s")) for _ in range(1)]
        assert a == b


class TestReflectClamp:
    """AC3: reflect_clamp pulls an out-of-cell dest back inside the zone."""

    def test_inside_cell_dest_is_unchanged(self) -> None:
        cx, _cy, cz = geometry.ZONE_CENTERS[Zone.PERIPATOS]
        x, z, fired = geometry.reflect_clamp(cx + 1.0, cz + 1.0, Zone.PERIPATOS)
        assert not fired
        assert (x, z) == (cx + 1.0, cz + 1.0)

    def test_out_of_cell_dest_is_clamped_into_zone(self) -> None:
        # A destination far outside STUDY's cell, tagged for STUDY.
        gx, _gy, gz = geometry.ZONE_CENTERS[Zone.GARDEN]
        x, z, fired = geometry.reflect_clamp(gx, gz, Zone.STUDY)
        assert fired
        assert geometry.locate_zone(x, 0.0, z) is Zone.STUDY
        cx, _cy, cz = geometry.ZONE_CENTERS[Zone.STUDY]
        assert ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5 <= (
            geometry.CELL_MICRO_RADIUS_M + 1e-9
        )

    def test_zero_norm_returns_centroid(self) -> None:
        # dest exactly on a foreign centroid but tagged for another zone: the
        # radial direction is undefined, so it snaps to the target centroid.
        px, _py, pz = geometry.ZONE_CENTERS[Zone.PERIPATOS]
        x, z, fired = geometry.reflect_clamp(px, pz, Zone.STUDY)
        assert fired
        assert geometry.locate_zone(x, 0.0, z) is Zone.STUDY


class TestDependencyDirection:
    """AC4: contracts.geometry imports only schemas + stdlib (one-way edge)."""

    def test_no_upper_layer_imports(self) -> None:
        tree = ast.parse(_GEOMETRY_SRC.read_text(encoding="utf-8"))
        banned = (
            "erre_sandbox.world",
            "erre_sandbox.cognition",
            "erre_sandbox.memory",
            "erre_sandbox.inference",
            "erre_sandbox.ui",
            "erre_sandbox.integration",
            "erre_sandbox.evidence",
            "erre_sandbox.erre",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith(banned), (
                    f"contracts.geometry must not import {node.module}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(banned), (
                        f"contracts.geometry must not import {alias.name}"
                    )


class TestColdImportNoCycle:
    """AC5: cold-importing each module in a fresh interpreter raises no cycle."""

    @pytest.mark.parametrize(
        "module",
        [
            "erre_sandbox.contracts.geometry",
            "erre_sandbox.world.zones",
            "erre_sandbox.world.physics",
            "erre_sandbox.world",
        ],
    )
    def test_cold_import(self, module: str) -> None:
        result = subprocess.run(  # noqa: S603 — sys.executable + parametrized module literal
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"cold import of {module} failed:\n{result.stderr}"
        )
