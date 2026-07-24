"""Issue 005 (M13 live-loop-closure): Godot inbound wire-contract guards.

Pure-Python, always-on-in-CI guards for the Godot-side half of the inbound
seam (``.steering/20260724-m13-live-loop-closure/design-final.md`` Issue
005). No Godot binary is required — both checks are regex extraction over
the committed ``.gd`` source, mirroring ``test_envelope_kind_sync.py``'s
extract-and-diff idiom (and ``test_inbound.py``'s "duplicate the small
extraction technique locally rather than importing test-internal helpers
across files" convention).

* AC2 — ``test_gdscript_perturbation_frame_matches_inbound_schema``:
  ``WebSocketClient.gd::send_perturbation``'s payload ``Dictionary`` key set
  matches :class:`~erre_sandbox.schemas.WorldPerturbationMsg`'s
  ``model_fields`` exactly (the ``_EnvelopeBase`` header fields
  ``schema_version`` / ``tick`` / ``sent_at`` included) — so a frame built by
  that GDScript function is exactly what the Python
  :data:`~erre_sandbox.schemas.InboundEnvelope` adapter validates.
* AC3 — ``test_router_does_not_receive_inbound_kind``: ``EnvelopeRouter.gd``'s
  ``on_envelope_received`` match block does **not** grow a
  ``"world_perturbation"`` arm (LOW-2, design-final.md DA-2) — Godot sends
  this frame, it never receives one back.

Godot binary is not needed for either check; a live ``headless-godot`` send
test is out of scope for this issue (grill G3: environment-gated, deferred to
the Godot-capable machine) — the pure-Python contract guard is preferred over
forcing that here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from erre_sandbox.schemas import WorldPerturbationMsg

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
WEBSOCKET_CLIENT_GD: Final = (
    REPO_ROOT / "godot_project" / "scripts" / "WebSocketClient.gd"
)
ROUTER_GD: Final = REPO_ROOT / "godot_project" / "scripts" / "EnvelopeRouter.gd"

# Scope extraction to the body of ``send_perturbation`` so unrelated
# Dictionary literals elsewhere in WebSocketClient.gd (e.g. the client
# handshake payload) cannot contaminate the key set.
_SEND_PERTURBATION_RE = re.compile(
    r"func\s+send_perturbation\b[\s\S]*?(?=\nfunc\s|\Z)",
    re.MULTILINE,
)
# Further scope to the ``var payload := { ... }`` block within that function.
_PAYLOAD_BLOCK_RE = re.compile(r"var\s+payload\s*:=\s*\{([\s\S]*?)\n\t\}", re.MULTILINE)
# Each payload entry is ``"key": <value>,`` on its own line (unlike the
# router's bare ``"kind_name":`` match-arm lines, these carry a value after
# the colon on the same line) — match the quoted key regardless of what
# follows.
_PAYLOAD_KEY_RE = re.compile(r'"([a-z_]+)"\s*:', re.MULTILINE)

# Mirrors test_envelope_kind_sync.py's ``_ROUTER_MATCH_KEY_RE`` /
# ``_ROUTER_DISPATCH_RE`` exactly (same extraction technique, duplicated
# locally per test_inbound.py's cross-file convention).
_ROUTER_MATCH_KEY_RE = re.compile(r'^\s*"([a-z_]+)"\s*:\s*$', re.MULTILINE)
_ROUTER_DISPATCH_RE = re.compile(
    r"func\s+on_envelope_received\b[\s\S]*?(?=\nfunc\s|\Z)",
    re.MULTILINE,
)


def _gdscript_perturbation_payload_keys() -> set[str]:
    """Extract the ``Dictionary`` key set ``send_perturbation`` sends over the wire."""
    source = WEBSOCKET_CLIENT_GD.read_text(encoding="utf-8")
    func_match = _SEND_PERTURBATION_RE.search(source)
    if func_match is None:
        msg = "WebSocketClient.gd lacks a ``send_perturbation`` function."
        raise AssertionError(msg)
    payload_match = _PAYLOAD_BLOCK_RE.search(func_match.group(0))
    if payload_match is None:
        msg = "send_perturbation lacks a ``var payload := { ... }`` block."
        raise AssertionError(msg)
    return set(_PAYLOAD_KEY_RE.findall(payload_match.group(1)))


def _gdscript_router_kinds() -> set[str]:
    """Extract match-arm ``kind`` literals from ``on_envelope_received``."""
    source = ROUTER_GD.read_text(encoding="utf-8")
    dispatch_match = _ROUTER_DISPATCH_RE.search(source)
    if dispatch_match is None:
        msg = "EnvelopeRouter.gd lacks an ``on_envelope_received`` function body."
        raise AssertionError(msg)
    return set(_ROUTER_MATCH_KEY_RE.findall(dispatch_match.group(0)))


def test_gdscript_perturbation_frame_matches_inbound_schema() -> None:
    """AC2: send_perturbation's frame key set == WorldPerturbationMsg's fields.

    A byte-for-byte key match means a frame ``send_perturbation`` builds is
    exactly what :func:`pydantic.TypeAdapter(InboundEnvelope).validate_python`
    accepts — no gdscript-side field drift (missing/extra/misnamed key) can
    silently ship.
    """
    gdscript_keys = _gdscript_perturbation_payload_keys()
    python_keys = set(WorldPerturbationMsg.model_fields.keys())
    missing_in_gdscript = python_keys - gdscript_keys
    missing_in_python = gdscript_keys - python_keys
    assert gdscript_keys == python_keys, (
        f"WorldPerturbationMsg frame drift detected.\n"
        f"  python-only (missing from gdscript payload): "
        f"{sorted(missing_in_gdscript)}\n"
        f"  gdscript-only (unknown to WorldPerturbationMsg): "
        f"{sorted(missing_in_python)}\n"
        f"Update WebSocketClient.gd::send_perturbation's payload dict so its "
        f"keys match WorldPerturbationMsg.model_fields exactly."
    )


def test_router_does_not_receive_inbound_kind() -> None:
    """AC3 (LOW-2): EnvelopeRouter.gd never gains a ``world_perturbation`` arm.

    ``WorldPerturbationMsg`` is client -> server only (design-final.md DA-2).
    Godot sends it via ``send_perturbation`` but must never be taught to
    receive one back — the router's ``on_envelope_received`` match block
    only ever carries the (unchanged, ``test_envelope_kind_sync.py``-pinned)
    outbound ``ControlEnvelope`` kinds.
    """
    router_kinds = _gdscript_router_kinds()
    assert "world_perturbation" not in router_kinds
