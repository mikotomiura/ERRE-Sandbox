r"""de-focused monolog collector — m9-c-adopt Plan B (Candidate C hybrid retrain).

採取される shard は kant のドイツ語 monolog (single-turn long-form、no
addressee) で構成され、retrain v3 corpus の de-mass を 0.30+ に押し上げる。

Plan A REJECT (DA-15 Phase 1、`.steering/20260516-m9-c-adopt-da15-impl/
da15-verdict-kant.md`) を受けて、Plan B = Candidate C targeted hybrid
retrain (ADR DA-15 D-1) の B-2 driver として新規実装。既存 5022 examples
は preserve、本 driver の出力は append される。

Design refs:
* `.steering/20260517-m9-c-adopt-plan-b-design/design.md` §1.1, §1.2
* `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-2
* `scripts/m9-c-adopt/tier_b_pilot.py` (SGLang client + DuckDB sink base)

差分 from `tier_b_pilot.py`:

* persona system prompt は de monolog 用に **fork** (`_build_de_monolog_
  system_prompt`)、既存 `_build_system_prompt` は touch しない
* `addressee_persona_id=None` 固定、`expected_turn_count=1` 固定 (multi-
  turn alternation なし)
* sampling: `temperature=0.7`、`frequency_penalty=0.3` / `presence_penalty
  =0.3` (R-2 loop mitigation)
* **post-hoc filter (hard gate)** を採取直後に適用:
  - `classify_language(utterance) == "de"`
  - `estimate_token_count(utterance) >= 60`
  - `marker_density_per_100_tokens >= 1.0` (Cambridge anchor の 50% floor)
  - 同一 trigram 出現 >= 4 回で reject (loop detector)
* `--target-net N`: net 例数 (filter pass 後) が N に達したら停止
* `--max-attempts M`: 採取試行上限 (M 攻撃しても N 不達なら exit 2)
* shard 物理削除: filter reject 行は DuckDB から DELETE、`pilot_state` は
  filter 後の `completed_turns` で更新

Usage:
    python scripts/m9-c-adopt/de_focused_monolog_collector.py \\
        --persona kant --target-net 250 --max-attempts 800 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-plan-b/kant_de_monolog_run0.duckdb

    # smoke test (50 attempts、acceptance rate 測定用)
    python scripts/m9-c-adopt/de_focused_monolog_collector.py \\
        --persona kant --target-net 50 --max-attempts 200 \\
        --sglang-host http://127.0.0.1:30000 \\
        --output data/eval/m9-c-adopt-plan-b/smoke/kant_de_monolog_smoke.duckdb \\
        --dry-run
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import duckdb
import yaml

from erre_sandbox.training.example_features import (
    GERMAN_PATTERNS,
    KANTIAN_PATTERNS,
    classify_language,
    count_markers,
    estimate_token_count,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (mirrors tier_b_pilot.py where applicable)
# ---------------------------------------------------------------------------

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_DEFAULT_STIMULUS_DIR: Final = _REPO_ROOT / "golden" / "stimulus"
_DEFAULT_PERSONAS_DIR: Final = _REPO_ROOT / "personas"
_DEFAULT_SGLANG_HOST: Final = "http://127.0.0.1:30000"
_DEFAULT_TIMEOUT_S: Final = 120.0
_DEFAULT_TARGET_NET: Final = 250
_DEFAULT_MAX_ATTEMPTS: Final = 800
_DEFAULT_TEMPERATURE: Final = 0.7
_DEFAULT_FREQ_PENALTY: Final = 0.3
_DEFAULT_PRESENCE_PENALTY: Final = 0.3
_DEFAULT_MAX_TOKENS: Final = 320
_DEFAULT_MIN_TOKEN_COUNT: Final = 60
_DEFAULT_MIN_MARKER_DENSITY: Final = 1.0
_DEFAULT_TRIGRAM_LOOP_MAX: Final = 4
_CHECKPOINT_FLUSH_EVERY: Final = 25
_INFERENCE_RETRY_MAX: Final = 3
_INFERENCE_RETRY_BACKOFF_S: Final = 1.5
_NO_LORA_MODEL: Final = "Qwen/Qwen3-8B"
_TARGET_ZONES: Final = frozenset({"study", "peripatos"})
_EXCLUDED_CATEGORIES: Final = frozenset({"moral_dilemma", "tom_chashitsu", "roleeval"})

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
    last_stim_id TEXT,
    last_attempt_idx INTEGER,
    completed_net INTEGER,
    total_attempts INTEGER,
    rejected INTEGER,
    updated_at TIMESTAMP
);
"""

