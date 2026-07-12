"""M4 situated-3D — Issue 006 (I6): headless placement-dump verification.

Machine-checks (AC2/AC3/AC4, design-final-ref.md §4 / §3.4) that the landed
``SocietyReplayViewer.gd`` (I5, read-only here) replays the committed N-body
society substrate **deterministically, in ``order_slot`` order, following the
committed trace**:

* **I6-G1 / AC2 (causal wiring)** — ``test_headless_dump_matches_expected``:
  run the viewer headless (``--manifest --trace --stream --dump=<tmp>``),
  normalise every dump line through handoff ``canonical_dumps`` and byte-compare
  to the committed ``expected_placement.jsonl``. The N=2 avatars resolve in
  ``order_slot`` order to their trace ``(x, y, z, yaw)``; live WS / LLM are never
  contacted (offline golden only).
* **I6-G2 / AC3 (reproducibility)** — ``test_dump_deterministic``: two headless
  runs over the same golden produce byte-identical (normalised) dumps, both
  equal to the committed expected.
* **I6-G3 / AC4 (5-zone load)** — ``test_scene_loads_five_zones``: headless-load
  ``SocietyReplayScene.tscn`` and assert exactly 5 zone nodes load (Study /
  Peripatos / Chashitsu / Agora / Garden), Zazen absent (it is an ERRE mode, not
  a Zone). Boolean only.
* **I6-G4 (idempotent expected)** — ``test_expected_placement_idempotent``:
  regenerate the expected列 from the golden via the pure-Python
  :func:`build_expected_placement` and byte-compare to the committed file (no
  Godot needed — deterministic derivation).

HIGH-3 (Codex): a Godot runtime float→str is NOT a cross-machine byte witness.
The witness is the committed trace value echoed pass-through by the viewer; the
Python side canonicalises (6-decimal quantisation + ``sort_keys`` + compact +
``allow_nan=False``) both the dump and the expected列 before comparing, so
cross-platform ``libm`` drift below half a quantum is absorbed
(``feedback_golden_crossplatform_float_drift``).

Construction, not measurement: the placement byte-comparison is a
**reproducibility witness** (peer of handoff ``ecl_trace_checksum``), never a
metric / floor / verdict / scorer. Godot binary is resolved via
``resolve_godot()`` (``GODOT_BIN`` / known Mac path / PATH); absent → skip.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Final

import pytest

from erre_sandbox.integration.embodied.handoff import canonical_dumps
from tests._godot_helpers import (
    GODOT_PROJECT,
    HEADLESS_TIMEOUT_SEC,
    resolve_godot,
)

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_GOLDEN_DIR: Final = _REPO_ROOT / "tests" / "fixtures" / "m2_society_golden"
_TRACE_PATH: Final = _GOLDEN_DIR / "ecl_trace.jsonl"
_STREAM_PATH: Final = _GOLDEN_DIR / "envelope_stream.jsonl"
_MANIFEST_PATH: Final = _GOLDEN_DIR / "manifest.json"
_EXPECTED_PATH: Final = _GOLDEN_DIR / "expected_placement.jsonl"

_VIEWER_RES: Final = "res://scripts/dev/SocietyReplayViewer.gd"
_SCENE_RES: Final = "res://scenes/dev/SocietyReplayScene.tscn"

# Only speech / animation fire here — ``move`` is a motive record, not a position
# authority (design-final-ref.md §3.3). Mirrors ``SocietyReplayViewer.FIRING_KINDS``.
_FIRING_KINDS: Final[frozenset[str]] = frozenset({"speech", "animation"})

_EXPECTED_PLACEMENT_ROWS: Final = 40  # 2 order_slots × 20 physics ticks
_EXPECTED_ENVELOPE_ROWS: Final = 16  # speech 8 + animation 8 (move excluded)


# --------------------------------------------------------------------------- #
# Pure-Python expected列 derivation (Godot-independent, deterministic).
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def build_expected_placement(trace_path: Path, stream_path: Path) -> str:
    """Derive the committed expected列 from the golden artifacts.

    Placement rows come from ``ecl_trace.jsonl`` (motion authority, physics_tick
    clock) sorted by ``(physics_tick_index, order_slot)``; envelope rows come
    from ``envelope_stream.jsonl`` (speech / animation only, agent_tick clock)
    sorted by ``(order_slot, agent_tick, seq)``. Each row is serialised with the
    same canonical discipline the viewer's dump is normalised through, so the two
    are byte-identical when the replay is faithful. Placements first, then
    envelopes; trailing newline (matches the viewer's per-line dump).
    """
    placements: list[dict[str, Any]] = [
        {
            "kind": "placement",
            "physics_tick_index": int(row["physics_tick_index"]),
            "order_slot": int(row["order_slot"]),
            "x": row["x"],
            "y": row["y"],
            "z": row["z"],
            "yaw": row["yaw"],
            "zone": row["zone"],
        }
        for row in _read_jsonl(trace_path)
    ]
    placements.sort(key=lambda d: (d["physics_tick_index"], d["order_slot"]))

    envelopes: list[dict[str, Any]] = []
    for row in _read_jsonl(stream_path):
        envelope = row["envelope"]
        kind = envelope["kind"]
        if kind not in _FIRING_KINDS:
            continue
        envelopes.append(
            {
                "kind": "envelope",
                "order_slot": int(row["order_slot"]),
                "agent_tick": int(row["agent_tick"]),
                "seq": int(row["seq"]),
                "envelope_kind": kind,
            }
        )
    envelopes.sort(key=lambda d: (d["order_slot"], d["agent_tick"], d["seq"]))

    return "".join(f"{canonical_dumps(row)}\n" for row in (*placements, *envelopes))


# --------------------------------------------------------------------------- #
# Godot headless helpers.
# --------------------------------------------------------------------------- #
def _normalise_dump(text: str) -> str:
    """Canonicalise each dump line (HIGH-3): parse the Godot JSON, re-serialise
    with the handoff rules so the byte witness is the committed value, never the
    Godot runtime float→str representation."""
    lines = [line for line in text.splitlines() if line.strip()]
    return "".join(f"{canonical_dumps(json.loads(line))}\n" for line in lines)


def _run_viewer_dump(godot: Path, dump_path: Path) -> str:
    """Run the viewer headless over the committed golden, return the raw dump."""
    # All argv from known locations (resolve_godot path, fixed project path,
    # committed fixtures, tmp dump path) — no user-supplied input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "--script",
            _VIEWER_RES,
            "--",
            f"--manifest={_MANIFEST_PATH}",
            f"--trace={_TRACE_PATH}",
            f"--stream={_STREAM_PATH}",
            f"--dump={dump_path}",
        ],
        capture_output=True,
        text=True,
        timeout=HEADLESS_TIMEOUT_SEC,
        check=False,
    )
    assert result.returncode == 0, (
        f"viewer headless dump failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ERROR:" not in result.stderr, (
        f"viewer emitted runtime errors:\n{result.stderr}"
    )
    return dump_path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# I6-G1 — AC2 causal wiring.
# --------------------------------------------------------------------------- #
@pytest.mark.godot
def test_headless_dump_matches_expected(tmp_path: Path) -> None:
    """AC2: normalised headless dump == committed expected_placement.jsonl.

    N=2 avatars resolve in ``order_slot`` order to their committed trace poses;
    offline golden only (no live WS / LLM)."""
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    dump_text = _run_viewer_dump(godot, tmp_path / "placement_dump.jsonl")
    normalised = _normalise_dump(dump_text)

    expected = _EXPECTED_PATH.read_text(encoding="utf-8")
    assert normalised == expected, "headless dump diverged from committed expected列"

    lines = normalised.splitlines()
    placements = [
        json.loads(line) for line in lines if json.loads(line)["kind"] == "placement"
    ]
    envelopes = [
        json.loads(line) for line in lines if json.loads(line)["kind"] == "envelope"
    ]
    assert len(placements) == _EXPECTED_PLACEMENT_ROWS
    assert len(envelopes) == _EXPECTED_ENVELOPE_ROWS

    # N=2 avatars, resolved in order_slot order within each physics tick.
    slots_at_tick0 = [
        p["order_slot"] for p in placements if p["physics_tick_index"] == 0
    ]
    assert slots_at_tick0 == [0, 1]


# --------------------------------------------------------------------------- #
# I6-G2 — AC3 reproducibility.
# --------------------------------------------------------------------------- #
@pytest.mark.godot
def test_dump_deterministic(tmp_path: Path) -> None:
    """AC3: two headless runs over the same golden are byte-identical (normalised)
    and both equal the committed expected列."""
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    first = _normalise_dump(_run_viewer_dump(godot, tmp_path / "dump_a.jsonl"))
    second = _normalise_dump(_run_viewer_dump(godot, tmp_path / "dump_b.jsonl"))
    assert first == second, "repeat headless dumps diverged (non-deterministic)"
    assert first == _EXPECTED_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# I6-G3 — AC4 5-zone load (boolean).
# --------------------------------------------------------------------------- #
@pytest.mark.godot
def test_scene_loads_five_zones(tmp_path: Path) -> None:
    """AC4: the dev scene loads exactly 5 zone nodes; Zazen is absent."""
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    smoke = tmp_path / "scene_load_smoke.gd"
    smoke.write_text(
        "extends SceneTree\n"
        "func _init() -> void:\n"
        f'\tvar packed := load("{_SCENE_RES}")\n'
        "\tif packed == null:\n"
        '\t\tpush_error("scene failed to load")\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        "\tvar scene: Node = packed.instantiate()\n"
        "\tif scene == null:\n"
        '\t\tpush_error("scene failed to instantiate")\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        '\tvar zones := ["Study", "Peripatos", "Chashitsu", "Agora", "Garden"]\n'
        "\tvar found := 0\n"
        "\tfor zname: String in zones:\n"
        "\t\tif scene.has_node(NodePath(zname)):\n"
        "\t\t\tfound += 1\n"
        '\tvar has_zazen := scene.has_node(NodePath("Zazen"))\n'
        "\tscene.free()\n"
        "\tif found != 5:\n"
        '\t\tpush_error("expected 5 zone nodes, got %d" % found)\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        "\tif has_zazen:\n"
        '\t\tpush_error("Zazen must not be present")\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        '\tprint("SCENE_OK zones=%d" % found)\n'
        "\tquit(0)\n",
        encoding="utf-8",
    )

    # All argv from known locations (resolve_godot path, fixed project path,
    # tmp_path written by this test) — no user-supplied input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "--script",
            str(smoke),
        ],
        capture_output=True,
        text=True,
        timeout=HEADLESS_TIMEOUT_SEC,
        check=False,
    )
    assert result.returncode == 0, (
        f"scene-load smoke failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ERROR:" not in result.stderr, (
        f"scene-load smoke emitted runtime errors:\n{result.stderr}"
    )
    assert "SCENE_OK zones=5" in result.stdout


# --------------------------------------------------------------------------- #
# I6-G4 — idempotent expected列 (no Godot needed).
# --------------------------------------------------------------------------- #
def test_expected_placement_idempotent() -> None:
    """AC I6-G4: regenerating expected_placement.jsonl from the golden via the
    pure-Python derivation byte-matches the committed file (deterministic)."""
    regenerated = build_expected_placement(_TRACE_PATH, _STREAM_PATH)
    assert regenerated == _EXPECTED_PATH.read_text(encoding="utf-8")

    lines = regenerated.splitlines()
    assert len([line for line in lines if '"kind":"placement"' in line]) == (
        _EXPECTED_PLACEMENT_ROWS
    )
    assert len([line for line in lines if '"kind":"envelope"' in line]) == (
        _EXPECTED_ENVELOPE_ROWS
    )
