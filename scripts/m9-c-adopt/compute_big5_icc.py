"""Big5 ICC consumer — m9-c-adopt Phase B 第 4 セッション (DA-11 closure).

Per-window IPIP-50 administering against an LLM-backed responder, followed by
:func:`erre_sandbox.evidence.tier_b.big5_icc.compute_big5_icc` to obtain
ICC(C,k) primary + ICC(A,1) diagnostic with hierarchical bootstrap CI
(cluster_only=True, ME-14).

Responder backends:

* ``--responder ollama``: Windows-native Ollama qwen3:8b ``think=false``
  (no-LoRA baseline).
* ``--responder sglang``: SGLang fp8 with ``--sglang-adapter kant_r{N}_real``
  (LoRA-on per-rank). Adapter must already be POSTed via
  ``/load_lora_adapter`` (re-use ``multi_pin_sanity.sh``).

Anti-demand-characteristics design (Salecha et al. 2024 / ME-13): per-window
context conditioning is **none** — the responder sees only the single rendered
IPIP item, never the focal kant utterances. This deliberately differs from
``tier_b_pilot.py`` (which is multi-turn stimulus-conditioned dialog).

Window slicing matches ``compute_baseline_vendi.py`` so the cluster structure
fed into the hierarchical bootstrap is consistent across the three DA-1 axes:
non-overlapping windows of ``--window-size`` turns per shard, tail dropped.
Per window we administer IPIP-50 once, score Big5, and accumulate one
:class:`Big5Scores` entry; the resulting per-window matrix drives
:func:`compute_big5_icc`.

Usage::

    # no-LoRA baseline (Ollama)
    python scripts/m9-c-adopt/compute_big5_icc.py \\
        --persona kant \\
        --shards-glob "data/eval/golden/kant_stimulus_run*.duckdb" \\
        --responder ollama \\
        --ollama-host http://127.0.0.1:11434 \\
        --ollama-model qwen3:8b --ollama-think false \\
        --window-size 100 \\
        --output .steering/20260513-m9-c-adopt/tier-b-baseline-kant-icc.json

    # LoRA-on (SGLang, single adapter pinned)
    python scripts/m9-c-adopt/compute_big5_icc.py \\
        --persona kant \\
        --shards-glob "data/eval/m9-c-adopt-tier-b-pilot/kant_r4_run*_stim.duckdb" \\
        --responder sglang \\
        --sglang-host http://127.0.0.1:30000 \\
        --sglang-adapter kant_r4_real \\
        --window-size 100 \\
        --output .steering/20260513-m9-c-adopt/tier-b-icc-kant-r4.json
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import duckdb

from erre_sandbox.evidence.tier_b.big5_icc import compute_big5_icc
from erre_sandbox.evidence.tier_b.ipip_neo import (
    DEFAULT_LIKERT_MAX,
    DEFAULT_LIKERT_MIN,
    Big5Scores,
    administer_ipip_neo,
)

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_SIZE: Final[int] = 100
_DEFAULT_TIMEOUT_S: Final[float] = 60.0
_DEFAULT_RETRY_MAX: Final[int] = 3
_DEFAULT_RETRY_BACKOFF_S: Final[float] = 1.0
_LIKERT_RE: Final[re.Pattern[str]] = re.compile(r"[1-5]")


def _load_focal_utterances(shard_path: Path, persona_id: str) -> list[str]:
    """Mirror ``compute_baseline_vendi._load_focal_utterances`` for parity."""
    con = duckdb.connect(str(shard_path), read_only=True)
    rows = con.execute(
        "SELECT utterance FROM raw_dialog.dialog"
        " WHERE speaker_persona_id = ?"
        " ORDER BY tick, turn_index",
        (persona_id,),
    ).fetchall()
    con.close()
    return [str(r[0]).strip() for r in rows if r[0]]


def _windowize(utterances: list[str], window_size: int) -> list[list[str]]:
    n = len(utterances)
    full = n // window_size
    return [
        utterances[i * window_size : (i + 1) * window_size] for i in range(full)
    ]


def _extract_likert(reply: str) -> int:
    """Pull the first 1-5 digit out of an LLM reply.

    Defensive against verbose responders that ignore the "reply with only the
    digit" instruction. Falls back to neutral 3 when no digit is found so the
    administration completes; that fallback contributes to the
    ``acquiescence_index`` diagnostic and is therefore detectable.
    """
    stripped = reply.strip()
    # qwen3 may still emit <think> blocks when enable_thinking is misrouted.
    if "</think>" in stripped:
        stripped = stripped.split("</think>", 1)[1].strip()
    if stripped.startswith("<think>"):
        stripped = stripped.removeprefix("<think>").strip()
    match = _LIKERT_RE.search(stripped)
    if match is None:
        return 3
    return int(match.group(0))


# ---------------------------------------------------------------------------
# Responder factories
# ---------------------------------------------------------------------------


def _build_ollama_responder(
    *,
    host: str,
    model: str,
    think: bool,
    timeout_s: float,
    seed_offset: int,
    temperature: float,
) -> Callable[[str], int]:
    base = host.rstrip("/")
    # Per-call seed counter so each IPIP item gets a unique seed; at T>0
    # this produces administration-level stochasticity while remaining
    # reproducible across re-runs (deterministic ladder from seed_offset).
    state = {"call_idx": 0}

    def responder(prompt: str) -> int:
        call_seed = (seed_offset ^ (state["call_idx"] * 0x85EBCA77)) & 0xFFFFFFFF
        state["call_idx"] += 1
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": think,
            "options": {
                "temperature": temperature,
                "num_predict": 8,
                "seed": int(call_seed),
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 — fixed host
            f"{base}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_exc: Exception | None = None
        for attempt in range(_DEFAULT_RETRY_MAX):
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
                    raw = json.loads(resp.read().decode("utf-8"))
                text = str(raw.get("message", {}).get("content", "")).strip()
                return _clamp_likert(_extract_likert(text))
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_exc = exc
                wait_s = _DEFAULT_RETRY_BACKOFF_S * (2**attempt)
                logger.warning(
                    "ollama responder attempt=%d/%d failed: %s — sleep %.1fs",
                    attempt + 1,
                    _DEFAULT_RETRY_MAX,
                    exc,
                    wait_s,
                )
                time.sleep(wait_s)
        msg = f"ollama responder exhausted retries: {last_exc!r}"
        raise RuntimeError(msg)

    return responder


def _build_sglang_responder(
    *,
    host: str,
    adapter: str,
    timeout_s: float,
    seed_offset: int,
    temperature: float,
) -> Callable[[str], int]:
    base = host.rstrip("/")
    state = {"call_idx": 0}

    def responder(prompt: str) -> int:
        call_seed = (seed_offset ^ (state["call_idx"] * 0x85EBCA77)) & 0xFFFFFFFF
        state["call_idx"] += 1
        payload: dict[str, Any] = {
            "model": adapter,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 8,
            "seed": int(call_seed),
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 — fixed host
            f"{base}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_exc: Exception | None = None
        for attempt in range(_DEFAULT_RETRY_MAX):
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
                    raw = json.loads(resp.read().decode("utf-8"))
                choices = raw.get("choices") or []
                if not choices:
                    msg = f"sglang returned no choices: {raw}"
                    raise RuntimeError(msg)
                text = str(choices[0].get("message", {}).get("content", "")).strip()
                return _clamp_likert(_extract_likert(text))
            except (urllib.error.URLError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
                last_exc = exc
                wait_s = _DEFAULT_RETRY_BACKOFF_S * (2**attempt)
                logger.warning(
                    "sglang responder attempt=%d/%d failed: %s — sleep %.1fs",
                    attempt + 1,
                    _DEFAULT_RETRY_MAX,
                    exc,
                    wait_s,
                )
                time.sleep(wait_s)
        msg = f"sglang responder exhausted retries: {last_exc!r}"
        raise RuntimeError(msg)

    return responder


def _clamp_likert(value: int) -> int:
    return max(DEFAULT_LIKERT_MIN, min(DEFAULT_LIKERT_MAX, value))


# ---------------------------------------------------------------------------
# Window administering
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class WindowAdministration:
    run_id: str
    window_index: int
    big5: Big5Scores
    n_items: int
    acquiescence_index: float
    straight_line_runs: int
    reverse_keyed_agreement: float
    decoy_consistency: float


def _administer_window(
    *,
    responder: Callable[[str], int],
    seed: int,
) -> tuple[Big5Scores, dict[str, float | int]]:
    big5, diagnostic = administer_ipip_neo(
        responder,
        version="ipip-50",
        language="en",
        seed=seed,
        include_decoys=True,
    )
    return big5, {
        "acquiescence_index": diagnostic.acquiescence_index,
        "straight_line_runs": diagnostic.straight_line_runs,
        "reverse_keyed_agreement": diagnostic.reverse_keyed_agreement,
        "decoy_consistency": diagnostic.decoy_consistency,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-big5-icc")
    p.add_argument("--persona", required=True, choices=("kant", "nietzsche", "rikyu"))
    p.add_argument("--shards-glob", required=True)
    p.add_argument("--window-size", type=int, default=_DEFAULT_WINDOW_SIZE)
    p.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Cap windows administered (useful for smoke runs).",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-resamples", type=int, default=2000)
    p.add_argument("--ci", type=float, default=0.95)
    p.add_argument(
        "--responder", required=True, choices=("ollama", "sglang", "stub-constant")
    )
    p.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    p.add_argument("--ollama-model", default="qwen3:8b")
    p.add_argument(
        "--ollama-think",
        default="false",
        choices=("true", "false"),
        help="qwen3 think mode toggle (false = no CoT).",
    )
    p.add_argument("--sglang-host", default="http://127.0.0.1:30000")
    p.add_argument("--sglang-adapter", default=None)
    p.add_argument("--timeout-s", type=float, default=_DEFAULT_TIMEOUT_S)
    p.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help=(
            "LLM sampling temperature. T>0 is required for non-trivial ICC:"
            " at T=0 the responder is deterministic so all windows produce"
            " identical Big5 vectors and ICC collapses to 1.0."
        ),
    )
    p.add_argument("--stub-constant-value", type=int, default=3)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--log-level", default="info", choices=("debug", "info", "warning", "error")
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    shards = sorted(Path(s) for s in glob.glob(args.shards_glob))
    if not shards:
        logger.error("no shards matched %s", args.shards_glob)
        return 2

    # Build responder.
    if args.responder == "ollama":
        responder = _build_ollama_responder(
            host=args.ollama_host,
            model=args.ollama_model,
            think=args.ollama_think.lower() == "true",
            timeout_s=args.timeout_s,
            seed_offset=args.seed,
            temperature=args.temperature,
        )
        responder_id = (
            f"ollama:{args.ollama_model}(think={args.ollama_think},T={args.temperature})"
        )
    elif args.responder == "sglang":
        if not args.sglang_adapter:
            logger.error("--sglang-adapter is required when --responder sglang")
            return 4
        responder = _build_sglang_responder(
            host=args.sglang_host,
            adapter=args.sglang_adapter,
            timeout_s=args.timeout_s,
            seed_offset=args.seed,
            temperature=args.temperature,
        )
        responder_id = f"sglang:{args.sglang_adapter}(T={args.temperature})"
    else:  # stub-constant
        constant_value = _clamp_likert(args.stub_constant_value)

        def responder(_: str) -> int:
            return constant_value

        responder_id = f"stub-constant:{constant_value}"

    # Administer per window.
    administrations: list[WindowAdministration] = []
    big5_list: list[Big5Scores] = []
    started_at = time.monotonic()
    global_window_idx = 0

    for shard in shards:
        utterances = _load_focal_utterances(shard, args.persona)
        windows = _windowize(utterances, args.window_size)
        logger.info(
            "shard=%s focal=%d windows=%d", shard.name, len(utterances), len(windows)
        )
        for w_idx, _window in enumerate(windows):
            if args.max_windows is not None and global_window_idx >= args.max_windows:
                logger.info("--max-windows=%d reached — stopping", args.max_windows)
                break
            seed = (args.seed ^ (global_window_idx * 0x9E3779B1)) & 0xFFFFFFFF
            try:
                big5, diag = _administer_window(responder=responder, seed=int(seed))
            except RuntimeError:
                logger.exception(
                    "administer failed shard=%s window=%d — skipping",
                    shard.name,
                    w_idx,
                )
                global_window_idx += 1
                continue
            administrations.append(
                WindowAdministration(
                    run_id=shard.stem,
                    window_index=w_idx,
                    big5=big5,
                    n_items=big5.n_items,
                    acquiescence_index=float(diag["acquiescence_index"]),
                    straight_line_runs=int(diag["straight_line_runs"]),
                    reverse_keyed_agreement=float(diag["reverse_keyed_agreement"]),
                    decoy_consistency=float(diag["decoy_consistency"]),
                )
            )
            big5_list.append(big5)
            global_window_idx += 1
            elapsed = time.monotonic() - started_at
            rate = global_window_idx / max(elapsed, 1e-3)
            logger.info(
                "window %d/?  shard=%s w_idx=%d big5=E:%.2f/A:%.2f/C:%.2f/N:%.2f/O:%.2f"
                " rate=%.2f win/s",
                global_window_idx,
                shard.name,
                w_idx,
                big5.extraversion,
                big5.agreeableness,
                big5.conscientiousness,
                big5.neuroticism,
                big5.openness,
                rate,
            )
        if args.max_windows is not None and global_window_idx >= args.max_windows:
            break

    if len(big5_list) < 2:
        logger.error(
            "only %d windows administered — ICC requires >=2; aborting", len(big5_list)
        )
        return 3

    icc_result = compute_big5_icc(
        big5_list, seed=args.seed, n_resamples=args.n_resamples, ci=args.ci
    )

    payload: dict[str, Any] = {
        "persona": args.persona,
        "responder_id": responder_id,
        "temperature": args.temperature,
        "window_size": args.window_size,
        "n_windows": len(big5_list),
        "shards": [s.name for s in shards],
        "icc": {
            "icc_consistency_average": icc_result.icc_consistency_average,
            "icc_consistency_single": icc_result.icc_consistency_single,
            "icc_consistency_lower_ci": icc_result.icc_consistency_lower_ci,
            "icc_consistency_upper_ci": icc_result.icc_consistency_upper_ci,
            "me1_fallback_fire": icc_result.me1_fallback_fire,
            "icc_agreement_single": icc_result.icc_agreement_single,
            "icc_agreement_average": icc_result.icc_agreement_average,
            "icc_agreement_lower_ci": icc_result.icc_agreement_lower_ci,
            "icc_agreement_upper_ci": icc_result.icc_agreement_upper_ci,
            "degenerate": icc_result.degenerate,
            "formula_notation": icc_result.formula_notation,
            "n_dimensions": icc_result.n_dimensions,
        },
        "bootstrap": {
            "n_resamples": args.n_resamples,
            "ci": args.ci,
            "method": "hierarchical-cluster-only (column-bootstrap, ME-14)",
        },
        "per_window": [
            {
                "run_id": w.run_id,
                "window_index": w.window_index,
                "big5": {
                    "E": w.big5.extraversion,
                    "A": w.big5.agreeableness,
                    "C": w.big5.conscientiousness,
                    "N": w.big5.neuroticism,
                    "O": w.big5.openness,
                },
                "n_items": w.n_items,
                "diagnostic": {
                    "acquiescence_index": w.acquiescence_index,
                    "straight_line_runs": w.straight_line_runs,
                    "reverse_keyed_agreement": w.reverse_keyed_agreement,
                    "decoy_consistency": w.decoy_consistency,
                },
            }
            for w in administrations
        ],
        "elapsed_s": time.monotonic() - started_at,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "ICC(C,k)=%.4f [%.4f, %.4f] | ICC(A,1)=%.4f [%.4f, %.4f] | n_windows=%d"
        " | me1_fallback_fire=%s | output=%s",
        icc_result.icc_consistency_average,
        icc_result.icc_consistency_lower_ci,
        icc_result.icc_consistency_upper_ci,
        icc_result.icc_agreement_single,
        icc_result.icc_agreement_lower_ci,
        icc_result.icc_agreement_upper_ci,
        len(big5_list),
        icc_result.me1_fallback_fire,
        args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
