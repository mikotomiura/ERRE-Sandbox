"""Unit tests for ``erre_sandbox.training.qc_detectors`` (PR-20 DPN20-0 Hybrid C+A).

stub 中心 unit test (CI base 環境で PASS、 langdetect / sentence_transformers
依存なし)。 実 detector の integration test は
``test_qc_detectors_real.py`` (importorskip gated) に分離。

Covers:

* :class:`LanguageDetectorProtocol` contract (stub で fixed return、 4 軸 QC
  の language 軸入力)
* :class:`NoveltyScorerProtocol` contract (stub で fixed return、 4 軸 QC
  の novelty 軸入力)
* :func:`make_qc_filter` factory injection (DPN20-0 wire-in pattern、
  back-compat factory=None default no-op verify)
"""

from __future__ import annotations

import pytest

from erre_sandbox.training.gated_burrows_reward import (
    LanguageDetectorProtocol,
    NoveltyScorerProtocol,
    make_qc_filter,
)

# ---------------------------------------------------------------------------
# LanguageDetectorProtocol contract (stub-based)
# ---------------------------------------------------------------------------


class _FixedConfidenceDetector:
    """Stub LanguageDetectorProtocol: return fixed confidence for matching lang."""

    def __init__(self, *, lang_confidences: dict[str, float]) -> None:
        self._lang_confidences = lang_confidences

    def __call__(self, text: str, *, expected_language: str) -> float:  # noqa: ARG002
        return self._lang_confidences.get(expected_language, 0.0)


def test_language_detector_protocol_ja_passes() -> None:
    """Case 1: ja text で expected_language=ja の confidence ≥ threshold."""
    detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"ja": 0.95},
    )
    assert detector(
        "これは日本語のテストです", expected_language="ja"
    ) == pytest.approx(0.95)


def test_language_detector_protocol_en_passes() -> None:
    """Case 2: en text で expected_language=en の confidence ≥ threshold."""
    detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"en": 0.92},
    )
    assert detector("this is an english test sentence", expected_language="en") == (
        pytest.approx(0.92)
    )


def test_language_detector_protocol_de_passes() -> None:
    """Case 3: de text で expected_language=de の confidence ≥ threshold."""
    detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.88},
    )
    assert detector(
        "Dies ist ein deutscher Testsatz mit ausreichender Länge",
        expected_language="de",
    ) == pytest.approx(0.88)


def test_language_detector_protocol_unknown_fails() -> None:
    """Case 4: unknown text (= detector が 0.0 を返す path) で QC FAIL trigger."""
    detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={},  # 全 lang 0.0
    )
    assert detector("random gibberish xyz qwerty", expected_language="de") == 0.0


def test_language_detector_protocol_short_string_zero() -> None:
    """Case 5: short string (1-2 token) で confidence=0.0 強制 (fragile 防止)."""

    class _ShortRejectingDetector:
        def __call__(self, text: str, *, expected_language: str) -> float:  # noqa: ARG002
            return 0.0 if len(text.split()) < 5 else 0.9

    detector: LanguageDetectorProtocol = _ShortRejectingDetector()
    assert detector("hi", expected_language="de") == 0.0
    assert detector(
        "this is a longer sentence", expected_language="de"
    ) == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# NoveltyScorerProtocol contract (stub-based)
# ---------------------------------------------------------------------------


class _FixedNoveltyScorer:
    """Stub NoveltyScorerProtocol: return fixed novelty score."""

    def __init__(self, *, score: float) -> None:
        self._score = score

    def __call__(self, text: str) -> float:  # noqa: ARG002
        return self._score


def test_novelty_scorer_identical_to_prior_low() -> None:
    """Case 6: identical to prior で novelty ≈ 0."""
    scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.05)
    assert scorer("repeated text") == pytest.approx(0.05)


def test_novelty_scorer_paraphrase_mid() -> None:
    """Case 7: paraphrase で novelty 中間値."""
    scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.5)
    assert scorer("paraphrased text") == pytest.approx(0.5)


def test_novelty_scorer_different_topic_high() -> None:
    """Case 8: different topic で novelty ≈ 1."""
    scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.95)
    assert scorer("completely different topic") == pytest.approx(0.95)


def test_novelty_scorer_empty_prior_max() -> None:
    """Case 9: empty prior (first text) で novelty=1.0."""
    scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=1.0)
    assert scorer("first text seen") == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# make_qc_filter factory injection + back-compat
# ---------------------------------------------------------------------------


def test_make_qc_filter_factory_none_back_compat_no_op() -> None:
    """Case 10: factory=None で default no-op (= PR-18 完全同等).

    DPN20-0 binding: ``make_qc_filter()`` の ``language_detector=None`` +
    ``novelty_scorer=None`` 経路は PR-18 の既存挙動 (langdetect / novelty
    軸が常に 1.0 を返す = 常に PASS) と完全一致。 既存 PR-18 retrain
    artefact の forensic chain を 1 行も曲げない strict back-compat。
    """
    # loose level で wire-in なしの場合: langdetect / novelty 軸は default no-op、
    # length (>=20) + repetition (<0.5) のみ effective
    qc_filter = make_qc_filter("loose", language="de")
    # 20+ token + low repetition の de 風 text は PASS
    long_text = " ".join([f"word{i}" for i in range(25)])  # 25 unique tokens
    assert qc_filter(long_text) is True
    # 19 token (length FAIL)
    short_text = " ".join([f"word{i}" for i in range(19)])
    assert qc_filter(short_text) is False


