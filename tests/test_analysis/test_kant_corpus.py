"""Smoke tests for scripts/analysis/analyze_kant_training_corpus.py.

3-case suite covering the three metrics whose computation is non-trivial:
self-reference marker density, dialog/monolog classification, and the
whitespace × 1.3 token-count proxy (used when the Qwen3-8B tokenizer is
unreachable on CI).

The analyser imports DuckDB lazily inside :func:`iter_shard_rows`, so
these tests can drive ``_row_to_metrics`` and ``aggregate`` directly
with hand-crafted row dicts — no DuckDB fixture is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# scripts/ is added to sys.path via conftest.py.
from scripts.analysis.analyze_kant_training_corpus import (  # type: ignore[import-not-found]
    LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS,
    PerExampleMetrics,
    _classify_language,
    _estimate_token_count_whitespace,
    _row_to_metrics,
    aggregate,
    estimate_token_count,
)

_KANT_DIALOG_SHARD = Path("kant_natural_run0.duckdb")
_KANT_STIMULUS_SHARD = Path("kant_stimulus_run2.duckdb")


def _row(
    *,
    utterance: str,
    speaker: str = "kant",
    epoch_phase: str = "phase_b",
    addressee: str | None = "leibniz",
    mode: str = "shu_kata",
    zone: str = "study",
    dialog_id: str = "dlg-001",
    turn_index: int = 3,
) -> dict[str, object]:
    return {
        "dialog_id": dialog_id,
        "turn_index": turn_index,
        "speaker_persona_id": speaker,
        "addressee_persona_id": addressee,
        "utterance": utterance,
        "epoch_phase": epoch_phase,
        "mode": mode,
        "zone": zone,
    }


# ---------------------------------------------------------------------------
# Case 1: self-reference + Kantian marker density
# ---------------------------------------------------------------------------


def test_row_to_metrics_counts_german_and_kantian_markers() -> None:
    # Dense Kantian + first-person passage; both pattern families should
    # contribute. ``ich`` (1), ``meiner Ansicht nach`` (1, also counts
    # standalone ``meiner`` inside it — regex are independent), and the
    # Kantian markers ``categorical imperative`` (1) + ``a priori`` (1) +
    # ``transcendental`` (1).
    utterance = (
        "Ich behaupte meiner Ansicht nach, dass der kategorische Imperativ"
        " a priori gilt — categorical imperative ist transcendental."
    )
    row = _row(utterance=utterance, addressee=None, mode="zazen", zone="peripatos")
    metric = _row_to_metrics(row, _KANT_DIALOG_SHARD, use_real_tokenizer=False)
    assert metric is not None
    # The 3 Kantian markers (kategorischer imperativ / categorical imperative /
    # a priori / transcendental — 4 matches) and the German first-person
    # markers (ich + meiner inside "meiner ansicht nach" + meiner ansicht
    # nach itself) are both > 0.
    assert metric.self_ref_marker_count >= 2, (
        f"expected German first-person markers ≥2, got {metric.self_ref_marker_count}"
    )
    assert metric.kantian_marker_count >= 3, (
        f"expected Kantian markers ≥3, got {metric.kantian_marker_count}"
    )
    assert metric.total_marker_count == (
        metric.self_ref_marker_count + metric.kantian_marker_count
    )
    # Density should be positive and well above the literature anchor
    # (this is a deliberately dense fixture).
    assert metric.marker_density_per_100_tokens > 0.0
    # Sanity: a row with no Kant markers should produce density ≈ 0.
    sparse_row = _row(
        utterance="The weather seems acceptable for a walk along the river.",
        addressee="hume",
    )
    sparse = _row_to_metrics(sparse_row, _KANT_DIALOG_SHARD, use_real_tokenizer=False)
    assert sparse is not None
    assert sparse.kantian_marker_count == 0
    assert sparse.self_ref_marker_count == 0
    assert sparse.marker_density_per_100_tokens == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Case 2: dialog vs monolog aggregation
# ---------------------------------------------------------------------------


def test_aggregate_dialog_monolog_ratio_from_addressee_field() -> None:
    metrics = [
        PerExampleMetrics(
            utterance_id="d:1",
            source_shard="kant_natural_run0.duckdb",
            source_shard_type="natural",
            source_shard_run=0,
            token_count=50,
            char_count=200,
            self_ref_marker_count=1,
            kantian_marker_count=0,
            total_marker_count=1,
            marker_density_per_100_tokens=2.0,
            has_addressee=True,
            addressee_persona_id="leibniz",
            mode="shu_kata",
            zone="study",
            language="de",
        ),
        PerExampleMetrics(
            utterance_id="d:2",
            source_shard="kant_natural_run0.duckdb",
            source_shard_type="natural",
            source_shard_run=0,
            token_count=80,
            char_count=320,
            self_ref_marker_count=0,
            kantian_marker_count=2,
            total_marker_count=2,
            marker_density_per_100_tokens=2.5,
            has_addressee=False,
            addressee_persona_id=None,
            mode="zazen",
            zone="peripatos",
            language="en",
        ),
        PerExampleMetrics(
            utterance_id="d:3",
            source_shard="kant_stimulus_run2.duckdb",
            source_shard_type="stimulus",
            source_shard_run=2,
            token_count=120,
            char_count=480,
            self_ref_marker_count=1,
            kantian_marker_count=1,
            total_marker_count=2,
            marker_density_per_100_tokens=1.67,
            has_addressee=True,
            addressee_persona_id="hume",
            mode="ha_deviate",
            zone="agora",
            language="en",
        ),
    ]
    agg = aggregate(metrics, used_real_tokenizer=False, tokenizer_proxy_note="proxy")
    assert agg.realised_examples == 3
    assert agg.dialog_ratio == pytest.approx(2 / 3)
    assert agg.monolog_ratio == pytest.approx(1 / 3)
    assert agg.addressee_counts == {"leibniz": 1, "hume": 1}
    assert agg.shard_type_counts["natural"] == 2
    assert agg.shard_type_counts["stimulus"] == 1
    # Token-length histogram should put 50/80/120 into the documented bins.
    # 50 → "30-59"; 80 → "60-119"; 120 → "120-239".
    assert agg.token_length_histogram["30-59"] == 1
    assert agg.token_length_histogram["60-119"] == 1
    assert agg.token_length_histogram["120-239"] == 1
    # Literature anchor ratio is mean density / 2.0.
    expected_anchor_ratio = (
        sum(m.marker_density_per_100_tokens for m in metrics) / 3
    ) / LITERATURE_ANCHOR_DENSITY_PER_100_TOKENS
    assert agg.literature_anchor_ratio == pytest.approx(expected_anchor_ratio)


# ---------------------------------------------------------------------------
# Case 3: token-length proxy + language classifier
# ---------------------------------------------------------------------------


def test_token_length_proxy_and_language_classifier_handle_mixed_corpus() -> None:
    # Whitespace × 1.3 proxy: 10 words → 13 tokens; CJK chars add 1:1.
    german = "Ich denke also bin ich, sagte Kant einst klar und deutlich heute."
    english = "The categorical imperative requires universalisability of maxims."
    japanese = "カントの定言命法は普遍化可能性を要求する。"

    # Force proxy path so the test is deterministic and does not require
    # the Qwen3-8B tokenizer to be reachable.
    de_tokens = estimate_token_count(german, use_real_tokenizer=False)
    en_tokens = estimate_token_count(english, use_real_tokenizer=False)
    ja_tokens = estimate_token_count(japanese, use_real_tokenizer=False)

    # Proxy must equal the public whitespace estimator (no hidden state).
    assert de_tokens == _estimate_token_count_whitespace(german)
    assert en_tokens == _estimate_token_count_whitespace(english)
    assert ja_tokens == _estimate_token_count_whitespace(japanese)

    # Empty string returns 0.
    assert estimate_token_count("", use_real_tokenizer=False) == 0

    # Language classifier: heuristics call de/en/ja correctly for these
    # canonical fixtures.
    assert _classify_language(german) == "de"
    assert _classify_language(english) == "en"
    assert _classify_language(japanese) == "ja"

    # Latin alpha falls through to "en" once CJK and German have been
    # ruled out (loanwords like "Naïve" are absorbed into the en bucket
    # since this analysis only needs to separate de / en / ja).
    assert _classify_language("Hi! Naïve world") == "en"
    # Empty / whitespace-only / pure punctuation → "mixed".
    assert _classify_language("") == "mixed"
    assert _classify_language("   ") == "mixed"
    assert _classify_language("!?!?") == "mixed"
