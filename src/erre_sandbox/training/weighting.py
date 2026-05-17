"""Signal-driven per-example weighting for m9-c-adopt retrain v2 (DA-14 / DR-1).

This module is the **training-time** half of the retrain v2 spec
(`.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` §3.2/§3.3).
It consumes a pre-computed per-example metadata dict (language / token_count /
has_addressee / marker_density_per_100_tokens — derived in
:mod:`erre_sandbox.training.example_features`) and produces:

* per-example raw weights via :func:`compute_example_weight` (Codex HIGH-C
  verbatim formula, clamped to ``[0.1, 3.0]``);
* per-train-split normalised weights via :func:`normalise_weights_to_mean_one`
  so effective LR is not silently shifted by the heuristic coefficient choice
  (Codex HIGH-C #2);
* a pre-training audit JSON via :func:`emit_weight_audit` that surfaces
  per-language weighted mass, top-5% concentration, and N_eff — the three
  signals that drive the Candidate C fallback trigger (Codex HIGH-A #2).

Coefficient transparency (Codex HIGH-C #3): the 0.35 / 0.20 / 0.15 / 0.30
coefficients are **heuristic** (sum-to-1 for interpretability), NOT
empirically optimal. The closest prior art is static importance weighting /
curriculum learning (Bengio 2009); focal loss is a loose analogy only because
focal loss is model-confidence-dependent and dynamic. DAP / preference
personalization is a different objective entirely.

No torch / transformers imports — the gate-only path in
:func:`erre_sandbox.training.train_kant_lora.train_kant_lora` and the
pre-training audit step must remain installable without the ``[training]``
extras.
"""

from __future__ import annotations

import json
import statistics
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


_CE_IGNORE_INDEX: Final[int] = -100
"""HuggingFace causal-LM ignored-position sentinel; used in cross_entropy."""

_LEN_BUCKET_SHORT_MAX: Final[int] = 30
_LEN_BUCKET_MID_MAX: Final[int] = 60
_LEN_BUCKET_LONG_MAX: Final[int] = 120
"""Bucket upper bounds (exclusive) for the audit length histogram."""


# ---------------------------------------------------------------------------
# Constants (Codex HIGH-C verbatim spec)
# ---------------------------------------------------------------------------

WEIGHT_CLAMP_MIN: Final[float] = 0.1
"""Lower bound on the raw per-example weight (Codex HIGH-C).

Structural defence against pathological zero-weight examples; the formula's
practical minimum is roughly ``0.34`` for ja/short/dialog/zero-marker rows, so
this clamp is rarely hit but guards against future coefficient retuning that
could push raw values below the floor.
"""

WEIGHT_CLAMP_MAX: Final[float] = 3.0
"""Upper bound on the raw per-example weight (Codex HIGH-C).

Caps gradient variance: at ``rank=8`` with ``batch=1, grad_accum=8`` the
weighted-sum reduction means a single example's contribution to the gradient
scales linearly in its weight, so an uncapped raw of e.g. 7.5 (from a very
high marker_density) would dominate the batch. The 3.0 cap together with
mean=1.0 normalisation keeps the effective per-example ratio at ~10x rather
than the formula's nominal ~30x (Codex HIGH-C LOW-2 reflection).
"""

_LANG_FACTORS: Final[dict[str, float]] = {
    "de": 1.4,
    "en": 1.0,
    "mixed": 0.5,
    "ja": 0.2,
}
"""Per-language multiplicative factor in the raw-weight formula.

German is rewarded most aggressively (1.4x) because the Step 1 corpus
analysis showed only 15.9% German share — well below the Kant base rate ~16%
that produces persona-discriminative signal. Mixed text gets 0.5x because the
language classifier flags it when neither side dominates, signalling a
diluted training example. Japanese is heavily down-weighted (0.2x) because
the corpus is 56.7% ja-heavy and the trainer was previously dominated by
non-discriminative ja conversation patterns.
"""

_LENGTH_THRESHOLDS: Final[tuple[tuple[int, float], ...]] = (
    (30, 0.3),
    (60, 0.8),
    (120, 1.5),
)
"""``(strict-upper-token-bound, factor)`` ladder for the length multiplier.

Rows with token_count >= the highest bound (120) get the saturated factor
(2.0). Step 1 corpus analysis showed 69.0% of rows are <30 tokens — the
0.3 multiplier on that majority is the primary lever for emphasising
long-form Kant rhetoric.
"""
_LENGTH_FACTOR_SATURATED: Final[float] = 2.0

