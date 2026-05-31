"""WP1 Layer 1 active metrics — typed, honest-degrade implementations.

Every metric is implemented *valid-capable* (the valid branch is exercised by
unit tests with synthetic fixtures), but each one degrades honestly to
``degenerate`` / ``unsupported`` when its input channel is absent — it never
fabricates a value (decisions DA-M10I-13). On the real M10-0 golden set
(Japanese utterances, empty ``mode``/``reasoning``, no belief / SWM / LLMPlan
capture) only :func:`vendi_diversity` and :func:`zone_behavior_consistency`
produce ``valid`` results; the rest are ``unsupported`` (burrows ja / belief /
SWM / recovery) or ``degenerate`` (centroid N=1 same-base, behavioral channels).

``world_model_overlap_jaccard`` (SWM Jaccard, active M10-A) and
``intervention_recovery_rate`` (recovery, M11-C) are **never ``valid``** here;
the :data:`~.policy.METRIC_SPECS` allow-lists make a valid construction raise.

Each function returns a :class:`~.models.MetricResult`. The caller (runner)
supplies a :class:`MetricContext` carrying the row identity + provenance
primitives for the relevant aggregation scope; the metric supplies its own
name / channel / status / value. Provenance ``embedding_model_id`` is threaded
from the :class:`EmbeddingProvider`, never hardcoded twice (DA-M10I-11).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003  # runtime use in signatures
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    INDIVIDUATION_SCHEMA_VERSION,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.tier_a.burrows import (
    DEFAULT_WHITESPACE_LANGUAGES,
    BurrowsLanguageMismatchError,
    BurrowsTokenizationUnsupportedError,
    compute_burrows_delta,
)
from erre_sandbox.evidence.tier_b.vendi import (
    DEFAULT_ENCODER_MODEL_ID,
    VendiKernel,
    compute_vendi,
    e5_passage_prefix,
    model_needs_e5_prefix,
)

if TYPE_CHECKING:
    from erre_sandbox.evidence.tier_a.burrows import BurrowsReference

_SOURCE_TABLE = "raw_dialog.dialog"
_MIN_POPULATION = 2  # vendi / centroid need >= 2 to be non-degenerate
_MIN_FLOOR_SPLIT_HALF = 4
"""Min utterances per odd/even half for a non-degenerate within-floor.

