r"""DA-15 Plan A rescore — apples-to-apples Vendi under a swapped encoder.

Reads the v2 LoRA-on and no-LoRA SGLang baseline shards used by DA-14,
encodes them once with the requested HuggingFace model, then recomputes
Vendi semantic per window via index-based bootstrap (so embeddings are
computed only once per condition, not once per bootstrap iteration). Reports
Cohen's d (v2 − no-LoRA) along with the Codex HIGH-2 eligibility-gate
variants:

* **standard bootstrap**: resample the 6 natural windows per condition with
  replacement, recompute d each iteration.
* **language-quota-balanced bootstrap**: for each iteration, draw a mixed
  100-utterance window with per-stratum quotas (de / en, ja excluded
  because Kant generation yields ≪100 ja utterances per condition), then
  compute one Vendi score over that mixed kernel. Equal de/en quota
  prevents language ID from dominating the resampled window even though
  the kernel still includes cross-language cosine pairs. (Codex MEDIUM-2:
  this is quota-balanced mixed-window bootstrap, not the stricter
  per-language pure-window method — kept here because the resulting d
  failed either way for the kant pool.)
* **token-length-quota-balanced bootstrap**: same quota-balanced mixed-
  window mechanism, stratified by the four length quartiles of the merged
  utterance pool.
* **within-language d** (d_de, d_en, d_ja): bootstrap d using only the
  utterances of a single language. Slices below the minimum window mass
  report ``null``.

DA-14 thresholds are unchanged. The new metric is
``vendi_semantic_v2_encoder_swap``; MPNet ``vendi_semantic`` is reported
alongside as the regression baseline.

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

from erre_sandbox.evidence.tier_b.vendi import _vendi_score_from_kernel

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
_BALANCED_BOOTSTRAP: int = 500
"""Balanced bootstrap is slower (kernel construction per sample) but still
fast once embeddings are pre-computed. 500 iterations is enough for a
stable 95% CI without exhausting RAM on a CPU box."""

_E5_PASSAGE_PREFIX: str = "passage: "
_D2_ALLOWLIST_PATH = Path(
    ".steering/20260516-m9-c-adopt-da15-impl/d2-encoder-allowlist.json",
)
"""Default D-2 allowlist (Plan A). Plan B verdict passes
``--allowlist-path .steering/20260517-m9-c-adopt-plan-b-design/
d2-encoder-allowlist-plan-b.json`` to opt-in to the 4-encoder
agreement panel."""

_LEXICAL_5GRAM_ENCODER_KEY: str = "lexical_5gram"
"""Sentinel encoder name for the lexical-5gram (TF-IDF char-5-gram cosine)
kernel. Matches the D-2 allowlist (Plan B) key and bypasses the
SentenceTransformer code path."""


def _load_allowlist(path: Path = _D2_ALLOWLIST_PATH) -> dict[str, Any]:
    """Load the D-2 pre-registration allowlist (Codex HIGH-1 enforcement).

    Calibration and rescore scripts refuse to run on encoders that are not
    in the allowlist, and they pass the pinned revision SHA to
    ``SentenceTransformer`` so the run cannot accidentally pick up a
    different snapshot from the local cache.
    """
    if not path.exists():
        msg = f"D-2 allowlist missing: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def _local_revision_sha(encoder_name: str) -> str | None:
    """Read the locally-cached HF snapshot SHA. Works offline."""
    safe = encoder_name.replace("/", "--")
    base = (
        Path.home() / ".cache" / "huggingface" / "hub" / f"models--{safe}" / "snapshots"
    )
    if not base.exists():
        return None
    snapshots = list(base.iterdir())
    if not snapshots:
        return None
    return sorted(snapshots, key=lambda p: p.stat().st_mtime)[-1].name


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


def _encode_pool(
    encoder_name: str,
    revision: str,
    texts: list[str],
) -> np.ndarray:
    """Encode every utterance once and return unit-norm row embeddings.

    ``revision`` is the pinned HF commit SHA from the D-2 allowlist; it is
    passed through to ``SentenceTransformer`` so the run is locked to a
    specific snapshot.
    """
    from sentence_transformers import (  # noqa: PLC0415
        SentenceTransformer,
    )

    logger.info("loading encoder %s @ revision %s", encoder_name, revision)
    model = SentenceTransformer(encoder_name, revision=revision)
    needs_e5_prefix = "e5" in encoder_name.lower()
    inputs = [(_E5_PASSAGE_PREFIX + t) if needs_e5_prefix else t for t in texts]
    logger.info("encoding %d utterances…", len(inputs))
    raw = np.asarray(
        model.encode(inputs, show_progress_bar=False),
        dtype=float,
    )
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / np.where(norms == 0, 1.0, norms)


def _encode_pools_lexical_5gram(
    v2_texts: list[str],
    nolora_texts: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Pool-fit TF-IDF char 5-gram encoding for the Plan B lexical kernel.

    Returns ``(v2_unit, nolora_unit)`` — both unit-l2-normalized so that
    ``unit @ unit.T`` recovers cosine similarity for the natural / bootstrap
    window scoring path used by the semantic encoders.

    DE-1 design rationale (see ``.steering/20260516-m9-c-adopt-plan-b-eval-
    gen/design.md`` §7): fit ``TfidfVectorizer`` once on the merged pool so
    both conditions share the same IDF basis (apples-to-apples). This
    deviates from ``vendi_lexical_5gram.make_tfidf_5gram_cosine_kernel``'s
    per-window fit, but mirrors the semantic pre-compute-once pattern used
    by ``_encode_pool``: window slices are taken from a single, condition-
    agnostic embedding space rather than re-fit per resample.
    """
    from sklearn.feature_extraction.text import (  # noqa: PLC0415
        TfidfVectorizer,
    )

    n_v2 = len(v2_texts)
    n_nolora = len(nolora_texts)
    cleaned = [str(t) if str(t).strip() else " " for t in (v2_texts + nolora_texts)]
    logger.info(
        "lexical_5gram pool-fit: v2=%d nolora=%d merged=%d",
        n_v2,
        n_nolora,
        len(cleaned),
    )
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(5, 5),
        lowercase=True,
        norm="l2",
        sublinear_tf=False,
    )
    tfidf = vectorizer.fit_transform(cleaned).toarray().astype(float, copy=False)
    # TfidfVectorizer(norm="l2") already l2-normalises rows, but re-clamp
    # numerical drift so cosine via raw matmul is exact on the diagonal.
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    unit = tfidf / np.where(norms == 0, 1.0, norms)
    return unit[:n_v2], unit[n_v2:]


