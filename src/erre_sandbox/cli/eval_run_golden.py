r"""``eval_run_golden`` — drive the m9-eval golden battery against live qwen3:8b.

This CLI is the m9-eval-system **P3a Step 1** entry point: it captures one
``(persona, condition, run_idx)`` cell into a fresh DuckDB file under the
``raw_dialog`` schema enforced by
:mod:`erre_sandbox.contracts.eval_paths` / :mod:`erre_sandbox.evidence.eval_store`.

Two conditions, single CLI:

* ``--condition stimulus`` — drives :class:`GoldenBaselineDriver` with a
  **stratified slice** of ``golden/stimulus/<persona>.yaml`` so the focal
  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
  No WorldRuntime is needed; each stimulus opens / drives / closes a single
  dialog through the public scheduler API.
* ``--condition natural`` — replicates :func:`erre_sandbox.bootstrap.bootstrap`
  headlessly (no uvicorn): MemoryStore (sqlite) + EmbeddingClient +
  CognitionCycle + WorldRuntime + InMemoryDialogScheduler +
  OllamaDialogTurnGenerator. Three personas (kant + nietzsche + rikyu) are
  registered in :attr:`Zone.AGORA`; the watchdog stops the runtime once the
  focal speaker has uttered ``--turn-count`` turns.

Design properties:

* :func:`_stratified_stimulus_slice` keeps proportional category
  representation instead of YAML-prefix slicing.
* focal speaker turn budget for both conditions (driver alternates
  speakers on multi-turn stimuli).
* DuckDB sink is **fail-fast**; an INSERT error sets the run
  ``fatal_error`` flag and aborts before any atomic rename.
* capture writes to ``<output>.tmp``; pre-existing ``<output>``
  refuses unless ``--overwrite`` is passed; final ``atomic_temp_rename``
  is the only path that publishes the result file.
* natural-condition scheduler RNG is seeded with
  :func:`derive_seed` so admission auto-fire is reproducible per ``run_idx``.
* ``runtime.stop()`` is followed by
  ``asyncio.wait_for(runtime_task, grace_s)``; on timeout the run is
  abandoned (no rename) so partial captures cannot masquerade as complete.

The ``mode`` raw column is **left empty**: the column is
reserved for ERRE mode in the live-run contract, while the stimulus / natural
condition is encoded in ``run_id`` instead.

Usage::

    python -m erre_sandbox.cli.eval_run_golden \\
        --persona kant --run-idx 0 --condition stimulus \\
        --turn-count 200 --cycle-count 3 \\
        --output data/eval/pilot/kant_stimulus_run0.duckdb
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, assert_never, cast

import duckdb
import yaml

from erre_sandbox.bootstrap import _make_relational_sink, make_agent_id
from erre_sandbox.cognition import CognitionCycle, Reflector
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE, DefaultERREModePolicy
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    read_sidecar,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.eval_store import (
    atomic_temp_rename,
    bootstrap_schema,
    write_with_checkpoint,
)
from erre_sandbox.evidence.golden_baseline import (
    DEFAULT_INTERLOCUTOR_ID,
    DEFAULT_PERSONAS,
    GoldenBaselineDriver,
    assert_seed_manifest_consistent,
    derive_seed,
    load_seed_manifest,
    load_stimulus_battery,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as _HINT_ENGAGEMENT_TRACE_TABLE,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    bootstrap_hint_engagement_trace_schema,
    build_hint_engagement_trace_row,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    column_names as _hint_engagement_trace_columns,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME as _INDIVIDUAL_STATE_TRACE_TABLE,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    bootstrap_individual_state_trace_schema,
    build_individual_state_trace_row,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    column_names as _individual_state_trace_columns,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    TABLE_NAME as _FLOOR_INPUT_TRACE_TABLE,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    bootstrap_floor_input_trace_schema,
    build_floor_input_trace_row,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    column_names as _floor_input_trace_columns,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME as _SATURATION_TRACE_TABLE,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    bootstrap_saturation_trace_schema,
    build_saturation_trace_rows,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    column_names as _saturation_trace_columns,
)
from erre_sandbox.inference import (
    ChatMessage,
    OllamaChatClient,
    OllamaUnavailableError,
    compose_sampling,
)
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.integration.dialog_turn import OllamaDialogTurnGenerator
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import (
    AgentState,
    DialogTurnMsg,
    ERREMode,
    ERREModeName,
    PersonaSpec,
    Position,
    SamplingDelta,
    Zone,
)
from erre_sandbox.world import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import Literal

    from erre_sandbox.contracts.cognition_layers import (
        IndividualLayerConfig,
        IndividualProfile,
        PromotedEvidenceUnit,
        WorldModelHintDisposition,
        WorldModelSnapshot,
    )
    from erre_sandbox.evidence.capture_sidecar import CaptureStatus, StopReason

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TURN_COUNT: Final[int] = 200
"""Focal speaker turn budget per ``(persona, condition)`` cell (P3a target)."""

_DEFAULT_CYCLE_COUNT: Final[int] = 3
"""Stimulus battery cycle count — matches design-final.md P3 production."""

_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 120.0
"""Default wall budget (minutes) for the natural capture phase.

G-GEAR re-capture measured cognition_period ≈ 120 s/tick on qwen3:8b Q4_K_M.
With the v2 ``COOLDOWN_TICKS_EVAL=5`` and ``dialog_turn_budget=6``, one effective
cycle is ~11 ticks ≈ 22 min wall, so 120 min wall yields ~5 cycles ⇒
focal ≈ 24/cell as a conservative lower bound. 60 min is below the conservative
margin and was rejected; operators may still override via ``--wall-timeout-min``. Hard
wall-clock cap for one capture, primarily natural condition.
"""

_RUNTIME_DRAIN_GRACE_S: Final[float] = 60.0
"""Seconds to await ``runtime_task`` after ``runtime.stop()``.

This was raised from 30.0 to 60.0
because the natural-condition cognition tick is ≈ 120 s/tick on qwen3:8b
Q4_K_M; a 30 s grace promotes too many in-flight ticks to fatal. The cost
is +30 s × N(cell) ≈ +15 min over a 30-cell P3 sweep — negligible against
the run1 wall budget (≈ 10 h)."""

_NATURAL_AGORA_POSITIONS: Final[dict[str, tuple[float, float, float]]] = {
    # Three distinct seats inside AGORA so the M5/M6 separation nudge does
    # not perturb spawn coordinates the very first physics tick. AGORA uses
    # the default zone radius, well within the 5m proximity threshold so
    # all three pairs auto-fire.
    "kant": (0.0, 0.0, 0.0),
    "nietzsche": (0.8, 0.0, 0.0),
    "rikyu": (-0.8, 0.0, 0.0),
}

_NATURAL_AGORA_SEATS: Final[tuple[tuple[float, float, float], ...]] = tuple(
    _NATURAL_AGORA_POSITIONS.values()
)
"""Positional AGORA seats indexed by roster position (M11-C3b P-1).

The same-base launcher registers several individuals of *one* base persona,
so seats are assigned by roster index rather than persona id; reusing the same
three non-overlapping coordinates keeps every pair inside the proximity
threshold. The default (one-per-persona) roster keeps using the persona-keyed
:data:`_NATURAL_AGORA_POSITIONS`, so that path is byte-identical to before.

**Frozen at three seats** so the legacy :func:`build_natural_roster`
``same_base_count`` ValueError cap (``len(_NATURAL_AGORA_SEATS)``) stays at 3 —
the S4 population launcher uses the separate :data:`_NATURAL_POPULATION_SEATS`
instead (PR-S4a, DA-S4A-3)."""

_POPULATION_N_MAX: Final[int] = 31
"""Frozen population world-size ceiling (S4 pre-flight ADR §4.1 / stage C N_MAX).

D_max=30 ↔ world ≥ 31 (stage A §5.2). The S4 density-bearing run registers at
most this many agents (3 measured same-base + up to 28 background). Raising it
re-opens the frozen stage-C envelope (goalpost move), so it is pinned here and
asserted against the seat-table length below."""

_MEASURED_INDIVIDUAL_COUNT: Final[int] = 3
"""Frozen number of measured same-base individuals (⑤ N=3 / stage C, PR-S4a).

Stage C pins D = the promoted distinct-other count of **3** same-base measured
individuals; the disposition's N=3 binding forbids moving this goalpost. The
population builder rejects any other count (Codex MEDIUM, DA-S4A-6) so an
internal caller cannot silently widen / shrink the H2 comparison set."""


def _build_population_seats() -> tuple[tuple[float, float, float], ...]:
    """Build :data:`_NATURAL_POPULATION_SEATS` deterministically (PR-S4a).

    The first three seats are :data:`_NATURAL_AGORA_SEATS` byte-for-byte (so the
    three measured same-base individuals spawn on the exact C3b coordinates),
    followed by a deterministic grid of 28 distinct points at ``z >= 1.6`` so
    none collides with the legacy ``z == 0`` seats. Grid spacing is 1.6 m, above
    the widest persona ``separation_radius_m`` (1.5 m, Kant), so the M7ζ-3
    separation nudge does not fire between background seats on the first physics
    tick. eval_natural_mode bypasses proximity for dialog admission, so seat
    geometry never affects who can talk to whom — this only keeps spawn tidy.
    """
    seats: list[tuple[float, float, float]] = list(_NATURAL_AGORA_SEATS)
    seats.extend(
        (col * 1.6, 0.0, row * 1.6)
        for row in range(1, 5)  # z = 1.6, 3.2, 4.8, 6.4
        for col in range(-3, 4)  # x = -4.8 .. 4.8 (7 columns) -> 28 points
    )
    return tuple(seats)


_NATURAL_POPULATION_SEATS: Final[tuple[tuple[float, float, float], ...]] = (
    _build_population_seats()
)
"""Positional seats for the S4 population launcher (3 measured + 28 background).

