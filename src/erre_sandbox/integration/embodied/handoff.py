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
    ecl_trace_checksum,
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
    from typing import Protocol

    from erre_sandbox.integration.embodied.society import SocietyRunResult

    class _GeometrySource(Protocol):
        """Structural shape :func:`build_manifest`/:func:`render_golden` need.

        Both :class:`~erre_sandbox.integration.embodied.loop.EclRunResult`
        (legacy, single-agent) and
        :class:`~erre_sandbox.integration.embodied.society.SocietyRunResult`
        (M2, N-agent) satisfy this structurally (Codex HIGH-2 M2-path adapter,
        design-final.md §M7) — no import of ``society`` is needed here, keeping
        this module's dependency surface unchanged. Declared via read-only
        ``@property`` (not plain attributes) so both frozen-dataclass results'
        ``tuple``-typed fields structurally satisfy the covariant ``Sequence``
        here (a plain-attribute Protocol member is invariant and would reject a
        ``tuple`` where a mutable ``Sequence`` is nominally expected).
        """

        @property
        def run_id(self) -> str: ...
        @property
        def rows(self) -> Sequence[EclTraceRow]: ...
        @property
        def checksum(self) -> str: ...

    class _EnvelopeSource(Protocol):
        """Shape :func:`build_envelope_stream` needs (read-only property, see above)."""

        @property
        def rows(self) -> Sequence[EclTraceRow]: ...
        @property
        def decisions(self) -> Sequence[EclDecisionRecord]: ...

# --------------------------------------------------------------------------- #
# Handoff spec version + frozen convention constants (manifest AC1 pins)
# --------------------------------------------------------------------------- #

MANIFEST_SCHEMA_VERSION: Final[str] = "ecl-v0-handoff-2"
"""Handoff artifact schema version — bumped only by a superseding ADR.

Distinct from ``schemas.SCHEMA_VERSION`` (the wire-envelope version): this
versions the *manifest/golden* shape, not the ControlEnvelope contract.

**Frozen for the legacy (single-agent) path** (Codex HIGH-2, design-final.md
§M7): ``run_ecl_loop`` + the committed ``tests/fixtures/ecl_v0_golden/`` bundle
must stay byte-unchanged, so this constant is never mutated in place — the M2
(N-agent) schema is a *separate*, additive constant
(:data:`M2_MANIFEST_SCHEMA_VERSION`), not an overwrite of this one."""

M2_MANIFEST_SCHEMA_VERSION: Final[str] = "m2-society-1"
"""M2 (N-agent society) handoff manifest schema version (Issue 005, §M7).

Versioned-additive sibling of :data:`MANIFEST_SCHEMA_VERSION`: a society-driver
run's manifest carries this value instead (via :func:`build_manifest`'s
``manifest_version`` override), while every legacy caller — which never passes
that argument — keeps emitting :data:`MANIFEST_SCHEMA_VERSION` byte-for-byte
unchanged. A raw-byte comparison between an ``m2-society-1`` manifest and an
``ecl-v0-handoff-2`` one is not expected to match (different schema versions,
DA-M2IMPL-7); the M2 path's acceptance is canonical-projection/adapter
*semantic* equivalence (Codex HIGH-2), not raw-byte identity."""

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

CANONICAL_FLOAT_DECIMALS: Final[int] = 6
"""Decimals every emitted float is quantised to before serialisation/checksum.

Absorbs sub-ULP cross-platform ``libm`` drift: the frozen ``disc_jitter``'s
``math.cos``/``math.sin`` differ by ~1 ULP (max abs 8.88e-16, non-amplifying)
between Windows (UCRT) and Linux (glibc), which would otherwise diverge the
golden checksum between machines. ``round(x, 6)`` uses CPython's
correctly-rounded dtoa (platform-independent), and the drift is far below half a
quantum (5e-7), so both platforms round identically. Six decimals is micron
precision on metre coordinates — semantically ample."""

CANONICAL_JSON_RULES: Final[dict[str, Any]] = {
    "sort_keys": True,
    "ensure_ascii": False,
    "separators": [",", ":"],
    "allow_nan": False,
    "float_quantize_decimals": CANONICAL_FLOAT_DECIMALS,
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
    "(design §論点3); NOT a metric/floor/verdict. It canonicalises under the same "
    "rules as CANONICAL_JSON_RULES (sort_keys + compact separators + "
    "ensure_ascii=False + allow_nan=False + 6-decimal float quantisation), so a "
    "consumer recomputing the digest under the advertised rules gets identical "
    "bytes; a non-finite trace raises (allow_nan=False) — a Stop condition, not a "
    "silently-hashed value",
    "cross-platform libm float drift is absorbed by quantising every emitted float "
    "to 6 decimals (round is platform-independent), not silently tolerated",
)
"""Human-auditable determinism guarantees the golden was baked under."""

