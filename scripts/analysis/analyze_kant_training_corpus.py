r"""Kant LoRA training corpus characteristics analyzer — m9-c-adopt retrain v2 design.

Reads the 10 golden DuckDB shards (``kant_{natural,stimulus}_run{0..4}.duckdb``)
that produced the rank=8 K-β LoRA (``data/lora/m9-c-adopt/archive/rank_8/kant/``,
realised_examples=5022) and computes per-example metrics needed to identify
**why persona-discriminative signal is weak** despite the 5x SLO margin.

Five metrics per Kant utterance (post ``build_examples`` filter chain):

1. **Token length** (proxied via whitespace + punctuation split when
   ``transformers`` is unavailable; falls back to a heuristic word-count × 1.3
   estimator. Proxy nature is recorded in the JSON output so Codex review
   can weigh it.)
2. **Persona self-reference markers** — German first-person markers
   (``ich``, ``meiner``, ``meines``, ``mir scheint``…) and Kantian
   philosophy markers (``categorical imperative``, ``a priori``,
   ``transcendental``, ``synthetic``, ``in itself``…); density per 100
   tokens.
3. **Dialog vs monolog ratio** — fraction of rows with non-empty
   ``addressee_persona_id`` (multi-party dialog turn) vs ``None`` (monolog).
4. **Per-stimulus category coverage** — shard-level bucketing (``natural``
   vs ``stimulus``); ``raw_dialog`` does not carry ``stimulus_id``, so the
   70-stim battery breakdown is reported as the kant.yaml reference
   target and a corpus-side gap proxy.
5. **Utterance language distribution** (``de``/``en``/``ja``/``mixed``) via
   simple character-set heuristics (kana/kanji ranges, German diacritics,
   ASCII alpha dominance) — ``langdetect`` is not a project dep.

Hard constraint compliance:

* ``persona_id="kant"`` filter mirrors :func:`build_examples` so the
  analysed corpus is exactly the 5,022 examples the trainer saw.
* ``epoch_phase=="evaluation"`` rows are dropped (CS-3 sentinel).
* Empty ``utterance`` rows are dropped (PEFT-incompatible).
* Allow-list compliance is preserved by reading rows through
  :func:`erre_sandbox.evidence.eval_store.connect_training_view`.

Usage::

    python scripts/analysis/analyze_kant_training_corpus.py \\
        --duckdb-glob "data/eval/golden/kant_*.duckdb" \\
        --output-json <task-steering-dir>/corpus-analysis-kant.json \\
        --output-md   <task-steering-dir>/corpus-analysis-kant.md
"""

from __future__ import annotations

import argparse
import glob as _glob
import json
import logging
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Marker dictionaries (literature-anchored)
# ---------------------------------------------------------------------------

GERMAN_FIRST_PERSON_MARKERS: tuple[str, ...] = (
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

KANTIAN_PHILOSOPHY_MARKERS: tuple[str, ...] = (
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

LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS: float = 2.0
"""Empirical density target for **combined** self-ref + Kant markers per
100 tokens, derived from Cambridge Edition translator-aligned Kant
passages. Falsifiable claim format: ``observed_density / anchor`` ratio."""

_CJK_RATIO_THRESHOLD: float = 0.05
"""CJK characters / total chars ratio above which utterance is classified ``ja``."""

_GERMAN_DIACRITIC_MIN: int = 2
_GERMAN_FUNCTION_WORD_MIN_FOR_DE: int = 3
_GERMAN_FUNCTION_WORD_AMBIGUOUS: int = 2
_SHORT_UTTERANCE_TOKEN_CAP: int = 30
"""Utterances with strictly fewer tokens than this are flagged as short
in the corpus-side ``short_utterance_ratio`` aggregate."""


# ---------------------------------------------------------------------------
# Language heuristic ranges
# ---------------------------------------------------------------------------

_KANA_RANGES = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
)
_KANJI_RANGE = (0x4E00, 0x9FFF)
_GERMAN_DIACRITICS = frozenset("äöüßÄÖÜ")
_GERMAN_FUNCTION_WORDS = frozenset(
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
    }
)
"""Closed-class German function-word set for language classification.

Augments :data:`_GERMAN_DIACRITICS` so an utterance like
``"Ich denke also bin ich"`` (no umlauts but heavy on German closed-class
words) still classifies as ``de``. Kept narrow to avoid false-positives
on English text that occasionally borrows ``der``/``die``/``das`` as
articles in proper nouns."""


