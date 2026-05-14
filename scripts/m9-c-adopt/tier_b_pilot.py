"""SGLang LoRA Tier B pilot driver — m9-c-adopt Phase B Step 5c.

Per-rank serialized inference loop against SGLang with LoRA adapter routing.
Ollama-only ``eval_run_golden`` cannot select a LoRA adapter, so this driver
goes straight to the SGLang OpenAI-compatible chat endpoint with
``model=kant_r{rank}_real`` per Step 4 multi-pin sanity result.

Outputs ``raw_dialog`` rows with ``epoch_phase=evaluation`` so the captured
shard never leaks back into training. Per-turn checkpoint resume is keyed on
``(cycle_idx, stimulus_id)`` so an interrupted run picks up where it left off
without re-firing the prior 100 turns.

Scope narrowing (DA-11, Phase B 第 3 セッション):
* Each multi-turn stimulus is folded to a single focal turn (turn_index=0
  only). Rationale: pilot focuses on adapter-conditional Vendi
  diversity / future Big5 ICC, not multi-turn ToM dynamics. Full multi-turn
  采取 deferred to Phase E (A-6 full Tier B 7500 turn).
* No interlocutor; the persona speaks to the stimulus directly.
* SGLang HTTP API only — no MultiBackendChatClient (Phase D scope).
* Big5 ICC + Burrows scoring deferred (separate consumer in Phase B 第 4 セッション).

Usage::

    python scripts/m9-c-adopt/tier_b_pilot.py \\
        --persona kant --rank 8 --run-idx 0 \\
        --turn-count 300 --cycle-count 6 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-tier-b-pilot/kant_r8_run0_stim.duckdb
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
_CHECKPOINT_FLUSH_EVERY: Final = 25
_INFERENCE_RETRY_MAX: Final = 3
_INFERENCE_RETRY_BACKOFF_S: Final = 1.5
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
# Stimulus loading + stratified slice (self-contained replica of
# eval_run_golden._stratified_stimulus_slice to avoid heavy import surface)
# ---------------------------------------------------------------------------


def _load_stimulus_battery(persona_id: str, root: Path) -> list[dict[str, Any]]:
    path = root / f"{persona_id}.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("stimuli"), list):
        msg = f"{path}: malformed stimulus YAML"
        raise ValueError(msg)
    return list(parsed["stimuli"])


def _focal_turn_count(stimulus: dict[str, Any]) -> int:
    """Folded to 1 — multi-turn stimuli are evaluated as single focal turn."""
    del stimulus
    return 1


def _stratified_slice(
    battery: list[dict[str, Any]], target_focal_per_cycle: int
) -> list[dict[str, Any]]:
    if target_focal_per_cycle <= 0:
        return []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for stim in battery:
        by_cat[str(stim.get("category", ""))].append(stim)
    total = sum(_focal_turn_count(s) for s in battery)
    if total == 0 or target_focal_per_cycle >= total:
        return list(battery)
    selected: list[dict[str, Any]] = []
    chosen = 0
    for stims in by_cat.values():
        cat_total = sum(_focal_turn_count(s) for s in stims)
        share = round(cat_total / total * target_focal_per_cycle)
        cum = 0
        for stim in stims:
            cf = _focal_turn_count(stim)
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
            chosen += _focal_turn_count(stim)
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


def _build_user_prompt(stimulus: dict[str, Any], cycle_idx: int) -> str:
    prompt_text = str(stimulus.get("prompt_text", "")).strip()
    category = str(stimulus.get("category", ""))
    return (
        f"[stimulus_id={stimulus.get('stimulus_id', '?')} "
        f"category={category} cycle={cycle_idx} turn=0]\n\n{prompt_text}"
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
    # qwen3 emits <think>...</think> CoT by default; baseline shards were
    # captured via Ollama think=false. Disable thinking for apples-to-apples
    # parity through the chat_template_kwargs hook (qwen3 chat template
    # honours enable_thinking).
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
            # Defensive: strip <think>...</think> blocks if leaked despite
            # enable_thinking=False (qwen3 occasionally emits them when the
            # template kwarg is silently ignored by an upstream layer).
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


def _insert_focal_turn(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    persona_id: str,
    dialog_id: str,
    tick: int,
    utterance: str,
    zone: str,
) -> None:
    row_id = f"{run_id}:{dialog_id}:0"
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
            0,
            _AGENT_ID_FMT.format(persona_id=persona_id),
            persona_id,
            _INTERLOCUTOR_ID,
            _INTERLOCUTOR_ID,
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


def _derive_seed(persona: str, rank: int, run_idx: int) -> int:
    key = f"{persona}|r{rank}|run{run_idx}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def run_pilot(args: argparse.Namespace) -> int:
    persona_id = args.persona
    rank = args.rank
    run_idx = args.run_idx
    adapter_name = args.adapter_name or f"{persona_id}_r{rank}_real"

    persona_yaml = _load_persona_yaml(args.personas_dir, persona_id)
    system_prompt = _build_system_prompt(persona_yaml)

    battery = _load_stimulus_battery(persona_id, args.stimulus_dir)
    target_per_cycle = max(1, args.turn_count // max(1, args.cycle_count))
    sliced = _stratified_slice(battery, target_focal_per_cycle=target_per_cycle)
    if not sliced:
        logger.error("stratified slice produced 0 stimuli for persona=%s", persona_id)
        return 2

    seed_root = _derive_seed(persona_id, rank, run_idx)
    run_id = f"{persona_id}_r{rank}_run{run_idx}_pilot"

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

    if not args.skip_adapter_check:
        _ensure_adapter_loaded(
            host=args.sglang_host,
            adapter_name=adapter_name,
            timeout_s=args.timeout_s,
        )
        logger.info("adapter %s confirmed loaded on sglang", adapter_name)

    target_total = args.turn_count
    tick = completed
    started_at = time.monotonic()
    skip_until_resume = completed > 0

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
            user_prompt = _build_user_prompt(stimulus, cycle_idx)
            zone = str(stimulus.get("expected_zone", ""))
            dialog_id = f"{run_id}:c{cycle_idx}:{stim_id}"
            seed = (seed_root ^ (cycle_idx << 16) ^ hash(stim_id)) & 0xFFFFFFFF
            try:
                resp = _sglang_chat(
                    host=args.sglang_host,
                    model_name=adapter_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=args.temperature,
                    seed=int(seed),
                    timeout_s=args.timeout_s,
                )
            except RuntimeError:
                logger.exception(
                    "fatal sglang failure at cycle=%d stim=%s — checkpointing",
                    cycle_idx,
                    stim_id,
                )
                _flush_state(con, cycle_idx, stim_id, completed)
                con.execute("CHECKPOINT")
                con.close()
                return 3
            _insert_focal_turn(
                con,
                run_id=run_id,
                persona_id=persona_id,
                dialog_id=dialog_id,
                tick=tick,
                utterance=resp.text,
                zone=zone,
            )
            completed += 1
            tick += 1
            if completed % _CHECKPOINT_FLUSH_EVERY == 0:
                _flush_state(con, cycle_idx, stim_id, completed)
                con.execute("CHECKPOINT")
                elapsed = time.monotonic() - started_at
                rate = completed / max(elapsed, 1e-3)
                eta_s = max(0.0, (target_total - completed) / max(rate, 1e-6))
                logger.info(
                    "checkpoint persona=%s rank=%d run=%d completed=%d/%d"
                    " rate=%.2f turn/s eta=%.1f min",
                    persona_id,
                    rank,
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
        "pilot done persona=%s rank=%d run=%d completed=%d elapsed=%.1f min"
        " output=%s",
        persona_id,
        rank,
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
            "Per-rank Tier B pilot采取 against SGLang with LoRA adapter routing."
            " Outputs raw_dialog with epoch_phase=evaluation; per-25-turn"
            " checkpoint resume."
        ),
    )
    p.add_argument("--persona", required=True, choices=("kant", "nietzsche", "rikyu"))
    p.add_argument("--rank", required=True, type=int, choices=(4, 8, 16, 32))
    p.add_argument("--run-idx", required=True, type=int)
    p.add_argument("--turn-count", type=int, default=_DEFAULT_TURN_COUNT)
    p.add_argument("--cycle-count", type=int, default=_DEFAULT_CYCLE_COUNT)
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
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )
    return run_pilot(args)


if __name__ == "__main__":
    sys.exit(main())
