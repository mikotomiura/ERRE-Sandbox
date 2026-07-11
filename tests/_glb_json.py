"""Pure GLB-JSON parser helper for the M4 fingerprint tests (Issue 002, I2).

M13 M4 situated-3D — Issue 002 of the FROZEN M4 impl-design ADR
(``.steering/20260711-m13-m4-impl-design/design-final.md`` §1.3 純 GLB-JSON
パーサ). The I3/I4 ``.glb`` fingerprint tests read a committed geometry-nodes
``.glb``, recompute its structural fingerprint through this helper, and diff it
against a committed fingerprint. This module supplies that reader.

**bpy-free / non-GPL** (leading-underscore filename → pytest does not collect it
as a test): it only parses the glTF *JSON chunk* of a binary ``.glb`` and reads
structural metadata (``accessor.count`` / POSITION ``accessor.min`` / ``max`` /
material names / mesh count). It never decodes the binary buffer, never imports
``bpy``, and computes no measurement surface — the fingerprint is a
reproducibility witness, not a metric.

Fail-closed discipline (design §1.3, Codex HIGH-1 / HIGH-2):

* **HIGH-1** — any non-identity glTF node transform (``matrix`` /
  ``translation`` / ``rotation`` / ``scale`` off its default) raises. The
  fingerprint compares *mesh-local* POSITION accessor min/max, so a node that
  moves geometry would make the witness lie; a non-identity node is a Stop, not
  a silently-hashed value.
* **HIGH-2** — ``KHR_draco_mesh_compression`` / ``EXT_meshopt_compression``
  (mesh compression makes accessor min/max non-authoritative), an external
  buffer ``uri`` (data outside the committed ``.glb``), or a sparse POSITION
  accessor (data not in the plain bufferView the min/max describe) each raise.
"""

from __future__ import annotations

import json
import struct
from typing import Any, Final

_GLB_MAGIC: Final[int] = 0x46546C67  # b"glTF" little-endian
_GLB_VERSION: Final[int] = 2
_CHUNK_TYPE_JSON: Final[int] = 0x4E4F534A  # b"JSON"
_GLB_HEADER_LEN: Final[int] = 12
_CHUNK_HEADER_LEN: Final[int] = 8

_IDENTITY_MATRIX: Final[tuple[float, ...]] = (
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
)
_DEFAULT_TRANSLATION: Final[tuple[float, ...]] = (0.0, 0.0, 0.0)
_DEFAULT_ROTATION: Final[tuple[float, ...]] = (0.0, 0.0, 0.0, 1.0)
_DEFAULT_SCALE: Final[tuple[float, ...]] = (1.0, 1.0, 1.0)

_COMPRESSION_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {"KHR_draco_mesh_compression", "EXT_meshopt_compression"}
)


class GlbParseError(ValueError):
    """Raised fail-closed when a ``.glb`` violates the fingerprint preconditions."""


