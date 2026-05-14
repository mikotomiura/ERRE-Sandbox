"""Burrows Δ consumer — m9-c-adopt Phase B 第 4 セッション (DA-11 closure).

Per-window Burrows Delta against ``kant_de`` reference profile with Option A
language routing (DA-11 第 4 セッション scope):

* Detect each focal utterance language via ``langdetect`` (deterministic with
  ``DetectorFactory.seed=0``).
* Keep only utterances classified as ``de`` with probability ≥
  ``--lang-confidence``. en/ja are dropped as a **named limitation** —
  documented effective sample size disclosure (DA-8 MEDIUM-2 spirit).
* Per-window Δ = mean of per-utterance ``compute_burrows_delta`` against the
  Akademie-Ausgabe Kant German reference (``kant_de``).
* Cluster bootstrap CI (cluster_only=True, ME-14) over per-window means.

DA-1 axis 3 threshold (decisions.md):
* Burrows Δ reduction ≥ 10% point + CI lower > 0

Usage::

    # no-LoRA baseline
    python scripts/m9-c-adopt/compute_burrows_delta.py \\
        --persona kant \\
        --shards-glob "data/eval/golden/kant_stimulus_run*.duckdb" \\
        --window-size 100 \\
        --output .steering/20260513-m9-c-adopt/tier-b-baseline-kant-burrows.json

    # per-rank LoRA-on
    for r in 4 8 16; do
      python scripts/m9-c-adopt/compute_burrows_delta.py \\
        --persona kant \\
        --shards-glob "data/eval/m9-c-adopt-tier-b-pilot/kant_r${r}_run*_stim.duckdb" \\
        --window-size 100 \\
        --output .steering/20260513-m9-c-adopt/tier-b-pilot-kant-r${r}-burrows.json
    done
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Final

import duckdb
from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

from erre_sandbox.evidence.bootstrap_ci import (
    DEFAULT_CI,
    DEFAULT_N_RESAMPLES,
    hierarchical_bootstrap_ci,
)
from erre_sandbox.evidence.reference_corpus.loader import load_reference
from erre_sandbox.evidence.tier_a.burrows import (
    BurrowsLanguageMismatchError,
    BurrowsTokenizationUnsupportedError,
    compute_burrows_delta,
)

logger = logging.getLogger(__name__)

DetectorFactory.seed = 0
"""Deterministic langdetect — required for shard-to-shard reproducibility."""

_DEFAULT_WINDOW_SIZE: Final[int] = 100
_DEFAULT_LANG_CONFIDENCE: Final[float] = 0.85
_DEFAULT_MIN_TOKENS: Final[int] = 5


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
    n = len(utterances)
    full = n // window_size
    return [
        utterances[i * window_size : (i + 1) * window_size] for i in range(full)
    ]


@dataclasses.dataclass
class LangDecision:
    text: str
    language: str | None  # None = drop
    probability: float


def _classify_utterance(
    text: str, *, confidence_threshold: float, min_tokens: int
) -> LangDecision:
    """Route utterance via langdetect; drop short / low-confidence / non-de."""
    if len(text.split()) < min_tokens and not any(ord(c) > 0x3000 for c in text):
        # Below tokens threshold AND not Japanese script → drop
        return LangDecision(text, None, 0.0)
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return LangDecision(text, None, 0.0)
    if not candidates:
        return LangDecision(text, None, 0.0)
    top = candidates[0]
    lang = str(top.lang)
    prob = float(top.prob)
    if prob < confidence_threshold:
        return LangDecision(text, None, prob)
    return LangDecision(text, lang, prob)


@dataclasses.dataclass
class WindowResult:
    run_id: str
    window_index: int
    n_total: int
    n_de: int
    n_en: int
    n_ja: int
    n_other: int
    n_dropped: int
    mean_burrows: float | None
    per_utt_burrows: list[float]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-burrows-delta")
    p.add_argument("--persona", required=True, choices=("kant", "nietzsche", "rikyu"))
    p.add_argument("--shards-glob", required=True)
    p.add_argument("--window-size", type=int, default=_DEFAULT_WINDOW_SIZE)
    p.add_argument(
        "--reference-persona",
        default="kant",
        help="Persona id used to look up the de Burrows reference (default kant).",
    )
    p.add_argument("--reference-language", default="de", choices=("de",))
    p.add_argument(
        "--lang-confidence",
        type=float,
        default=_DEFAULT_LANG_CONFIDENCE,
        help="Drop utterances with langdetect top-1 prob < this threshold.",
    )
    p.add_argument(
        "--min-tokens",
        type=int,
        default=_DEFAULT_MIN_TOKENS,
        help="Skip langdetect on whitespace-token strings shorter than this.",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-resamples", type=int, default=DEFAULT_N_RESAMPLES)
    p.add_argument("--ci", type=float, default=DEFAULT_CI)
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

    reference = load_reference(args.reference_persona, args.reference_language)
    logger.info(
        "loaded reference persona=%s lang=%s |fw|=%d",
        args.reference_persona,
        args.reference_language,
        len(reference.function_words),
    )

    per_cluster_means: list[list[float]] = []
    window_results: list[WindowResult] = []
    n_total_seen = 0
    n_total_de = 0
    n_total_en = 0
    n_total_ja = 0
    n_total_other = 0

    for shard in shards:
        utterances = _load_focal_utterances(shard, args.persona)
        windows = _windowize(utterances, args.window_size)
        cluster_means: list[float] = []
        logger.info(
            "shard=%s focal=%d windows=%d", shard.name, len(utterances), len(windows)
        )
        for w_idx, window in enumerate(windows):
            per_utt: list[float] = []
            counts = {"de": 0, "en": 0, "ja": 0, "other": 0, "dropped": 0}
            for utt in window:
                decision = _classify_utterance(
                    utt,
                    confidence_threshold=args.lang_confidence,
                    min_tokens=args.min_tokens,
                )
                if decision.language is None:
                    counts["dropped"] += 1
                    continue
                if decision.language == "de":
                    counts["de"] += 1
                elif decision.language == "en":
                    counts["en"] += 1
                    continue  # en dropped — no en reference (DA-11 named limitation)
                elif decision.language == "ja":
                    counts["ja"] += 1
                    continue
                else:
                    counts["other"] += 1
                    continue
                try:
                    delta = compute_burrows_delta(
                        decision.text,
                        reference,
                        language="de",
                    )
                except (
                    BurrowsLanguageMismatchError,
                    BurrowsTokenizationUnsupportedError,
                ) as exc:
                    logger.warning(
                        "burrows compute failed shard=%s w=%d: %s",
                        shard.name,
                        w_idx,
                        exc,
                    )
                    continue
                if delta is None or (isinstance(delta, float) and math.isnan(delta)):
                    continue
                per_utt.append(float(delta))

            n_total_seen += len(window)
            n_total_de += counts["de"]
            n_total_en += counts["en"]
            n_total_ja += counts["ja"]
            n_total_other += counts["other"]

            mean = sum(per_utt) / len(per_utt) if per_utt else None
            window_results.append(
                WindowResult(
                    run_id=shard.stem,
                    window_index=w_idx,
                    n_total=len(window),
                    n_de=counts["de"],
                    n_en=counts["en"],
                    n_ja=counts["ja"],
                    n_other=counts["other"],
                    n_dropped=counts["dropped"],
                    mean_burrows=mean,
                    per_utt_burrows=per_utt,
                )
            )
            if mean is not None:
                cluster_means.append(mean)
            logger.info(
                "shard=%s w=%d total=%d de=%d en=%d ja=%d other=%d dropped=%d"
                " mean_burrows=%s",
                shard.name,
                w_idx,
                len(window),
                counts["de"],
                counts["en"],
                counts["ja"],
                counts["other"],
                counts["dropped"],
                f"{mean:.4f}" if mean is not None else "NaN",
            )
        if cluster_means:
            per_cluster_means.append(cluster_means)

    if not per_cluster_means:
        logger.error(
            "no per-window means computed — every utterance was non-de or dropped"
        )
        return 3

    boot = hierarchical_bootstrap_ci(
        per_cluster_means,
        cluster_only=True,
        n_resamples=args.n_resamples,
        ci=args.ci,
        seed=args.seed,
    )

    de_fraction = (
        float(n_total_de) / float(n_total_seen) if n_total_seen > 0 else 0.0
    )

    payload: dict[str, Any] = {
        "persona": args.persona,
        "metric": "burrows_delta_de",
        "reference_persona": args.reference_persona,
        "reference_language": args.reference_language,
        "n_function_words": len(reference.function_words),
        "window_size": args.window_size,
        "n_clusters": len(per_cluster_means),
        "n_windows_with_de": len(window_results),
        "lang_confidence_threshold": args.lang_confidence,
        "min_tokens": args.min_tokens,
        "lang_routing_counts": {
            "total_utterances_seen": n_total_seen,
            "de": n_total_de,
            "en_dropped": n_total_en,
            "ja_dropped": n_total_ja,
            "other_dropped": n_total_other,
            "low_confidence_dropped": (
                n_total_seen - n_total_de - n_total_en - n_total_ja - n_total_other
            ),
            "de_fraction": de_fraction,
        },
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
        "shards": [s.name for s in shards],
        "per_window": [dataclasses.asdict(w) for w in window_results],
        "named_limitation": (
            "Option A language routing (DA-11): en/ja utterances dropped"
            " because there is no Cambridge Edition English Kant reference"
            " (license-pending, M9-eval-system separate PR) and Japanese"
            " Burrows tokenization is deferred (H-2). Effective sample size"
            " is the de_fraction above."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "burrows_de point=%.4f lo=%.4f hi=%.4f width=%.4f n_clusters=%d"
        " de_fraction=%.3f output=%s",
        boot.point,
        boot.lo,
        boot.hi,
        boot.width,
        len(per_cluster_means),
        de_fraction,
        args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
