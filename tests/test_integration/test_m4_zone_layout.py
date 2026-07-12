"""M4 situated-3D — Issue 002 (I2): zone-layout / drift / GLB-JSON parser ACs.

Issue ``loop/20260711-m13-m4-code/issues/002-zone-layout-tooling.md`` of the
FROZEN M4 impl-design ADR. AC4 下地 (layout mirror + ``.tscn`` root drift close +
Zone enum 網羅) and the I3/I4 GLB-JSON parser's fail-closed contract (AC I2-G4).

Construction, not measurement: every check here is a 6-decimal canonical *exact*
equality between the ``contracts.geometry`` authority and its Godot mirror
(``.tscn`` roots / ``zone_layout.json``) — a reproducibility witness, never a
floor / verdict / ``D_*`` statistic (tolerance is forbidden, MEDIUM-3).
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any, Final

import pytest

from erre_sandbox.contracts.geometry import WORLD_SIZE_M, ZONE_CENTERS
from erre_sandbox.schemas import Zone
from tests._glb_json import (
    GlbParseError,
    extract_fingerprint,
    glb_fingerprint,
    read_glb_json_chunk,
)

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_LAYOUT_PATH: Final[Path] = (
    _REPO_ROOT / "godot_project" / "assets" / "environment" / "zone_layout.json"
)
_ZONES_DIR: Final[Path] = _REPO_ROOT / "godot_project" / "scenes" / "zones"
_CANONICAL_DECIMALS: Final[int] = 6
_WORLD_SIZE_KEY: Final[str] = "world_size_m"

# The five zones in declaration order (Zone enum), used to assert exact coverage.
_EXPECTED_ZONE_VALUES: Final[list[str]] = [
    "study",
    "peripatos",
    "chashitsu",
    "agora",
    "garden",
]


def _q(value: float) -> float:
    """6-decimal canonical quantisation (the exact-comparison basis)."""
    return round(value, _CANONICAL_DECIMALS)


# --------------------------------------------------------------------------- #
# I2-G1 — zone_layout.json mirrors ZONE_CENTERS (6-decimal canonical exact)
# --------------------------------------------------------------------------- #


def test_m4_zone_layout_matches_zone_centers() -> None:
    """AC I2-G1: the committed mirror equals ``ZONE_CENTERS`` for all five zones
    (canonical 6-decimal exact) plus the reserved ``world_size_m`` scalar."""
    data = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))

    assert set(data) == {z.value for z in Zone} | {_WORLD_SIZE_KEY}
    assert len(ZONE_CENTERS) == 5

    for zone in Zone:
        expected = [_q(c) for c in ZONE_CENTERS[zone]]
        assert data[zone.value] == expected, zone.value

    assert data[_WORLD_SIZE_KEY] == _q(WORLD_SIZE_M)


# --------------------------------------------------------------------------- #
# I2-G2 — each zone .tscn root transform matches the authority (drift closed)
# --------------------------------------------------------------------------- #

_TRANSFORM_RE: Final = re.compile(r"transform = Transform3D\(([^)]*)\)")
_SECTION_RE: Final = re.compile(r"(?m)^\[[^\]]*\]")


def _root_origin(tscn_path: Path) -> tuple[float, float, float]:
    """Return the root ``Node3D``'s translation (last three Transform3D args).

    The root node is the ``[node ...]`` section with no ``parent=`` attribute; a
    root with no ``transform`` line is the identity (origin ``(0, 0, 0)``). Only
    the root section is parsed — child-mesh relative coordinates are untouched.
    """
    text = tscn_path.read_text(encoding="utf-8")
    headers = list(_SECTION_RE.finditer(text))
    for i, header in enumerate(headers):
        head = header.group(0)
        if not head.startswith("[node ") or "parent=" in head:
            continue
        body_start = header.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        match = _TRANSFORM_RE.search(text[body_start:body_end])
        if match is None:
            return (0.0, 0.0, 0.0)
        nums = [float(v.strip()) for v in match.group(1).split(",")]
        return (nums[-3], nums[-2], nums[-1])
    msg = f"no root node found in {tscn_path.name}"
    raise AssertionError(msg)


def test_m4_tscn_root_matches_authority() -> None:
    """AC I2-G2: every zone ``.tscn`` root translation equals ``ZONE_CENTERS``
    at 6-decimal canonical exact (no tolerance) — the ``33.33`` drift is closed
    to ``33.333333``."""
    for zone in Zone:
        tscn = _ZONES_DIR / f"{zone.value.capitalize()}.tscn"
        assert tscn.is_file(), tscn
        origin = tuple(_q(c) for c in _root_origin(tscn))
        expected = tuple(_q(c) for c in ZONE_CENTERS[zone])
        assert origin == expected, zone.value


# --------------------------------------------------------------------------- #
# I2-G3 — Zone enum is exactly the five zones; Zazen is not a zone
# --------------------------------------------------------------------------- #


def test_m4_zone_enum_exactly_five_no_zazen() -> None:
    """AC I2-G3: ``Zone`` enumerates exactly the five spatial zones and never
    ``zazen`` (a ``.tscn`` scaffold, not a zone — design §7)."""
    values = [z.value for z in Zone]
    assert values == _EXPECTED_ZONE_VALUES
    assert len(Zone) == 5
    assert "zazen" not in values

    # The Zazen scaffold exists on disk but is deliberately outside the zone set.
    assert (_ZONES_DIR / "Zazen.tscn").is_file()
    assert not any(z.value == "zazen" for z in Zone)


# --------------------------------------------------------------------------- #
# I2-G4 — the pure GLB-JSON parser is fail-closed (HIGH-1 / HIGH-2)
# --------------------------------------------------------------------------- #


def _clean_gltf() -> dict[str, Any]:
    """A minimal, well-formed glTF-JSON dict (one mesh, one POSITION accessor)."""
    return {
        "asset": {"version": "2.0"},
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": 0}]}],
        "accessors": [
            {
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "bufferView": 0,
                "min": [-1.0, 0.0, -1.0],
                "max": [1.0, 2.0, 1.0],
            }
        ],
        "materials": [{"name": "zone_surface"}],
        "bufferViews": [{"buffer": 0, "byteLength": 36, "byteOffset": 0}],
        "buffers": [{"byteLength": 36}],
    }


def _make_glb(gltf: dict[str, Any]) -> bytes:
    """Wrap a glTF-JSON dict in a minimal binary ``.glb`` container (JSON chunk)."""
    payload = json.dumps(gltf).encode("utf-8")
    payload += b" " * ((-len(payload)) % 4)  # 4-byte align (spaces)
    total = 12 + 8 + len(payload)
    header = struct.pack("<III", 0x46546C67, 2, total)
    chunk = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    return header + chunk


def test_m4_glb_json_parser_reads_clean_fingerprint() -> None:
    """Positive control: a clean glTF yields the expected mesh-local fingerprint,
    both from a dict and round-tripped through synthetic ``.glb`` bytes."""
    expected = {
        "mesh_count": 1,
        "materials": ["zone_surface"],
        "positions": [{"count": 3, "min": [-1.0, 0.0, -1.0], "max": [1.0, 2.0, 1.0]}],
    }
    assert extract_fingerprint(_clean_gltf()) == expected
    assert glb_fingerprint(_make_glb(_clean_gltf())) == expected
    assert read_glb_json_chunk(_make_glb(_clean_gltf()))["asset"]["version"] == "2.0"


def _with(**overrides: Any) -> dict[str, Any]:
    gltf = _clean_gltf()
    gltf.update(overrides)
    return gltf


def test_m4_glb_json_parser_fail_closed() -> None:
    """AC I2-G4: each HIGH-1 / HIGH-2 violation raises :class:`GlbParseError`.

    HIGH-1 = non-identity node transform (matrix / translation / rotation /
    scale); HIGH-2 = Draco / meshopt compression, external buffer uri, or a
    sparse POSITION accessor. Verified on synthetic glTF-JSON dicts.
    """
    # HIGH-1: non-identity node transforms.
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(nodes=[{"mesh": 0, "translation": [1.0, 0.0, 0.0]}]))
    with pytest.raises(GlbParseError):
        extract_fingerprint(
            _with(nodes=[{"mesh": 0, "matrix": [2.0, *[0.0] * 14, 1.0]}])
        )
    with pytest.raises(GlbParseError):
        extract_fingerprint(
            _with(nodes=[{"mesh": 0, "rotation": [0.0, 0.7071, 0.0, 0.7071]}])
        )
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(nodes=[{"mesh": 0, "scale": [2.0, 2.0, 2.0]}]))

    # HIGH-2: mesh compression (top-level required / used, and per-primitive).
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(extensionsRequired=["KHR_draco_mesh_compression"]))
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(extensionsUsed=["EXT_meshopt_compression"]))
    draco_primitive = {
        "attributes": {"POSITION": 0},
        "extensions": {"KHR_draco_mesh_compression": {"bufferView": 0}},
    }
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(meshes=[{"primitives": [draco_primitive]}]))

    # HIGH-2: external buffer uri (a non-``data:`` reference).
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(buffers=[{"uri": "geometry.bin", "byteLength": 36}]))

    # HIGH-2: sparse-only POSITION accessor.
    sparse_accessor = {
        "componentType": 5126,
        "count": 3,
        "type": "VEC3",
        "bufferView": 0,
        "min": [0.0, 0.0, 0.0],
        "max": [1.0, 1.0, 1.0],
        "sparse": {"count": 1},
    }
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[sparse_accessor]))


def _position_accessor(**overrides: Any) -> dict[str, Any]:
    """A concrete, well-formed POSITION accessor, mutated per negative case."""
    accessor: dict[str, Any] = {
        "componentType": 5126,
        "count": 3,
        "type": "VEC3",
        "bufferView": 0,
        "min": [-1.0, 0.0, -1.0],
        "max": [1.0, 2.0, 1.0],
    }
    accessor.update(overrides)
    return accessor


def test_m4_glb_json_parser_position_concrete_fail_closed() -> None:
    """AC I2-G4 (design §1.3 HIGH-2 完全実装): a POSITION accessor that does not
    resolve to a concrete plain bufferView is fail-closed.

    Covers the sparse-only cases (missing ``bufferView`` / dangling
    ``bufferView`` / dangling buffer) plus the malformed-structure cases
    (non-``VEC3`` type / non-positive ``count`` / ``min`` not length-3), each of
    which would make the mesh-local min/max the fingerprint hashes non-authoritative.
    """
    # bufferView missing entirely (sparse-only without a plain buffer).
    no_view = _position_accessor()
    del no_view["bufferView"]
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[no_view]))

    # bufferView index out of range.
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[_position_accessor(bufferView=9)]))

    # bufferView present but its buffer index dangles.
    with pytest.raises(GlbParseError):
        extract_fingerprint(
            _with(
                accessors=[_position_accessor()],
                bufferViews=[{"buffer": 7, "byteLength": 36}],
            )
        )

    # type != VEC3 (min/max would not be a 3-vector bbox).
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[_position_accessor(type="SCALAR")]))

    # count == 0 (no vertices behind the bounds).
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[_position_accessor(count=0)]))

    # min not length-3.
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[_position_accessor(min=[0.0, 0.0])]))

    # max element non-numeric.
    with pytest.raises(GlbParseError):
        extract_fingerprint(_with(accessors=[_position_accessor(max=[1.0, "2", 1.0])]))


def test_m4_glb_json_parser_bytes_fail_closed() -> None:
    """The binary reader is fail-closed on a corrupt GLB container (bad magic)."""
    good = _make_glb(_clean_gltf())
    with pytest.raises(GlbParseError):
        read_glb_json_chunk(b"XXXX" + good[4:])
    with pytest.raises(GlbParseError):
        read_glb_json_chunk(b"too short")
