"""Integration tests for ``erre_sandbox.training.qc_detectors`` (PR-20 DPN20-0).

**Triple gating (user DPN20-2 #5)**:

1. ``pytest.importorskip("langdetect")`` — eval extras 環境のみ
2. ``pytest.importorskip("sentence_transformers")`` — eval extras 環境のみ
3. ``ERRE_RUN_REAL_MPNET_TESTS=1`` 環境変数 (opt-in) — default CI で MPNet
   model download (~440MB) を走らせない、 local cache がある時 or 明示
   opt-in 時のみ実行 (CI envelope 保護)

加えて ``pytest.mark.eval`` marker で ``pytest -m "not eval"`` でも除外可能。

Covers:

* :class:`LangdetectAdapter` — 実 ja/en/de 文字列で expected lang code +
  confidence 範囲
* :class:`LangdetectAdapter` 短文 fragile 防止 (min_length=5 token 未満で 0.0)
* :class:`MPNetNoveltyScorer` — 実 sentence pair (identical / different topic)
  で per-pair running centroid novelty range
* :func:`make_qc_filter` + 実 factory で end-to-end (1 PASS + 1 FAIL)
"""

from __future__ import annotations

import os

import pytest

# importorskip gated (eval extras 環境のみ実行)
pytest.importorskip("langdetect")
pytest.importorskip("sentence_transformers")

from erre_sandbox.training.gated_burrows_reward import make_qc_filter
from erre_sandbox.training.qc_detectors import (
    LangdetectAdapter,
    MPNetNoveltyScorer,
    make_langdetect_factory,
    make_mpnet_novelty_factory,
)

pytestmark = pytest.mark.eval

# DPN20-2 #5: MPNet model download (~440MB) を default で走らせない opt-in gate
_RUN_REAL_MPNET = os.environ.get("ERRE_RUN_REAL_MPNET_TESTS") == "1"
_REAL_MPNET_SKIP_REASON = (
    "MPNet integration tests skipped by default to avoid ~440MB model"
    " download in base CI. Set ERRE_RUN_REAL_MPNET_TESTS=1 to opt-in"
    " (local cache or explicit network OK)."
)
_skip_real_mpnet = pytest.mark.skipif(
    not _RUN_REAL_MPNET,
    reason=_REAL_MPNET_SKIP_REASON,
)


# ---------------------------------------------------------------------------
# LangdetectAdapter integration tests
# ---------------------------------------------------------------------------


def test_langdetect_adapter_de_confidence() -> None:
    """Case 11a: 実 de 文字列で expected_language='de' confidence > 0.6."""
    adapter = LangdetectAdapter()
    text = (
        "Die kategorischen Imperative von Immanuel Kant bilden die"
        " Grundlage seiner Moralphilosophie und prägen das deutsche"
        " Denken bis heute."
    )
    confidence = adapter(text, expected_language="de")
    assert confidence >= 0.6, f"expected de confidence >= 0.6, got {confidence}"


def test_langdetect_adapter_en_confidence() -> None:
    """Case 11b: 実 en 文字列で expected_language='en' confidence > 0.6."""
    adapter = LangdetectAdapter()
    text = (
        "The categorical imperative is a moral principle"
        " developed by Immanuel Kant in his foundational work."
    )
    confidence = adapter(text, expected_language="en")
    assert confidence >= 0.6, f"expected en confidence >= 0.6, got {confidence}"


def test_langdetect_adapter_ja_confidence() -> None:
    """Case 11c: 実 ja 文字列で expected_language='ja' confidence > 0.6."""
    adapter = LangdetectAdapter()
    text = "カントの定言命法は道徳哲学の基礎をなす重要な原理であります"
    confidence = adapter(text, expected_language="ja")
    assert confidence >= 0.6, f"expected ja confidence >= 0.6, got {confidence}"


def test_langdetect_adapter_short_text_zero() -> None:
    """Case 12: short text (< min_length=5 token) で confidence=0.0 強制 (non-CJK)."""
    adapter = LangdetectAdapter(min_length=5)
    assert adapter("hi", expected_language="de") == 0.0
    assert adapter("yes no", expected_language="en") == 0.0
    assert adapter("short text okay", expected_language="en") == 0.0  # 3 token


def test_langdetect_adapter_cjk_short_text_passes_threshold() -> None:
    """DPN20-2 #4: CJK 文字含む短文は token 数 short-circuit を skip する."""
    adapter = LangdetectAdapter(min_length=5)
    # 日本語短文 (空白なし、 token 数 1 だが CJK 文字含む) で 0.0 強制せず
    # detector へ流す → confidence > 0 が返る (ja として識別される)
    confidence = adapter("カント定言命法", expected_language="ja")
    assert confidence > 0.0, (
        f"CJK short text should bypass token-count gate, got {confidence}"
    )


