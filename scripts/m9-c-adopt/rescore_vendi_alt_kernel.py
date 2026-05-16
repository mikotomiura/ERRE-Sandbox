r"""DA-15 Plan A rescore — apples-to-apples Vendi under a swapped encoder.

Reads the v2 LoRA-on and no-LoRA SGLang baseline shards used by DA-14, encodes
them with the requested HuggingFace model, recomputes Vendi semantic per
window, and reports Cohen's d (v2 − no-LoRA) along with the Codex HIGH-2
eligibility-gate variants:

* **standard bootstrap**: resample the 6 natural windows per condition with
  replacement, recompute d each iteration.
* **language-balanced bootstrap**: for each iteration, build language-pure
  bootstrap windows of 100 utterances each (de / en), compute d per language,
  weight equally. Japanese is excluded because Kant generation yields ≪100 ja
  utterances per condition, which the verdict file calls out as a documented
  limitation rather than an unreliable estimate.
* **token-length-balanced bootstrap**: identical mechanism but stratified by
  the four length quartiles of the merged utterance pool.
* **within-language d** (d_de, d_en, d_ja): bootstrap d using only the
  utterances of a single language. Slices below the minimum window mass
  report ``null`` with a documented reason.

DA-14 thresholds are unchanged. The new metric name is
``vendi_semantic_v2_encoder_swap``; the MPNet DA-14 instrument
(``vendi_semantic``) is reported alongside as the regression baseline.

Usage::

    python scripts/m9-c-adopt/rescore_vendi_alt_kernel.py \
        --encoder intfloat/multilingual-e5-large \
        --output .steering/20260516-m9-c-adopt-da15-impl/da15-rescore-e5-kant.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import duckdb
import numpy as np

from erre_sandbox.evidence.tier_b.vendi import compute_vendi

logger = logging.getLogger(__name__)

_V2_SHARDS = (
    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb"),
    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb"),
)
_NOLORA_SHARDS = (
    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run0_stim.duckdb"),
    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run1_stim.duckdb"),
)
_WINDOW_SIZE: int = 100
_N_BOOTSTRAP: int = 2000
_E5_PASSAGE_PREFIX: str = "passage: "


def _detect_language(text: str) -> str:
    if re.search(r"[぀-ヿ一-鿿]", text):
        return "ja"
    if re.search(r"[ÄÖÜßäöü]", text):
        return "de"
    return "en"


def _load_focal_utterances(shard: Path, persona_id: str) -> list[str]:
    con = duckdb.connect(str(shard), read_only=True)
    rows = con.execute(
        "SELECT utterance FROM raw_dialog.dialog"
        " WHERE speaker_persona_id = ?"
        " ORDER BY tick, turn_index",
        (persona_id,),
    ).fetchall()
    con.close()
    return [str(r[0]).strip() for r in rows if r[0]]


def _build_encoder_kernel(encoder_name: str) -> Any:
    """Return a Vendi kernel callable for the requested encoder.

    We cache the SentenceTransformer instance in a closure so all windows of
    a condition reuse the same loaded model (loading multilingual-e5-large
    twice doubles the wall time without changing the embeddings).
    """
    from sentence_transformers import (  # noqa: PLC0415
        SentenceTransformer,
    )

    logger.info("loading encoder %s", encoder_name)
    model = SentenceTransformer(encoder_name)
    needs_e5_prefix = "e5" in encoder_name.lower()

    def kernel(items):
        inputs = [(_E5_PASSAGE_PREFIX + t) if needs_e5_prefix else t for t in items]
        encoded = model.encode(inputs, show_progress_bar=False)
        arr = np.asarray(encoded, dtype=float)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        unit = arr / np.where(norms == 0, 1.0, norms)
        cosine = unit @ unit.T
        np.fill_diagonal(cosine, 1.0)
        return cosine

    return kernel


def _window_scores(
    utterances: list[str],
    *,
    kernel,
    window_size: int,
) -> list[float]:
    n_full = len(utterances) // window_size
    out: list[float] = []
    for i in range(n_full):
        window = utterances[i * window_size : (i + 1) * window_size]
        result = compute_vendi(window, kernel=kernel, kernel_name="semantic_v2_encoder_swap")
        out.append(result.score)
    return out


def _cohens_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    ma, mb = mean(a), mean(b)
    sa, sb = stdev(a), stdev(b)
    na, nb = len(a), len(b)
    pooled_var = ((na - 1) * sa * sa + (nb - 1) * sb * sb) / max(na + nb - 2, 1)
    pooled_sd = math.sqrt(max(pooled_var, 1e-30))
    return (ma - mb) / pooled_sd


def _bootstrap_d_ci(
    a: list[float],
    b: list[float],
    *,
    seed: int,
    n_resamples: int,
) -> dict[str, float]:
    """Window-level bootstrap CI on cohens_d (a − b)."""
    rng = np.random.default_rng(seed)
    ds: list[float] = []
    for _ in range(n_resamples):
        ra = rng.choice(a, size=len(a), replace=True).tolist()
        rb = rng.choice(b, size=len(b), replace=True).tolist()
        ds.append(_cohens_d(ra, rb))
    ds_sorted = sorted(x for x in ds if not math.isnan(x))
    if not ds_sorted:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan")}
    n = len(ds_sorted)
    lo = ds_sorted[int(0.025 * n)]
    hi = ds_sorted[int(0.975 * n)]
    return {
        "point": _cohens_d(a, b),
        "lo": float(lo),
        "hi": float(hi),
        "n_resamples": n_resamples,
        "seed": seed,
    }


def _stratified_window_d(
    *,
    v2_pool: list[str],
    nolora_pool: list[str],
    v2_strata: list[str],
    nolora_strata: list[str],
    kernel,
    window_size: int,
    n_resamples: int,
    seed: int,
    strata_filter: list[str] | None = None,
) -> dict[str, Any] | None:
    """Stratified bootstrap: each iteration draws a window of ``window_size``
    utterances per condition, sampling equally from each stratum after
    filtering. Returns bootstrap CI on cohens_d across iterations.

    ``strata_filter`` keeps only the named strata; ``None`` keeps all.
    """
    rng = np.random.default_rng(seed)

    strata = sorted(set(v2_strata) | set(nolora_strata))
    if strata_filter is not None:
        strata = [s for s in strata if s in strata_filter]
    if not strata:
        return None

    v2_by: dict[str, list[str]] = {s: [] for s in strata}
    for text, s in zip(v2_pool, v2_strata, strict=True):
        if s in v2_by:
            v2_by[s].append(text)
    nolora_by: dict[str, list[str]] = {s: [] for s in strata}
    for text, s in zip(nolora_pool, nolora_strata, strict=True):
        if s in nolora_by:
            nolora_by[s].append(text)

    # Ensure every stratum has at least one utterance per condition; drop
    # strata that don't qualify so we never sample from an empty pool.
    eligible = [s for s in strata if v2_by[s] and nolora_by[s]]
    if not eligible:
        return None
    per_stratum_quota = max(1, window_size // len(eligible))

    diffs: list[float] = []
    v2_scores_iter: list[float] = []
    nolora_scores_iter: list[float] = []
    for _ in range(n_resamples):
        v2_window: list[str] = []
        nolora_window: list[str] = []
        for s in eligible:
            v2_pool_s = v2_by[s]
            nolora_pool_s = nolora_by[s]
            v2_idx = rng.integers(0, len(v2_pool_s), size=per_stratum_quota)
            nolora_idx = rng.integers(0, len(nolora_pool_s), size=per_stratum_quota)
            v2_window.extend(v2_pool_s[int(i)] for i in v2_idx)
            nolora_window.extend(nolora_pool_s[int(i)] for i in nolora_idx)

        # Top up to the requested window size by sampling uniformly across
        # eligible strata. This handles the case where window_size //
        # len(eligible) leaves a remainder.
        while len(v2_window) < window_size:
            s = eligible[rng.integers(0, len(eligible))]
            v2_window.append(v2_by[s][int(rng.integers(0, len(v2_by[s])))])
        while len(nolora_window) < window_size:
            s = eligible[rng.integers(0, len(eligible))]
            nolora_window.append(nolora_by[s][int(rng.integers(0, len(nolora_by[s])))])
        v2_window = v2_window[:window_size]
        nolora_window = nolora_window[:window_size]

        v2_score = compute_vendi(
            v2_window, kernel=kernel, kernel_name="semantic_v2_encoder_swap",
        ).score
        nolora_score = compute_vendi(
            nolora_window, kernel=kernel, kernel_name="semantic_v2_encoder_swap",
        ).score
        v2_scores_iter.append(v2_score)
        nolora_scores_iter.append(nolora_score)
        diffs.append(v2_score - nolora_score)

    point_d = _cohens_d(v2_scores_iter, nolora_scores_iter)
    diffs_sorted = sorted(diffs)
    lo = diffs_sorted[int(0.025 * len(diffs_sorted))]
    hi = diffs_sorted[int(0.975 * len(diffs_sorted))]
    return {
        "eligible_strata": eligible,
        "per_stratum_quota": per_stratum_quota,
        "n_resamples": n_resamples,
        "seed": seed,
        "v2_mean": float(np.mean(v2_scores_iter)),
        "nolora_mean": float(np.mean(nolora_scores_iter)),
        "diff_point": float(np.mean(diffs)),
        "diff_lo": float(lo),
        "diff_hi": float(hi),
        "cohens_d": float(point_d),
    }


def _length_quartile(length: int, thresholds: tuple[int, int, int]) -> str:
    if length <= thresholds[0]:
        return "q1"
    if length <= thresholds[1]:
        return "q2"
    if length <= thresholds[2]:
        return "q3"
    return "q4"


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
    p = argparse.ArgumentParser(prog="m9-c-adopt-da15-rescore")
    p.add_argument(
        "--encoder",
        required=True,
        help=(
            "HuggingFace model id. Plan A primary candidates are"
            " 'intfloat/multilingual-e5-large' and 'BAAI/bge-m3'. Pass"
            " 'sentence-transformers/all-mpnet-base-v2' to reproduce the"
            " DA-14 MPNet regression baseline under the same code path."
        ),
    )
    p.add_argument("--persona", default="kant", choices=("kant",))
    p.add_argument("--window-size", type=int, default=_WINDOW_SIZE)
    p.add_argument("--n-resamples", type=int, default=_N_BOOTSTRAP)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--log-level", default="info", choices=("debug", "info", "warning", "error"),
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    v2_utterances: list[str] = []
    nolora_utterances: list[str] = []
    v2_window_runs: list[tuple[str, int]] = []  # (run_id, window_index)
    for shard in _V2_SHARDS:
        ut = _load_focal_utterances(shard, args.persona)
        v2_utterances.extend(ut)
        for i in range(len(ut) // args.window_size):
            v2_window_runs.append((shard.stem, i))
    nolora_window_runs: list[tuple[str, int]] = []
    for shard in _NOLORA_SHARDS:
        ut = _load_focal_utterances(shard, args.persona)
        nolora_utterances.extend(ut)
        for i in range(len(ut) // args.window_size):
            nolora_window_runs.append((shard.stem, i))

    logger.info("v2 utterances=%d nolora utterances=%d", len(v2_utterances), len(nolora_utterances))

    kernel = _build_encoder_kernel(args.encoder)

    # === Standard per-window scoring ===
    logger.info("scoring natural windows…")
    v2_window_scores: list[float] = []
    nolora_window_scores: list[float] = []
    # Score each shard's windows separately so we don't bleed across shards.
    cursor = 0
    for shard in _V2_SHARDS:
        ut = _load_focal_utterances(shard, args.persona)
        v2_window_scores.extend(
            _window_scores(ut, kernel=kernel, window_size=args.window_size),
        )
        cursor += len(ut)
    cursor = 0
    for shard in _NOLORA_SHARDS:
        ut = _load_focal_utterances(shard, args.persona)
        nolora_window_scores.extend(
            _window_scores(ut, kernel=kernel, window_size=args.window_size),
        )
        cursor += len(ut)
    logger.info(
        "natural windows: v2=%d nolora=%d", len(v2_window_scores), len(nolora_window_scores),
    )

    standard = _bootstrap_d_ci(
        v2_window_scores, nolora_window_scores,
        seed=args.seed, n_resamples=args.n_resamples,
    )

    # === Strata for balanced bootstrap ===
    v2_langs = [_detect_language(t) for t in v2_utterances]
    nolora_langs = [_detect_language(t) for t in nolora_utterances]
    merged_lengths = sorted(len(t) for t in v2_utterances + nolora_utterances)
    quartile_cuts = (
        merged_lengths[len(merged_lengths) // 4],
        merged_lengths[len(merged_lengths) // 2],
        merged_lengths[3 * len(merged_lengths) // 4],
    )
    v2_quartiles = [_length_quartile(len(t), quartile_cuts) for t in v2_utterances]
    nolora_quartiles = [_length_quartile(len(t), quartile_cuts) for t in nolora_utterances]

    logger.info("running language-balanced bootstrap…")
    lang_balanced = _stratified_window_d(
        v2_pool=v2_utterances,
        nolora_pool=nolora_utterances,
        v2_strata=v2_langs,
        nolora_strata=nolora_langs,
        kernel=kernel,
        window_size=args.window_size,
        n_resamples=min(args.n_resamples, 200),  # stratified is ~30x slower; cap
        seed=args.seed,
        strata_filter=["de", "en"],  # ja excluded — insufficient mass
    )

    logger.info("running length-balanced bootstrap…")
    length_balanced = _stratified_window_d(
        v2_pool=v2_utterances,
        nolora_pool=nolora_utterances,
        v2_strata=v2_quartiles,
        nolora_strata=nolora_quartiles,
        kernel=kernel,
        window_size=args.window_size,
        n_resamples=min(args.n_resamples, 200),
        seed=args.seed,
    )

    # === Within-language d (de, en, ja) ===
    logger.info("running within-language d…")
    within_lang: dict[str, Any] = {}
    for lang in ("de", "en", "ja"):
        v2_lang = [t for t, l in zip(v2_utterances, v2_langs, strict=True) if l == lang]
        nolora_lang = [t for t, l in zip(nolora_utterances, nolora_langs, strict=True) if l == lang]
        if len(v2_lang) < args.window_size or len(nolora_lang) < args.window_size:
            within_lang[lang] = {
                "auc": None,
                "n_v2": len(v2_lang),
                "n_nolora": len(nolora_lang),
                "note": "insufficient mass for a single 100-utterance window per condition",
            }
            continue
        # Build random language-pure windows via bootstrap (same scheme as
        # stratified, but only one stratum).
        result = _stratified_window_d(
            v2_pool=v2_lang,
            nolora_pool=nolora_lang,
            v2_strata=[lang] * len(v2_lang),
            nolora_strata=[lang] * len(nolora_lang),
            kernel=kernel,
            window_size=args.window_size,
            n_resamples=min(args.n_resamples, 200),
            seed=args.seed,
        )
        within_lang[lang] = result

    # === DA-14 threshold check ===
    pass_point = standard.get("point") is not None and standard["point"] <= -0.5
    pass_ci = standard.get("hi") is not None and standard["hi"] < 0
    balanced_lang_pass = (
        lang_balanced is not None
        and lang_balanced["cohens_d"] <= -0.5
        and lang_balanced["diff_hi"] < 0
    )
    balanced_length_pass = (
        length_balanced is not None
        and length_balanced["cohens_d"] <= -0.5
        and length_balanced["diff_hi"] < 0
    )

    # === Runtime environment record (for pre-registration audit) ===
    try:
        import sentence_transformers as _st  # noqa: PLC0415
        import transformers as _tf  # noqa: PLC0415
        from huggingface_hub import HfApi  # noqa: PLC0415

        revision_sha = HfApi().repo_info(args.encoder).sha
        library_versions = {
            "sentence_transformers": _st.__version__,
            "transformers": _tf.__version__,
        }
    except Exception as exc:  # noqa: BLE001  # best-effort metadata only
        revision_sha = f"<unavailable: {exc}>"
        library_versions = {}

    payload: dict[str, Any] = {
        "encoder": args.encoder,
        "encoder_revision_sha": revision_sha,
        "library_versions": library_versions,
        "preregistration_anchor": (
            "DA-15 D-2 (.steering/20260516-m9-c-adopt-da15-impl/decisions.md)."
            " Encoder + revision SHA + library versions must match the pinned"
            " values for the verdict to count as ADOPT-eligible."
        ),
        "persona": args.persona,
        "metric": "vendi_semantic_v2_encoder_swap",
        "window_size": args.window_size,
        "n_resamples": args.n_resamples,
        "seed": args.seed,
        "v2_shards": [s.name for s in _V2_SHARDS],
        "nolora_shards": [s.name for s in _NOLORA_SHARDS],
        "natural_windows": {
            "v2_scores": v2_window_scores,
            "nolora_scores": nolora_window_scores,
            "v2_mean": float(np.mean(v2_window_scores)),
            "nolora_mean": float(np.mean(nolora_window_scores)),
            "cohens_d": _cohens_d(v2_window_scores, nolora_window_scores),
        },
        "standard_bootstrap": standard,
        "language_balanced_bootstrap": lang_balanced,
        "length_balanced_bootstrap": length_balanced,
        "within_language": within_lang,
        "length_quartile_cuts": list(quartile_cuts),
        "thresholds": {
            "cohens_d_point_le": -0.5,
            "diff_ci_upper_lt": 0.0,
            "note": "DA-14 thresholds, unchanged. Plan A pass requires the gate to clear under both standard and balanced bootstrap.",
        },
        "verdict_per_axis": {
            "standard_pass": pass_point and pass_ci,
            "language_balanced_pass": balanced_lang_pass,
            "length_balanced_pass": balanced_length_pass,
        },
        "preregistration_note": (
            "DA-15 Plan A rescore. encoder + revision pin + transformer +"
            " sentence-transformers versions are recorded in"
            " .steering/20260516-m9-c-adopt-da15-impl/decisions.md D-2."
            " ja within-language d intentionally omitted: Kant generation"
            " produces <20 ja utterances per shard, well below the"
            " 100-utterance Vendi window."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "encoder=%s natural cohens_d=%.4f standard_pass=%s output=%s",
        args.encoder,
        payload["natural_windows"]["cohens_d"],
        payload["verdict_per_axis"]["standard_pass"],
        args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