Frozen at 4 by the M11-C3b GO/NO-GO ADR §3: each half of the odd/even
interleave split must hold a
real sub-window centroid, which the >=8 utterance/個体 floor guarantees."""

# Embedding encoder shape mirrors ``tier_a.novelty.NoveltyEncoder``: strings ->
# one vector per string. Kept as a local alias so layer1 does not depend on
# novelty's module surface.
EmbeddingEncoder = Callable[[Sequence[str]], list[list[float]]]


@dataclass(frozen=True, slots=True)
class EmbeddingProvider:
    """Bundles the two embedding abstractions with their shared model id.

    ``vendi`` consumes a Gram matrix (:data:`~.tier_b.vendi.VendiKernel`) while
    ``centroid`` needs raw vectors (:data:`EmbeddingEncoder`); they are distinct
    callables (DA-M10I-11). ``embedding_model_id`` is the single id threaded
    into provenance for both.
    """

    embedding_model_id: str
    encoder: EmbeddingEncoder
    vendi_kernel: VendiKernel


@dataclass(frozen=True, slots=True)
class MetricContext:
    """Row identity + provenance primitives for one metric result.

    Built by the runner per aggregation scope (per_individual / per_dyad /
    population) so layer1 stays free of grouping/provenance-assembly logic.
    """

    run_id: str
    individual_id: str
    base_persona_id: str
    aggregation_level: AggregationLevel
    tick: int
    source_epoch_phase: str
    source_individual_layer_enabled: bool
    source_filter_hash: str
    source_table: str = _SOURCE_TABLE
    """Provenance source table. Defaults to the raw_dialog window source; the
    runner overrides it for trace-derived metrics (M11-C2 ``belief_variance``
    reads ``metrics.individual_state_trace``, not ``raw_dialog.dialog``, so its
    recompute provenance must say so)."""


def build_embedding_provider(model_id: str) -> EmbeddingProvider:
    """Production provider for an arbitrary encoder ``model_id`` (prefix-aware).

    Loads the ``sentence-transformers`` model once and shares it across the
    centroid :data:`EmbeddingEncoder` and the Vendi :data:`VendiKernel`. The
    heavy import is deferred to call time so a flag-off CLI run never pulls it
    into the import graph (DA-M10I-14).

    E5-family ids (``model_needs_e5_prefix``) get the ``passage:`` document
    prefix threaded into **both** paths so ``intfloat/multilingual-e5-large``
    embeds documents correctly in the M11-C3b centroid panel (ADR §5.1, MED-2).
    MPNet / BGE-M3 are not E5 family → no prefix, so
    ``build_embedding_provider(DEFAULT_ENCODER_MODEL_ID)`` is byte-equivalent to
    the legacy MPNet provider (the ``default_embedding_provider`` delegation
    below relies on this).
    """
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    model = SentenceTransformer(model_id)
    needs_prefix = model_needs_e5_prefix(model_id)
    prefix = e5_passage_prefix()

    def _prep(batch: Sequence[str]) -> list[str]:
        if needs_prefix:
            return [prefix + str(text) for text in batch]
        return list(batch)

    def encoder(batch: Sequence[str]) -> list[list[float]]:
        encoded = model.encode(_prep(batch), show_progress_bar=False)
        return [list(map(float, vec)) for vec in encoded]

    def vendi_kernel(items: Sequence[str]) -> np.ndarray:
        encoded = np.asarray(
            model.encode(_prep(items), show_progress_bar=False), dtype=float
        )
        norms = np.linalg.norm(encoded, axis=1, keepdims=True)
        unit = encoded / np.where(norms == 0, 1.0, norms)
        gram = unit @ unit.T
        np.fill_diagonal(gram, 1.0)
        return np.clip(gram, -1.0, 1.0)

    return EmbeddingProvider(
        embedding_model_id=model_id,
        encoder=encoder,
        vendi_kernel=vendi_kernel,
    )


def default_embedding_provider() -> EmbeddingProvider:
    """Production provider backed by MPNet (baseline, M10-0 default).

    Delegates to :func:`build_embedding_provider` with the default MPNet id;
    MPNet is not E5 family so no prefix is applied and the behaviour is
    unchanged from the pre-M11-C3b inline implementation (byte-equivalent).
    """
    return build_embedding_provider(DEFAULT_ENCODER_MODEL_ID)


def stub_embedding_provider(model_id: str = "stub:identity") -> EmbeddingProvider:
    """Deterministic provider for tests — no model download, no network."""

    def encoder(batch: Sequence[str]) -> list[list[float]]:
        return [
            [
                float(len(s)),
                float(sum(ord(c) for c in s) % 97),
                float(s.count(" ")),
                1.0,
            ]
            for s in batch
        ]

    def vendi_kernel(items: Sequence[str]) -> np.ndarray:
        return np.eye(len(items), dtype=float)

    return EmbeddingProvider(
        embedding_model_id=model_id,
        encoder=encoder,
        vendi_kernel=vendi_kernel,
    )


def _build(
    ctx: MetricContext,
    *,
    metric_name: str,
    channel: MetricChannel,
    status: MetricStatus,
    value: float | None,
    reason: str | None,
    computed_at: datetime,
    embedding_model_id: str | None = None,
) -> MetricResult:
    """Stamp a :class:`MetricResult` from a context + a computed outcome."""
    return MetricResult(
        run_id=ctx.run_id,
        individual_id=ctx.individual_id,
        base_persona_id=ctx.base_persona_id,
        aggregation_level=ctx.aggregation_level,
        tick=ctx.tick,
        metric_name=metric_name,
        channel=channel,
        status=status,
        value=value,
        reason=reason,
        provenance=Provenance(
            metric_schema_version=INDIVIDUATION_SCHEMA_VERSION,
            source_table=ctx.source_table,
            source_run_id=ctx.run_id,
            source_epoch_phase=ctx.source_epoch_phase,
            source_individual_layer_enabled=ctx.source_individual_layer_enabled,
            source_filter_hash=ctx.source_filter_hash,
            embedding_model_id=embedding_model_id,
        ),
        computed_at=computed_at,
    )


# ---------------------------------------------------------------------------
# Utterance-channel metrics
# ---------------------------------------------------------------------------


def burrows_base_retention(
    utterances: Sequence[str],
    *,
    language: str,
    reference: BurrowsReference | None,
    ctx: MetricContext,
    computed_at: datetime,
    preprocessed_tokens: Sequence[str] | None = None,
) -> MetricResult:
    """Burrows Delta vs the base-persona reference (stylometric anchoring).

    A language whose built-in whitespace tokeniser handles it (en/de) is
    computed directly. ja has no built-in tokeniser: it is ``unsupported``
    unless the caller supplies ``preprocessed_tokens`` (the runner pre-tokenises
    ja with :func:`~erre_sandbox.evidence.tier_a.burrows.tokenise_ja` and feeds
    them here — M11-C3a). With a reference and a finite Delta the result is
    ``valid``; an empty corpus or a non-finite Delta is ``degenerate``.
    """
    name = "burrows_base_retention"
    if language not in DEFAULT_WHITESPACE_LANGUAGES and preprocessed_tokens is None:
        return _build(
            ctx,
            metric_name=name,
            channel=MetricChannel.UTTERANCE,
            status=MetricStatus.UNSUPPORTED,
            value=None,
            reason=(
                f"burrows has no built-in tokenizer for language {language!r}"
                " and no preprocessed_tokens supplied (en/de only by default;"
                " ja must be pre-tokenised via tokenise_ja)"
            ),
            computed_at=computed_at,
        )
    text = " ".join(utterances).strip()
    if not text:
        return _degenerate(
            ctx, name, MetricChannel.UTTERANCE, "no utterances in window", computed_at
        )
    if reference is None:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            f"no reference corpus registered for language {language!r}",
            computed_at,
        )
    try:
        delta = compute_burrows_delta(
            text,
            reference,
            language=language,
            preprocessed_tokens=preprocessed_tokens,
        )
    except BurrowsTokenizationUnsupportedError:
        return _build(
            ctx,
            metric_name=name,
            channel=MetricChannel.UTTERANCE,
            status=MetricStatus.UNSUPPORTED,
            value=None,
            reason=f"burrows tokenizer unsupported for language {language!r}",
            computed_at=computed_at,
        )
    except BurrowsLanguageMismatchError:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            f"reference language != {language!r}",
            computed_at,
        )
    # Single tail return (keeps the branch count within the return-statement
    # budget): a non-finite Delta is the "unmeasurable" degenerate signal.
    finite = math.isfinite(delta)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID if finite else MetricStatus.DEGENERATE,
        value=float(delta) if finite else None,
        reason=None
        if finite
        else "burrows delta unmeasurable (no surviving function words)",
        computed_at=computed_at,
    )


def semantic_centroid_distance(
    utterances_a: Sequence[str],
    utterances_b: Sequence[str] | None,
    *,
    provider: EmbeddingProvider,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Cosine distance between two same-base individuals' utterance centroids.

    ``utterances_b is None`` marks an N=1 same-base group (no pair) →
    ``degenerate``. Empty either side → ``degenerate``. Otherwise ``valid``
    with the provider's ``embedding_model_id`` in provenance.
    """
    name = "semantic_centroid_distance"
    if utterances_b is None:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            "requires N>=2 individuals sharing the base persona (got 1)",
            computed_at,
        )
    if not utterances_a or not utterances_b:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            "empty utterance window in dyad",
            computed_at,
        )
    centroid_a = _centroid(provider.encoder, utterances_a)
    centroid_b = _centroid(provider.encoder, utterances_b)
    if centroid_a is None or centroid_b is None:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            "encoder returned no vectors",
            computed_at,
        )
    distance = _cosine_distance(centroid_a, centroid_b)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=distance,
        reason=None,
        computed_at=computed_at,
        embedding_model_id=provider.embedding_model_id,
    )


