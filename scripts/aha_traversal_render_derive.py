#!/usr/bin/env python
"""Derive a Godot-renderable keyframe trace from the committed traversal golden.

M13 Godot traversal rendering — S1 of the FROZEN ADR
``.steering/20260723-m13-godot-traversal-rendering/design-final.md`` (§3 データ
フロー / §4 sampling invariant / §5 witness). Pure-Python: no Godot, no ``bpy``,
no network, no LLM.

**What this renders** (honest framing, ADR §0, binding): a **scripted golden
traversal replay**. The committed ``tests/fixtures/aha_traversal_golden/``
artifacts were produced by a *scripted* traversal harness
(``integration.embodied.traversal_live``) walking a pre-registered 5-leg
itinerary; visualising them shows a recorded walk being played back, **not**
emergence, not an "aha", not an effect. This tool is a *consumer* of that
golden and changes nothing about what the golden means.

**Why a derived keyframe trace at all** (ADR §2 DA-3): the raw
``ecl_trace.jsonl`` is a 30 Hz physics record (10000 rows / ~5.1 MB) — an order
of magnitude over the dev viewer's defensive input bound. This tool decimates it
to a keyframe series the viewer lerp-interpolates between, under the hard
sampling rules pinned in :data:`SAMPLING_RULES` (ADR §4, Codex HIGH-3), with
every emitted pose **echoed** from the raw row (never recomputed, so the raw
trace stays the single motion authority).

**SSOT discipline** (Codex HIGH-1, ADR §5(c)): the raw ``ecl_trace.jsonl`` is the
*only* truth source. The derived keyframe stream is regenerated on demand (tests
build it in ``tmp_path``); the only committed derivatives are the witness target
(``expected_keyframe_dump.jsonl``) plus a manifest recording
``source_trace_sha256`` / sampling policy / counts / byte size, and
``test_traversal_render.py`` re-derives both from the raw trace and byte-compares
— so a derivative can never silently go stale against its source.

**Construction, not measurement** (ADR §1, binding): this module computes and
emits no effect / divergence / structural-limit / adjudication / aha-proxy /
detectability surface. The one observable it exposes is the position-derived
zone-visit sequence (:func:`visit_sequence_from_keyframes`), an exact-match
boolean witness recomputed from ``(x, z)`` via
:func:`~erre_sandbox.contracts.geometry.locate_zone` — never a threshold.

Developer use::

    python scripts/aha_traversal_render_derive.py \\
        --emit /tmp/render_keyframes.jsonl \\
        --emit-manifest /tmp/render_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Final

from erre_sandbox.contracts.geometry import locate_zone
from erre_sandbox.integration.embodied.handoff import canonical_dumps

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

GOLDEN_DIR: Final[Path] = _REPO_ROOT / "tests" / "fixtures" / "aha_traversal_golden"
"""The committed traversal golden this tool consumes (read-only, byte-stable)."""

SOURCE_TRACE_PATH: Final[Path] = GOLDEN_DIR / "ecl_trace.jsonl"
"""The raw 30 Hz physics record — the single motion authority (HIGH-1)."""

RENDER_FIXTURE_DIR: Final[Path] = (
    _REPO_ROOT / "tests" / "fixtures" / "aha_traversal_render"
)
"""Committed witness targets, kept OUT of the golden dir (Codex MEDIUM-3)."""

EXPECTED_DUMP_PATH: Final[Path] = RENDER_FIXTURE_DIR / "expected_keyframe_dump.jsonl"
RENDER_MANIFEST_PATH: Final[Path] = RENDER_FIXTURE_DIR / "render_manifest.json"

KEYFRAME_INTERVAL_TICKS: Final[int] = 25
"""Rule 4's ``K``: baseline decimation stride over the 30 Hz physics record.

