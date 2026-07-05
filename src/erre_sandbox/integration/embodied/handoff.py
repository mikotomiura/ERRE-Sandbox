"""ECL v0 cross-machine handoff — Issue 005 (design-final.md §論点5).

G-GEAR *generates* an embodiment run; a MacBook Godot build *consumes* it. The
two machines are asynchronous (``.steering`` / auto-memory do not sync), so the
handoff is a **repo-tracked spec + committed golden**: this module turns an
:class:`~erre_sandbox.integration.embodied.loop.EclRunResult` (the Issue 004
harness output, imported and consumed *without modification*) into the four
artifacts a consumer replays:

* ``manifest.json`` — :func:`build_manifest`: ``SCHEMA_VERSION`` + run metadata +
  env pins + the coordinate convention (**Y-up / XZ ground / metres /
  yaw=atan2(dz, dx)**) + the two-axis tick mapping (30 Hz ``physics_tick_index``
  vs cognition ``agent_tick``) + a determinism checklist + the canonical-JSON
  rules + per-artifact SHA-256 hashes + the authoritative replay checksum + the
  expected envelope ordering + the Godot headless command.
* ``ecl_trace.jsonl`` — :func:`trace_rows_to_jsonl`: one line per physics tick, a
  lossless projection of the frozen :class:`~...loop.EclTraceRow` superset.
* ``decisions.jsonl`` — :func:`decisions_to_jsonl`: the Plane 2 record set
  (design §論点3); :func:`recorded_calls_from_jsonl` reconstructs the replay
  stream from it alone (the cross-machine reproducibility contract).
* ``envelope_stream.jsonl`` — :func:`build_envelope_stream`: the converter's
  ``ControlEnvelope`` (move / animation / speech) replay列, ordered
  deterministically by ``(order_slot, agent_tick, seq)``.

Scope guard (design §論点4/§論点5, binding). This is a *construction* apparatus,
**NOT a measurement line — verdict は holding**. It imports no ``evidence`` /
``spdm`` / ``runningness`` machinery and computes/emits no floor / landscape /
verdict statistic. The golden's authoritative checksum is
:func:`~...loop.ecl_trace_checksum`, which proves *reproducibility* (a re-run
reproduces the trace byte-for-byte); it is not a metric. The module is pure
(no live Ollama / httpx / filesystem side-effects beyond :func:`write_golden`);
the offline run orchestration lives in ``scripts/ecl_v0_golden.py`` and the
tests, which inject a deterministic in-memory store + embedding.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from importlib import metadata
from typing import TYPE_CHECKING, Any, Final

from pydantic import TypeAdapter

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied.loop import (
    DEFAULT_PHYSICS_TICKS_PER_COGNITION,
    GOLDEN_COGNITION_TICKS,
    EclDecisionRecord,
    EclRunResult,
    EclTraceRow,
    RecordedLlmCall,
)
from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentState,
    CognitiveHabit,
    ControlEnvelope,
    HabitFlag,
    PersonalityTraits,
    PersonaSpec,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# --------------------------------------------------------------------------- #
# Handoff spec version + frozen convention constants (manifest AC1 pins)
# --------------------------------------------------------------------------- #

MANIFEST_SCHEMA_VERSION: Final[str] = "ecl-v0-handoff-1"
"""Handoff artifact schema version — bumped only by a superseding ADR.

Distinct from ``schemas.SCHEMA_VERSION`` (the wire-envelope version): this
versions the *manifest/golden* shape, not the ControlEnvelope contract."""

COORDINATE_CONVENTION: Final[dict[str, str]] = {
    "up_axis": "Y",
    "ground_plane": "XZ",
    "units": "meters",
    "yaw": "atan2(dz, dx)",
    "pitch": "radians (0.0 level)",
}
"""The world's spatial convention a Godot consumer must assume (design §論点5)."""

TICK_MAPPING: Final[dict[str, str]] = {
    "physics_tick_index": "30 Hz world clock; ecl_trace_sink fires after "
    "step_kinematics on each _on_physics_tick (Codex MEDIUM-2)",
    "agent_tick": "cognition counter (one CognitionCycle.step per tick); "
    "physics_ticks_per_cognition physics ticks per cognition window",
    "axis_separation": "physics_tick_index and agent_tick are distinct axes; a "
    "MoveMsg target is recorded on the agent_tick axis, kinematics on the "
    "physics_tick_index axis",
}
"""Explicit two-axis tick mapping (Codex MEDIUM-2, design §論点5)."""

