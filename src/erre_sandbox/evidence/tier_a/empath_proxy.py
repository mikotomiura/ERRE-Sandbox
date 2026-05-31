"""Empath secondary diagnostic — psycholinguistic category vector.

Empath (Fast et al. 2016) is a deep-learning category lexicon that maps
text to ~200 affective / topical categories ("anger", "ritual",
"violence", ...). The M9 design uses Empath as **one Tier A axis**
among the five — a coarse signal of which themes a persona spends
words on, useful for descriptive contrast between Kant's "law" /
"order" / "duty" register and Nietzsche's "war" / "art" / "power"
register.

**Big5 claim is explicitly NOT made.** ME-1 in the design's
``decisions.md`` keeps Big5 self-report on IPIP-NEO via Tier B; using
Empath as a Big5 estimator was the v1 sketch and was rejected. The
secondary-diagnostic role lets the metric still earn its keep without
inheriting the LIWC-shaped problems Empath was originally critiqued
for.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

EmpathAnalyzer = Callable[[Sequence[str]], dict[str, float]]
"""Stub-friendly callable: take a list of utterances, return a category
score dict (category → mean / normalized intensity over the batch).

The single-callable boundary lets unit tests inject a deterministic
score map without spinning up the Empath lexicon (which downloads a
pickle on first use).
"""


def compute_empath_proxy(
    utterances: Sequence[str],
    *,
    analyzer: EmpathAnalyzer | None = None,
) -> dict[str, float]:
    """Return the Empath category-score vector aggregated over utterances.

    Args:
        utterances: Sequence of turn texts to analyse together. Empty
            input returns an empty dict; the caller is responsible for
            treating "no measurement" as it sees fit (Tier A
            aggregation typically drops empty maps before bootstrap).
        analyzer: Optional stub callable. When ``None`` the default
            Empath lexicon is lazily loaded; tests should always pass
            a stub to keep the lexicon download out of CI.

    Returns:
        Dict mapping Empath category name → score. Score units depend
        on the analyzer (the default returns normalized intensities in
        ``[0, 1]``); the metric layer treats this as opaque since the
        downstream Tier A consumer just ranks personas by category.
    """
    if not utterances:
        return {}
    fn = analyzer if analyzer is not None else _load_default_analyzer()
    return dict(fn(list(utterances)))


def _load_default_analyzer() -> EmpathAnalyzer:
    """Lazy-load the Empath lexicon and wrap ``analyze()`` as a callable.

    Heavy import deferred so importing this module without ``[eval]``
    extras stays free.
    """
    from empath import Empath  # noqa: PLC0415  # heavy data dep behind eval extras

    lex = Empath()

    def analyzer(batch: Sequence[str]) -> dict[str, float]:
        joined = " ".join(batch)
        # ``Empath.analyze`` returns ``Mapping[str, float] | None``;
        # an empty input or unknown vocabulary yields ``None``, which
        # we surface as an empty dict for type-stable callers.
        result = lex.analyze(joined, normalize=True)
        if result is None:
            return {}
        return {str(k): float(v) for k, v in result.items()}

    return analyzer
