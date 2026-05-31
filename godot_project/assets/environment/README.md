# `assets/environment/` — zone 3D environment `.glb` artefacts

Static 3D background geometry for each zone. Authored in the separate
GPL-3.0 package `../../erre-sandbox-blender/` and copied here as `.glb`
so the Apache-2.0 OR MIT core can load them without any GPL inheritance.

## Expected files

| File                  | Source script                                                   | Zone       |
|-----------------------|-----------------------------------------------------------------|------------|
| `chashitsu_v1.glb`    | `erre-sandbox-blender/scripts/export_chashitsu.py`              | chashitsu  |
| *(future M7)*         | `erre-sandbox-blender/scripts/export_study.py`                  | study      |
| *(future M7)*         | `erre-sandbox-blender/scripts/export_agora.py`                  | agora      |
| *(future M7)*         | `erre-sandbox-blender/scripts/export_garden.py`                 | garden     |

Peripatos stays Godot-primitive-only (a long colonnade is cheap enough
that the Blender pipeline would be overkill — see
`godot_project/scenes/zones/Peripatos.tscn`).

## How scenes consume these

`godot_project/scenes/zones/Chashitsu.tscn` declares the `.glb` as an
optional `ext_resource`. If the file is absent (CI without the export
step, fresh checkout before the Blender run), the scene keeps its
PlaneMesh ground and simply omits the `.glb` child. So you can clone the
repo and boot Godot before ever touching Blender.

## Regeneration

```bash
blender --background --python erre-sandbox-blender/scripts/export_chashitsu.py
```

Produces `chashitsu_v1.glb` in this directory (and a staging copy inside
the GPL package). Re-running is idempotent.
