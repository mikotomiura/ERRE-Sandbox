"""Tests for ``erre_sandbox.evidence.tier_b.vendi_lexical_5gram``.

m9-c-adopt Plan B D-2 allowlist primary encoder unit-test surface. The
sanity tests pin the kernel contract (symmetry, diagonal=1, identical→1,
disjoint→0) and the dispatch hook exposed via
``vendi._load_default_kernel(kernel_type="lexical_5gram")``. See
``.steering/20260518-m9-c-adopt-plan-b-retrain/design.md`` §1 and
``decisions.md`` DR-1 / DR-2 / DR-3 for the design rationale.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from erre_sandbox.evidence.tier_b.vendi import (
    _load_default_kernel,
    compute_vendi,
)
from erre_sandbox.evidence.tier_b.vendi_lexical_5gram import (
    LEXICAL_5GRAM_KERNEL_NAME,
    make_tfidf_5gram_cosine_kernel,
)

# sklearn (transitive dep of sentence-transformers, explicit in [eval] extras)
# is required for every test that actually invokes the kernel. Skip the
# entire module under the CI default profile (no extras installed); the
# constant + signature + dispatch-error tests are kept inside this gate
# because their pytest collection imports do not exercise sklearn but
# splitting them would fragment the file. Production smoke verifies the
# kernel under `uv sync --extra eval`.
pytest.importorskip("sklearn")


def test_lexical_5gram_kernel_name_constant() -> None:
    """D-2 allowlist identifier must match the JSON pre-registration."""
    assert LEXICAL_5GRAM_KERNEL_NAME == "lexical_5gram"


def test_kernel_diagonal_is_one_and_symmetric() -> None:
    """Vendi contract: diagonal=1, symmetric, shape (N, N)."""
    kernel = make_tfidf_5gram_cosine_kernel()
    matrix = kernel(
        [
            "alpha bravo charlie delta echo",
            "alpha bravo charlie delta foxtrot",
            "zulu yankee whiskey victor uniform",
        ],
    )
    assert matrix.shape == (3, 3)
    assert np.allclose(np.diag(matrix), 1.0, atol=1e-9)
    assert np.allclose(matrix, matrix.T, atol=1e-9)


def test_identical_texts_similarity_one_distinct_below_one() -> None:
    """Identical inputs → cosine=1; distinct inputs → cosine<1."""
    kernel = make_tfidf_5gram_cosine_kernel()
    matrix = kernel(
        [
            "the quick brown fox jumps over",
            "the quick brown fox jumps over",
            "completely orthogonal vocabulary distinct lexicon",
        ],
    )
    assert matrix[0, 1] == pytest.approx(1.0, abs=1e-6)
    assert matrix[0, 2] < 0.5
    assert matrix[1, 2] < 0.5


def test_disjoint_5grams_yield_zero_similarity() -> None:
    """No shared 5-grams (case-folded char_wb) → cosine = 0."""
    kernel = make_tfidf_5gram_cosine_kernel()
    matrix = kernel(["abcdefghijklmno", "pqrstuvwxyz12345"])
    assert matrix[0, 1] == pytest.approx(0.0, abs=1e-6)


def test_short_inputs_below_5_chars_fallback_identity() -> None:
    """All inputs < 5 chars → empty vocab → identity fallback (DR-3)."""
    kernel = make_tfidf_5gram_cosine_kernel()
    matrix = kernel(["a", "b", "c"])
    assert matrix.shape == (3, 3)
    assert np.allclose(matrix, np.eye(3), atol=1e-9)


def test_empty_input_returns_zero_shape_matrix() -> None:
    """Boundary: empty input → (0, 0) matrix without invoking sklearn."""
    kernel = make_tfidf_5gram_cosine_kernel()
    matrix = kernel([])
    assert matrix.shape == (0, 0)


def test_kernel_round_trip_through_compute_vendi() -> None:
    """Vendi integration: the kernel must satisfy ``compute_vendi`` validation.

    ``compute_vendi`` calls ``_check_kernel`` (diagonal=1, symmetric); a kernel
    that fails either contract would raise here before any score computation.
    """
    kernel = make_tfidf_5gram_cosine_kernel()
    result = compute_vendi(
        [
            "alpha bravo charlie delta echo",
            "alpha bravo charlie delta foxtrot",
            "zulu yankee whiskey victor uniform",
        ],
        kernel=kernel,
        kernel_name="lexical_5gram",
    )
    assert result.n == 3
    assert result.kernel_name == "lexical_5gram"
    # 3 partially-similar items → score strictly between 1 (degenerate) and N.
    assert 1.0 < result.score <= 3.0 + 1e-6


def test_load_default_kernel_dispatches_lexical_5gram() -> None:
    """``kernel_type='lexical_5gram'`` returns the TF-IDF char-5-gram kernel."""
    kernel = _load_default_kernel(kernel_type="lexical_5gram")
    matrix = kernel(
        [
            "alpha bravo charlie delta echo",
            "zulu yankee whiskey victor uniform",
        ],
    )
    assert matrix.shape == (2, 2)
    assert np.allclose(np.diag(matrix), 1.0, atol=1e-9)
    # Disjoint character 5-grams across the two strings.
    assert matrix[0, 1] == pytest.approx(0.0, abs=1e-6)


def test_load_default_kernel_unknown_kernel_type_raises() -> None:
    """Unknown ``kernel_type`` must raise ``ValueError`` (regression safety)."""
    with pytest.raises(ValueError, match="unknown kernel_type"):
        _load_default_kernel(kernel_type="byte_pair_v1")


def test_load_default_kernel_signature_preserves_existing_contract() -> None:
    """DA-15 regression: ``encoder_name`` parameter and MPNet fallback must remain.

    The Plan B kernel_type kwarg must not displace the existing semantic-path
    source contract (``test_vendi.py:test_load_default_kernel_signature_
    accepts_encoder_name`` pins the same invariants — duplicated here so a
    refactor that breaks this file is caught locally).
    """
    sig = inspect.signature(_load_default_kernel)
    assert "encoder_name" in sig.parameters
    assert "kernel_type" in sig.parameters
    assert sig.parameters["encoder_name"].default is None
    assert sig.parameters["kernel_type"].default == "semantic"
    source = inspect.getsource(_load_default_kernel)
    assert "encoder_name or _DEFAULT_ENCODER_MODEL_ID" in source
