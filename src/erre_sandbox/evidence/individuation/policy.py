"""Frozen contract for M10-0 individuation metrics (leaf module).

This module imports **nothing** from the rest of the ``individuation``
package — it is the dependency leaf that breaks the import cycle:
the enums and the per-metric
policy live here so that ``models.py`` (validators) and ``ddl.py`` can
both import them without ``ddl`` ever importing ``models``.

What it pins (the *whole* contract is frozen even though Layer 1
metric *implementations* land later):

* :class:`MetricStatus` / :class:`MetricChannel` / :class:`AggregationLevel`
  — the closed enums used by the DDL ``CHECK`` clauses and the model.
* :data:`METRIC_SPECS` — the single source of truth that encodes the
  **claim boundary as code** (M10-0 design): each metric's allowed
  statuses / channels / aggregation
  levels and whether a valid result requires an embedding model id.
  This is what makes "SWM Jaccard / recovery / cite_belief_discipline.*
  are never ``valid`` in M10-0" structurally enforced rather than a
  documentation promise.

The policy is **model/writer-level**, not baked into DB ``CHECK``:
widening a metric's allowed statuses when it goes active
(SWM Jaccard at M10-A, recovery at M11-C) is then a one-line edit here,
not a DuckDB migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

INDIVIDUATION_SCHEMA_VERSION: Final[str] = "m10-0.1"
"""Pinned schema version stamped into every ``MetricResult`` provenance."""


class MetricStatus(StrEnum):
    """Typed extraction outcome (mirrors the DDL ``status`` CHECK)."""

    VALID = "valid"
    DEGENERATE = "degenerate"
    UNSUPPORTED = "unsupported"


class MetricChannel(StrEnum):
    """Input channel a metric draws from (descriptive provenance)."""

    UTTERANCE = "utterance"
    """Burrows / centroid / Vendi — utterance window."""
    BEHAVIORAL = "behavioral"
    """cognitive_habit_recall / action_adherence / zone_behavior."""
    BELIEF_SUBSTRATE = "belief_substrate"
    """belief_variance / cite_belief_discipline.provisional_to_promoted_rate."""
    WORLD_MODEL = "world_model"
    """world_model_overlap_jaccard (SWM Jaccard)."""
    CITATION_SUBSTRATE = "citation_substrate"
    """cite_belief_discipline cited-memory / counterfactual metrics."""
    RECOVERY = "recovery"
    """intervention_recovery_rate."""


class AggregationLevel(StrEnum):
    """Scope a metric row aggregates over (orthogonal to ``tick``)."""

    PER_INDIVIDUAL = "per_individual"
    PER_DYAD = "per_dyad"
    POPULATION = "population"
    RUN = "run"


# ---------------------------------------------------------------------------
# Reserved identifier sentinels for non per-individual aggregation scopes:
# individual_id / base_persona_id are NOT NULL, so a
# population/run row needs a defined value. These tokens make that explicit
# and the model validator enforces the convention.
# ---------------------------------------------------------------------------

RESERVED_POPULATION_ID: Final[str] = "__population__"
"""``individual_id`` for a ``population`` row (aggregate within one base persona)."""

RESERVED_RUN_ID: Final[str] = "__run__"
"""``individual_id`` and ``base_persona_id`` for a ``run`` row."""

DYAD_SEP: Final[str] = "|"
"""Separator for a ``per_dyad`` composite id, e.g. ``"A|B"`` (sorted pair)."""

TICK_AGGREGATE_SENTINEL: Final[int] = -1
"""``tick`` value when a row aggregates over a window/run (no single tick)."""

UNSUPPORTED_PIN_FILTER_HASH: Final[str] = "unsupported:m10-0:cite-belief-discipline:v1"
"""Deterministic ``source_filter_hash`` token for Layer 2 unsupported pins.

