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

Codex `gpt-5.5 xhigh` review (`.steering/20260430-m9-eval-system/codex-review-step1.md`)
is reflected end-to-end:

* HIGH-1 — :func:`_stratified_stimulus_slice` keeps proportional category
  representation instead of YAML-prefix slicing.
* HIGH-2 — focal speaker turn budget for both conditions (driver alternates
  speakers on multi-turn stimuli).
* HIGH-3 — DuckDB sink is **fail-fast**; an INSERT error sets the run
  ``fatal_error`` flag and aborts before any atomic rename.
* HIGH-4 — capture writes to ``<output>.tmp``; pre-existing ``<output>``
  refuses unless ``--overwrite`` is passed; final ``atomic_temp_rename``
  is the only path that publishes the result file.
* HIGH-5 — natural-condition scheduler RNG is seeded with
  :func:`derive_seed` so admission auto-fire is reproducible per ``run_idx``.
* HIGH-6 — ``runtime.stop()`` is followed by
  ``asyncio.wait_for(runtime_task, grace_s)``; on timeout the run is
  abandoned (no rename) so partial captures cannot masquerade as complete.

The ``mode`` raw column is **left empty** (Codex MEDIUM-2): the column is
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

from erre_sandbox.cognition import CognitionCycle, Reflector
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
    from collections.abc import Callable
    from typing import Literal

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

m9-eval-system P3a-decide v2 (ME-8 amendment 2026-05-01): G-GEAR re-capture
PR #131 measured cognition_period ≈ 120 s/tick on qwen3:8b Q4_K_M. With the
v2 ``COOLDOWN_TICKS_EVAL=5`` and ``dialog_turn_budget=6``, one effective
cycle is ~11 ticks ≈ 22 min wall, so 120 min wall yields ~5 cycles ⇒
focal ≈ 24/cell as a conservative lower bound (design-natural-gating-fix-v2.md
§5.1). 60 min was rejected by Codex review (Q3) as below the conservative
margin; operators may still override via ``--wall-timeout-min``. Hard
wall-clock cap for one capture, primarily natural condition.
"""

_RUNTIME_DRAIN_GRACE_S: Final[float] = 60.0
"""Seconds to await ``runtime_task`` after ``runtime.stop()`` (Codex HIGH-6).

