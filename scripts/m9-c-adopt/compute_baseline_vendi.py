"""Vendi semantic baseline computation — m9-c-adopt Phase B Step 5a (narrowed).

Loads ``data/eval/golden/<persona>_stimulus_run{0..4}.duckdb`` (5 shard,
PR #160 由来 no-LoRA baseline) and computes per-window Vendi semantic score
+ hierarchical bootstrap CI per ME-14 (cluster_only=True).

Big5 ICC + Burrows Δ baseline are deferred (DA-11):
* Big5 ICC: needs LLM-backed PersonaResponder + 50 question × 25 window × 5 run
  (~6,250 inference, ~9h Ollama compute on G-GEAR). Separate consumer in
  Phase B 第 4 セッション.
* Burrows Δ: kant utterances are mixed-language (de/en/ja); Burrows reference
  is German-only. Need either (a) language-detection per utterance with
  per-language reference, or (b) English Kant reference corpus
  (Cambridge Edition, license-audit pending). Deferred to Phase B 第 4 セッション.

Output: JSON aggregate with point + CI + window breakdown.

Usage::

    python scripts/m9-c-adopt/compute_baseline_vendi.py \\
        --persona kant --condition stimulus \\
        --shards-glob "data/eval/golden/kant_stimulus_run*.duckdb" \\
        --output .steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi.json
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import logging
import sys
from pathlib import Path
from typing import Any

import duckdb

from erre_sandbox.evidence.bootstrap_ci import (
    DEFAULT_CI,
    DEFAULT_N_RESAMPLES,
    hierarchical_bootstrap_ci,
)
from erre_sandbox.evidence.tier_b.vendi import (
    compute_vendi,
    make_lexical_5gram_kernel,
)

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_SIZE = 100


def _load_focal_utterances(shard_path: Path, persona_id: str) -> list[str]:
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
    """Slice into non-overlapping windows of size `window_size`. Drops tail."""
    n = len(utterances)
    full = n // window_size
    return [
        utterances[i * window_size : (i + 1) * window_size] for i in range(full)
    ]


@dataclasses.dataclass
class WindowResult:
    run_id: str
    window_index: int
    vendi_score: float
    n: int
    spectrum_entropy: float


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-baseline-vendi")
    p.add_argument("--persona", required=True, choices=("kant", "nietzsche", "rikyu"))
    p.add_argument("--condition", default="stimulus", choices=("stimulus", "natural"))
    p.add_argument("--shards-glob", required=True)
    p.add_argument("--window-size", type=int, default=_DEFAULT_WINDOW_SIZE)
    p.add_argument("--n-resamples", type=int, default=DEFAULT_N_RESAMPLES)
    p.add_argument("--ci", type=float, default=DEFAULT_CI)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--kernel",
        default="semantic",
        choices=("semantic", "lexical-5gram"),
        help=(
            "Vendi kernel. 'semantic' loads MPNet (needs [eval] extras +"
            " ~440MB model download); 'lexical-5gram' is dependency-free."
        ),
    )
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
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
    logger.info("loading %d shards: %s", len(shards), [s.name for s in shards])

    per_cluster_scores: list[list[float]] = []
    window_results: list[WindowResult] = []

    if args.kernel == "lexical-5gram":
        kernel = make_lexical_5gram_kernel()
        kernel_name = "lexical-5gram"
    else:
        kernel = None  # lazy MPNet load inside compute_vendi
        kernel_name = "semantic"

    for shard in shards:
        utterances = _load_focal_utterances(shard, args.persona)
        windows = _windowize(utterances, args.window_size)
        cluster_scores: list[float] = []
        logger.info(
            "shard=%s focal=%d windows=%d", shard.name, len(utterances), len(windows)
        )
        for w_idx, window in enumerate(windows):
            try:
                result = compute_vendi(window, kernel=kernel, kernel_name=kernel_name)
            except Exception:
                logger.exception(
                    "compute_vendi failed shard=%s window=%d", shard.name, w_idx
                )
                continue
            cluster_scores.append(result.score)
            window_results.append(
                WindowResult(
                    run_id=shard.stem,
                    window_index=w_idx,
                    vendi_score=result.score,
                    n=result.n,
                    spectrum_entropy=result.spectrum_entropy,
                )
            )
        if cluster_scores:
            per_cluster_scores.append(cluster_scores)

    if not per_cluster_scores:
        logger.error("no windows computed — aborting")
        return 3

    boot = hierarchical_bootstrap_ci(
        per_cluster_scores,
        cluster_only=True,
        n_resamples=args.n_resamples,
        ci=args.ci,
        seed=args.seed,
    )

    payload: dict[str, Any] = {
        "persona": args.persona,
        "condition": args.condition,
        "metric": f"vendi_{kernel_name.replace('-', '_')}",
        "kernel_name": kernel_name,
        "encoder_model": (
            "sentence-transformers/all-mpnet-base-v2"
            if kernel_name == "semantic"
            else "char-5gram-jaccard"
        ),
        "window_size": args.window_size,
        "n_clusters": len(per_cluster_scores),
        "total_windows": len(window_results),
        "shards": [s.name for s in shards],
        "bootstrap": {
            "method": boot.method,
            "n_resamples": boot.n_resamples,
            "ci": args.ci,
            "point": boot.point,
            "lo": boot.lo,
            "hi": boot.hi,
            "width": boot.width,
            "n": boot.n,
        },
        "per_window": [dataclasses.asdict(w) for w in window_results],
        "scope_narrowing_note": (
            "Per DA-11 (Phase B 第 3 セッション scope narrowing): Vendi only."
            " Big5 ICC consumer + Burrows Δ language handling are deferred"
            " to Phase B 第 4 セッション (separate PR)."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "baseline vendi point=%.4f lo=%.4f hi=%.4f width=%.4f n=%d clusters=%d output=%s",
        boot.point,
        boot.lo,
        boot.hi,
        boot.width,
        boot.n,
        len(per_cluster_scores),
        args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