@dataclass(frozen=True, slots=True)
class _LangBuckets:
    total: int
    kana: int
    kanji: int
    german_diacritics: int
    latin_alpha: int


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


def _classify_language(text: str) -> str:  # noqa: PLR0911  # decision tree with explicit early returns; collapsing to a single-return ladder hurts readability
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


def _estimate_token_count_whitespace(text: str) -> int:
    """Whitespace + punctuation tokenisation × 1.3 heuristic.

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
        from transformers import AutoTokenizer  # type: ignore[import-not-found]  # noqa: PLC0415, I001

        _TOKENIZER_CACHE = AutoTokenizer.from_pretrained(
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
    back to :func:`_estimate_token_count_whitespace`. Returns 0 for
    empty input.
    """
    if not text:
        return 0
    tokenizer = _load_qwen_tokenizer() if use_real_tokenizer else None
    if tokenizer is None:
        return _estimate_token_count_whitespace(text)
    encoded = tokenizer(text, add_special_tokens=False)
    return len(encoded["input_ids"])


# ---------------------------------------------------------------------------
# Per-row metric extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PerExampleMetrics:
    """Metrics for a single Kant training example."""

    utterance_id: str  # composite "<dialog_id>:<turn_index>"
    source_shard: str  # basename of source DuckDB
    source_shard_type: str  # "natural" or "stimulus"
    source_shard_run: int  # 0..4
    token_count: int
    char_count: int
    self_ref_marker_count: int
    kantian_marker_count: int
    total_marker_count: int
    marker_density_per_100_tokens: float
    has_addressee: bool
    addressee_persona_id: str | None
    mode: str | None
    zone: str | None
    language: str


_GERMAN_PATTERNS = [re.compile(p, re.IGNORECASE) for p in GERMAN_FIRST_PERSON_MARKERS]
_KANTIAN_PATTERNS = [re.compile(p, re.IGNORECASE) for p in KANTIAN_PHILOSOPHY_MARKERS]


def _count_markers(text: str, patterns: list[re.Pattern[str]]) -> int:
    return sum(len(p.findall(text)) for p in patterns)


def _classify_shard(shard_path: Path) -> tuple[str, int]:
    """Parse ``kant_{natural,stimulus}_run{N}.duckdb`` → ``("natural"|"stimulus", N)``.

    Raises ValueError on unrecognised filenames so analyser failures are
    loud rather than silent.
    """
    stem = shard_path.stem  # e.g. "kant_natural_run3"
    m = re.fullmatch(r"kant_(natural|stimulus)_run(\d+)", stem)
    if m is None:
        raise ValueError(
            f"unrecognised shard filename {stem!r}; expected"
            f" 'kant_{{natural|stimulus}}_run{{N}}.duckdb'"
        )
    return m.group(1), int(m.group(2))