def test_make_qc_filter_with_stub_factory_strict_4_axes() -> None:
    """Bonus case: strict level + stub factory で 4 軸全 active 動作確認."""
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.9},
    )
    novelty_scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.6)
    qc_filter = make_qc_filter(
        "strict",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=novelty_scorer,
    )
    # 50+ token + low repetition + lang 0.9 (>=0.85) + novelty 0.6 (>=0.5) → PASS
    long_text = " ".join([f"word{i}" for i in range(55)])
    assert qc_filter(long_text) is True

    # lang 0.0 (FAIL) detector で trigger
    fail_lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={},
    )
    qc_filter_lang_fail = make_qc_filter(
        "strict",
        language="de",
        language_detector=fail_lang_detector,
        novelty_scorer=novelty_scorer,
    )
    assert qc_filter_lang_fail(long_text) is False

    # novelty 0.3 (FAIL strict>=0.5) で trigger
    low_novelty_scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.3)
    qc_filter_novelty_fail = make_qc_filter(
        "strict",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=low_novelty_scorer,
    )
    assert qc_filter_novelty_fail(long_text) is False


def test_make_qc_filter_with_stub_factory_loose_3_axes_novelty_no_op() -> None:
    """DPN20-0 Hybrid C+A: loose で novelty=0.0 effective no-op verify."""
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.7},
    )
    # loose で novelty=0.0 (= effective no-op) を返す stub
    no_op_novelty: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.0)
    qc_filter = make_qc_filter(
        "loose",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=no_op_novelty,
    )
    # 20+ token + lang 0.7 (>=0.6) + novelty 0.0 (>= loose's 0.0) → PASS
    # = loose で novelty 軸が effective no-op であることを verify
    long_text = " ".join([f"wort{i}" for i in range(25)])
    assert qc_filter(long_text) is True


# ---------------------------------------------------------------------------
# Codex HIGH-1 反映: loose level で novelty_scorer を call しない短絡 verify
# ---------------------------------------------------------------------------


class _RaisingNoveltyScorer:
    """Stub scorer that raises if called (HIGH-1 short-circuit verify)."""

    def __init__(self) -> None:
        self.called: int = 0

    def __call__(self, text: str) -> float:  # noqa: ARG002
        self.called += 1
        msg = "novelty_scorer should not be called for loose level"
        raise AssertionError(msg)


def test_make_qc_filter_loose_short_circuits_novelty_call() -> None:
    """HIGH-1: loose (min_semantic_novelty=0.0) では novelty_scorer 呼ばれない.

    `QcFilterCallable.__call__()` は `min_semantic_novelty <= 0.0` で
    early return = True (novelty axis short-circuit)。 MPNet model load /
    stateful prior buffer 更新を loose では完全回避することを verify。
    """
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.7},
    )
    raising_scorer = _RaisingNoveltyScorer()
    qc_filter = make_qc_filter(
        "loose",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=raising_scorer,
    )
    long_text = " ".join([f"wort{i}" for i in range(25)])
    # loose で novelty が呼ばれないため、 raising stub でも AssertionError 起きず PASS
    assert qc_filter(long_text) is True
    assert raising_scorer.called == 0


def test_make_qc_filter_strict_calls_novelty_normally() -> None:
    """strict (min_semantic_novelty=0.5) では novelty_scorer 通常呼出される.

    HIGH-1 短絡が strict には影響しないことを反証。
    """
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.9},
    )
    novelty_scorer: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.6)
    qc_filter = make_qc_filter(
        "strict",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=novelty_scorer,
    )
    long_text = " ".join([f"wort{i}" for i in range(55)])
    assert qc_filter(long_text) is True


# ---------------------------------------------------------------------------
# Codex HIGH-2 反映: reset_state() per-triple binding verify
# ---------------------------------------------------------------------------


class _StatefulNoveltyScorerWithReset:
    """Stub scorer with reset(): track reset call count for HIGH-2 verify."""

    def __init__(self, *, score: float) -> None:
        self._score = score
        self.reset_count: int = 0
        self.call_count: int = 0

    def __call__(self, text: str) -> float:  # noqa: ARG002
        self.call_count += 1
        return self._score

    def reset(self) -> None:
        self.reset_count += 1


def test_qc_filter_callable_reset_state_calls_scorer_reset() -> None:
    """HIGH-2: QcFilterCallable.reset_state() が novelty_scorer.reset() を呼ぶ.

    stateful scorer (MPNetNoveltyScorer 等) の rolling prior buffer を
    per-pair/triple scope の境界で reset する API contract を verify。
    """
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.9},
    )
    stateful_scorer = _StatefulNoveltyScorerWithReset(score=0.8)
    qc_filter = make_qc_filter(
        "strict",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=stateful_scorer,
    )
    assert stateful_scorer.reset_count == 0
    qc_filter.reset_state()
    assert stateful_scorer.reset_count == 1
    qc_filter.reset_state()
    assert stateful_scorer.reset_count == 2


def test_qc_filter_callable_reset_state_no_op_on_stateless() -> None:
    """HIGH-2: reset() を持たない scorer では reset_state() が no-op."""
    lang_detector: LanguageDetectorProtocol = _FixedConfidenceDetector(
        lang_confidences={"de": 0.7},
    )
    stateless: NoveltyScorerProtocol = _FixedNoveltyScorer(score=0.0)
    qc_filter = make_qc_filter(
        "loose",
        language="de",
        language_detector=lang_detector,
        novelty_scorer=stateless,
    )
    # reset() が無い scorer でも exception なく no-op
    qc_filter.reset_state()  # no-op
    qc_filter.reset_state()