def _vendi_from_unit_embeddings(unit: np.ndarray, indices: np.ndarray) -> float:
    """Pull rows from the pre-normalised embedding matrix and Vendi-score them."""
    slice_ = unit[indices]
    cosine = slice_ @ slice_.T
    np.fill_diagonal(cosine, 1.0)
    score, _ = _vendi_score_from_kernel(cosine)
    return float(score)


def _natural_window_scores(unit: np.ndarray, utt_per_shard: list[int]) -> list[float]:
    """Score each shard's contiguous 100-turn windows, preserving order."""
    out: list[float] = []
    cursor = 0
    for n in utt_per_shard:
        n_full = n // _WINDOW_SIZE
        for i in range(n_full):
            start = cursor + i * _WINDOW_SIZE
            indices = np.arange(start, start + _WINDOW_SIZE)
            out.append(_vendi_from_unit_embeddings(unit, indices))
        cursor += n
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


def _bootstrap_window_diff_ci(
    a: list[float],
    b: list[float],
    *,
    seed: int,
    n_resamples: int,
) -> dict[str, Any]:
    """Window-level bootstrap of the mean difference (a − b).

    Matches the DA-14 instrument exactly (see da14-verdict-v2-kant.json
    ``diff_v2_minus_nolora`` + ``diff_ci_95``): the CI is on ``mean(ra) -
    mean(rb)`` across bootstrap resamples, not on a bootstrap distribution
    of Cohen's d. Cohen's d is reported as a separate point statistic on the
    observed windows so the DA-14 gate (``cohens_d <= -0.5 AND diff_ci_upper
    < 0``) can be applied against the original definitions.
    """
    rng = np.random.default_rng(seed)
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    diffs: list[float] = []
    for _ in range(n_resamples):
        ra = rng.choice(a_arr, size=len(a_arr), replace=True)
        rb = rng.choice(b_arr, size=len(b_arr), replace=True)
        diffs.append(float(np.mean(ra) - np.mean(rb)))
    diffs_sorted = sorted(diffs)
    n = len(diffs_sorted)
    return {
        "diff_point": float(np.mean(a_arr) - np.mean(b_arr)),
        "diff_lo": float(diffs_sorted[int(0.025 * n)]),
        "diff_hi": float(diffs_sorted[int(0.975 * n)]),
        "cohens_d": _cohens_d(a, b),
        "n_resamples": n_resamples,
        "seed": seed,
    }