Indexed by roster position like :data:`_NATURAL_AGORA_SEATS`; the first three
entries are identical to it. Kept separate from :data:`_NATURAL_AGORA_SEATS` so
the legacy launcher's ``same_base_count`` cap stays at 3 (byte-identical) — only
:func:`build_population_roster` scales up to :data:`_POPULATION_N_MAX`."""

# Module-load sentinels (Codex LOW): pin the frozen seat invariants at import so
# a regression fails immediately, not only under the test suite. Tests also
# assert all of them.
assert len(_NATURAL_AGORA_SEATS) == len(DEFAULT_PERSONAS), (
    "legacy _NATURAL_AGORA_SEATS must stay at the one-per-persona seat count"
    " (byte-identical same_base_count cap)"
)
assert len(_NATURAL_POPULATION_SEATS) == _POPULATION_N_MAX, (
    "population seat table must hold exactly _POPULATION_N_MAX seats"
)
assert _NATURAL_POPULATION_SEATS[:3] == _NATURAL_AGORA_SEATS, (
    "first 3 population seats must equal the legacy table byte-for-byte"
)
assert len(set(_NATURAL_POPULATION_SEATS)) == _POPULATION_N_MAX, (
    "population seats must all be distinct (distinct agent spawn coordinates)"
)

_PERSONAS_DIR_DEFAULT: Final[Path] = Path("personas")

_INFERENCE_RETRY_MAX_ATTEMPTS: Final[int] = 3
_INFERENCE_RETRY_BASE_S: Final[float] = 0.2
_INFERENCE_RETRY_MULTIPLIER: Final[float] = 4.0

_STIMULUS_NUM_PREDICT: Final[int] = 240
_STIMULUS_MCQ_NUM_PREDICT: Final[int] = 8
_STIMULUS_STOP: Final[tuple[str, ...]] = ("\n\n",)
_STIMULUS_MCQ_STOP: Final[tuple[str, ...]] = ("\n",)

_MCQ_DETERMINISTIC_SAMPLING: Final[SamplingDelta] = SamplingDelta(
    temperature=-1.0,  # clamp pulls to 0.01 minimum (deterministic enough)
    top_p=0.0,
    repeat_penalty=0.0,
)
"""``SamplingDelta`` floor used for MCQ inference (forces low temperature)."""

_MCQ_LANG_HINT: Final[str] = (
    "Answer with exactly one of the labels A, B, C, or D — no extra text."
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


class CaptureFatalError(Exception):
    """Raised by the DuckDB sink when a row INSERT fails — eval-fatal.

    The scheduler swallows sink exceptions in
    :meth:`InMemoryDialogScheduler.record_turn`, which is correct for live
    runs but not for eval. The matching ``state["fatal_error"]`` flag the
    sink also sets is the authoritative signal the watchdog / driver loop
    polls.
    """


@dataclass
class CaptureResult:
    """Returned from :func:`capture_stimulus` / :func:`capture_natural`.

    Used by the unit tests to assert row counts and selection metadata
    without re-opening the DuckDB file. The post-ME-9 fields encode the
    partial / fatal / complete trichotomy the sidecar persists:

    ``soft_timeout``
        Set when the watchdog hit ``--wall-timeout-min`` without reaching
        ``focal_target``. Mutually exclusive with ``fatal_error``.
    ``partial_capture``
        True iff ``soft_timeout is not None`` (cached for callers).
    ``stop_reason``
        Concrete reason the run terminated; pinned to
        :data:`erre_sandbox.evidence.capture_sidecar.StopReason`.
    ``drain_completed`` / ``runtime_drain_timeout``
        Whether ``runtime.stop()`` finished within the configured runtime
        drain grace (``capture_natural``'s ``runtime_drain_grace_s``, default
        ``_RUNTIME_DRAIN_GRACE_S`` = 60 s); ``True / False`` is the normal
        pair, ``False / True`` indicates a drain timeout (= fatal).
    ``selected_stimulus_ids``
        **Planned** stratified slice ids. Records
        what the run *intended* to consume so a partial run is replay-
        reproducible; the actually-observed subset is left to the audit
        layer / future ``event_log`` field.
    """

    run_id: str
    output_path: Path
    total_rows: int
    focal_rows: int
    fatal_error: str | None = None
    soft_timeout: str | None = None
    partial_capture: bool = False
    stop_reason: StopReason = "complete"
    drain_completed: bool = True
    runtime_drain_timeout: bool = False
    selected_stimulus_ids: list[str] = field(default_factory=list)
    elapsed_seconds: float | None = None
    """Measured runtime-phase wall clock (natural condition only, M11-C3b §5.3).

    ``time.monotonic()`` from the runtime task launch to the moment the
    watchdog returns (just before ``runtime.stop()``). This is the throughput
    denominator the C3b verdict uses — the *observed* elapsed, never the
    ``wall_timeout_min`` soft cap. ``None`` for the stimulus condition / a
    fatal that returns before the runtime phase starts."""

    seed: int | None = None
    """The ``uint64`` ``seed_root`` this run used (U4 provenance). Surfaced so
    ``_publish_capture`` can persist the *actual* seed into the sidecar — the
    versioned-verdict manifest builder pairs ON/OFF on the actual seed, which
    depends on the seed-manifest ``salt`` and so is not implied by ``run_idx``
    alone."""

    seed_salt: str | None = None
    """The seed-manifest ``salt`` that produced :attr:`seed` (its identity)."""


@dataclass
class _SinkState:
    """Shared mutable state surfaced to the watchdog / driver loop.

    The DuckDB sink owns the writes; counters here let async watchers /
    sync assertions reach the same numbers without poking at DuckDB
    mid-flight.

    ``fatal_error`` and ``soft_timeout`` follow a **fatal-precedence**
    policy: a fatal can land after a soft
    timeout (e.g. drain-grace expired after the wall budget already
    fired), and the capture must then refuse atomic rename. Conversely,
    once a fatal is recorded, ``set_soft_timeout`` is treated as a logic
    bug. :meth:`set_fatal` / :meth:`set_soft_timeout` are the canonical
    write paths and keep the policy machine-checked rather than relying
    on review of every assignment.

    ``drain_completed`` / ``runtime_drain_timeout`` mirror the names used
    on :class:`CaptureResult` for the sidecar payload; a clean drain is
    the default and the finally block flips them on TimeoutError.
    """

    total: int = 0
    focal: int = 0
    fatal_error: str | None = None
    soft_timeout: str | None = None
    drain_completed: bool = True
    runtime_drain_timeout: bool = False
    last_zone_by_speaker: dict[str, str] = field(default_factory=dict)

    def set_fatal(self, reason: str) -> None:
        """Record a fatal failure (first call wins; later calls are ignored)."""
        if self.fatal_error is None:
            self.fatal_error = reason

    def set_soft_timeout(self, reason: str) -> None:
        """Record a wall (soft) timeout; refuses if a fatal already landed.

        First call wins for soft timeouts as well — re-entry from a noisy
        watchdog loop is a bug but does not corrupt state.
        """
        if self.fatal_error is not None:
            msg = (
                f"set_soft_timeout({reason!r}) called after fatal_error"
                f" ({self.fatal_error!r}); fatal must take precedence"
            )
            raise AssertionError(msg)
        if self.soft_timeout is None:
            self.soft_timeout = reason


def _derive_stop_reason(state: _SinkState) -> StopReason:  # noqa: PLR0911
    """Map the in-process ``_SinkState`` to a canonical ``StopReason``.

    Pure helper so :func:`capture_stimulus` / :func:`capture_natural` and
    the CLI driver agree on how a fatal_error string maps to the published
    Literal. ``fatal_incomplete_before_target`` is *not* derivable here —
    that branch needs ``args.turn_count`` and is decided by
    :func:`_async_main` after the run returns.
    """
    if state.fatal_error is not None:
        msg = state.fatal_error
        if "duckdb insert" in msg:
            return "fatal_duckdb_insert"
        if "ollama unreachable" in msg:
            return "fatal_ollama"
        if "runtime drain exceeded" in msg:
            return "fatal_drain_timeout"
        if "runtime_task raised" in msg:
            return "fatal_runtime_exception"
        # Default fatal bucket — keeps the Literal closed without losing
        # the actual error text (sidecar persists ``fatal_error`` verbatim).
        return "fatal_runtime_exception"
    if state.soft_timeout is not None:
        return "wall_timeout"
    return "complete"


# ---------------------------------------------------------------------------
# Stimulus prompt builder (CLI-local; do not reach into
# integration.dialog_turn private symbols).
# ---------------------------------------------------------------------------


def _format_persona_habits(persona: PersonaSpec, *, limit: int = 3) -> str:
    habits = list(persona.cognitive_habits)[:limit]
    if not habits:
        return "(no habits recorded)"
    return "\n".join(f"- {h.description} [{h.flag.value}]" for h in habits)


def _build_stimulus_system_prompt(persona: PersonaSpec) -> str:
    """System prompt for the stimulus condition.

    Stimulus invocations have no transcript / addressee state; the persona
    block + a stimulus-aware instruction is enough. Order is load-bearing
    (RadixAttention prefix sharing across personas + a single-turn cue).
    """
    common = (
        "You are an autonomous agent in ERRE-Sandbox. A researcher hands you "
        "a curated stimulus from a Toulmin / Theory-of-Mind / RoleEval / "
        "moral-dilemma battery. Stay in character; speak as yourself, not "
        "about yourself."
    )
    persona_block = (
        f"Persona: {persona.display_name} ({persona.era}).\n"
        f"Cognitive habits:\n{_format_persona_habits(persona)}"
    )
    closing = (
        "Respond in a single concise utterance: at most 80 Japanese characters "
        "or 160 Latin characters. Return ONLY the utterance text — no names, "
        "no quotation marks, no stage directions, no JSON, no chain-of-thought."
    )
    return f"{common}\n\n{persona_block}\n\n{closing}"


def _build_stimulus_user_prompt(
    stimulus: dict[str, Any],
    *,
    cycle_idx: int,
    turn_index: int,
    mcq_options: dict[str, str] | None,
) -> str:
    """User prompt for a single stimulus turn.

    For multi-turn stimuli (``expected_turn_count > 1``) the cue includes the
    turn position so the model knows where in the stimulus arc it is. MCQ
    items get the post-shuffle option block + the deterministic instruction.
    """
    prompt_text = str(stimulus.get("prompt_text", "")).strip()
    category = str(stimulus.get("category", ""))
    body = (
        f"[stimulus_id={stimulus.get('stimulus_id', '?')} category={category} "
        f"cycle={cycle_idx} turn={turn_index}]\n\n{prompt_text}"
    )
    if mcq_options is not None:
        options_block = "\n".join(
            f"({label}) {text}" for label, text in mcq_options.items()
        )
        body = f"{body}\n\nOptions:\n{options_block}\n\n{_MCQ_LANG_HINT}"
    return body


# ---------------------------------------------------------------------------
# Inference factories
# ---------------------------------------------------------------------------


async def _retrying_chat(
    client: OllamaChatClient,
    messages: list[ChatMessage],
    *,
    sampling_delta: SamplingDelta,
    persona_spec: PersonaSpec,
    options: dict[str, Any],
) -> str | None:
    """Issue ``chat()`` with bounded retry; return ``None`` on terminal failure.

    Retries only on :class:`OllamaUnavailableError` (transient HTTP / parse
    issues). Logical content failures fall through to the caller, which
    handles MCQ-specific scoring on the resulting empty string.
    """
    last_exc: OllamaUnavailableError | None = None
    sampling = compose_sampling(persona_spec.default_sampling, sampling_delta)
    for attempt in range(_INFERENCE_RETRY_MAX_ATTEMPTS):
        try:
            resp = await client.chat(
                messages,
                sampling=sampling,
                options=options,
                think=False,
            )
        except OllamaUnavailableError as exc:
            last_exc = exc
            wait_s = _INFERENCE_RETRY_BASE_S * (_INFERENCE_RETRY_MULTIPLIER**attempt)
            logger.warning(
                "ollama chat failed attempt=%d/%d: %s — backing off %.2fs",
                attempt + 1,
                _INFERENCE_RETRY_MAX_ATTEMPTS,
                exc,
                wait_s,
            )
            await asyncio.sleep(wait_s)
            continue
        return str(resp.content)
    logger.error(
        "ollama chat exhausted %d attempts: %s",
        _INFERENCE_RETRY_MAX_ATTEMPTS,
        last_exc,
    )
    return None


def _make_stimulus_inference_fn(
    *,
    client: OllamaChatClient,
    persona_spec: PersonaSpec,
    sink_state: _SinkState,
    loop: asyncio.AbstractEventLoop,
) -> Callable[..., str]:
    """Build the synchronous ``inference_fn`` consumed by GoldenBaselineDriver.

    The driver expects a sync callable; we hop onto the supplied event loop
    via ``run_coroutine_threadsafe`` because the driver itself runs on the
    main thread (the loop is being driven by ``asyncio.run``). Aborts the
    capture when ``sink_state.fatal_error`` is set (propagation).
    """
    system_prompt = _build_stimulus_system_prompt(persona_spec)

    def inference_fn(
        *,
        persona_id: str,
        stimulus: dict[str, Any],
        cycle_idx: int,
        turn_index: int,
        prior_turns: tuple[DialogTurnMsg, ...],
        mcq_shuffled_options: dict[str, str] | None,
    ) -> str:
        del persona_id, prior_turns  # honoured by the driver but not used here
        if sink_state.fatal_error is not None:
            raise CaptureFatalError(sink_state.fatal_error)
        is_mcq = mcq_shuffled_options is not None
        user_prompt = _build_stimulus_user_prompt(
            stimulus,
            cycle_idx=cycle_idx,
            turn_index=turn_index,
            mcq_options=mcq_shuffled_options,
        )
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        sampling_delta = _MCQ_DETERMINISTIC_SAMPLING if is_mcq else SamplingDelta()
        options: dict[str, Any] = {
            "num_predict": (
                _STIMULUS_MCQ_NUM_PREDICT if is_mcq else _STIMULUS_NUM_PREDICT
            ),
            "stop": list(_STIMULUS_MCQ_STOP if is_mcq else _STIMULUS_STOP),
        }
        future = asyncio.run_coroutine_threadsafe(
            _retrying_chat(
                client,
                messages,
                sampling_delta=sampling_delta,
                persona_spec=persona_spec,
                options=options,
            ),
            loop,
        )
        result = future.result()
        return result if result is not None else ""

    return inference_fn


# ---------------------------------------------------------------------------
# DuckDB sink
# ---------------------------------------------------------------------------


def _make_duckdb_sink(
    *,
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    focal_persona_id: str,
    persona_resolver: Callable[[str], str | None] | None,
    fallback_speaker_persona: str,
    fallback_addressee_persona: str,
    zone_resolver: Callable[[str, str], str],
    state: _SinkState,
    enough_event: asyncio.Event | None = None,
    focal_budget: int | None = None,
    individual_layer_enabled: bool = False,
) -> Callable[[DialogTurnMsg], None]:
    """Construct the synchronous closure stored in the scheduler ``turn_sink``.

    Any DuckDB INSERT failure sets ``state.fatal_error`` and
    raises :class:`CaptureFatalError`. The scheduler logs and continues, but the
    capture loop polls ``state.fatal_error`` and aborts before any atomic
    rename can publish a half-written file.

    The 16 ALLOWED_RAW_DIALOG_KEYS columns are bound positionally so a
    drift of either side (DDL vs allow-list) trips the existing
    ``_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS`` import-time check
    in :mod:`evidence.eval_store` first. PR-Z (20260529) wires the 16th column
    ``individual_layer_enabled`` via the keyword-only ``individual_layer_enabled``
    argument so flag-on natural runs record ``TRUE`` and ADR §10 P-1 preflight
    obtains a machine-readable distinction; the default ``False`` keeps
    ``capture_stimulus`` (and any other dormant caller that does not pass the
    kwarg) on a semantic/logical row-content path identical to the pre-PR-Z
    DEFAULT-FALSE behaviour, excluding the non-deterministic ``created_at``.
    """

    def _resolve_personas(turn: DialogTurnMsg) -> tuple[str, str]:
        if persona_resolver is None:
            return fallback_speaker_persona, fallback_addressee_persona
        sp = persona_resolver(turn.speaker_id) or fallback_speaker_persona
        ap = persona_resolver(turn.addressee_id) or fallback_addressee_persona
        return sp, ap

    def sink(turn: DialogTurnMsg) -> None:
        if state.fatal_error is not None:
            return
        speaker_pid, addressee_pid = _resolve_personas(turn)
        row_id = f"{run_id}:{turn.dialog_id}:{turn.turn_index}"
        zone_label = zone_resolver(turn.speaker_id, turn.dialog_id)
        try:
            # B-1 / PR-Z (20260529): the ``individual_layer_enabled``
            # column is written explicitly from the kwarg of the
            # same name (default ``False`` for stimulus and any
            # caller that does not pass the kwarg, propagated as
            # ``individual_layer_on`` from ``capture_natural`` —
            # see eval_run_golden.py:1317 + the sink construction
            # roughly 100 lines below). The DDL constraint
            # ``BOOLEAN NOT NULL DEFAULT FALSE`` in
            # ``eval_store._RAW_DIALOG_DDL_COLUMNS`` remains the
            # safety floor; explicit binding lifts the partial
            # M10-A "truthy-setting branch" deferral so ADR §10
            # P-1 preflight (matrix-validator) obtains a
            # machine-readable flag-on / flag-off distinction at
            # capture time. INSERT order matches
            # ``_RAW_DIALOG_DDL_COLUMNS`` ordinal_position
            # exactly (lockstep guard, enforced by
            # the new unit test in
            # tests/test_cli/test_eval_run_golden_individual_layer_provenance.py).
            con.execute(
                "INSERT INTO raw_dialog.dialog"
                ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
                ' "speaker_agent_id", "speaker_persona_id",'
                ' "addressee_agent_id", "addressee_persona_id",'
                ' "utterance", "mode", "zone", "reasoning",'
                ' "epoch_phase", "individual_layer_enabled", "created_at")'
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row_id,
                    run_id,
                    turn.dialog_id,
                    turn.tick,
                    turn.turn_index,
                    turn.speaker_id,
                    speaker_pid,
                    turn.addressee_id,
                    addressee_pid,
                    turn.utterance,
                    "",  # mode left empty (reserved for ERRE mode)
                    zone_label,
                    "",
                    "autonomous",
                    individual_layer_enabled,
                    datetime.now(UTC),
                ),
            )
        except duckdb.Error as exc:
            state.set_fatal(f"duckdb insert failed: {exc!r}")
            raise CaptureFatalError(state.fatal_error) from exc

        state.total += 1
        if speaker_pid == focal_persona_id:
            state.focal += 1
            if (
                focal_budget is not None
                and state.focal >= focal_budget
                and enough_event is not None
                and not enough_event.is_set()
            ):
                enough_event.set()

    return sink


def _make_individual_trace_sink(
    *,
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    state: _SinkState,
) -> Callable[
    [IndividualProfile, list[str] | None, list[PromotedEvidenceUnit] | None, int],
    None,
]:
    """Construct the flag-on individual-state trace sink (M11-C2 / M10-A 段B).

    Mirrors :func:`_make_duckdb_sink`'s error contract: a DuckDB
    INSERT failure sets ``state.fatal_error`` and raises
    :class:`CaptureFatalError`, so a half-written trace cannot publish through
    the atomic rename. ``run_id`` is bound here so ``WorldRuntime`` never learns
    it (DA-M11C2-4); the row is built from the C1 ``IndividualProfile`` snapshot
    plus the ``CycleResult`` belief classes **and** per-dyad raw evidence units
    (M10-A 段B H2 substrate), so ``world`` imports neither ``evidence`` nor
    ``memory`` (DA-M11C2-2 / DA-SB-1). Column order tracks
    ``trace_ddl.column_names()`` in lockstep, and the qualified table name is
    composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI grep gate).
    """
    cols = _individual_state_trace_columns()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{_INDIVIDUAL_STATE_TRACE_TABLE}"  # noqa: S608 — static identifiers only
        f" ({columns_sql}) VALUES ({placeholders})"
    )

    def sink(
        profile: IndividualProfile,
        belief_classes: list[str] | None,
        world_model_evidence: list[PromotedEvidenceUnit] | None,
        tick: int,
    ) -> None:
        if state.fatal_error is not None:
            return
        row = build_individual_state_trace_row(
            profile, belief_classes, world_model_evidence, run_id=run_id, tick=tick
        )
        try:
            con.execute(insert_sql, row.to_row())
        except duckdb.Error as exc:
            state.set_fatal(f"duckdb individual_state_trace insert failed: {exc!r}")
            raise CaptureFatalError(state.fatal_error) from exc

    return sink


def _make_saturation_trace_sink(
    *,
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    seed: int,
    individual_layer_enabled: bool,
    state: _SinkState,
) -> Callable[[str, WorldModelSnapshot, int], None]:
    """Construct the flag-on saturation trace sink (saturation ADR section 5).

    Mirrors :func:`_make_individual_trace_sink`'s error contract: a DuckDB INSERT
    failure sets ``state.fatal_error`` and raises :class:`CaptureFatalError`, so a
    half-written trace cannot publish through the atomic rename. ``run_id`` /
    ``seed`` / ``individual_layer_enabled`` are bound here so ``WorldRuntime`` never
    learns the run identity; the rows are built from the post-reconcile pre-nudge
    ``WorldModelSnapshot`` carried off ``CycleResult`` (ADR section 2.1), so
    ``world`` imports neither ``evidence`` nor ``cognition``. ``seed`` is the
    ``derive_seed`` uint64 (UBIGINT column; DA-IMPL-2), bound explicitly alongside
    ``individual_layer_enabled`` so the loader can reject a provenance-false seed
    (avoids the M11-C3b-exec column-omission bug). Column order tracks
    ``_saturation_trace_columns()`` in lockstep, and the qualified table name is
    composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI grep gate).
    """
    cols = _saturation_trace_columns()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{_SATURATION_TRACE_TABLE}"  # noqa: S608 — static identifiers only
        f" ({columns_sql}) VALUES ({placeholders})"
    )

    def sink(individual_id: str, snapshot: WorldModelSnapshot, tick: int) -> None:
        if state.fatal_error is not None:
            return
        rows = build_saturation_trace_rows(
            snapshot,
            run_id=run_id,
            seed=seed,
            individual_id=individual_id,
            tick=tick,
            individual_layer_enabled=individual_layer_enabled,
        )
        try:
            for row in rows:
                con.execute(insert_sql, row.to_row())
        except duckdb.Error as exc:
            state.set_fatal(
                f"duckdb swm_modulation_saturation_trace insert failed: {exc!r}"
            )
            raise CaptureFatalError(state.fatal_error) from exc

    return sink


def _make_hint_engagement_trace_sink(
    *,
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    seed: int,
    individual_layer_enabled: bool,
    state: _SinkState,
) -> Callable[[str, WorldModelHintDisposition, int], None]:
    """Construct the flag-on hint-engagement trace sink (engagement instrument ADR §5).

    Mirrors :func:`_make_saturation_trace_sink`'s error contract: a DuckDB INSERT
    failure sets ``state.fatal_error`` and raises :class:`CaptureFatalError`, so a
    half-written trace cannot publish through the atomic rename. ``run_id`` / ``seed`` /
    ``individual_layer_enabled`` are bound here so ``WorldRuntime`` never learns the run
    identity; the row is built from the :class:`WorldModelHintDisposition` carried off
    ``CycleResult`` (a ``contracts`` read-model), so ``world`` imports neither
    ``evidence`` nor ``cognition``. ``individual_layer_enabled`` is bound explicitly
    alongside ``seed`` so the loader can reject a provenance-false seed (avoids the
    M11-C3b-exec column-omission bug). Column order tracks
    ``_hint_engagement_trace_columns()`` in lockstep, and the qualified table name is
    composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI grep gate).
    """
    cols = _hint_engagement_trace_columns()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{_HINT_ENGAGEMENT_TRACE_TABLE}"  # noqa: S608 — static identifiers only
        f" ({columns_sql}) VALUES ({placeholders})"
    )

    def sink(
        individual_id: str, disposition: WorldModelHintDisposition, tick: int
    ) -> None:
        if state.fatal_error is not None:
            return
        row = build_hint_engagement_trace_row(
            disposition,
            run_id=run_id,
            seed=seed,
            individual_id=individual_id,
            tick=tick,
            individual_layer_enabled=individual_layer_enabled,
        )
        try:
            con.execute(insert_sql, row.to_row())
        except duckdb.Error as exc:
            state.set_fatal(f"duckdb swm_hint_engagement_trace insert failed: {exc!r}")
            raise CaptureFatalError(state.fatal_error) from exc

    return sink


def _make_floor_input_trace_sink(
    *,
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    seed: int,
    individual_layer_enabled: bool,
    state: _SinkState,
) -> Callable[[str, WorldModelSnapshot, int], None]:
    """Construct the flag-on reconcile-input floor trace sink (U5 replay infra).

    Mirrors :func:`_make_saturation_trace_sink`'s error contract: a DuckDB INSERT
    failure sets ``state.fatal_error`` and raises :class:`CaptureFatalError`, so a
    half-written trace cannot publish through the atomic rename. ``run_id`` / ``seed`` /
    ``individual_layer_enabled`` are bound here so ``WorldRuntime`` never learns the run
    identity; the row is built from the **same** post-reconcile pre-nudge
    ``WorldModelSnapshot`` the saturation sink reads, but persists the full
    ``snapshot.base_floor`` (the reconcile input) so a deterministic replay can re-feed
    it into the unchanged ``reconcile_world_model`` kernel — the lossy saturation trace
    cannot. ``seed`` is the ``derive_seed`` uint64 (UBIGINT column), bound explicitly
    alongside ``individual_layer_enabled`` so a reader can reject a provenance-false
    seed. Column order tracks ``_floor_input_trace_columns()`` in lockstep, and the
    qualified table name is composed from ``METRICS_SCHEMA`` (never a schema-dot
    literal; CI grep gate).
    """
    cols = _floor_input_trace_columns()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{_FLOOR_INPUT_TRACE_TABLE}"  # noqa: S608 — static identifiers only
        f" ({columns_sql}) VALUES ({placeholders})"
    )

    def sink(individual_id: str, snapshot: WorldModelSnapshot, tick: int) -> None:
        if state.fatal_error is not None:
            return
        row = build_floor_input_trace_row(
            snapshot,
            run_id=run_id,
            seed=seed,
            individual_id=individual_id,
            tick=tick,
            individual_layer_enabled=individual_layer_enabled,
        )
        try:
            con.execute(insert_sql, row.to_row())
        except duckdb.Error as exc:
            state.set_fatal(f"duckdb swm_floor_input_trace insert failed: {exc!r}")
            raise CaptureFatalError(state.fatal_error) from exc

    return sink


# ---------------------------------------------------------------------------
# Stratified slicing
# ---------------------------------------------------------------------------


def _focal_turn_count(stimulus: dict[str, Any]) -> int:
    """Approximate per-stimulus focal-speaker turn count.

    The driver alternates speakers (turn 0 = focal, turn 1 = interlocutor, …)
    so over ``expected_turn_count = n`` turns the focal persona speaks
    ``ceil(n / 2)`` times. This approximation is exact for n=1 (MCQ) and
    n=2; for n=3 it matches the driver's interleaving deterministically.
    """
    expected = int(stimulus.get("expected_turn_count", 1))
    return (expected + 1) // 2


def _stratified_stimulus_slice(  # noqa: C901 — proportional rebalance is inherently branchy
    battery: list[dict[str, Any]],
    *,
    target_focal_per_cycle: int,
) -> list[dict[str, Any]]:
    """Stratify the battery so the slice's category mix matches the original.

    Each category contributes proportionally to its share of the battery's
    total focal-speaker turns; within a category, YAML order is preserved
    (deterministic). When ``target_focal_per_cycle`` exceeds the battery's
    focal-turn capacity the full battery is returned (no oversampling).
    """
    if target_focal_per_cycle <= 0:
        return []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for stim in battery:
        by_cat[str(stim.get("category", ""))].append(stim)

    total_focal = sum(_focal_turn_count(s) for s in battery)
    if total_focal == 0:
        return []
    if target_focal_per_cycle >= total_focal:
        return list(battery)

    selected: list[dict[str, Any]] = []
    chosen_focal = 0
    for cat, stims in by_cat.items():
        cat_focal = sum(_focal_turn_count(s) for s in stims)
        # Use ratio rounded to nearest int — sum of ratios may differ from
        # target by a small amount, which we re-balance after the loop.
        share = round(cat_focal / total_focal * target_focal_per_cycle)
        cum = 0
        for stim in stims:
            cf = _focal_turn_count(stim)
            if cum + cf > share:
                break
            selected.append(stim)
            cum += cf
        chosen_focal += cum
        del cat  # quiet linter; cat was for loop binding only

    # Rebalance: if the sum of category shares undershot the target due to
    # rounding, top up by appending the next stimulus from the largest
    # under-represented category until we hit target. Capped at battery
    # length so we cannot oversample.
    if chosen_focal < target_focal_per_cycle:
        remaining: list[dict[str, Any]] = [s for s in battery if s not in selected]
        for stim in remaining:
            if chosen_focal >= target_focal_per_cycle:
                break
            selected.append(stim)
            chosen_focal += _focal_turn_count(stim)

    # Preserve the battery's YAML order (rebalance step may interleave),
    # which keeps cycle-1 / cycle-N pairing identical across test runs.
    selected_ids = {s.get("stimulus_id") for s in selected}
    return [s for s in battery if s.get("stimulus_id") in selected_ids]


# ---------------------------------------------------------------------------
# Persona / agent helpers
# ---------------------------------------------------------------------------


def _load_persona(personas_dir: Path, persona_id: str) -> PersonaSpec:
    path = personas_dir / f"{persona_id}.yaml"
    return PersonaSpec.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8")),
    )


def _initial_state_for_natural(
    persona: PersonaSpec,
    *,
    ordinal: int = 1,
    seat: tuple[float, float, float] | None = None,
) -> AgentState:
    """Build the AgentState used to register an individual for the natural run.

    Mirrors :func:`erre_sandbox.bootstrap._build_initial_state` but pins
    the spawn ``Position`` to a non-overlapping seat inside :attr:`Zone.AGORA`
    so the M5/M6 separation nudge does not fire on the first physics tick.

    ``ordinal`` (1-based) selects the same-base individual id via
    :func:`~erre_sandbox.bootstrap.make_agent_id`; ``ordinal=1`` reproduces the
    historical ``a_<persona_id>_001`` byte-for-byte (M11-C3b P-1, DA-M11C-2).
    ``seat is None`` falls back to the persona-keyed default seat (the
    one-per-persona roster), so that path stays byte-identical; the same-base
    launcher passes an explicit positional seat per roster index.
    """
    pid = persona.persona_id
    if seat is None:
        seat = _NATURAL_AGORA_POSITIONS.get(pid, (0.0, 0.0, 0.0))
    erre_name = ZONE_TO_DEFAULT_ERRE_MODE.get(Zone.AGORA, ERREModeName.DEEP_WORK)
    return AgentState(
        agent_id=make_agent_id(pid, ordinal),
        persona_id=pid,
        tick=0,
        position=Position(x=seat[0], y=seat[1], z=seat[2], zone=Zone.AGORA),
        erre=ERREMode(name=erre_name, entered_at_tick=0),
    )


def build_natural_roster(
    focal_persona: str,
    *,
    same_base_count: int | None = None,
) -> tuple[tuple[str, int], ...]:
    """Return the ``(base_persona_id, ordinal)`` roster the natural run registers.

    ``same_base_count is None`` (default) yields the historical one-per-persona
    roster — ``[(pid, 1) for pid in DEFAULT_PERSONAS]`` — so the registration
    loop stays byte-identical. A non-None count yields ``same_base_count``
    individuals of ``focal_persona`` (``a_<persona>_001 .. _NNN``), the M11-C3b
    same-base launcher (ADR §10 P-1).

    Raises:
        ValueError: ``same_base_count`` is < 1 or exceeds the number of
            distinct AGORA seats (:data:`_NATURAL_AGORA_SEATS`).
    """
    if same_base_count is None:
        return tuple((pid, 1) for pid in DEFAULT_PERSONAS)
    if same_base_count < 1:
        msg = f"same_base_count must be >= 1, got {same_base_count}"
        raise ValueError(msg)
    if same_base_count > len(_NATURAL_AGORA_SEATS):
        msg = (
            f"same_base_count={same_base_count} exceeds the {len(_NATURAL_AGORA_SEATS)}"
            " distinct AGORA seats available; add seats before scaling individuals"
        )
        raise ValueError(msg)
    return tuple((focal_persona, ordinal) for ordinal in range(1, same_base_count + 1))


def _register_natural_roster(
    runtime: WorldRuntime,
    roster: Sequence[tuple[str, int]],
    persona_specs: Mapping[str, PersonaSpec],
    *,
    same_base: bool,
) -> None:
    """Register every roster individual into *runtime* (M11-C3b P-1 launcher seam).

    Extracted from :func:`capture_natural` so the registration (3 same-base
    individuals get distinct ``agent_id`` + distinct seats) is verifiable
    offline with a stub runtime — no Ollama / SGLang health check, no real
    inference (MED-3). For the default one-per-persona roster (``same_base`` is
    ``False``) the seat is the persona-keyed default, keeping the path
    byte-identical to before.
    """
    for index, (base_pid, ordinal) in enumerate(roster):
        spec = persona_specs[base_pid]
        seat = _NATURAL_AGORA_SEATS[index] if same_base else None
        runtime.register_agent(
            _initial_state_for_natural(spec, ordinal=ordinal, seat=seat), spec
        )


@dataclass(frozen=True, slots=True)
class NaturalPopulationRoster:
    """The S4 population roster: 3 measured same-base + (N-3) background (PR-S4a).

    ``measured`` is the same-base individuals of ``focal_persona`` whose
    individuation H2 statistic the density audit compares
    (``a_<focal>_001 .. _MMM``). ``background`` is the cross-base, non-focal
    distinct-other supply that is **not** an H2 comparison subject (disposition
    §2.4). Keeping the two in separate fields lets PR-S4c aggregate per-owner
    density over the measured individuals only, and lets the G0-1 smoke gate
    assert the split offline.
    """

    focal_persona: str
    measured: tuple[tuple[str, int], ...]
    background: tuple[tuple[str, int], ...]

    @property
    def measured_individual_ids(self) -> tuple[str, ...]:
        """Resolve the measured roster to concrete ``a_<focal>_NNN`` agent ids."""
        return tuple(make_agent_id(pid, ordinal) for pid, ordinal in self.measured)

    @property
    def world_size(self) -> int:
        """Total registered agents = ``len(measured) + len(background)``."""
        return len(self.measured) + len(self.background)

    def all_entries(self) -> tuple[tuple[str, int], ...]:
        """Registration order = measured first, then background (seat order)."""
        return self.measured + self.background


def build_population_roster(
    focal_persona: str,
    *,
    world_size: int,
    measured_count: int = _MEASURED_INDIVIDUAL_COUNT,
) -> NaturalPopulationRoster:
    """Build the S4 population roster (3 measured same-base + background supply).

    ``measured`` is :data:`_MEASURED_INDIVIDUAL_COUNT` (=3, frozen ⑤ N=3)
    individuals of ``focal_persona`` (``a_<focal>_001 .. _003``); ``background``
    is ``world_size - measured_count`` cross-base individuals drawn round-robin
    from the **non-focal** :data:`DEFAULT_PERSONAS`, so the loader's same-base
    ``base_groups`` isolates the focal trio cleanly for the density audit
    (PR-S4c). The ``measured_count`` parameter is kept for signature clarity but
    is pinned to 3 — any other value is rejected (Codex MEDIUM, DA-S4A-6) so an
    internal caller cannot widen / shrink the H2 comparison set. The legacy
    one-per-persona / same-base launchers (:func:`build_natural_roster`) are
    untouched — this is a separate API (DA-S4A-1/3).

    Raises:
        ValueError: ``focal_persona`` is not a DEFAULT persona; ``measured_count``
            != :data:`_MEASURED_INDIVIDUAL_COUNT` (frozen 3); ``world_size`` <
            ``measured_count``; ``world_size`` exceeds :data:`_POPULATION_N_MAX`;
            or no non-focal persona exists to supply a requested background.
    """
    if focal_persona not in DEFAULT_PERSONAS:
        msg = (
            f"focal_persona={focal_persona!r} is not part of the natural-condition"
            f" agent set ({DEFAULT_PERSONAS})"
        )
        raise ValueError(msg)
    if measured_count != _MEASURED_INDIVIDUAL_COUNT:
        msg = (
            f"measured_count must equal the frozen _MEASURED_INDIVIDUAL_COUNT"
            f" ({_MEASURED_INDIVIDUAL_COUNT}, ⑤ N=3 / stage C), got {measured_count};"
            " the measured same-base set is fixed and may not be re-sized"
        )
        raise ValueError(msg)
    if world_size < measured_count:
        msg = f"world_size={world_size} must be >= measured_count={measured_count}"
        raise ValueError(msg)
    if world_size > _POPULATION_N_MAX:
        msg = (
            f"world_size={world_size} exceeds the frozen population ceiling"
            f" _POPULATION_N_MAX={_POPULATION_N_MAX}; add seats / re-open stage C"
            " before scaling the world"
        )
        raise ValueError(msg)

    measured = tuple(
        (focal_persona, ordinal) for ordinal in range(1, measured_count + 1)
    )
    non_focal = tuple(pid for pid in sorted(DEFAULT_PERSONAS) if pid != focal_persona)
    background_count = world_size - measured_count
    background: list[tuple[str, int]] = []
    if background_count > 0:
        if not non_focal:
            msg = (
                "no non-focal personas available to supply background agents"
                f" (DEFAULT_PERSONAS={DEFAULT_PERSONAS}, focal={focal_persona!r})"
            )
            raise ValueError(msg)
        for i in range(background_count):
            pid = non_focal[i % len(non_focal)]
            ordinal = i // len(non_focal) + 1
            background.append((pid, ordinal))
    return NaturalPopulationRoster(
        focal_persona=focal_persona,
        measured=measured,
        background=tuple(background),
    )


def _register_population_roster(
    runtime: WorldRuntime,
    roster: NaturalPopulationRoster,
    persona_specs: Mapping[str, PersonaSpec],
) -> None:
    """Register a population roster into *runtime* (S4 launcher seam, PR-S4a).

    Each entry (measured then background, seat order) gets a distinct
    :data:`_NATURAL_POPULATION_SEATS` seat by index and a distinct ``agent_id``;
    ``register_agent`` raises on a duplicate id so a launcher bug surfaces at
    registration. Verifiable offline with a stub runtime — no Ollama / SGLang
    health check, no real inference (MED-3). The legacy
    :func:`_register_natural_roster` is untouched.
    """
    for index, (base_pid, ordinal) in enumerate(roster.all_entries()):
        spec = persona_specs[base_pid]
        seat = _NATURAL_POPULATION_SEATS[index]
        runtime.register_agent(
            _initial_state_for_natural(spec, ordinal=ordinal, seat=seat), spec
        )


# ---------------------------------------------------------------------------
# Output path / overwrite policy
# ---------------------------------------------------------------------------


ALLOWED_MEMORY_DB_PREFIX_STRINGS: Final[tuple[str, ...]] = (
    "/tmp/p3a_natural_",  # noqa: S108 — back-compat ME-2 default location
    "/tmp/erre-",  # noqa: S108 — new convention for ad-hoc eval scratch
)
# Basename prefixes under /tmp that are allowed (i.e. the basename of the
# immediate child under /tmp). Used by ``_is_allowed_memory_db_prefix`` so the
# check works regardless of whether /tmp is a symlink to /private/tmp (macOS).
_ALLOWED_MEMORY_DB_TMP_BASENAME_PREFIXES: Final[tuple[str, ...]] = (
    "p3a_natural_",
    "erre-",
)


def _is_allowed_memory_db_prefix(path: Path) -> bool:
    """Check whether ``path`` falls under an allowlisted memory-db location.

    Allowed locations (SH-4 ADR, 2026-05-13):

    * ``/tmp/p3a_natural_*`` — back-compat ME-2 default (auto-managed)
    * ``/tmp/erre-*`` — new naming convention for ad-hoc eval scratch
    * ``<cwd>/var/eval/...`` — repo-relative persistent eval store

    Any other path (e.g. ``/etc/passwd``, ``/home/me/important.sqlite``) is
    rejected so a typo cannot delete an unrelated SQLite file via
    ``_resolve_memory_db_path``'s overwrite branch.

    The check uses :meth:`Path.relative_to` after :meth:`Path.resolve` so it
    works uniformly across Linux (``/tmp`` is real) and macOS (``/tmp`` is a
    symlink to ``/private/tmp``).
    """
    resolved = path.resolve()
    tmp_root = Path("/tmp").resolve()  # noqa: S108 — sanctioned scratch root
    try:
        rel = resolved.relative_to(tmp_root)
    except ValueError:
        pass
    else:
        first = rel.parts[0] if rel.parts else ""
        if any(first.startswith(p) for p in _ALLOWED_MEMORY_DB_TMP_BASENAME_PREFIXES):
            return True
    try:
        resolved.relative_to((Path.cwd() / "var" / "eval").resolve())
    except ValueError:
        return False
    return True


def _resolve_memory_db_path(
    path: Path | None,
    *,
    persona: str,
    run_idx: int,
    overwrite: bool,
) -> Path:
    """Validate / default the natural-condition memory DB path (SH-4 ADR).

    Two branches with asymmetric semantics by design:

    * ``path is None`` → default ``/tmp/p3a_natural_<persona>_run<idx>.sqlite``.
      The default location is treated as scratch — pre-existing files are
      unlinked unconditionally to preserve back-compat with the pre-SH-4
      ME-2 behaviour. No ``--overwrite-memory-db`` flag required.
    * explicit ``path`` → symlinks are rejected, only paths under
      :data:`ALLOWED_MEMORY_DB_PREFIX_STRINGS` (or ``var/eval/``) are accepted,
      and a pre-existing file requires ``--overwrite-memory-db``. This stops
      a typo like ``--memory-db /etc/important.sqlite`` from quietly deleting
      an unrelated file the way the pre-SH-4 unconditional ``unlink`` did.

    Returns a ``Path`` guaranteed not to exist on disk when the caller opens
    it. Raises :class:`argparse.ArgumentTypeError` (validation) or
    :class:`FileExistsError` (overwrite gate) on policy violation.

    .. note::
        **TOCTOU disclosure** — there is a small race window between the
        ``os.path.lexists`` / ``is_symlink`` checks here and the caller's
        subsequent ``open()`` on the returned ``Path``. A privileged actor
        with write access to the parent directory could swap in a symlink
        in that window. The eval CLI runs on a single-user developer
        machine (``/tmp`` owned by the same UID, ``var/eval`` inside the
        repo) so the impact is negligible. Callers should ``open()`` the
        returned path immediately to keep the window short. A
        regression test would require multi-thread / multi-process timing
        primitives that the eval pipeline does not otherwise import; the
        docstring contract is the canonical reference instead.
    """
    if path is None:
        default = Path(
            f"/tmp/p3a_natural_{persona}_run{run_idx}.sqlite",  # noqa: S108
        )
        # Use ``os.path.lexists`` rather than ``Path.exists``: ``Path.exists``
        # follows symlinks and reports False for broken symlinks, so a stale
        # link to a missing target would pass through unnoticed and later
        # cause MemoryStore to open() through it.
        if os.path.lexists(default):
            if default.is_symlink():
                msg = (
                    f"symlink not allowed at default --memory-db location "
                    f"{default!s}; remove or replace the link before re-running"
                    " (SH-4)"
                )
                raise argparse.ArgumentTypeError(msg)
            default.unlink()
        return default

    if path.is_symlink():
        msg = (
            f"symlink not allowed for --memory-db: {path!s}; pass the resolved"
            " target directly so we never unlink through a symlink"
        )
        raise argparse.ArgumentTypeError(msg)
    if not _is_allowed_memory_db_prefix(path):
        allowed = ", ".join(ALLOWED_MEMORY_DB_PREFIX_STRINGS) + ", var/eval/"
        msg = (
            f"--memory-db must be under {allowed}: got {path!s}"
            " (SH-4: prevents accidental unlink of unrelated SQLite files)"
        )
        raise argparse.ArgumentTypeError(msg)
    # Use ``os.path.lexists`` for symmetry with the default branch and as
    # defence-in-depth: ``path.is_symlink()`` above already rejects symlinks,
    # so by here ``exists()`` and ``lexists()`` agree.
    if os.path.lexists(path):
        if not overwrite:
            msg = (
                f"--memory-db {path!s} already exists;"
                " pass --overwrite-memory-db to replace it"
            )
            raise FileExistsError(msg)
        path.unlink()
    return path


def _resolve_output_paths(
    output: Path,
    *,
    overwrite: bool,
    allow_partial_rescue: bool = False,
    force_rescue: bool = False,
) -> tuple[Path, Path]:
    """Return ``(temp_path, final_path)`` for the staged write protocol.

    Refuses to clobber a pre-existing final file unless ``--overwrite`` is
    explicit. The ``.tmp`` sibling is removed up-front so a stale temp from
    a previous failed run cannot poison this capture's CHECKPOINT, **but**
    only after the operator acknowledges what is being discarded:

    * stale ``.tmp`` with a *valid* sidecar (status=partial / fatal):
      requires ``--allow-partial-rescue``.
    * stale ``.tmp`` with a *corrupted* sidecar (Pydantic ValidationError
      or unreadable JSON): requires ``--force-rescue``; the
      sidecar represents an unknown state and ``--allow-partial-rescue``
      alone is too weak.
    * stale ``.tmp`` with no sidecar (legacy or pre-ME-9 capture): unlinks
      silently, matching the pre-ADR behaviour.
    """
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        msg = f"output {output!s} already exists; pass --overwrite to replace it"
        raise FileExistsError(msg)
    temp = output.with_suffix(output.suffix + ".tmp")
    if temp.exists():
        sidecar = sidecar_path_for(output)
        if sidecar.exists():
            try:
                payload = read_sidecar(sidecar)
            except Exception as exc:
                if not force_rescue:
                    msg = (
                        f"stale {temp!s} found with corrupted sidecar"
                        f" {sidecar!s} ({exc!r}); pass --force-rescue to"
                        " unlink, or recover the sidecar manually first"
                    )
                    raise FileExistsError(msg) from exc
                logger.warning(
                    "force-rescue: discarding %s + corrupted sidecar %s (%s)",
                    temp,
                    sidecar,
                    exc,
                )
            else:
                if not allow_partial_rescue:
                    msg = (
                        f"stale {temp!s} found with sidecar"
                        f" status={payload.status!r};"
                        " pass --allow-partial-rescue to unlink, or"
                        " rescue/audit the partial capture manually first"
                    )
                    raise FileExistsError(msg)
                logger.warning(
                    "allow-partial-rescue: discarding %s (sidecar status=%s)",
                    temp,
                    payload.status,
                )
            sidecar.unlink()
        temp.unlink()
    return temp, output


# ---------------------------------------------------------------------------
# Stimulus capture
# ---------------------------------------------------------------------------


async def _warm_up_ollama(client: OllamaChatClient, persona: PersonaSpec) -> None:
    """Best-effort warmup so the first capture turn is not the cold call.

    ``health_check()`` only hits ``/api/tags``; a 1-token
    chat call is what actually loads the model into VRAM. Failures are
    tolerated — the capture path retries on its own.
    """
    try:
        await client.health_check()
    except OllamaUnavailableError as exc:
        logger.warning("ollama health_check failed during warmup: %s", exc)
        return
    try:
        await client.chat(
            [
                ChatMessage(role="system", content="warmup"),
                ChatMessage(role="user", content="ok"),
            ],
            sampling=compose_sampling(persona.default_sampling, SamplingDelta()),
            options={"num_predict": 1, "stop": ["\n"]},
            think=False,
        )
    except OllamaUnavailableError as exc:
        logger.warning("ollama warmup chat failed (continuing): %s", exc)


async def capture_stimulus(  # noqa: C901, PLR0915 — composition glue mirrors bootstrap.py inherently long shape
    *,
    persona: str,
    run_idx: int,
    turn_count: int,
    cycle_count: int,
    temp_path: Path,
    inference_fn: Callable[..., str] | None,
    client: OllamaChatClient | None,
    personas_dir: Path = _PERSONAS_DIR_DEFAULT,
    seeds_path: Path | None = None,
) -> CaptureResult:
    """Capture one stimulus-condition cell into ``temp_path``.

    ``inference_fn`` and ``client`` are mutually exclusive: tests inject a
    stub ``inference_fn`` (no Ollama dependency) while the live CLI passes
    ``client`` and the function builds the Ollama-backed inference itself.

    Returns a :class:`CaptureResult` with row counts; the caller is
    responsible for the atomic rename + result publishing. Raises
    :class:`CaptureFatalError` if a DuckDB insert fails.
    """
    manifest = (
        load_seed_manifest() if seeds_path is None else load_seed_manifest(seeds_path)
    )
    assert_seed_manifest_consistent(manifest)
    seed_root = derive_seed(persona, run_idx, salt=manifest["salt"])

    persona_spec = _load_persona(personas_dir, persona)
    battery = load_stimulus_battery(persona)
    target_per_cycle = max(1, turn_count // max(1, cycle_count))
    sliced = _stratified_stimulus_slice(
        battery, target_focal_per_cycle=target_per_cycle
    )
    if not sliced:
        msg = (
            f"stratified slice produced 0 stimuli for persona={persona!r} "
            f"(target={target_per_cycle}, battery={len(battery)} stim)"
        )
        raise ValueError(msg)
    selected_ids = [str(s.get("stimulus_id")) for s in sliced]

    run_id = f"{persona}_stimulus_run{run_idx}"
    state = _SinkState()

    con = duckdb.connect(str(temp_path), read_only=False)
    bootstrap_schema(con)

    def _zone_resolver(speaker_id: str, dialog_id: str) -> str:
        # The driver opens dialogs in stimulus-declared zones; we mirror the
        # last-stamped zone via the sink-state cache so the per-row write
        # has a definite value even on multi-turn stimuli.
        del speaker_id
        return state.last_zone_by_speaker.get(dialog_id, "")

    def _stimulus_persona_resolver(agent_id: str) -> str | None:
        # The driver uses the persona_id literal as the focal speaker's
        # ``speaker_id`` and DEFAULT_INTERLOCUTOR_ID for the partner. Map
        # both back to the persona namespace so HIGH-2 focal counting
        # (``speaker_persona_id == persona``) is faithful even on
        # multi-turn stimuli where the partner speaks turn_index=1.
        if agent_id == persona:
            return persona
        if agent_id == DEFAULT_INTERLOCUTOR_ID:
            return DEFAULT_INTERLOCUTOR_ID
        return None

    sink = _make_duckdb_sink(
        con=con,
        run_id=run_id,
        focal_persona_id=persona,
        persona_resolver=_stimulus_persona_resolver,
        fallback_speaker_persona=persona,
        fallback_addressee_persona=DEFAULT_INTERLOCUTOR_ID,
        zone_resolver=_zone_resolver,
        state=state,
    )

    scheduler = InMemoryDialogScheduler(
        envelope_sink=lambda _e: None,
        turn_sink=sink,
        golden_baseline_mode=True,
    )

    if inference_fn is None:
        if client is None:
            msg = "capture_stimulus: provide either inference_fn or client"
            raise ValueError(msg)
        loop = asyncio.get_running_loop()
        inference_fn = _make_stimulus_inference_fn(
            client=client,
            persona_spec=persona_spec,
            sink_state=state,
            loop=loop,
        )
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=inference_fn,
        seed_root=seed_root,
        cycle_count=cycle_count,
    )

    # Warmup is a pre-condition only when we own the client.
    if client is not None:
        await _warm_up_ollama(client, persona_spec)

    # Populate the zone cache as the driver opens dialogs by hooking the
    # envelope sink. We receive a DialogInitiateMsg per open with its
    # ``zone``; feed it into ``state.last_zone_by_speaker`` keyed on
    # dialog_id (not speaker_id, because both pair members share it).
    initiate_log: dict[str, str] = {}

    def _envelope_sink(env: Any) -> None:
        zone = getattr(env, "zone", None)
        dialog_id = getattr(env, "dialog_id", None)
        if zone is not None and dialog_id is None:
            # DialogInitiateMsg carries zone but no dialog_id at this layer;
            # we resolve through scheduler.get_dialog_id below.
            initiator = getattr(env, "initiator_agent_id", None)
            target = getattr(env, "target_agent_id", None)
            if initiator and target:
                did = scheduler.get_dialog_id(initiator, target)
                if did is not None:
                    initiate_log[did] = str(zone)
        if zone is None and dialog_id is not None:
            # DialogCloseMsg — strip from cache (best-effort)
            initiate_log.pop(str(dialog_id), None)

    # Wire envelope sink in-place (scheduler's internal _sink is private).
    scheduler._sink = _envelope_sink  # noqa: SLF001 — local-only sink swap

    # Make the cache visible to the DuckDB sink before run_persona starts
    # firing. The driver calls schedule_initiate first, the envelope sink
    # populates initiate_log[dialog_id], then record_turn fires record_turn
    # which calls our DuckDB sink — at that point the lookup hits.
    state.last_zone_by_speaker = initiate_log  # alias

    # Drive the battery — synchronous loop since the driver itself is sync.
    # If the inference_fn raises CaptureFatalError (HIGH-3 propagation) it tears
    # down the run before any rename.
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None, lambda: driver.run_persona(persona, stimuli=sliced)
        )
    except CaptureFatalError:
        # Already recorded in state.fatal_error; fall through to closing.
        logger.exception("stimulus capture aborted by fatal sink error")

    write_with_checkpoint(con)

    return CaptureResult(
        run_id=run_id,
        output_path=temp_path,
        total_rows=state.total,
        focal_rows=state.focal,
        fatal_error=state.fatal_error,
        soft_timeout=state.soft_timeout,
        partial_capture=False,  # stimulus has no wall-timeout path
        stop_reason=_derive_stop_reason(state),
        drain_completed=True,  # stimulus has no async runtime drain
        runtime_drain_timeout=False,
        selected_stimulus_ids=selected_ids,
        seed=seed_root,
        seed_salt=str(manifest["salt"]),
    )


# ---------------------------------------------------------------------------
# Natural capture (full bootstrap stack, headless)
# ---------------------------------------------------------------------------


async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors bootstrap.py
    *,
    persona: str,
    run_idx: int,
    turn_count: int,
    temp_path: Path,
    ollama_host: str,
    chat_model: str,
    embed_model: str,
    memory_db_path: Path | None,
    wall_timeout_min: float,
    personas_dir: Path = _PERSONAS_DIR_DEFAULT,
    seeds_path: Path | None = None,
    runtime_factory: Callable[..., WorldRuntime] | None = None,
    overwrite_memory_db: bool = False,
    individual_layer: IndividualLayerConfig | None = None,
    same_base_count: int | None = None,
    population_world_size: int | None = None,
    runtime_drain_grace_s: float = _RUNTIME_DRAIN_GRACE_S,
) -> CaptureResult:
    """Capture one natural-condition cell using a headless WorldRuntime stack.

    ``runtime_factory`` exists so the unit test can inject a manually clocked
    WorldRuntime + stub DialogTurnGenerator without the live cognition stack.

    ``same_base_count`` (M11-C3b P-1) switches the registration roster: ``None``
    keeps the historical one-per-persona set (byte-identical), an int registers
    that many same-base individuals of ``persona`` (``a_<persona>_001 .. _NNN``)
    so the same-base individuation pilot can run; see :func:`build_natural_roster`.

    ``population_world_size`` (M10-A S4, PR-S4a) selects the population roster
    instead: 3 measured same-base individuals of ``persona`` + ``(N-3)``
    cross-base background agents (total ``N``); see
    :func:`build_population_roster`. It is **mutually exclusive** with
    ``same_base_count`` — passing both raises ``ValueError`` (the guard is here,
    not only in the CLI, because this is an internal API; DA-S4A-4).

    ``runtime_drain_grace_s`` (M10-A S4 GPU exec) is the wait for the runtime task
    to drain its final in-flight tick after :meth:`WorldRuntime.stop`; exceeding it
    is a fatal drain timeout. It defaults to :data:`_RUNTIME_DRAIN_GRACE_S` (60 s,
    byte-identical for every existing caller / the 3-agent same-base launcher). A
    population run registers up to N=31 agents whose single cognition tick can take
    longer than 60 s, so the S4 launcher passes a larger grace; only that caller
    changes behaviour.

    ``individual_layer`` is the M11-C2 substrate seam (DA-M11C2-9): ``None``
    (default) leaves the flag-off path byte-identical; an enabled config bootstraps
    ``metrics.individual_state_trace``, wires the trace sink into the default
    WorldRuntime, **and** (M10-A E1, DA-S1) chains the belief-promotion relational
    sink onto the dialog turn sink so the evaluation epoch promotes beliefs — the
    substrate ``belief_variance`` reads. The flag-off path keeps a single
    ``duckdb_sink`` turn sink and never bootstraps the trace table, so the DuckDB
    stays byte-identical (DB byte-invariance is asserted for flag-off only).
    """
    if same_base_count is not None and population_world_size is not None:
        msg = (
            "capture_natural: same_base_count and population_world_size are"
            " mutually exclusive (legacy/C3b same-base launcher vs S4 population"
            " launcher); pass at most one"
        )
        raise ValueError(msg)

    manifest = (
        load_seed_manifest() if seeds_path is None else load_seed_manifest(seeds_path)
    )
    assert_seed_manifest_consistent(manifest)
    seed_root = derive_seed(persona, run_idx, salt=manifest["salt"])

    persona_specs: dict[str, PersonaSpec] = {
        pid: _load_persona(personas_dir, pid) for pid in DEFAULT_PERSONAS
    }
    if persona not in persona_specs:
        msg = (
            f"persona={persona!r} is not part of the natural-condition agent "
            f"set ({DEFAULT_PERSONAS})"
        )
        raise ValueError(msg)

    # Build (and thereby validate) the population roster *before* any DB / memory
    # / Ollama setup so an invalid --population-world-size fails fast with the
    # real input error instead of a downstream resource fatal (Codex LOW).
    population_roster = (
        build_population_roster(persona, world_size=population_world_size)
        if population_world_size is not None
        else None
    )

    run_id = f"{persona}_natural_run{run_idx}"
    state = _SinkState()
    enough_event = asyncio.Event()

    con = duckdb.connect(str(temp_path), read_only=False)
    bootstrap_schema(con)
    # M11-C2 (DA-M11C2-1/9): flag-on conditional trace table. Created only when
    # the individual layer is enabled — never inside ``bootstrap_schema`` — so a
    # flag-off run never issues this DDL and the DuckDB stays byte-identical
    # (DB byte-invariance is asserted for flag-off only).
    individual_layer_on = individual_layer is not None and individual_layer.enabled
    if individual_layer_on:
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        # Saturation probe (ADR section 5): flag-on conditional trace table, created
        # in the same individual-layer-enabled branch so a flag-off run never issues
        # this DDL and the DuckDB stays byte-identical (new-module shadow; the frozen
        # individual_state_trace path above is untouched).
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        # Engagement instrument (ADR §5): flag-on conditional trace table, created in
        # the same individual-layer-enabled branch so a flag-off run never issues this
        # DDL and the DuckDB stays byte-identical (new-module shadow).
        bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
        # U5 replay infra: flag-on conditional reconcile-input floor trace table,
        # created in the same individual-layer-enabled branch so a flag-off run never
        # issues this DDL and the DuckDB stays byte-identical (new-module shadow).
        bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)

    # SH-4: validate (symlink/prefix/overwrite) for explicit paths, fall back to
    # ME-2 default ``/tmp/p3a_natural_<persona>_run<idx>.sqlite`` when None.
    # The default path is treated as scratch and auto-unlinked; user-supplied
    # paths require ``--overwrite-memory-db`` to replace an existing file.
    memory_db_path = _resolve_memory_db_path(
        memory_db_path,
        persona=persona,
        run_idx=run_idx,
        overwrite=overwrite_memory_db,
    )

    memory = MemoryStore(db_path=str(memory_db_path))
    memory.create_schema()

    embedding = EmbeddingClient(model=embed_model, endpoint=ollama_host)
    inference = OllamaChatClient(model=chat_model, endpoint=ollama_host)

    try:
        await inference.health_check()
    except OllamaUnavailableError as exc:
        logger.exception("ollama health check failed for natural capture")
        state.set_fatal(f"ollama unreachable: {exc!r}")
        return CaptureResult(
            run_id=run_id,
            output_path=temp_path,
            total_rows=0,
            focal_rows=0,
            fatal_error=state.fatal_error,
            stop_reason="fatal_ollama",
            drain_completed=state.drain_completed,
            runtime_drain_timeout=state.runtime_drain_timeout,
            seed=seed_root,
            seed_salt=str(manifest["salt"]),
        )

    retriever = Retriever(memory, embedding)

    # M11-C2: wire the flag-on trace sink (run_id bound here, so WorldRuntime
    # never learns it; DA-M11C2-4). ``None`` flag-off keeps _consume_result's
    # snapshot path inert (flag-off byte-invariant). Built before the runtime so
    # both the default and ``runtime_factory`` branches receive it symmetrically
    # (the factory seam must be able to verify full wiring).
    trace_sink = (
        _make_individual_trace_sink(con=con, run_id=run_id, state=state)
        if individual_layer_on
        else None
    )
    # Saturation probe (ADR section 5): flag-on per-channel sink. ``seed`` is the
    # ``derive_seed`` uint64 already computed for this run (UBIGINT column;
    # DA-IMPL-2) so the N=3 paired seeds partition cleanly in the loader.
    # ``individual_layer_enabled`` is bound true here (the only path that writes it).
    saturation_trace_sink = (
        _make_saturation_trace_sink(
            con=con,
            run_id=run_id,
            seed=seed_root,
            individual_layer_enabled=individual_layer_on,
            state=state,
        )
        if individual_layer_on
        else None
    )
    # Engagement instrument (ADR §5): flag-on per-(agent, tick) hint-disposition sink.
    # ``seed`` / ``individual_layer_enabled`` bound here for the same provenance reason
    # as the saturation sink; ``None`` flag-off keeps the trace table absent.
    hint_engagement_trace_sink = (
        _make_hint_engagement_trace_sink(
            con=con,
            run_id=run_id,
            seed=seed_root,
            individual_layer_enabled=individual_layer_on,
            state=state,
        )
        if individual_layer_on
        else None
    )
    # U5 replay infra: flag-on per-(agent, tick) reconcile-input floor sink. Reads the
    # same snapshot as the saturation sink but persists the full ``base_floor`` so a
    # deterministic replay can re-feed it into the unchanged reconcile kernel; ``seed``
    # / ``individual_layer_enabled`` bound here for the same provenance reason as the
    # saturation sink; ``None`` flag-off keeps the trace table absent.
    floor_input_trace_sink = (
        _make_floor_input_trace_sink(
            con=con,
            run_id=run_id,
            seed=seed_root,
            individual_layer_enabled=individual_layer_on,
            state=state,
        )
        if individual_layer_on
        else None
    )

    # Build the WorldRuntime + cognition stack.  ``runtime_factory`` is the
    # injection seam used by the unit test to swap in a ManualClock-driven
    # WorldRuntime + stub DialogTurnGenerator.  Production path uses the
    # default factory below.
    if runtime_factory is None:

        def _resolve_persona_display_name(agent_id: str) -> str | None:
            pid = runtime.agent_persona_id(agent_id)
            if pid is None:
                return None
            spec = persona_specs.get(pid)
            return spec.display_name if spec is not None else None

        reflector = Reflector(
            store=memory,
            embedding=embedding,
            llm=inference,
            persona_resolver=_resolve_persona_display_name,
        )
        cycle = CognitionCycle(
            retriever=retriever,
            store=memory,
            embedding=embedding,
            llm=inference,
            erre_policy=DefaultERREModePolicy(),
            bias_sink=lambda _e: None,
            reflector=reflector,
            individual_layer=individual_layer,
        )
        runtime = WorldRuntime(
            cycle=cycle,
            individual_trace_sink=trace_sink,
            saturation_trace_sink=saturation_trace_sink,
            hint_engagement_trace_sink=hint_engagement_trace_sink,
            floor_input_trace_sink=floor_input_trace_sink,
        )
    else:
        runtime = runtime_factory(
            memory=memory,
            embedding=embedding,
            inference=inference,
            retriever=retriever,
            persona_specs=persona_specs,
            individual_layer=individual_layer,
            individual_trace_sink=trace_sink,
            saturation_trace_sink=saturation_trace_sink,
            hint_engagement_trace_sink=hint_engagement_trace_sink,
            floor_input_trace_sink=floor_input_trace_sink,
        )

    def _persona_resolver(agent_id: str) -> str | None:
        return runtime.agent_persona_id(agent_id)

    def _zone_resolver(speaker_id: str, _dialog_id: str) -> str:
        zone = runtime.get_agent_zone(speaker_id)
        return zone.value if zone is not None else ""

    duckdb_sink = _make_duckdb_sink(
        con=con,
        run_id=run_id,
        focal_persona_id=persona,
        persona_resolver=_persona_resolver,
        fallback_speaker_persona=persona,
        fallback_addressee_persona="?",
        zone_resolver=_zone_resolver,
        state=state,
        enough_event=enough_event,
        focal_budget=turn_count,
        # PR-Z (20260529): propagate the bool flag from line 1317 so the
        # raw_dialog row records the truthful flag-on state. capture_stimulus
        # intentionally omits this kwarg and relies on the default ``False``
        # — stimulus has no individual-layer semantic (DA-PR-Z-3).
        individual_layer_enabled=individual_layer_on,
    )

    # M10-A E1 (DA-S1, Codex C3/C4b): flag-on **only**, chain the belief-promotion
    # relational sink after the raw_dialog write so the evaluation epoch actually
    # promotes beliefs (per-turn affinity delta + maybe_promote_belief upsert) —
    # the substrate ``belief_variance`` reads via ``list_semantic_beliefs``. A
    # flag-off run keeps ``turn_sink=duckdb_sink`` alone so the raw_dialog byte
    # stream is unchanged (affinity dynamics can shift dialog generation, so this
    # must never run flag-off). Mirrors bootstrap.py ``_chained_turn_sink``;
    # ``_make_relational_sink`` is reused from the bootstrap composition root
    # (private import accepted for S1, Codex C4). Belief substrate lands in the
    # sqlite memory store and is read at the next cognition tick's trace emit, so
    # the final-tick trace reflects the run's promoted beliefs (C4b ordering).
    turn_sink: Callable[[DialogTurnMsg], None] = duckdb_sink
    if individual_layer_on:
        relational_sink = _make_relational_sink(
            runtime=runtime,
            memory=memory,
            persona_registry=persona_specs,
        )

        def _chained_turn_sink(turn: DialogTurnMsg) -> None:
            duckdb_sink(turn)
            relational_sink(turn)

        turn_sink = _chained_turn_sink

    scheduler_rng = random.Random(seed_root)  # noqa: S311 — non-crypto, eval seed
    scheduler = InMemoryDialogScheduler(
        envelope_sink=runtime.inject_envelope,
        rng=scheduler_rng,
        turn_sink=turn_sink,
        golden_baseline_mode=False,
        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
        # sustain dialog after LLM destination_zone scatters them out of
        # AGORA.
        eval_natural_mode=True,
    )
    runtime.attach_dialog_scheduler(scheduler)

    dialog_generator = OllamaDialogTurnGenerator(llm=inference, personas=persona_specs)
    runtime.attach_dialog_generator(dialog_generator)

    # Register the roster so proximity auto-fire has every pair available.
    # _iter_colocated_pairs only checks zone equality,
    # so distinct seats inside AGORA are sufficient. The default roster is the
    # three personas (byte-identical to before); the M11-C3b same-base roster is
    # N individuals of the focal persona (DA-M11C3b-P1-3).
    if population_roster is not None:
        _register_population_roster(runtime, population_roster, persona_specs)
    else:
        roster = build_natural_roster(persona, same_base_count=same_base_count)
        _register_natural_roster(
            runtime, roster, persona_specs, same_base=same_base_count is not None
        )

    # Warmup — same fail-soft logic as stimulus.
    await _warm_up_ollama(inference, persona_specs[persona])

    # Drive: spawn runtime task + watchdog.  The watchdog returns once the
    # focal budget is reached, the wall hard cap is hit, or the runtime
    # task itself completes (e.g. fatal error inside the cycle).
    runtime_phase_start = time.monotonic()
    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
    wall_deadline = runtime_phase_start + wall_timeout_min * 60.0

    async def _watchdog() -> None:
        while True:
            if state.fatal_error is not None:
                logger.error(
                    "natural capture aborting on fatal sink error: %s",
                    state.fatal_error,
                )
                return
            if enough_event.is_set():
                logger.info("natural capture focal budget %d reached", turn_count)
                return
            if runtime_task.done():
                logger.info("runtime task exited before focal budget")
                return
            if time.monotonic() >= wall_deadline:
                # wall budget = soft timeout,
                # not fatal. The capture publishes as ``status=partial`` while
                # the audit gate keeps it out of complete-runs aggregation.
                msg = f"wall timeout ({wall_timeout_min} min) exceeded"
                state.set_soft_timeout(msg)
                logger.warning(msg)
                return
            await asyncio.sleep(0.5)

    try:
        await _watchdog()
    finally:
        # M11-C3b §5.3: the runtime phase ends when the watchdog returns (focal
        # budget reached / wall cap / fatal), measured just before stop() so the
        # throughput denominator is the observed elapsed, not the soft cap.
        runtime_phase_end = time.monotonic()
        runtime.stop()
        try:
            await asyncio.wait_for(runtime_task, timeout=runtime_drain_grace_s)
        except TimeoutError:
            # drain incomplete = fatal regardless of
            # wall budget — checkpoint/close cannot be guaranteed, so silent
            # publish of a torn DuckDB file is unsafe.
            state.drain_completed = False
            state.runtime_drain_timeout = True
            state.set_fatal(f"runtime drain exceeded {runtime_drain_grace_s}s")
            runtime_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await runtime_task
        except Exception as exc:  # noqa: BLE001 — capture unhandled
            # an exception inside ``runtime.run()`` was
            # previously re-raised by ``wait_for`` and dropped on the floor,
            # so the capture appeared complete with no sidecar trail.
            state.drain_completed = False
            state.set_fatal(f"runtime_task raised: {exc!r}")

    write_with_checkpoint(con)

    # Close the rest of the stack so /tmp sqlite handles flush before the
    # caller renames the DuckDB file out of .tmp.
    await inference.close()
    await embedding.close()
    await memory.close()

    return CaptureResult(
        run_id=run_id,
        output_path=temp_path,
        total_rows=state.total,
        focal_rows=state.focal,
        fatal_error=state.fatal_error,
        soft_timeout=state.soft_timeout,
        partial_capture=(state.fatal_error is None and state.soft_timeout is not None),
        stop_reason=_derive_stop_reason(state),
        drain_completed=state.drain_completed,
        runtime_drain_timeout=state.runtime_drain_timeout,
        elapsed_seconds=runtime_phase_end - runtime_phase_start,
        seed=seed_root,
        seed_salt=str(manifest["salt"]),
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-eval-run-golden",
        description=(
            "Capture one (persona, condition, run_idx) cell into a fresh "
            "DuckDB file under raw_dialog schema for m9-eval P3a."
        ),
    )
    parser.add_argument(
        "--persona",
        choices=list(DEFAULT_PERSONAS),
        required=True,
        help="Focal persona id (kant / nietzsche / rikyu).",
    )
    parser.add_argument(
        "--run-idx",
        type=int,
        required=True,
        help="Seed manifest run index (0..4 per design).",
    )
    parser.add_argument(
        "--condition",
        choices=("stimulus", "natural"),
        required=True,
        help="Capture condition.",
    )
    parser.add_argument(
        "--turn-count",
        type=int,
        default=_DEFAULT_TURN_COUNT,
        help=(
            "Focal-speaker turn budget for the cell (default %(default)d). "
            "Stimulus condition slices the battery to fit; natural condition "
            "stops the runtime once the budget is reached."
        ),
    )
    parser.add_argument(
        "--cycle-count",
        type=int,
        default=_DEFAULT_CYCLE_COUNT,
        help="Stimulus cycle count (default %(default)d).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="DuckDB output path; capture writes to <output>.tmp first.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing --output file (default: refuse).",
    )
    parser.add_argument(
        "--allow-partial-rescue",
        action="store_true",
        help=(
            "Permit unlinking a stale <output>.tmp whose sidecar reports a"
            " known partial / fatal status (default: refuse — protects"
            " against silent loss of an in-progress rescue)."
        ),
    )
    parser.add_argument(
        "--force-rescue",
        action="store_true",
        help=(
            "Permit unlinking a stale <output>.tmp whose sidecar is"
            " corrupted or unreadable (default: refuse). Strictly stronger"
            " than --allow-partial-rescue; reserved for unknown-state"
            " recovery."
        ),
    )
    parser.add_argument(
        "--overwrite-memory-db",
        action="store_true",
        help=(
            "Permit replacing an existing user-supplied --memory-db sqlite"
            " file (default: refuse). The implicit default"
            " /tmp/p3a_natural_<persona>_run<idx>.sqlite is treated as"
            " scratch and does NOT require this flag (SH-4 ADR)."
        ),
    )
    parser.add_argument(
        "--ollama-host",
        default="http://127.0.0.1:11434",
        help="Ollama HTTP endpoint (default %(default)s).",
    )
    parser.add_argument(
        "--model",
        default="qwen3:8b",
        help="Chat model tag (default %(default)s).",
    )
    parser.add_argument(
        "--embed-model",
        default="nomic-embed-text",
        help="Embedding model tag (natural condition only).",
    )
    parser.add_argument(
        "--memory-db",
        type=Path,
        default=None,
        help=(
            "sqlite path for the natural-condition cognition stack "
            "(default: /tmp/p3a_natural_<persona>_run<idx>.sqlite)."
        ),
    )
    parser.add_argument(
        "--wall-timeout-min",
        type=float,
        default=_DEFAULT_WALL_TIMEOUT_MIN,
        help=(
            "Hard wall-clock cap for natural condition in minutes "
            "(default %(default).0f)."
        ),
    )
    parser.add_argument(
        "--personas-dir",
        type=Path,
        default=_PERSONAS_DIR_DEFAULT,
        help="personas/ directory (default %(default)s).",
    )
    parser.add_argument(
        "--compute-individuation",
        action="store_true",
        default=False,
        help=(
            "After a COMPLETE capture, compute M10-0 individuation metrics into"
            " a <output>.individuation.json sidecar. Runs as a read-only second"
            " pass against the published file, so the .duckdb stays"
            " byte-for-byte unchanged; default off (no analysis view opened)."
        ),
    )
    # M10-A S4 (DA-S4A-4): the two scaled-roster launchers are mutually
    # exclusive — argparse rejects passing both, mirroring the function-level
    # guard in capture_natural (so neither the CLI nor an internal direct call
    # can request a same-base and a population roster at once).
    roster_group = parser.add_mutually_exclusive_group()
    roster_group.add_argument(
        "--same-base-count",
        type=int,
        default=None,
        help=(
            "M11-C3b same-base launcher: register this many individuals of"
            " --persona (a_<persona>_001 .. _NNN) into one natural run instead"
            " of the default one-per-persona set. Natural condition only;"
            " default off (byte-identical legacy roster). Mutually exclusive"
            " with --population-world-size."
        ),
    )
    roster_group.add_argument(
        "--population-world-size",
        type=int,
        default=None,
        help=(
            "M10-A S4 population launcher: register 3 measured same-base"
            " individuals of --persona plus (N-3) cross-base background agents"
            " (total N, max 31) into one natural run. Mutually exclusive with"
            " --same-base-count. Natural condition only; default off."
        ),
    )
    parser.add_argument(
        "--individual-layer",
        choices=("on", "off"),
        default="off",
        help=(
            "Toggle the M11-C2 individual layer for the natural run (flag-on"
            " bootstraps the individual_state_trace table + SWM injection)."
            " Natural condition only; default off (byte-invariant)."
        ),
    )
    parser.add_argument(
        "--stm-carry-arm",
        choices=("on", "off"),
        default="off",
        help=(
            "Fork III-a STM carry arm for the natural run. ON carries a bounded"
            " LLM offset across a floor-fingerprint change for a bounded horizon"
            " (reconcile_world_model(stm_carry=...)); OFF is the frozen"
            " drop-on-churn control. ON REQUIRES --individual-layer on and the"
            " natural condition (a contradictory combination fails fast). Natural"
            " condition only; default off (byte-invariant)."
        ),
    )
    parser.add_argument(
        "--replicate-id",
        type=int,
        choices=(0, 1),
        default=None,
        help=(
            "Fork III-a live §5.3 capture-matrix replicate index (0 or 1). The"
            " matrix is seed x arm{ON,OFF} x replicate{0,1} = 12 runs: the same"
            " seed is run twice per arm so the cross-arm scorer can measure the"
            " run-to-run noise floor (OFF r0 vs OFF r1) and the ON/ON sanity null."
            " REQUIRES --condition natural + --individual-layer on (the arm may be"
            " on or off — both are valid matrix members; a contradictory combination"
            " fails fast). Default unset (no matrix provenance; backward-compatible"
            " with U4 arm captures)."
        ),
    )
    parser.add_argument(
        "--runtime-drain-grace-s",
        type=float,
        default=_RUNTIME_DRAIN_GRACE_S,
        help=(
            "Seconds to wait for the runtime to drain its final in-flight tick"
            " after stop before declaring a fatal drain timeout (natural"
            " condition; default %(default).0f). A population run (up to N=31"
            " agents) needs a larger grace than the 3-agent default because a"
            " single cognition tick can exceed it."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
        help="Root logger level.",
    )
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    temp_path, final_path = _resolve_output_paths(
        args.output,
        overwrite=args.overwrite,
        allow_partial_rescue=args.allow_partial_rescue,
        force_rescue=args.force_rescue,
    )
    logger.info(
        "capture begin persona=%s condition=%s run_idx=%d turn_count=%d "
        "temp=%s final=%s",
        args.persona,
        args.condition,
        args.run_idx,
        args.turn_count,
        temp_path,
        final_path,
    )

    if args.condition == "stimulus":
        async with OllamaChatClient(
            model=args.model, endpoint=args.ollama_host
        ) as client:
            result = await capture_stimulus(
                persona=args.persona,
                run_idx=args.run_idx,
                turn_count=args.turn_count,
                cycle_count=args.cycle_count,
                temp_path=temp_path,
                inference_fn=None,
                client=client,
                personas_dir=args.personas_dir,
            )
    else:
        # M11-C3b P-1: --individual-layer on bootstraps the C2 trace table + SWM
        # injection; default off keeps individual_layer=None (byte-invariant).
        individual_layer: IndividualLayerConfig | None = None
        if getattr(args, "individual_layer", "off") == "on":
            from erre_sandbox.contracts.cognition_layers import (  # noqa: PLC0415
                IndividualLayerConfig as _IndividualLayerConfig,
            )

            # Fork III-a STM carry arm: ON gates reconcile_world_model(stm_carry=...)
            # only when the individual layer is live. main()._validate_stm_carry_arm
            # already rejected --stm-carry-arm on without --individual-layer on, so a
            # True here always has its substrate. Default off keeps the legacy
            # frozen drop-on-churn behaviour (byte-invariant).
            individual_layer = _IndividualLayerConfig(
                enabled=True,
                stm_carry_enabled=(getattr(args, "stm_carry_arm", "off") == "on"),
            )
        result = await capture_natural(
            persona=args.persona,
            run_idx=args.run_idx,
            turn_count=args.turn_count,
            temp_path=temp_path,
            ollama_host=args.ollama_host,
            chat_model=args.model,
            embed_model=args.embed_model,
            memory_db_path=args.memory_db,
            wall_timeout_min=args.wall_timeout_min,
            personas_dir=args.personas_dir,
            overwrite_memory_db=args.overwrite_memory_db,
            individual_layer=individual_layer,
            same_base_count=getattr(args, "same_base_count", None),
            population_world_size=getattr(args, "population_world_size", None),
            runtime_drain_grace_s=getattr(
                args, "runtime_drain_grace_s", _RUNTIME_DRAIN_GRACE_S
            ),
        )

    return _publish_capture(args, result, temp_path, final_path)


def _publish_capture(
    args: argparse.Namespace,
    result: CaptureResult,
    temp_path: Path,
    final_path: Path,
) -> int:
    """Pick status / stop_reason, write sidecar, and atomically publish.

    The 3-way split (complete / partial / fatal) is encoded as a Python
    ``match`` so :func:`typing.assert_never` flags any future
    ``CaptureStatus`` Literal addition that misses a branch.
    """
    status, stop_reason = _resolve_publish_outcome(result, args.turn_count)
    sidecar_path = sidecar_path_for(final_path)
    payload = SidecarV1(
        status=status,
        stop_reason=stop_reason,
        focal_target=int(args.turn_count),
        focal_observed=int(result.focal_rows),
        total_rows=int(result.total_rows),
        wall_timeout_min=float(args.wall_timeout_min),
        drain_completed=result.drain_completed,
        runtime_drain_timeout=result.runtime_drain_timeout,
        git_sha=_git_sha_short(),
        captured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        persona=str(args.persona),
        # argparse ``choices=("stimulus", "natural")`` narrows this at
        # runtime; the cast tells the static checker the same thing.
        condition=cast("Literal['stimulus', 'natural']", args.condition),
        run_idx=int(args.run_idx),
        duckdb_path=str(final_path),
        elapsed_seconds=result.elapsed_seconds,
        # U4 fork III-a paired-arm provenance: record the arm only for an
        # arm-bearing capture (natural + --individual-layer on); the seed/salt
        # are recorded for every capture so the manifest builder can pair ON/OFF
        # on the actual seed (which depends on the seed-manifest salt, not on
        # run_idx alone).
        stm_carry_arm=(
            cast("Literal['on', 'off']", args.stm_carry_arm)
            if (
                args.condition == "natural"
                and getattr(args, "individual_layer", "off") == "on"
            )
            else None
        ),
        seed=result.seed,
        seed_salt=result.seed_salt,
        # Fork III-a live §5.3 12-run capture-matrix replicate index. Recorded only
        # for an arm-bearing capture (natural + --individual-layer on), the same gate
        # as ``stm_carry_arm``; ``_validate_replicate_id`` already rejected
        # --replicate-id outside the full arm combination, so ``args.replicate_id`` is
        # None here unless the arm is live.
        replicate_id=(
            getattr(args, "replicate_id", None)
            if (
                args.condition == "natural"
                and getattr(args, "individual_layer", "off") == "on"
            )
            else None
        ),
    )
    write_sidecar_atomic(sidecar_path, payload)

    typed_status: CaptureStatus = status
    match typed_status:
        case "complete":
            atomic_temp_rename(temp_path, final_path)
            # Byte-invariance seam (DA-M10I-14): the individuation pass runs
            # ONLY here, after the file is published, as a read-only second
            # pass writing a sidecar — it never touches the .duckdb bytes.
            # getattr guards callers (tests) whose Namespace predates the flag.
            if getattr(args, "compute_individuation", False):
                _run_individuation_sidecar(args, final_path)
            logger.info(
                "capture OK persona=%s condition=%s run_idx=%d"
                " total=%d focal=%d sidecar=%s output=%s",
                args.persona,
                args.condition,
                args.run_idx,
                result.total_rows,
                result.focal_rows,
                sidecar_path,
                final_path,
            )
            return 0
        case "partial":
            atomic_temp_rename(temp_path, final_path)
            logger.warning(
                "capture PARTIAL (%s) persona=%s condition=%s run_idx=%d"
                " total=%d focal=%d/%d sidecar=%s output=%s",
                stop_reason,
                args.persona,
                args.condition,
                args.run_idx,
                result.total_rows,
                result.focal_rows,
                args.turn_count,
                sidecar_path,
                final_path,
            )
            return 3
        case "fatal":
            logger.error(
                "capture FAILED (%s) persona=%s condition=%s run_idx=%d"
                " total=%d focal=%d reason=%s sidecar=%s",
                stop_reason,
                args.persona,
                args.condition,
                args.run_idx,
                result.total_rows,
                result.focal_rows,
                result.fatal_error,
                sidecar_path,
            )
            # Leave temp_path on disk for inspection; refuse atomic rename.
            return 2
        case _:  # pragma: no cover — Literal exhaustiveness guard
            assert_never(typed_status)


def _run_individuation_sidecar(args: argparse.Namespace, final_path: Path) -> None:
    """Read-only individuation second pass → JSON sidecar (capture untouched).

    Runs only when ``--compute-individuation`` is set and a capture completed.
    Heavy imports (analysis view, sentence-transformers via the default
    embedding provider) are deferred to this function so a flag-off run keeps
    them out of the import graph (DA-M10I-14). A failure is logged and recorded
    in an *error* sidecar but never downgrades the already-published capture's
    return code — the publish succeeded; the metrics pass is additive
    best-effort.
    """
    from erre_sandbox.evidence.individuation.report import (  # noqa: PLC0415
        individuation_sidecar_path_for,
        write_individuation_error_sidecar,
    )

    run_id = f"{args.persona}_{args.condition}_run{args.run_idx}"
    sidecar_path = individuation_sidecar_path_for(final_path)
    try:
        from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415
            connect_analysis_view,
        )
        from erre_sandbox.evidence.individuation.layer1 import (  # noqa: PLC0415
            default_embedding_provider,
        )
        from erre_sandbox.evidence.individuation.report import (  # noqa: PLC0415
            build_report,
            write_individuation_sidecar_atomic,
        )
        from erre_sandbox.evidence.individuation.runner import (  # noqa: PLC0415
            IndividuationContext,
            compute_individuation,
        )

        ctx = IndividuationContext(
            personas_dir=args.personas_dir,
            provider=default_embedding_provider(),
            computed_at=datetime.now(UTC),
        )
        view = connect_analysis_view(final_path)
        try:
            results = compute_individuation(view, run_id=run_id, ctx=ctx)
        finally:
            view.close()
        report = build_report(run_id, results, computed_at=datetime.now(UTC))
        write_individuation_sidecar_atomic(sidecar_path, report)
        logger.info(
            "individuation sidecar written run_id=%s rows=%d sidecar=%s",
            run_id,
            len(results),
            sidecar_path,
        )
    except Exception as exc:
        logger.exception(
            "individuation pass failed run_id=%s (capture already published)",
            run_id,
        )
        try:
            write_individuation_error_sidecar(
                sidecar_path,
                run_id=run_id,
                error_type=type(exc).__name__,
                error_summary=str(exc)[:500],
                computed_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception(
                "failed to write individuation error sidecar run_id=%s", run_id
            )


def _resolve_publish_outcome(
    result: CaptureResult,
    focal_target: int,
) -> tuple[CaptureStatus, StopReason]:
    """Decide ``(status, stop_reason)`` from a returned :class:`CaptureResult`.

    Encodes the failure case: a complete branch with focal_rows below
    target is escalated to ``fatal_incomplete_before_target`` so the
    runtime-task path cannot publish a silent under-budget run.
    """
    if result.fatal_error is not None:
        return "fatal", result.stop_reason
    if result.soft_timeout is not None:
        return "partial", "wall_timeout"
    if result.focal_rows < focal_target:
        return "fatal", "fatal_incomplete_before_target"
    return "complete", "complete"


def _git_sha_short() -> str:
    """Return the current short git SHA, or ``"unknown"`` if unavailable.

    Same-process invocation keeps the sidecar runtime independent of any
    external env var (CI / launch wrapper). Failures (no repo, missing
    git binary) degrade to ``"unknown"`` rather than blocking publish.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def _validate_stm_carry_arm(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Fail-fast: ``--stm-carry-arm on`` requires natural + ``--individual-layer on``.

    The STM carry arm only has a substrate when the individual layer is live
    (it gates ``reconcile_world_model(stm_carry=...)`` via
    ``IndividualLayerConfig.stm_carry_enabled``), and the stimulus condition has
    no individual-layer semantic. A contradictory combination is rejected with
    ``parser.error`` (argparse exit code 2) before any capture begins, so an
    operator never produces a capture whose arm tag the runtime silently ignored.
    """
    if args.stm_carry_arm == "on":
        if args.condition != "natural":
            parser.error(
                "--stm-carry-arm on requires --condition natural (the stimulus"
                " condition has no individual-layer / STM-carry semantic)"
            )
        if args.individual_layer != "on":
            parser.error(
                "--stm-carry-arm on requires --individual-layer on (the STM carry"
                " arm gates reconcile_world_model via the individual layer; ON"
                " without the layer would be silently dropped)"
            )


def _validate_replicate_id(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Fail-fast: ``--replicate-id`` requires the full live-§5.3 arm combination.

    The 12-run capture matrix (``seed x arm{ON,OFF} x replicate{0,1}``, freeze ADR
    §0/§3) only exists for an arm-bearing natural run, so a replicate index is
    meaningless without ``--condition natural`` + ``--individual-layer on``. Both
    arm values are valid matrix members (the OFF replicates supply the run-to-run
    noise floor), so ``--stm-carry-arm`` is **not** additionally constrained here. A
    contradictory combination is rejected with ``parser.error`` (argparse exit code
    2) before any capture begins, so an operator never produces a sidecar whose
    ``replicate_id`` the runtime would have silently dropped. ``--replicate-id`` unset
    is allowed (backward-compatible U4 arm captures); the cross-arm scorer — not this
    CLI — enforces matrix completeness (missing / duplicate / role-swapped key =
    INVALID_MEASUREMENT, ADR §0/§3/§7).
    """
    if args.replicate_id is not None:
        if args.condition != "natural":
            parser.error(
                "--replicate-id requires --condition natural (the stimulus"
                " condition has no individual-layer / STM-carry matrix)"
            )
        if args.individual_layer != "on":
            parser.error(
                "--replicate-id requires --individual-layer on (the live §5.3"
                " capture matrix only exists when the individual layer is live)"
            )


def main(argv: list[str] | None = None) -> int:
    """Console entry — used by both the live CLI and the smoke tests."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    _validate_stm_carry_arm(parser, args)
    _validate_replicate_id(parser, args)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.warning("capture interrupted by user")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "CaptureFatalError",
    "CaptureResult",
    "capture_natural",
    "capture_stimulus",
    "main",
]