def semantic_centroid_within_floor(
    utterances: Sequence[str],
    *,
    provider: EmbeddingProvider,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Within-individual odd/even split self-centroid distance (noise floor).

    Splits the (loader-ordered) utterance list by **index parity** into an even
    half and an odd half, takes each half's centroid, and returns the cosine
    distance between them. This is one individual's within-sample variation
    floor — the C3b verdict scales the cross-individual centroid distance
    against the **median** of the 3 individuals' floors (ADR §2.1/§4.2). The
    median across individuals is the scorer's deterministic step; this metric
    emits one raw ``per_individual`` value so no post-hoc aggregation choice is
    baked into the row (decisions DA-M11C3b-P1-6).

    Each half needs ``>= _MIN_FLOOR_SPLIT_HALF`` (=4) utterances (ADR §3) or the
    result is ``degenerate``; an empty centroid is likewise ``degenerate``. A
    finite distance is ``valid`` with the provider's ``embedding_model_id``.
    """
    name = "semantic_centroid_within_floor"
    even = [u for i, u in enumerate(utterances) if i % 2 == 0]
    odd = [u for i, u in enumerate(utterances) if i % 2 == 1]
    if len(even) < _MIN_FLOOR_SPLIT_HALF or len(odd) < _MIN_FLOOR_SPLIT_HALF:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            (
                f"odd/even split needs >= {_MIN_FLOOR_SPLIT_HALF} utterances per"
                f" half (got even={len(even)}, odd={len(odd)})"
            ),
            computed_at,
        )
    centroid_even = _centroid(provider.encoder, even)
    centroid_odd = _centroid(provider.encoder, odd)
    if centroid_even is None or centroid_odd is None:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            "encoder returned no vectors",
            computed_at,
        )
    distance = _cosine_distance(centroid_even, centroid_odd)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=distance,
        reason=None,
        computed_at=computed_at,
        embedding_model_id=provider.embedding_model_id,
    )


def vendi_diversity(
    utterances: Sequence[str],
    *,
    provider: EmbeddingProvider,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Within-base population diversity (Vendi Score over the utterance set)."""
    name = "vendi_diversity"
    if len(utterances) < _MIN_POPULATION:
        return _degenerate(
            ctx,
            name,
            MetricChannel.UTTERANCE,
            f"requires >= {_MIN_POPULATION} utterances (got {len(utterances)})",
            computed_at,
        )
    result = compute_vendi(utterances, kernel=provider.vendi_kernel)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=float(result.score),
        reason=None,
        computed_at=computed_at,
        embedding_model_id=provider.embedding_model_id,
    )