M2_NBODY_DETERMINISM_CHECKLIST: Final[tuple[str, ...]] = (
    "agent_id set is frozen for the whole run; order_slot = "
    "sorted(agent_ids).index(agent_id), stable across every cognition window "
    "(§M2/§M4.1) — never dict-insertion/registration order",
    "N-agent cognition steps strictly sequentially in sorted(agent_id) order per "
    "cognition window (no asyncio.gather fan-out, §M4.1)",
    "pair-order is canonicalised as sorted_pair=(min(agent_id), max(agent_id)) "
    "keyed by a collision-free canonical-JSON-array pair_key (§M4.2, Codex "
    "MEDIUM-7) — never a naive string-join",
)
"""Additive M2 (N-agent) determinism pins (Issue 005, §M7), appended to
:data:`DETERMINISM_CHECKLIST` only in an M2-schema manifest
(:func:`build_manifest`'s ``extra_determinism_checklist``) — the legacy
single-agent manifest's checklist is unaffected."""

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


def _quantize_floats(obj: Any, ndigits: int) -> Any:
    """Recursively round every float in ``obj`` to ``ndigits`` decimals.

    Walks dict values / list·tuple items; leaves ``bool`` / ``int`` / ``str`` /
    ``None`` untouched (``bool`` is excluded explicitly even though it is not a
    ``float``). ``round`` uses CPython's correctly-rounded dtoa, so the same input
    rounds identically on every platform — this is what absorbs the sub-ULP
    cross-platform ``libm`` drift (``math.cos``/``math.sin`` in the frozen
    ``contracts.geometry.disc_jitter``) that would otherwise diverge the golden
    checksum between Windows (UCRT) and Linux (glibc).
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _quantize_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_quantize_floats(v, ndigits) for v in obj]
    return obj


def canonical_dumps(obj: Any) -> str:
    """Serialise ``obj`` under :data:`CANONICAL_JSON_RULES` (single line).

    ``sort_keys`` + ``allow_nan=False`` make a byte-identical re-serialisation a
    reproducibility witness; ``ensure_ascii=False`` keeps UTF-8 utterances
    readable. Non-finite floats raise (the manifest's NaN policy). Before
    serialising, every float is quantised to :data:`CANONICAL_FLOAT_DECIMALS`
    decimals (:func:`_quantize_floats`) so cross-platform ``libm`` drift below
    half a quantum is absorbed and every machine emits identical bytes.

    Shares its exact canonicalisation (``sort_keys`` + compact ``separators`` +
    ``ensure_ascii=False`` + ``allow_nan=False`` + 6-decimal float quantisation)
    with ``loop.ecl_trace_checksum``. The rule set is inlined in both places
    rather than shared through one helper because ``handoff`` imports ``loop`` (a
    shared canonicaliser would create an import cycle);
    ``test_ecl_trace_checksum_canonical_rules`` pins that the two produce
    identical digests so the duplication cannot drift (CR-M2).
    """
    return json.dumps(
        _quantize_floats(obj, CANONICAL_FLOAT_DECIMALS),
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
        # ``response`` is ``None`` for a ``raised`` (response-less) call; emit
        # explicit ``null`` so the roundtrip is total (Codex M-1).
        "response": (
            call.response.model_dump(mode="json") if call.response is not None else None
        ),
        "outcome": call.outcome,
    }


def _recorded_call_from_dict(data: dict[str, Any]) -> RecordedLlmCall:
    # Backward compatible with committed golden ``decisions.jsonl`` baked before
    # the outcome-tagged union (Codex M-1): a missing ``outcome`` defaults to
    # ``ok`` and a missing/``null`` ``response`` stays ``None``. This must not
    # break the committed golden's replay.
    response_data = data.get("response")
    return RecordedLlmCall(
        system_prompt=data["system_prompt"],
        user_prompt=data["user_prompt"],
        sampling=ResolvedSampling.model_validate(data["sampling"]),
        response=(
            ChatResponse.model_validate(response_data)
            if response_data is not None
            else None
        ),
        outcome=data.get("outcome", "ok"),
    )


def _quantize_embedded_json(serialised: str) -> str:
    """Re-serialise a ``model_dump_json`` string with its floats quantised.

    ``envelope_provenance`` stores each envelope as a *pre-serialised* JSON string
    (``ControlEnvelope.model_dump_json``), so the floats inside are text, invisible
    to :func:`_quantize_floats` when the surrounding decision dict is canonicalised.
    Those embedded floats include the drift-prone kinematic position (same
    ``contracts.geometry.disc_jitter`` ``cos``/``sin`` origin as the trace), so
    unless they are quantised here ``decisions.jsonl`` diverges cross-platform even
    though ``ecl_trace.jsonl`` does not (empirically: Windows/UCRT vs Linux/glibc).
    Parse → quantise → re-dump under the same compact / UTF-8 options
    ``model_dump_json`` uses, preserving insertion order (NOT sorted) so the sole
    change is float precision.
    """
    return json.dumps(
        _quantize_floats(json.loads(serialised), CANONICAL_FLOAT_DECIMALS),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
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
        "envelope_provenance": [
            _quantize_embedded_json(env) for env in decision.envelope_provenance
        ],
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


def build_envelope_stream(result: _EnvelopeSource) -> list[dict[str, Any]]:
    """Convert the run's recorded envelopes into an ordered replay stream (AC3).

    For each cognition tick's :class:`EclDecisionRecord`, the recorded envelope
    provenance is re-validated through the ``ControlEnvelope`` discriminated
    union (schema conformance), the Godot-replayable kinds
    (:data:`ENVELOPE_STREAM_KINDS`) are kept, and each is wrapped with its
    ``order_slot`` / ``agent_tick`` / within-tick ``seq``. The list is sorted by
    ``(order_slot, agent_tick, seq)`` so replay order is deterministic and
    forward-compatible with multi-agent runs (single agent → ``order_slot`` 0).

    ``order_slot`` is the frozen ``sorted(agent_id)`` index of each envelope's own
    ``agent_id`` (design §論点6), derived per-envelope from a slot map over the
    run's agents — not the first row's slot — so a future multi-agent run
    interleaves correctly (Codex TASK-POST LOW). Empty runs yield an empty stream.
    """
    slot_by_agent = {
        agent_id: slot
        for slot, agent_id in enumerate(sorted({r.agent_id for r in result.rows}))
    }
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
                    "order_slot": slot_by_agent.get(raw.get("agent_id", ""), 0),
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
# M2 path (Issue 005, §M7) — N-agent society handoff, additive, legacy-untouched
# --------------------------------------------------------------------------- #


def project_society_agent_to_ecl_result(
    result: SocietyRunResult, agent_id: str
) -> EclRunResult:
    """Canonical N=1 projection/adapter (Codex HIGH-2 M2 path, §M7).

    Projects one agent's slice of a :class:`SocietyRunResult` into the exact
    shape :func:`render_golden`/:func:`build_manifest` already understand
    (:class:`EclRunResult`), so a genuine N=1 society run can be checked for
    *semantic* equivalence against the pre-existing single-agent
    ``run_ecl_loop`` path using the unmodified legacy rendering functions —
    this is the "canonical projection or adapter" the ADR requires instead of
    raw-byte identity across schema versions (DA-M2IMPL-7). Raises if
    ``agent_id`` produced no rows (a construction precondition; a silent empty
    projection would be a false-equivalence witness).
    """
    agent_rows = tuple(r for r in result.rows if r.agent_id == agent_id)
    if not agent_rows:
        msg = f"no rows for agent_id {agent_id!r} in society run {result.run_id!r}"
        raise ValueError(msg)
    if agent_id not in result.decisions:
        msg = f"no decisions for agent_id {agent_id!r} in society run {result.run_id!r}"
        raise ValueError(msg)
    return EclRunResult(
        run_id=result.run_id,
        rows=agent_rows,
        decisions=tuple(result.decisions[agent_id]),
        checksum=ecl_trace_checksum(agent_rows),
    )


@dataclasses.dataclass(slots=True)
class _FlatSocietyView:
    """Adapter: an N-agent result flattened to the shape build_envelope_stream needs.

    Read-only view for :func:`build_envelope_stream` (§M7, Codex HIGH-2 M2
    path). Not a new schema — reuses :func:`build_envelope_stream` **unmodified**
    (its own ``order_slot`` derivation already reads each envelope's own embedded
    ``agent_id``, so flattening ``decisions`` in any stable order is safe).
    """

    rows: tuple[EclTraceRow, ...]
    decisions: tuple[EclDecisionRecord, ...]


def _flatten_society_decisions(
    result: SocietyRunResult,
) -> tuple[EclDecisionRecord, ...]:
    """Every agent's decisions, concatenated in ``sorted(agent_id)`` order."""
    flat: list[EclDecisionRecord] = []
    for agent_id in sorted(result.decisions):
        flat.extend(result.decisions[agent_id])
    return tuple(flat)


def build_society_envelope_stream(result: SocietyRunResult) -> list[dict[str, Any]]:
    """N-agent envelope stream (§M7) — reuses :func:`build_envelope_stream` as-is.

    The legacy function's own ``(order_slot, agent_tick, seq)`` sort and
    per-envelope ``agent_id``-derived ``order_slot`` lookup are already N-agent
    forward-compatible (handoff.py L553/576/664 lineage); this only supplies the
    flattened view its signature expects.
    """
    view = _FlatSocietyView(
        rows=tuple(result.rows), decisions=_flatten_society_decisions(result)
    )
    return build_envelope_stream(view)


def build_society_decisions_stream(result: SocietyRunResult) -> list[dict[str, Any]]:
    """N-agent ``decisions.jsonl`` stream (§M7, additive M2 schema).

    The legacy ``decisions.jsonl``/:func:`decision_to_dict` shape carries no
    agent identity (a single-agent-only contract, left **unmodified** — Codex
    HIGH-2 legacy path); an N-agent handoff needs one, so each per-agent,
    per-tick decision is wrapped with its ``order_slot`` (frozen
    ``sorted(agent_ids).index(agent_id)``, §M2) and ``agent_id``, reusing
    :func:`decision_to_dict` unmodified for the inner payload. Ordered by
    ``(order_slot, agent_tick)`` — the same convention the envelope stream uses
    — so the interleave is deterministic regardless of Python dict-iteration
    order.
    """
    agent_ids = sorted(result.decisions)
    order_slot_map = {agent_id: slot for slot, agent_id in enumerate(agent_ids)}
    entries: list[dict[str, Any]] = [
        {
            "order_slot": order_slot_map[agent_id],
            "agent_id": agent_id,
            "decision": decision_to_dict(d),
        }
        for agent_id in agent_ids
        for d in result.decisions[agent_id]
    ]
    entries.sort(key=lambda e: (e["order_slot"], e["decision"]["agent_tick"]))
    return entries


def society_decisions_to_jsonl(result: SocietyRunResult) -> str:
    """Serialise :func:`build_society_decisions_stream` as canonical JSONL."""
    return _jsonl(build_society_decisions_stream(result))


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
        # Fallback mirrors ``CognitionCycle.__init__``'s
        # ``os.environ.get("ERRE_ZONE_BIAS_P", "0.2")`` default so an unset env
        # records the value the run actually used (Codex TASK-POST MEDIUM-2).
        "ERRE_ZONE_BIAS_P": os.environ.get("ERRE_ZONE_BIAS_P", "0.2"),
    }


