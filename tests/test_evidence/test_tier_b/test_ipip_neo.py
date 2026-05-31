"""Tests for ``erre_sandbox.evidence.tier_b.ipip_neo`` (M9-eval P4a).

Anti-demand-characteristics design (Codex P4a HIGH-4 / M9-eval ME-13) and
Japanese defer (HIGH-3 / ME-12) are pinned by the tests below.
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.tier_b.ipip_neo import (
    DEFAULT_LIKERT_MAX,
    DEFAULT_LIKERT_MIN,
    FORBIDDEN_KEYWORDS,
    IPIPDiagnostic,
    administer_ipip_neo,
    get_ipip_50_items,
    render_item_prompt,
)


def _constant_responder(value: int):
    """Return a responder that always replies with the same Likert digit."""

    def responder(_: str) -> int:
        return value

    return responder


def _alternating_responder():
    """Return a responder that alternates between Likert 1 and 5."""
    state = {"toggle": False}

    def responder(_: str) -> int:
        state["toggle"] = not state["toggle"]
        return DEFAULT_LIKERT_MAX if state["toggle"] else DEFAULT_LIKERT_MIN

    return responder


def test_get_ipip_50_items_returns_50_with_partial_reverse_keying() -> None:
    """Sanity: 50 items, 10 per dimension, at least one reverse-keyed item per dim.

    The official IPIP-50 (Goldberg 1992) is not perfectly balanced. The
    Neuroticism scale, for instance, has 8 forward-keyed items and only 2
    reverse-keyed items because the dimension is conventionally scored with
    "high N = high neuroticism" and there are simply more high-N descriptors
    in the official corpus. The test pins the *spec-as-shipped*, not an
    ad-hoc balance assumption.
    """
    items = get_ipip_50_items(language="en")
    assert len(items) == 50

    by_dim: dict[str, list[int]] = {}
    for item in items:
        by_dim.setdefault(item.dimension, []).append(item.sign)
    assert set(by_dim) == {"E", "A", "C", "N", "O"}
    for dim, signs in by_dim.items():
        assert len(signs) == 10, f"{dim} has {len(signs)} items"
        assert sum(1 for s in signs if s == +1) >= 2, (
            f"{dim} has fewer than 2 forward-keyed items"
        )
        assert sum(1 for s in signs if s == -1) >= 2, (
            f"{dim} has fewer than 2 reverse-keyed items"
            " (the IPIP-50 spec has N=2 reverse but every dim has >=2)"
        )


def test_administer_ipip_50_no_personality_keywords_in_prompt() -> None:
    """HIGH-4: no forbidden self-test keyword leaks into the rendered prompt."""
    items = get_ipip_50_items(language="en")
    for item in items:
        prompt = render_item_prompt(item).lower()
        for keyword in FORBIDDEN_KEYWORDS:
            assert keyword.lower() not in prompt, (
                f"forbidden keyword {keyword!r} leaked into prompt for item"
                f" {item.statement!r}"
            )


def test_administer_ipip_50_replay_determinism_under_same_seed() -> None:
    """temp=0 stub + same seed → identical Big5 + diagnostic across runs."""
    a_b5, a_diag = administer_ipip_neo(
        _constant_responder(3),
        seed=42,
        include_decoys=True,
    )
    b_b5, b_diag = administer_ipip_neo(
        _constant_responder(3),
        seed=42,
        include_decoys=True,
    )
    assert a_b5 == b_b5
    assert a_diag == b_diag


def test_administer_ipip_50_japanese_raises_not_implemented() -> None:
    """HIGH-3 / ME-12: language='ja' is explicitly deferred."""
    with pytest.raises(NotImplementedError, match="Japanese"):
        administer_ipip_neo(_constant_responder(3), language="ja")


def test_administer_ipip_50_unsupported_version_raises() -> None:
    """ME-12: only version='ipip-50' is supported in P4a."""
    with pytest.raises(NotImplementedError, match="not supported"):
        administer_ipip_neo(_constant_responder(3), version="mini-ipip-20")


def test_administer_ipip_50_constant_three_yields_three_per_dimension() -> None:
    """Reverse-keying contract: constant Likert 3 → all dimensions return 3.

    With Likert 3 across the board, reverse-keyed items also map to 3, so
    every dimension mean must be exactly 3.0 (the neutral midpoint).
    """
    big5, _ = administer_ipip_neo(_constant_responder(3), seed=7, include_decoys=False)
    assert big5.extraversion == pytest.approx(3.0)
    assert big5.agreeableness == pytest.approx(3.0)
    assert big5.conscientiousness == pytest.approx(3.0)
    assert big5.neuroticism == pytest.approx(3.0)
    assert big5.openness == pytest.approx(3.0)
    assert big5.n_items == 50
    assert big5.version == "ipip-50"


def test_administer_ipip_50_diagnostic_straight_line_detects_constant() -> None:
    """HIGH-4 diagnostic: constant responder must surface high straight-line runs."""
    _, diag = administer_ipip_neo(
        _constant_responder(5),
        seed=0,
        include_decoys=True,
    )
    assert isinstance(diag, IPIPDiagnostic)
    # 50 IPIP items + 5 decoys, all the same Likert → run length = 55
    assert diag.straight_line_runs >= 50
    # Acquiescence: maximally-biased toward 5 → mean abs deviation from 3 = 2
    assert diag.acquiescence_index == pytest.approx(2.0, abs=1e-6)


def test_administer_ipip_50_decoy_consistency_zero_for_neutral() -> None:
    """HIGH-4 decoy diagnostic: Likert 3 on decoys → consistency 0 (unbiased)."""
    _, diag = administer_ipip_neo(_constant_responder(3), seed=11)
    assert diag.decoy_consistency == pytest.approx(0.0, abs=1e-6)


def test_administer_ipip_50_decoy_consistency_high_for_biased_responder() -> None:
    """HIGH-4: Likert 5 on decoys → consistency 1.0 (maximally biased)."""
    _, diag = administer_ipip_neo(_constant_responder(5), seed=11)
    assert diag.decoy_consistency == pytest.approx(1.0, abs=1e-6)


def test_administer_ipip_50_alternating_diagnostic_breaks_straight_lines() -> None:
    """Sanity: alternating 1/5 → straight-line runs == 1, decoy biased toward 3."""
    _, diag = administer_ipip_neo(_alternating_responder(), seed=3)
    assert diag.straight_line_runs == 1
    # Mean of alternating 1/5 → 3 ± a half-step depending on parity → ~0
    assert diag.decoy_consistency <= 0.34