Literal-pinned (ADR §4): 10000 physics rows / K=25 = 400 baseline samples plus
the mandatory first/last, end-of-cognition-tick and leg-endpoint rows — a few
tens of kilobytes, two orders of magnitude under
:data:`MAX_RENDER_INPUT_BYTES`. At the golden's walking speed (~0.0433 m per
30 Hz tick) K=25 keeps adjacent keyframes ~1.1 m apart, well inside
:data:`MAX_KEYFRAME_STEP_M`, so the viewer's lerp between them is faithful.
"""

MAX_RENDER_INPUT_BYTES: Final[int] = 4_194_304
"""Defensive bound the derived stream must stay under (Codex MEDIUM-1).

Value-mirrors ``SocietyReplayViewer.MAX_INPUT_BYTES`` /
``TraversalReplayViewer.MAX_INPUT_BYTES`` (the viewer-side read bound). Mirrored
as a literal rather than shared because the authority lives in GDScript; the
M4 viewer's own constant is **not** modified by this task (ADR §2 DA-3).
"""

MAX_KEYFRAME_STEP_M: Final[float] = 2.0
"""Rule 5's spatial-continuity bound between adjacent keyframes (metres).

The golden's kinematics advance at most ~0.0433 m per physics tick, so K=25
implies ~1.1 m; 2.0 m leaves headroom without admitting a teleport (a dropped
leg would jump tens of metres). Pinned literally, never tuned to pass.
"""

MAX_KEYFRAME_YAW_STEP_RAD: Final[float] = math.pi
"""Rule 5's yaw-continuity bound between adjacent keyframes (radians, wrapped).

Heading may flip when a new leg starts, so the bound is the widest meaningful
wrapped delta (π) — it rejects only a non-finite / unwrappable yaw, which is
the failure this rule exists to catch on a flat-ground golden whose yaw is a
constant 0.0.
"""

SAMPLING_RULES: Final[tuple[str, ...]] = (
    "1. the first and last physics row are always keyframes",
    "2. the last physics row of every cognition tick (agent_tick) is a keyframe",
    "3. both rows bracketing a position-derived zone change are keyframes",
    f"4. otherwise every K={KEYFRAME_INTERVAL_TICKS} physics rows",
    "5. physics_tick_index strictly increasing, adjacent gap <= K, adjacent "
    f"spatial delta <= {MAX_KEYFRAME_STEP_M} m, wrapped yaw delta <= pi",
    "6. every emitted pose is echoed from the raw row, never recomputed",
)
"""The hard sampling rules (ADR §4 / Codex HIGH-3), pinned as data.

