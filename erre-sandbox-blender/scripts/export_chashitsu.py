"""Procedural builder + glb exporter for the M6-C chashitsu (茶室).

Run headlessly::

    blender --background --python erre-sandbox-blender/scripts/export_chashitsu.py

The script wipes the current Blender scene, rebuilds the chashitsu from
parametric primitives, and emits a single ``.glb`` at

* ``erre-sandbox-blender/exports/chashitsu_v1.glb`` — package-local
  staging artefact (git-ignored).
* ``godot_project/assets/environment/chashitsu_v1.glb`` — the Godot side's
  expected load path. The Chashitsu.tscn scene tolerates absence, so this
  file is the only bridge between the two packages.

Idempotency: re-running the script with no source edits produces the same
bytes (Blender glTF exporter is deterministic for the fixed primitive
geometry below).

License: GPL-3.0-or-later (inherits from ``import bpy``). This script and
the package that contains it are deliberately isolated from the Apache-2.0
OR MIT core at ``../../src/erre_sandbox/`` — see the package README.
"""

from __future__ import annotations

import math
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
STAGING_OUT = REPO_ROOT / "erre-sandbox-blender" / "exports" / "chashitsu_v1.glb"
GODOT_OUT = REPO_ROOT / "godot_project" / "assets" / "environment" / "chashitsu_v1.glb"


# ---------- Colours (PBR albedo) --------------------------------------------

# Pinned light and dark wood tones chosen to sit inside the existing zone
# palette (peripatos tan / chashitsu brown) so the export slots into the
# scene without an extra lighting pass.
WOOD_LIGHT = (0.72, 0.55, 0.35, 1.0)
WOOD_DARK = (0.42, 0.28, 0.18, 1.0)
TATAMI = (0.78, 0.70, 0.50, 1.0)
SHOJI = (0.94, 0.92, 0.84, 1.0)
ROOF = (0.22, 0.18, 0.16, 1.0)
ASH = (0.55, 0.52, 0.48, 1.0)
CLAY = (0.48, 0.22, 0.14, 1.0)


# ---------- Helpers ---------------------------------------------------------


