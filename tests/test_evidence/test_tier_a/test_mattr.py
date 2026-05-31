"""MATTR unit tests — pure math.

Cover the empty / short / long / boundary cases for the sliding-window
type-token ratio. Persona-discriminative claim is just "vocabulary
breadth differs" — exercised here via a synthetic high-diversity
sequence vs a synthetic repetition sequence.
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.tier_a.mattr import (
    DEFAULT_WINDOW,
    compute_mattr,
)


def test_empty_text_returns_none() -> None:
    assert compute_mattr("") is None
    assert compute_mattr("   ") is None


def test_short_text_falls_back_to_plain_ttr() -> None:
    text = "alpha beta gamma alpha"  # 4 tokens, 3 unique
    result = compute_mattr(text)
    assert result == pytest.approx(3 / 4)


def test_pure_repetition_yields_low_mattr() -> None:
    text = " ".join(["alpha"] * 200)
    result = compute_mattr(text)
    # Window of 100 tokens, all identical → 1 unique / 100 = 0.01
    assert result == pytest.approx(0.01)


def test_pure_novelty_yields_unit_mattr() -> None:
    text = " ".join(f"w{i}" for i in range(200))
    result = compute_mattr(text)
    assert result == pytest.approx(1.0)


def test_window_size_changes_signal() -> None:
    # 200 tokens, alternating between 10 unique types → at window=10
    # every window saturates with 10 types → ratio=1.0; at window=100
    # ratio is still 10/100=0.1.
    cycle = [f"t{i}" for i in range(10)]
    text = " ".join(cycle * 20)
    narrow = compute_mattr(text, window=10)
    wide = compute_mattr(text, window=100)
    assert narrow == pytest.approx(1.0)
    assert wide == pytest.approx(0.1)


def test_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        compute_mattr("a b c", window=0)


def test_default_window_is_100() -> None:
    # Public constant should not silently drift; it is part of the
    # cross-tier comparability contract for Tier A vs Tier B Vendi.
    assert DEFAULT_WINDOW == 100


def test_persona_discriminative_diversity_gap() -> None:
    # "Kant-like" tight register: 30 unique words cycled.
    kant_tokens = [f"k{i}" for i in range(30)] * 5  # 150 tokens
    # "Nietzsche-like" broader register: 100 unique words cycled.
    nietzsche_tokens = [f"n{i}" for i in range(100)] * 2  # 200 tokens
    kant_mattr = compute_mattr(" ".join(kant_tokens))
    nietzsche_mattr = compute_mattr(" ".join(nietzsche_tokens))
    assert kant_mattr is not None
    assert nietzsche_mattr is not None
    assert nietzsche_mattr > kant_mattr
    # Signal gap should be substantial on synthetic input — not just
    # a noise-level rounding difference.
    assert nietzsche_mattr - kant_mattr > 0.1