The ``source_filter_hash`` column is ``hash or sentinel token``:
a sha256 hex for data-derived rows, or this fixed sentinel for
pins that read no data. It records "this is an unsupported declaration,
not a real input filter".
"""


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """The closed contract for one metric name (claim boundary as code).

    A :class:`~erre_sandbox.evidence.individuation.models.MetricResult` is
    rejected at construction if its ``status`` / ``channel`` /
    ``aggregation_level`` falls outside this spec, or if ``embedding_required``
    is set and a ``valid`` result omits ``embedding_model_id``.
    """

    metric_name: str
    allowed_statuses: frozenset[MetricStatus]
    allowed_channels: frozenset[MetricChannel]
    allowed_aggregation_levels: frozenset[AggregationLevel]
    embedding_required: bool


# Layer 2 metric names — exported because cite_belief.py and the golden
# pin test reference them directly.
CITE_BELIEF_PROVISIONAL_TO_PROMOTED: Final[str] = (
    "cite_belief_discipline.provisional_to_promoted_rate"
)
CITE_BELIEF_CITED_MEMORY_SOURCE_DIST: Final[str] = (
    "cite_belief_discipline.cited_memory_id_source_distribution"
)
CITE_BELIEF_COUNTERFACTUAL_REJECTION: Final[str] = (
    "cite_belief_discipline.counterfactual_challenge_rejection_rate"
)

_S = MetricStatus
_C = MetricChannel
_A = AggregationLevel

METRIC_SPECS: Final[dict[str, MetricSpec]] = {
    # --- Layer 1 active-valid (M10-0) -----------------------------------
    "burrows_base_retention": MetricSpec(
        "burrows_base_retention",
        # en/de valid via the built-in tokeniser; ja valid when the runner
        # supplies tokenise_ja output via preprocessed_tokens (M11-C3a),
        # unsupported when ja arrives without that adapter; empty corpus
        # degenerate.
        frozenset({_S.VALID, _S.DEGENERATE, _S.UNSUPPORTED}),
        frozenset({_C.UTTERANCE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    "semantic_centroid_distance": MetricSpec(
        "semantic_centroid_distance",
        frozenset({_S.VALID, _S.DEGENERATE}),  # N=1 degenerate
        frozenset({_C.UTTERANCE}),
        frozenset({_A.PER_DYAD}),
        embedding_required=True,
    ),
    "semantic_centroid_within_floor": MetricSpec(
        # M11-C3b within-individual odd/even split noise floor (ADR §2.1/§4.2).
        # per_individual raw value; the verdict scorer takes the 3-individual
        # median. degenerate when a half is below the >=4 utterance floor.
        "semantic_centroid_within_floor",
        frozenset({_S.VALID, _S.DEGENERATE}),
        frozenset({_C.UTTERANCE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=True,
    ),
    "vendi_diversity": MetricSpec(
        "vendi_diversity",
        frozenset({_S.VALID, _S.DEGENERATE}),
        frozenset({_C.UTTERANCE}),
        frozenset({_A.POPULATION}),
        embedding_required=True,
    ),
    "cognitive_habit_recall_rate": MetricSpec(
        "cognitive_habit_recall_rate",
        frozenset({_S.VALID, _S.DEGENERATE}),
        frozenset({_C.BEHAVIORAL}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    "action_adherence_rate": MetricSpec(
        "action_adherence_rate",
        frozenset({_S.VALID, _S.DEGENERATE}),
        frozenset({_C.BEHAVIORAL}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    "zone_behavior_consistency": MetricSpec(
        "zone_behavior_consistency",
        frozenset({_S.VALID, _S.DEGENERATE}),
        frozenset({_C.BEHAVIORAL}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    # --- Layer 1 active-if-input-present --------------------------------
    "belief_variance": MetricSpec(
        "belief_variance",
        # valid only when promoted belief records are present, else
        # unsupported; degenerate for single-class input.
        frozenset({_S.VALID, _S.DEGENERATE, _S.UNSUPPORTED}),
        frozenset({_C.BELIEF_SUBSTRATE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    # --- Layer 1 function-only / protocol-only: NEVER valid in M10-0 ----
    "world_model_overlap_jaccard": MetricSpec(
        "world_model_overlap_jaccard",  # SWM Jaccard, active M10-A
        frozenset({_S.DEGENERATE, _S.UNSUPPORTED}),  # ⚠ no VALID
        frozenset({_C.WORLD_MODEL}),
        frozenset({_A.PER_DYAD}),
        embedding_required=False,
    ),
    "intervention_recovery_rate": MetricSpec(
        "intervention_recovery_rate",  # recovery, run M11-C
        frozenset({_S.UNSUPPORTED}),  # ⚠ no VALID
        frozenset({_C.RECOVERY}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    # --- Layer 2 cite_belief_discipline: unsupported pin only -----------
    CITE_BELIEF_PROVISIONAL_TO_PROMOTED: MetricSpec(
        CITE_BELIEF_PROVISIONAL_TO_PROMOTED,
        frozenset({_S.UNSUPPORTED}),
        frozenset({_C.BELIEF_SUBSTRATE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    CITE_BELIEF_CITED_MEMORY_SOURCE_DIST: MetricSpec(
        CITE_BELIEF_CITED_MEMORY_SOURCE_DIST,
        frozenset({_S.UNSUPPORTED}),
        frozenset({_C.CITATION_SUBSTRATE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
    CITE_BELIEF_COUNTERFACTUAL_REJECTION: MetricSpec(
        CITE_BELIEF_COUNTERFACTUAL_REJECTION,
        frozenset({_S.UNSUPPORTED}),
        frozenset({_C.CITATION_SUBSTRATE}),
        frozenset({_A.PER_INDIVIDUAL}),
        embedding_required=False,
    ),
}

ALLOWED_METRIC_NAMES: Final[frozenset[str]] = frozenset(METRIC_SPECS)
"""Closed allow-list of metric names; unknown names are rejected at model build."""


__all__ = [
    "ALLOWED_METRIC_NAMES",
    "CITE_BELIEF_CITED_MEMORY_SOURCE_DIST",
    "CITE_BELIEF_COUNTERFACTUAL_REJECTION",
    "CITE_BELIEF_PROVISIONAL_TO_PROMOTED",
    "DYAD_SEP",
    "INDIVIDUATION_SCHEMA_VERSION",
    "METRIC_SPECS",
    "RESERVED_POPULATION_ID",
    "RESERVED_RUN_ID",
    "TICK_AGGREGATE_SENTINEL",
    "UNSUPPORTED_PIN_FILTER_HASH",
    "AggregationLevel",
    "MetricChannel",
    "MetricSpec",
    "MetricStatus",
]