_MONOLOG_BONUS: Final[float] = 1.5
_DIALOG_BONUS: Final[float] = 1.0
"""Monolog (no addressee) is boosted because Step 1 found 0% monolog ratio.

Synthetic monolog re-cast in :func:`_collect_from_shards_weighted` brings
this to ~5-7% of the train split; the bonus magnifies the per-example
contribution so the trainer sees the long-form / self-addressed style as a
distinct mode rather than a sampling outlier.
"""

_MARKER_FACTOR_FLOOR: Final[float] = 0.2
_MARKER_DENSITY_DIVISOR: Final[float] = 2.0
"""``marker_factor = max(marker_density / 2.0, 0.2)`` — see design-final §3.2.

The literature anchor (Cambridge Edition translator-aligned passages) is
~2.0 markers per 100 tokens, so dividing by 2.0 normalises the factor to
~1.0 at anchor density. The 0.2 floor prevents zero-marker rows from
collapsing to weight 0 (the corpus median marker density is 0, so without
the floor ~half the rows would contribute nothing).
"""

_COEFF_LANG: Final[float] = 0.35
_COEFF_LENGTH: Final[float] = 0.20
_COEFF_MONOLOG: Final[float] = 0.15
_COEFF_MARKER: Final[float] = 0.30
"""Linear-combination coefficients (sum = 1.0).

Heuristic, NOT empirical (Codex HIGH-C #3). Language gets the largest share
because the ja-heavy gap (C1 from corpus analysis) is the empirically
largest of the four. Marker density second, length third, monolog bonus
lowest because monolog re-cast is a synthetic injection rather than a
property of the realised corpus.
"""


# ---------------------------------------------------------------------------
# compute_example_weight
# ---------------------------------------------------------------------------


def compute_example_weight(example_metadata: dict[str, object]) -> float:
    """Compute the clamped raw weight for one training example (HIGH-C verbatim).

    Args:
        example_metadata: Per-row metadata dict with keys

            * ``language`` (``"de"``/``"en"``/``"mixed"``/``"ja"``)
            * ``token_count`` (int)
            * ``has_addressee`` (bool)
            * ``marker_density_per_100_tokens`` (float)

            Extra keys are ignored. Missing or mis-typed keys raise
            ``KeyError`` / ``TypeError`` — callers must materialise the
            metadata before invoking this function (the
            :func:`erre_sandbox.training.example_features.extract_example_metadata`
            helper does this end-to-end).

    Returns:
        A float in ``[WEIGHT_CLAMP_MIN, WEIGHT_CLAMP_MAX]``. The practical
        minimum across the Step 1 corpus is roughly 0.34 (ja / short /
        dialog / zero-marker); the practical maximum saturates at 3.0 for
        de / 120+ tokens / monolog / marker_density >= ~10.

    Notes:
        The returned weight is raw — it has *not* yet been normalised to
        mean=1.0. Pass the full per-train-split list through
        :func:`normalise_weights_to_mean_one` before feeding to
        :class:`WeightedTrainer`, otherwise the effective learning rate
        will drift relative to the K-β rank=8 baseline (Codex HIGH-C #2).
    """
    lang = example_metadata["language"]
    tokens = int(cast("int", example_metadata["token_count"]))
    has_addressee = bool(example_metadata["has_addressee"])
    marker_density = float(
        cast("float", example_metadata["marker_density_per_100_tokens"])
    )

    lang_factor = _LANG_FACTORS[str(lang)]
    length_factor = _LENGTH_FACTOR_SATURATED
    for upper_bound, factor in _LENGTH_THRESHOLDS:
        if tokens < upper_bound:
            length_factor = factor
            break
    monolog_bonus = _DIALOG_BONUS if has_addressee else _MONOLOG_BONUS
    marker_factor = max(marker_density / _MARKER_DENSITY_DIVISOR, _MARKER_FACTOR_FLOOR)

    raw = (
        lang_factor * _COEFF_LANG
        + length_factor * _COEFF_LENGTH
        + monolog_bonus * _COEFF_MONOLOG
        + marker_factor * _COEFF_MARKER
    )
    return float(min(max(raw, WEIGHT_CLAMP_MIN), WEIGHT_CLAMP_MAX))


# ---------------------------------------------------------------------------
# normalise_weights_to_mean_one
# ---------------------------------------------------------------------------