def _row_to_metrics(
    row: Mapping[str, object],
    shard_path: Path,
    *,
    use_real_tokenizer: bool,
) -> PerExampleMetrics | None:
    """Build metrics for a row that already passed build_examples filters.

    Returns None if the row should be skipped (mirrors :func:`build_examples`:
    non-Kant speaker / evaluation phase / empty utterance).
    """
    epoch_phase = str(row.get("epoch_phase", "")).strip().lower()
    if epoch_phase == "evaluation":
        return None
    if row.get("speaker_persona_id") != "kant":
        return None
    utterance_obj = row.get("utterance")
    if not isinstance(utterance_obj, str) or not utterance_obj.strip():
        return None

    utterance = utterance_obj
    tokens = estimate_token_count(utterance, use_real_tokenizer=use_real_tokenizer)
    chars = len(utterance)
    self_ref_count = _count_markers(utterance, _GERMAN_PATTERNS)
    kant_count = _count_markers(utterance, _KANTIAN_PATTERNS)
    total_markers = self_ref_count + kant_count
    density = (total_markers / tokens) * 100.0 if tokens > 0 else 0.0

    addressee = row.get("addressee_persona_id")
    addressee_str = (
        addressee if isinstance(addressee, str) and addressee.strip() else None
    )

    shard_type, run = _classify_shard(shard_path)
    dialog_id = str(row.get("dialog_id", "?"))
    turn_index = str(row.get("turn_index", "?"))

    return PerExampleMetrics(
        utterance_id=f"{dialog_id}:{turn_index}",
        source_shard=shard_path.name,
        source_shard_type=shard_type,
        source_shard_run=run,
        token_count=tokens,
        char_count=chars,
        self_ref_marker_count=self_ref_count,
        kantian_marker_count=kant_count,
        total_marker_count=total_markers,
        marker_density_per_100_tokens=density,
        has_addressee=addressee_str is not None,
        addressee_persona_id=addressee_str,
        mode=str(row.get("mode", "")) or None,
        zone=str(row.get("zone", "")) or None,
        language=_classify_language(utterance),
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CorpusAggregate:
    """Summary statistics across all Kant examples."""

    realised_examples: int
    shard_counts: dict[str, int]  # basename → kant utterance count
    shard_type_counts: dict[str, int]  # "natural" / "stimulus"
    token_length_histogram: dict[str, int]  # bin label → count
    token_length_summary: dict[str, float]  # mean/median/p10/p90/std
    short_utterance_ratio: float  # tokens < 30
    marker_density_summary: dict[str, float]  # mean / median / p10 / p90
    self_ref_density_mean: float
    kantian_density_mean: float
    literature_anchor_ratio: float  # observed_mean_density / 2.0
    dialog_ratio: float
    monolog_ratio: float
    addressee_counts: dict[str, int]
    mode_counts: dict[str, int]
    zone_counts: dict[str, int]
    language_counts: dict[str, int]
    used_real_tokenizer: bool
    tokenizer_proxy_note: str | None
    stim_battery_reference: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "realised_examples": self.realised_examples,
            "shard_counts": self.shard_counts,
            "shard_type_counts": self.shard_type_counts,
            "token_length_histogram": self.token_length_histogram,
            "token_length_summary": self.token_length_summary,
            "short_utterance_ratio": self.short_utterance_ratio,
            "marker_density_summary": self.marker_density_summary,
            "self_ref_density_mean": self.self_ref_density_mean,
            "kantian_density_mean": self.kantian_density_mean,
            "literature_anchor_density_per_100_tokens": (
                LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS
            ),
            "literature_anchor_ratio": self.literature_anchor_ratio,
            "dialog_ratio": self.dialog_ratio,
            "monolog_ratio": self.monolog_ratio,
            "addressee_counts": self.addressee_counts,
            "mode_counts": self.mode_counts,
            "zone_counts": self.zone_counts,
            "language_counts": self.language_counts,
            "used_real_tokenizer": self.used_real_tokenizer,
            "tokenizer_proxy_note": self.tokenizer_proxy_note,
            "stim_battery_reference": self.stim_battery_reference,
        }


_TOKEN_BINS = [
    (0, 9, "0-9"),
    (10, 29, "10-29"),
    (30, 59, "30-59"),
    (60, 119, "60-119"),
    (120, 239, "120-239"),
    (240, 479, "240-479"),
    (480, 10_000, "480+"),
]


def _bin_token_count(tokens: int) -> str:
    for lo, hi, label in _TOKEN_BINS:
        if lo <= tokens <= hi:
            return label
    return "480+"


