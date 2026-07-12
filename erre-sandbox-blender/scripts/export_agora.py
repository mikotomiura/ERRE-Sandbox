# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 ERRE-Sandbox Contributors
#
# This file is part of erre-sandbox-blender.
# It is distributed under the terms of the GNU General Public License v3.0 or later.
"""Seed-free geometry-nodes builder + glb exporter for the M4 agora (広場) zone.

M13 M4 situated-3D — Issue 004 (I4) of the FROZEN M4 impl-design ADR
(``loop/20260711-m13-m4-code/design-final-ref.md`` §1.2 段階移行 / §1 geometry-nodes
seed-free / §1.3 決定性契約・二層 witness / §2 .glb 粒度 / §8 SPDX). Applies the I3
``export_peripatos.py`` pipeline to the agora zone.

Run headlessly::

    blender --background --python erre-sandbox-blender/scripts/export_agora.py

The agora zone is an open public square: a seed-free deterministic geometry-nodes
tree builds a broad floor grid plus an index-driven colonnade of stone columns
instanced on a ``Mesh Line`` point source and merged with ``Realize Instances``.
Baked (``export_apply=True``) into a single ``.glb`` at

* ``erre-sandbox-blender/exports/agora_v1.glb`` — package-local staging artefact
  (git-ignored).
* ``godot_project/assets/environment/agora_v1.glb`` — the committed Godot side
  load path.

Determinism contract (design §1.1 / §1.3, Codex HIGH-1 / HIGH-2), identical to the
I3 template:

* **seed-free** — only deterministic primitives (``Mesh Grid`` / ``Mesh Line`` /
  ``Mesh Cube``) + ``Instance on Points`` + ``Realize Instances`` are used. No
  ``Distribute Points on Faces``, no un-seeded ``Random Value``, no time/frame
  input. The colonnade is an index-driven lattice (evenly spaced line points).
* **identity node transform (HIGH-1)** — the object sits at the world origin with
  identity TRS and ``export_apply=True`` bakes the modifier, so the exported glTF
  node carries no transform and the accessor-local POSITION min/max *is* the asset
  bbox (the pure GLB-JSON parser fails closed on any non-identity node).
* **uncompressed / self-contained (HIGH-2)** — GLB format embeds the buffer,
  Draco / meshopt compression are disabled, POSITION is a plain (non-sparse)
  accessor.

Local content is centred on the world origin ``(0, 0, 0)`` (design §2); the Godot
side places the zone root at ``ZONE_CENTERS[agora]`` and the shared ``BaseTerrain``
stays separate — this ``.glb`` carries no full ground plane. The structural
fingerprint sidecar is generated separately from the committed ``.glb`` by the
non-GPL pure parser (see ``tests/test_integration/test_m4_zone_glb_fingerprint.py``).

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
STAGING_OUT = REPO_ROOT / "erre-sandbox-blender" / "exports" / "agora_v1.glb"
GODOT_OUT = REPO_ROOT / "godot_project" / "assets" / "environment" / "agora_v1.glb"


# ---------- Colours (PBR albedo) --------------------------------------------

# Pale-stone plaza paving and lighter marble columns.
PAVING = (0.70, 0.68, 0.62, 1.0)
MARBLE = (0.86, 0.84, 0.80, 1.0)


# ---------- Geometry parameters (pinned; index-driven, seed-free) -----------

FLOOR_SIZE_X = 24.0
"""Plaza width (metres) — a broad open square."""
FLOOR_SIZE_Y = 24.0
"""Plaza depth (metres)."""
FLOOR_VERTS_X = 7
"""Grid vertices across the plaza (deterministic, fixed)."""
FLOOR_VERTS_Y = 7
"""Grid vertices along the plaza (deterministic, fixed)."""

COLUMN_COUNT = 10
"""Number of colonnade columns (index-driven line points)."""
COLUMN_SPAN = 20.0
"""Total span (metres) the colonnade covers along one edge."""
COLUMN_OFFSET_Y = 10.0
"""Distance of the colonnade from the plaza centre (metres)."""
COLUMN_SIZE = (0.8, 0.8, 4.5)
"""Colonnade column cube dimensions (metres)."""


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


def _build_node_group(mat_floor: object, mat_column: object) -> object:
    """Assemble the seed-free deterministic geometry-nodes tree.

    Branch 1 (plaza) = ``Mesh Grid`` -> ``Set Material``.
    Branch 2 (colonnade) = ``Mesh Line`` (evenly-spaced, index-driven points) ->
    ``Instance on Points`` (a ``Mesh Cube`` per point) -> ``Realize Instances``
    -> ``Set Material``. The two branches merge with ``Join Geometry``. No
    random / distribute / time node is used.
    """
    ng = bpy.data.node_groups.new("AgoraGN", "GeometryNodeTree")
    ng.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    nodes = ng.nodes
    links = ng.links

    out = nodes.new("NodeGroupOutput")

    # --- Branch 1: plaza floor grid, centred on origin ---
    grid = nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = FLOOR_SIZE_X
    grid.inputs["Size Y"].default_value = FLOOR_SIZE_Y
    grid.inputs["Vertices X"].default_value = FLOOR_VERTS_X
    grid.inputs["Vertices Y"].default_value = FLOOR_VERTS_Y

    set_mat_floor = nodes.new("GeometryNodeSetMaterial")
    set_mat_floor.inputs["Material"].default_value = mat_floor
    links.new(grid.outputs["Mesh"], set_mat_floor.inputs["Geometry"])

    # --- Branch 2: index-driven colonnade along one plaza edge ---
    line = nodes.new("GeometryNodeMeshLine")
    line.mode = "OFFSET"
    line.inputs["Count"].default_value = COLUMN_COUNT
    step = COLUMN_SPAN / float(COLUMN_COUNT - 1)
    line.inputs["Start Location"].default_value = (
        -COLUMN_SPAN / 2.0,
        COLUMN_OFFSET_Y,
        COLUMN_SIZE[2] / 2.0,
    )
    line.inputs["Offset"].default_value = (step, 0.0, 0.0)

    cube = nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = COLUMN_SIZE

    instance = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(line.outputs["Mesh"], instance.inputs["Points"])
    links.new(cube.outputs["Mesh"], instance.inputs["Instance"])

    realize = nodes.new("GeometryNodeRealizeInstances")
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])

    set_mat_column = nodes.new("GeometryNodeSetMaterial")
    set_mat_column.inputs["Material"].default_value = mat_column
    links.new(realize.outputs["Geometry"], set_mat_column.inputs["Geometry"])

    # --- Merge branches into the group output ---
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(set_mat_floor.outputs["Geometry"], join.inputs["Geometry"])
    links.new(set_mat_column.outputs["Geometry"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], out.inputs["Geometry"])

    return ng


def build_agora() -> None:
    """Create the agora object driven by the seed-free geometry-nodes tree."""
    mat_floor = _make_material("AgoraPaving", PAVING)
    mat_column = _make_material("AgoraColumn", MARBLE)

    mesh = bpy.data.meshes.new("AgoraBase")
    obj = bpy.data.objects.new("Agora", mesh)
    bpy.context.collection.objects.link(obj)
    # HIGH-1: identity object transform so the baked node carries no transform.
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

    modifier = obj.modifiers.new("AgoraGeometryNodes", "NODES")
    modifier.node_group = _build_node_group(mat_floor, mat_column)


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
    print(f"[export_agora] wrote {STAGING_OUT.relative_to(REPO_ROOT)}")  # noqa: T201
    print(f"[export_agora] copied to {GODOT_OUT.relative_to(REPO_ROOT)}")  # noqa: T201


def main() -> int:
    _clear_scene()
    build_agora()
    export_glb()
    return 0


if __name__ == "__main__":
    sys.exit(main())
