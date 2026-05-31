"""Burrows-aware loss term — KL on n-gram distribution.

Training-objective augmentation for PR-15 ADR
`da-XX-burrows-aware-loss.md` (DPN15-1.1) + PR-16 Phase 1.
Adds a differentiable auxiliary loss term

    L_total = causal_lm_loss + λ * KL(P_model_marginal || P_reference)

where the marginal distribution is computed over a small partition of the
vocab consisting of German function-word first-token-id proxies plus one
OTHER bucket carrying the residual probability mass. The intent is to push
the model toward the empirical Burrows function-word frequency profile of
a reference corpus (Kant German) during training, complementing the
existing causal-LM next-token loss with a stylometry-aware signal.

The reference unigram table is built once (offline) by a separate
reference-corpus builder script and persisted as
JSON under ``data/burrows_aware_loss/reference_unigram_kant_de.json`` so
the training run reads a frozen distribution + SHA256 hash. The hash is
embedded in ``train_metadata.json`` (forensic continuity).

Sub-binding:

1. OTHER bucket default = present (function-word tokens + 1 OTHER bucket
   that absorbs residual mass; renormalised so the partition sums to 1).
2. label=-100 / padding mask = applied (HF Trainer standard ignore index).
3. sequence / batch averaging = per-token KL → sequence-average over valid
   positions → batch mean (same reduction as ``compute_weighted_causal_lm_loss``).
4. logits temperature = 1.0 (softmax as-is; tempered variants are §future).
5. eps clamp = ``1e-9`` applied to the model marginal before ``log``
   (reference is Laplace-smoothed so already zero-free).

KL direction is **reverse KL** ``KL(model || reference)`` (PR-15 ADR
§user feedback #1.3 default). The function-word → token-id mapping uses
the **first token id** as a single-token proxy when subword splits occur
(PR-15 ADR §user feedback #1.1 default); the roundtrip match rate is
computed by the build script and persisted in the JSON metadata.

No torch import at module-load: ``torch.nn.functional`` is imported lazily
inside :func:`compute_burrows_kl_term` so the gate-only path in
:mod:`erre_sandbox.training.train_kant_lora` stays installable without the
``[training]`` extras (consistent with ``compute_weighted_causal_lm_loss``
in :mod:`erre_sandbox.training.weighting`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pathlib import Path


_CE_IGNORE_INDEX: Final[int] = -100
"""HuggingFace causal-LM ignored-position sentinel (same as weighting.py)."""

DEFAULT_EPS: Final[float] = 1e-9
"""Default epsilon for log clamp inside the KL term."""

_SUM_TOLERANCE: Final[float] = 1e-3
"""Tolerance for reference probability normalisation check (sum ≈ 1.0)."""


@dataclass(frozen=True, slots=True)
class ReferenceUnigramTable:
    """Reference unigram distribution over function-word token ids + OTHER bucket.

    The probabilities are aligned with ``function_word_token_ids`` by index
    (i.e. ``reference_probabilities[i]`` is the smoothed reference
    probability of token ``function_word_token_ids[i]``). The OTHER bucket
    absorbs the residual mass for non-function-word tokens; the partition
    therefore sums to ``1.0`` within :data:`_SUM_TOLERANCE`.
    """

    function_word_token_ids: tuple[int, ...]
    reference_probabilities: tuple[float, ...]
    other_bucket_probability: float
    roundtrip_match_rate: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.function_word_token_ids) != len(self.reference_probabilities):
            msg = (
                "ReferenceUnigramTable: function_word_token_ids and"
                f" reference_probabilities length mismatch"
                f" ({len(self.function_word_token_ids)} vs"
                f" {len(self.reference_probabilities)})"
            )
            raise ValueError(msg)
        total = sum(self.reference_probabilities) + self.other_bucket_probability
        if abs(total - 1.0) > _SUM_TOLERANCE:
            msg = (
                "ReferenceUnigramTable: probabilities + other_bucket must sum"
                f" to 1.0 ± {_SUM_TOLERANCE}, got {total:.6f}"
            )
            raise ValueError(msg)
        for prob in (*self.reference_probabilities, self.other_bucket_probability):
            if prob < 0.0:
                msg = (
                    "ReferenceUnigramTable: reference probabilities must be"
                    f" non-negative, got {prob}"
                )
                raise ValueError(msg)
        if not 0.0 <= self.roundtrip_match_rate <= 1.0:
            msg = (
                "ReferenceUnigramTable: roundtrip_match_rate must be in"
                f" [0.0, 1.0], got {self.roundtrip_match_rate}"
            )
            raise ValueError(msg)

    @property
    def distribution_hash(self) -> str:
        """Return the SHA256 hash of the canonical distribution body.

        The hash covers ``function_word_token_ids`` +
        ``reference_probabilities`` + ``other_bucket_probability`` only
        (metadata excluded so unrelated forensic fields do not perturb the
        hash). Persisted alongside the JSON file and embedded in
        ``train_metadata.json``.
        """
        canonical = json.dumps(
            {
                "function_word_token_ids": list(self.function_word_token_ids),
                "reference_probabilities": list(self.reference_probabilities),
                "other_bucket_probability": self.other_bucket_probability,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_reference_unigram_table(path: Path) -> ReferenceUnigramTable:
    """Load a reference unigram JSON produced by the build script.

    Args:
        path: Path to the JSON file. Must contain the keys
            ``function_word_token_ids`` (list[int]),
            ``reference_probabilities`` (list[float]),
            ``other_bucket_probability`` (float),
            ``roundtrip_match_rate`` (float), and ``metadata`` (object).

    Returns:
        Parsed :class:`ReferenceUnigramTable`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the JSON is malformed or fails the normalisation
            invariants enforced by :class:`ReferenceUnigramTable`.
    """
    if not path.is_file():
        msg = f"reference unigram JSON not found: {path}"
        raise FileNotFoundError(msg)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"reference unigram JSON is malformed: {path}: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(payload, dict):
        msg = (
            "reference unigram JSON root must be an object, got"
            f" {type(payload).__name__}"
        )
        raise TypeError(msg)
    try:
        token_ids = tuple(int(x) for x in payload["function_word_token_ids"])
        probs = tuple(float(x) for x in payload["reference_probabilities"])
        other = float(payload["other_bucket_probability"])
        roundtrip = float(payload["roundtrip_match_rate"])
        metadata = dict(payload.get("metadata", {}))
    except (KeyError, TypeError, ValueError) as exc:
        msg = f"reference unigram JSON schema invalid: {path}: {exc}"
        raise ValueError(msg) from exc
    return ReferenceUnigramTable(
        function_word_token_ids=token_ids,
        reference_probabilities=probs,
        other_bucket_probability=other,
        roundtrip_match_rate=roundtrip,
        metadata=metadata,
    )


def compute_burrows_kl_term(
    logits: Any,
    labels: Any,
    reference_table: ReferenceUnigramTable,
    *,
    eps: float = DEFAULT_EPS,
) -> Any:
    """Compute the Burrows-aware KL auxiliary loss term (PR-15 ADR §核心式 verbatim).

    Args:
        logits: ``(batch, seq_len, vocab)`` float tensor from the model
            (un-shifted; this function applies the causal-LM shift
            internally, matching :func:`compute_weighted_causal_lm_loss`).
        labels: ``(batch, seq_len)`` int tensor; ``-100`` marks ignored
            positions (HF causal-LM padding sentinel).
        reference_table: Loaded :class:`ReferenceUnigramTable` carrying the
            function-word token ids and the smoothed reference
            distribution over the (function-word ∪ OTHER) partition.
        eps: Epsilon used to clamp the model marginal before ``log`` so
            zero-probability positions do not cause ``log(0)``. Default
            :data:`DEFAULT_EPS`. The reference distribution is
            Laplace-smoothed and therefore already zero-free.

    Returns:
        Scalar tensor: the reverse-KL ``KL(model_marginal || reference)``
        averaged over valid token positions (label != -100) within each
        sequence, then averaged over the batch (same reduction as
        :func:`compute_weighted_causal_lm_loss`).

    Raises:
        ValueError: If ``logits.shape[1] < 2`` (cannot shift) or if
            ``reference_table.function_word_token_ids`` is empty.
    """
    import torch  # noqa: PLC0415  # lazy GPU stack
    import torch.nn.functional as torch_fn  # noqa: PLC0415  # lazy GPU stack

    if logits.shape[1] < 2:  # noqa: PLR2004  # 2 = need at least one shift position
        msg = (
            "compute_burrows_kl_term: logits seq_len must be >= 2"
            f" (got shape {tuple(logits.shape)}); shifting is impossible."
        )
        raise ValueError(msg)
    if len(reference_table.function_word_token_ids) == 0:
        msg = (
            "compute_burrows_kl_term: reference_table.function_word_token_ids"
            " is empty; cannot compute KL over an empty function-word set."
        )
        raise ValueError(msg)

    # Causal-LM shift: predict token at position t+1 from position t.
    # Matches compute_weighted_causal_lm_loss (weighting.py:551).
    logits_shifted = logits[:, :-1, :]
    labels_shifted = labels[:, 1:]

    # Softmax over the full vocab → P_model[b, t, v].
    p_model = torch_fn.softmax(logits_shifted, dim=-1)

    # Gather function-word token probabilities → P_model_fw[b, t, K].
    fw_ids = torch.tensor(
        reference_table.function_word_token_ids,
        device=logits.device,
        dtype=torch.long,
    )
    p_model_fw = p_model.index_select(dim=-1, index=fw_ids)

    # OTHER bucket = 1 - sum_K(P_model_fw). Differentiable (sum + sub).
    p_model_other = 1.0 - p_model_fw.sum(dim=-1, keepdim=True)

    # Concatenate to form the (K+1)-partition: [fw_1, ..., fw_K, OTHER].
    p_model_marginal = torch.cat([p_model_fw, p_model_other], dim=-1)

    # Clamp to avoid log(0) (eps=1e-9 default).
    p_model_marginal = p_model_marginal.clamp_min(eps)

    # Reference distribution tensor (frozen, no grad needed).
    p_ref = torch.tensor(
        [
            *reference_table.reference_probabilities,
            reference_table.other_bucket_probability,
        ],
        device=logits.device,
        dtype=p_model_marginal.dtype,
    )
    # Reference is Laplace-smoothed so already > 0 everywhere; clamp is a
    # belt-and-braces guard against external pathological tables.
    p_ref = p_ref.clamp_min(eps)

    # Reverse KL per token: KL(model || ref) = Σ_k p_m * (log p_m - log p_r).
    log_p_model = p_model_marginal.log()
    log_p_ref = p_ref.log()
    kl_per_token = (p_model_marginal * (log_p_model - log_p_ref)).sum(dim=-1)
    # kl_per_token shape: (batch, seq_len - 1)

    # Mask padding positions (label == -100). Same shift as the labels.
    valid_mask = (labels_shifted != _CE_IGNORE_INDEX).to(kl_per_token.dtype)
    valid_counts = valid_mask.sum(dim=1).clamp_min(1.0)
    per_example_kl = (kl_per_token * valid_mask).sum(dim=1) / valid_counts
    return per_example_kl.mean()


__all__ = [
    "DEFAULT_EPS",
    "ReferenceUnigramTable",
    "compute_burrows_kl_term",
    "load_reference_unigram_table",
]
