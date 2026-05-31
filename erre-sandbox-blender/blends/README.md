# `blends/` — hand-authored Blender source files

Put `.blend` source files here. The procedural export scripts in
`../scripts/` can also write finished scenes here if you want to edit the
procedural output by hand before re-exporting.

Naming: `{zone_or_asset}_v{n}.blend`. Bump `v{n}` for breaking changes to
the outer scale or pivot — callers in `godot_project/scenes/` key on the
filename so a drop-in replacement keeps backward compatibility.

## M6-C: chashitsu_v1.blend (pending)

The chashitsu is currently produced parametrically by
`../scripts/export_chashitsu.py`. The hand-tuned `.blend` lands when the
researcher wants to customise beyond the primitive geometry (tatami mat
alignment, shoji wood lattice, clay-texture bowls). Until then, the
scripted path is the source of truth.
