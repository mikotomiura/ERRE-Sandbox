"""Per-row metric extraction shared between training and corpus-analysis paths.

This module promotes the per-row feature heuristics previously living inside
``scripts/analysis/analyze_kant_training_corpus.py`` into the production
package so that:

* :func:`erre_sandbox.training.dataset.build_weighted_examples` (training
  kickoff) and the offline analyser (PR #167 corpus-analysis-kant pipeline)
  reach the SAME classification verdict for any given raw_dialog row;
* DR-2 from `.steering/20260514-m9-c-adopt-retrain-v2-design/decisions.md`
  (Codex MEDIUM-1 maintenance-risk flag) is partially resolved — the
  duplicate-mirror risk between training and analysis paths shrinks to
  zero for the four heuristics that actually drive
  :func:`erre_sandbox.training.weighting.compute_example_weight`
  (``language``, ``token_count``, ``has_addressee``, ``marker_density``).

No torch / transformers / DuckDB imports at module load time — these helpers
must remain installable on the CI default profile (no ``[training]`` extras).
The Qwen3-8B tokenizer is loaded lazily inside :func:`estimate_token_count`
and falls back to a whitespace × 1.3 proxy when ``transformers`` is missing.

Public surfaces:

* :data:`GERMAN_FIRST_PERSON_MARKERS`, :data:`KANTIAN_PHILOSOPHY_MARKERS`
  — regex pattern strings (case-insensitive), source-of-truth for
  marker_density computation.
* :data:`LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS` — Cambridge Edition
  translator-aligned Kant target density (2.0 markers per 100 tokens).
* :func:`classify_language` — heuristic de/en/ja/mixed classifier.
* :func:`count_markers` — count regex hits across a list of compiled patterns.
* :func:`estimate_token_count` — Qwen3-8B-preferred token counter with
  whitespace fallback.
* :func:`classify_shard` — ``kant_{natural,stimulus}_run{N}.duckdb`` parser.
* :func:`extract_example_metadata` — convenience row → metadata dict adapter
  used by :func:`build_weighted_examples`.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Marker dictionaries (literature-anchored)
# ---------------------------------------------------------------------------

GERMAN_FIRST_PERSON_MARKERS: Final[tuple[str, ...]] = (
    r"\bich\b",
    r"\bmir\b",
    r"\bmich\b",
    r"\bmein(?:e|er|es|en|em)?\b",
    r"\bmeiner ansicht nach\b",
    r"\bmir scheint\b",
    r"\bm\.e\.\b",
)
"""German first-person / opinion-marker tokens.

Calibrated against Kant's ``Kritik der reinen Vernunft`` (Cambridge Edition
translator-aligned passages used in :func:`build_examples`'s upstream stim
battery). Case-insensitive."""

KANTIAN_PHILOSOPHY_MARKERS: Final[tuple[str, ...]] = (
    r"\bcategorical imperative\b",
    r"\bkategorischer imperativ\b",
    r"\ba priori\b",
    r"\ba posteriori\b",
    r"\bsynthetic\b",
    r"\bsynthetisch\b",
    r"\btranscendental\b",
    r"\btranszendental\b",
    r"\bin itself\b",
    r"\ban sich\b",
    r"\bnoumen\w*\b",
    r"\bphenomen\w*\b",
    r"\bduty\b",
    r"\bpflicht\b",
)
"""Kant-philosophy lexicon markers (English + German).