CANONICAL_JSON_RULES: Final[dict[str, Any]] = {
    "sort_keys": True,
    "ensure_ascii": False,
    "separators": [",", ":"],
    "allow_nan": False,
    "float_repr": "python repr (shortest round-trip IEEE-754 double)",
    "newline": "\\n (one JSON object per line, trailing newline)",
}
"""Byte-level serialisation rules a consumer must match to reproduce hashes."""

DETERMINISM_CHECKLIST: Final[tuple[str, ...]] = (
    "Plane 1 pinned: fixed retrieval clock, tick-derived memory id/ts, named "
    "RNG substreams (random.Random(str) → sha512 seed, PYTHONHASHSEED-independent)",
    "Plane 2 pinned: every action-LLM call recorded; replay injects recorded "
    "responses and calls no LLM (inner_invocations == 0)",
    "reflection disabled in record mode (second LLM non-determinism source closed)",
    "retrieval tie-break total order (-strength, created_at, id); k_world=0; "
    "mark_recalled=False",
    "envelope sent_at pinned to the record-mode clock",
    "ERRE_ZONE_BIAS_P pinned via env_pins (bias non-firing but pinned to close "
    "an un-pinned non-determinism source)",
    "authoritative reproducibility digest = ecl_trace_checksum over EclTraceRow "
    "(design §論点3); NOT a metric/floor/verdict",
    "cross-platform libm float drift is a Stop condition (superseding ADR), not "
    "silently tolerated",
)
"""Human-auditable determinism guarantees the golden was baked under."""

ENVELOPE_STREAM_KINDS: Final[tuple[str, ...]] = ("speech", "move", "animation")
"""ControlEnvelope kinds the converter emits into the replay stream (design
§論点5 item 4: MoveMsg / AnimationMsg / SpeechMsg). ``agent_update`` /
reasoning-trace envelopes stay out of the Godot dev-player replay列."""

GODOT_HEADLESS_COMMAND: Final[str] = (
    "godot --headless --path godot_project "
    "--script res://scripts/dev/EclReplayPlayer.gd "
    "-- --manifest=<abs>/manifest.json --stream=<abs>/envelope_stream.jsonl"
)
"""The dev-only headless replay command (EclReplayPlayer.gd, design §論点5)."""

# --------------------------------------------------------------------------- #
# Golden run pins (single source of truth for bake + verify + tests)
# --------------------------------------------------------------------------- #

GOLDEN_RUN_ID: Final[str] = "ecl-v0-golden"
GOLDEN_SEED: Final[int] = 0
GOLDEN_AGENT_ID: Final[str] = "a_kant_001"
GOLDEN_PERSONA_ID: Final[str] = "kant"
GOLDEN_N_COGNITION_TICKS: Final[int] = GOLDEN_COGNITION_TICKS
GOLDEN_PHYSICS_TICKS_PER_COGNITION: Final[int] = DEFAULT_PHYSICS_TICKS_PER_COGNITION
GOLDEN_TS: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed retrieval/base timestamp for the golden run (Plane 1 clock pin)."""

GOLDEN_EMBED_VALUE: Final[float] = 0.01
"""The constant every golden embedding vector component takes.

