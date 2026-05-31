"""Moving Average Type-Token Ratio (MATTR) — lexical diversity metric.

MATTR (Covington & McFall 2010) sidesteps the well-known bias of plain
TTR against text length by averaging the type-token ratio of every
window of fixed size as the window slides across the token stream.
The persona-discriminative claim in the M9 design is that thinkers
with broader vocabularies (Nietzsche) sustain a higher MATTR than
thinkers with a tight technical jargon set (Kant) at the same window
size.

Window size 100 is the literature default and matches what the
Vendi-vs-MATTR Tier B comparison expects; if a future spike wants to
tune it the parameter is exposed but pinned per-run for fairness.
"""

from __future__ import annotations

DEFAULT_WINDOW: int = 100
"""Default sliding window size in tokens.

Covington & McFall (2010) recommend 100 tokens as the empirical sweet
spot — small enough to retain locality, large enough to absorb the
"first-token-of-a-window" novelty noise that drives plain TTR to 1.0
on short snippets.
"""


def compute_mattr(
    text: str,
    *,
    window: int = DEFAULT_WINDOW,
) -> float | None:
    """Mean type-token ratio over sliding windows of ``window`` tokens.

    Args:
        text: Whitespace-separated text. The same naive tokeniser as
            :mod:`erre_sandbox.evidence.metrics` is used so the M8
            baseline metric and the M9 Tier A metric line up at the
            tokenisation layer (consistent inputs to a consistent
            stylometric question).
        window: Sliding window size in tokens. Must be ``>= 1``;
            defaults to :data:`DEFAULT_WINDOW`.

    Returns:
        ``None`` when the text is empty (no measurement possible).
        Otherwise the mean window TTR. When the text is shorter than
        ``window`` the function falls back to plain TTR over all tokens
        — the M8 ``compute_*`` contract treats short runs as
        "best-effort, not NaN" so downstream bootstrap-CI sees a usable
        number rather than a spurious gap.

    Raises:
        ValueError: If ``window < 1``.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1 (got {window})")
    tokens = text.split()
    if not tokens:
        return None
    n = len(tokens)
    if n <= window:
        return len(set(tokens)) / n

    ratios: list[float] = []
    for i in range(n - window + 1):
        chunk = tokens[i : i + window]
        ratios.append(len(set(chunk)) / window)
    return sum(ratios) / len(ratios)