def _stratified_bootstrap_d(
    *,
    v2_unit: np.ndarray,
    nolora_unit: np.ndarray,
    v2_strata: np.ndarray,
    nolora_strata: np.ndarray,
    eligible_strata: list[str],
    window_size: int,
    n_resamples: int,
    seed: int,
) -> dict[str, Any] | None:
    """Index-level stratified bootstrap on the swapped Vendi metric.

    Each iteration draws ``window_size`` utterance indices per condition,
    sampling ``window_size // len(eligible)`` per stratum so language ID
    cannot dominate. Embeddings are pre-computed, so each iteration is just
    a slice + matmul + eigvalsh — fast enough to do 500 iterations even on
    CPU.
    """
    if not eligible_strata:
        return None
    v2_by: dict[str, np.ndarray] = {
        s: np.where(v2_strata == s)[0] for s in eligible_strata
    }
    nolora_by: dict[str, np.ndarray] = {
        s: np.where(nolora_strata == s)[0] for s in eligible_strata
    }
    eligible = [s for s in eligible_strata if v2_by[s].size and nolora_by[s].size]
    if not eligible:
        return None
    per_quota = max(1, window_size // len(eligible))
    rng = np.random.default_rng(seed)

    v2_scores: list[float] = []
    nolora_scores: list[float] = []
    diffs: list[float] = []
    for _ in range(n_resamples):
        v2_idx_list: list[int] = []
        nolora_idx_list: list[int] = []
        for s in eligible:
            v2_idx_list.extend(
                int(i) for i in rng.choice(v2_by[s], size=per_quota, replace=True)
            )
            nolora_idx_list.extend(
                int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True)
            )
        # Top-up: fill any remainder from a randomly chosen eligible stratum.
        while len(v2_idx_list) < window_size:
            s = eligible[int(rng.integers(0, len(eligible)))]
            v2_idx_list.append(int(rng.choice(v2_by[s])))
        while len(nolora_idx_list) < window_size:
            s = eligible[int(rng.integers(0, len(eligible)))]
            nolora_idx_list.append(int(rng.choice(nolora_by[s])))
        v2_idx = np.asarray(v2_idx_list[:window_size], dtype=int)
        nolora_idx = np.asarray(nolora_idx_list[:window_size], dtype=int)
        v2_score = _vendi_from_unit_embeddings(v2_unit, v2_idx)
        nolora_score = _vendi_from_unit_embeddings(nolora_unit, nolora_idx)
        v2_scores.append(v2_score)
        nolora_scores.append(nolora_score)
        diffs.append(v2_score - nolora_score)

    diffs_sorted = sorted(diffs)
    return {
        "eligible_strata": eligible,
        "per_stratum_quota": per_quota,
        "n_resamples": n_resamples,
        "seed": seed,
        "v2_mean": float(np.mean(v2_scores)),
        "nolora_mean": float(np.mean(nolora_scores)),
        "diff_point": float(np.mean(diffs)),
        "diff_lo": float(diffs_sorted[int(0.025 * len(diffs_sorted))]),
        "diff_hi": float(diffs_sorted[int(0.975 * len(diffs_sorted))]),
        "cohens_d": _cohens_d(v2_scores, nolora_scores),
    }


