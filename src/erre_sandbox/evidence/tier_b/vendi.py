"""Vendi Score (Friedman & Dieng 2023) — Tier B diversity metric.

The Vendi Score is the exponential of the Shannon entropy of the eigenvalue
spectrum of a positive semi-definite similarity kernel ``K`` with ``K_ii = 1``,
applied to ``K / N``. Identical items collapse to score 1; an identity kernel
with ``N`` items yields score ``N``.

DB9 sub-metric: ``vendi_score``. Persona-conditional: bootstrap CI per persona
across 25 windows (5 runs × 5 per-100-turn windows). Use with
:func:`erre_sandbox.evidence.bootstrap_ci.hierarchical_bootstrap_ci`
``cluster_only=True`` (M9-eval ME-14).

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report only —
no LIWC equivalence claim, no external-lexicon Big5 inference. Tier A
``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10 Option D).

ME-10 (Codex P4a HIGH-1) keeps the default kernel as ``"semantic"`` (MPNet,
the same encoder Tier A novelty uses). ``vendi_kernel_sensitivity_panel``
exposes the preregistered weight grid for the P4b sensitivity test on golden
baseline data; the production gate consumes the default kernel only until
that empirical comparison lands.

DA-15 (Plan A = Vendi kernel swap) parameterises ``_load_default_kernel`` to
accept an alternate HuggingFace encoder id. The DA-14 MPNet instrument is
preserved as the default (``encoder_name=None``); DA-15 reports a versioned
amended metric ``vendi_semantic_v2_encoder_swap`` under the new encoder so
the original DA-14 numbers stay reproducible. Pre-registered encoders for
the kant escalation are pinned in
``.steering/20260516-m9-c-adopt-da15-impl/decisions.md`` D-2.

ME-15 metadata: emit ``window_index`` / ``window_start_turn`` /
``window_end_turn`` / ``window_size`` / ``metric_schema_version`` / ``kernel_name``
in the sidecar ``notes`` JSON when persisting to ``metrics.tier_b``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

VendiKernel = Callable[[Sequence[str]], np.ndarray]
"""Stub-friendly callable: utterances -> ``N × N`` similarity matrix.

The matrix must be symmetric, positive semi-definite, with diagonal entries
``1.0``. Off-diagonal entries are similarity scores in ``[0, 1]`` (cosine for
the semantic kernel, Jaccard for the lexical kernel). Tests pass deterministic
stubs so the heavy MPNet load never fires under unit tests.
"""

DEFAULT_KERNEL_NAME: str = "semantic"
"""Default kernel identifier surfaced in :class:`VendiResult` and notes JSON."""

_EIGENVALUE_FLOOR: float = 1e-12
"""Eigenvalues below this floor are treated as zero in the entropy sum.

