"""Zero-shot NLI contradiction over (premise, hypothesis) pairs.

The Tier A NLI metric quantifies whether a persona contradicts itself
across consecutive turns or stated commitments. The default model is
``MoritzLaurer/DeBERTa-v3-base-mnli`` — small enough (~140 MB) to load
on the Mac side without GPU pressure, accurate enough to produce a
useful contradiction probability for short philosophical exchanges.

Tests stub the heavy model via the ``scorer`` keyword, so the unit
tests exercise the aggregation logic without pulling
``transformers`` into resolution. Real-model integration tests live
behind ``@pytest.mark.eval`` and only run with ``--extra eval``
installed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

NLIScorer = Callable[[Sequence[tuple[str, str]]], list[float]]
"""Stub-friendly callable shape: take ``(premise, hypothesis)`` pairs and
return per-pair contradiction probability in ``[0, 1]``.

Wrapping the model in a callable rather than depending on the concrete
``transformers.Pipeline`` API keeps unit tests free of the heavy ML
import and lets future spikes swap in alternative NLI heads
(BIG5-CHAT regression head fallback, multilingual NLI) without
touching the metric aggregation code.
"""


def compute_nli_contradiction(
    pairs: Sequence[tuple[str, str]],
    *,
    scorer: NLIScorer | None = None,
) -> float | None:
    """Mean contradiction probability across the supplied pairs.

    Args:
        pairs: Sequence of ``(premise, hypothesis)`` strings — typically
            consecutive utterances by the same persona, or a stated
            principle vs. a later application of it.
        scorer: Optional stub callable. When ``None`` the default
            DeBERTa-v3-base-mnli pipeline is lazily loaded; tests
            should always pass a stub to avoid the model download.

    Returns:
        ``None`` when ``pairs`` is empty (no measurement possible).
        Otherwise the mean contradiction probability across pairs.
    """
    if not pairs:
        return None
    fn = scorer if scorer is not None else _load_default_scorer()
    probs = list(fn(pairs))
    if not probs:
        return None
    return sum(probs) / len(probs)


def _load_default_scorer() -> NLIScorer:
    """Lazy-load the default DeBERTa-v3-base-mnli zero-shot pipeline.

    Heavy imports stay function-local so that the project is importable
    without ``[eval]`` extras (``transformers`` resolution is then
    skipped). ``# noqa: PLC0415`` is the project-wide pattern for this.
    """
    from transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        pipeline,
    )

    pipe = pipeline(
        "zero-shot-classification",
        model="MoritzLaurer/DeBERTa-v3-base-mnli",
    )
    candidate_labels = ["contradiction", "neutral", "entailment"]

    def scorer(pairs: Sequence[tuple[str, str]]) -> list[float]:
        out: list[float] = []
        for premise, hypothesis in pairs:
            # The "[SEP]" join is the convention DeBERTa-v3-base-mnli
            # was trained with; it lets the zero-shot head treat the
            # pair as a single sequence whose label space is the three
            # NLI classes above.
            joined = f"{premise} [SEP] {hypothesis}"
            result = pipe(joined, candidate_labels=candidate_labels)
            scores = dict(zip(result["labels"], result["scores"], strict=True))
            out.append(float(scores.get("contradiction", 0.0)))
        return out

    return scorer
