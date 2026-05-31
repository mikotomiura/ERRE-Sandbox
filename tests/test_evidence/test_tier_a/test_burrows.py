"""Burrows Delta unit tests — pure math against synthetic references.

Real corpus integration (Akademie-Ausgabe Kant, KGW Nietzsche, 利休百首)
lands in P1b; here we exercise the function-word z-score L1 distance
formula on synthetic profiles where the discriminative outcome is known
ahead of time.

Per Codex review HIGH-5 the metric is L1 (Manhattan) distance between
z-scored function-word frequency vectors — the cosine variant in the v1
sketch was rejected as not-Burrows. The persona-discriminative test
below also wires in the DB7 LOW-1 synthetic 4th persona heldout fixture
(``_synthetic_4th``) inline so we know we are not just memorising a
3-persona contrast.
"""

from __future__ import annotations

import math

import pytest

from erre_sandbox.evidence.tier_a.burrows import (
    BurrowsLanguageMismatchError,
    BurrowsReference,
    BurrowsTokenizationUnsupportedError,
    compute_burrows_delta,
)

# --- synthetic reference fixtures ----------------------------------------
#
# Five English function words with deliberately separated profile
# frequencies. Background mean and std are picked so each profile sits
# at a distinct z-score signature; the synthetic 4th persona occupies
# the "neutral on every word" corner so we can show the discriminative
# distance is not a 3-class artefact.

_FW = ("the", "of", "and", "to", "a")
_BG_MEAN = (0.05, 0.04, 0.03, 0.025, 0.02)
_BG_STD = (0.01, 0.01, 0.01, 0.01, 0.01)


def _ref(profile: tuple[float, ...]) -> BurrowsReference:
    return BurrowsReference(
        language="en",
        function_words=_FW,
        background_mean=_BG_MEAN,
        background_std=_BG_STD,
        profile_freq=profile,
    )


# Kant: heavy on "the" / "of" (the categorical/grammatical register)
_KANT = _ref(profile=(0.08, 0.07, 0.03, 0.02, 0.02))
# Nietzsche: heavy on "and" / "to" (more rhetorical chaining)
_NIETZSCHE = _ref(profile=(0.04, 0.03, 0.06, 0.05, 0.02))
# DB7 LOW-1 synthetic 4th persona: at background mean for every word
_SYNTH4 = _ref(profile=_BG_MEAN)


# --- core math -----------------------------------------------------------


def test_identical_profile_text_yields_zero_delta() -> None:
    # Construct a text whose observed frequencies exactly match the
    # Kant profile; Delta must collapse to 0.
    # 100 function-word tokens: 8 "the", 7 "of", 3 "and", 2 "to", 2 "a"
    # plus 78 filler tokens that aren't function words.
    tokens = (
        ["the"] * 8 + ["of"] * 7 + ["and"] * 3 + ["to"] * 2 + ["a"] * 2 + ["x"] * 78
    )
    delta = compute_burrows_delta(
        " ".join(tokens),
        _KANT,
        language="en",
    )
    assert delta == pytest.approx(0.0, abs=1e-9)


def test_empty_text_returns_nan() -> None:
    delta = compute_burrows_delta("", _KANT, language="en")
    assert math.isnan(delta)


def test_only_zero_std_words_returns_nan() -> None:
    zero_std_ref = BurrowsReference(
        language="en",
        function_words=("the", "of"),
        background_mean=(0.05, 0.04),
        background_std=(0.0, 0.0),
        profile_freq=(0.05, 0.04),
    )
    delta = compute_burrows_delta(
        "the of the of the",
        zero_std_ref,
        language="en",
    )
    assert math.isnan(delta)


def test_zero_std_words_skipped_but_others_counted() -> None:
    # Only the second word (std>0) should contribute; the first word
    # (std=0) is dropped from the sum.
    mixed_ref = BurrowsReference(
        language="en",
        function_words=("the", "of"),
        background_mean=(0.05, 0.04),
        background_std=(0.0, 0.01),
        profile_freq=(0.05, 0.04),
    )
    # 100-token text: 5 "the" (matches profile freq 0.05), 8 "of"
    # (0.08 vs profile 0.04 -> z_test = (0.08-0.04)/0.01 = 4.0, z_profile = 0).
    tokens = ["the"] * 5 + ["of"] * 8 + ["x"] * 87
    delta = compute_burrows_delta(
        " ".join(tokens),
        mixed_ref,
        language="en",
    )
    assert delta == pytest.approx(4.0, abs=1e-9)


def test_preprocessed_tokens_bypass_default_tokenizer() -> None:
    delta = compute_burrows_delta(
        "ignored",
        _KANT,
        language="en",
        preprocessed_tokens=["the"] * 8
        + ["of"] * 7
        + ["and"] * 3
        + ["to"] * 2
        + ["a"] * 2
        + ["x"] * 78,
    )
    assert delta == pytest.approx(0.0, abs=1e-9)


