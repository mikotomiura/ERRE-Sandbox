"""M4 situated-3D — Issue 003 (I3): committed ``.glb`` structural fingerprint AC.

Issue ``loop/20260711-m13-m4-code/issues/003-peripatos-glb-pipeline.md`` of the
FROZEN M4 impl-design ADR (``loop/20260711-m13-m4-code/design-final-ref.md`` §1.3
決定性契約 二層 witness). This module is the **CI-side** half of the determinism
contract: it reads a committed geometry-nodes ``.glb``, recomputes its structural
fingerprint through the bpy-free pure parser (``tests/_glb_json.py``), and diffs
it byte-for-byte against a committed ``<zone>_v1.fingerprint.json`` sidecar. Both
inputs are committed artefacts, so this test is green in CI without Blender.

The developer-side half (same-machine ``.glb`` byte idempotency) lives in
``erre-sandbox-blender/scripts/run.sh`` (Blender required, not a CI gate).

Construction, not measurement: the fingerprint is a **reproducibility witness**
(structure only — mesh count, POSITION accessor vertex counts, mesh-local bbox,
material names) quantised to 6 decimals to absorb cross-platform ``libm`` ULP
drift. It is never a floor / landscape / ``D_*`` statistic (R-budget stays 0).

I3 lands the ``peripatos`` row; I4 appends the remaining four zones by extending
:data:`_ZONES` (the parametrised skeleton keeps the per-zone body identical).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from tests._glb_json import extract_fingerprint, glb_fingerprint, read_glb_json_chunk

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_ENV_DIR: Final[Path] = _REPO_ROOT / "godot_project" / "assets" / "environment"
_CANONICAL_DECIMALS: Final[int] = 6

# Zones whose committed geometry-nodes ``.glb`` + fingerprint this test covers.
# I3 landed {peripatos}; I4 appended study / chashitsu / agora / garden (all five
# baked from seed-free geometry-nodes exporters under the identical determinism
# contract, so the parametrised body stays zone-agnostic).
_ZONES: Final[tuple[str, ...]] = (
    "peripatos",
    "study",
    "chashitsu",
    "agora",
    "garden",
)


def _glb_path(zone: str) -> Path:
    return _ENV_DIR / f"{zone}_v1.glb"


def _fingerprint_path(zone: str) -> Path:
    return _ENV_DIR / f"{zone}_v1.fingerprint.json"


# --------------------------------------------------------------------------- #
# Canonical fingerprint (handoff.py discipline: 6-decimal quantise + sort_keys +
# compact + allow_nan=False + trailing newline). bpy-free, aggregation-free.
# --------------------------------------------------------------------------- #


def _quantize(obj: Any) -> Any:
    """Recursively round every float to :data:`_CANONICAL_DECIMALS` decimals."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, _CANONICAL_DECIMALS)
    if isinstance(obj, dict):
        return {k: _quantize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_quantize(v) for v in obj]
    return obj


def canonical_dumps(obj: Any) -> str:
    """Serialise under the handoff canonical rules (single line + trailing NL)."""
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


def _bbox(positions: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Element-wise (x, y, z) min/max aggregated across every POSITION accessor.

    Plain builtin ``min`` / ``max`` over ``zip`` of the per-accessor bounds — no
    numpy / statistics aggregation surface (construction guard, design §11).
    """
    axis_mins = list(zip(*(p["min"] for p in positions), strict=True))
    axis_maxs = list(zip(*(p["max"] for p in positions), strict=True))
    return {
        "min": [min(axis) for axis in axis_mins],
        "max": [max(axis) for axis in axis_maxs],
    }


def fingerprint_from_glb(data: bytes) -> dict[str, Any]:
    """Structural fingerprint dict from a binary ``.glb`` (fail-closed via parser).

    Content = ``{mesh_count, total_vertex_count, bbox:{min, max}, materials:[sorted
    names]}`` — the design §1.3 sidecar shape, derived from the pure parser's
    mesh-local structure (mesh count / POSITION accessor counts + bounds / material
    names).
    """
    parsed = glb_fingerprint(data)
    positions = parsed["positions"]
    return {
        "mesh_count": parsed["mesh_count"],
        "total_vertex_count": sum(p["count"] for p in positions),
        "bbox": _bbox(positions),
        "materials": sorted(m for m in parsed["materials"]),
    }


def render_fingerprint_text(data: bytes) -> str:
    """Canonical committed-file text for a ``.glb``'s structural fingerprint."""
    return canonical_dumps(fingerprint_from_glb(data))


# --------------------------------------------------------------------------- #
# I3-G1 / I4-G1 — committed .glb fingerprint recomputes byte-identically
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("zone", _ZONES)
def test_zone_fingerprint(zone: str) -> None:
    """AC I3-G1 / I4-G1: recomputing the committed ``<zone>_v1.glb`` fingerprint
    through the pure parser byte-matches the committed
    ``<zone>_v1.fingerprint.json`` (all five zones)."""
    glb_path = _glb_path(zone)
    fingerprint_path = _fingerprint_path(zone)
    assert glb_path.is_file(), glb_path
    assert fingerprint_path.is_file(), fingerprint_path

    recomputed = render_fingerprint_text(glb_path.read_bytes())
    committed = fingerprint_path.read_text(encoding="utf-8")
    assert recomputed == committed, zone


# --------------------------------------------------------------------------- #
# I3-G2 / I4-G1 — the real .glb does NOT trip the parser's fail-closed paths
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("zone", _ZONES)
def test_zone_glb_not_fail_closed(zone: str) -> None:
    """AC I3-G2 / I4-G1: the committed ``<zone>_v1.glb`` passes every HIGH-1 / HIGH-2
    precondition — identity node transforms, no Draco / meshopt compression, no
    external buffer, no sparse POSITION — proving the exporter honoured the
    identity + uncompressed contract (dual to I2-G4's synthetic fail-closed)."""
    data = _glb_path(zone).read_bytes()
    gltf = read_glb_json_chunk(data)

    # The parser fingerprint call runs all fail-closed guards; it must not raise.
    fingerprint = extract_fingerprint(gltf)
    assert fingerprint["mesh_count"] >= 1, zone
    assert fingerprint["positions"], zone

    # Explicit structural evidence the exporter kept the contract.
    for node in gltf.get("nodes", []):
        assert "matrix" not in node, zone
        assert "translation" not in node, zone
        assert "rotation" not in node, zone
        assert "scale" not in node, zone
    for key in ("extensionsUsed", "extensionsRequired"):
        for name in gltf.get(key, []):
            assert "compression" not in name.lower(), zone
    for buffer in gltf.get("buffers", []):
        uri = buffer.get("uri")
        assert uri is None or uri.startswith("data:"), zone
