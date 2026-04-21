# erre-sandbox-blender

GPL-3.0 **separate package** containing every `.blend` source file and every
script that imports `bpy`. This directory must stay outside the Apache-2.0
OR MIT core at `../src/erre_sandbox/` — see `../docs/architecture.md` and
the `architecture-rules` skill for the legal rationale.

## What lives here

```
erre-sandbox-blender/
├── README.md                     # this file
├── LICENSE                       # GPL-3.0 (full text)
├── blends/                       # hand-authored .blend source files
│   └── chashitsu_v1.blend        # M6-C (pending manual authoring; scripted fallback in scripts/)
├── scripts/                      # headless export drivers
│   └── export_chashitsu.py       # procedural chashitsu builder + glb export
└── exports/                      # generated .glb artefacts (git-ignored)
```

## Usage

### Headless export (M6-C chashitsu)

```bash
# From the repo root. Blender 4.x required on PATH.
blender --background --python erre-sandbox-blender/scripts/export_chashitsu.py
```

The script:

1. Wipes the default scene
2. Procedurally builds a 6×6×3.5 m chashitsu with wooden posts, shoji-paper
   walls, tatami floor, tokonoma (床の間), hearth, and two tea bowls
3. Exports to `erre-sandbox-blender/exports/chashitsu_v1.glb`
4. **Copies the file** into
   `godot_project/assets/environment/chashitsu_v1.glb` so Godot can load
   it on the next scene reload

Re-running the script is idempotent. Output diff is zero when no authoring
has changed; a non-zero diff means the script (or a dependency) shifted —
commit the new `.glb` alongside whichever source changed.

### Manual authoring

Open `blends/chashitsu_v1.blend` in Blender for hand-tuning. When you are
happy, re-export with `Export ▸ glTF 2.0 (.glb)`, destination
`../godot_project/assets/environment/`. Keep the hand-authored file in
`blends/` as the source of truth; do not edit the generated `.glb` directly.

## Why a separate package?

Blender is GPL-2+. Any Python module that `import bpy` is a derivative work
of Blender and therefore GPL-2+. Mixing such code into the Apache-2.0 OR
MIT `src/erre_sandbox/` would force the **entire** `erre-sandbox` to
relicense. Keeping the GPL code physically separated is how the project
preserves its dual license.

See `../.claude/skills/architecture-rules/SKILL.md` §"GPL 分離" for the
enforcement rule (Claude Code refuses to write `import bpy` into
`src/erre_sandbox/`).

## Runtime boundary

At runtime, the Godot viewer and the Python cognition loop both load the
`.glb` artefact — they never invoke Blender. The only process that ever
holds `bpy` in memory is this package's export scripts. That keeps the
Apache-2.0 OR MIT binary produced by `uv build` free of GPL-tainted code.
