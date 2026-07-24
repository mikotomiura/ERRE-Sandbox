"""M13 Godot traversal rendering — the two-layer witness (S2 + S4).

FROZEN ADR ``.steering/20260723-m13-godot-traversal-rendering/design-final.md``
(§4 sampling invariant / §5 witness / §7 acceptance). Machine-checks that the
committed aha-traversal golden can be rendered as a walked itinerary
**deterministically and faithfully**:

* **AC1** — ``test_derivation_is_deterministic`` / ``test_sampling_rule_*``:
  ``scripts/aha_traversal_render_derive.py`` decimates the raw 30 Hz physics
  record into a keyframe series twice byte-identically, and every one of the 6
  hard sampling rules (ADR §4, Codex HIGH-3) holds on the result.
* **AC2** — ``test_route_from_positions_matches_expected`` plus the four
  ``test_route_witness_teeth_*`` negatives: the visit sequence recomputed from
  keyframe **positions** equals the frozen
  :data:`~erre_sandbox.integration.embodied.traversal_live.TRAVERSAL_EXPECTED_ROUTE`,
  and a truncated / reordered / coordinate-corrupted / under-simulated series
  makes it differ (so the match is not vacuous, Codex HIGH-2).
* **AC3** — ``test_committed_render_fixtures_regenerate`` /
  ``test_render_manifest_pins_source_and_size``: the committed derivatives are
  re-derived from the raw trace and byte-compared, their manifest's
  ``source_trace_sha256`` matches the raw trace's actual digest (staleness gate,
  Codex HIGH-1) and the derived stream stays under the viewer's input bound
  (Codex MEDIUM-1).
* **AC4** (``@pytest.mark.godot``, self-skipping) —
  ``test_headless_keyframe_dump_matches_expected`` /
  ``test_traversal_scene_loads_five_zones``: the Godot viewer's headless dump,
  canonicalised in Python, byte-matches the committed expected dump, and the
  traversal scene loads 5 zone nodes plus the single ``Avatar0``.

**Anti-tautology (Codex HIGH-2)**: every zone in the route witness is
recomputed from ``(x, z)`` via
:func:`~erre_sandbox.contracts.geometry.locate_zone`. The keyframes' committed
``zone`` label is carried for the viewer to display and is **never read** by a
check here — ``test_route_witness_teeth_corrupted_coordinates`` proves it by
corrupting coordinates while leaving every label intact and asserting the route
still changes.

**HIGH-3 (Codex)**: a Godot runtime float→str is not a cross-machine byte
witness, so the AC4 comparison canonicalises the dump in Python (handoff
``canonical_dumps``: 6-decimal quantisation + ``sort_keys`` + compact +
``allow_nan=False``) before comparing — cross-platform ``libm`` drift below half
a quantum is absorbed (``feedback_golden_crossplatform_float_drift``).

**Honest framing (ADR §0, AC6)**: what is rendered is a *scripted golden
traversal replay* — a recorded walk played back. Construction, not measurement:
every assertion here is boolean/exact reproducibility or an exact-match route
identity, never an effect, a structural limit, an adjudication or an aha proxy.
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest

from erre_sandbox.contracts.geometry import locate_zone
from erre_sandbox.integration.embodied.handoff import canonical_dumps
from erre_sandbox.integration.embodied.traversal_live import TRAVERSAL_EXPECTED_ROUTE
from tests._godot_helpers import (
    GODOT_PROJECT,
    HEADLESS_TIMEOUT_SEC,
    resolve_godot,
)

if TYPE_CHECKING:
    from types import ModuleType

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_DERIVE_PATH: Final = _REPO_ROOT / "scripts" / "aha_traversal_render_derive.py"

_VIEWER_RES: Final = "res://scripts/dev/TraversalReplayViewer.gd"
_SCENE_RES: Final = "res://scenes/dev/TraversalReplayScene.tscn"

# The golden's window length — one cognition tick's physics ticks. Used only to
# build the under-simulation negative tooth (a deliberately short window).
_PHYSICS_TICKS_PER_COGNITION: Final = 2000
_UNDERSHOOT_WINDOW_TICKS: Final = 500


def _load_derive() -> ModuleType:
    """Import the derivation tool from ``scripts/`` (not an installed package)."""
    spec = importlib.util.spec_from_file_location(
        "aha_traversal_render_derive", _DERIVE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


derive: Final = _load_derive()


@pytest.fixture(scope="module")
def raw_rows() -> list[dict[str, Any]]:
    """The committed golden's raw 30 Hz physics record (read-only)."""
    return derive.read_trace_rows()


