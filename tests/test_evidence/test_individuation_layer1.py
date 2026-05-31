"""WP1 Layer 1 metric coverage (M10-0 individuation PR-2).

Each metric is exercised on its valid branch (synthetic fixtures) and its
honest-degrade branch (absent channel). The never-valid metrics (SWM Jaccard,
recovery) are asserted ``unsupported``. ``embedding_model_id`` threading is
checked on the embedding-backed metrics.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from erre_sandbox.evidence.individuation.layer1 import (
    MetricContext,
    action_adherence_rate,
    belief_variance,
    build_embedding_provider,
    burrows_base_retention,
    cognitive_habit_recall_rate,
    default_embedding_provider,
    intervention_recovery_rate,
    semantic_centroid_distance,
    semantic_centroid_within_floor,
    stub_embedding_provider,
    vendi_diversity,
    world_model_overlap_jaccard,
    zone_behavior_consistency,
)
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    RESERVED_POPULATION_ID,
    AggregationLevel,
    MetricStatus,
)
from erre_sandbox.evidence.tier_a.burrows import BurrowsReference
from erre_sandbox.evidence.tier_b.vendi import DEFAULT_ENCODER_MODEL_ID

_NOW = datetime(2026, 5, 26, tzinfo=UTC)


def _ctx(
    level: AggregationLevel = AggregationLevel.PER_INDIVIDUAL,
    *,
    individual_id: str = "a_kant_001",
    base_persona_id: str = "kant",
) -> MetricContext:
    return MetricContext(
        run_id="run0",
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        aggregation_level=level,
        tick=-1,
        source_epoch_phase="autonomous",
        source_individual_layer_enabled=False,
        source_filter_hash="deadbeef",
    )


def _en_reference() -> BurrowsReference:
    return BurrowsReference(
        language="en",
        function_words=("the", "of", "and"),
        background_mean=(0.05, 0.04, 0.03),
        background_std=(0.02, 0.02, 0.02),
        profile_freq=(0.06, 0.03, 0.02),
    )


# --- burrows ---------------------------------------------------------------


def test_burrows_en_valid() -> None:
    r = burrows_base_retention(
        ["the of and the of and the"],
        language="en",
        reference=_en_reference(),
        ctx=_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None


def _ja_reference() -> BurrowsReference:
    return BurrowsReference(
        language="ja",
        function_words=("の", "に"),
        background_mean=(0.05, 0.04),
        background_std=(0.01, 0.01),
        profile_freq=(0.05, 0.04),
    )


def test_burrows_ja_unsupported() -> None:
    # ja with no preprocessed_tokens adapter stays unsupported (M11-C3a keeps
    # the honest-degrade branch: the built-in tokeniser is en/de only).
    r = burrows_base_retention(
        ["これは日本語の発話である"],
        language="ja",
        reference=None,
        ctx=_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.UNSUPPORTED
    assert r.value is None


def test_burrows_ja_valid_with_preprocessed_tokens() -> None:
    # M11-C3a: ja becomes valid when the runner pre-tokenises with tokenise_ja
    # and feeds the result through preprocessed_tokens.
    from erre_sandbox.evidence.tier_a.burrows import tokenise_ja

    ref = _ja_reference()
    text = "のののにに"
    tokens = tokenise_ja(text, ref.function_words)
    r = burrows_base_retention(
        [text],
        language="ja",
        reference=ref,
        ctx=_ctx(),
        computed_at=_NOW,
        preprocessed_tokens=tokens,
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None


def test_burrows_empty_degenerate() -> None:
    r = burrows_base_retention(
        [], language="en", reference=_en_reference(), ctx=_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.DEGENERATE


def test_burrows_missing_reference_degenerate() -> None:
    r = burrows_base_retention(
        ["the of and"], language="en", reference=None, ctx=_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.DEGENERATE


# --- centroid --------------------------------------------------------------


def _dyad_ctx() -> MetricContext:
    return _ctx(
        AggregationLevel.PER_DYAD,
        individual_id=f"a{DYAD_SEP}b",
        base_persona_id=f"kant{DYAD_SEP}kant",
    )


def test_centroid_valid_with_stub_provider() -> None:
    r = semantic_centroid_distance(
        ["kant utterance one", "kant utterance two"],
        ["a much longer different utterance here entirely"],
        provider=stub_embedding_provider(),
        ctx=_dyad_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None
    assert r.provenance.embedding_model_id == "stub:identity"


def test_centroid_n1_degenerate() -> None:
    r = semantic_centroid_distance(
        ["only one member"],
        None,
        provider=stub_embedding_provider(),
        ctx=_dyad_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.DEGENERATE
    assert r.provenance.embedding_model_id is None


# --- vendi -----------------------------------------------------------------


def _pop_ctx() -> MetricContext:
    return _ctx(AggregationLevel.POPULATION, individual_id=RESERVED_POPULATION_ID)


def test_vendi_valid_with_stub_kernel() -> None:
    r = vendi_diversity(
        ["a", "b", "c"],
        provider=stub_embedding_provider(),
        ctx=_pop_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None
    assert r.provenance.embedding_model_id == "stub:identity"


def test_vendi_single_utterance_degenerate() -> None:
    r = vendi_diversity(
        ["only one"],
        provider=stub_embedding_provider(),
        ctx=_pop_ctx(),
        computed_at=_NOW,
    )
    assert r.status is MetricStatus.DEGENERATE


# --- behavioral ------------------------------------------------------------


def test_cognitive_habit_valid_and_degenerate() -> None:
    valid = cognitive_habit_recall_rate(
        [True, False, True], ctx=_ctx(), computed_at=_NOW
    )
    assert valid.status is MetricStatus.VALID
    assert valid.value == 2 / 3
    degen = cognitive_habit_recall_rate(None, ctx=_ctx(), computed_at=_NOW)
    assert degen.status is MetricStatus.DEGENERATE


def test_action_adherence_valid_and_degenerate() -> None:
    valid = action_adherence_rate([True, True], ctx=_ctx(), computed_at=_NOW)
    assert valid.status is MetricStatus.VALID
    assert valid.value == 1.0
    degen = action_adherence_rate(None, ctx=_ctx(), computed_at=_NOW)
    assert degen.status is MetricStatus.DEGENERATE


def test_zone_consistency_valid_and_degenerate() -> None:
    pref = frozenset({"study", "peripatos"})
    valid = zone_behavior_consistency(
        ["study", "study", "agora"], pref, ctx=_ctx(), computed_at=_NOW
    )
    assert valid.status is MetricStatus.VALID
    assert valid.value == 2 / 3
    no_pref = zone_behavior_consistency([], None, ctx=_ctx(), computed_at=_NOW)
    assert no_pref.status is MetricStatus.DEGENERATE
    no_zone = zone_behavior_consistency(["", ""], pref, ctx=_ctx(), computed_at=_NOW)
    assert no_zone.status is MetricStatus.DEGENERATE


# --- belief_variance -------------------------------------------------------


def test_belief_variance_branches() -> None:
    valid = belief_variance(["trust", "clash", "trust"], ctx=_ctx(), computed_at=_NOW)
    assert valid.status is MetricStatus.VALID
    assert valid.value is not None
    assert 0.0 < valid.value < 1.0
    single = belief_variance(["trust", "trust"], ctx=_ctx(), computed_at=_NOW)
    assert single.status is MetricStatus.DEGENERATE
    absent = belief_variance(None, ctx=_ctx(), computed_at=_NOW)
    assert absent.status is MetricStatus.UNSUPPORTED


# --- never valid -----------------------------------------------------------


def test_swm_jaccard_never_valid() -> None:
    r = world_model_overlap_jaccard(ctx=_dyad_ctx(), computed_at=_NOW)
    assert r.status is MetricStatus.UNSUPPORTED
    assert r.value is None


def test_recovery_never_valid() -> None:
    r = intervention_recovery_rate(ctx=_ctx(), computed_at=_NOW)
    assert r.status is MetricStatus.UNSUPPORTED
    assert r.value is None


# --- M11-C3b: within-individual odd/even floor -----------------------------


def _floor_ctx(individual_id: str = "a_rikyu_001") -> MetricContext:
    return _ctx(individual_id=individual_id, base_persona_id="rikyu")


def test_within_floor_valid_with_stub_provider() -> None:
    # 8 utterances -> even (4) / odd (4); each half >= 4 so valid.
    utts = [f"rikyu utterance number {i} about tea ceremony" for i in range(8)]
    r = semantic_centroid_within_floor(
        utts, provider=stub_embedding_provider(), ctx=_floor_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None
    assert 0.0 <= r.value <= 2.0  # cosine distance range
    assert r.provenance.embedding_model_id == "stub:identity"


def test_within_floor_identical_halves_distance_zero() -> None:
    # All-identical utterances -> even-centroid == odd-centroid -> distance 0.0.
    utts = ["the very same line"] * 8
    r = semantic_centroid_within_floor(
        utts, provider=stub_embedding_provider(), ctx=_floor_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.VALID
    assert r.value == pytest.approx(0.0, abs=1e-9)


def test_within_floor_distinct_halves_positive() -> None:
    # even indices -> "aaaa", odd indices -> "bbbbbbbb": halves differ -> > 0.
    utts = [("aaaa" if i % 2 == 0 else "bbbbbbbb") for i in range(8)]
    r = semantic_centroid_within_floor(
        utts, provider=stub_embedding_provider(), ctx=_floor_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.VALID
    assert r.value is not None
    assert r.value > 0.0


def test_within_floor_degenerate_when_half_below_four() -> None:
    # 7 utterances -> even=4 (idx 0,2,4,6), odd=3 (idx 1,3,5): odd < 4 -> degenerate.
    utts = [f"line {i}" for i in range(7)]
    r = semantic_centroid_within_floor(
        utts, provider=stub_embedding_provider(), ctx=_floor_ctx(), computed_at=_NOW
    )
    assert r.status is MetricStatus.DEGENERATE
    assert r.value is None
    assert r.reason is not None
    assert "per" in r.reason


# --- M11-C3b: build_embedding_provider factory (real-model gated) ----------

_RUN_REAL_MPNET = os.environ.get("ERRE_RUN_REAL_MPNET_TESTS") == "1"
_REAL_MPNET_SKIP = pytest.mark.skipif(
    not _RUN_REAL_MPNET,
    reason=(
        "MPNet (~440MB) download avoided in base CI;"
        " set ERRE_RUN_REAL_MPNET_TESTS=1 to opt-in"
    ),
)


@pytest.mark.eval
@_REAL_MPNET_SKIP
def test_build_embedding_provider_mpnet_byte_equivalent_to_default() -> None:
    """MPNet needs no prefix, so the factory matches the legacy default provider."""
    pytest.importorskip("sentence_transformers")
    batch = ["tea ceremony in the morning", "a different sentence entirely"]
    legacy = default_embedding_provider()
    factored = build_embedding_provider(DEFAULT_ENCODER_MODEL_ID)
    assert (
        factored.embedding_model_id
        == DEFAULT_ENCODER_MODEL_ID
        == (legacy.embedding_model_id)
    )
    assert factored.encoder(batch) == legacy.encoder(batch)
