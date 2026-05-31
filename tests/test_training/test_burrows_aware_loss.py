"""Unit tests for ``erre_sandbox.training.burrows_aware_loss`` (PR-16 Phase 1).

Covers the two public surfaces:

* :func:`load_reference_unigram_table` — JSON loader + invariant checks.
* :func:`compute_burrows_kl_term` — differentiable reverse-KL auxiliary
  loss term over the (function-word ∪ OTHER) partition.

These tests ``pytest.importorskip("torch")`` so the CI default profile
(no ``[training]`` extras) silently skips the differentiable-math cases.
The JSON-loader cases are torch-free and run on every profile.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from erre_sandbox.training.burrows_aware_loss import (
    DEFAULT_EPS,
    ReferenceUnigramTable,
    compute_burrows_kl_term,
    load_reference_unigram_table,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_reference_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_reference_payload() -> dict[str, object]:
    # K = 3 function-word token ids; reference probs = [0.10, 0.05, 0.02],
    # OTHER bucket = 0.83 → sums to 1.0.
    return {
        "function_word_token_ids": [11, 22, 33],
        "reference_probabilities": [0.10, 0.05, 0.02],
        "other_bucket_probability": 0.83,
        "roundtrip_match_rate": 0.95,
        "metadata": {
            "tokenizer_name": "Qwen/Qwen3-8B",
            "smoothing": "laplace-add-1.0",
            "source_corpus": ["mock://corpus"],
            "build_date": "2026-05-21T00:00:00+00:00",
            "function_word_count": 3,
        },
    }


def _build_reference_table() -> ReferenceUnigramTable:
    payload = _valid_reference_payload()
    return ReferenceUnigramTable(
        function_word_token_ids=tuple(
            int(x) for x in payload["function_word_token_ids"]
        ),  # type: ignore[arg-type]
        reference_probabilities=tuple(
            float(x)
            for x in payload["reference_probabilities"]  # type: ignore[union-attr]
        ),
        other_bucket_probability=float(payload["other_bucket_probability"]),  # type: ignore[arg-type]
        roundtrip_match_rate=float(payload["roundtrip_match_rate"]),  # type: ignore[arg-type]
        metadata=dict(payload["metadata"]),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Loader tests (torch-free)
# ---------------------------------------------------------------------------


def test_load_reference_unigram_table_valid(tmp_path: Path) -> None:
    """Loading a well-formed JSON parses into ReferenceUnigramTable."""
    json_path = _write_reference_json(
        tmp_path / "ref.json",
        _valid_reference_payload(),
    )
    table = load_reference_unigram_table(json_path)
    assert table.function_word_token_ids == (11, 22, 33)
    assert table.reference_probabilities == (0.10, 0.05, 0.02)
    assert table.other_bucket_probability == pytest.approx(0.83)
    assert table.roundtrip_match_rate == pytest.approx(0.95)
    assert table.metadata["tokenizer_name"] == "Qwen/Qwen3-8B"


def test_load_reference_unigram_table_missing_path_raises_filenotfound(
    tmp_path: Path,
) -> None:
    """A missing path surfaces FileNotFoundError (not bare RuntimeError)."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="not found"):
        load_reference_unigram_table(missing)