# --- contract violations ------------------------------------------------


def test_language_mismatch_raises() -> None:
    with pytest.raises(BurrowsLanguageMismatchError):
        compute_burrows_delta("der die das", _KANT, language="de")


def test_unsupported_language_without_preprocessed_tokens_raises() -> None:
    ja_ref = BurrowsReference(
        language="ja",
        function_words=("の", "に"),
        background_mean=(0.05, 0.04),
        background_std=(0.01, 0.01),
        profile_freq=(0.05, 0.04),
    )
    with pytest.raises(BurrowsTokenizationUnsupportedError):
        compute_burrows_delta("茶の湯の道", ja_ref, language="ja")


def test_unsupported_language_with_preprocessed_tokens_succeeds() -> None:
    ja_ref = BurrowsReference(
        language="ja",
        function_words=("の", "に"),
        background_mean=(0.05, 0.04),
        background_std=(0.01, 0.01),
        profile_freq=(0.05, 0.04),
    )
    # 100 tokens: 5 "の" (z_test = z_profile = 0), 4 "に" (z_test =
    # z_profile = 0), and 91 filler. Both function words match the
    # profile exactly, so Delta = 0.
    tokens = ["の"] * 5 + ["に"] * 4 + ["x"] * 91
    delta = compute_burrows_delta(
        "",
        ja_ref,
        language="ja",
        preprocessed_tokens=tokens,
    )
    assert delta == pytest.approx(0.0, abs=1e-9)


def test_mismatched_vector_lengths_raise() -> None:
    with pytest.raises(ValueError, match="equal length"):
        BurrowsReference(
            language="en",
            function_words=("the", "of"),
            background_mean=(0.05,),  # length 1, not 2
            background_std=(0.01, 0.01),
            profile_freq=(0.05, 0.04),
        )


def test_negative_std_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BurrowsReference(
            language="en",
            function_words=("the",),
            background_mean=(0.05,),
            background_std=(-0.01,),
            profile_freq=(0.05,),
        )


# --- persona-discriminative ---------------------------------------------


def _kant_like_text() -> str:
    # Heavy on "the" / "of" — matches Kant profile.
    tokens = (
        ["the"] * 8 + ["of"] * 7 + ["and"] * 3 + ["to"] * 2 + ["a"] * 2 + ["x"] * 78
    )
    return " ".join(tokens)


def _nietzsche_like_text() -> str:
    # Heavy on "and" / "to" — matches Nietzsche profile.
    tokens = (
        ["the"] * 4 + ["of"] * 3 + ["and"] * 6 + ["to"] * 5 + ["a"] * 2 + ["x"] * 80
    )
    return " ".join(tokens)


def test_kant_text_closer_to_kant_than_nietzsche_profile() -> None:
    text = _kant_like_text()
    d_kant = compute_burrows_delta(text, _KANT, language="en")
    d_nietzsche = compute_burrows_delta(text, _NIETZSCHE, language="en")
    # Discriminative gap >= 5.0 z-units across 5 function words is well
    # above measurement noise on a 100-token synthetic text.
    assert d_nietzsche - d_kant >= 5.0


def test_nietzsche_text_closer_to_nietzsche_than_kant_profile() -> None:
    text = _nietzsche_like_text()
    d_kant = compute_burrows_delta(text, _KANT, language="en")
    d_nietzsche = compute_burrows_delta(text, _NIETZSCHE, language="en")
    assert d_kant - d_nietzsche >= 5.0


def test_synthetic_4th_persona_distinct_from_both() -> None:
    # DB7 LOW-1 heldout: a 4th persona with a profile distinct from
    # the original two should produce a measurably different distance
    # for both Kant-like and Nietzsche-like texts. The contract is
    # only "non-zero distinguishability"; we don't claim a specific
    # ordering, since the synthetic 4th sits on the background mean.
    kant_text = _kant_like_text()
    nietzsche_text = _nietzsche_like_text()
    d_synth_kant_text = compute_burrows_delta(kant_text, _SYNTH4, language="en")
    d_synth_nietzsche_text = compute_burrows_delta(
        nietzsche_text,
        _SYNTH4,
        language="en",
    )
    # The 4th persona profile is at background mean; both texts move
    # off-mean enough to register a non-trivial distance.
    assert d_synth_kant_text > 1.0
    assert d_synth_nietzsche_text > 1.0
    # And the two distances should not be equal — otherwise the 4th
    # profile would be functionally indistinguishable across the two
    # discriminative texts.
    assert abs(d_synth_kant_text - d_synth_nietzsche_text) > 0.5