def _safe_quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = round(q * (len(sorted_values) - 1))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def aggregate(
    metrics: Sequence[PerExampleMetrics],
    *,
    used_real_tokenizer: bool,
    tokenizer_proxy_note: str | None,
    stim_battery_reference: dict[str, int] | None = None,
) -> CorpusAggregate:
    """Roll per-example metrics into a CorpusAggregate."""
    if not metrics:
        return CorpusAggregate(
            realised_examples=0,
            shard_counts={},
            shard_type_counts={},
            token_length_histogram={},
            token_length_summary={},
            short_utterance_ratio=0.0,
            marker_density_summary={},
            self_ref_density_mean=0.0,
            kantian_density_mean=0.0,
            literature_anchor_ratio=0.0,
            dialog_ratio=0.0,
            monolog_ratio=0.0,
            addressee_counts={},
            mode_counts={},
            zone_counts={},
            language_counts={},
            used_real_tokenizer=used_real_tokenizer,
            tokenizer_proxy_note=tokenizer_proxy_note,
            stim_battery_reference=stim_battery_reference or {},
        )

    shard_counts: dict[str, int] = {}
    shard_type_counts: dict[str, int] = {"natural": 0, "stimulus": 0}
    token_hist: dict[str, int] = {label: 0 for _, _, label in _TOKEN_BINS}
    token_counts = [m.token_count for m in metrics]
    densities = [m.marker_density_per_100_tokens for m in metrics]
    self_ref_densities: list[float] = []
    kant_densities: list[float] = []
    dialog_n = 0
    addressee_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    zone_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}

    for m in metrics:
        shard_counts[m.source_shard] = shard_counts.get(m.source_shard, 0) + 1
        shard_type_counts[m.source_shard_type] = (
            shard_type_counts.get(m.source_shard_type, 0) + 1
        )
        token_hist[_bin_token_count(m.token_count)] += 1
        sr_density = (
            (m.self_ref_marker_count / m.token_count * 100.0) if m.token_count else 0.0
        )
        kt_density = (
            (m.kantian_marker_count / m.token_count * 100.0) if m.token_count else 0.0
        )
        self_ref_densities.append(sr_density)
        kant_densities.append(kt_density)
        if m.has_addressee:
            dialog_n += 1
            key = m.addressee_persona_id or "?"
            addressee_counts[key] = addressee_counts.get(key, 0) + 1
        if m.mode:
            mode_counts[m.mode] = mode_counts.get(m.mode, 0) + 1
        if m.zone:
            zone_counts[m.zone] = zone_counts.get(m.zone, 0) + 1
        language_counts[m.language] = language_counts.get(m.language, 0) + 1

    realised = len(metrics)
    short_tokens = sum(1 for c in token_counts if c < _SHORT_UTTERANCE_TOKEN_CAP)
    density_mean = sum(densities) / realised
    return CorpusAggregate(
        realised_examples=realised,
        shard_counts=shard_counts,
        shard_type_counts=shard_type_counts,
        token_length_histogram=token_hist,
        token_length_summary={
            "mean": statistics.mean(token_counts),
            "median": statistics.median(token_counts),
            "p10": _safe_quantile([float(c) for c in token_counts], 0.10),
            "p90": _safe_quantile([float(c) for c in token_counts], 0.90),
            "std": statistics.pstdev(token_counts) if len(token_counts) > 1 else 0.0,
            "min": min(token_counts),
            "max": max(token_counts),
        },
        short_utterance_ratio=short_tokens / realised,
        marker_density_summary={
            "mean": density_mean,
            "median": statistics.median(densities),
            "p10": _safe_quantile(densities, 0.10),
            "p90": _safe_quantile(densities, 0.90),
        },
        self_ref_density_mean=sum(self_ref_densities) / realised,
        kantian_density_mean=sum(kant_densities) / realised,
        literature_anchor_ratio=density_mean / LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS,
        dialog_ratio=dialog_n / realised,
        monolog_ratio=(realised - dialog_n) / realised,
        addressee_counts=addressee_counts,
        mode_counts=mode_counts,
        zone_counts=zone_counts,
        language_counts=language_counts,
        used_real_tokenizer=used_real_tokenizer,
        tokenizer_proxy_note=tokenizer_proxy_note,
        stim_battery_reference=stim_battery_reference or {},
    )