def normalise_weights_to_mean_one(raw: Sequence[float]) -> list[float]:
    """Rescale ``raw`` so the mean is exactly 1.0 (Codex HIGH-C #2).

    Without normalisation the hand-set coefficients (0.35/0.20/0.15/0.30)
    silently shift the effective learning rate because the corpus-wide
    mean of unnormalised weights is ~0.85 (estimated from Step 1 finding).
    With normalisation the trainer's effective LR matches the K-β baseline
    exactly except for the per-example variance the weights introduce.

    Args:
        raw: The per-example raw weights as returned by
            :func:`compute_example_weight`. Must be non-empty and contain
            at least one positive value (an all-zero list raises
            ``ZeroDivisionError`` — that condition indicates a metadata
            extraction bug, not a recoverable runtime state).

    Returns:
        A list of floats with ``sum(out) / len(out) == 1.0`` to numerical
        precision. Pairwise ratios are preserved exactly.
    """
    if not raw:
        raise ValueError("normalise_weights_to_mean_one: raw list is empty")
    mean = sum(raw) / len(raw)
    if mean <= 0.0:
        raise ZeroDivisionError(
            "normalise_weights_to_mean_one: mean of raw weights is non-positive"
            f" ({mean!r}); compute_example_weight should never emit 0/negative"
            " — investigate the upstream metadata extraction.",
        )
    return [w / mean for w in raw]


# ---------------------------------------------------------------------------
# emit_weight_audit
# ---------------------------------------------------------------------------

_BUCKET_LANGS: Final[tuple[str, ...]] = ("de", "en", "ja", "mixed")
_BUCKET_LENGTHS: Final[tuple[str, ...]] = ("<30", "30-59", "60-119", "120+")


def _length_bucket(token_count: int) -> str:
    if token_count < _LEN_BUCKET_SHORT_MAX:
        return "<30"
    if token_count < _LEN_BUCKET_MID_MAX:
        return "30-59"
    if token_count < _LEN_BUCKET_LONG_MAX:
        return "60-119"
    return "120+"


def _marker_quartile_label(density: float, breakpoints: list[float]) -> str:
    """Return ``"q1"``/``"q2"``/``"q3"``/``"q4"`` for a marker-density value."""
    if not breakpoints:
        return "q1"
    if density <= breakpoints[0]:
        return "q1"
    if len(breakpoints) > 1 and density <= breakpoints[1]:
        return "q2"
    if len(breakpoints) > 2 and density <= breakpoints[2]:  # noqa: PLR2004
        return "q3"
    return "q4"


def _compute_marker_quartile_breakpoints(
    metadata: Sequence[dict[str, object]],
) -> list[float]:
    """Return 25/50/75-percentile breakpoints of marker density.

    Computed across the train set; used to label per-row buckets in the
    weight-audit histogram.
    """
    densities = sorted(
        float(cast("float", m["marker_density_per_100_tokens"])) for m in metadata
    )
    if not densities:
        return []
    n = len(densities)
    return [
        densities[max(0, int(0.25 * n) - 1)],
        densities[max(0, int(0.50 * n) - 1)],
        densities[max(0, int(0.75 * n) - 1)],
    ]