def _length_quartile(length: int, thresholds: tuple[int, int, int]) -> str:
    if length <= thresholds[0]:
        return "q1"
    if length <= thresholds[1]:
        return "q2"
    if length <= thresholds[2]:
        return "q3"
    return "q4"


def _resolve_encoder_default(args: argparse.Namespace) -> None:
    """Apply post-parse defaulting + kernel_type/encoder cross-validation.

    Split from ``main`` so unit tests can drive the same logic without
    triggering DuckDB shard loading.
    """
    if args.kernel_type == "lexical_5gram":
        if args.encoder is None:
            args.encoder = _LEXICAL_5GRAM_ENCODER_KEY
        elif args.encoder != _LEXICAL_5GRAM_ENCODER_KEY:
            msg = (
                f"--encoder must be {_LEXICAL_5GRAM_ENCODER_KEY!r} (or"
                " omitted) when --kernel-type lexical_5gram; got"
                f" {args.encoder!r}"
            )
            raise SystemExit(msg)
    elif args.encoder is None:
        raise SystemExit(
            "--encoder is required for --kernel-type semantic (Plan A path)",
        )


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915, C901, PLR0912
    p = argparse.ArgumentParser(prog="m9-c-adopt-da15-rescore")
    p.add_argument(
        "--encoder",
        default=None,
        help=(
            "HuggingFace model id. Plan A primary candidates are"
            " 'intfloat/multilingual-e5-large' and 'BAAI/bge-m3'. Pass"
            " 'sentence-transformers/all-mpnet-base-v2' to reproduce the"
            " DA-14 MPNet regression baseline under the same code path."
            " Required for --kernel-type semantic; defaults to"
            f" {_LEXICAL_5GRAM_ENCODER_KEY!r} when --kernel-type"
            " lexical_5gram."
        ),
    )
    p.add_argument("--persona", default="kant", choices=("kant",))
    p.add_argument("--window-size", type=int, default=_WINDOW_SIZE)
    p.add_argument("--n-resamples", type=int, default=_N_BOOTSTRAP)
    p.add_argument(
        "--balanced-n-resamples",
        type=int,
        default=_BALANCED_BOOTSTRAP,
        help=(
            "Balanced + within-language bootstrap iteration count. Each"
            " iteration costs one cosine kernel + eigvalsh per condition; on"
            " CPU 500 iterations is ~5 minutes per encoder."
        ),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
    )
    p.add_argument(
        "--v2-shards",
        nargs="+",
        type=Path,
        default=list(_V2_SHARDS),
        help=(
            "DuckDB shard paths for the LoRA-on (v2 or Plan B) condition."
            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
            " Plan B kant_r8v3 shards to score the Plan B retrain artifact."
        ),
    )
    p.add_argument(
        "--nolora-shards",
        nargs="+",
        type=Path,
        default=list(_NOLORA_SHARDS),
        help=(
            "DuckDB shard paths for the no-LoRA control condition. Defaults"
            " to the existing kant_nolora_run{0,1} SGLang baseline; pass the"
            " Plan B no-LoRA control shards (kant_planb_nolora_run{0,1}) for"
            " Plan B verdict apples-to-apples."
        ),
    )
    p.add_argument(
        "--kernel-type",
        choices=("semantic", "lexical_5gram"),
        default="semantic",
        help=(
            "Vendi kernel family. 'semantic' uses the SentenceTransformer"
            " path (MPNet / E5 / BGE-M3). 'lexical_5gram' uses the Plan B"
            " D-2 primary TF-IDF char-5-gram cosine kernel (pool-fit, see"
            " DE-1 in design.md)."
        ),
    )
    p.add_argument(
        "--allowlist-path",
        type=Path,
        default=_D2_ALLOWLIST_PATH,
        help=(
            "Path to the D-2 allowlist JSON. Default is the Plan A allowlist"
            f" ({_D2_ALLOWLIST_PATH}); pass the Plan B allowlist for the"
            " 4-encoder agreement panel (encoder_agreement_axis)."
        ),
    )
    args = p.parse_args(argv)
    _resolve_encoder_default(args)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    # === Load + concatenate per-condition pools ===
    v2_utterances: list[str] = []
    v2_utt_per_shard: list[int] = []
    for shard in args.v2_shards:
        ut = _load_focal_utterances(shard, args.persona)
        v2_utterances.extend(ut)
        v2_utt_per_shard.append(len(ut))

    nolora_utterances: list[str] = []
    nolora_utt_per_shard: list[int] = []
    for shard in args.nolora_shards:
        ut = _load_focal_utterances(shard, args.persona)
        nolora_utterances.extend(ut)
        nolora_utt_per_shard.append(len(ut))

    logger.info(
        "v2 utterances=%d nolora utterances=%d",
        len(v2_utterances),
        len(nolora_utterances),
    )

    # === D-2 allowlist enforcement (Codex HIGH-1) ===
    allowlist = _load_allowlist(args.allowlist_path)
    if args.encoder not in allowlist["encoders"]:
        msg = (
            f"encoder {args.encoder!r} is not in the D-2 allowlist"
            f" ({sorted(allowlist['encoders'])}). Add the encoder to"
            f" {args.allowlist_path} with a revision SHA and a role before"
            " rerunning."
        )
        raise SystemExit(msg)
    pinned = allowlist["encoders"][args.encoder]
    revision = pinned["revision_sha"]
    role = pinned["role"]
    if args.kernel_type == "semantic":
        local_sha = _local_revision_sha(args.encoder)
        if local_sha and local_sha != revision:
            logger.warning(
                "local cache snapshot %s differs from pinned %s — passing pinned"
                " revision to SentenceTransformer to force the right snapshot",
                local_sha,
                revision,
            )

    # === Encode each pool once (the only expensive call) ===
    if args.kernel_type == "lexical_5gram":
        v2_unit, nolora_unit = _encode_pools_lexical_5gram(
            v2_utterances,
            nolora_utterances,
        )
    else:
        v2_unit = _encode_pool(args.encoder, revision, v2_utterances)
        nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)

    # === Natural per-window scores ===
    v2_window_scores = _natural_window_scores(v2_unit, v2_utt_per_shard)
    nolora_window_scores = _natural_window_scores(nolora_unit, nolora_utt_per_shard)
    logger.info(
        "natural windows: v2=%d nolora=%d",
        len(v2_window_scores),
        len(nolora_window_scores),
    )

    standard = _bootstrap_window_diff_ci(
        v2_window_scores,
        nolora_window_scores,
        seed=args.seed,
        n_resamples=args.n_resamples,
    )

    # === Strata ===
    v2_langs = np.asarray([_detect_language(t) for t in v2_utterances])
    nolora_langs = np.asarray([_detect_language(t) for t in nolora_utterances])
    merged_lengths = sorted(len(t) for t in v2_utterances + nolora_utterances)
    quartile_cuts = (
        merged_lengths[len(merged_lengths) // 4],
        merged_lengths[len(merged_lengths) // 2],
        merged_lengths[3 * len(merged_lengths) // 4],
    )
    v2_quartiles = np.asarray(
        [_length_quartile(len(t), quartile_cuts) for t in v2_utterances],
    )
    nolora_quartiles = np.asarray(
        [_length_quartile(len(t), quartile_cuts) for t in nolora_utterances],
    )

    logger.info("running language-balanced bootstrap…")
    lang_balanced = _stratified_bootstrap_d(
        v2_unit=v2_unit,
        nolora_unit=nolora_unit,
        v2_strata=v2_langs,
        nolora_strata=nolora_langs,
        eligible_strata=["de", "en"],
        window_size=args.window_size,
        n_resamples=args.balanced_n_resamples,
        seed=args.seed,
    )

    logger.info("running length-balanced bootstrap…")
    length_balanced = _stratified_bootstrap_d(
        v2_unit=v2_unit,
        nolora_unit=nolora_unit,
        v2_strata=v2_quartiles,
        nolora_strata=nolora_quartiles,
        eligible_strata=["q1", "q2", "q3", "q4"],
        window_size=args.window_size,
        n_resamples=args.balanced_n_resamples,
        seed=args.seed,
    )

    logger.info("running within-language d…")
    within_lang: dict[str, Any] = {}
    for lang in ("de", "en", "ja"):
        v2_mass = int((v2_langs == lang).sum())
        nolora_mass = int((nolora_langs == lang).sum())
        if v2_mass < args.window_size or nolora_mass < args.window_size:
            within_lang[lang] = {
                "cohens_d": None,
                "n_v2": v2_mass,
                "n_nolora": nolora_mass,
                "note": (
                    "insufficient mass for a single 100-utterance window per"
                    " condition; this is the documented limitation for ja"
                    " (Codex LOW-1 unrelated, but called out in verdict)."
                ),
            }
            continue
        within_lang[lang] = _stratified_bootstrap_d(
            v2_unit=v2_unit,
            nolora_unit=nolora_unit,
            v2_strata=v2_langs,
            nolora_strata=nolora_langs,
            eligible_strata=[lang],
            window_size=args.window_size,
            n_resamples=args.balanced_n_resamples,
            seed=args.seed,
        )

    # === DA-14 threshold check (unchanged) ===
    # DA-14 gate: cohens_d <= -0.5 AND mean-diff CI upper < 0.
    pass_point = standard.get("cohens_d") is not None and standard["cohens_d"] <= -0.5
    pass_ci = standard.get("diff_hi") is not None and standard["diff_hi"] < 0
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

    # === Runtime environment record (pre-registration audit) ===
    # Library versions and the pinned revision come from the D-2 allowlist;
    # we no longer call HfApi at runtime so the script is offline-safe.
    import transformers as _tf  # noqa: PLC0415

    revision_sha = revision
    library_versions: dict[str, str] = {
        "transformers": _tf.__version__,
    }
    if args.kernel_type == "semantic":
        import sentence_transformers as _st  # noqa: PLC0415

        library_versions["sentence_transformers"] = _st.__version__
    else:
        import sklearn as _sk  # noqa: PLC0415

        library_versions["sklearn"] = _sk.__version__
    expected_lib = allowlist.get("library_versions", {})
    # Only enforce overlap (kernel-relevant libs). lexical_5gram skips the
    # sentence_transformers pin since the kernel is computed via sklearn
    # TF-IDF; the allowlist does not pin sklearn yet.
    relevant_keys = set(expected_lib).intersection(library_versions)
    library_versions_match = all(
        library_versions[k] == expected_lib[k] for k in relevant_keys
    )

    if args.kernel_type == "lexical_5gram":
        metric_name = "vendi_lexical_5gram"
    else:
        metric_name = "vendi_semantic_v2_encoder_swap"

    payload: dict[str, Any] = {
        "encoder": args.encoder,
        "encoder_revision_sha": revision_sha,
        "encoder_role": role,
        "kernel_type": args.kernel_type,
        "allowlist_path": str(args.allowlist_path),
        "library_versions": library_versions,
        "library_versions_match_d2": library_versions_match,
        "preregistration_anchor": (
            "DA-15 D-2 / Plan B D-2 allowlist. Encoder + revision SHA +"
            " library versions must match the pinned values for the verdict"
            " to count as ADOPT-eligible. ``encoder_role`` decides whether"
            " this run can contribute to the primary ADOPT panel"
            " (``primary``) or only serves as a regression baseline"
            " (``regression``) / exploratory channel (``exploratory``)."
        ),
        "persona": args.persona,
        "metric": metric_name,
        "window_size": args.window_size,
        "n_resamples": args.n_resamples,
        "balanced_n_resamples": args.balanced_n_resamples,
        "seed": args.seed,
        "v2_shards": [s.name for s in args.v2_shards],
        "nolora_shards": [s.name for s in args.nolora_shards],
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
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
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
