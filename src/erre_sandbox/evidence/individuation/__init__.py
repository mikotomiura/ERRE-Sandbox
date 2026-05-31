"""M10-0 individuation metrics (Layer 1 active + Layer 2 unsupported pin).

Measures persona individuation regardless of provenance (LoRA or prompt
persona; M10-0 baseline = no-LoRA / prompt persona, ADR-PM-8 gate
DISCHARGED). Layer 1 active-valid metrics + Layer 2 (Cite-Belief
Discipline) **unsupported pins** are written to the additive
``metrics.individuation`` DuckDB table.

⚠ **Claim boundary** (canonical A16): Layer 2 measures Cite-Belief
Discipline only, **NOT Social-ToM**; in M10-0 it is unsupported pin only,
never active. ``world_model_overlap_jaccard`` (SWM Jaccard) and
``intervention_recovery_rate`` (recovery) are **never ``valid`` in
M10-0** — the :data:`~.policy.METRIC_SPECS` allow-lists enforce this
structurally.

The foundation exposes the typed result, the DDL + policy contract,
and the Layer 2 pins. The loader, Layer 1 metric implementations, CLI
flag, correlation matrix and docs are layered on top.
"""

from __future__ import annotations

from erre_sandbox.evidence.individuation.cite_belief import (
    all_cite_belief_pins,
    cited_memory_id_source_distribution_pin,
    counterfactual_challenge_rejection_rate_pin,
    provisional_to_promoted_rate_pin,
)
from erre_sandbox.evidence.individuation.correlation import (
    CORRELATION_SCHEMA_VERSION,
    CORRELATION_SIDECAR_SUFFIX,
    DOUBLE_MEASUREMENT_THRESHOLD,
    MIN_CORRELATION_OBSERVATIONS,
    CorrelationPair,
    CorrelationReport,
    CorrelationStatus,
    ExcludedMetric,
    correlate_individuation,
    correlation_sidecar_path_for,
    write_correlation_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.ddl import (
    INDIVIDUATION_COLUMN_COUNT,
    TABLE_NAME,
    individuation_ddl_sql,
    row_field_names,
)
from erre_sandbox.evidence.individuation.layer1 import (
    EmbeddingProvider,
    MetricContext,
    default_embedding_provider,
    stub_embedding_provider,
)
from erre_sandbox.evidence.individuation.loader import (
    IndividualWindow,
    IndividuationLoaderError,
    LoadedRun,
    load_individual_windows,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    ALLOWED_METRIC_NAMES,
    INDIVIDUATION_SCHEMA_VERSION,
    METRIC_SPECS,
    UNSUPPORTED_PIN_FILTER_HASH,
    AggregationLevel,
    MetricChannel,
    MetricSpec,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.report import (
    INDIVIDUATION_SIDECAR_SUFFIX,
    IndividuationReport,
    build_report,
    individuation_sidecar_path_for,
    write_individuation_error_sidecar,
    write_individuation_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.runner import (
    IndividuationContext,
    compute_individuation,
)

__all__ = [
    "ALLOWED_METRIC_NAMES",
    "CORRELATION_SCHEMA_VERSION",
    "CORRELATION_SIDECAR_SUFFIX",
    "DOUBLE_MEASUREMENT_THRESHOLD",
    "INDIVIDUATION_COLUMN_COUNT",
    "INDIVIDUATION_SCHEMA_VERSION",
    "INDIVIDUATION_SIDECAR_SUFFIX",
    "METRIC_SPECS",
    "MIN_CORRELATION_OBSERVATIONS",
    "TABLE_NAME",
    "UNSUPPORTED_PIN_FILTER_HASH",
    "AggregationLevel",
    "CorrelationPair",
    "CorrelationReport",
    "CorrelationStatus",
    "EmbeddingProvider",
    "ExcludedMetric",
    "IndividualWindow",
    "IndividuationContext",
    "IndividuationLoaderError",
    "IndividuationReport",
    "LoadedRun",
    "MetricChannel",
    "MetricContext",
    "MetricResult",
    "MetricSpec",
    "MetricStatus",
    "Provenance",
    "all_cite_belief_pins",
    "build_report",
    "cited_memory_id_source_distribution_pin",
    "compute_individuation",
    "correlate_individuation",
    "correlation_sidecar_path_for",
    "counterfactual_challenge_rejection_rate_pin",
    "default_embedding_provider",
    "individuation_ddl_sql",
    "individuation_sidecar_path_for",
    "load_individual_windows",
    "provisional_to_promoted_rate_pin",
    "row_field_names",
    "stub_embedding_provider",
    "write_correlation_sidecar_atomic",
    "write_individuation_error_sidecar",
    "write_individuation_sidecar_atomic",
]