_AGENT_ID_FMT: Final = "a_{persona_id}_001"

_DE_MONOLOG_DIRECTIVE: Final = """\

Answer in **German**, even if the stimulus is in English. Write a single \
self-addressed monolog of 80–160 German words (≈ 100–200 \
tokens). Do not address an interlocutor; do not name the questioner. \
Use the Critique-of-Pure-Reason register: transcendental, a priori, an \
sich, kategorischer Imperativ, where the topic permits. Return ONLY the \
monolog text — no preamble, no quotation marks, no JSON, no \
chain-of-thought."""


# ---------------------------------------------------------------------------
# Stimulus loading + subset (de prompt + study/peripatos zone)
# ---------------------------------------------------------------------------


def _load_stimulus_battery(persona_id: str, root: Path) -> list[dict[str, Any]]:
    path = root / f"{persona_id}.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("stimuli"), list):
        msg = f"{path}: malformed stimulus YAML"
        raise TypeError(msg)
    return list(parsed["stimuli"])


def _is_de_prompt(prompt_text: str) -> bool:
    """Heuristic: prompt_text classified as ``de`` or ``mixed`` with strong de hits.

    Reuses :func:`classify_language` for consistency with the post-hoc
    filter applied to model outputs. Allow ``mixed`` so e.g. bilingual
    stims with heavy German function-word density still slip through.
    """
    lang = classify_language(prompt_text)
    return lang in {"de", "mixed"}