def golden_run_config() -> dict[str, Any]:
    """The golden run's input config for the manifest ``run`` block.

    Explicit so :func:`build_manifest` records the *actual* run inputs rather
    than reading module globals — a non-golden caller passes its own config and
    gets honest provenance (Codex TASK-POST MEDIUM-2).
    """
    return {
        "seed": GOLDEN_SEED,
        "physics_ticks_per_cognition": GOLDEN_PHYSICS_TICKS_PER_COGNITION,
        "k_ecl": K_ECL,
        "base_ts": GOLDEN_TS.isoformat(),
        "retrieval_now": GOLDEN_TS.isoformat(),
    }


def build_manifest(
    result: _GeometrySource,
    *,
    run_config: dict[str, Any],
    trace_jsonl: str,
    decisions_jsonl: str,
    envelope_jsonl: str,
    env_pins: dict[str, Any] | None = None,
    manifest_version: str | None = None,
    extra_determinism_checklist: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble the ``manifest.json`` dict — the AC1 pin surface (design §論点5).

    ``result`` supplies the derived run metadata (agent_ids / tick counts) + the
    authoritative ``replay_checksum`` (``ecl_trace_checksum``); ``run_config``
    supplies the run *inputs* (seed / physics_ticks_per_cognition / k_ecl /
    clocks) so the provenance reflects the actual run, not module globals (Codex
    TASK-POST MEDIUM-2). The three ``*_jsonl`` strings supply the per-artifact
    SHA-256 integrity hashes; all convention/checklist pins are module constants
    so they are stable across bakes; ``env_pins`` defaults to a fresh snapshot.

    ``manifest_version`` / ``extra_determinism_checklist`` are additive M2-path
    overrides (Issue 005, §M7, Codex HIGH-2): every existing (legacy) caller
    omits both, so ``manifest_version`` stays :data:`MANIFEST_SCHEMA_VERSION`
    and ``determinism_checklist`` stays exactly :data:`DETERMINISM_CHECKLIST` —
    byte-for-byte unchanged. A society caller passes
    ``manifest_version=M2_MANIFEST_SCHEMA_VERSION`` and
    ``extra_determinism_checklist=M2_NBODY_DETERMINISM_CHECKLIST`` to get the
    N-agent pins appended.
    """
    agent_ids = sorted({r.agent_id for r in result.rows})
    world_tick_count = max((r.physics_tick_index for r in result.rows), default=-1) + 1
    cognition_ticks = len({r.agent_tick for r in result.rows})
    return {
        "manifest_version": (
            manifest_version
            if manifest_version is not None
            else MANIFEST_SCHEMA_VERSION
        ),
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": result.run_id,
            "seed": run_config["seed"],
            "agent_ids": agent_ids,
            "world_tick_count": world_tick_count,
            "cognition_ticks": cognition_ticks,
            "physics_ticks_per_cognition": run_config["physics_ticks_per_cognition"],
            "k_ecl": run_config["k_ecl"],
            "base_ts": run_config["base_ts"],
            "retrieval_now": run_config["retrieval_now"],
        },
        "coordinate_convention": COORDINATE_CONVENTION,
        "tick_mapping": TICK_MAPPING,
        "determinism_checklist": [
            *DETERMINISM_CHECKLIST,
            *extra_determinism_checklist,
        ],
        "canonical_json_rules": CANONICAL_JSON_RULES,
        "env_pins": env_pins if env_pins is not None else capture_env_pins(),
        "artifacts": {
            "ecl_trace.jsonl": {"sha256": _sha256(trace_jsonl)},
            "decisions.jsonl": {"sha256": _sha256(decisions_jsonl)},
            "envelope_stream.jsonl": {"sha256": _sha256(envelope_jsonl)},
        },
        "replay_checksum": result.checksum,
        "replay_checksum_algorithm": "sha256",
        # Derived from CANONICAL_JSON_RULES rather than a hardcoded literal so the
        # advertised checksum canonicalisation can never drift from the rules the
        # module actually applies (CR-M1). The checksum canonicalisation is exactly
        # these five keys (sort_keys + compact separators + ensure_ascii=False +
        # allow_nan=False + float_quantize_decimals, the last absorbing
        # cross-platform libm drift); float_repr / newline are JSONL-shape rules,
        # not part of the checksum contract, so they stay out.
        "replay_checksum_json_rules": {
            k: CANONICAL_JSON_RULES[k]
            for k in (
                "sort_keys",
                "separators",
                "ensure_ascii",
                "allow_nan",
                "float_quantize_decimals",
            )
        },
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
    result: EclRunResult,
    *,
    run_config: dict[str, Any] | None = None,
    env_pins: dict[str, Any] | None = None,
    manifest_version: str | None = None,
    extra_determinism_checklist: Sequence[str] = (),
) -> dict[str, str]:
    """Render the four handoff artifacts as ``{filename: text}`` (pure).

    Deterministic given ``result`` (and ``run_config`` / ``env_pins`` for
    ``manifest.json``): the caller writes the strings, or diffs them against the
    committed golden. ``run_config`` defaults to :func:`golden_run_config`.

    ``manifest_version`` / ``extra_determinism_checklist`` are additive M2-path
    passthroughs to :func:`build_manifest` (Issue 005, §M7, Codex HIGH-2): every
    existing (legacy) caller omits both, so this function's byte output is
    unchanged. A caller checking the M2 path's "canonical projection/adapter"
    equivalence (e.g. an N=1 society run projected via
    :func:`project_society_agent_to_ecl_result`) can still reuse this exact
    legacy-shaped renderer for ``ecl_trace.jsonl``/``decisions.jsonl``/
    ``envelope_stream.jsonl`` while tagging ``manifest.json`` with the M2
    schema version instead.
    """
    trace_jsonl = trace_rows_to_jsonl(result.rows)
    decisions_jsonl = decisions_to_jsonl(result.decisions)
    envelope_jsonl = envelope_stream_to_jsonl(build_envelope_stream(result))
    manifest = build_manifest(
        result,
        run_config=run_config if run_config is not None else golden_run_config(),
        trace_jsonl=trace_jsonl,
        decisions_jsonl=decisions_jsonl,
        envelope_jsonl=envelope_jsonl,
        env_pins=env_pins,
        manifest_version=manifest_version,
        extra_determinism_checklist=extra_determinism_checklist,
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
    run_config: dict[str, Any] | None = None,
    env_pins: dict[str, Any] | None = None,
) -> None:
    """Write the four handoff artifacts into ``out_dir`` (the only side-effect)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_golden(result, run_config=run_config, env_pins=env_pins)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


def render_society_golden(
    result: SocietyRunResult,
    *,
    run_config: dict[str, Any],
    env_pins: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render the M2 (N-agent) handoff artifact bundle (Issue 005, §M7).

    Same four-filename shape as :func:`render_golden` (``manifest.json`` /
    ``ecl_trace.jsonl`` / ``decisions.jsonl`` / ``envelope_stream.jsonl``), but:

    * ``ecl_trace.jsonl`` reuses :func:`trace_rows_to_jsonl` **unmodified**
      (already N-agent forward-compatible — every row already carries its own
      ``agent_id``/``order_slot``).
    * ``decisions.jsonl`` is :func:`society_decisions_to_jsonl` (order_slot +
      agent_id-tagged wrapper around the unmodified ``decision_to_dict``) since
      the legacy shape carries no agent identity.
    * ``envelope_stream.jsonl`` is :func:`build_society_envelope_stream` (a thin
      flattening adapter that calls the unmodified :func:`build_envelope_stream`).
    * ``manifest.json`` is tagged :data:`M2_MANIFEST_SCHEMA_VERSION` and its
      determinism checklist gains :data:`M2_NBODY_DETERMINISM_CHECKLIST`.

    ``run_config`` has no society-specific default (unlike :func:`render_golden`,
    which defaults to the fixed single-agent :func:`golden_run_config`) — the
    caller always supplies the actual society run's inputs, since there is no
    single canonical N-agent config to default to.
    """
    trace_jsonl = trace_rows_to_jsonl(result.rows)
    decisions_jsonl = society_decisions_to_jsonl(result)
    envelope_jsonl = envelope_stream_to_jsonl(build_society_envelope_stream(result))
    manifest = build_manifest(
        result,
        run_config=run_config,
        trace_jsonl=trace_jsonl,
        decisions_jsonl=decisions_jsonl,
        envelope_jsonl=envelope_jsonl,
        env_pins=env_pins,
        manifest_version=M2_MANIFEST_SCHEMA_VERSION,
        extra_determinism_checklist=M2_NBODY_DETERMINISM_CHECKLIST,
    )
    return {
        "manifest.json": canonical_dumps(manifest) + "\n",
        "ecl_trace.jsonl": trace_jsonl,
        "decisions.jsonl": decisions_jsonl,
        "envelope_stream.jsonl": envelope_jsonl,
    }


def _nonempty(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


__all__ = [
    "CANONICAL_FLOAT_DECIMALS",
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
    "M2_MANIFEST_SCHEMA_VERSION",
    "M2_NBODY_DETERMINISM_CHECKLIST",
    "MANIFEST_SCHEMA_VERSION",
    "TICK_MAPPING",
    "build_envelope_stream",
    "build_manifest",
    "build_society_decisions_stream",
    "build_society_envelope_stream",
    "canonical_dumps",
    "capture_env_pins",
    "decision_to_dict",
    "decisions_to_jsonl",
    "golden_agent_state",
    "golden_persona",
    "golden_recorded_calls",
    "golden_run_config",
    "project_society_agent_to_ecl_result",
    "recorded_calls_from_jsonl",
    "render_golden",
    "render_society_golden",
    "society_decisions_to_jsonl",
    "trace_row_from_dict",
    "trace_row_to_dict",
    "trace_rows_from_jsonl",
    "trace_rows_to_jsonl",
    "validate_envelope_stream",
    "write_golden",
]