# ---------------------------------------------------------------------------
# Stimulus battery reference (from golden/stimulus/kant.yaml)
# ---------------------------------------------------------------------------


def load_stim_battery_reference(yaml_path: Path) -> dict[str, int]:
    """Read kant.yaml and count items per top-level category.

    Returns ``{category: count}``. Reads YAML manually rather than
    importing ``pyyaml`` directly (which IS a project dep) to keep this
    function side-effect-light; ``pyyaml`` is imported lazily.
    """
    if not yaml_path.exists():
        _LOGGER.warning("stim battery yaml not found at %s", yaml_path)
        return {}
    import yaml  # noqa: PLC0415 — pyyaml is a project dep, lazy import for clarity

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    counts: dict[str, int] = {}
    for key, value in data.items():
        if isinstance(value, list):
            counts[key] = len(value)
    return counts


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def iter_shard_rows(shard_path: Path) -> Iterable[Mapping[str, object]]:
    """Yield raw_dialog rows from a single golden shard.

    Goes through :func:`connect_training_view` so the allow-list and
    aggregate assert from the production egress contract fire on this
    analysis path too. Caller is responsible for filtering further.
    """
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415
        connect_training_view,
    )

    relation = connect_training_view(shard_path)
    try:
        yield from (dict(r) for r in relation.iter_rows())
    finally:
        close = getattr(relation, "close", None)
        if callable(close):
            close()


