#!/usr/bin/env python
"""Snapshot ``contracts.geometry.ZONE_CENTERS`` into a committed layout mirror.

M13 M4 situated-3D — Issue 002 (I2) of the FROZEN M4 impl-design ADR
(``.steering/20260711-m13-m4-impl-design/design-final.md`` §6 配置権威座標 snapshot).

The SSOT authority for zone placement is
:data:`erre_sandbox.contracts.geometry.ZONE_CENTERS`. The Godot environment
(``.tscn`` roots, geometry-nodes ``.glb`` placement) mirrors those coordinates,
so a drift between them silently breaks the deterministic replay witness. This
pure-Python tool writes the authority table to a committed canonical JSON mirror
(``godot_project/assets/environment/zone_layout.json``) that the M4 tests diff
against, closing the drift with a 6-decimal canonical exact contract.

This is a **construction** tool, not a measurement line: the emitted mirror is a
reproducibility snapshot of the authority coordinates, never a floor / landscape
/ verdict / ``D_*`` statistic (R-budget stays 0). It is **bpy-free / non-GPL**
(本体 Apache/MIT side, ``scripts/`` placement per MEDIUM-4) — it imports only
``contracts.geometry`` + stdlib and never touches the live ``WorldLayoutMsg``
wire path.

Run ``python scripts/export_zone_layout.py`` to (re)generate the committed
mirror; the output is idempotent (a re-run byte-matches the committed file).

Serialisation follows the handoff canonical discipline
(``integration/embodied/handoff.py``): every float is quantised to
:data:`CANONICAL_FLOAT_DECIMALS` decimals (platform-independent ``round``,
absorbing sub-ULP cross-platform ``libm`` drift), keys are sorted, separators are
compact, ``allow_nan`` is ``False``, and the file ends with a trailing newline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from erre_sandbox.contracts.geometry import WORLD_SIZE_M, ZONE_CENTERS

CANONICAL_FLOAT_DECIMALS: Final[int] = 6
"""Decimals every emitted float is quantised to (mirrors handoff.py)."""

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
OUTPUT_PATH: Final[Path] = (
    _REPO_ROOT / "godot_project" / "assets" / "environment" / "zone_layout.json"
)
"""Committed canonical mirror the M4 tests diff against (design §6)."""

WORLD_SIZE_KEY: Final[str] = "world_size_m"
"""Reserved top-level key carrying the terrain edge length (metres)."""


def _quantize(obj: Any) -> Any:
    """Recursively round every float to :data:`CANONICAL_FLOAT_DECIMALS`.

    ``round`` uses CPython's correctly-rounded dtoa (platform-independent), so
    the same authority value serialises to identical bytes on every machine —
    the handoff.py cross-platform-drift discipline, ported (not imported) so this
    tool stays dependency-light and bpy-free.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, CANONICAL_FLOAT_DECIMALS)
    if isinstance(obj, dict):
        return {k: _quantize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_quantize(v) for v in obj]
    return obj


def build_layout() -> dict[str, Any]:
    """Assemble the layout mirror dict from the authority table.

    Content = ``{zone_name: [x, y, z]}`` for the five zones (keyed by
    ``Zone`` enum value) plus the reserved ``world_size_m`` scalar. The Zazen
    locus is not a zone (design §7) and is intentionally absent.
    """
    layout: dict[str, Any] = {
        zone.value: [float(x), float(y), float(z)]
        for zone, (x, y, z) in ZONE_CENTERS.items()
    }
    layout[WORLD_SIZE_KEY] = float(WORLD_SIZE_M)
    return layout


def canonical_dumps(obj: Any) -> str:
    """Serialise ``obj`` under the handoff canonical rules (single line + newline).

    Quantise floats, then ``sort_keys`` + compact ``separators`` +
    ``ensure_ascii=False`` + ``allow_nan=False`` so a byte-identical re-emission
    is a reproducibility witness (non-finite floats raise).
    """
    return (
        json.dumps(
            _quantize(obj),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def render_layout_text() -> str:
    """Render the committed mirror's exact file text (pure, no side-effect)."""
    return canonical_dumps(build_layout())


def main() -> None:
    """Write the canonical mirror to :data:`OUTPUT_PATH` (idempotent)."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_layout_text(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
