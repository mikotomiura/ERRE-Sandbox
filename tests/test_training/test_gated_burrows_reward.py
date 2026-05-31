"""Unit tests for ``erre_sandbox.training.gated_burrows_reward`` (PR-18 Phase 3).

Covers:

* :data:`THRESHOLD_TABLE` — DPN18-0 A 確定値 (none / loose / strict)。
* :func:`count_tokens` + :func:`compute_repetition_ratio` — pure-Python sub-check。
* :func:`make_qc_filter` — 4 軸 (length / language / repetition / novelty) の
  threshold-aware QC filter assembly。
* :func:`compute_gated_burrows_reward` — QC PASS 時 reduction%、 FAIL 時 -inf。

すべて pure Python (default 経路)、 langdetect / sentence-transformers
依存なし (callable injection で skip 可能)。
"""

from __future__ import annotations

import math

import pytest

from erre_sandbox.training.gated_burrows_reward import (
    THRESHOLD_TABLE,
    QcFilterCallable,
    QcThresholds,
    compute_gated_burrows_reward,
    compute_repetition_ratio,
    count_tokens,
    make_qc_filter,
)

# ---------------------------------------------------------------------------
# THRESHOLD_TABLE invariants (DPN18-0 A binding)
# ---------------------------------------------------------------------------


def test_threshold_table_contains_all_three_levels() -> None:
    assert set(THRESHOLD_TABLE.keys()) == {"none", "loose", "strict"}


def test_threshold_table_none_is_permissive_passthrough() -> None:
    none = THRESHOLD_TABLE["none"]
    assert none.min_token_length == 0
    assert none.min_language_confidence == 0.0
    assert none.max_repetition_ratio == 1.0
    assert none.min_semantic_novelty == 0.0


def test_threshold_table_loose_matches_dpn20_0_hybrid_c_a() -> None:
    """DPN20-0 Hybrid C+A 採用後の loose final form.

    PR-18 DPN18-0 A 原案 = novelty>=0.3 だったが、 DPN20-0 で
    Hybrid C+A 採用 → loose の novelty 軸を effective no-op (>=0.0) へ
    refine。 forensic 上 「length+repetition+langdetect-only loose」 と整合化。
    """
    loose = THRESHOLD_TABLE["loose"]
    assert loose.min_token_length == 20
    assert loose.min_language_confidence == pytest.approx(0.6)
    assert loose.max_repetition_ratio == pytest.approx(0.5)
    assert loose.min_semantic_novelty == pytest.approx(0.0)  # DPN20-0 refine


def test_threshold_table_strict_matches_dpn18_0_a() -> None:
    strict = THRESHOLD_TABLE["strict"]
    assert strict.min_token_length == 50
    assert strict.min_language_confidence == pytest.approx(0.85)
    assert strict.max_repetition_ratio == pytest.approx(0.3)
    assert strict.min_semantic_novelty == pytest.approx(0.5)


def test_threshold_table_strict_dominates_loose_dominates_none() -> None:
    none = THRESHOLD_TABLE["none"]
    loose = THRESHOLD_TABLE["loose"]
    strict = THRESHOLD_TABLE["strict"]
    assert none.min_token_length <= loose.min_token_length <= strict.min_token_length
    assert (
        none.min_language_confidence
        <= loose.min_language_confidence
        <= strict.min_language_confidence
    )
    assert (
        none.max_repetition_ratio
        >= loose.max_repetition_ratio
        >= strict.max_repetition_ratio
    )
    assert (
        none.min_semantic_novelty
        <= loose.min_semantic_novelty
        <= strict.min_semantic_novelty
    )


# ---------------------------------------------------------------------------
# pure-Python sub-checks
# ---------------------------------------------------------------------------


def test_count_tokens_simple() -> None:
    assert count_tokens("der die das") == 3
    assert count_tokens("") == 0
    assert count_tokens("   spaces   only   ") == 2


