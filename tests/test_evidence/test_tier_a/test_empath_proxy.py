"""Empath proxy unit tests — stub-based aggregation.

Heavy lexicon download is gated behind ``@pytest.mark.eval`` and not
exercised here. The metric layer is just a thin wrapper around an
analyzer callable, so we verify boundary handling (empty input,
empty analyzer output) and the explicit DB10 contract that this
metric does NOT make a Big5 claim.
"""

from __future__ import annotations

from collections.abc import Sequence

from erre_sandbox.evidence.tier_a.empath_proxy import compute_empath_proxy


def _stub_analyzer(scores: dict[str, float]):  # type: ignore[no-untyped-def]
    def analyzer(_batch: Sequence[str]) -> dict[str, float]:
        return scores

    return analyzer


def test_empty_utterances_returns_empty_dict() -> None:
    result = compute_empath_proxy(
        [],
        analyzer=_stub_analyzer({"anger": 0.5}),
    )
    assert result == {}


def test_stub_analyzer_passes_through() -> None:
    result = compute_empath_proxy(
        ["the cat sat"],
        analyzer=_stub_analyzer({"animal": 0.3, "rest": 0.1}),
    )
    assert result == {"animal": 0.3, "rest": 0.1}


def test_analyzer_returning_empty_dict_is_preserved() -> None:
    result = compute_empath_proxy(
        ["x"],
        analyzer=_stub_analyzer({}),
    )
    assert result == {}


def test_no_big5_axis_in_default_contract() -> None:
    # DB10 / ME-1: Empath is a Tier A psycholinguistic axis only;
    # using it as a Big5 estimator was rejected. The metric layer
    # MUST NOT inject Big5 trait names into the returned dict — it
    # only returns whatever the analyzer produced.
    result = compute_empath_proxy(
        ["dummy"],
        analyzer=_stub_analyzer({"anger": 0.2, "joy": 0.1}),
    )
    big5_axes = {
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    }
    assert big5_axes.isdisjoint(result.keys())


def test_persona_discriminative_category_gap() -> None:
    kant_scores = {"law": 0.8, "duty": 0.7, "violence": 0.05}
    nietzsche_scores = {"law": 0.1, "duty": 0.1, "violence": 0.6}
    kant_out = compute_empath_proxy(
        ["dummy"],
        analyzer=_stub_analyzer(kant_scores),
    )
    nietzsche_out = compute_empath_proxy(
        ["dummy"],
        analyzer=_stub_analyzer(nietzsche_scores),
    )
    # Discriminative direction matches the literary stereotype (Kant
    # weighted toward law/duty, Nietzsche toward violence/will-to-power).
    assert kant_out["law"] > nietzsche_out["law"]
    assert kant_out["duty"] > nietzsche_out["duty"]
    assert nietzsche_out["violence"] > kant_out["violence"]