def select_de_focused_stimuli(battery: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter battery to de-prompt stimuli in study / peripatos zones.

    Excludes ``moral_dilemma`` / ``tom_chashitsu`` / ``roleeval`` categories
    (design.md R-4: persona drift mitigation — de-monolog directive plus
    out-of-domain stimuli would force artificial German output unrelated
    to Critique-of-Pure-Reason register).
    """
    selected: list[dict[str, Any]] = []
    for stim in battery:
        category = str(stim.get("category", ""))
        zone = str(stim.get("expected_zone", ""))
        prompt_text = str(stim.get("prompt_text", ""))
        if category in _EXCLUDED_CATEGORIES:
            continue
        if zone not in _TARGET_ZONES:
            continue
        if not _is_de_prompt(prompt_text):
            continue
        selected.append(stim)
    return selected


# ---------------------------------------------------------------------------
# Persona prompt — fork of tier_b_pilot._build_system_prompt for de monolog
# ---------------------------------------------------------------------------


def _load_persona_yaml(personas_dir: Path, persona_id: str) -> dict[str, Any]:
    path = personas_dir / f"{persona_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_de_monolog_system_prompt(persona: dict[str, Any]) -> str:
    """Persona system prompt with the de-monolog directive appended.

    Mirrors ``tier_b_pilot._build_system_prompt`` so the persona block
    (display name, era, cognitive habits) is identical, then appends the
    de-monolog directive. Keeping the persona block byte-identical to the
    baseline collector preserves the apples-to-apples comparison axis with
    DA-14 baseline / Plan A rescore.
    """
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
    persona_block = f"Persona: {display} ({era}).\nCognitive habits:\n{habits_block}"
    return f"{common}\n\n{persona_block}\n{_DE_MONOLOG_DIRECTIVE}"


def _build_user_prompt(stimulus: dict[str, Any], attempt_idx: int) -> str:
    prompt_text = str(stimulus.get("prompt_text", "")).strip()
    category = str(stimulus.get("category", ""))
    return (
        f"[stimulus_id={stimulus.get('stimulus_id', '?')} "
        f"category={category} attempt={attempt_idx}]\n\n{prompt_text}"
    )


# ---------------------------------------------------------------------------
# SGLang HTTP client (mirrors tier_b_pilot._sglang_chat with extra penalties)
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
    frequency_penalty: float,
    presence_penalty: float,
    max_tokens: int,
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
        "max_tokens": max_tokens,
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "seed": seed,
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
# Post-hoc filter (hard gate, design.md §1.1)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FilterResult:
    accepted: bool
    reason: str | None  # "lang" | "length" | "marker" | "trigram" | "addressee" | None
    language: str
    token_count: int
    marker_density: float
    trigram_max: int
    has_addressee: bool = False


_WORD_RE: Final = re.compile(r"[\wäöüßÄÖÜ]+", re.UNICODE)

# German addressee / second-person patterns. Hits any of these in an
# accepted "monolog" indicate the persona is actually addressing an
# interlocutor — which would cause the weighting path to boost an
# addressed example as a no-addressee data point (Codex MEDIUM-2).
#
# Informal 2nd-person forms ("du/dich/dir/dein-/euch/euer") are matched
# case-insensitively. Formal forms ("Sie/Ihnen/Ihr-") are matched
# **case-sensitively** because the lowercase variants ("sie" = "she/they",
# "ihr" = "their/her") are ordinary 3rd-person pronouns in German monolog
# (e.g. "die Vernunft erkennt die Grenzen ihrer eigenen Anwendung"). The
# capitalised forms are the address-signal that distinguishes formal you.
_ADDRESSEE_PATTERNS_CI: Final = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bdu\b",
        r"\bdich\b",
        r"\bdir\b",
        r"\bdein(?:e|er|es|en|em)?\b",
        r"\beuch\b",
        r"\beuer\b",
        r"\bfragst\b",
    )
)
_ADDRESSEE_PATTERNS_CS: Final = tuple(
    re.compile(p)
    for p in (
        r"\bSie\b",
        r"\bIhnen\b",
        r"\bIhr(?:e|er|es|en|em)?\b",
    )
)


def _has_addressee_marker(text: str) -> bool:
    """Return True if ``text`` contains a German 2nd-person / addressee form.

    Used as a 5th post-hoc filter axis (Codex MEDIUM-2): stimulus-response
    monologs that address the questioner should not be treated as
    ``addressee=None`` training rows.
    """
    return any(p.search(text) for p in _ADDRESSEE_PATTERNS_CI) or any(
        p.search(text) for p in _ADDRESSEE_PATTERNS_CS
    )


def _max_trigram_count(text: str) -> int:
    """Return the maximum frequency of any token trigram in ``text``."""
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if len(tokens) < 3:  # noqa: PLR2004
        return 0
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for i in range(len(tokens) - 2):
        counts[(tokens[i], tokens[i + 1], tokens[i + 2])] += 1
    return max(counts.values()) if counts else 0


def filter_de_monolog(  # noqa: PLR0911 — short-circuit returns are intentional per-axis
    text: str,
    *,
    min_token_count: int = _DEFAULT_MIN_TOKEN_COUNT,
    min_marker_density: float = _DEFAULT_MIN_MARKER_DENSITY,
    trigram_loop_max: int = _DEFAULT_TRIGRAM_LOOP_MAX,
) -> FilterResult:
    """Apply the 4-axis post-hoc hard gate to a single utterance.

    Order of checks: language → length → marker_density → trigram_loop.
    Short-circuits on first failure for diagnostic clarity.
    """
    if not text or not text.strip():
        return FilterResult(
            accepted=False,
            reason="lang",
            language="mixed",
            token_count=0,
            marker_density=0.0,
            trigram_max=0,
        )
    language = classify_language(text)
    if language != "de":
        return FilterResult(
            accepted=False,
            reason="lang",
            language=language,
            token_count=0,
            marker_density=0.0,
            trigram_max=0,
        )
    tokens = estimate_token_count(text, use_real_tokenizer=False)
    if tokens < min_token_count:
        return FilterResult(
            accepted=False,
            reason="length",
            language=language,
            token_count=tokens,
            marker_density=0.0,
            trigram_max=0,
        )
    marker_count = count_markers(text, GERMAN_PATTERNS) + count_markers(
        text, KANTIAN_PATTERNS
    )
    density = (marker_count / tokens) * 100.0 if tokens > 0 else 0.0
    if density < min_marker_density:
        return FilterResult(
            accepted=False,
            reason="marker",
            language=language,
            token_count=tokens,
            marker_density=density,
            trigram_max=0,
        )
    trigram_max = _max_trigram_count(text)
    if trigram_max > trigram_loop_max:
        return FilterResult(
            accepted=False,
            reason="trigram",
            language=language,
            token_count=tokens,
            marker_density=density,
            trigram_max=trigram_max,
        )
    addressed = _has_addressee_marker(text)
    if addressed:
        return FilterResult(
            accepted=False,
            reason="addressee",
            language=language,
            token_count=tokens,
            marker_density=density,
            trigram_max=trigram_max,
            has_addressee=True,
        )
    return FilterResult(
        accepted=True,
        reason=None,
        language=language,
        token_count=tokens,
        marker_density=density,
        trigram_max=trigram_max,
        has_addressee=False,
    )


# ---------------------------------------------------------------------------
# DuckDB sink + checkpoint
# ---------------------------------------------------------------------------


def _bootstrap_db(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_RAW_DIALOG_TABLE_DDL)


def _read_resume_state(
    con: duckdb.DuckDBPyConnection,
) -> tuple[str | None, int, int, int, int]:
    rows = con.execute(
        "SELECT last_stim_id, last_attempt_idx, completed_net, total_attempts,"
        " rejected FROM pilot_state ORDER BY updated_at DESC LIMIT 1"
    ).fetchall()
    if not rows:
        return None, 0, 0, 0, 0
    return (
        rows[0][0],
        int(rows[0][1]),
        int(rows[0][2]),
        int(rows[0][3]),
        int(rows[0][4]),
    )


def _flush_state(
    con: duckdb.DuckDBPyConnection,
    last_stim: str,
    attempt_idx: int,
    completed_net: int,
    total_attempts: int,
    rejected: int,
) -> None:
    con.execute("DELETE FROM pilot_state")
    con.execute(
        "INSERT INTO pilot_state VALUES (?, ?, ?, ?, ?, ?)",
        (
            last_stim,
            attempt_idx,
            completed_net,
            total_attempts,
            rejected,
            datetime.now(UTC),
        ),
    )


def _insert_monolog_row(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    persona_id: str,
    dialog_id: str,
    tick: int,
    utterance: str,
    zone: str,
) -> None:
    row_id = f"{run_id}:{dialog_id}"
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
            0,  # turn_index always 0 (single-turn monolog)
            _AGENT_ID_FMT.format(persona_id=persona_id),
            persona_id,
            None,  # addressee_agent_id NULL (monolog)
            None,  # addressee_persona_id NULL (monolog)
            utterance,
            "",  # mode reserved for ERRE FSM
            zone,
            "",
            "training",  # NOT evaluation — Plan B output is training corpus
            datetime.now(UTC),
        ),
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _derive_seed(persona: str, run_idx: int) -> int:
    key = f"{persona}|de_monolog|run{run_idx}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "little")


def run_collection(args: argparse.Namespace) -> int:  # noqa: PLR0915
    persona_id = args.persona
    run_idx = args.run_idx

    persona_yaml = _load_persona_yaml(args.personas_dir, persona_id)
    system_prompt = build_de_monolog_system_prompt(persona_yaml)

    battery = _load_stimulus_battery(persona_id, args.stimulus_dir)
    de_stimuli = select_de_focused_stimuli(battery)
    if not de_stimuli:
        logger.error("no de-focused stimuli found for persona=%s", persona_id)
        return 2
    logger.info("de-focused stimulus subset: %d / %d", len(de_stimuli), len(battery))

    seed_root = _derive_seed(persona_id, run_idx)
    run_id = f"{persona_id}_de_monolog_run{run_idx}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.output), read_only=False)
    _bootstrap_db(con)

    if args.dry_run:
        # Dry-run skips resume entirely (Codex LOW-1): the operator wants a
        # clean acceptance-rate measurement free of prior state.
        _resume_stim = None
        resume_attempt = 0
        completed_net = 0
        total_attempts = 0
        rejected = 0
        # Wipe any stale pilot_state so a re-run of --dry-run on the same
        # path produces deterministic acceptance numbers.
        con.execute("DELETE FROM pilot_state")
    else:
        _resume_stim, resume_attempt, completed_net, total_attempts, rejected = (
            _read_resume_state(con)
        )
        if completed_net > 0:
            logger.info(
                "resuming: completed_net=%d total_attempts=%d rejected=%d",
                completed_net,
                total_attempts,
                rejected,
            )

    target_net = args.target_net
    max_attempts = args.max_attempts
    started_at = time.monotonic()

    logger.info(
        "collection start persona=%s run=%d target_net=%d max_attempts=%d"
        " de_stim=%d host=%s",
        persona_id,
        run_idx,
        target_net,
        max_attempts,
        len(de_stimuli),
        args.sglang_host,
    )

    reject_reasons: dict[str, int] = defaultdict(int)
    attempt_idx = resume_attempt

    while completed_net < target_net and total_attempts < max_attempts:
        stim_pos = attempt_idx % len(de_stimuli)
        stimulus = de_stimuli[stim_pos]
        stim_id = str(stimulus.get("stimulus_id", f"unknown_{stim_pos}"))
        zone = str(stimulus.get("expected_zone", ""))
        seed = (seed_root ^ (attempt_idx << 4)) & 0xFFFFFFFF
        user_prompt = _build_user_prompt(stimulus, attempt_idx)

        try:
            resp = _sglang_chat(
                host=args.sglang_host,
                model_name=_NO_LORA_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=args.temperature,
                frequency_penalty=args.frequency_penalty,
                presence_penalty=args.presence_penalty,
                max_tokens=args.max_tokens,
                seed=int(seed),
                timeout_s=args.timeout_s,
            )
        except RuntimeError:
            logger.exception(
                "fatal sglang failure at attempt=%d stim=%s — checkpointing",
                attempt_idx,
                stim_id,
            )
            _flush_state(
                con, stim_id, attempt_idx, completed_net, total_attempts, rejected
            )
            con.execute("CHECKPOINT")
            con.close()
            return 3

        total_attempts += 1
        filter_result = filter_de_monolog(
            resp.text,
            min_token_count=args.min_token_count,
            min_marker_density=args.min_marker_density,
            trigram_loop_max=args.trigram_loop_max,
        )

        if filter_result.accepted:
            dialog_id = f"de_mono_{stim_id}_a{attempt_idx}"
            tick = completed_net
            _insert_monolog_row(
                con,
                run_id=run_id,
                persona_id=persona_id,
                dialog_id=dialog_id,
                tick=tick,
                utterance=resp.text,
                zone=zone,
            )
            completed_net += 1
        else:
            rejected += 1
            reason = filter_result.reason or "unknown"
            reject_reasons[reason] += 1

        attempt_idx += 1

        if total_attempts % _CHECKPOINT_FLUSH_EVERY == 0:
            _flush_state(
                con, stim_id, attempt_idx, completed_net, total_attempts, rejected
            )
            con.execute("CHECKPOINT")
            elapsed = time.monotonic() - started_at
            rate = completed_net / max(elapsed, 1e-3)
            eta_s = max(0.0, (target_net - completed_net) / max(rate, 1e-6))
            acceptance = completed_net / max(total_attempts, 1)
            logger.info(
                "checkpoint completed_net=%d/%d attempts=%d rejected=%d"
                " acceptance=%.1f%% rate=%.2f net/s eta=%.1f min",
                completed_net,
                target_net,
                total_attempts,
                rejected,
                acceptance * 100.0,
                rate,
                eta_s / 60.0,
            )

    _flush_state(con, "complete", attempt_idx, completed_net, total_attempts, rejected)
    con.execute("CHECKPOINT")
    con.close()

    elapsed = time.monotonic() - started_at
    acceptance = completed_net / max(total_attempts, 1)
    logger.info(
        "collection done completed_net=%d target=%d attempts=%d rejected=%d"
        " acceptance=%.1f%% elapsed=%.1f min output=%s",
        completed_net,
        target_net,
        total_attempts,
        rejected,
        acceptance * 100.0,
        elapsed / 60.0,
        args.output,
    )
    for reason, count in sorted(reject_reasons.items()):
        logger.info("  reject reason %s: %d", reason, count)

    # Emit manifest (DA-11 convention; Codex MEDIUM-1 reflection). Includes
    # everything a future reader needs to reproduce or audit the corpus:
    # the merge SHA, sampling params, post-hoc filter thresholds, the
    # stimulus subset, and the achieved acceptance rate.
    manifest_path = _write_manifest(
        args=args,
        run_id=run_id,
        persona_id=persona_id,
        de_stimuli=de_stimuli,
        completed_net=completed_net,
        total_attempts=total_attempts,
        rejected=rejected,
        reject_reasons=reject_reasons,
        acceptance=acceptance,
        elapsed_s=elapsed,
    )
    logger.info("manifest written: %s", manifest_path)

    if completed_net < target_net:
        logger.error(
            "target_net=%d not reached after max_attempts=%d (completed=%d)",
            target_net,
            max_attempts,
            completed_net,
        )
        return 2

    return 0


def _write_manifest(
    *,
    args: argparse.Namespace,
    run_id: str,
    persona_id: str,
    de_stimuli: list[dict[str, Any]],
    completed_net: int,
    total_attempts: int,
    rejected: int,
    reject_reasons: dict[str, int],
    acceptance: float,
    elapsed_s: float,
) -> Path:
    """Emit ``<shard>_manifest.json`` alongside the DuckDB shard (DA-11).

    Records provenance (merge SHA + collection time) plus the parameters
    a future verdict reader needs to reproduce or audit the corpus:
    sampling params, post-hoc filter thresholds, stimulus subset ids.
    """
    output_path: Path = args.output
    manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"
    merge_sha = os.environ.get("PLAN_B_MERGE_SHA", "")
    manifest = {
        "schema_version": 1,
        "shard": output_path.name,
        "run_id": run_id,
        "persona": persona_id,
        "collection_mode": "de_focused_monolog",
        "base_model": _NO_LORA_MODEL,
        "merge_sha": merge_sha,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "target_net": args.target_net,
        "max_attempts": args.max_attempts,
        "achieved_net": completed_net,
        "total_attempts": total_attempts,
        "rejected": rejected,
        "reject_reasons": dict(sorted(reject_reasons.items())),
        "acceptance_rate": acceptance,
        "elapsed_s": elapsed_s,
        "stimulus_subset_ids": sorted(
            str(s.get("stimulus_id", "")) for s in de_stimuli
        ),
        "sampling_params": {
            "temperature": args.temperature,
            "frequency_penalty": args.frequency_penalty,
            "presence_penalty": args.presence_penalty,
            "max_tokens": args.max_tokens,
        },
        "filter_thresholds": {
            "min_token_count": args.min_token_count,
            "min_marker_density": args.min_marker_density,
            "trigram_loop_max": args.trigram_loop_max,
        },
        "is_dry_run": bool(args.dry_run),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m9-c-adopt-de-focused-monolog-collector",
        description=(
            "Plan B (Candidate C hybrid retrain) driver: collect de-focused"
            " single-turn monolog examples from SGLang base model with"
            " post-hoc 4-axis hard gate (de / >=60 tokens / marker density"
            " >=1.0 / no trigram loop)."
        ),
    )
    p.add_argument("--persona", required=True, choices=("kant",))
    p.add_argument("--run-idx", type=int, default=0)
    p.add_argument("--target-net", type=int, default=_DEFAULT_TARGET_NET)
    p.add_argument("--max-attempts", type=int, default=_DEFAULT_MAX_ATTEMPTS)
    p.add_argument("--temperature", type=float, default=_DEFAULT_TEMPERATURE)
    p.add_argument(
        "--frequency-penalty", type=float, default=_DEFAULT_FREQ_PENALTY
    )
    p.add_argument(
        "--presence-penalty", type=float, default=_DEFAULT_PRESENCE_PENALTY
    )
    p.add_argument("--max-tokens", type=int, default=_DEFAULT_MAX_TOKENS)
    p.add_argument(
        "--min-token-count", type=int, default=_DEFAULT_MIN_TOKEN_COUNT
    )
    p.add_argument(
        "--min-marker-density", type=float, default=_DEFAULT_MIN_MARKER_DENSITY
    )
    p.add_argument(
        "--trigram-loop-max", type=int, default=_DEFAULT_TRIGRAM_LOOP_MAX
    )
    p.add_argument("--sglang-host", default=_DEFAULT_SGLANG_HOST)
    p.add_argument("--timeout-s", type=float, default=_DEFAULT_TIMEOUT_S)
    p.add_argument("--stimulus-dir", type=Path, default=_DEFAULT_STIMULUS_DIR)
    p.add_argument("--personas-dir", type=Path, default=_DEFAULT_PERSONAS_DIR)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip resume; useful for smoke / acceptance-rate measurement."
            " Output shard is still written so the operator can inspect"
            " accepted examples."
        ),
    )
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
    return run_collection(args)


if __name__ == "__main__":
    sys.exit(main())