def test_load_reference_unigram_table_malformed_json_raises_valueerror(
    tmp_path: Path,
) -> None:
    """Invalid JSON surfaces ValueError carrying the original decode error."""
    json_path = tmp_path / "bad.json"
    json_path.write_text("{not: valid", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        load_reference_unigram_table(json_path)


def test_load_reference_unigram_table_normalized_probabilities(
    tmp_path: Path,
) -> None:
    """Probabilities + OTHER bucket must sum to 1.0 ± tolerance."""
    bad = _valid_reference_payload()
    bad["other_bucket_probability"] = 0.50  # → total 0.67, fails invariant
    json_path = _write_reference_json(tmp_path / "bad_sum.json", bad)
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        load_reference_unigram_table(json_path)


def test_reference_unigram_table_length_mismatch_raises() -> None:
    """Constructor rejects token_ids / probabilities length mismatch."""
    with pytest.raises(ValueError, match="length mismatch"):
        ReferenceUnigramTable(
            function_word_token_ids=(11, 22, 33),
            reference_probabilities=(0.10, 0.05),  # K=2 vs K=3 ids
            other_bucket_probability=0.85,
            roundtrip_match_rate=0.95,
        )


def test_reference_unigram_table_negative_probability_raises() -> None:
    """Constructor rejects negative reference probabilities."""
    with pytest.raises(ValueError, match="non-negative"):
        ReferenceUnigramTable(
            function_word_token_ids=(11,),
            reference_probabilities=(-0.10,),
            other_bucket_probability=1.10,
            roundtrip_match_rate=0.95,
        )


def test_reference_unigram_table_roundtrip_out_of_range_raises() -> None:
    """roundtrip_match_rate must be in [0.0, 1.0]."""
    with pytest.raises(ValueError, match=r"roundtrip_match_rate"):
        ReferenceUnigramTable(
            function_word_token_ids=(11,),
            reference_probabilities=(0.10,),
            other_bucket_probability=0.90,
            roundtrip_match_rate=1.5,
        )


def test_reference_unigram_table_distribution_hash_stable() -> None:
    """distribution_hash depends only on (ids, probs, OTHER), not metadata."""
    table_a = ReferenceUnigramTable(
        function_word_token_ids=(11, 22),
        reference_probabilities=(0.10, 0.20),
        other_bucket_probability=0.70,
        roundtrip_match_rate=0.95,
        metadata={"tokenizer_name": "A"},
    )
    table_b = ReferenceUnigramTable(
        function_word_token_ids=(11, 22),
        reference_probabilities=(0.10, 0.20),
        other_bucket_probability=0.70,
        roundtrip_match_rate=0.80,  # different rate
        metadata={"tokenizer_name": "B"},  # different metadata
    )
    assert table_a.distribution_hash == table_b.distribution_hash
    # Sanity: changing a probability changes the hash.
    table_c = ReferenceUnigramTable(
        function_word_token_ids=(11, 22),
        reference_probabilities=(0.10, 0.21),
        other_bucket_probability=0.69,
        roundtrip_match_rate=0.95,
    )
    assert table_a.distribution_hash != table_c.distribution_hash


# ---------------------------------------------------------------------------
# KL term tests (require torch)
# ---------------------------------------------------------------------------


def _make_logits_labels(
    *,
    batch: int,
    seq_len: int,
    vocab: int,
    seed: int = 0,
) -> tuple[object, object]:
    import torch

    torch.manual_seed(seed)
    logits = torch.randn(batch, seq_len, vocab, requires_grad=True)
    labels = torch.randint(0, vocab, (batch, seq_len))
    return logits, labels


def test_compute_burrows_kl_term_returns_scalar() -> None:
    """KL term reduces to a 0-D tensor."""
    torch = pytest.importorskip("torch")
    table = _build_reference_table()
    logits, labels = _make_logits_labels(batch=2, seq_len=8, vocab=50)
    kl = compute_burrows_kl_term(logits, labels, table)
    assert isinstance(kl, torch.Tensor)
    assert kl.shape == ()
    assert torch.isfinite(kl).item()


def test_compute_burrows_kl_term_is_differentiable() -> None:
    """The KL term must produce a gradient on the input logits."""
    pytest.importorskip("torch")
    table = _build_reference_table()
    logits, labels = _make_logits_labels(batch=2, seq_len=8, vocab=50)
    kl = compute_burrows_kl_term(logits, labels, table)
    kl.backward()  # type: ignore[no-untyped-call]
    assert logits.grad is not None  # type: ignore[union-attr]
    grad_norm = float(logits.grad.norm())  # type: ignore[union-attr]
    assert grad_norm > 0.0


def test_compute_burrows_kl_term_uniform_match_near_zero() -> None:
    """When model marginal ≈ reference, KL ≈ 0 (sanity for the math)."""
    torch = pytest.importorskip("torch")
    # Construct a reference distribution where each of K=3 fw tokens has
    # 1/(K+1) mass, and OTHER bucket has 1/(K+1) too. A uniform-logits
    # model produces a uniform vocab distribution → fw mass and OTHER
    # bucket mass are each (1/vocab) and ((vocab-K)/vocab). Picking
    # vocab=4, K=3 means fw=3/4 and OTHER=1/4, which already gives a
    # closed-form expectation. We just assert kl is non-negative and
    # finite — divergence is a non-negative quantity by definition.
    vocab = 4
    table = ReferenceUnigramTable(
        function_word_token_ids=(0, 1, 2),
        reference_probabilities=(0.25, 0.25, 0.25),
        other_bucket_probability=0.25,
        roundtrip_match_rate=1.0,
    )
    logits = torch.zeros(1, 4, vocab, requires_grad=False)
    labels = torch.zeros(1, 4, dtype=torch.long)
    kl = compute_burrows_kl_term(logits, labels, table)
    assert torch.isfinite(kl).item()
    assert float(kl) >= 0.0
    # Uniform model produces uniform marginal (3/4 fw split + 1/4 OTHER
    # absorbed into one bucket); against a uniform 4-way reference the
    # divergence should be small.
    assert float(kl) < 0.5


def test_compute_burrows_kl_term_pushes_toward_reference() -> None:
    """One SGD step on the KL term reduces the divergence (effect direction)."""
    torch = pytest.importorskip("torch")
    table = _build_reference_table()
    # Start far from the reference — initialise so fw tokens get tiny mass.
    torch.manual_seed(1)
    logits_raw = torch.full((1, 4, 50), -2.0)
    logits_raw[:, :, [11, 22, 33]] = -5.0  # suppress function-word tokens
    logits = logits_raw.detach().clone().requires_grad_(True)  # noqa: FBT003
    labels = torch.zeros(1, 4, dtype=torch.long)

    kl_before = compute_burrows_kl_term(logits, labels, table)
    kl_before.backward()  # type: ignore[no-untyped-call]
    with torch.no_grad():
        logits -= 0.5 * logits.grad  # type: ignore[operator]
    kl_after = compute_burrows_kl_term(
        logits.detach().requires_grad_(False),  # noqa: FBT003
        labels,
        table,
    )
    assert float(kl_after.detach()) < float(kl_before.detach())


def test_compute_burrows_kl_term_masks_label_neg100() -> None:
    """All-masked sequences contribute zero KL (mask correctness)."""
    torch = pytest.importorskip("torch")
    table = _build_reference_table()
    logits, _ = _make_logits_labels(batch=1, seq_len=4, vocab=50)
    masked_labels = torch.full((1, 4), -100, dtype=torch.long)
    kl_masked = compute_burrows_kl_term(logits, masked_labels, table)
    # Implementation guards against zero valid positions with clamp_min(1.0)
    # on the denominator; the numerator however is zeroed by the mask,
    # so the resulting per-example KL is exactly 0.
    assert float(kl_masked.detach()) == pytest.approx(0.0, abs=1e-6)


def test_compute_burrows_kl_term_eps_clamp_no_nan() -> None:
    """Pathological -inf logits for fw tokens still produce finite KL."""
    torch = pytest.importorskip("torch")
    table = _build_reference_table()
    logits = torch.zeros(1, 4, 50, requires_grad=True)
    # Suppress all function-word tokens to -inf-ish so softmax mass → 0.
    with torch.no_grad():
        logits[:, :, [11, 22, 33]] = -1e9
    labels = torch.zeros(1, 4, dtype=torch.long)
    kl = compute_burrows_kl_term(
        logits.detach().requires_grad_(True),  # noqa: FBT003
        labels,
        table,
        eps=DEFAULT_EPS,
    )
    assert math.isfinite(float(kl.detach()))


def test_compute_burrows_kl_term_seq_len_lt_2_raises_valueerror() -> None:
    """seq_len < 2 cannot perform causal-LM shift → ValueError."""
    torch = pytest.importorskip("torch")
    table = _build_reference_table()
    logits = torch.zeros(1, 1, 50, requires_grad=True)  # seq_len=1
    labels = torch.zeros(1, 1, dtype=torch.long)
    with pytest.raises(ValueError, match="seq_len must be >= 2"):
        compute_burrows_kl_term(logits, labels, table)


def test_compute_burrows_kl_term_empty_function_word_set_raises_valueerror() -> None:
    """An empty function-word token id set is rejected up front."""
    torch = pytest.importorskip("torch")
    empty_table = ReferenceUnigramTable(
        function_word_token_ids=(),
        reference_probabilities=(),
        other_bucket_probability=1.0,
        roundtrip_match_rate=0.0,
    )
    logits = torch.zeros(1, 4, 50, requires_grad=True)
    labels = torch.zeros(1, 4, dtype=torch.long)
    with pytest.raises(ValueError, match="empty function-word set"):
        compute_burrows_kl_term(logits, labels, empty_table)