def test_compute_repetition_ratio_zero_for_short_text() -> None:
    # tokens < n=3
    assert compute_repetition_ratio("der die", n=3) == 0.0
    assert compute_repetition_ratio("", n=3) == 0.0


def test_compute_repetition_ratio_zero_for_unique_ngrams() -> None:
    text = "a b c d e f"  # 4 unique 3-grams, 0 repeated
    assert compute_repetition_ratio(text, n=3) == 0.0


def test_compute_repetition_ratio_high_for_repeated_text() -> None:
    text = "a b c a b c a b c"  # repeats "a b c" three times
    ratio = compute_repetition_ratio(text, n=3)
    assert ratio > 0.5


def test_compute_repetition_ratio_n_parameter_respected() -> None:
    text = "a b c d e f"
    # n=2 で 5 bigram、 全 unique
    assert compute_repetition_ratio(text, n=2) == 0.0


# ---------------------------------------------------------------------------
# make_qc_filter — level "none" は常に PASS
# ---------------------------------------------------------------------------


def test_qc_filter_none_passes_all_text() -> None:
    qc = make_qc_filter("none")
    assert qc("anything") is True
    assert qc("der") is True
    assert qc("") is True  # min_token_length=0 → empty も PASS


def test_qc_filter_unknown_level_raises() -> None:
    with pytest.raises(ValueError, match=r"unknown level"):
        make_qc_filter("medium")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# make_qc_filter — length check
# ---------------------------------------------------------------------------


def test_qc_filter_loose_rejects_short_text() -> None:
    qc = make_qc_filter("loose")
    short = "ein zwei drei vier"  # 4 tokens < 20
    assert qc(short) is False


def test_qc_filter_loose_passes_long_text() -> None:
    # 25 tokens, 全 unique → length + repetition + default langdetect / novelty
    long_text = " ".join([f"token{i}" for i in range(25)])
    qc = make_qc_filter("loose")
    assert qc(long_text) is True


def test_qc_filter_strict_requires_50_tokens() -> None:
    qc = make_qc_filter("strict")
    text_30 = " ".join([f"token{i}" for i in range(30)])
    text_60 = " ".join([f"token{i}" for i in range(60)])
    assert qc(text_30) is False
    assert qc(text_60) is True


# ---------------------------------------------------------------------------
# make_qc_filter — repetition check
# ---------------------------------------------------------------------------


def test_qc_filter_loose_rejects_high_repetition() -> None:
    qc = make_qc_filter("loose")
    # 20+ tokens で repetition > 0.5
    pattern = "a b c " * 10  # = 30 tokens, 28 3-grams、 ほぼ全部 repeated
    assert qc(pattern) is False


# ---------------------------------------------------------------------------
# make_qc_filter — language detector injection
# ---------------------------------------------------------------------------


def test_qc_filter_loose_rejects_low_language_confidence() -> None:
    def low_conf_detector(text: str, *, expected_language: str) -> float:  # noqa: ARG001
        return 0.3  # < 0.6 (loose threshold)

    text = " ".join([f"token{i}" for i in range(25)])
    qc = make_qc_filter("loose", language_detector=low_conf_detector)
    assert qc(text) is False


def test_qc_filter_strict_requires_higher_language_confidence() -> None:
    def mid_conf_detector(text: str, *, expected_language: str) -> float:  # noqa: ARG001
        return 0.7  # >= loose 0.6, < strict 0.85

    text = " ".join([f"token{i}" for i in range(60)])
    qc_loose = make_qc_filter("loose", language_detector=mid_conf_detector)
    qc_strict = make_qc_filter("strict", language_detector=mid_conf_detector)
    assert qc_loose(text) is True
    assert qc_strict(text) is False


# ---------------------------------------------------------------------------
# make_qc_filter — novelty scorer injection
# ---------------------------------------------------------------------------