Numerical noise from ``eigvalsh`` on a near-rank-deficient kernel can produce
small negative or sub-floor positive eigenvalues; clamping avoids ``log(0)``
without changing the entropy meaningfully (the contribution of a sub-floor
eigenvalue is below numpy's float resolution anyway).
"""


@dataclass(frozen=True, slots=True)
class VendiResult:
    """Vendi Score for a single window.

    ``score = N`` only when the normalized kernel equals the identity matrix
    (M9-eval ME-10). ``score = 1`` when every item is identical. Other values
    fall in ``[1, N]`` for PSD kernels with ``K_ii = 1``.
    """

    score: float
    n: int
    kernel_name: str
    semantic_weight: float
    lexical_weight: float
    spectrum_entropy: float


def _vendi_score_from_kernel(kernel_matrix: np.ndarray) -> tuple[float, float]:
    """Return ``(score, entropy)`` for an ``N × N`` PSD kernel with diag=1.

    Pulled out so the unit tests can exercise the math without going through
    the encoder boundary. The kernel must already be symmetric; ``eigvalsh``
    raises ``LinAlgError`` if asymmetry leaks past the input validation.
    """
    n = kernel_matrix.shape[0]
    if n == 0:
        return 0.0, 0.0
    normalized = kernel_matrix / float(n)
    eigvals = np.linalg.eigvalsh(normalized)
    safe = eigvals[eigvals > _EIGENVALUE_FLOOR]
    if safe.size == 0:
        return 1.0, 0.0
    entropy = float(-np.sum(safe * np.log(safe)))
    return float(np.exp(entropy)), entropy


def _check_kernel(matrix: np.ndarray, n: int) -> None:
    """Validate kernel shape, diagonal, and symmetry within float tolerance."""
    if matrix.shape != (n, n):
        raise ValueError(
            f"kernel matrix shape {matrix.shape} != ({n}, {n})",
        )
    if not np.allclose(np.diag(matrix), 1.0, atol=1e-6):
        raise ValueError("kernel diagonal must equal 1.0 (Vendi assumption)")
    if not np.allclose(matrix, matrix.T, atol=1e-6):
        raise ValueError("kernel must be symmetric")


def compute_vendi(
    utterances: Sequence[str],
    *,
    kernel: VendiKernel | None = None,
    kernel_name: str = DEFAULT_KERNEL_NAME,
    semantic_weight: float = 1.0,
    lexical_weight: float = 0.0,
) -> VendiResult:
    """Compute Vendi Score for a window of utterances.

    Args:
        utterances: One window — typically the 100 turns of a per-100-turn
            window. Order is preserved.
        kernel: Optional stub callable (``utterances -> N × N`` similarity).
            ``None`` lazy-loads the default semantic kernel (MPNet cosine,
            same encoder Tier A novelty uses).
        kernel_name: Identifier surfaced in :class:`VendiResult` and notes
            JSON. Use ``"semantic"`` / ``"lexical-5gram"`` /
            ``"hybrid-{semantic_weight}-{lexical_weight}"`` for production
            kernels, ``"identity"`` only inside tests.
        semantic_weight: Weight on the semantic component for ``hybrid-*``
            kernel identifiers; ``1.0`` for ``"semantic"``.
        lexical_weight: Weight on the lexical component for ``hybrid-*``;
            ``0.0`` for ``"semantic"``.

    Returns:
        :class:`VendiResult` with ``score``, ``n``, kernel metadata, and the
        underlying spectrum entropy. Empty input returns ``score=0.0, n=0``.

    Raises:
        ValueError: On inconsistent kernel shape, non-unit diagonal, or
            non-symmetric kernel matrix.
    """
    items = list(utterances)
    n = len(items)
    if n == 0:
        return VendiResult(
            score=0.0,
            n=0,
            kernel_name=kernel_name,
            semantic_weight=semantic_weight,
            lexical_weight=lexical_weight,
            spectrum_entropy=0.0,
        )

    fn = kernel if kernel is not None else _load_default_kernel()
    matrix = np.asarray(fn(items), dtype=float)
    _check_kernel(matrix, n)

    score, entropy = _vendi_score_from_kernel(matrix)
    return VendiResult(
        score=score,
        n=n,
        kernel_name=kernel_name,
        semantic_weight=semantic_weight,
        lexical_weight=lexical_weight,
        spectrum_entropy=entropy,
    )


def vendi_kernel_sensitivity_panel(
    utterances: Sequence[str],
    *,
    semantic_kernel: VendiKernel,
    lexical_kernel: VendiKernel,
    weights: Sequence[tuple[float, float]] = (
        (1.0, 0.0),
        (0.0, 1.0),
        (0.5, 0.5),
        (0.7, 0.3),
        (0.9, 0.1),
    ),
) -> list[VendiResult]:
    """Preregistered Vendi kernel sensitivity panel (M9-eval ME-10).

    Computes Vendi Score for the same window under each ``(semantic_weight,
    lexical_weight)`` combination so the P4b empirical comparison can rank
    kernels by persona-discriminative power on golden baseline data.

    The default ``weights`` grid is the preregistered set in ME-10:
    ``semantic-only`` / ``lexical-only`` / ``hybrid-0.5-0.5`` /
    ``hybrid-0.7-0.3`` / ``hybrid-0.9-0.1``.

    Args:
        utterances: One window of turn texts.
        semantic_kernel: Callable returning the semantic similarity matrix
            (cosine over MPNet embeddings in production).
        lexical_kernel: Callable returning the lexical similarity matrix
            (5-gram Jaccard in production; tests pass a deterministic stub).
        weights: Iterable of ``(semantic_weight, lexical_weight)`` pairs.
            Each pair must sum to a positive number; weights are applied to
            the matching kernel matrix and combined linearly.

    Returns:
        One :class:`VendiResult` per ``weights`` entry, in the same order.
    """
    items = list(utterances)
    n = len(items)
    if n == 0:
        return [
            VendiResult(
                score=0.0,
                n=0,
                kernel_name=_kernel_name_for(w_s, w_l),
                semantic_weight=w_s,
                lexical_weight=w_l,
                spectrum_entropy=0.0,
            )
            for w_s, w_l in weights
        ]

    semantic_matrix = np.asarray(semantic_kernel(items), dtype=float)
    lexical_matrix = np.asarray(lexical_kernel(items), dtype=float)
    _check_kernel(semantic_matrix, n)
    _check_kernel(lexical_matrix, n)

    results: list[VendiResult] = []
    for w_s, w_l in weights:
        if w_s + w_l <= 0:
            raise ValueError(
                f"weight sum must be positive (got {w_s} + {w_l})",
            )
        # Normalize so the combined matrix still has diagonal 1; both inputs
        # already have diagonal 1, so the convex sum preserves that.
        total = w_s + w_l
        combined = (w_s / total) * semantic_matrix + (w_l / total) * lexical_matrix
        score, entropy = _vendi_score_from_kernel(combined)
        results.append(
            VendiResult(
                score=score,
                n=n,
                kernel_name=_kernel_name_for(w_s, w_l),
                semantic_weight=w_s / total,
                lexical_weight=w_l / total,
                spectrum_entropy=entropy,
            ),
        )
    return results


def _kernel_name_for(semantic_weight: float, lexical_weight: float) -> str:
    """Return the kernel identifier for a ``(semantic, lexical)`` weight pair."""
    if math.isclose(lexical_weight, 0.0):
        return "semantic"
    if math.isclose(semantic_weight, 0.0):
        return "lexical-5gram"
    return f"hybrid-{semantic_weight:.1f}-{lexical_weight:.1f}"


def make_lexical_5gram_kernel() -> VendiKernel:
    """Return a deterministic lexical 5-gram Jaccard kernel.

    The kernel hashes character 5-grams of each utterance into sets and
    computes pairwise Jaccard similarity. Empty utterances collapse to a
    single-element set so the diagonal stays at ``1.0``. Used as the lexical
    half of the sensitivity panel.
    """

    def kernel(items: Sequence[str]) -> np.ndarray:
        n = len(items)
        sets = [_char_5gram_set(text) for text in items]
        matrix = np.eye(n, dtype=float)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = sets[i], sets[j]
                if not a or not b:
                    sim = 0.0 if a != b else 1.0
                else:
                    sim = len(a & b) / len(a | b)
                matrix[i, j] = sim
                matrix[j, i] = sim
        return matrix

    return kernel


_NON_TOKEN = re.compile(r"\s+")


def _char_5gram_set(text: str) -> frozenset[str]:
    """Return the set of character 5-grams for a text (whitespace-collapsed)."""
    cleaned = _NON_TOKEN.sub(" ", text.strip())
    if len(cleaned) < 5:  # noqa: PLR2004 — 5-gram width is the documented cell
        return frozenset({cleaned}) if cleaned else frozenset()
    return frozenset(cleaned[i : i + 5] for i in range(len(cleaned) - 4))


_DEFAULT_ENCODER_MODEL_ID: str = "sentence-transformers/all-mpnet-base-v2"
"""DA-14 instrument: MPNet semantic cosine kernel (regression baseline)."""

_E5_PASSAGE_PREFIX: str = "passage: "
"""E5 family expects the ``passage:`` prefix for document embedding (arxiv:
2402.05672 §3). Without it, retrieval performance degrades materially. We use
the same prefix for every item in a window so pairwise similarity stays
self-consistent."""


def _load_default_kernel(encoder_name: str | None = None) -> VendiKernel:
    """Lazy-load the semantic cosine kernel for the given encoder.

    Heavy ``sentence-transformers`` import is deferred until the caller
    actually needs the real model — the eval extras gate keeps it out of base
    install resolution.

    Args:
        encoder_name: HuggingFace model id. ``None`` falls back to MPNet
            (DA-14 baseline, asserted by
            ``test_vendi_default_encoder_model_id_is_all_mpnet_base_v2``).
            DA-15 Plan A swaps in a multilingual encoder
            (``intfloat/multilingual-e5-large`` or ``BAAI/bge-m3``) via this
            argument — see ``.steering/20260516-m9-c-adopt-da15-impl/
            decisions.md`` D-2 for the pre-registered revision pins.
    """
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    model_id = encoder_name or _DEFAULT_ENCODER_MODEL_ID
    model = SentenceTransformer(model_id)
    needs_e5_prefix = "e5" in model_id.lower()

    def kernel(items: Sequence[str]) -> np.ndarray:
        if needs_e5_prefix:
            encode_inputs = [_E5_PASSAGE_PREFIX + str(text) for text in items]
        else:
            encode_inputs = list(items)
        encoded = model.encode(encode_inputs, show_progress_bar=False)
        matrix = np.asarray(encoded, dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        safe = np.where(norms == 0, 1.0, norms)
        unit = matrix / safe
        cosine = unit @ unit.T
        # Numerical noise can push diagonal slightly above 1; clamp to keep
        # _check_kernel happy. Off-diagonal clamping to [0, 1] would mask real
        # negative similarity from contradictory text — leave that to the
        # caller to interpret.
        np.fill_diagonal(cosine, 1.0)
        return cosine

    return kernel


__all__ = [
    "DEFAULT_KERNEL_NAME",
    "VendiKernel",
    "VendiResult",
    "_load_default_kernel",
    "compute_vendi",
    "make_lexical_5gram_kernel",
    "vendi_kernel_sensitivity_panel",
]