def emit_weight_audit(
    weights: Sequence[float],
    metadata: Sequence[dict[str, object]],
    output_path: Path,
) -> dict[str, object]:
    """Materialise a JSON audit of the per-example weight distribution (HIGH-A #2).

    Run this **before** training kickoff. The Candidate C fallback trigger
    consumes the audit's ``n_eff`` and ``top_5_pct_weight_share`` fields:

    * ``n_eff < 1000`` → exit 6 (:class:`InsufficientEffectiveSampleSizeError`)
    * ``top_5_pct_weight_share >= 0.50`` → exit 7 (:class:`WeightConcentrationError`)
    * ``per_language_weighted_mass["de"] + ["en"] < 0.60`` → soft warning only

    Args:
        weights: Per-example weights *after* normalisation. Length must
            match ``metadata``. The audit reports descriptive stats
            (min/p50/p90/max) and the structural metrics (N_eff,
            top-5% share, per-lang mass).
        metadata: Per-example metadata dicts (same keys as
            :func:`compute_example_weight`'s input). Used to bucket the
            distribution by language / length / marker quartile.
        output_path: JSON output path. Parent directory is created if
            missing. The audit dict is also returned so callers can apply
            fallback-trigger checks without re-reading the file.

    Returns:
        The audit dict (same content as the JSON file).

    Raises:
        ValueError: ``weights`` and ``metadata`` have different lengths
            (programming bug — caller must materialise both from the same
            train split).
    """
    if len(weights) != len(metadata):
        raise ValueError(
            f"emit_weight_audit: weights / metadata length mismatch"
            f" ({len(weights)} vs {len(metadata)}); both must come from"
            f" the same train split",
        )
    if not weights:
        raise ValueError("emit_weight_audit: weights list is empty")

    n = len(weights)
    total_weight = sum(weights)
    sum_sq = sum(w * w for w in weights)
    n_eff = (total_weight * total_weight) / sum_sq if sum_sq > 0 else 0.0

    # Per-language weighted mass (fraction of total weight per language)
    lang_mass: dict[str, float] = dict.fromkeys(_BUCKET_LANGS, 0.0)
    for w, m in zip(weights, metadata, strict=True):
        lang = str(m.get("language", "mixed"))
        if lang not in lang_mass:
            lang_mass[lang] = 0.0
        lang_mass[lang] += w
    for lang, value in list(lang_mass.items()):
        lang_mass[lang] = value / total_weight if total_weight > 0 else 0.0

    # Top 5% share: ceil(0.05 * n), at minimum 1
    top_k = max(1, math_ceil_5_pct(n))
    sorted_desc = sorted(weights, reverse=True)
    top_k_sum = sum(sorted_desc[:top_k])
    top_5_share = top_k_sum / total_weight if total_weight > 0 else 0.0

    # Bucket histogram (lang × length × marker_quartile)
    marker_breaks = _compute_marker_quartile_breakpoints(metadata)
    bucket_histogram: dict[str, int] = {}
    for m in metadata:
        lang_b = str(m.get("language", "mixed"))
        len_b = _length_bucket(int(cast("int", m["token_count"])))
        q_b = _marker_quartile_label(
            float(cast("float", m["marker_density_per_100_tokens"])),
            marker_breaks,
        )
        key = f"{lang_b}|{len_b}|{q_b}"
        bucket_histogram[key] = bucket_histogram.get(key, 0) + 1

    # Descriptive stats on weight distribution
    sorted_weights = sorted(weights)
    audit: dict[str, object] = {
        "n_examples": n,
        "weight_min": float(sorted_weights[0]),
        "weight_p10": float(sorted_weights[max(0, int(0.10 * (n - 1)))]),
        "weight_p50": float(statistics.median(weights)),
        "weight_p90": float(sorted_weights[max(0, int(0.90 * (n - 1)))]),
        "weight_max": float(sorted_weights[-1]),
        "weight_mean": float(total_weight / n),
        "n_eff": float(n_eff),
        "top_5_pct_weight_share": float(top_5_share),
        "top_5_pct_count": int(top_k),
        "per_language_weighted_mass": lang_mass,
        "bucket_histogram": bucket_histogram,
        "marker_quartile_breakpoints": marker_breaks,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def math_ceil_5_pct(n: int) -> int:
    """Ceiling of 5% of ``n``; at least 1 if ``n > 0``.

    Inlined helper to avoid importing ``math`` only for ``ceil``. At n=20,
    the top 5% is 1 example; at n=100, the top 5% is 5.
    """
    if n <= 0:
        return 0
    raw = 0.05 * n
    return max(1, int(raw) + (1 if raw > int(raw) else 0))


# ---------------------------------------------------------------------------
# Weighted causal-LM loss (pure function so unit tests can exercise the math
# without instantiating transformers.Trainer). The next-token shift logic is
# Codex HIGH-C verbatim; the batch-level reduce was updated by DA-16 ADR
# DA16-2 from ``sum/weights.sum()`` to ``.mean()`` so that per-example
# weights survive the batch=1 + grad_accum gradient path under DI-7's
# VRAM-saturated Qwen3-8B + NF4 + rank=8 retrain configuration.
# ---------------------------------------------------------------------------


def compute_weighted_causal_lm_loss(logits: Any, labels: Any, weights: Any) -> Any:
    """Compute per-example weighted causal-LM loss (Codex HIGH-C verbatim shift logic).

    The function operates on **un-shifted** logits/labels — it performs
    the next-token shift internally so callers can pass raw model outputs.

    Logic:

    1. Shift logits one position left, labels one position right
       (standard causal-LM contract).
    2. Compute token-level cross-entropy with ``reduction="none"`` and
       ``ignore_index=-100``.
    3. Reduce to **per-example mean** over valid (non-``-100``) positions.
    4. Reduce across the batch as ``(per_example_loss * weights).mean()``
       (DA-16 ADR DA16-2: ``.mean()`` reduce, replaces the prior
       ``.sum() / weights.sum()`` form so that weight magnitude is
       preserved in the gradient under ``per_device_train_batch_size=1``).

    **Semantic note (DA-16 ADR DA16-2, replaces the original Codex HIGH-C
    ``sum/weights.sum()`` reduce)**:

    Under ``per_device_train_batch_size=1`` (the DI-7 VRAM-saturated
    Qwen3-8B + NF4 + rank=8 retrain configuration) the prior
    ``(per_example_loss * weights).sum() / weights.sum()`` form
    degenerates to ``(l[0] * w[0]) / w[0] = l[0]`` — the weight cancels
    out of the gradient, and DA-14 ``compute_example_weight`` acts as a
    no-op in training (retrain blockers.md Blocker 2, kant Plan B v3
    REJECT root cause hypothesis). The new ``.mean()`` reduce keeps
    ``loss = l[0] * w[0]`` so the weight is preserved in
    ``loss.backward()``; under gradient accumulation the HF Trainer then
    aggregates weight-aware gradients across micro-batches automatically.

    This form **requires that ``weights`` are mean=1 normalised over
    the training pool**. The training pipeline performs that
    normalisation explicitly via :func:`normalise_weights_to_mean_one`
    just before tokenisation (see
    :func:`erre_sandbox.training.train_kant_lora._run_trainer_weighted`
    around line 742); :func:`compute_example_weight` itself only
    *produces* the per-example raw weights — the pool-level mean=1
    invariant is a contract enforced by the caller, not the function.

    With ``mean(weights) ≈ 1`` **in expectation over shuffled batches**,
    the new ``(l*w).mean()`` and the prior ``sum(l*w)/sum(w)`` produce
    similar averaged scales for ``batch_size >= 2`` — but only in
    expectation. For any given small batch, the new value equals the
    old value scaled by the **local** ``mean(weights)`` of that batch,
    which can deviate materially from 1.0 even when the pool mean is
    exactly 1.0. Concretely, a batch=2 of ``weights=[0.5, 1.5]`` has
    local mean 1.0 (no scale change), but a batch=2 of
    ``weights=[0.2, 1.8]`` (local mean 1.0 too) yields a different
    per-example *gradient* distribution than the prior reducer because
    weight magnitude survives. Future analysis of train-loss
    trajectories at ``batch_size >= 2`` must treat this as a reducer
    artefact rather than misread it as a model/corpus effect. For
    ``batch_size = 1`` the two reduce forms diverge by design — that
    divergence is exactly what re-establishes the DA-14 weighting
    signal in the training gradient.

    The ``torch.clamp(min=1e-8)`` epsilon used in the prior form was a
    zero-weight-batch defence; with ``.mean()`` the denominator is the
    tensor element count (always > 0 for batch ≥ 1) so the epsilon is
    no longer required.

    Args:
        logits: ``(batch, seq_len, vocab)`` float tensor from the model.
        labels: ``(batch, seq_len)`` int tensor; ``-100`` marks ignored
            positions (typically padding / non-assistant tokens).
        weights: ``(batch,)`` float tensor of per-example sample weights.
            Caller is responsible for mean=1 normalisation across the
            training pool (see :func:`normalise_weights_to_mean_one`).

    Returns:
        A scalar tensor — the weighted-mean loss for the batch under the
        DA-16 ADR ``.mean()`` reduce.

    Notes:
        ``torch`` and ``torch.nn.functional`` are imported lazily inside
        the function so :mod:`erre_sandbox.training.weighting` stays
        installable without the ``[training]`` extras (the gate-only path
        and the pre-training audit must work on the CI default profile).
    """
    import torch.nn.functional as torch_fn  # noqa: PLC0415  # lazy GPU stack

    if logits.shape[1] < 2:  # noqa: PLR2004  # 2 = need at least one shift position
        raise ValueError(
            "compute_weighted_causal_lm_loss: logits seq_len must be >= 2"
            f" (got shape {tuple(logits.shape)}); shifting is impossible.",
        )
    logits_shifted = logits[:, :-1, :]
    labels_shifted = labels[:, 1:]
    token_ce = torch_fn.cross_entropy(
        logits_shifted.reshape(-1, logits_shifted.size(-1)),
        labels_shifted.reshape(-1),
        ignore_index=_CE_IGNORE_INDEX,
        reduction="none",
    ).reshape(labels_shifted.shape)
    valid_mask = (labels_shifted != _CE_IGNORE_INDEX).to(token_ce.dtype)
    valid_counts = valid_mask.sum(dim=1).clamp_min(1.0)
    per_example_loss = (token_ce * valid_mask).sum(dim=1) / valid_counts
    return (per_example_loss * weights).mean()


__all__ = [
    "WEIGHT_CLAMP_MAX",
    "WEIGHT_CLAMP_MIN",
    "compute_example_weight",
    "compute_weighted_causal_lm_loss",
    "emit_weight_audit",
    "normalise_weights_to_mean_one",
]