def test_qc_filter_strict_rejects_low_novelty() -> None:
    """DPN20-0 Hybrid C+A: novelty 軸 effective は strict のみ (loose で no-op).

    PR-18 では loose.novelty=0.3 で effective、 PR-20 refine 後は loose.novelty=0.0
    (= effective no-op、 caveat ③ wording 整合)。 novelty 軸 effective verify は
    strict (novelty>=0.5) で行う。
    """

    def low_novelty(_text: str) -> float:
        return 0.3  # < strict 0.5

    # strict は length>=50 + lang>=0.85、 ここでは pass する設定で novelty 軸のみ FAIL
    text = " ".join([f"token{i}" for i in range(55)])  # 55 tokens >= 50

    def high_lang(_text: str, *, expected_language: str) -> float:  # noqa: ARG001
        return 0.9  # >= strict 0.85

    qc = make_qc_filter(
        "strict",
        novelty_scorer=low_novelty,
        language_detector=high_lang,
    )
    assert qc(text) is False


def test_qc_filter_loose_novelty_axis_effective_no_op_dpn20_0() -> None:
    """DPN20-0 Hybrid C+A binding: loose で novelty 軸が effective no-op."""

    def low_novelty(_text: str) -> float:
        return 0.0  # 過去 PR-18 では loose 0.3 で FAIL、 PR-20 では loose 0.0 で PASS

    def high_lang(_text: str, *, expected_language: str) -> float:  # noqa: ARG001
        return 0.7  # >= loose 0.6

    text = " ".join([f"token{i}" for i in range(25)])  # 25 tokens >= 20
    qc = make_qc_filter(
        "loose",
        novelty_scorer=low_novelty,
        language_detector=high_lang,
    )
    # loose では novelty>=0.0 なので 0.0 でも PASS = DPN20-0 refine verify
    assert qc(text) is True


# ---------------------------------------------------------------------------
# compute_gated_burrows_reward
# ---------------------------------------------------------------------------


def test_compute_gated_burrows_reward_qc_fail_returns_neg_inf() -> None:
    qc = make_qc_filter("strict")  # 50 token 必須
    reward = compute_gated_burrows_reward(
        "kurz text",
        qc_filter=qc,
        burrows_delta_text=1.0,
        burrows_delta_baseline=2.0,
    )
    assert reward == float("-inf")


def test_compute_gated_burrows_reward_qc_pass_returns_reduction_pct() -> None:
    qc = make_qc_filter("none")  # passthrough
    # baseline=2.0 → text=1.0 = 50% reduction
    reward = compute_gated_burrows_reward(
        "anything",
        qc_filter=qc,
        burrows_delta_text=1.0,
        burrows_delta_baseline=2.0,
    )
    assert reward == pytest.approx(50.0)


def test_compute_gated_burrows_reward_returns_nan_for_zero_baseline() -> None:
    qc = make_qc_filter("none")
    reward = compute_gated_burrows_reward(
        "anything",
        qc_filter=qc,
        burrows_delta_text=1.0,
        burrows_delta_baseline=0.0,
    )
    assert math.isnan(reward)


def test_compute_gated_burrows_reward_negative_for_worse_text() -> None:
    qc = make_qc_filter("none")
    # text=3.0 > baseline=2.0 → reduction% < 0 (悪化)
    reward = compute_gated_burrows_reward(
        "anything",
        qc_filter=qc,
        burrows_delta_text=3.0,
        burrows_delta_baseline=2.0,
    )
    assert reward == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# QcFilterCallable dataclass
# ---------------------------------------------------------------------------


def test_qc_filter_callable_immutability() -> None:
    qc = make_qc_filter("loose")
    assert isinstance(qc, QcFilterCallable)
    with pytest.raises((AttributeError, TypeError)):
        qc.language = "en"  # type: ignore[misc]


def test_qc_thresholds_immutability() -> None:
    t = QcThresholds(
        min_token_length=10,
        min_language_confidence=0.5,
        max_repetition_ratio=0.5,
        min_semantic_novelty=0.3,
    )
    with pytest.raises((AttributeError, TypeError)):
        t.min_token_length = 20  # type: ignore[misc]