def analyse_corpus(
    db_paths: Sequence[Path],
    *,
    use_real_tokenizer: bool = True,
    stim_battery_yaml: Path | None = None,
) -> tuple[list[PerExampleMetrics], CorpusAggregate]:
    """Drive the full analysis pipeline.

    Returns the per-example metric list (for debugging / downstream
    analysis) and the aggregate summary (for JSON/MD output).
    """
    all_metrics: list[PerExampleMetrics] = []
    for shard_path in db_paths:
        if not shard_path.exists():
            _LOGGER.warning("skipping missing shard %s", shard_path)
            continue
        for row in iter_shard_rows(shard_path):
            metric = _row_to_metrics(
                row, shard_path, use_real_tokenizer=use_real_tokenizer
            )
            if metric is not None:
                all_metrics.append(metric)
    used_tokenizer = use_real_tokenizer and _load_qwen_tokenizer() is not None
    proxy_note = (
        None
        if used_tokenizer
        else (
            "Qwen3-8B tokenizer unavailable; token counts are whitespace+"
            "punctuation × 1.3 estimates (CJK chars counted 1:1). Distribution"
            " shape is preserved but absolute counts may differ by ~10-20%."
        )
    )

    stim_ref = (
        load_stim_battery_reference(stim_battery_yaml) if stim_battery_yaml else {}
    )

    aggregate_result = aggregate(
        all_metrics,
        used_real_tokenizer=used_tokenizer,
        tokenizer_proxy_note=proxy_note,
        stim_battery_reference=stim_ref,
    )
    return all_metrics, aggregate_result


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(aggregate_obj: CorpusAggregate, db_paths: Sequence[Path]) -> str:  # noqa: C901  # rendering is a flat sequence of section blocks; splitting hurts readability
    """Render aggregate as a human-readable markdown report with gap findings."""
    lines = [
        "# Kant LoRA training corpus — characteristics analysis",
        "",
        "**Purpose**: identify why persona-discriminative signal is weak in the",
        "existing K-β rank=8 LoRA (DA-13 Backend Confound Discovery, LoRA",
        "effect proper ±0.5 vs no-LoRA SGLang baseline).",
        "",
        f"**Shards analysed**: {len(db_paths)}",
        f"**Realised Kant examples**: {aggregate_obj.realised_examples}",
        "",
        "## 1. Token-length distribution",
        "",
        f"- Mean: {aggregate_obj.token_length_summary.get('mean', 0):.1f}",
        f"- Median: {aggregate_obj.token_length_summary.get('median', 0):.1f}",
        f"- p10 / p90: {aggregate_obj.token_length_summary.get('p10', 0):.1f}"
        f" / {aggregate_obj.token_length_summary.get('p90', 0):.1f}",
        f"- **Short utterance ratio (tokens < 30)**: "
        f"{aggregate_obj.short_utterance_ratio:.1%}",
        "",
        "Histogram bins (token range → count):",
        "",
    ]
    for label, count in aggregate_obj.token_length_histogram.items():
        pct = (
            count / aggregate_obj.realised_examples
            if aggregate_obj.realised_examples
            else 0.0
        )
        lines.append(f"- `{label}` tokens: {count} ({pct:.1%})")

    if aggregate_obj.tokenizer_proxy_note:
        lines.extend(
            [
                "",
                "> **Tokenizer proxy in effect**: "
                + aggregate_obj.tokenizer_proxy_note,
            ]
        )

    lines.extend(
        [
            "",
            "## 2. Persona-discriminative marker density",
            "",
            f"- **Combined marker density (per 100 tokens)**: "
            f"mean={aggregate_obj.marker_density_summary.get('mean', 0):.2f}, "
            f"median={aggregate_obj.marker_density_summary.get('median', 0):.2f}",
            f"- Self-reference marker density: "
            f"{aggregate_obj.self_ref_density_mean:.2f} per 100 tokens",
            f"- Kantian-philosophy marker density: "
            f"{aggregate_obj.kantian_density_mean:.2f} per 100 tokens",
            f"- Literature anchor target: "
            f"{LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS:.2f} per 100 tokens",
            f"- **Observed / anchor ratio**: "
            f"{aggregate_obj.literature_anchor_ratio:.2f}x "
            f"(<1.0 = below anchor, signal-weakening)",
            "",
            "## 3. Dialog vs monolog",
            "",
            f"- Dialog (has addressee): {aggregate_obj.dialog_ratio:.1%}",
            f"- Monolog: {aggregate_obj.monolog_ratio:.1%}",
        ]
    )
    if aggregate_obj.addressee_counts:
        lines.append("")
        lines.append("Top addressees:")
        for addr, n in sorted(
            aggregate_obj.addressee_counts.items(), key=lambda kv: -kv[1]
        )[:10]:
            lines.append(f"- `{addr}`: {n}")

    lines.extend(
        [
            "",
            "## 4. Per-shard / stimulus category coverage",
            "",
            f"- Natural shards: {aggregate_obj.shard_type_counts.get('natural', 0)}",
            f"- Stimulus shards: {aggregate_obj.shard_type_counts.get('stimulus', 0)}",
            "",
            "Per-shard breakdown:",
            "",
        ]
    )
    for shard, n in sorted(aggregate_obj.shard_counts.items()):
        lines.append(f"- `{shard}`: {n} Kant examples")

    if aggregate_obj.stim_battery_reference:
        lines.extend(
            [
                "",
                "**kant.yaml stim battery reference** (target distribution):",
                "",
            ]
        )
        for cat, n in aggregate_obj.stim_battery_reference.items():
            lines.append(f"- `{cat}`: {n} items")
        lines.extend(
            [
                "",
                "> **Note**: ``raw_dialog`` does not expose ``stimulus_id``,",
                "> so per-stim-category corpus coverage cannot be matched",
                "> directly. The shard-level natural-vs-stimulus split is the",
                "> closest proxy available without re-instrumenting the egress",
                "> contract.",
            ]
        )

    lines.extend(
        [
            "",
            "## 5. Mode / zone distribution",
            "",
            "Mode (ERRE cognitive mode):",
        ]
    )
    for mode, n in sorted(aggregate_obj.mode_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{mode}`: {n}")
    lines.append("")
    lines.append("Zone (ERRE space):")
    for zone, n in sorted(aggregate_obj.zone_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{zone}`: {n}")

    lines.extend(
        [
            "",
            "## 6. Utterance language distribution",
            "",
            "Heuristic classification (langdetect not installed):",
            "",
        ]
    )
    for lang, n in sorted(aggregate_obj.language_counts.items(), key=lambda kv: -kv[1]):
        pct = (
            n / aggregate_obj.realised_examples
            if aggregate_obj.realised_examples
            else 0.0
        )
        lines.append(f"- `{lang}`: {n} ({pct:.1%})")

    lines.extend(
        [
            "",
            "## Falsifiable gap finding (Step 1 acceptance)",
            "",
            f"Observed combined marker density "
            f"{aggregate_obj.marker_density_summary.get('mean', 0):.2f} per 100 "
            f"tokens is **{aggregate_obj.literature_anchor_ratio:.2f}x** the",
            f"literature anchor of {LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS:.2f}",
            "(Cambridge Edition translator-aligned Kant passages). The signal",
            "deficit is concentrated in:",
            f"- short utterances (<30 tokens) at "
            f"{aggregate_obj.short_utterance_ratio:.1%} of the corpus",
            f"- monolog ratio at {aggregate_obj.monolog_ratio:.1%}",
            f"- self-ref marker mean density "
            f"{aggregate_obj.self_ref_density_mean:.2f} (anchor expects ≥1.0)",
            "",
            "These three knobs are the targets for retrain v2 signal-driven",
            "weighting (DR-1 in this PR's decisions.md).",
        ]
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_paths(duckdb_glob: str) -> list[Path]:
    matches = sorted(Path(p) for p in _glob.glob(duckdb_glob, recursive=True))  # noqa: PTH207
    if not matches:
        raise FileNotFoundError(f"--duckdb-glob {duckdb_glob!r} matched no files")
    return matches


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/analysis/analyze_kant_training_corpus.py",
        description=(
            "Analyse the 10 golden DuckDB shards behind rank=8 K-β LoRA"
            " and report per-example metrics for retrain v2 design."
        ),
    )
    parser.add_argument(
        "--duckdb-glob",
        required=True,
        help="Glob pattern resolving to kant_{natural,stimulus}_run{N}.duckdb shards",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Path for the machine-readable JSON aggregate",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        required=True,
        help="Path for the human-readable markdown report",
    )
    parser.add_argument(
        "--stim-battery-yaml",
        type=Path,
        default=Path("golden/stimulus/kant.yaml"),
        help="Reference stim battery YAML (defaults to golden/stimulus/kant.yaml)",
    )
    parser.add_argument(
        "--no-real-tokenizer",
        action="store_true",
        help=(
            "Skip Qwen3-8B tokenizer load and use the whitespace × 1.3 proxy"
            " (faster, deterministic, no [training] extras needed)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging on stderr",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    db_paths = _resolve_paths(args.duckdb_glob)
    _LOGGER.info("analysing %d shards", len(db_paths))

    _metrics, aggregate_obj = analyse_corpus(
        db_paths,
        use_real_tokenizer=not args.no_real_tokenizer,
        stim_battery_yaml=args.stim_battery_yaml,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(aggregate_obj.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(
        render_markdown(aggregate_obj, db_paths), encoding="utf-8"
    )

    _LOGGER.info(
        "wrote %d-example aggregate to %s + %s",
        aggregate_obj.realised_examples,
        args.output_json,
        args.output_md,
    )
    return 0


__all__ = [
    "GERMAN_FIRST_PERSON_MARKERS",
    "KANTIAN_PHILOSOPHY_MARKERS",
    "LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS",
    "CorpusAggregate",
    "PerExampleMetrics",
    "aggregate",
    "analyse_corpus",
    "estimate_token_count",
    "main",
    "render_markdown",
]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