@pytest.fixture(scope="module")
def keyframes(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The derived keyframe series under the pinned sampling policy."""
    return derive.build_keyframes(raw_rows)


def _expected_route() -> tuple[str, ...]:
    """The frozen itinerary as plain zone values (the harness's own constant)."""
    return tuple(zone.value for zone in TRAVERSAL_EXPECTED_ROUTE)


# --------------------------------------------------------------------------- #
# AC1 — deterministic derivation + the 6 hard sampling rules (ADR §4).
# --------------------------------------------------------------------------- #
def test_derivation_is_deterministic(raw_rows: list[dict[str, Any]]) -> None:
    """AC1: deriving twice from the same raw trace is byte-identical."""
    first = derive.keyframe_jsonl(derive.build_keyframes(raw_rows))
    second = derive.keyframe_jsonl(derive.build_keyframes(raw_rows))
    assert first == second


def test_sampling_rule_1_first_and_last_row(
    raw_rows: list[dict[str, Any]], keyframes: list[dict[str, Any]]
) -> None:
    """Rule 1: the first and last physics rows are always keyframes."""
    ticks = {k["physics_tick_index"] for k in keyframes}
    assert raw_rows[0]["physics_tick_index"] in ticks
    assert raw_rows[-1]["physics_tick_index"] in ticks


def test_sampling_rule_2_end_of_every_cognition_tick(
    raw_rows: list[dict[str, Any]], keyframes: list[dict[str, Any]]
) -> None:
    """Rule 2: every cognition tick's last physics row is a keyframe.

    This is the route witness's sampling point, so a missing one would silently
    drop a leg from the visit sequence.
    """
    end_of_tick: dict[int, int] = {}
    for row in raw_rows:
        end_of_tick[int(row["agent_tick"])] = int(row["physics_tick_index"])
    ticks = {k["physics_tick_index"] for k in keyframes}
    assert set(end_of_tick.values()) <= ticks
    assert set(end_of_tick) == {k["agent_tick"] for k in keyframes}


def test_sampling_rule_3_leg_endpoints_are_kept(
    raw_rows: list[dict[str, Any]], keyframes: list[dict[str, Any]]
) -> None:
    """Rule 3: both rows bracketing a position-derived zone change are kept."""
    ticks = {k["physics_tick_index"] for k in keyframes}
    previous = locate_zone(float(raw_rows[0]["x"]), 0.0, float(raw_rows[0]["z"]))
    crossings = 0
    for index in range(1, len(raw_rows)):
        row = raw_rows[index]
        zone = locate_zone(float(row["x"]), 0.0, float(row["z"]))
        if zone is not previous:
            crossings += 1
            assert int(raw_rows[index - 1]["physics_tick_index"]) in ticks
            assert int(row["physics_tick_index"]) in ticks
            previous = zone
    # Non-vacuous: the frozen itinerary really does cross zones (5 legs, plus
    # the transient Voronoi triple-point clips the continuous path makes).
    assert crossings >= len(TRAVERSAL_EXPECTED_ROUTE) - 1


def test_sampling_rule_4_baseline_interval(keyframes: list[dict[str, Any]]) -> None:
    """Rule 4: the pinned stride ``K`` samples the record between the above."""
    ticks = {k["physics_tick_index"] for k in keyframes}
    stride = derive.KEYFRAME_INTERVAL_TICKS
    assert stride >= 1
    assert {t for t in ticks if t % stride == 0} == set(
        range(0, max(ticks) + 1, stride)
    )


def test_sampling_rule_5_monotonic_and_continuous(
    keyframes: list[dict[str, Any]],
) -> None:
    """Rule 5: strictly increasing clock, bounded gap, bounded spatial/yaw step."""
    for previous, current in pairwise(keyframes):
        gap = current["physics_tick_index"] - previous["physics_tick_index"]
        assert gap > 0, "physics_tick_index must strictly increase"
        assert gap <= derive.KEYFRAME_INTERVAL_TICKS, "keyframe gap exceeded K"
        step = math.dist(
            (float(previous["x"]), float(previous["z"])),
            (float(current["x"]), float(current["z"])),
        )
        assert step <= derive.MAX_KEYFRAME_STEP_M, "spatial discontinuity"
        yaw_step = abs(
            math.remainder(float(current["yaw"]) - float(previous["yaw"]), math.tau)
        )
        assert yaw_step <= derive.MAX_KEYFRAME_YAW_STEP_RAD, "yaw discontinuity"


def test_sampling_rule_6_poses_are_echoed_not_recomputed(
    raw_rows: list[dict[str, Any]], keyframes: list[dict[str, Any]]
) -> None:
    """Rule 6: every emitted pose is the raw row's value, unchanged."""
    by_tick = {int(row["physics_tick_index"]): row for row in raw_rows}
    for keyframe in keyframes:
        row = by_tick[int(keyframe["physics_tick_index"])]
        for field in ("x", "y", "z", "yaw"):
            assert keyframe[field] == row[field], field
        assert keyframe["zone"] == row["zone"]
        assert keyframe["agent_tick"] == row["agent_tick"]
        assert keyframe["order_slot"] == row["order_slot"]


# --------------------------------------------------------------------------- #
# AC2 — position-derived route witness + its four negative teeth (HIGH-2).
# --------------------------------------------------------------------------- #
def test_route_from_positions_matches_expected(
    keyframes: list[dict[str, Any]],
) -> None:
    """AC2: the zone sequence recomputed from ``(x, z)`` is the frozen route."""
    assert derive.visit_sequence_from_keyframes(keyframes) == _expected_route()


def test_route_witness_teeth_truncated_final_leg(
    keyframes: list[dict[str, Any]],
) -> None:
    """Tooth (i): dropping the last leg's keyframes must break the match."""
    last_tick = max(int(k["agent_tick"]) for k in keyframes)
    truncated = [k for k in keyframes if int(k["agent_tick"]) < last_tick]
    assert derive.visit_sequence_from_keyframes(truncated) != _expected_route()


def test_route_witness_teeth_reordered_keyframes(
    keyframes: list[dict[str, Any]],
) -> None:
    """Tooth (ii): replaying the series out of order must break the match."""
    assert derive.visit_sequence_from_keyframes(list(reversed(keyframes))) != (
        _expected_route()
    )


def test_route_witness_teeth_corrupted_coordinates(
    keyframes: list[dict[str, Any]],
) -> None:
    """Tooth (iii): corrupt the positions, keep every committed label intact.

    This is the anti-tautology proof (Codex HIGH-2): if the route witness read
    the committed ``zone`` label it would still match; because it recomputes the
    zone from the (now mirrored) coordinates, it does not.
    """
    corrupted = [{**k, "x": -float(k["x"]), "z": -float(k["z"])} for k in keyframes]
    assert [k["zone"] for k in corrupted] == [k["zone"] for k in keyframes], (
        "the labels must survive untouched — that is what makes this a proof"
    )
    assert derive.visit_sequence_from_keyframes(corrupted) != _expected_route()


def test_route_witness_teeth_under_simulated_window(
    raw_rows: list[dict[str, Any]],
) -> None:
    """Tooth (iv): too few physics ticks per leg (the agent never arrives).

    Mirrors ``test_traversal_undershoot_fails_route``: keeping only the first
    ``500`` physics rows of each ``2000``-tick cognition window leaves the agent
    mid-flight on the long legs, so the end-of-tick zones are not the itinerary.
    """
    short = [
        row
        for row in raw_rows
        if int(row["physics_tick_index"]) % _PHYSICS_TICKS_PER_COGNITION
        < _UNDERSHOOT_WINDOW_TICKS
    ]
    assert short, "the under-simulation slice must not be empty"
    under = derive.build_keyframes(short)
    assert derive.visit_sequence_from_keyframes(under) != _expected_route()


# --------------------------------------------------------------------------- #
# AC3 — committed derivatives regenerate from the raw trace (HIGH-1 / MEDIUM-1).
# --------------------------------------------------------------------------- #
def test_committed_render_fixtures_regenerate(
    keyframes: list[dict[str, Any]],
) -> None:
    """AC3: both committed derivatives are re-derived byte-identically.

    The raw ``ecl_trace.jsonl`` stays the single truth source; a derivative that
    drifted from it (or a raw trace edited without regenerating) fails here.
    """
    dump_text = derive.keyframe_jsonl(keyframes)
    assert dump_text == derive.EXPECTED_DUMP_PATH.read_text(encoding="utf-8")

    manifest_text = derive.render_manifest_json(
        derive.build_render_manifest(keyframes, dump_text)
    )
    assert manifest_text == derive.RENDER_MANIFEST_PATH.read_text(encoding="utf-8")


def test_render_manifest_pins_source_and_size(
    keyframes: list[dict[str, Any]],
) -> None:
    """AC3: staleness gate (source digest) + the input-bound assertion."""
    manifest = json.loads(derive.RENDER_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["source_trace_sha256"] == derive.source_trace_sha256()
    assert manifest["keyframe_count"] == len(keyframes)

    dump_bytes = derive.EXPECTED_DUMP_PATH.read_bytes()
    assert manifest["keyframe_byte_size"] == len(dump_bytes)
    assert len(dump_bytes) < derive.MAX_RENDER_INPUT_BYTES, (
        "the derived stream must stay under the viewer's defensive read bound"
    )
    # The manifest states the policy the committed derivative was produced under.
    assert manifest["sampling_interval_ticks"] == derive.KEYFRAME_INTERVAL_TICKS
    assert manifest["sampling_rules"] == list(derive.SAMPLING_RULES)
    assert manifest["visit_sequence"] == list(_expected_route())


# --------------------------------------------------------------------------- #
# AC4 — Godot headless witness (self-skipping when no binary is installed).
# --------------------------------------------------------------------------- #
def _normalise_dump(text: str) -> str:
    """Canonicalise each dump line in Python (HIGH-3), never trusting Godot's
    own float→str rendering as the byte witness."""
    lines = [line for line in text.splitlines() if line.strip()]
    return "".join(f"{canonical_dumps(json.loads(line))}\n" for line in lines)


@pytest.mark.godot
def test_headless_keyframe_dump_matches_expected(tmp_path: Path) -> None:
    """AC4: the viewer's headless dump == the committed expected dump."""
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    keyframes_path = tmp_path / "render_keyframes.jsonl"
    dump_path = tmp_path / "keyframe_dump.jsonl"
    exit_code = derive.main(["--emit", str(keyframes_path)])
    assert exit_code == 0

    # All argv from known locations (resolve_godot path, fixed project path,
    # tmp paths written by this test) — no user-supplied input.
    result = subprocess.run(  # noqa: S603
        [
            str(godot),
            "--path",
            str(GODOT_PROJECT),
            "--headless",
            "--script",
            _VIEWER_RES,
            "--",
            f"--keyframes={keyframes_path}",
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

    normalised = _normalise_dump(dump_path.read_text(encoding="utf-8"))
    assert normalised == derive.EXPECTED_DUMP_PATH.read_text(encoding="utf-8")


@pytest.mark.godot
def test_traversal_scene_loads_five_zones(tmp_path: Path) -> None:
    """AC4: the traversal scene loads 5 zone nodes and the single ``Avatar0``.

    Zazen is an ERRE mode, not a Zone, so it must be absent; the traversal
    golden records one agent, so exactly one avatar node is expected.
    """
    godot = resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; see docs for setup instructions")

    smoke = tmp_path / "traversal_scene_load_smoke.gd"
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
        '\tvar has_avatar := scene.has_node(NodePath("Avatar0"))\n'
        '\tvar has_second := scene.has_node(NodePath("Avatar1"))\n'
        "\tscene.free()\n"
        "\tif found != 5:\n"
        '\t\tpush_error("expected 5 zone nodes, got %d" % found)\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        "\tif has_zazen:\n"
        '\t\tpush_error("Zazen must not be present")\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        "\tif not has_avatar or has_second:\n"
        '\t\tpush_error("expected exactly one avatar node (Avatar0)")\n'
        "\t\tquit(1)\n"
        "\t\treturn\n"
        '\tprint("TRAVERSAL_SCENE_OK zones=%d" % found)\n'
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
    assert "TRAVERSAL_SCENE_OK zones=5" in result.stdout