def read_glb_json_chunk(data: bytes) -> dict[str, Any]:
    """Parse the glTF-JSON chunk of a binary ``.glb`` (binary buffer untouched).

    Validates the 12-byte GLB header (magic ``glTF`` / version 2) and reads the
    first chunk, which the glTF-Binary spec requires to be the JSON chunk. The
    trailing ``BIN`` chunk is never decoded. Raises :class:`GlbParseError` on any
    malformed header / chunk (fail-closed).
    """
    if len(data) < _GLB_HEADER_LEN:
        raise GlbParseError("truncated GLB header")
    magic, version, total_len = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC:
        raise GlbParseError(f"bad GLB magic: {magic:#010x}")
    if version != _GLB_VERSION:
        raise GlbParseError(f"unsupported GLB version: {version}")
    if total_len != len(data):
        raise GlbParseError(f"GLB length {total_len} != actual {len(data)}")
    if len(data) < _GLB_HEADER_LEN + _CHUNK_HEADER_LEN:
        raise GlbParseError("truncated first chunk header")
    chunk_len, chunk_type = struct.unpack_from("<II", data, _GLB_HEADER_LEN)
    if chunk_type != _CHUNK_TYPE_JSON:
        raise GlbParseError(f"first chunk is not JSON: {chunk_type:#010x}")
    start = _GLB_HEADER_LEN + _CHUNK_HEADER_LEN
    end = start + chunk_len
    if end > len(data):
        raise GlbParseError("JSON chunk overruns file")
    try:
        parsed: Any = json.loads(data[start:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlbParseError(f"invalid JSON chunk: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GlbParseError("JSON chunk is not an object")
    return parsed


def _as_floats(seq: Any) -> tuple[float, ...]:
    if not isinstance(seq, (list, tuple)):
        raise GlbParseError(f"expected a numeric array, got {type(seq).__name__}")
    return tuple(float(v) for v in seq)


def _assert_identity_nodes(gltf: dict[str, Any]) -> None:
    """HIGH-1: every node must carry an identity (or absent) transform."""
    for index, node in enumerate(gltf.get("nodes", [])):
        if "matrix" in node and _as_floats(node["matrix"]) != _IDENTITY_MATRIX:
            raise GlbParseError(f"node {index} has a non-identity matrix")
        if (
            "translation" in node
            and _as_floats(node["translation"]) != _DEFAULT_TRANSLATION
        ):
            raise GlbParseError(f"node {index} has a non-zero translation")
        if "rotation" in node and _as_floats(node["rotation"]) != _DEFAULT_ROTATION:
            raise GlbParseError(f"node {index} has a non-identity rotation")
        if "scale" in node and _as_floats(node["scale"]) != _DEFAULT_SCALE:
            raise GlbParseError(f"node {index} has a non-unit scale")


def _assert_no_compression(gltf: dict[str, Any]) -> None:
    """HIGH-2: reject Draco / meshopt compression (top-level or per-primitive)."""
    for key in ("extensionsUsed", "extensionsRequired"):
        for name in gltf.get(key, []):
            if name in _COMPRESSION_EXTENSIONS:
                raise GlbParseError(f"{key} declares compression extension {name!r}")
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            for name in primitive.get("extensions", {}):
                if name in _COMPRESSION_EXTENSIONS:
                    raise GlbParseError(
                        f"primitive uses compression extension {name!r}"
                    )


def _assert_no_external_buffers(gltf: dict[str, Any]) -> None:
    """HIGH-2: every buffer must be embedded (GLB ``BIN`` or ``data:`` URI)."""
    for index, buffer in enumerate(gltf.get("buffers", [])):
        uri = buffer.get("uri")
        if uri is not None and not uri.startswith("data:"):
            raise GlbParseError(f"buffer {index} references external uri {uri!r}")


def _position_accessor_indices(gltf: dict[str, Any]) -> list[int]:
    indices: list[int] = []
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            position = primitive.get("attributes", {}).get("POSITION")
            if position is not None:
                indices.append(int(position))
    return indices


def extract_fingerprint(gltf: dict[str, Any]) -> dict[str, Any]:
    """Return the structural fingerprint of a parsed glTF (fail-closed first).

    Runs the HIGH-1 / HIGH-2 preconditions, then reads mesh-local structure:
    ``mesh_count``, material names (in glTF order), and one entry per POSITION
    accessor carrying its ``count`` + ``min`` / ``max`` bounds. A sparse POSITION
    accessor raises (HIGH-2: its min/max would not describe the plain
    bufferView).
    """
    _assert_identity_nodes(gltf)
    _assert_no_compression(gltf)
    _assert_no_external_buffers(gltf)

    accessors = gltf.get("accessors", [])
    positions: list[dict[str, Any]] = []
    for accessor_index in _position_accessor_indices(gltf):
        accessor = accessors[accessor_index]
        if "sparse" in accessor:
            raise GlbParseError(
                f"POSITION accessor {accessor_index} is sparse (min/max not plain)"
            )
        positions.append(
            {
                "count": int(accessor["count"]),
                "min": list(accessor.get("min", [])),
                "max": list(accessor.get("max", [])),
            }
        )

    materials = [material.get("name") for material in gltf.get("materials", [])]
    return {
        "mesh_count": len(gltf.get("meshes", [])),
        "materials": materials,
        "positions": positions,
    }


def glb_fingerprint(data: bytes) -> dict[str, Any]:
    """Read a binary ``.glb`` and return its structural fingerprint (fail-closed).

    Convenience composition of :func:`read_glb_json_chunk` and
    :func:`extract_fingerprint` for the I3/I4 fingerprint tests.
    """
    return extract_fingerprint(read_glb_json_chunk(data))