Anchored on Kantian secondary literature (Stanford Encyclopedia entries
for Kant's epistemology + ethics, Korsgaard 1996, Allison 2004). Higher
density indicates the corpus exposes the LoRA to persona-discriminative
philosophical content rather than generic conversational text."""

LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS: Final[float] = 2.0
"""Empirical density target for **combined** self-ref + Kant markers per
100 tokens, derived from Cambridge Edition translator-aligned Kant
passages. Falsifiable claim format: ``observed_density / anchor`` ratio."""


GERMAN_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(p, re.IGNORECASE) for p in GERMAN_FIRST_PERSON_MARKERS
]
KANTIAN_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(p, re.IGNORECASE) for p in KANTIAN_PHILOSOPHY_MARKERS
]


def count_markers(text: str, patterns: list[re.Pattern[str]]) -> int:
    """Count total regex matches across ``patterns`` in ``text`` (case-insensitive)."""
    return sum(len(p.findall(text)) for p in patterns)


# ---------------------------------------------------------------------------
# Language classifier
# ---------------------------------------------------------------------------

_CJK_RATIO_THRESHOLD: Final[float] = 0.05
"""CJK characters / total chars ratio above which utterance is classified ``ja``."""

_GERMAN_DIACRITIC_MIN: Final[int] = 2
_GERMAN_FUNCTION_WORD_MIN_FOR_DE: Final[int] = 3
_GERMAN_FUNCTION_WORD_AMBIGUOUS: Final[int] = 2
SHORT_UTTERANCE_TOKEN_CAP: Final[int] = 30
"""Utterances with strictly fewer tokens than this are flagged as short
in the corpus-side ``short_utterance_ratio`` aggregate."""


_KANA_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
)
_KANJI_RANGE: Final[tuple[int, int]] = (0x4E00, 0x9FFF)
_GERMAN_DIACRITICS: Final[frozenset[str]] = frozenset("äöüßÄÖÜ")
_GERMAN_FUNCTION_WORDS: Final[frozenset[str]] = frozenset(
    {
        "der",
        "die",
        "das",
        "und",
        "ist",
        "nicht",
        "ein",
        "eine",
        "einen",
        "auch",
        "auf",
        "aus",
        "bei",
        "dem",
        "den",
        "des",
        "im",
        "mit",
        "nur",
        "sich",
        "sind",
        "über",
        "von",
        "war",
        "werden",
        "wir",
        "zu",
        "zur",
        "zum",
        "ich",
        "du",
        "er",
        "sie",
        "es",
        "wenn",
        "wie",
        "was",
        "so",
        "nach",
        "vor",
        "noch",
    },
)
"""Closed-class German function-word set for language classification.

Augments :data:`_GERMAN_DIACRITICS` so an utterance like
``"Ich denke also bin ich"`` (no umlauts but heavy on German closed-class
words) still classifies as ``de``."""


class _LangBuckets:
    __slots__ = ("german_diacritics", "kana", "kanji", "latin_alpha", "total")

    def __init__(
        self,
        *,
        total: int,
        kana: int,
        kanji: int,
        german_diacritics: int,
        latin_alpha: int,
    ) -> None:
        self.total = total
        self.kana = kana
        self.kanji = kanji
        self.german_diacritics = german_diacritics
        self.latin_alpha = latin_alpha


def _count_lang_buckets(text: str) -> _LangBuckets:
    kana = 0
    kanji = 0
    german_diacritics = 0
    latin_alpha = 0
    for char in text:
        cp = ord(char)
        if any(lo <= cp <= hi for lo, hi in _KANA_RANGES):
            kana += 1
        elif _KANJI_RANGE[0] <= cp <= _KANJI_RANGE[1]:
            kanji += 1
        elif char in _GERMAN_DIACRITICS:
            german_diacritics += 1
        elif char.isalpha() and char.isascii():
            latin_alpha += 1
    return _LangBuckets(
        total=len(text),
        kana=kana,
        kanji=kanji,
        german_diacritics=german_diacritics,
        latin_alpha=latin_alpha,
    )


def _count_german_function_words(text: str) -> int:
    return sum(
        1
        for tok in re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
        if tok.lower() in _GERMAN_FUNCTION_WORDS
    )


def classify_language(text: str) -> str:  # noqa: PLR0911  # decision tree with early returns
    """Heuristic language classifier for an utterance.

    Decision order:

    1. Empty / no-alphabetic / no-CJK text → ``mixed``.
    2. CJK ratio ≥ :data:`_CJK_RATIO_THRESHOLD` → ``ja``.
    3. German diacritics ≥ :data:`_GERMAN_DIACRITIC_MIN` OR German
       function-word hits ≥ :data:`_GERMAN_FUNCTION_WORD_MIN_FOR_DE` → ``de``.
    4. Function-word hits == :data:`_GERMAN_FUNCTION_WORD_AMBIGUOUS` → ``mixed``.
    5. Otherwise (latin alpha present) → ``en``.
    """
    if not text:
        return "mixed"
    buckets = _count_lang_buckets(text)
    if buckets.total == 0:
        return "mixed"
    cjk_ratio = (buckets.kana + buckets.kanji) / buckets.total
    if cjk_ratio >= _CJK_RATIO_THRESHOLD:
        return "ja"
    german_hits = _count_german_function_words(text)
    if (
        buckets.german_diacritics >= _GERMAN_DIACRITIC_MIN
        or german_hits >= _GERMAN_FUNCTION_WORD_MIN_FOR_DE
    ):
        return "de"
    if buckets.latin_alpha == 0:
        return "mixed"
    if german_hits == _GERMAN_FUNCTION_WORD_AMBIGUOUS:
        return "mixed"
    return "en"


# ---------------------------------------------------------------------------
# Token-length estimation (lazy transformers + fallback)
# ---------------------------------------------------------------------------


def estimate_token_count_whitespace(text: str) -> int:
    """Whitespace + punctuation tokenisation × 1.3 heuristic + CJK 1:1.

    Empirical ratio: BPE/SentencePiece tokenisers produce ~1.25-1.35
    tokens per whitespace-delimited word for European languages, more
    for CJK (each character is roughly one token in Qwen tokenizers).
    Used as a fallback when the Qwen3-8B tokenizer is not available
    (transformers extra not installed).
    """
    word_count = len(re.findall(r"\S+", text))
    cjk_chars = sum(
        1
        for c in text
        if any(lo <= ord(c) <= hi for lo, hi in (*_KANA_RANGES, _KANJI_RANGE))
    )
    return int(word_count * 1.3) + cjk_chars


_TOKENIZER_CACHE: Any = None


def _load_qwen_tokenizer() -> Any | None:
    """Attempt to load Qwen3-8B tokenizer; return None on failure.

    Lazy + cached. Failure modes:
    * ``transformers`` not installed (training extras off) → ``ImportError``.
    * Hugging Face hub download blocked / model gated → various exceptions.

    Both are caught and reduced to ``None`` so the caller can switch to
    the whitespace proxy without aborting the run.
    """
    global _TOKENIZER_CACHE  # noqa: PLW0603
    if _TOKENIZER_CACHE is not None:
        return _TOKENIZER_CACHE if _TOKENIZER_CACHE is not False else None
    try:
        from transformers import AutoTokenizer  # noqa: PLC0415

        _TOKENIZER_CACHE = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
            "Qwen/Qwen3-8B",
            trust_remote_code=True,
            use_fast=True,
        )
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        _LOGGER.warning(
            "Qwen3-8B tokenizer unavailable (%s: %s); using whitespace × 1.3 proxy",
            type(exc).__name__,
            exc,
        )
        _TOKENIZER_CACHE = False
        return None
    return _TOKENIZER_CACHE


def estimate_token_count(text: str, *, use_real_tokenizer: bool = True) -> int:
    """Estimate token count for *text*.

    Prefer the real Qwen3-8B tokenizer when available; otherwise fall
    back to :func:`estimate_token_count_whitespace`. Returns 0 for
    empty input.
    """
    if not text:
        return 0
    tokenizer = _load_qwen_tokenizer() if use_real_tokenizer else None
    if tokenizer is None:
        return estimate_token_count_whitespace(text)
    encoded = tokenizer(text, add_special_tokens=False)
    return len(encoded["input_ids"])


# ---------------------------------------------------------------------------
# Shard provenance
# ---------------------------------------------------------------------------


def classify_shard(shard_path: Path) -> tuple[str, int]:
    """Parse ``kant_{natural,stimulus}_run{N}.duckdb`` → ``("natural"|"stimulus", N)``.

    Raises ``ValueError`` on unrecognised filenames so analyser failures
    are loud rather than silent.
    """
    stem = shard_path.stem  # e.g. "kant_natural_run3"
    m = re.fullmatch(r"kant_(natural|stimulus)_run(\d+)", stem)
    if m is None:
        raise ValueError(
            f"unrecognised shard filename {stem!r}; expected"
            f" 'kant_{{natural|stimulus}}_run{{N}}.duckdb'",
        )
    return m.group(1), int(m.group(2))


# ---------------------------------------------------------------------------
# Row → weight metadata adapter
# ---------------------------------------------------------------------------


def extract_example_metadata(
    row: Mapping[str, object],
    *,
    source_shard: str,
    source_shard_type: str,
    use_real_tokenizer: bool = False,
) -> dict[str, object]:
    """Build the per-example metadata dict consumed by :func:`compute_example_weight`.

    Mirrors :func:`scripts.analysis.analyze_kant_training_corpus._row_to_metrics`
    but is **dedicated to the training pipeline**: it skips the
    epoch_phase / persona filter (callers must run :func:`build_examples`
    first) and returns a plain dict rather than the analyse-side dataclass.

    Args:
        row: A raw_dialog row dict whose ``utterance`` and
            ``addressee_persona_id`` keys are populated. Caller's
            responsibility to filter for ``speaker_persona_id``.
        source_shard: Basename of the source DuckDB shard
            (``kant_natural_run0.duckdb`` etc.).
        source_shard_type: ``"natural"`` or ``"stimulus"`` (precomputed
            via :func:`classify_shard`).
        use_real_tokenizer: When ``True``, attempt to load the Qwen3-8B
            tokenizer for token counting. CI / unit tests pass ``False``
            so the run stays deterministic and dependency-light.

    Returns:
        A metadata dict with keys

        * ``language`` (``"de"``/``"en"``/``"mixed"``/``"ja"``)
        * ``token_count`` (int)
        * ``has_addressee`` (bool)
        * ``marker_density_per_100_tokens`` (float)
        * ``self_ref_marker_count`` (int) — diagnostic
        * ``kantian_marker_count`` (int) — diagnostic
        * ``source_shard`` (str) — provenance
        * ``source_shard_type`` (str) — used by group-aware split stratification
        * ``dialog_id`` (str) — used by group-aware split key
        * ``turn_index`` (int) — used by monolog re-cast detection
    """
    utterance = str(row.get("utterance", ""))
    tokens = estimate_token_count(utterance, use_real_tokenizer=use_real_tokenizer)
    self_ref = count_markers(utterance, GERMAN_PATTERNS)
    kantian = count_markers(utterance, KANTIAN_PATTERNS)
    total = self_ref + kantian
    density = (total / tokens) * 100.0 if tokens > 0 else 0.0

    addressee_obj = row.get("addressee_persona_id")
    has_addressee = isinstance(addressee_obj, str) and bool(addressee_obj.strip())

    dialog_id_obj = row.get("dialog_id", "?")
    turn_index_obj = row.get("turn_index", -1)
    return {
        "language": classify_language(utterance),
        "token_count": tokens,
        "has_addressee": has_addressee,
        "marker_density_per_100_tokens": density,
        "self_ref_marker_count": self_ref,
        "kantian_marker_count": kantian,
        "source_shard": source_shard,
        "source_shard_type": source_shard_type,
        "dialog_id": str(dialog_id_obj),
        "turn_index": int(turn_index_obj) if isinstance(turn_index_obj, int) else -1,
    }


__all__ = [
    "GERMAN_FIRST_PERSON_MARKERS",
    "GERMAN_PATTERNS",
    "KANTIAN_PATTERNS",
    "KANTIAN_PHILOSOPHY_MARKERS",
    "LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS",
    "SHORT_UTTERANCE_TOKEN_CAP",
    "classify_language",
    "classify_shard",
    "count_markers",
    "estimate_token_count",
    "estimate_token_count_whitespace",
    "extract_example_metadata",
]