``test_traversal_render.py`` verifies each rule against the derived series, and
this tuple is copied verbatim into the render manifest so a committed
derivative always states the policy it was produced under.
"""

_POSE_KEYS: Final[tuple[str, ...]] = ("x", "y", "z", "yaw")
"""Raw-row pose fields echoed pass-through into a keyframe (rule 6)."""


class RenderDeriveError(RuntimeError):
    """The raw trace could not be decimated into a well-formed keyframe series."""


# --------------------------------------------------------------------------- #
# Raw trace input
# --------------------------------------------------------------------------- #
def read_trace_rows(trace_path: Path = SOURCE_TRACE_PATH) -> list[dict[str, Any]]:
    """Read the raw 30 Hz physics record, in file order.

    The golden is written in strictly increasing ``(agent_tick,
    physics_tick_index)`` order by the harness that produced it; this function
    does not re-sort (a re-sort would mask a corrupted source rather than let
    rule 5's monotonicity check catch it).
    """
    rows: list[dict[str, Any]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    if not rows:
        msg = f"empty raw trace: {trace_path}"
        raise RenderDeriveError(msg)
    return rows


def source_trace_sha256(trace_path: Path = SOURCE_TRACE_PATH) -> str:
    """SHA-256 of the raw trace bytes — the staleness gate (Codex HIGH-1)."""
    return hashlib.sha256(trace_path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Keyframe selection (ADR §4 sampling invariant)
# --------------------------------------------------------------------------- #
def select_keyframe_indices(
    rows: list[dict[str, Any]], *, interval: int = KEYFRAME_INTERVAL_TICKS
) -> list[int]:
    """Row indices retained as keyframes, ascending (rules 1-4).

    Rule 3's zone change is computed from the row **position** via
    :func:`~erre_sandbox.contracts.geometry.locate_zone`, never from the row's
    committed ``zone`` label — the same anti-tautology discipline the route
    witness follows (Codex HIGH-2), so a corrupted coordinate moves the leg
    endpoints rather than silently keeping the label's ones.
    """
    if interval < 1:
        msg = f"keyframe interval must be >= 1, got {interval}"
        raise RenderDeriveError(msg)

    keep: set[int] = {0, len(rows) - 1}  # rule 1
    keep.update(range(0, len(rows), interval))  # rule 4

    last_index_of_tick: dict[int, int] = {}
    for index, row in enumerate(rows):
        last_index_of_tick[int(row["agent_tick"])] = index
    keep.update(last_index_of_tick.values())  # rule 2

    previous_zone = locate_zone(float(rows[0]["x"]), 0.0, float(rows[0]["z"]))
    for index in range(1, len(rows)):
        zone = locate_zone(float(rows[index]["x"]), 0.0, float(rows[index]["z"]))
        if zone is not previous_zone:
            keep.update((index - 1, index))  # rule 3
            previous_zone = zone
    return sorted(keep)


def build_keyframes(
    rows: list[dict[str, Any]], *, interval: int = KEYFRAME_INTERVAL_TICKS
) -> list[dict[str, Any]]:
    """Decimate the raw rows into the keyframe series the viewer replays.

    Each keyframe echoes the raw row's pose verbatim (rule 6) plus the clock
    fields the viewer needs to sequence playback. ``zone`` is carried as the
    raw row's committed **label**: the viewer may display it, but no witness
    reads it — the route witness recomputes the zone from ``(x, z)``
    (:func:`visit_sequence_from_keyframes`), which is exactly what makes the
    coordinate-corruption negative tooth non-vacuous (Codex HIGH-2).
    """
    keyframes: list[dict[str, Any]] = []
    for index in select_keyframe_indices(rows, interval=interval):
        row = rows[index]
        keyframe: dict[str, Any] = {
            "kind": "keyframe",
            "physics_tick_index": int(row["physics_tick_index"]),
            "agent_tick": int(row["agent_tick"]),
            "order_slot": int(row["order_slot"]),
            "zone": row["zone"],
        }
        keyframe.update({key: row[key] for key in _POSE_KEYS})
        keyframes.append(keyframe)
    return keyframes


def keyframe_jsonl(keyframes: list[dict[str, Any]]) -> str:
    """Canonical JSONL text of the keyframe series (one object per line).

    Canonicalised through the handoff rules (``sort_keys`` + compact separators
    + ``ensure_ascii=False`` + ``allow_nan=False`` + 6-decimal quantisation) so
    cross-platform ``libm`` drift below half a quantum is absorbed
    (``feedback_golden_crossplatform_float_drift``). This is both the viewer's
    input format and the committed witness target's format.
    """
    return "".join(f"{canonical_dumps(keyframe)}\n" for keyframe in keyframes)


# --------------------------------------------------------------------------- #
# Position-derived route witness (ADR §5(a), anti-tautology)
# --------------------------------------------------------------------------- #
def visit_sequence_from_keyframes(keyframes: list[dict[str, Any]]) -> tuple[str, ...]:
    """The zone-visit sequence recomputed from keyframe **positions**.

    Samples the first keyframe (the itinerary's origin as the agent physically
    stands in it) followed by the last keyframe of each cognition tick — the
    same end-of-tick sampling ``traversal_live.extract_visit_sequence`` uses,
    which is immune to the transient Voronoi triple-point clip a continuous
    30 Hz path shows mid-leg (that module's docstring).

    Every entry comes from :func:`~erre_sandbox.contracts.geometry.locate_zone`
    applied to ``(x, z)``; the committed ``zone`` label is never read. So this
    proves the rendered position lands in the geometrically correct zone rather
    than echoing a label (Codex HIGH-2).
    """
    if not keyframes:
        msg = "cannot derive a visit sequence from an empty keyframe series"
        raise RenderDeriveError(msg)

    last_of_tick: dict[int, dict[str, Any]] = {}
    for keyframe in keyframes:
        last_of_tick[int(keyframe["agent_tick"])] = keyframe

    ticks = sorted(last_of_tick)
    missing = [tick for tick in range(ticks[-1] + 1) if tick not in last_of_tick]
    if missing:
        msg = (
            f"cognition tick(s) {missing} contributed no keyframe — a silently "
            "dropped leg would defeat the exact-match route witness"
        )
        raise RenderDeriveError(msg)

    origin = keyframes[0]
    visited = [locate_zone(float(origin["x"]), 0.0, float(origin["z"]))]
    visited.extend(
        locate_zone(float(last_of_tick[tick]["x"]), 0.0, float(last_of_tick[tick]["z"]))
        for tick in ticks
    )
    return tuple(zone.value for zone in visited)


# --------------------------------------------------------------------------- #
# Render manifest (staleness + policy record, Codex HIGH-1 / MEDIUM-1)
# --------------------------------------------------------------------------- #
def build_render_manifest(
    keyframes: list[dict[str, Any]],
    dump_text: str,
    *,
    trace_path: Path = SOURCE_TRACE_PATH,
    interval: int = KEYFRAME_INTERVAL_TICKS,
) -> dict[str, Any]:
    """The committed derivative's provenance + policy record.

    Not a measurement artifact: every field is a provenance digest, a pinned
    policy literal, or a plain count/byte size of the derived stream.
    """
    return {
        "artifact": "aha traversal render keyframes",
        "framing": (
            "scripted golden traversal replay — a recorded walk played back, "
            "not emergence and not an effect (ADR §0 honest framing)"
        ),
        "source_trace": trace_path.name,
        "source_trace_sha256": source_trace_sha256(trace_path),
        "source_row_count": len(read_trace_rows(trace_path)),
        "keyframe_count": len(keyframes),
        "keyframe_byte_size": len(dump_text.encode("utf-8")),
        "max_input_bytes": MAX_RENDER_INPUT_BYTES,
        "sampling_interval_ticks": interval,
        "sampling_rules": list(SAMPLING_RULES),
        "expected_keyframe_dump_sha256": hashlib.sha256(
            dump_text.encode("utf-8")
        ).hexdigest(),
        "visit_sequence": list(visit_sequence_from_keyframes(keyframes)),
        "visit_sequence_source": (
            "recomputed from keyframe (x, z) via contracts.geometry.locate_zone; "
            "the committed zone label is never read"
        ),
    }


def render_manifest_json(manifest: dict[str, Any]) -> str:
    """Canonical JSON text of the render manifest (trailing newline)."""
    return f"{canonical_dumps(manifest)}\n"


# --------------------------------------------------------------------------- #
# Developer entry point
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument(
        "--trace",
        type=Path,
        default=SOURCE_TRACE_PATH,
        help="raw ecl_trace.jsonl to decimate (default: the committed golden)",
    )
    parser.add_argument(
        "--emit",
        type=Path,
        default=None,
        help="write the derived keyframe JSONL here (viewer input)",
    )
    parser.add_argument(
        "--emit-manifest",
        type=Path,
        default=None,
        help="write the render manifest JSON here",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Derive the keyframe series, optionally writing it out for a viewer run."""
    args = _parse_args(argv)
    rows = read_trace_rows(args.trace)
    keyframes = build_keyframes(rows)
    dump_text = keyframe_jsonl(keyframes)
    manifest = build_render_manifest(keyframes, dump_text, trace_path=args.trace)

    if args.emit is not None:
        args.emit.parent.mkdir(parents=True, exist_ok=True)
        args.emit.write_text(dump_text, encoding="utf-8", newline="\n")
    if args.emit_manifest is not None:
        args.emit_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.emit_manifest.write_text(
            render_manifest_json(manifest), encoding="utf-8", newline="\n"
        )

    print(  # noqa: T201 — developer CLI feedback
        f"[aha-traversal-render] {len(rows)} raw rows -> "
        f"{manifest['keyframe_count']} keyframes "
        f"({manifest['keyframe_byte_size']} bytes), "
        f"route={'->'.join(manifest['visit_sequence'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
