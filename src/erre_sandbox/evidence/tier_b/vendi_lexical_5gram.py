"""Vendi lexical 5-gram kernel — TF-IDF character n-gram cosine for Plan B.

m9-c-adopt Plan B D-2 allowlist primary encoder (see
``.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json``).
Provides a retrieval-trained free, language-agnostic shallow stylometry kernel
for the encoder agreement axis (3-of-4 majority direction discipline).

The kernel computes character 5-grams (``analyzer="char_wb"``) with TF-IDF
weighting then takes pairwise cosine similarity. This is **distinct from**
``vendi.make_lexical_5gram_kernel`` (Jaccard over set-of-5-grams):

* ``vendi.make_lexical_5gram_kernel`` — Jaccard, P4b sensitivity panel
  (kept for ME-10 continuity).
* ``vendi_lexical_5gram.make_tfidf_5gram_cosine_kernel`` — TF-IDF cosine,
  Plan B D-2 primary (this module).

Both are retrieval-trained-free by design (Codex MEDIUM-2 / Plan B DI-4 anti-
retrieval-artefact rationale). The TF-IDF cosine variant down-weights very
common 5-grams (function-word stems) and amplifies persona-discriminative
substrings, which is closer to a Burrows-adjacent shallow stylometry channel.

Production ``compute_vendi`` integration goes through
``vendi._load_default_kernel(kernel_type="lexical_5gram")`` so consumers can
swap the kernel by allowlist entry name without importing this module
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.tier_b.vendi import VendiKernel

LEXICAL_5GRAM_KERNEL_NAME: str = "lexical_5gram"
"""D-2 allowlist identifier (Plan B). Matches the ``encoders`` key in
``d2-encoder-allowlist-plan-b.json`` and the
``vendi._load_default_kernel(kernel_type=...)`` dispatch token."""


_MIN_NGRAM_CHARS: int = 5
"""Minimum source-string length below which ``char_wb`` 5-gram extraction
yields no terms; the fallback below returns the identity matrix."""


def make_tfidf_5gram_cosine_kernel() -> VendiKernel:
    """Return a TF-IDF char-5-gram cosine kernel (Plan B D-2 primary).

    The returned callable maps a window of utterances to an ``N × N`` cosine
    similarity matrix. The kernel is symmetric, has diagonal ``1.0`` (after
    re-clamping numerical drift), and off-diagonals in ``[0, 1]`` since
    TF-IDF vectors are non-negative.

    Implementation details:

    * ``TfidfVectorizer(analyzer="char_wb", ngram_range=(5, 5))`` extracts
      character 5-grams from inside word boundaries, padding word edges
      with spaces. Lowercase=True for language-agnostic case folding.
    * ``norm="l2"`` so the raw matmul ``X @ X.T`` already returns cosine
      similarity for unit-normalized rows.
    * If the corpus is degenerate (all inputs shorter than 5 characters
      after padding, producing an empty vocabulary), the kernel falls back
      to the identity matrix. This boundary is unreachable in production
      (Plan B collector filters to ``token_count >= 60``) but keeps unit
      tests robust — see ``DR-3`` in
      ``.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md``.
    """

    def kernel(items: Sequence[str]) -> np.ndarray:
        # sklearn is in the eval-extras transitive closure (sentence-
        # transformers depends on it). Lazy-import keeps base-install
        # resolution slim and mirrors the ``vendi._load_default_kernel``
        # lazy-import pattern.
        from sklearn.feature_extraction.text import (  # noqa: PLC0415
            TfidfVectorizer,
        )

        n = len(items)
        if n == 0:
            return np.zeros((0, 0), dtype=float)

        cleaned = [str(text) if str(text).strip() else " " for text in items]
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(_MIN_NGRAM_CHARS, _MIN_NGRAM_CHARS),
            lowercase=True,
            norm="l2",
            sublinear_tf=False,
        )
        try:
            tfidf = vectorizer.fit_transform(cleaned)
        except ValueError:
            # Empty vocabulary: all inputs below 5 chars even after edge
            # padding. Return identity so callers see "fully distinct"
            # rather than crashing the bootstrap pipeline.
            return np.eye(n, dtype=float)

        cosine = (tfidf @ tfidf.T).toarray().astype(float, copy=False)
        # Clamp [0, 1]: TF-IDF rows are non-negative so cosine cannot be
        # negative analytically, but float rounding can drift slightly.
        cosine = np.clip(cosine, 0.0, 1.0)
        # Force exact 1.0 on the diagonal so vendi._check_kernel's
        # diagonal=1 contract holds with no tolerance budget consumed.
        np.fill_diagonal(cosine, 1.0)
        # Symmetrize against floating-point drift on the L2 product.
        return (cosine + cosine.T) / 2.0

    return kernel


__all__ = [
    "LEXICAL_5GRAM_KERNEL_NAME",
    "make_tfidf_5gram_cosine_kernel",
]
