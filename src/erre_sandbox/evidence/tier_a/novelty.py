"""Semantic novelty — mean cosine distance to running prior centroid.

For every turn after the first, embed the utterance with MPNet
(``sentence-transformers/all-mpnet-base-v2``) and compare it to the
average direction of all prior turns. A persona that keeps cycling
through the same idea collapses toward zero; a persona that
genuinely introduces new content yields persistent positive distance.

The pure-numpy aggregation step is kept stub-friendly via the
``encoder`` keyword. Tests inject a fixed embedding fixture so the
heavy ``sentence-transformers`` import never fires unless the caller
asked for the real model. Numpy is a core dependency, so the metric
itself stays lightweight.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

NoveltyEncoder = Callable[[Sequence[str]], list[list[float]]]
"""Stub-friendly callable shape: take a list of strings, return a list of
embeddings (one per string, fixed dimensionality).

Returning plain ``list[list[float]]`` rather than ``np.ndarray`` keeps
test fixtures readable and avoids forcing the encoder implementation
to use numpy (an Ollama-served embedding service, for example, can
return Python lists directly).
"""


def compute_semantic_novelty(
    utterances: Sequence[str],
    *,
    encoder: NoveltyEncoder | None = None,
) -> float | None:
    """Mean cosine distance between each turn embedding and prior centroid.

    Args:
        utterances: Ordered sequence of turn utterances. The first turn
            has no prior centroid so it does not contribute; subsequent
            turns each contribute one cosine-distance value.
        encoder: Optional stub callable. When ``None`` the default
            MPNet encoder is lazily loaded; tests should always pass a
            stub.

    Returns:
        ``None`` when fewer than 2 utterances are available (no prior
        centroid to compare against). Otherwise the mean cosine
        distance ``1 - cos(emb_i, mean(emb_0..i-1))`` across
        ``i = 1..n-1``. Values are in ``[0, 2]`` because cosine
        similarity ranges over ``[-1, 1]``.
    """
    if len(utterances) < 2:  # noqa: PLR2004 — contract: need ≥2 turns
        return None
    fn = encoder if encoder is not None else _load_default_encoder()
    raw = fn(list(utterances))
    if not raw:
        return None
    matrix = np.asarray(raw, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != len(utterances):  # noqa: PLR2004 — 2D embedding matrix expected
        raise ValueError(
            f"encoder returned shape {matrix.shape}, expected 2D with"
            f" {len(utterances)} rows",
        )

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    unit = matrix / safe_norms

    distances: list[float] = []
    for i in range(1, len(unit)):
        prior_mean = unit[:i].mean(axis=0)
        prior_norm = float(np.linalg.norm(prior_mean))
        if prior_norm == 0.0:
            # Antipodal prior turns cancelled; treat as max novelty
            # (1.0) rather than NaN so downstream aggregation still
            # produces a number on pathological synthetic inputs.
            distances.append(1.0)
            continue
        prior_unit = prior_mean / prior_norm
        cos_sim = float(np.dot(unit[i], prior_unit))
        distances.append(1.0 - cos_sim)

    if not distances:
        return None
    return float(sum(distances) / len(distances))


def _load_default_encoder() -> NoveltyEncoder:
    """Lazy-load ``sentence-transformers/all-mpnet-base-v2``.

    Heavy import deferred until the caller actually needs the real
    embedding model — keeps the module importable without
    ``[eval]`` extras.
    """
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

    def encoder(batch: Sequence[str]) -> list[list[float]]:
        encoded = model.encode(list(batch), show_progress_bar=False)
        return [list(map(float, vec)) for vec in encoded]

    return encoder