A uniform embedding makes all retrieval cosine-similarities equal, so ranking
falls entirely to the deterministic tie-break ``(-strength, created_at, id)`` —
the value itself does not affect the trace, but pinning it here gives bake and
replay a single source so the offline mock embedding never drifts."""

_GOLDEN_PLAN_JSON: Final[str] = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)
"""The fixed LLMPlan the golden replays each tick (grill G-5): a destination
(→ history-dependent centroid + MoveMsg), an utterance (→ SpeechMsg) and an
animation (→ AnimationMsg), so every stream kind appears."""

_GOLDEN_SAMPLING: Final[ResolvedSampling] = ResolvedSampling(
    temperature=0.7, top_p=0.9, repeat_penalty=1.1
)
"""A recorded sampling value for the golden Plane 2. Replay carries it as
provenance only (the injected response drives the run), so a fixed in-range
triple is a faithful fixture (grill G-5)."""


def golden_agent_state() -> AgentState:
    """The golden run's fixed agent (Kant in ``study`` at tick 0).

    Byte-identical every construction so bake and replay start from the same
    state (mirrors ``tests/conftest.py``'s ``make_agent_state`` default).
    """
    return AgentState.model_validate(
        {
            "agent_id": GOLDEN_AGENT_ID,
            "persona_id": GOLDEN_PERSONA_ID,
            "tick": 0,
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "zone": "study"},
            "erre": {"name": "deep_work", "entered_at_tick": 0},
        }
    )


def golden_persona() -> PersonaSpec:
    """The golden run's fixed persona (minimal Kant, study+peripatos).

    Mirrors ``tests/conftest.py``'s ``make_persona_spec`` default so the
    apparatus is pinned by ``MANIFEST_SCHEMA_VERSION`` rather than a fixture.
    """
    return PersonaSpec.model_validate(
        {
            "persona_id": GOLDEN_PERSONA_ID,
            "display_name": "Immanuel Kant",
            "era": "1724-1804",
            "primary_corpus_refs": ["kuehn2001"],
            "personality": PersonalityTraits(
                conscientiousness=0.95,
                openness=0.85,
            ).model_dump(),
            "cognitive_habits": [
                CognitiveHabit(
                    description="15:30 daily walk",
                    source="kuehn2001",
                    flag=HabitFlag.FACT,
                    mechanism="DMN activation via rhythmic locomotion",
                    trigger_zone=Zone.PERIPATOS,
                ).model_dump(mode="json"),
            ],
            "preferred_zones": ["study", "peripatos"],
        }
    )


def golden_recorded_calls() -> list[RecordedLlmCall]:
    """The fixed Plane 2 the golden replays — one identical call per tick.

    Hand-built (grill G-5 sanctions baking the recorded plan列 into the fixture):
    each tick injects ``_GOLDEN_PLAN_JSON``. Replaying these reconstructs the
    run with no live LLM.
    """
    response = ChatResponse(
        content=_GOLDEN_PLAN_JSON,
        model="qwen3:8b",
        eval_count=0,
        prompt_eval_count=0,
        total_duration_ms=0.0,
    )
    return [
        RecordedLlmCall(
            system_prompt="[golden] system",
            user_prompt=f"[golden] cognition tick {tick}",
            sampling=_GOLDEN_SAMPLING,
            response=response,
        )
        for tick in range(GOLDEN_N_COGNITION_TICKS)
    ]


# --------------------------------------------------------------------------- #
# Canonical JSON
# --------------------------------------------------------------------------- #

_CONTROL_ENVELOPE_ADAPTER: Final[TypeAdapter[ControlEnvelope]] = TypeAdapter(
    ControlEnvelope
)


def canonical_dumps(obj: Any) -> str:
    """Serialise ``obj`` under :data:`CANONICAL_JSON_RULES` (single line).

    ``sort_keys`` + ``allow_nan=False`` make a byte-identical re-serialisation a
    reproducibility witness; ``ensure_ascii=False`` keeps UTF-8 utterances
    readable. Non-finite floats raise (the manifest's NaN policy).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _jsonl(rows: Sequence[Any]) -> str:
    """Join canonical-serialised objects one-per-line with a trailing newline."""
    return "".join(f"{canonical_dumps(row)}\n" for row in rows)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# ecl_trace.jsonl (lossless EclTraceRow round-trip)
# --------------------------------------------------------------------------- #


def _pair(value: tuple[float, float] | None) -> list[float] | None:
    return [value[0], value[1]] if value is not None else None


def _pair_back(value: list[float] | None) -> tuple[float, float] | None:
    return (value[0], value[1]) if value is not None else None


def trace_row_to_dict(row: EclTraceRow) -> dict[str, Any]:
    """Lossless projection of one :class:`EclTraceRow` (superset of TraceRow)."""
    return {
        "run_id": row.run_id,
        "agent_id": row.agent_id,
        "physics_tick_index": row.physics_tick_index,
        "agent_tick": row.agent_tick,
        "order_slot": row.order_slot,
        "x": row.x,
        "y": row.y,
        "z": row.z,
        "yaw": row.yaw,
        "pitch": row.pitch,
        "zone": row.zone.value,
        "resolved_from": row.resolved_from,
        "move_centroid": _pair(row.move_centroid),
        "move_provenance": (
            list(row.move_provenance) if row.move_provenance is not None else None
        ),
        "move_jitter": _pair(row.move_jitter),
        "move_pre_clamp": _pair(row.move_pre_clamp),
        "move_post_clamp": _pair(row.move_post_clamp),
        "move_clamp_fired": row.move_clamp_fired,
    }


def trace_row_from_dict(data: dict[str, Any]) -> EclTraceRow:
    """Rebuild an :class:`EclTraceRow` from :func:`trace_row_to_dict` output."""
    provenance = data["move_provenance"]
    return EclTraceRow(
        run_id=data["run_id"],
        agent_id=data["agent_id"],
        physics_tick_index=data["physics_tick_index"],
        agent_tick=data["agent_tick"],
        order_slot=data["order_slot"],
        x=data["x"],
        y=data["y"],
        z=data["z"],
        yaw=data["yaw"],
        pitch=data["pitch"],
        zone=Zone(data["zone"]),
        resolved_from=data["resolved_from"],
        move_centroid=_pair_back(data["move_centroid"]),
        move_provenance=tuple(provenance) if provenance is not None else None,
        move_jitter=_pair_back(data["move_jitter"]),
        move_pre_clamp=_pair_back(data["move_pre_clamp"]),
        move_post_clamp=_pair_back(data["move_post_clamp"]),
        move_clamp_fired=data["move_clamp_fired"],
    )


def trace_rows_to_jsonl(rows: Sequence[EclTraceRow]) -> str:
    """Serialise the trace as canonical JSONL (one physics tick per line)."""
    return _jsonl([trace_row_to_dict(r) for r in rows])


def trace_rows_from_jsonl(text: str) -> list[EclTraceRow]:
    """Parse committed ``ecl_trace.jsonl`` back into rows."""
    return [trace_row_from_dict(json.loads(line)) for line in _nonempty(text)]


# --------------------------------------------------------------------------- #
# decisions.jsonl (Plane 2 record set + replay-stream reconstruction)
# --------------------------------------------------------------------------- #


def _recorded_call_to_dict(call: RecordedLlmCall) -> dict[str, Any]:
    return {
        "system_prompt": call.system_prompt,
        "user_prompt": call.user_prompt,
        "sampling": call.sampling.model_dump(mode="json"),
        "response": call.response.model_dump(mode="json"),
    }


def _recorded_call_from_dict(data: dict[str, Any]) -> RecordedLlmCall:
    return RecordedLlmCall(
        system_prompt=data["system_prompt"],
        user_prompt=data["user_prompt"],
        sampling=ResolvedSampling.model_validate(data["sampling"]),
        response=ChatResponse.model_validate(data["response"]),
    )


def decision_to_dict(decision: EclDecisionRecord) -> dict[str, Any]:
    """Serialise one cognition tick's Plane 2 record (design §論点3, closed set)."""
    move = decision.move_decision
    return {
        "agent_tick": decision.agent_tick,
        "call": _recorded_call_to_dict(decision.call),
        "plan": (
            decision.plan.model_dump(mode="json") if decision.plan is not None else None
        ),
        "plan_schema_version": decision.plan_schema_version,
        "llm_fell_back": decision.llm_fell_back,
        "llm_status": decision.llm_status,
        "bias_fired": (
            dataclasses.asdict(decision.bias_fired)
            if decision.bias_fired is not None
            else None
        ),
        "move_decision": (
            {
                "target": move.target.model_dump(mode="json"),
                "resolved_from": move.resolved_from,
                "centroid": list(move.centroid),
                "provenance": list(move.provenance),
                "jitter": list(move.jitter),
                "pre_clamp": list(move.pre_clamp),
                "post_clamp": list(move.post_clamp),
                "clamp_fired": move.clamp_fired,
            }
            if move is not None
            else None
        ),
        "envelope_provenance": list(decision.envelope_provenance),
    }


def decisions_to_jsonl(decisions: Sequence[EclDecisionRecord]) -> str:
    """Serialise the Plane 2 decision set as canonical JSONL."""
    return _jsonl([decision_to_dict(d) for d in decisions])


def recorded_calls_from_jsonl(text: str) -> list[RecordedLlmCall]:
    """Reconstruct the replay stream from committed ``decisions.jsonl`` alone.

    This is the cross-machine reproducibility contract (AC2): a consumer that
    only has ``decisions.jsonl`` can rebuild the recorded Plane 2 and replay the
    run to the exact same :func:`~...loop.ecl_trace_checksum`.
    """
    return [
        _recorded_call_from_dict(json.loads(line)["call"]) for line in _nonempty(text)
    ]


# --------------------------------------------------------------------------- #
# envelope_stream.jsonl (converter: decisions → ordered ControlEnvelope replay)
# --------------------------------------------------------------------------- #


def build_envelope_stream(result: EclRunResult) -> list[dict[str, Any]]:
    """Convert the run's recorded envelopes into an ordered replay stream (AC3).

    For each cognition tick's :class:`EclDecisionRecord`, the recorded envelope
    provenance is re-validated through the ``ControlEnvelope`` discriminated
    union (schema conformance), the Godot-replayable kinds
    (:data:`ENVELOPE_STREAM_KINDS`) are kept, and each is wrapped with its
    ``order_slot`` / ``agent_tick`` / within-tick ``seq``. The list is sorted by
    ``(order_slot, agent_tick, seq)`` so replay order is deterministic and
    forward-compatible with multi-agent runs (single agent → ``order_slot`` 0).
    """
    order_slot = result.rows[0].order_slot if result.rows else 0
    entries: list[dict[str, Any]] = []
    for decision in result.decisions:
        seq = 0
        for env_json in decision.envelope_provenance:
            raw = json.loads(env_json)
            if raw.get("kind") not in ENVELOPE_STREAM_KINDS:
                continue
            # Re-validate through the discriminated union (AC3 conformance) then
            # re-dump canonically so the stream carries a schema-clean envelope.
            envelope = _CONTROL_ENVELOPE_ADAPTER.validate_python(raw)
            entries.append(
                {
                    "order_slot": order_slot,
                    "agent_tick": decision.agent_tick,
                    "seq": seq,
                    "envelope": _CONTROL_ENVELOPE_ADAPTER.dump_python(
                        envelope, mode="json"
                    ),
                }
            )
            seq += 1
    entries.sort(key=lambda e: (e["order_slot"], e["agent_tick"], e["seq"]))
    return entries


def envelope_stream_to_jsonl(entries: Sequence[dict[str, Any]]) -> str:
    """Serialise the converter's envelope stream as canonical JSONL."""
    return _jsonl(list(entries))


def validate_envelope_stream(text: str) -> list[ControlEnvelope]:
    """Parse committed ``envelope_stream.jsonl`` and validate each envelope.

    Returns the validated :class:`ControlEnvelope` objects in file order; raises
    if any wrapped envelope is not schema-conformant (AC3).
    """
    envelopes: list[ControlEnvelope] = []
    for line in _nonempty(text):
        wrapper = json.loads(line)
        envelopes.append(_CONTROL_ENVELOPE_ADAPTER.validate_python(wrapper["envelope"]))
    return envelopes


# --------------------------------------------------------------------------- #
# manifest.json
# --------------------------------------------------------------------------- #


def capture_env_pins() -> dict[str, Any]:
    """Snapshot the runtime env for the manifest (provenance, not determinism).

    Records interpreter + key package versions and ``ERRE_ZONE_BIAS_P`` (pinned
    so a future consumer re-runs under the same bias regime — bias is
    non-firing for preferred-zone destinations but an un-pinned env var is an
    un-pinned non-determinism source, design §論点5 / Codex).
    """
    packages: dict[str, str] = {}
    for name in ("pydantic", "httpx"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover - env-dependent
            packages[name] = "unknown"
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}",
        "packages": packages,
        "godot": "4.6 (consumer; not required to generate)",
        "ERRE_ZONE_BIAS_P": os.environ.get("ERRE_ZONE_BIAS_P", "0.1"),
    }


def build_manifest(
    result: EclRunResult,
    *,
    trace_jsonl: str,
    decisions_jsonl: str,
    envelope_jsonl: str,
    env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the ``manifest.json`` dict — the AC1 pin surface (design §論点5).

    ``result`` supplies the run metadata + the authoritative ``replay_checksum``
    (``ecl_trace_checksum``); the three ``*_jsonl`` strings supply the per-artifact
    SHA-256 integrity hashes. All convention/checklist pins are module constants
    so they are stable across bakes; ``env_pins`` defaults to a fresh snapshot.
    """
    agent_ids = sorted({r.agent_id for r in result.rows})
    world_tick_count = max((r.physics_tick_index for r in result.rows), default=-1) + 1
    cognition_ticks = len({r.agent_tick for r in result.rows})
    return {
        "manifest_version": MANIFEST_SCHEMA_VERSION,
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": result.run_id,
            "seed": GOLDEN_SEED,
            "agent_ids": agent_ids,
            "world_tick_count": world_tick_count,
            "cognition_ticks": cognition_ticks,
            "physics_ticks_per_cognition": GOLDEN_PHYSICS_TICKS_PER_COGNITION,
            "k_ecl": K_ECL,
            "base_ts": GOLDEN_TS.isoformat(),
            "retrieval_now": GOLDEN_TS.isoformat(),
        },
        "coordinate_convention": COORDINATE_CONVENTION,
        "tick_mapping": TICK_MAPPING,
        "determinism_checklist": list(DETERMINISM_CHECKLIST),
        "canonical_json_rules": CANONICAL_JSON_RULES,
        "env_pins": env_pins if env_pins is not None else capture_env_pins(),
        "artifacts": {
            "ecl_trace.jsonl": {"sha256": _sha256(trace_jsonl)},
            "decisions.jsonl": {"sha256": _sha256(decisions_jsonl)},
            "envelope_stream.jsonl": {"sha256": _sha256(envelope_jsonl)},
        },
        "replay_checksum": result.checksum,
        "expected_envelope_ordering": "sort ascending by (order_slot, agent_tick, seq)",
        "envelope_stream_kinds": list(ENVELOPE_STREAM_KINDS),
        "godot_headless_command": GODOT_HEADLESS_COMMAND,
    }


# --------------------------------------------------------------------------- #
# Golden artifact bundle
# --------------------------------------------------------------------------- #

GOLDEN_FILENAMES: Final[tuple[str, ...]] = (
    "manifest.json",
    "ecl_trace.jsonl",
    "decisions.jsonl",
    "envelope_stream.jsonl",
)


def render_golden(
    result: EclRunResult, *, env_pins: dict[str, Any] | None = None
) -> dict[str, str]:
    """Render the four handoff artifacts as ``{filename: text}`` (pure).

    Deterministic given ``result`` (and ``env_pins`` for ``manifest.json``): the
    caller writes the strings, or diffs them against the committed golden.
    """
    trace_jsonl = trace_rows_to_jsonl(result.rows)
    decisions_jsonl = decisions_to_jsonl(result.decisions)
    envelope_jsonl = envelope_stream_to_jsonl(build_envelope_stream(result))
    manifest = build_manifest(
        result,
        trace_jsonl=trace_jsonl,
        decisions_jsonl=decisions_jsonl,
        envelope_jsonl=envelope_jsonl,
        env_pins=env_pins,
    )
    return {
        "manifest.json": canonical_dumps(manifest) + "\n",
        "ecl_trace.jsonl": trace_jsonl,
        "decisions.jsonl": decisions_jsonl,
        "envelope_stream.jsonl": envelope_jsonl,
    }


def write_golden(
    result: EclRunResult,
    out_dir: Path,
    *,
    env_pins: dict[str, Any] | None = None,
) -> None:
    """Write the four handoff artifacts into ``out_dir`` (the only side-effect)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in render_golden(result, env_pins=env_pins).items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


def _nonempty(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


__all__ = [
    "CANONICAL_JSON_RULES",
    "COORDINATE_CONVENTION",
    "DETERMINISM_CHECKLIST",
    "ENVELOPE_STREAM_KINDS",
    "GODOT_HEADLESS_COMMAND",
    "GOLDEN_AGENT_ID",
    "GOLDEN_EMBED_VALUE",
    "GOLDEN_FILENAMES",
    "GOLDEN_N_COGNITION_TICKS",
    "GOLDEN_PHYSICS_TICKS_PER_COGNITION",
    "GOLDEN_RUN_ID",
    "GOLDEN_SEED",
    "GOLDEN_TS",
    "MANIFEST_SCHEMA_VERSION",
    "TICK_MAPPING",
    "build_envelope_stream",
    "build_manifest",
    "canonical_dumps",
    "capture_env_pins",
    "decision_to_dict",
    "decisions_to_jsonl",
    "golden_agent_state",
    "golden_persona",
    "golden_recorded_calls",
    "recorded_calls_from_jsonl",
    "render_golden",
    "trace_row_from_dict",
    "trace_row_to_dict",
    "trace_rows_from_jsonl",
    "trace_rows_to_jsonl",
    "validate_envelope_stream",
    "write_golden",
]
