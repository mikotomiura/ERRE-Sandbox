"""M4 situated-3D — Issue 001 (I1): GPL/SPDX boundary guard.

Issue ``loop/20260711-m13-m4-code/issues/001-measurement-gpl-guard.md`` of the
FROZEN M4 impl-design ADR ``.steering/20260711-m13-m4-impl-design/design-final.md``
(§8 SPDX GPL header, §11 不可侵 GPL 分離). Machine guarantee that the GPL boundary
is intact:

* every ``erre-sandbox-blender/**/*.py`` (GPL-3.0-or-later, ``import bpy``) carries
  an SPDX header near the top (§8: 既存 header 欠を是正);
* the Apache-2.0-OR-MIT core ``src/erre_sandbox/**/*.py`` never imports ``bpy``
  (GPL must not be dragged into the core);
* the non-GPL M4 tooling (``scripts/export_zone_layout.py`` + the ``tests/``
  GLB-JSON parser) is ``bpy``-free (pure-python GLB-JSON parse, no Blender dep).

Pure text/AST scan — no ``bpy`` import needed to run these tests, so they run in
CI without Blender installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_SPDX_GPL: Final = "SPDX-License-Identifier: GPL-3.0-or-later"
_HEADER_WINDOW: Final = 15  # SPDX must appear within the first N lines


def _imports_bpy(path: Path) -> bool:
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.lstrip()
        if stripped.startswith(("import bpy", "from bpy")):
            return True
    return False


# --------------------------------------------------------------------------- #
# I1-G5 — every GPL (blender) python file has an SPDX GPL header
# --------------------------------------------------------------------------- #


def test_m4_gpl_header_present() -> None:
    """AC I1-G5: every ``erre-sandbox-blender/**/*.py`` file declares
    ``SPDX-License-Identifier: GPL-3.0-or-later`` within its first lines."""
    blender_root = _REPO_ROOT / "erre-sandbox-blender"
    py_files = sorted(blender_root.rglob("*.py"))
    assert py_files, "expected at least one erre-sandbox-blender/**/*.py file"

    offenders: list[str] = []
    for path in py_files:
        head = path.read_text(encoding="utf-8").splitlines()[:_HEADER_WINDOW]
        if not any(_SPDX_GPL in line for line in head):
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert not offenders, (
        "GPL blender python files missing the SPDX header "
        f"({_SPDX_GPL!r}) within the first {_HEADER_WINDOW} lines:\n"
        + "\n".join(f"  {p}" for p in offenders)
    )


# --------------------------------------------------------------------------- #
# I1-G6 — the core is bpy-free, and the M4 non-GPL tooling is bpy-free
# --------------------------------------------------------------------------- #


def test_m4_no_bpy_in_core() -> None:
    """AC I1-G6: ``src/erre_sandbox/**/*.py`` never imports ``bpy`` (GPL stays out
    of the Apache/MIT core), and the M4 non-GPL GLB-JSON tooling
    (``scripts/export_zone_layout.py`` + the ``tests/`` GLB parser) is bpy-free."""
    src_root = _REPO_ROOT / "src" / "erre_sandbox"
    src_offenders = [
        str(p.relative_to(_REPO_ROOT))
        for p in sorted(src_root.rglob("*.py"))
        if _imports_bpy(p)
    ]
    assert not src_offenders, (
        "src/erre_sandbox/ must not import bpy (GPL boundary); offenders:\n"
        + "\n".join(f"  {p}" for p in src_offenders)
    )

    # The M4 non-GPL tooling must parse GLB via pure-python JSON, never via bpy.
    tooling = [
        _REPO_ROOT / "scripts" / "export_zone_layout.py",
        _REPO_ROOT / "tests" / "_glb_json.py",
    ]
    tool_offenders = [
        str(p.relative_to(_REPO_ROOT))
        for p in tooling
        if p.is_file() and _imports_bpy(p)
    ]
    assert not tool_offenders, (
        "M4 non-GPL GLB tooling must be bpy-free (pure-python GLB-JSON parse);"
        " offenders:\n" + "\n".join(f"  {p}" for p in tool_offenders)
    )
