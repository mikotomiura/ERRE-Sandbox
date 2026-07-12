# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 ERRE-Sandbox Contributors
#
# This file is part of erre-sandbox-blender.
# It is distributed under the terms of the GNU General Public License v3.0 or later.
"""Seed-free geometry-nodes builder + glb exporter for the M4 peripatos zone.

M13 M4 situated-3D — Issue 003 (I3) of the FROZEN M4 impl-design ADR
(``loop/20260711-m13-m4-code/design-final-ref.md`` §1 geometry-nodes seed-free /
§1.3 決定性契約・二層 witness / §2 .glb 粒度 / §8 SPDX).

Run headlessly::

    blender --background --python erre-sandbox-blender/scripts/export_peripatos.py

The script wipes the current Blender scene, builds the peripatos (歩行路) zone
with a **seed-free deterministic geometry-nodes tree** — a walking-path grid plus
index-driven marker pillars instanced on a ``Mesh Line`` point source and merged
with ``Realize Instances`` — then bakes it (``export_apply=True``) and emits a
single ``.glb`` at

* ``erre-sandbox-blender/exports/peripatos_v1.glb`` — package-local staging
  artefact (git-ignored).
* ``godot_project/assets/environment/peripatos_v1.glb`` — the committed Godot
  side load path.

Determinism contract (design §1.1 / §1.3, Codex HIGH-1 / HIGH-2):

* **seed-free** — only deterministic primitives (``Mesh Grid`` / ``Mesh Line`` /
  ``Mesh Cube``) + ``Instance on Points`` + ``Realize Instances`` are used. No
  ``Distribute Points on Faces``, no un-seeded ``Random Value``, no time/frame
  input. The marker "scatter" is an index-driven lattice (evenly spaced line
  points), not random.
* **identity node transform (HIGH-1)** — the object sits at the world origin with
  identity TRS and ``export_apply=True`` bakes the modifier, so the exported glTF
  node carries no transform and the accessor-local POSITION min/max *is* the
  asset bbox (the pure GLB-JSON parser fails closed on any non-identity node).
* **uncompressed / self-contained (HIGH-2)** — GLB format embeds the buffer (no
  external URI), Draco / meshopt compression are disabled, POSITION is a plain
  (non-sparse) accessor.

Local content is centred on the world origin ``(0, 0, 0)`` (design §2); the Godot
side places the zone root at ``ZONE_CENTERS[peripatos]`` (also the origin) and the
shared 100 m ``BaseTerrain`` stays separate — this ``.glb`` carries no full ground
plane.

The structural fingerprint sidecar
(``godot_project/assets/environment/peripatos_v1.fingerprint.json``) is generated
separately from the committed ``.glb`` by the non-GPL pure parser (see
``tests/test_integration/test_m4_zone_glb_fingerprint.py``), so it is not written
here — this GPL script only bakes the ``.glb``.

License: GPL-3.0-or-later (inherits from ``import bpy``). Deliberately isolated
from the Apache-2.0 OR MIT core at ``../../src/erre_sandbox/`` — see the package
README. This is a **construction** artefact, not a measurement line.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    import bpy  # type: ignore[import-not-found]  # provided by Blender
except ImportError:
    print(  # noqa: T201
        "ERROR: this script must be run with `blender --background --python ...`",
        file=sys.stderr,
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_OUT = REPO_ROOT / "erre-sandbox-blender" / "exports" / "peripatos_v1.glb"
GODOT_OUT = REPO_ROOT / "godot_project" / "assets" / "environment" / "peripatos_v1.glb"


# ---------- Colours (PBR albedo) --------------------------------------------

# Pinned tones matching the peripatos tan / stone palette used elsewhere so the
# export slots into the scene without an extra lighting pass.
STONE = (0.66, 0.62, 0.54, 1.0)
WOOD = (0.42, 0.28, 0.18, 1.0)


# ---------- Geometry parameters (pinned; index-driven, seed-free) -----------

PATH_SIZE_X = 8.0
"""Walking-path width (metres)."""
PATH_SIZE_Y = 40.0
"""Walking-path length (metres)."""
PATH_VERTS_X = 3
"""Grid vertices across the path (deterministic, fixed)."""
PATH_VERTS_Y = 11
"""Grid vertices along the path (deterministic, fixed)."""

MARKER_COUNT = 8
"""Number of colonnade marker pillars (index-driven line points)."""
MARKER_SPAN = 36.0
"""Total span (metres) the marker line covers along the path."""
MARKER_OFFSET_X = 3.4
"""Lateral offset of the marker line from the path centre (metres)."""
MARKER_SIZE = (0.5, 0.5, 3.0)
"""Marker pillar cube dimensions (metres)."""


# ---------- Helpers ---------------------------------------------------------


def _clear_scene() -> None:
    """Remove every mesh/material/node-group so the script is idempotent."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block, do_unlink=True)
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block, do_unlink=True)
    for group in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(group, do_unlink=True)


