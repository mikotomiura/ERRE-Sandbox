r"""SGLang LoRA Tier B pilot driver — m9-c-adopt Phase B Step 5c.

Per-rank serialized inference loop against SGLang with LoRA adapter routing.
Ollama-only ``eval_run_golden`` cannot select a LoRA adapter, so this driver
goes straight to the SGLang OpenAI-compatible chat endpoint with
``model=kant_r{rank}_real`` per Step 4 multi-pin sanity result.

Outputs ``raw_dialog`` rows with ``epoch_phase=evaluation`` so the captured
shard never leaks back into training. Per-stimulus checkpoint resume is keyed
on ``(cycle_idx, stimulus_id)`` so an interrupted run picks up where it left
off without re-firing the prior 100 turns.

Phase B 第 3 セッション scope (DA-11、single-turn):
* ``--multi-turn-max 1`` (default) folds multi-turn stimuli to a single focal
  turn (turn_index=0 only). Pilot focuses on adapter-conditional Vendi
  diversity / future Big5 ICC, not multi-turn ToM dynamics.

m9-c-adopt-pilot-multiturn investigation 第 1 セッション (本拡張、2026-05-14):
* ``--multi-turn-max N >= 2`` enables baseline-style no-prior alternating-speaker
  stimulus protocol: for each stimulus, run ``min(expected_turn_count, N)`` turns
  alternating focal / interlocutor speakers; each turn is a fresh SGLang call
  with the same focal-persona system prompt + same stimulus user prompt (only
  ``turn=K`` marker varies). Mirrors ``GoldenBaselineDriver.run_stimulus`` +
  ``_make_stimulus_inference_fn`` (eval_run_golden.py) which delete persona_id
  and prior_turns to keep apples-to-apples parity with PR #160 baseline.
* ``--no-lora-control`` (HIGH-1) routes to the SGLang base model
  (``model=Qwen/Qwen3-8B``, no adapter) so a same-protocol no-LoRA control can
  be captured under the very same SGLang server. ``--rank`` is accepted as
  ``0`` in this mode and not used for adapter routing.
* Stimulus-atomic checkpointing (MEDIUM-3): on fatal SGLang error mid-stim,
  rows of the in-progress ``dialog_id`` are deleted before checkpoint so the
  shard never contains a partial multi-turn dialog.
* Big5 ICC + Burrows scoring deferred (separate consumer in Phase B 第 4
  セッション / multi-turn investigation 第 1 セッション).

Usage::

    # single-turn (legacy)
    python scripts/m9-c-adopt/tier_b_pilot.py \\
        --persona kant --rank 8 --run-idx 0 \\
        --turn-count 300 --cycle-count 6 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-tier-b-pilot/kant_r8_run0_stim.duckdb

    # multi-turn LoRA-on
    python scripts/m9-c-adopt/tier_b_pilot.py \\
        --persona kant --rank 8 --run-idx 0 \\
        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_r8_run0_stim.duckdb

    # multi-turn no-LoRA control (HIGH-1)
    python scripts/m9-c-adopt/tier_b_pilot.py \\
        --persona kant --rank 0 --run-idx 0 --no-lora-control \\
        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run0_stim.duckdb
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import duckdb
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_DEFAULT_STIMULUS_DIR: Final = _REPO_ROOT / "golden" / "stimulus"
_DEFAULT_PERSONAS_DIR: Final = _REPO_ROOT / "personas"
_DEFAULT_SGLANG_HOST: Final = "http://127.0.0.1:30000"
_DEFAULT_TIMEOUT_S: Final = 120.0
_DEFAULT_TURN_COUNT: Final = 300
_DEFAULT_CYCLE_COUNT: Final = 6
_DEFAULT_MULTI_TURN_MAX: Final = 1
_CHECKPOINT_FLUSH_EVERY: Final = 25
_INFERENCE_RETRY_MAX: Final = 3
_INFERENCE_RETRY_BACKOFF_S: Final = 1.5
_NO_LORA_MODEL: Final = "Qwen/Qwen3-8B"
_RAW_DIALOG_TABLE_DDL: Final = """
CREATE SCHEMA IF NOT EXISTS raw_dialog;
CREATE TABLE IF NOT EXISTS raw_dialog.dialog (
    "id" TEXT,
    "run_id" TEXT,
    "dialog_id" TEXT,
    "tick" INTEGER,
    "turn_index" INTEGER,
    "speaker_agent_id" TEXT,
    "speaker_persona_id" TEXT,
    "addressee_agent_id" TEXT,
    "addressee_persona_id" TEXT,
    "utterance" TEXT,
    "mode" TEXT,
    "zone" TEXT,
    "reasoning" TEXT,
    "epoch_phase" TEXT,
    "individual_layer_enabled" BOOLEAN NOT NULL DEFAULT FALSE,
    "created_at" TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pilot_state (
    last_cycle_idx INTEGER,
    last_stimulus_id TEXT,
    completed_turns INTEGER,
    updated_at TIMESTAMP
);
"""

_INTERLOCUTOR_ID: Final = "_stimulus"
_AGENT_ID_FMT: Final = "a_{persona_id}_001"
_FOCAL_NUM_PREDICT: Final = 240
_FOCAL_STOP: Final = ("\n\n",)


# ---------------------------------------------------------------------------
# Stimulus loading + stratified slice
# ---------------------------------------------------------------------------


def _load_stimulus_battery(persona_id: str, root: Path) -> list[dict[str, Any]]:
    path = root / f"{persona_id}.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("stimuli"), list):
        msg = f"{path}: malformed stimulus YAML"
        raise ValueError(msg)
    return list(parsed["stimuli"])


def _focal_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
    """Per-stimulus focal-speaker turn count.

    Mirrors ``eval_run_golden._focal_turn_count`` (P3 stimulus condition) so
    baseline (no-LoRA) and pilot (LoRA-on) shards are apples-to-apples on the
    turn-budget axis.

    single-turn mode (``multi_turn_max == 1``, DA-11): always 1.
    multi-turn mode (``multi_turn_max >= 2``): ``ceil(N/2)`` where
        ``N = min(expected_turn_count, multi_turn_max)``. The driver alternates
        speakers (turn_index=0 focal, turn_index=1 interlocutor, …) so for
        N=2 the focal speaks 1 turn, N=3 → 2 turns.
    """
    if multi_turn_max <= 1:
        return 1
    expected = int(stimulus.get("expected_turn_count", 1))
    capped = max(1, min(expected, multi_turn_max))
    return (capped + 1) // 2


def _total_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
    """Total turns per stimulus (focal + interlocutor)."""
    if multi_turn_max <= 1:
        return 1
    expected = int(stimulus.get("expected_turn_count", 1))
    return max(1, min(expected, multi_turn_max))


def _stratified_slice(
    battery: list[dict[str, Any]],
    target_focal_per_cycle: int,
    multi_turn_max: int,
) -> list[dict[str, Any]]:
    if target_focal_per_cycle <= 0:
        return []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for stim in battery:
        by_cat[str(stim.get("category", ""))].append(stim)
    total = sum(_focal_turn_count(s, multi_turn_max) for s in battery)
    if total == 0 or target_focal_per_cycle >= total:
        return list(battery)
    selected: list[dict[str, Any]] = []
    chosen = 0
    for stims in by_cat.values():
        cat_total = sum(_focal_turn_count(s, multi_turn_max) for s in stims)
        share = round(cat_total / total * target_focal_per_cycle)
        cum = 0
        for stim in stims:
            cf = _focal_turn_count(stim, multi_turn_max)
            if cum + cf > share:
                break
            selected.append(stim)
            cum += cf
        chosen += cum
    if chosen < target_focal_per_cycle:
        for stim in battery:
            if chosen >= target_focal_per_cycle:
                break
            if stim in selected:
                continue
            selected.append(stim)
            chosen += _focal_turn_count(stim, multi_turn_max)
    selected_ids = {s.get("stimulus_id") for s in selected}
    return [s for s in battery if s.get("stimulus_id") in selected_ids]


# ---------------------------------------------------------------------------
# Persona prompt — minimal, mirrors eval_run_golden._build_stimulus_system_prompt
# spirit so baseline (no-LoRA) and pilot (LoRA-on) shards are apples-to-apples
# on the prompt axis. The LoRA's contribution is the only conditional variable.
# ---------------------------------------------------------------------------


def _load_persona_yaml(personas_dir: Path, persona_id: str) -> dict[str, Any]:
    path = personas_dir / f"{persona_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _build_system_prompt(persona: dict[str, Any]) -> str:
    display = persona.get("display_name", persona.get("persona_id", "agent"))
    era = persona.get("era", "")
    habits_seq: list[Any] = persona.get("cognitive_habits") or []
    habit_lines: list[str] = []
    for habit in list(habits_seq)[:3]:
        if isinstance(habit, dict):
            desc = habit.get("description", "")
            flag = habit.get("flag", "")
            habit_lines.append(f"- {desc} [{flag}]")
    habits_block = "\n".join(habit_lines) if habit_lines else "(no habits recorded)"
    common = (
        "You are an autonomous agent in ERRE-Sandbox. A researcher hands you "
        "a curated stimulus from a Toulmin / Theory-of-Mind / RoleEval / "
        "moral-dilemma battery. Stay in character; speak as yourself, not "
        "about yourself."
    )
    persona_block = (
        f"Persona: {display} ({era}).\nCognitive habits:\n{habits_block}"
    )
    closing = (
        "Respond in a single concise utterance: at most 80 Japanese characters "
        "or 160 Latin characters. Return ONLY the utterance text — no names, "
        "no quotation marks, no stage directions, no JSON, no chain-of-thought."
    )
    return f"{common}\n\n{persona_block}\n\n{closing}"


def _build_user_prompt(
    stimulus: dict[str, Any], cycle_idx: int, turn_index: int
) -> str:
    prompt_text = str(stimulus.get("prompt_text", "")).strip()
    category = str(stimulus.get("category", ""))
    return (
        f"[stimulus_id={stimulus.get('stimulus_id', '?')} "
        f"category={category} cycle={cycle_idx} turn={turn_index}]\n\n{prompt_text}"
    )


# ---------------------------------------------------------------------------
# SGLang HTTP client (urllib only, no httpx dep)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SGLangChatResponse:
    text: str
    finish_reason: str | None
    raw: dict[str, Any]


def _sglang_chat(
    *,
    host: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    seed: int,
    timeout_s: float,
) -> SGLangChatResponse:
    """One blocking POST to SGLang ``/v1/chat/completions``."""
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": _FOCAL_NUM_PREDICT,
        "temperature": temperature,
        "seed": seed,
        "stop": list(_FOCAL_STOP),
        "chat_template_kwargs": {"enable_thinking": False},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — fixed scheme via host arg
        f"{host.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_exc: Exception | None = None
    for attempt in range(_INFERENCE_RETRY_MAX):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
                raw = json.loads(resp.read().decode("utf-8"))
            choices = raw.get("choices") or []
            if not choices:
                msg = f"sglang returned no choices: {raw}"
                raise RuntimeError(msg)
            choice = choices[0]
            text = str(choice.get("message", {}).get("content", "")).strip()
            if "</think>" in text:
                text = text.split("</think>", 1)[1].strip()
            if text.startswith("<think>"):
                text = text.removeprefix("<think>").strip()
            finish = choice.get("finish_reason")
            return SGLangChatResponse(text=text, finish_reason=finish, raw=raw)
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_exc = exc
            wait_s = _INFERENCE_RETRY_BACKOFF_S * (2**attempt)
            logger.warning(
                "sglang chat failed attempt=%d/%d: %s — backing off %.1fs",
                attempt + 1,
                _INFERENCE_RETRY_MAX,
                exc,
                wait_s,
            )
            time.sleep(wait_s)
    msg = f"sglang chat exhausted {_INFERENCE_RETRY_MAX} attempts: {last_exc!r}"
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Adapter health check
# ---------------------------------------------------------------------------


def _ensure_adapter_loaded(*, host: str, adapter_name: str, timeout_s: float) -> None:
    """Verify ``adapter_name`` is in SGLang ``/get_server_info`` loaded set.

    Pilot does NOT load adapters itself — operator must launch SGLang with
    ``--max-loras-per-batch >= rank_count`` and POST ``/load_lora_adapter`` for
    each rank ahead of time (re-using ``multi_pin_sanity.sh``). This check
    surfaces a misconfiguration before burning compute on 600 turns.
    """
    req = urllib.request.Request(  # noqa: S310 — fixed host
        f"{host.rstrip('/')}/v1/models",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            info = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"sglang /v1/models unreachable at {host}: {exc!r}"
        raise RuntimeError(msg) from exc
    entries: Iterable[dict[str, Any]] = info.get("data") or []
    loaded_set = {str(entry.get("id", "")) for entry in entries if entry.get("id")}
    if adapter_name not in loaded_set:
        msg = (
            f"adapter {adapter_name!r} not in sglang loaded set"
            f" {sorted(loaded_set)} — POST /load_lora_adapter first"
        )
        raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# DuckDB sink + checkpoint
# ---------------------------------------------------------------------------


def _bootstrap_db(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_RAW_DIALOG_TABLE_DDL)


def _read_resume_state(con: duckdb.DuckDBPyConnection) -> tuple[int, str | None, int]:
    rows = con.execute(
        "SELECT last_cycle_idx, last_stimulus_id, completed_turns"
        " FROM pilot_state ORDER BY updated_at DESC LIMIT 1"
    ).fetchall()
    if not rows:
        return 0, None, 0
    return int(rows[0][0]), rows[0][1], int(rows[0][2])


def _flush_state(
    con: duckdb.DuckDBPyConnection,
    cycle_idx: int,
    stimulus_id: str,
    completed: int,
) -> None:
    con.execute("DELETE FROM pilot_state")
    con.execute(
        "INSERT INTO pilot_state VALUES (?, ?, ?, ?)",
        (cycle_idx, stimulus_id, completed, datetime.now(UTC)),
    )


def _delete_dialog_rows(con: duckdb.DuckDBPyConnection, dialog_id: str) -> None:
    """Atomic rollback (MEDIUM-3): drop any rows of the in-progress dialog so
    a fatal mid-stim never leaves a partial multi-turn dialog in the shard.
    """
    con.execute("DELETE FROM raw_dialog.dialog WHERE dialog_id = ?", (dialog_id,))


def _insert_turn(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    speaker_pid: str,
    addressee_pid: str,
    dialog_id: str,
    tick: int,
    turn_index: int,
    utterance: str,
    zone: str,
) -> None:
    row_id = f"{run_id}:{dialog_id}:{turn_index}"
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
            dialog_id,
            tick,
            turn_index,
            (
                _AGENT_ID_FMT.format(persona_id=speaker_pid)
                if speaker_pid != _INTERLOCUTOR_ID
                else _INTERLOCUTOR_ID
            ),
            speaker_pid,
            (
                _AGENT_ID_FMT.format(persona_id=addressee_pid)
                if addressee_pid != _INTERLOCUTOR_ID
                else _INTERLOCUTOR_ID
            ),
            addressee_pid,
            utterance,
            "",  # mode reserved for ERRE FSM (eval doesn't fire FSM)
            zone,
            "",
            "evaluation",  # DB11 contamination contract — eval-only
            datetime.now(UTC),
        ),
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _derive_seed(persona: str, rank: int, run_idx: int, no_lora: bool) -> int:
    tag = "nolora" if no_lora else f"r{rank}"
    key = f"{persona}|{tag}|run{run_idx}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def run_pilot(args: argparse.Namespace) -> int:  # noqa: C901, PLR0915 — sequential capture is inherently long
    persona_id = args.persona
    rank = args.rank
    run_idx = args.run_idx
    no_lora = bool(args.no_lora_control)
    multi_turn_max = max(1, int(args.multi_turn_max))

    if no_lora:
        model_name = _NO_LORA_MODEL
        run_tag = "nolora"
    else:
        model_name = args.adapter_name or f"{persona_id}_r{rank}_real"
        run_tag = f"r{rank}"

    persona_yaml = _load_persona_yaml(args.personas_dir, persona_id)
    system_prompt = _build_system_prompt(persona_yaml)

    battery = _load_stimulus_battery(persona_id, args.stimulus_dir)
    target_per_cycle = max(1, args.turn_count // max(1, args.cycle_count))
    sliced = _stratified_slice(
        battery,
        target_focal_per_cycle=target_per_cycle,
        multi_turn_max=multi_turn_max,
    )
    if not sliced:
        logger.error("stratified slice produced 0 stimuli for persona=%s", persona_id)
        return 2

    seed_root = _derive_seed(persona_id, rank, run_idx, no_lora)
    run_id = f"{persona_id}_{run_tag}_run{run_idx}_pilot"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.output), read_only=False)
    _bootstrap_db(con)

    resume_cycle, resume_stim, completed = _read_resume_state(con)
    if completed > 0:
        logger.info(
            "resuming from cycle=%d last_stim=%s completed=%d",
            resume_cycle,
            resume_stim,
            completed,
        )

    if not args.skip_adapter_check and not no_lora:
        _ensure_adapter_loaded(
            host=args.sglang_host,
            adapter_name=model_name,
            timeout_s=args.timeout_s,
        )
        logger.info("adapter %s confirmed loaded on sglang", model_name)
    elif no_lora:
        logger.info("--no-lora-control mode: routing to base model %s", model_name)

    target_total = args.turn_count
    tick = completed
    started_at = time.monotonic()
    skip_until_resume = completed > 0

    total_turn_log = (
        f"multi-turn-max={multi_turn_max} (focal per stim avg ="
        f" {sum(_focal_turn_count(s, multi_turn_max) for s in sliced)/len(sliced):.2f})"
    )
    logger.info(
        "pilot start persona=%s tag=%s run=%d sliced=%d %s",
        persona_id,
        run_tag,
        run_idx,
        len(sliced),
        total_turn_log,
    )

    for cycle_idx in range(resume_cycle if completed > 0 else 0, args.cycle_count):
        for stim_idx, stimulus in enumerate(sliced):
            if completed >= target_total:
                break
            stim_id = str(stimulus.get("stimulus_id", f"unknown_{stim_idx}"))
            if skip_until_resume:
                if cycle_idx == resume_cycle and stim_id == resume_stim:
                    skip_until_resume = False
                    continue
                if cycle_idx == resume_cycle and stim_id != resume_stim:
                    continue
                # cycle past resume → resume done
                skip_until_resume = False

            zone = str(stimulus.get("expected_zone", ""))
            dialog_id = f"{run_id}:c{cycle_idx}:{stim_id}"
            total_turns_this_stim = _total_turn_count(stimulus, multi_turn_max)
            stim_focal = 0
            stim_fatal = False
            base_seed = (seed_root ^ (cycle_idx << 16) ^ hash(stim_id)) & 0xFFFFFFFF
            stim_tick_start = tick

            # Defensive: clean up any stale rows for this dialog_id before
            # writing (resume after a clean run is idempotent because state
            # only records completed stims, but a manual re-run with same
            # output path should not collide).
            _delete_dialog_rows(con, dialog_id)

            for turn_index in range(total_turns_this_stim):
                is_focal = (turn_index % 2) == 0
                speaker_pid = persona_id if is_focal else _INTERLOCUTOR_ID
                addressee_pid = _INTERLOCUTOR_ID if is_focal else persona_id
                user_prompt = _build_user_prompt(stimulus, cycle_idx, turn_index)
                seed = (base_seed ^ (turn_index << 8)) & 0xFFFFFFFF
                try:
                    resp = _sglang_chat(
                        host=args.sglang_host,
                        model_name=model_name,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=args.temperature,
                        seed=int(seed),
                        timeout_s=args.timeout_s,
                    )
                except RuntimeError:
                    logger.exception(
                        "fatal sglang failure at cycle=%d stim=%s turn=%d"
                        " — rolling back dialog rows, checkpointing",
                        cycle_idx,
                        stim_id,
                        turn_index,
                    )
                    _delete_dialog_rows(con, dialog_id)
                    # Restore tick + completed counters to pre-stim values so
                    # state is consistent (MEDIUM-3).
                    tick = stim_tick_start
                    _flush_state(con, cycle_idx, stim_id, completed)
                    con.execute("CHECKPOINT")
                    con.close()
                    stim_fatal = True
                    break
                _insert_turn(
                    con,
                    run_id=run_id,
                    speaker_pid=speaker_pid,
                    addressee_pid=addressee_pid,
                    dialog_id=dialog_id,
                    tick=tick,
                    turn_index=turn_index,
                    utterance=resp.text,
                    zone=zone,
                )
                if is_focal:
                    stim_focal += 1
                tick += 1
            if stim_fatal:
                return 3

            completed += stim_focal
            if completed % _CHECKPOINT_FLUSH_EVERY < stim_focal:
                _flush_state(con, cycle_idx, stim_id, completed)
                con.execute("CHECKPOINT")
                elapsed = time.monotonic() - started_at
                rate = completed / max(elapsed, 1e-3)
                eta_s = max(0.0, (target_total - completed) / max(rate, 1e-6))
                logger.info(
                    "checkpoint persona=%s tag=%s run=%d completed=%d/%d"
                    " rate=%.2f focal/s eta=%.1f min",
                    persona_id,
                    run_tag,
                    run_idx,
                    completed,
                    target_total,
                    rate,
                    eta_s / 60.0,
                )
        if completed >= target_total:
            break

    _flush_state(con, args.cycle_count, "complete", completed)
    con.execute("CHECKPOINT")
    con.close()
    elapsed = time.monotonic() - started_at
    logger.info(
        "pilot done persona=%s tag=%s run=%d completed=%d elapsed=%.1f min"
        " output=%s",
        persona_id,
        run_tag,
        run_idx,
        completed,
        elapsed / 60.0,
        args.output,
    )
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m9-c-adopt-tier-b-pilot",
        description=(
            "Per-rank Tier B pilot 采取 against SGLang with LoRA adapter routing."
            " Outputs raw_dialog with epoch_phase=evaluation; per-stimulus"
            " atomic checkpoint resume."
        ),
    )
    p.add_argument("--persona", required=True, choices=("kant", "nietzsche", "rikyu"))
    p.add_argument(
        "--rank",
        required=True,
        type=int,
        choices=(0, 4, 8, 16, 32),
        help=(
            "LoRA rank; pass 0 with --no-lora-control to route to the SGLang"
            " base model."
        ),
    )
    p.add_argument("--run-idx", required=True, type=int)
    p.add_argument("--turn-count", type=int, default=_DEFAULT_TURN_COUNT)
    p.add_argument("--cycle-count", type=int, default=_DEFAULT_CYCLE_COUNT)
    p.add_argument(
        "--multi-turn-max",
        type=int,
        default=_DEFAULT_MULTI_TURN_MAX,
        help=(
            "Per-stimulus turn cap. 1 (default) reproduces the DA-11 single-turn"
            " pilot. >=2 enables baseline-style no-prior alternating-speaker"
            " stimulus protocol (focal kant on turn 0/2/..., interlocutor on"
            " turn 1/...). Current Kant stimulus max expected_turn_count=3, so"
            " 6 is a no-op cap that future-proofs longer batteries."
        ),
    )
    p.add_argument(
        "--no-lora-control",
        action="store_true",
        help=(
            "Route to the SGLang base model (no LoRA adapter) for a"
            " same-protocol no-LoRA control capture. Pair with --rank 0."
        ),
    )
    p.add_argument("--temperature", type=float, default=0.6)
    p.add_argument("--sglang-host", default=_DEFAULT_SGLANG_HOST)
    p.add_argument("--timeout-s", type=float, default=_DEFAULT_TIMEOUT_S)
    p.add_argument("--adapter-name", default=None)
    p.add_argument("--skip-adapter-check", action="store_true")
    p.add_argument(
        "--stimulus-dir",
        type=Path,
        default=_DEFAULT_STIMULUS_DIR,
    )
    p.add_argument(
        "--personas-dir",
        type=Path,
        default=_DEFAULT_PERSONAS_DIR,
    )
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.no_lora_control and args.rank != 0:
        logger.warning(
            "--no-lora-control was passed with --rank %d; rank is ignored in"
            " no-LoRA mode (use --rank 0 to make this explicit)",
            args.rank,
        )
    if not args.no_lora_control and args.rank == 0:
        msg = "--rank 0 requires --no-lora-control"
        raise SystemExit(msg)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )
    return run_pilot(args)


if __name__ == "__main__":
    sys.exit(main())