def test_langdetect_adapter_factory_default() -> None:
    """make_langdetect_factory() で default LangdetectAdapter instance 返却."""
    detector = make_langdetect_factory()
    text = "Dies ist ein deutscher Satz mit hinreichender Länge"
    confidence = detector(text, expected_language="de")
    assert confidence >= 0.5


# ---------------------------------------------------------------------------
# MPNetNoveltyScorer integration tests
# ---------------------------------------------------------------------------


@_skip_real_mpnet
def test_mpnet_novelty_scorer_first_text_max() -> None:
    """Case 13a: first text (empty prior) で novelty=1.0 (max)."""
    scorer = MPNetNoveltyScorer(window_size=16)
    novelty = scorer("This is the first sentence in the scorer.")
    assert novelty == pytest.approx(1.0)


@_skip_real_mpnet
def test_mpnet_novelty_scorer_identical_low() -> None:
    """Case 13b: identical to prior で novelty 低い (~0)."""
    scorer = MPNetNoveltyScorer(window_size=16)
    text = "The categorical imperative is a moral principle."
    _ = scorer(text)  # prior に追加
    novelty = scorer(text)  # same text → cos≈1 → novelty≈0
    assert novelty < 0.1, f"identical text novelty should be ~0, got {novelty}"


@_skip_real_mpnet
def test_mpnet_novelty_scorer_different_topic_high() -> None:
    """Case 14: different topic で novelty 高い (~1)."""
    scorer = MPNetNoveltyScorer(window_size=16)
    _ = scorer("Mathematical proofs require rigorous logical inference.")
    novelty = scorer("Children play happily in the sunlit garden today.")
    # 異 topic embedding → cos ~ 0.2-0.5 → novelty ~ 0.5-0.8
    assert 0.3 < novelty < 1.2, f"different topic novelty range, got {novelty}"


@_skip_real_mpnet
def test_mpnet_novelty_scorer_reset() -> None:
    """DPN20-2 #3: reset() で prior buffer 空に、 model 不変保持 verify."""
    scorer = MPNetNoveltyScorer(window_size=4)
    _ = scorer("First sentence in scope A.")
    _ = scorer("Second sentence in scope A.")
    # reset() で scope 切替
    scorer.reset()
    novelty = scorer("First sentence in scope B.")
    # reset 後の first text は novelty=1.0 (max) であるべき
    assert novelty == pytest.approx(1.0)


@_skip_real_mpnet
def test_mpnet_novelty_scorer_factory_default() -> None:
    """make_mpnet_novelty_factory() で default MPNetNoveltyScorer instance 返却."""
    scorer = make_mpnet_novelty_factory(window_size=4)
    novelty = scorer("First text in factory test.")
    assert novelty == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# make_qc_filter + 実 factory end-to-end
# ---------------------------------------------------------------------------


@_skip_real_mpnet
def test_make_qc_filter_strict_real_factory_pass() -> None:
    """Case 15a: strict + 実 factory で 長い de 文字列 PASS."""
    qc_filter = make_qc_filter(
        "strict",
        language="de",
        language_detector=make_langdetect_factory(),
        novelty_scorer=make_mpnet_novelty_factory(window_size=4),
    )
    # 50+ token, langdetect ≥0.85 (de full sentence), first text novelty=1.0
    text = (
        "Die kategorischen Imperative von Immanuel Kant bilden die Grundlage"
        " seiner Moralphilosophie und prägen das deutsche Denken bis heute"
        " in vielfältiger Weise sowie in mehreren wissenschaftlichen Bereichen"
        " und kulturellen Strömungen weltweit erkennbar."
    )
    assert qc_filter(text) is True


@_skip_real_mpnet
def test_make_qc_filter_strict_real_factory_lang_fail() -> None:
    """Case 15b: strict + 実 factory で en 文字列を expected=de → lang FAIL."""
    qc_filter = make_qc_filter(
        "strict",
        language="de",
        language_detector=make_langdetect_factory(),
        novelty_scorer=make_mpnet_novelty_factory(window_size=4),
    )
    # en 文字列を expected=de で → langdetect が de confidence < 0.85 → FAIL
    text = (
        "The categorical imperative is a moral principle developed by"
        " Immanuel Kant in his foundational work on ethics, providing"
        " a universalizability test for maxims of action across many"
        " modern philosophical traditions and ongoing scholarship."
    )
    assert qc_filter(text) is False
