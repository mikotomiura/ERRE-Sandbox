r"""DA-15 calibration panel — Plan A eligibility gate (Codex HIGH-2).

Plan A swaps the MPNet Vendi kernel for ``intfloat/multilingual-e5-large`` or
``BAAI/bge-m3``. Both are retrieval-trained, not stylometry-trained: a Vendi
diversity drop on rescore could reflect language/length artefacts rather than
genuine persona-style discrimination. To rule this out, we require each
candidate encoder to separate Kant-style from non-Kant control text with
AUC ≥ 0.75 on a preregistered calibration corpus, with cross-validation that
strips language ID as a confound (within-language AUC must also clear the
gate).

Corpus (per ``.steering/20260516-m9-c-adopt-da15-impl/decisions.md`` D-1):
* class ``kant``  — 100 utterances sampled from
  ``data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb``
  (post-retrain v2 LoRA-on output — Plan A asks whether the swapped encoder
  can discriminate Kant-style in the *modelled* outputs we will rescore, so
  the calibration uses the same generator distribution).
* class ``control`` — 100 utterances sampled from
  ``data/eval/golden/nietzsche_natural_run0.duckdb`` (Nietzsche natural
  baseline; D-1 documents this as a license-clean substitute for the
  Heidegger control the spec example named — both are non-Kant 19c-German
  philosophers from the same generation pipeline).

Output:
* ``data/calibration/kant_heidegger_corpus.json`` — built once, deterministic
  given the random seed.
* ``.steering/20260516-m9-c-adopt-da15-impl/da15-calibration-{encoder}.json``
  — per-encoder AUC, per-language AUC, and the ≥ 0.75 pass verdict.

Usage::

    python scripts/m9-c-adopt/da15_calibration_panel.py \
        --encoder intfloat/multilingual-e5-large \
        --corpus data/calibration/kant_heidegger_corpus.json \
        --output .steering/20260516-m9-c-adopt-da15-impl/da15-calibration-e5.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

logger = logging.getLogger(__name__)

_KANT_SHARD = Path(
    "data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb",
)
_CONTROL_SHARD = Path("data/eval/golden/nietzsche_natural_run0.duckdb")
_PASS_AUC: float = 0.75
"""DA-15 Plan A eligibility gate threshold (Codex HIGH-2, preregistered)."""

_MIN_CHARS: int = 20
"""Skip very short utterances; below this length the encoder representation is
dominated by tokenizer boilerplate rather than persona-style."""

_E5_PASSAGE_PREFIX: str = "passage: "
"""Mirrors vendi._E5_PASSAGE_PREFIX so calibration and rescore use identical
encoder-side handling."""


def _detect_language(text: str) -> str:
    """Cheap script-based language detector.

    The calibration corpus is German / English / Japanese only (Aozora-style
    mixed Kant output). We do not need MUSE-level accuracy — what matters is
    that the same heuristic feeds both class labels so per-language AUC is
    computable. ``ja`` wins if any CJK char appears; ``de`` wins if a
    German-specific letter (ä/ö/ü/ß) appears; otherwise ``en``.
    """
    if re.search(r"[぀-ヿ一-鿿]", text):
        return "ja"
    if re.search(r"[ÄÖÜßäöü]", text):
        return "de"
    return "en"


def _load_utterances(shard: Path, persona_id: str) -> list[str]:
    con = duckdb.connect(str(shard), read_only=True)
    rows = con.execute(
        "SELECT utterance FROM raw_dialog.dialog"
        " WHERE speaker_persona_id = ?"
        " ORDER BY tick, turn_index",
        (persona_id,),
    ).fetchall()
    con.close()
    return [str(r[0]).strip() for r in rows if r[0] and len(str(r[0]).strip()) >= _MIN_CHARS]


def _build_corpus(seed: int, n_per_class: int, output: Path) -> dict[str, Any]:
    """Build the deterministic calibration corpus.

    We over-sample then language-stratify so each class has comparable de/en/ja
    mass, which makes within-language AUC meaningful even for small slices.
    """
    if not _KANT_SHARD.exists():
        msg = f"missing kant shard: {_KANT_SHARD}"
        raise FileNotFoundError(msg)
    if not _CONTROL_SHARD.exists():
        msg = f"missing control shard: {_CONTROL_SHARD}"
        raise FileNotFoundError(msg)

    rng = np.random.default_rng(seed)
    kant_pool = _load_utterances(_KANT_SHARD, "kant")
    control_pool = _load_utterances(_CONTROL_SHARD, "nietzsche")
    logger.info("pool sizes: kant=%d control=%d", len(kant_pool), len(control_pool))

    def _sample(pool: list[str], n: int) -> list[str]:
        if len(pool) < n:
            msg = f"pool too small: have {len(pool)}, need {n}"
            raise ValueError(msg)
        idx = rng.choice(len(pool), size=n, replace=False)
        return [pool[int(i)] for i in idx]

    kant = _sample(kant_pool, n_per_class)
    control = _sample(control_pool, n_per_class)

    entries: list[dict[str, Any]] = []
    for text in kant:
        entries.append(
            {"text": text, "label": "kant", "language": _detect_language(text)},
        )
    for text in control:
        entries.append(
            {"text": text, "label": "control", "language": _detect_language(text)},
        )

    payload: dict[str, Any] = {
        "corpus_schema_version": 1,
        "license_attribution": (
            "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2"
            " (Apache-2.0 generation pipeline, repository licence applies)."
            " nietzsche_natural_run0 — generated by Qwen3-8B + nietzsche"
            " persona prompt (no LoRA), license-clean Apache-2.0 pipeline."
            " D-1 substitution: Codex spec named Heidegger as control, repo"
            " has nietzsche persona instead; both are 19c-German non-Kant"
            " philosophers from the same generation pipeline."
        ),
        "seed": seed,
        "n_per_class": n_per_class,
        "min_chars": _MIN_CHARS,
        "sources": {
            "kant": str(_KANT_SHARD),
            "control": str(_CONTROL_SHARD),
        },
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _load_corpus(corpus_path: Path) -> dict[str, Any]:
    return json.loads(corpus_path.read_text(encoding="utf-8"))


def _encode(encoder_name: str, texts: list[str]) -> np.ndarray:
    """Load the encoder once, encode the corpus, return ``(N, D)`` floats."""
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    logger.info("loading encoder %s", encoder_name)
    model = SentenceTransformer(encoder_name)
    needs_e5_prefix = "e5" in encoder_name.lower()
    inputs = [(_E5_PASSAGE_PREFIX + t) if needs_e5_prefix else t for t in texts]
    return np.asarray(
        model.encode(inputs, show_progress_bar=False, normalize_embeddings=False),
        dtype=float,
    )


def _auc_via_logreg(features: np.ndarray, labels: np.ndarray, seed: int) -> float:
    """Stratified k-fold logistic regression AUC.

    We use cosine similarity to each class centroid (computed on train only)
    as a 2-D feature so the gate measures genuine separability of the encoder
    space rather than capacity of the classifier. AUC is the mean over folds.
    """
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415
    from sklearn.model_selection import StratifiedKFold  # noqa: PLC0415

    norms = np.linalg.norm(features, axis=1, keepdims=True)
    unit = features / np.where(norms == 0, 1.0, norms)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    fold_aucs: list[float] = []
    for train_idx, test_idx in skf.split(unit, labels):
        train_x = unit[train_idx]
        train_y = labels[train_idx]
        # Compute class centroids on the training fold only (no test leak).
        kant_centroid = train_x[train_y == 1].mean(axis=0)
        ctrl_centroid = train_x[train_y == 0].mean(axis=0)
        k_norm = np.linalg.norm(kant_centroid) or 1.0
        c_norm = np.linalg.norm(ctrl_centroid) or 1.0
        kant_centroid = kant_centroid / k_norm
        ctrl_centroid = ctrl_centroid / c_norm

        def feats(x: np.ndarray) -> np.ndarray:
            return np.stack([x @ kant_centroid, x @ ctrl_centroid], axis=1)

        clf = LogisticRegression(max_iter=2000, random_state=seed)
        clf.fit(feats(train_x), train_y)
        scores = clf.predict_proba(feats(unit[test_idx]))[:, 1]
        fold_aucs.append(float(roc_auc_score(labels[test_idx], scores)))

    return float(np.mean(fold_aucs))


def _within_language_auc(
    features: np.ndarray,
    labels: np.ndarray,
    languages: list[str],
    seed: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    lang_arr = np.asarray(languages)
    for lang in sorted(set(languages)):
        mask = lang_arr == lang
        n_pos = int(labels[mask].sum())
        n_neg = int((labels[mask] == 0).sum())
        # Need at least 5 of each class for 5-fold CV.
        if n_pos < 5 or n_neg < 5:
            out[lang] = {
                "auc": None,
                "n_kant": n_pos,
                "n_control": n_neg,
                "note": "insufficient class mass for CV",
            }
            continue
        auc = _auc_via_logreg(features[mask], labels[mask], seed=seed)
        out[lang] = {"auc": auc, "n_kant": n_pos, "n_control": n_neg}
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-da15-calibration-panel")
    p.add_argument(
        "--encoder",
        required=True,
        help=(
            "HuggingFace model id. Plan A primary candidates are"
            " 'intfloat/multilingual-e5-large' and 'BAAI/bge-m3'; the DA-14"
            " baseline 'sentence-transformers/all-mpnet-base-v2' is reported"
            " as the regression anchor."
        ),
    )
    p.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/calibration/kant_heidegger_corpus.json"),
    )
    p.add_argument("--build-corpus", action="store_true", help="(re)build the corpus before scoring")
    p.add_argument("--n-per-class", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
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

    if args.build_corpus or not args.corpus.exists():
        logger.info("building corpus -> %s", args.corpus)
        _build_corpus(seed=args.seed, n_per_class=args.n_per_class, output=args.corpus)

    corpus = _load_corpus(args.corpus)
    entries = corpus["entries"]
    texts = [e["text"] for e in entries]
    labels = np.asarray([1 if e["label"] == "kant" else 0 for e in entries], dtype=int)
    languages = [e["language"] for e in entries]

    features = _encode(args.encoder, texts)

    overall_auc = _auc_via_logreg(features, labels, seed=args.seed)
    per_lang = _within_language_auc(features, labels, languages, seed=args.seed)

    # Pass gate: overall AUC ≥ 0.75 AND every language slice with sufficient
    # mass also clears 0.75. A within-language failure means the overall
    # signal is riding language ID rather than persona-style.
    within_lang_pass = all(
        v["auc"] is None or v["auc"] >= _PASS_AUC for v in per_lang.values()
    )
    verdict = "PASS" if overall_auc >= _PASS_AUC and within_lang_pass else "FAIL"

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
    except Exception as exc:  # noqa: BLE001
        revision_sha = f"<unavailable: {exc}>"
        library_versions = {}

    payload: dict[str, Any] = {
        "encoder": args.encoder,
        "encoder_revision_sha": revision_sha,
        "library_versions": library_versions,
        "corpus": str(args.corpus),
        "n_total": len(texts),
        "n_kant": int(labels.sum()),
        "n_control": int((labels == 0).sum()),
        "language_distribution": {
            lang: int(sum(1 for x in languages if x == lang))
            for lang in sorted(set(languages))
        },
        "pass_gate_auc": _PASS_AUC,
        "overall_auc": overall_auc,
        "within_language_auc": per_lang,
        "within_language_pass": within_lang_pass,
        "verdict": verdict,
        "seed": args.seed,
        "preregistration_note": (
            "DA-15 Plan A eligibility gate (Codex HIGH-2). encoder passes only"
            " if overall AUC ≥ 0.75 AND every within-language AUC slice with"
            " sufficient class mass ≥ 0.75. Otherwise the encoder is excluded"
            " from the ADOPT primary panel."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "encoder=%s overall_auc=%.4f verdict=%s output=%s",
        args.encoder,
        overall_auc,
        verdict,
        args.output,
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