# ---------------------------------------------------------------------------
# Behavioral-channel metrics (mode / decision / zone)
# ---------------------------------------------------------------------------


def cognitive_habit_recall_rate(
    habit_fires: Sequence[bool] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Fraction of turns where the base cognitive habit fired as expected.

    The M10-0 golden does not capture a habit-fire channel (``mode`` /
    ``reasoning`` are empty), so the runner passes ``None`` → ``degenerate``.
    The valid branch (fraction of ``True``) is exercised by unit tests.
    """
    return _rate_or_degenerate(
        habit_fires,
        ctx=ctx,
        computed_at=computed_at,
        name="cognitive_habit_recall_rate",
        empty_reason=(
            "behavioral fire channel empty: mode/reasoning unpopulated at M10-0"
        ),
    )


def action_adherence_rate(
    adherence_flags: Sequence[bool] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Fraction of actions adhering to the zone-policy expected for the persona.

    The M10-0 golden does not capture an action/decision channel (no
    ``LLMPlan``), so the runner passes ``None`` → ``degenerate``.
    """
    return _rate_or_degenerate(
        adherence_flags,
        ctx=ctx,
        computed_at=computed_at,
        name="action_adherence_rate",
        empty_reason="action/decision channel absent: no LLMPlan captured at M10-0",
    )


def zone_behavior_consistency(
    zones: Sequence[str],
    preferred_zones: frozenset[str] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Fraction of (non-empty) zone observations inside the persona's preferred set.

    Computable on the real M10-0 golden (``zone`` is populated) → ``valid``.
    """
    name = "zone_behavior_consistency"
    if preferred_zones is None:
        return _degenerate(
            ctx,
            name,
            MetricChannel.BEHAVIORAL,
            "persona spec / preferred_zones unavailable",
            computed_at,
        )
    observed = [z for z in zones if z]
    if not observed:
        return _degenerate(
            ctx,
            name,
            MetricChannel.BEHAVIORAL,
            "no non-empty zone observations",
            computed_at,
        )
    inside = sum(1 for z in observed if z in preferred_zones)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.BEHAVIORAL,
        status=MetricStatus.VALID,
        value=inside / len(observed),
        reason=None,
        computed_at=computed_at,
    )


# ---------------------------------------------------------------------------
# Belief substrate
# ---------------------------------------------------------------------------


def belief_variance(
    belief_classes: Sequence[str] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Gini-Simpson diversity of promoted-belief classes (content divergence).

    No belief substrate is captured in ``raw_dialog`` at M10-0, so the runner
    passes ``None`` → ``unsupported``. A single class is ``degenerate``;
    >= 2 classes give a ``valid`` diversity in ``[0, 1)``.
    """
    name = "belief_variance"
    channel = MetricChannel.BELIEF_SUBSTRATE
    if belief_classes is None:
        return _build(
            ctx,
            metric_name=name,
            channel=channel,
            status=MetricStatus.UNSUPPORTED,
            value=None,
            reason=(
                "no promoted-belief substrate in raw_dialog;"
                " SemanticMemoryRecord belief lifecycle is an M10-C schema task"
            ),
            computed_at=computed_at,
        )
    if not belief_classes:
        return _degenerate(ctx, name, channel, "no belief records", computed_at)
    distinct = set(belief_classes)
    if len(distinct) < 2:  # noqa: PLR2004 — single-class is the documented degenerate cell
        return _degenerate(
            ctx, name, channel, "single belief class (no variance)", computed_at
        )
    counts = [belief_classes.count(c) for c in distinct]
    total = len(belief_classes)
    gini_simpson = 1.0 - sum((c / total) ** 2 for c in counts)
    return _build(
        ctx,
        metric_name=name,
        channel=channel,
        status=MetricStatus.VALID,
        value=gini_simpson,
        reason=None,
        computed_at=computed_at,
    )


# ---------------------------------------------------------------------------
# Function-only / protocol-only: NEVER valid in M10-0 (METRIC_SPECS enforced)
# ---------------------------------------------------------------------------


def world_model_overlap_jaccard(
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """SWM key overlap between same-base individuals — unsupported at M10-0.

    ``SubjectiveWorldModel`` is not captured in ``raw_dialog``; this metric is
    active only from M10-A. The :data:`~.policy.METRIC_SPECS` allow-list forbids
    ``valid`` here, so this can only ever return ``degenerate``/``unsupported``.
    """
    return _build(
        ctx,
        metric_name="world_model_overlap_jaccard",
        channel=MetricChannel.WORLD_MODEL,
        status=MetricStatus.UNSUPPORTED,
        value=None,
        reason=(
            "SubjectiveWorldModel not captured in raw_dialog;"
            " SWM Jaccard active at M10-A"
        ),
        computed_at=computed_at,
    )


def intervention_recovery_rate(
    *,
    ctx: MetricContext,
    computed_at: datetime,
) -> MetricResult:
    """Post-perturbation base-habit recovery — unsupported at M10-0 (M11-C)."""
    return _build(
        ctx,
        metric_name="intervention_recovery_rate",
        channel=MetricChannel.RECOVERY,
        status=MetricStatus.UNSUPPORTED,
        value=None,
        reason="requires perturbation protocol run, M11-C territory",
        computed_at=computed_at,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _degenerate(
    ctx: MetricContext,
    name: str,
    channel: MetricChannel,
    reason: str,
    computed_at: datetime,
) -> MetricResult:
    return _build(
        ctx,
        metric_name=name,
        channel=channel,
        status=MetricStatus.DEGENERATE,
        value=None,
        reason=reason,
        computed_at=computed_at,
    )


def _rate_or_degenerate(
    flags: Sequence[bool] | None,
    *,
    ctx: MetricContext,
    computed_at: datetime,
    name: str,
    empty_reason: str,
) -> MetricResult:
    if not flags:
        return _degenerate(
            ctx, name, MetricChannel.BEHAVIORAL, empty_reason, computed_at
        )
    rate = sum(1 for f in flags if f) / len(flags)
    return _build(
        ctx,
        metric_name=name,
        channel=MetricChannel.BEHAVIORAL,
        status=MetricStatus.VALID,
        value=rate,
        reason=None,
        computed_at=computed_at,
    )


def _centroid(
    encoder: EmbeddingEncoder, utterances: Sequence[str]
) -> np.ndarray | None:
    raw = encoder(list(utterances))
    if not raw:
        return None
    matrix = np.asarray(raw, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0:  # noqa: PLR2004 — 2D embedding matrix expected
        return None
    return matrix.mean(axis=0)


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    cos = float(np.dot(a, b) / (na * nb))
    return 1.0 - max(-1.0, min(1.0, cos))


__all__ = [
    "EmbeddingEncoder",
    "EmbeddingProvider",
    "MetricContext",
    "action_adherence_rate",
    "belief_variance",
    "build_embedding_provider",
    "burrows_base_retention",
    "cognitive_habit_recall_rate",
    "default_embedding_provider",
    "intervention_recovery_rate",
    "semantic_centroid_distance",
    "semantic_centroid_within_floor",
    "stub_embedding_provider",
    "vendi_diversity",
    "world_model_overlap_jaccard",
    "zone_behavior_consistency",
]