m9-eval-cli-partial-fix (Codex M2, 2026-05-06) raised this from 30.0 to 60.0
because the natural-condition cognition tick is ≈ 120 s/tick on qwen3:8b
Q4_K_M; a 30 s grace promotes too many in-flight ticks to fatal. The cost
is +30 s × N(cell) ≈ +15 min over a 30-cell P3 sweep — negligible against
the run1 wall budget (≈ 10 h)."""

_AGENT_ID_FMT: Final[str] = "a_{persona_id}_001"
"""Mirrors :func:`erre_sandbox.bootstrap._build_initial_state` agent id shape."""

_NATURAL_AGORA_POSITIONS: Final[dict[str, tuple[float, float, float]]] = {
    # Three distinct seats inside AGORA so the M5/M6 separation nudge does
    # not perturb spawn coordinates the very first physics tick. AGORA uses
    # the default zone radius, well within the 5m proximity threshold so
    # all three pairs auto-fire.
    "kant": (0.0, 0.0, 0.0),
    "nietzsche": (0.8, 0.0, 0.0),
    "rikyu": (-0.8, 0.0, 0.0),
}

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
    polls (Codex HIGH-3).
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
        Whether ``runtime.stop()`` finished within
        ``_RUNTIME_DRAIN_GRACE_S``; ``True / False`` is the normal pair,
        ``False / True`` indicates a drain timeout (= fatal).
    ``selected_stimulus_ids``
        **Planned** stratified slice ids (Codex L1, 2026-05-06). Records
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


@dataclass
class _SinkState:
    """Shared mutable state surfaced to the watchdog / driver loop.

    The DuckDB sink owns the writes; counters here let async watchers /
    sync assertions reach the same numbers without poking at DuckDB
    mid-flight.

    ``fatal_error`` and ``soft_timeout`` follow a **fatal-precedence**
    policy (Codex Q1 / M1, 2026-05-06): a fatal can land after a soft
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
# Stimulus prompt builder (CLI-local; Codex MEDIUM-4 — do not reach into
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
    capture when ``sink_state.fatal_error`` is set (Codex HIGH-3 propagation).
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
) -> Callable[[DialogTurnMsg], None]:
    """Construct the synchronous closure stored in the scheduler ``turn_sink``.

    Codex HIGH-3: any DuckDB INSERT failure sets ``state.fatal_error`` and
    raises :class:`CaptureFatalError`. The scheduler logs and continues, but the
    capture loop polls ``state.fatal_error`` and aborts before any atomic
    rename can publish a half-written file.

    The 15 ALLOWED_RAW_DIALOG_KEYS columns are bound positionally so a
    drift of either side (DDL vs allow-list) trips the existing
    ``_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS`` import-time check
    in :mod:`evidence.eval_store` first.
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
            con.execute(
                "INSERT INTO raw_dialog.dialog"
                ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
                ' "speaker_agent_id", "speaker_persona_id",'
                ' "addressee_agent_id", "addressee_persona_id",'
                ' "utterance", "mode", "zone", "reasoning",'
                ' "epoch_phase", "created_at")'
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    "",  # mode left empty per Codex MEDIUM-2 (reserved for ERRE mode)
                    zone_label,
                    "",
                    "autonomous",
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


# ---------------------------------------------------------------------------
# Stratified slicing (Codex HIGH-1)
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


def _initial_state_for_natural(persona: PersonaSpec) -> AgentState:
    """Build the AgentState used to register a persona for the natural run.

    Mirrors :func:`erre_sandbox.bootstrap._build_initial_state` but pins
    the spawn ``Position`` to a non-overlapping seat inside :attr:`Zone.AGORA`
    so the M5/M6 separation nudge does not fire on the first physics tick.
    """
    pid = persona.persona_id
    seat = _NATURAL_AGORA_POSITIONS.get(pid, (0.0, 0.0, 0.0))
    erre_name = ZONE_TO_DEFAULT_ERRE_MODE.get(Zone.AGORA, ERREModeName.DEEP_WORK)
    return AgentState(
        agent_id=_AGENT_ID_FMT.format(persona_id=pid),
        persona_id=pid,
        tick=0,
        position=Position(x=seat[0], y=seat[1], z=seat[2], zone=Zone.AGORA),
        erre=ERREMode(name=erre_name, entered_at_tick=0),
    )


# ---------------------------------------------------------------------------
# Output path / overwrite policy (Codex HIGH-4)
# ---------------------------------------------------------------------------


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
      requires ``--allow-partial-rescue`` (Codex HIGH-4, 2026-05-06).
    * stale ``.tmp`` with a *corrupted* sidecar (Pydantic ValidationError
      or unreadable JSON): requires ``--force-rescue`` (Codex M4); the
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

    Codex MEDIUM-3: ``health_check()`` only hits ``/api/tags``; a 1-token
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
) -> CaptureResult:
    """Capture one natural-condition cell using a headless WorldRuntime stack.

    ``runtime_factory`` exists so the unit test can inject a manually clocked
    WorldRuntime + stub DialogTurnGenerator without the live cognition stack.
    """
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

    run_id = f"{persona}_natural_run{run_idx}"
    state = _SinkState()
    enough_event = asyncio.Event()

    con = duckdb.connect(str(temp_path), read_only=False)
    bootstrap_schema(con)

    if memory_db_path is None:
        # ME-2 keeps the natural-condition memory DB /tmp-scoped so the eval
        # DuckDB file remains the only artefact rsync'd back to Mac.
        memory_db_path = Path(
            f"/tmp/p3a_natural_{persona}_run{run_idx}.sqlite",  # noqa: S108
        )
    if memory_db_path.exists():
        memory_db_path.unlink()

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
        )

    retriever = Retriever(memory, embedding)

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
        )
        runtime = WorldRuntime(cycle=cycle)
    else:
        runtime = runtime_factory(
            memory=memory,
            embedding=embedding,
            inference=inference,
            retriever=retriever,
            persona_specs=persona_specs,
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
    )

    scheduler_rng = random.Random(seed_root)  # noqa: S311 — non-crypto, eval seed
    scheduler = InMemoryDialogScheduler(
        envelope_sink=runtime.inject_envelope,
        rng=scheduler_rng,
        turn_sink=duckdb_sink,
        golden_baseline_mode=False,
        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
        # sustain dialog after LLM destination_zone scatters them out of
        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
        # for root-cause analysis.
        eval_natural_mode=True,
    )
    runtime.attach_dialog_scheduler(scheduler)

    dialog_generator = OllamaDialogTurnGenerator(llm=inference, personas=persona_specs)
    runtime.attach_dialog_generator(dialog_generator)

    # Register all three personas so proximity auto-fire has every pair
    # available.  Codex MEDIUM-5 confirmed _iter_colocated_pairs only checks
    # zone equality, so the three seats inside AGORA are sufficient.
    for pid in DEFAULT_PERSONAS:
        spec = persona_specs[pid]
        runtime.register_agent(_initial_state_for_natural(spec), spec)

    # Warmup — same fail-soft logic as stimulus.
    await _warm_up_ollama(inference, persona_specs[persona])

    # Drive: spawn runtime task + watchdog.  The watchdog returns once the
    # focal budget is reached, the wall hard cap is hit, or the runtime
    # task itself completes (e.g. fatal error inside the cycle).
    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
    wall_deadline = time.monotonic() + wall_timeout_min * 60.0

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
                # ME-9 / Codex HIGH-3 (2026-05-06): wall budget = soft timeout,
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
        runtime.stop()
        try:
            await asyncio.wait_for(runtime_task, timeout=_RUNTIME_DRAIN_GRACE_S)
        except TimeoutError:
            # Codex Q1 (2026-05-06): drain incomplete = fatal regardless of
            # wall budget — checkpoint/close cannot be guaranteed, so silent
            # publish of a torn DuckDB file is unsafe.
            state.drain_completed = False
            state.runtime_drain_timeout = True
            state.set_fatal(f"runtime drain exceeded {_RUNTIME_DRAIN_GRACE_S}s")
            runtime_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await runtime_task
        except Exception as exc:  # noqa: BLE001 — Codex H2: capture unhandled
            # Codex H2 (2026-05-06): an exception inside ``runtime.run()`` was
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
    ``CaptureStatus`` Literal addition that misses a branch (Codex L3,
    2026-05-06).
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
    )
    write_sidecar_atomic(sidecar_path, payload)

    typed_status: CaptureStatus = status
    match typed_status:
        case "complete":
            atomic_temp_rename(temp_path, final_path)
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


def _resolve_publish_outcome(
    result: CaptureResult,
    focal_target: int,
) -> tuple[CaptureStatus, StopReason]:
    """Decide ``(status, stop_reason)`` from a returned :class:`CaptureResult`.

    Encodes Codex H2 (2026-05-06): a complete branch with focal_rows below
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


def main(argv: list[str] | None = None) -> int:
    """Console entry — used by both the live CLI and the smoke tests."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
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