def _clear_scene() -> None:
    """Remove every mesh/material so the script is idempotent across runs."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block, do_unlink=True)
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block, do_unlink=True)


def _make_material(name: str, rgba: tuple[float, float, float, float]) -> object:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def _add_box(
    name: str,
    *,
    centre: tuple[float, float, float],
    size: tuple[float, float, float],
    material: object,
) -> object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def _add_cylinder(
    name: str,
    *,
    centre: tuple[float, float, float],
    radius: float,
    depth: float,
    material: object,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> object:
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=depth,
        location=centre,
        rotation=rotation,
        vertices=24,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    return obj


# ---------- Chashitsu assembly ---------------------------------------------


def build_chashitsu() -> None:
    """Procedurally construct the chashitsu geometry in the active scene."""
    mat_wood_dark = _make_material("WoodDark", WOOD_DARK)
    mat_wood_light = _make_material("WoodLight", WOOD_LIGHT)
    mat_tatami = _make_material("Tatami", TATAMI)
    mat_shoji = _make_material("Shoji", SHOJI)
    mat_roof = _make_material("RoofTile", ROOF)
    mat_ash = _make_material("Ash", ASH)
    mat_clay = _make_material("ClayBowl", CLAY)

    # --- Footprint: 6 x 6 m, floor ~0.15 m thick ---
    half = 3.0
    floor_h = 0.15
    wall_h = 2.6
    roof_peak = 1.2  # additional rise above the eaves

    # Tatami floor (3 x 2 mat grid = 3 rows × 2 cols, each mat 1.0 m × 2.0 m).
    # Approximated as a single slab so the glb stays small; a future pass can
    # split it into six mats for correct wabi-sabi alignment.
    _add_box(
        "Floor",
        centre=(0.0, 0.0, floor_h / 2.0),
        size=(2.0 * half, 2.0 * half, floor_h),
        material=mat_tatami,
    )

    # --- Four corner posts ---
    post_size = (0.22, 0.22, wall_h)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _add_box(
                f"Post_{sx}_{sy}",
                centre=(sx * (half - 0.11), sy * (half - 0.11), floor_h + wall_h / 2.0),
                size=post_size,
                material=mat_wood_dark,
            )

    # --- Shoji walls (three sides; south side = open engawa) ---
    wall_thickness = 0.06
    walls = [
        # (name, centre_xy, size_xy)
        ("WallN", (0.0, half - wall_thickness / 2.0), (2.0 * half - 0.44, wall_thickness)),
        ("WallE", (half - wall_thickness / 2.0, 0.0), (wall_thickness, 2.0 * half - 0.44)),
        ("WallW", (-half + wall_thickness / 2.0, 0.0), (wall_thickness, 2.0 * half - 0.44)),
    ]
    for name, (cx, cy), (sx, sy) in walls:
        _add_box(
            name,
            centre=(cx, cy, floor_h + wall_h / 2.0),
            size=(sx, sy, wall_h - 0.1),
            material=mat_shoji,
        )

    # --- Tokonoma (床の間) — raised alcove on the north wall ---
    _add_box(
        "TokonomaBase",
        centre=(0.0, half - 0.8, floor_h + 0.10),
        size=(1.8, 0.9, 0.12),
        material=mat_wood_light,
    )
    _add_box(
        "TokonomaBackWall",
        centre=(0.0, half - 0.35, floor_h + wall_h / 2.0),
        size=(1.8, 0.05, wall_h - 0.2),
        material=mat_wood_dark,
    )

    # --- Hearth (囲炉裏 / 炉) — sunken ash square ---
    _add_box(
        "Hearth",
        centre=(0.0, 0.0, floor_h + 0.03),
        size=(0.6, 0.6, 0.06),
        material=mat_ash,
    )
    # Kettle (釜) — single squat cylinder on ash.
    _add_cylinder(
        "Kettle",
        centre=(0.0, 0.0, floor_h + 0.19),
        radius=0.18,
        depth=0.24,
        material=mat_wood_dark,
    )

    # --- Two tea bowls (茶碗) — short ceramic cylinders flanking the hearth ---
    for idx, (tx, ty) in enumerate([(-0.9, -0.4), (0.9, 0.4)]):
        _add_cylinder(
            f"TeaBowl_{idx}",
            centre=(tx, ty, floor_h + 0.05),
            radius=0.10,
            depth=0.08,
            material=mat_clay,
        )

    # --- Gabled roof — two pitched slabs meeting at the ridge ---
    eaves_z = floor_h + wall_h
    pitch = math.atan2(roof_peak, half)
    roof_half_length = (half + 0.4) / math.cos(pitch)
    # Slab dimensions: slightly wider than footprint so the overhang is visible.
    slab_size = (2.0 * roof_half_length, 2.0 * half + 0.8, 0.10)
    # East slab
    _add_box(
        "RoofEast",
        centre=(half / 2.0, 0.0, eaves_z + roof_peak / 2.0),
        size=(slab_size[0] / 2.0, slab_size[1], slab_size[2]),
        material=mat_roof,
    )
    bpy.context.active_object.rotation_euler = (0.0, -pitch, 0.0)
    # West slab
    _add_box(
        "RoofWest",
        centre=(-half / 2.0, 0.0, eaves_z + roof_peak / 2.0),
        size=(slab_size[0] / 2.0, slab_size[1], slab_size[2]),
        material=mat_roof,
    )
    bpy.context.active_object.rotation_euler = (0.0, pitch, 0.0)

    # --- Ridge beam for visual weight ---
    _add_box(
        "Ridge",
        centre=(0.0, 0.0, eaves_z + roof_peak - 0.02),
        size=(0.22, 2.0 * half + 0.9, 0.18),
        material=mat_wood_dark,
    )


# ---------- Export ----------------------------------------------------------


def export_glb() -> None:
    STAGING_OUT.parent.mkdir(parents=True, exist_ok=True)
    GODOT_OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(STAGING_OUT),
        export_format="GLB",
        export_apply=True,
    )
    shutil.copyfile(STAGING_OUT, GODOT_OUT)
    print(f"[export_chashitsu] wrote {STAGING_OUT.relative_to(REPO_ROOT)}")  # noqa: T201
    print(f"[export_chashitsu] copied to {GODOT_OUT.relative_to(REPO_ROOT)}")  # noqa: T201


def main() -> int:
    _clear_scene()
    build_chashitsu()
    export_glb()
    return 0


if __name__ == "__main__":
    sys.exit(main())