def _make_material(name: str, rgba: tuple[float, float, float, float]) -> object:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = next(
        node
        for node in mat.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def _build_node_group(mat_path: object, mat_marker: object) -> object:
    """Assemble the seed-free deterministic geometry-nodes tree.

    Branch 1 (path) = ``Mesh Grid`` -> ``Set Material``.
    Branch 2 (markers) = ``Mesh Line`` (evenly-spaced, index-driven points) ->
    ``Instance on Points`` (a ``Mesh Cube`` per point) -> ``Realize Instances``
    -> ``Set Material``. The two branches are merged with ``Join Geometry`` into
    the group output. No random / distribute / time node is used.
    """
    ng = bpy.data.node_groups.new("PeripatosGN", "GeometryNodeTree")
    ng.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    nodes = ng.nodes
    links = ng.links

    out = nodes.new("NodeGroupOutput")

    # --- Branch 1: walking-path grid, centred on origin ---
    grid = nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = PATH_SIZE_X
    grid.inputs["Size Y"].default_value = PATH_SIZE_Y
    grid.inputs["Vertices X"].default_value = PATH_VERTS_X
    grid.inputs["Vertices Y"].default_value = PATH_VERTS_Y

    set_mat_path = nodes.new("GeometryNodeSetMaterial")
    set_mat_path.inputs["Material"].default_value = mat_path
    links.new(grid.outputs["Mesh"], set_mat_path.inputs["Geometry"])

    # --- Branch 2: index-driven marker pillars along the path ---
    line = nodes.new("GeometryNodeMeshLine")
    line.mode = "OFFSET"
    line.inputs["Count"].default_value = MARKER_COUNT
    # Evenly spaced points: deterministic function of the fixed span / count.
    step = MARKER_SPAN / float(MARKER_COUNT - 1)
    line.inputs["Start Location"].default_value = (
        MARKER_OFFSET_X,
        -MARKER_SPAN / 2.0,
        MARKER_SIZE[2] / 2.0,
    )
    line.inputs["Offset"].default_value = (0.0, step, 0.0)

    cube = nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = MARKER_SIZE

    instance = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(line.outputs["Mesh"], instance.inputs["Points"])
    links.new(cube.outputs["Mesh"], instance.inputs["Instance"])

    realize = nodes.new("GeometryNodeRealizeInstances")
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])

    set_mat_marker = nodes.new("GeometryNodeSetMaterial")
    set_mat_marker.inputs["Material"].default_value = mat_marker
    links.new(realize.outputs["Geometry"], set_mat_marker.inputs["Geometry"])

    # --- Merge branches into the group output ---
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(set_mat_path.outputs["Geometry"], join.inputs["Geometry"])
    links.new(set_mat_marker.outputs["Geometry"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], out.inputs["Geometry"])

    return ng


def build_peripatos() -> None:
    """Create the peripatos object driven by the seed-free geometry-nodes tree."""
    mat_path = _make_material("PeripatosPath", STONE)
    mat_marker = _make_material("PeripatosMarker", WOOD)

    mesh = bpy.data.meshes.new("PeripatosBase")
    obj = bpy.data.objects.new("Peripatos", mesh)
    bpy.context.collection.objects.link(obj)
    # HIGH-1: identity object transform so the baked node carries no transform.
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

    modifier = obj.modifiers.new("PeripatosGeometryNodes", "NODES")
    modifier.node_group = _build_node_group(mat_path, mat_marker)


# ---------- Export ----------------------------------------------------------


def export_glb() -> None:
    STAGING_OUT.parent.mkdir(parents=True, exist_ok=True)
    GODOT_OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(STAGING_OUT),
        export_format="GLB",
        export_apply=True,  # bake the geometry-nodes modifier -> identity mesh
        export_draco_mesh_compression_enable=False,  # HIGH-2: no Draco
        export_materials="EXPORT",
        use_selection=False,
    )
    shutil.copyfile(STAGING_OUT, GODOT_OUT)
    print(f"[export_peripatos] wrote {STAGING_OUT.relative_to(REPO_ROOT)}")  # noqa: T201
    print(f"[export_peripatos] copied to {GODOT_OUT.relative_to(REPO_ROOT)}")  # noqa: T201


def main() -> int:
    _clear_scene()
    build_peripatos()
    export_glb()
    return 0


if __name__ == "__main__":
    sys.exit(main())
